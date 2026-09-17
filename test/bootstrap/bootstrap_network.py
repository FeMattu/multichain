#!/usr/bin/env python3
"""The orchestrator: brings up a wPoA network, drives it, and tears it down.

One command runs the whole thing::

    ./docker/mcsim run python3 test/bootstrap/bootstrap_network.py \\
        --config test/config/profiles/small.yaml

Sequence, in order, each step justified in ``test/docs/architecture-notes.md``:

 1. read and validate the profile;
 2. ``multichain-util create``, then write every parameter into ``params.dat`` — including
    all eight activation keys. The ``enable-wpoa`` master now expands from the file too
    (it used to be inert there), but writing each phase explicitly keeps the file a
    complete statement of what the chain runs rather than something to be re-derived;
 3. start the admin node, wait for RPC, create a **dedicated** treasury address, restart
    every node with ``-weighttreasuryaddress`` so the hash-enforced value is identical;
 4. attach ``admin_daemon.py`` as a separate process — from here on the run is recorded;
 5. join each CA / miner / company to the seed (their first run exits after printing
    the address they are waiting to have granted), grant each what its role needs,
    then launch them as daemons;
 6. create the four streams from the admin **explicitly** (the node's auto-create is
    one-shot per process and was observed to fail), then grant the per-stream write
    permissions, which only become grantable once their stream exists, and seed GAS;
 7. register membership — miners as cluster heads, companies into their assigned cluster —
    and certify every node's ESG score;
 8. note whether the weight registry has become usable — an observation now, not a
    gate: the node falls back to native mining until the first weight confirms, so the
    bootstrap race this used to guard against can no longer happen;
 9. start one ``company_daemon.py`` per company and one ``miner_gas_daemon.py`` per miner,
    as separate tracked processes;
10. drive to the target height, shut everything down, then run phase 1, phase 2,
    phase 3 and the plots — so one command takes a profile and produces a report.
    ``--no-analyze`` stops after the shutdown.

Every child is a real OS process with its own log, individually killable, so a daemon
that misbehaves can be inspected and stopped without touching the rest of the run.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

from config_loader import (  # noqa: E402
    CA_PERMISSION,
    STREAM_ESG,
    STREAM_MALUS,
    STREAM_MEMBERSHIP,
    STREAM_WEIGHTS,
    ConfigError,
    Profile,
    load_profile,
)
from event_log import (  # noqa: E402
    EVENT_GAS_SEEDED,
    EVENT_MEMBERSHIP_REGISTERED,
    EVENT_NODE_STARTED,
    EVENT_PERMISSION_GRANTED,
    EVENT_STREAM_CREATED,
    EventLog,
    run_id as make_run_id,
)
from node_process import NodeRunner, NodeStartError, write_json  # noqa: E402
from rpc_client import TRANSPORT, RpcClient, RpcError, RpcTransportError  # noqa: E402

# Exit codes, so a CI wrapper can tell the failures apart.
EXIT_OK = 0
EXIT_CONFIG = 1
EXIT_ENVIRONMENT = 2
EXIT_RUNTIME = 3
EXIT_INCOMPLETE = 4


class BootstrapError(RuntimeError):
    """The network could not be brought into a state worth measuring."""


def log_step(message: str) -> None:
    print("[bootstrap] %s" % message, flush=True)


class Orchestrator:
    """Owns the run: the nodes, the child daemons and the run directory."""

    def __init__(self, profile: Profile, run_dir: Path, chain_home: Path) -> None:
        self.profile = profile
        self.run_dir = run_dir
        self.chain_home = chain_home
        self.runner = NodeRunner(profile, REPO_ROOT, chain_home)
        self.addresses: Dict[str, str] = {}
        self.clients: Dict[str, RpcClient] = {}
        self.children: List[Tuple[str, subprocess.Popen]] = []
        self.log = EventLog(run_dir, "orchestrator", "admin", epoch_length=profile.epoch_length)
        self.treasury: Optional[str] = None
        self.effective_params: Dict[str, str] = {}
        #: Set once the registry is seen carrying a positive weight. Reported, not gated on.
        self.wpoa_activated = False
        #: The weight distribution observed just before traffic starts, used to split the
        #: malicious quota proportionally. Empty until the registry first fills.
        self.initial_weights: Dict[str, float] = {}
        self._stopping = False

    # -- infrastructure ----------------------------------------------------------------

    def client(self, node_id: str) -> RpcClient:
        if node_id not in self.clients:
            node = self.profile.node(node_id)
            self.clients[node_id] = RpcClient.from_datadir(
                self.chain_home / node_id,
                self.profile.chain_name,
                self.profile.host,
                node.rpc_port,
                node_id=node_id,
                timeout=self.profile.runtime["rpc_timeout_s"],
            )
        return self.clients[node_id]

    @property
    def admin_rpc(self) -> RpcClient:
        return self.client(self.profile.admin.node_id)

    def tip(self) -> int:
        try:
            return self.admin_rpc.block_height()
        except (RpcError, RpcTransportError):
            return 0

    def wait_blocks(self, blocks: int, why: str) -> None:
        """Let the chain confirm what was just broadcast.

        A grant, a stream creation and a publish are all transactions: they change
        nothing until a block carries them. Waiting on *height* rather than on a sleep
        makes the wait correct at any block time.
        """
        start = self.tip()
        timeout = max(30, blocks * self.profile.target_block_time * 6 + 30)
        log_step("waiting %d block(s) for %s (tip %d)" % (blocks, why, start))
        reached = self.admin_rpc.wait_for_height(start + blocks, timeout)
        if reached is None:
            self.log.note("wait timed out", start, blocks=blocks, why=why, timeout_s=timeout)

    # -- 2. the chain ------------------------------------------------------------------

    def create_chain(self) -> None:
        log_step("creating chain %r" % self.profile.chain_name)
        self.runner.require_binaries()
        self.runner.prepare_datadirs()
        params_path = self.runner.create_chain()
        overrides = self.profile.params_overrides()
        written = self.runner.write_params(params_path, overrides)
        self.log.note(
            "params.dat written",
            None,
            path=str(params_path),
            keys=len(written),
            setup_first_blocks_requested=self.profile.setup_first_blocks,
            protocol_floor=self.profile.protocol_setup_floor,
        )

    # -- 3. admin, treasury, restart ---------------------------------------------------

    def start_admin(self) -> None:
        log_step("starting the admin node")
        self.runner.start(self.profile.admin.node_id, join=False)
        info = self.admin_rpc.wait_ready(self.profile.runtime["startup_timeout_s"])
        self.addresses[self.profile.admin.node_id] = self.admin_rpc.own_address()
        self.log.emit(
            EVENT_NODE_STARTED,
            int(info.get("blocks", 0)),
            {
                "node_id": self.profile.admin.node_id,
                "role": "admin",
                "port": self.profile.admin.port,
                "rpc_port": self.profile.admin.rpc_port,
                "address": self.addresses[self.profile.admin.node_id],
            },
        )
        # What the node settled on may differ from what was written: it raises
        # setup-first-blocks to its own floor before the hash is taken.
        params = self.runner.read_params(
            self.chain_home / self.profile.admin.node_id / self.profile.chain_name / "params.dat"
        )
        self.effective_params = params
        effective_setup = int(params.get("setup-first-blocks", 0))
        log_step(
            "effective setup-first-blocks on chain: %d (requested %d, protocol floor %d)"
            % (
                effective_setup,
                self.profile.setup_first_blocks,
                self.profile.protocol_setup_floor,
            )
        )
        if int(params.get("weight-epoch-length", 0)) != self.profile.epoch_length:
            raise BootstrapError(
                "weight-epoch-length on chain is %s, expected %d"
                % (params.get("weight-epoch-length"), self.profile.epoch_length)
            )
        if params.get("enable-weight-engine") != "true":
            raise BootstrapError(
                "enable-weight-engine is %r on chain: the run would measure native "
                "mining, not the weight engine" % params.get("enable-weight-engine")
            )

    def make_treasury(self) -> None:
        """A dedicated address, never the admin's.

        With the admin as treasury a refuel's own change output pays the treasury, and
        only a ``signer == treasury`` guard inside ``mc_AccumulateReconciliation`` spares
        it. That guard is correct, but a harness whose job is to demonstrate the
        direction rule must not depend on it.
        """
        log_step("creating the treasury address")
        address = self.admin_rpc.call("getnewaddress")
        # The grant must CONFIRM before the admin is restarted, or it dies in the mempool
        # and every later `sendfrom` to the treasury fails with
        #   -704 Destination address doesn't have receive permission
        # which silently removes R_k — the only quantity that drives the engine's feedback
        # — while the run otherwise looks healthy. Observed on a probe run.
        self.admin_rpc.try_call("grant", address, "receive")
        self.wait_blocks(2, "the treasury's receive permission to confirm")
        if address == self.addresses[self.profile.admin.node_id]:
            raise BootstrapError("the treasury address collided with the admin's")
        self.treasury = address
        self.runner.treasury_address = address
        # Written immediately, not left to the final manifest: the miner daemons read it
        # at startup, and they start long before this run is over.
        (self.run_dir / "treasury.txt").write_text(address + "\n", encoding="utf-8")
        self.log.note("treasury created", self.tip(), treasury_address=address)

    def restart_admin_with_treasury(self) -> None:
        """``weight-treasury-address`` is hash-enforced, so it goes on every node or none.

        It has to be in force before genesis to sit in ``params.dat``, but an address is
        born with the wallet — so it is passed as a uniform runtime flag instead. The
        admin is restarted here; every other node is started with the flag already set.
        """
        log_step("restarting the admin with -weighttreasuryaddress")
        self.runner.stop(self.profile.admin.node_id, self.profile.runtime["shutdown_grace_s"])
        self.clients.pop(self.profile.admin.node_id, None)
        self.runner.start(self.profile.admin.node_id, join=False)
        self.admin_rpc.wait_ready(self.profile.runtime["startup_timeout_s"])

    # -- 4. the observer ---------------------------------------------------------------

    def start_admin_daemon(self) -> None:
        log_step("attaching admin_daemon.py")
        self.spawn(
            "admin_daemon",
            [
                sys.executable,
                str(HERE / "admin_daemon.py"),
                "--config",
                str(self.profile.path),
                "--run-dir",
                str(self.run_dir),
                "--chain-home",
                str(self.chain_home),
                "--until-height",
                str(self.profile.target_height),
            ],
        )

    def spawn(self, name: str, command: List[str]) -> subprocess.Popen:
        """Start a tracked child in its own process group.

        Its own group, so that stopping one daemon cannot take the orchestrator with it
        and so that a stuck child can be signalled as a unit.
        """
        out_dir = self.run_dir / "logs" / name
        out_dir.mkdir(parents=True, exist_ok=True)
        handle = open(out_dir / "stdout.log", "a", encoding="utf-8", buffering=1)
        handle.write("\n$ %s\n" % " ".join(command))
        process = subprocess.Popen(
            command,
            stdout=handle,
            stderr=subprocess.STDOUT,
            cwd=str(REPO_ROOT),
            start_new_session=True,
        )
        self.children.append((name, process))
        return process

    # -- 5. the rest of the network ----------------------------------------------------

    def join_peers(self) -> None:
        """First launch of every non-admin node: initialise and collect its address.

        A joining node does not become a daemon on this run. With
        ``anyone-can-connect = false`` it fetches the chain parameters from the seed,
        creates its wallet, prints the grant it is waiting for, and exits — the documented
        sequence in ``Create-Blockchain.md`` §5. So the address is read from that output,
        because there is no RPC to ask until the node has been granted ``connect`` and
        started again.

        The joins run **in parallel**. Sequentially each costs seconds of wall clock while
        the seed keeps mining, and at thirty-odd nodes that is hundreds of blocks consumed
        before the first membership record is even published — past ``setup-first-blocks``,
        where wPoA takes over, finds an empty registry, elects nobody and stops. Each join
        talks only to the seed, so they are independent.
        """
        peers = [n for n in self.profile.nodes if not n.is_admin]
        log_step(
            "joining %d peer node(s) to %s" % (len(peers), self.profile.seed_node_address)
        )
        results: Dict[str, object] = {}
        with ThreadPoolExecutor(max_workers=min(16, len(peers))) as pool:
            futures = {
                pool.submit(self.runner.first_launch, node.node_id): node for node in peers
            }
            for future in as_completed(futures):
                node = futures[future]
                try:
                    results[node.node_id] = future.result()
                except Exception as exc:  # reported together, below
                    results[node.node_id] = exc

        failed = {k: v for k, v in results.items() if isinstance(v, Exception)}
        if failed:
            raise BootstrapError(
                "node(s) failed to join: %s"
                % "; ".join("%s: %s" % (k, v) for k, v in sorted(failed.items()))
            )
        for node in peers:
            address = results.get(node.node_id)
            if address:
                self.addresses[node.node_id] = str(address)
        write_json(self.run_dir / "addresses.json", self.addresses)
        log_step("collected %d peer address(es)" % (len(self.addresses) - 1))

    def launch_peers(self) -> None:
        """Second launch: now that the grants are in, bring every peer up as a daemon."""
        peers = [n for n in self.profile.nodes if not n.is_admin]
        log_step("launching %d peer daemon(s)" % len(peers))
        with ThreadPoolExecutor(max_workers=min(16, len(peers))) as pool:
            list(pool.map(lambda n: self.runner.start(n.node_id, join=True), peers))

        deadline = time.time() + self.profile.runtime["startup_timeout_s"] * 2
        pending = {n.node_id for n in peers}
        while pending and time.time() < deadline:
            for node_id in sorted(pending):
                try:
                    self.client(node_id).call("getinfo")
                    # A node whose datadir already existed never printed a grant hint, so
                    # its address is only available now.
                    self.addresses.setdefault(node_id, self.client(node_id).own_address())
                    pending.discard(node_id)
                except (RpcError, RpcTransportError):
                    continue
            if pending:
                time.sleep(2.0)
        if pending:
            raise BootstrapError(
                "node(s) did not serve RPC: %s. See <run>/chains/<node>/daemon.out"
                % ", ".join(sorted(pending))
            )

        tip = self.tip()
        for node in peers:
            self.log.emit(
                EVENT_NODE_STARTED,
                tip,
                {
                    "node_id": node.node_id,
                    "role": node.role,
                    "port": node.port,
                    "rpc_port": node.rpc_port,
                    "address": self.addresses[node.node_id],
                },
            )
        write_json(self.run_dir / "addresses.json", self.addresses)
        self.wait_peers_connected()

    def wait_peers_connected(self) -> None:
        """Wait until the admin actually sees the peers.

        A node that has been granted ``connect`` still has to dial the seed and complete
        the handshake. Proceeding before that means granting stream permissions to
        addresses whose nodes cannot yet see the transactions carrying them, which is
        recoverable but wastes a slice of the setup-phase budget.
        """
        expected = self.profile.node_count - 1
        deadline = time.time() + max(60, expected * 4)
        seen = 0
        while time.time() < deadline:
            try:
                seen = len(self.admin_rpc.call("getpeerinfo") or [])
            except (RpcError, RpcTransportError):
                seen = 0
            if seen >= expected:
                log_step("all %d peer(s) connected to the seed" % seen)
                return
            time.sleep(2.0)
        log_step("WARNING: only %d/%d peer(s) connected to the seed" % (seen, expected))
        self.log.note("peers not fully connected", self.tip(), seen=seen, expected=expected)

    def _grant_address(self, address: str, permission: str, tip: int, label: str) -> bool:
        """Grant to a bare address. The treasury is not a node and has no node_id."""
        ok, result = self.admin_rpc.try_call("grant", address, permission)
        if ok:
            self.log.emit(
                EVENT_PERMISSION_GRANTED,
                tip,
                {"node_id": label, "role": label, "permission": permission, "txid": result},
                node_address=address,
            )
            return True
        self.log.rpc_error("grant", result, tip, node_id=label, permission=permission)
        return False

    def verify_treasury_receivable(self) -> None:
        """The treasury must be able to receive, or R_k is silently always zero.

        Checked rather than assumed because the failure is invisible from the outside: the
        miners keep trying, every `sendfrom` is rejected, and the run completes with a
        perfectly flat rho that reads as "the feedback channel is inert" rather than as a
        broken permission.
        """
        if not self.treasury:
            return
        ok, result = self.admin_rpc.try_call("listpermissions", "receive", self.treasury, False)
        if ok and result:
            log_step("treasury %s holds receive" % self.treasury[:12])
            return
        raise BootstrapError(
            "the treasury address %s does not hold `receive`. Every miner restitution "
            "would fail with -704 and R_k would be zero for every cluster, making the "
            "WeightEngine's only feedback channel inert without any visible error."
            % self.treasury
        )

    def _grant(self, node, permission: str, tip: int) -> bool:
        """One grant. One call per permission — MultiChain rejects comma-joined entity keys."""
        address = self.addresses[node.node_id]
        ok, result = self.admin_rpc.try_call("grant", address, permission)
        if ok:
            self.log.emit(
                EVENT_PERMISSION_GRANTED,
                tip,
                {
                    "node_id": node.node_id,
                    "role": node.role,
                    "permission": permission,
                    "txid": result,
                },
                node_address=address,
            )
            return True
        self.log.rpc_error("grant", result, tip, node_id=node.node_id, permission=permission)
        return False

    def grant_global_permissions(self) -> None:
        """Global permissions, before the peers are launched.

        Only the ones that do not name an entity. A stream permission cannot be granted
        before its stream exists — the node answers ``-708 Entity with this name not
        found`` — so those wait for :meth:`grant_stream_permissions`. Splitting the two
        passes is not tidiness: granting them together silently loses every stream
        permission, and the first visible symptom is ``weightregistermembership`` failing
        with ``-704 lacks write permission`` several steps later.
        """
        log_step("granting global permissions")
        tip = self.tip()
        granted = 0
        for node in self.profile.nodes:
            if node.is_admin:
                continue
            granted += self._grant(node, "connect,send,receive", tip)
            if node.role == "miner":
                granted += self._grant(node, "mine", tip)
            if node.role == "ca":
                # The Certification Authority role. The administrator confers it and does
                # NOT hold it automatically: "who administers the network" stays
                # distinguishable on chain from "who certifies ESG scores".
                granted += self._grant(node, CA_PERMISSION, tip)
        # Re-asserted rather than assumed: the grant issued at treasury creation had to
        # survive the admin restart, and a grant is idempotent so repeating it is free.
        if self.treasury:
            self._grant_address(self.treasury, "receive", tip, "treasury")
            granted += 1
        log_step("issued %d global grant(s)" % granted)
        self.wait_blocks(2, "global grants to confirm")
        self.verify_treasury_receivable()

    def grant_stream_permissions(self) -> None:
        """Per-stream write permissions, once the streams exist."""
        log_step("granting stream permissions")
        tip = self.tip()
        event_stream = self.profile.traffic["event_stream"]
        granted = 0
        for node in self.profile.nodes:
            # Every node, not only miners: a wpoa-weights record is self-attested and
            # independently recomputable, so the grant is safe, and a narrow grant would
            # break the moment a company were promoted to cluster head.
            granted += self._grant(node, "%s.write" % STREAM_WEIGHTS, tip)
            granted += self._grant(node, "%s.write" % STREAM_MEMBERSHIP, tip)
            if node.role == "ca":
                granted += self._grant(node, "%s.write" % STREAM_ESG, tip)
            if node.role == "company":
                granted += self._grant(node, "%s.write" % event_stream, tip)
        log_step("issued %d stream grant(s)" % granted)
        expected = 2 * self.profile.node_count + self.profile.ca_count + self.profile.company_count
        if granted < expected:
            raise BootstrapError(
                "only %d of %d stream permissions were granted. A node without "
                "weight-engine-membership.write cannot join a cluster, and a miner that "
                "heads no cluster never receives a published weight."
                % (granted, expected)
            )
        self.wait_blocks(3, "stream grants to confirm")

    def create_streams(self) -> None:
        """Create every stream explicitly, from the admin.

        **Kept deliberately, though the node's auto-create now works.** It used to be a
        workaround: the auto-create latched "attempted" before the attempt and never
        retried, so on a probe run it produced only ``weight-engine-esg`` and left the
        registry permanently empty. That is fixed (``fix(wpoa): ... retry stream
        creation``) and all four streams now appear on their own.

        The explicit creation stays anyway, for a reason the fix does not remove: it makes
        stream existence a *precondition* of the bootstrap rather than something that
        happens concurrently with it. The harness grants per-stream write permissions in
        the very next step, and an entity permission cannot be granted before its entity
        exists. Relying on the auto-create would make that ordering depend on when the
        engine thread next ticked — fine in practice, but a timing dependency in the one
        part of a measurement harness that must not have any.

        The informative stream would have to be created here in any case: the node knows
        nothing about it.

        The first four are **closed**: an open informative stream would let any node with
        ``send`` publish, making the informative traffic indistinguishable from anything
        else on the chain. The malus stream is **open**, matching the node's own creation.
        """
        log_step("creating streams")
        tip = self.tip()
        # The three closed protocol streams, plus the informative one. The malus stream is
        # created OPEN, matching how the node's own ThreadMalusRegistry creates it: a
        # report's safety rests on its content being checkable, not on who may speak.
        streams = [
            (STREAM_WEIGHTS, False),
            (STREAM_MEMBERSHIP, False),
            (STREAM_ESG, False),
            (self.profile.traffic["event_stream"], False),
            (STREAM_MALUS, True),
        ]
        for stream, is_open in streams:
            ok, result = self.admin_rpc.try_call("create", "stream", stream, is_open)
            self.log.emit(
                EVENT_STREAM_CREATED,
                tip,
                {
                    "stream": stream,
                    "open": is_open,
                    "txid": result if ok else None,
                    "already_present": not ok,
                    "error": None if ok else str(result),
                },
            )
        self.wait_blocks(2, "stream creation to confirm")
        for stream, _ in streams:
            for node in self.profile.nodes:
                self.client(node.node_id).try_call("subscribe", stream, False)

    def seed_gas(self) -> None:
        """Fund every node from the premine. Admin -> node only; never node -> node.

        A company must not run dry mid-epoch: it would stop generating ``tau`` and that
        epoch's weight would silently understate it. Miners are funded too — they earn
        fees, but not before they have mined, and epoch 1 would otherwise find them with
        nothing to return.
        """
        log_step("seeding GAS from the premine")
        balance = self.admin_rpc.native_balance()
        if balance <= 0:
            raise BootstrapError(
                "the admin holds no native currency: first-block-reward did not take "
                "effect. Without it R_k is 0, rho is pinned and every economic result "
                "below would be vacuous."
            )
        tip = self.tip()
        seeded = 0
        for node in self.profile.nodes:
            if node.is_admin:
                continue
            amount = (
                self.profile.miner_seed_gas
                if node.role == "miner"
                else self.profile.gas_seed
            )
            ok, result = self.admin_rpc.try_call(
                "sendtoaddress", self.addresses[node.node_id], amount
            )
            if ok:
                seeded += 1
                self.log.emit(
                    EVENT_GAS_SEEDED,
                    tip,
                    {
                        "node_id": node.node_id,
                        "role": node.role,
                        "amount": amount,
                        "txid": result,
                    },
                    node_address=self.addresses[node.node_id],
                )
            else:
                self.log.rpc_error("sendtoaddress", result, tip, node_id=node.node_id)
        log_step("funded %d/%d node(s) (admin balance %.4f)" % (seeded, len(self.profile.nodes) - 1, balance))
        if seeded < self.profile.node_count - 1:
            raise BootstrapError(
                "only %d of %d nodes were funded; the unfunded ones cannot pay a fee and "
                "would generate no activity at all"
                % (seeded, self.profile.node_count - 1)
            )
        self.wait_blocks(3, "GAS to confirm")

    def register_membership(self) -> None:
        """Miners declare themselves cluster heads; companies join their assigned cluster.

        This is the single most load-bearing call in the bootstrap. The cluster map is
        built *only* from confirmed membership records, and a miner that is not a key of
        that map is never computed and never published — silently, with no error. Without
        this step the registry stays empty and the chain stops when wPoA engages.
        """
        log_step("registering cluster membership")
        tip = self.tip()
        assignment = self.profile.cluster_assignment()
        write_json(self.run_dir / "clusters.json", assignment)
        plan: List[Tuple[str, str]] = []
        for miner in self.profile.by_role("miner"):
            plan.append((miner.node_id, miner.node_id))  # a miner registers itself
        for company_id, miner_id in assignment.items():
            plan.append((company_id, miner_id))
        # CAs and the admin declare nothing: they head no cluster and belong to none, so
        # a record would only add a member whose tau the analysis would have to explain.

        ok_count = 0
        for node_id, miner_id in plan:
            miner_address = self.addresses[miner_id]
            try:
                txid = self.client(node_id).call("weightregistermembership", miner_address)
            except (RpcError, RpcTransportError) as exc:
                self.log.rpc_error(
                    "weightregistermembership",
                    exc,
                    tip,
                    node_id=node_id,
                    miner_node_id=miner_id,
                )
                continue
            ok_count += 1
            self.log.emit(
                EVENT_MEMBERSHIP_REGISTERED,
                tip,
                {
                    "txid": txid,
                    "node_id": node_id,
                    "miner_node_id": miner_id,
                    "miner_address": miner_address,
                    "is_cluster_head": node_id == miner_id,
                },
                node_address=self.addresses[node_id],
            )
        log_step("registered %d/%d membership record(s)" % (ok_count, len(plan)))
        if ok_count < len(self.profile.by_role("miner")):
            raise BootstrapError(
                "not every miner registered as a cluster head; those that did not will "
                "never receive a published weight"
            )

    def assign_esg(self) -> None:
        log_step("certifying ESG scores")
        from ca_assign_esg import assign  # local import: keeps the module independently runnable

        summary = assign(self.profile, self.run_dir, self.chain_home, self.addresses, self.log)
        log_step(
            "ESG: %d/%d published (%d failed)"
            % (summary["published"], summary["planned"], summary["failed"])
        )
        if summary["published"] == 0:
            raise BootstrapError(
                "no ESG score was published: every cluster would compute W_k = 0 and "
                "publish the positivity floor of 1, making the sortition uniform"
            )
        self.wait_blocks(4, "membership and ESG to confirm")

    # -- 8. readiness ------------------------------------------------------------------

    def observe_registry_activation(self) -> None:
        """Report when the registry first becomes usable. Never blocks the run.

        **This used to be the anti-deadlock guard**, and it is not needed as one any more.
        It blocked until a validator carried a non-zero weight and failed the run if the
        tip reached ``setup-first-blocks`` first, because at that moment wPoA took over a
        registry that could not name a proposer and the chain stopped dead.

        The node no longer does that: while no positive weight has ever been confirmed it
        keeps mining under the native MultiChain rules and lets wPoA activate by itself
        (``fix(wpoa): defer activation...``). So the race this guarded against cannot
        happen, and waiting for it only delayed the run.

        What remains is a *data-quality* observation, not a gate. If the registry never
        fills, the run is still valid as a run — the chain advances — but it measures
        native mining rather than a weighted election, and that is worth knowing early.
        Hence: look for a short while, say what was found, and proceed either way. The
        binding check happens after the fact, in
        :meth:`check_wpoa_activated` and in phase 3.
        """
        want = max(1, len(self.profile.by_role("miner")) // 2)
        budget = max(60, self.profile.epoch_length * self.profile.target_block_time * 2)
        log_step(
            "looking for >= %d validator(s) with a non-zero weight (up to %ds, "
            "non-blocking)" % (want, budget)
        )
        deadline = time.time() + budget
        while time.time() < deadline:
            tip = self.tip()
            try:
                weights = self.admin_rpc.call("getallweights").get("weights", {})
            except (RpcError, RpcTransportError):
                weights = {}
            scoreable = sum(1 for w in weights.values() if float(w or 0) > 0)
            if scoreable >= want:
                log_step(
                    "registry usable: %d scoreable validator(s) at height %d"
                    % (scoreable, tip)
                )
                self.log.note("registry usable", tip, scoreable=scoreable, weights=weights)
                self.wpoa_activated = True
                self._capture_initial_weights(weights)
                return
            time.sleep(3.0)

        tip = self.tip()
        log_step(
            "registry not yet usable at height %d — proceeding anyway; the node mines "
            "under the native rules until the first weight confirms" % tip
        )
        self.log.note("registry not yet usable at start of traffic", tip, wanted=want)

    def _capture_initial_weights(self, weights: Dict[str, Any]) -> None:
        """Map ``getallweights`` (address -> weight) onto miner node_ids.

        The malicious quota split is by node_id, so the address-keyed registry answer is
        translated here. A miner with no confirmed weight yet is simply absent, and the
        quota split then falls back to uniform for the whole set — recorded as such.
        """
        address_to_node = {
            self.addresses.get(n.node_id): n.node_id for n in self.profile.by_role("miner")
        }
        for address, weight in (weights or {}).items():
            node_id = address_to_node.get(address)
            if node_id is not None:
                try:
                    self.initial_weights[node_id] = float(weight or 0.0)
                except (TypeError, ValueError):
                    continue

    def write_malicious_manifest(self) -> None:
        """Freeze the malicious plan to ``<run>/malicious_manifest.json``.

        Written before the miner daemons start, because a selected miner reads it at
        startup, and written unconditionally — a disabled plan too — so phase 1 always
        finds one file of a known shape rather than having to tell "off" from "old". The
        addresses and the observed initial weights are folded in here, since neither
        exists at profile-load time.
        """
        plan = self.profile.malicious_plan(
            addresses=self.addresses, initial_weights=self.initial_weights or None
        )
        write_json(self.run_dir / "malicious_manifest.json", plan)
        if plan.get("enabled"):
            log_step(
                "malicious experiment: %d/%d miner(s) selected (%s), rate %.2f, split %s"
                % (
                    len(plan["malicious_miner_ids"]),
                    len(plan["all_miner_ids"]),
                    ", ".join(plan["malicious_miner_ids"]),
                    plan["target_action_rate"],
                    plan["quota_share_source"],
                )
            )
            self.log.note(
                "malicious plan frozen",
                self.tip(),
                seed=plan["seed"],
                malicious_miner_ids=plan["malicious_miner_ids"],
                per_miner_target_rate=plan["per_miner_target_rate"],
                quota_share_source=plan["quota_share_source"],
            )

    def check_wpoa_activated(self, tip: int) -> None:
        """After the run: did wPoA ever actually take over?

        The replacement for the guard above, and deliberately at the other end of the run.
        A registry that is still empty after several epochs is not a protocol deadlock any
        more — it means something upstream never happened: membership was not registered,
        no ESG score was certified, or the engine never got far enough to publish. That is
        a real defect, it is just not the one the old guard described, and it is only
        diagnosable once there has been time for it to have happened.
        """
        try:
            weights = self.admin_rpc.call("getallweights").get("weights", {})
        except (RpcError, RpcTransportError):
            weights = {}
        scoreable = sum(1 for w in weights.values() if float(w or 0) > 0)
        self.wpoa_activated = self.wpoa_activated or scoreable > 0
        epochs = self.profile.last_buried_epoch(tip)
        self.log.note(
            "wPoA activation check", tip, scoreable=scoreable, buried_epochs=epochs,
            activated=self.wpoa_activated,
        )
        if self.wpoa_activated:
            log_step("wPoA activated during the run (%d scoreable validator(s))" % scoreable)
            return
        log_step(
            "WARNING: wPoA never activated — %d buried epoch(s) and still no positive "
            "weight. The chain ran under the native rules throughout, so the election "
            "results measure round robin, not weighted sortition. Look upstream: "
            "membership registration, ESG certification, or the engine's own thread."
            % epochs
        )

    # -- 9. traffic --------------------------------------------------------------------

    def start_traffic(self) -> None:
        log_step("starting the traffic daemons")
        # The plan must be on disk before any miner daemon starts: a selected miner reads
        # it at startup to know it is malicious and what its target rate is.
        self.write_malicious_manifest()
        traffic_dir = REPO_ROOT / "test" / "traffic"
        common = [
            "--config",
            str(self.profile.path),
            "--run-dir",
            str(self.run_dir),
            "--chain-home",
            str(self.chain_home),
        ]
        self.spawn(
            "run_company_daemons",
            [sys.executable, str(traffic_dir / "run_company_daemons.py")] + common,
        )
        self.spawn(
            "run_miner_daemons",
            [sys.executable, str(traffic_dir / "run_miner_daemons.py")] + common,
        )
        # The honest detector runs only when there is something to detect. One process,
        # on the admin, so every offence is reported at most once (§ malus_detector).
        if self.profile.malicious_enabled:
            self.spawn(
                "malus_detector",
                [sys.executable, str(HERE / "malus_detector.py")] + common,
            )

    # -- 10. drive and stop ------------------------------------------------------------

    def drive(self) -> int:
        """Watch the height until the target is reached, refuelling as needed."""
        target = self.profile.target_height
        log_step("driving to height %d (%d epochs of %d blocks)"
                 % (target, self.profile.epoch_count, self.profile.epoch_length))
        timeout = target * self.profile.target_block_time * 6 + 600
        deadline = time.time() + timeout
        last_report = -1
        stalled_since = time.time()
        last_tip = -1

        while time.time() < deadline:
            tip = self.tip()
            if tip != last_tip:
                last_tip, stalled_since = tip, time.time()
            elif time.time() - stalled_since > self.profile.target_block_time * 60 + 300:
                self.log.note("chain appears stalled", tip)
                log_step("WARNING: no new block for a long time at height %d" % tip)
                stalled_since = time.time()

            epoch = self.profile.last_buried_epoch(tip)
            if epoch != last_report:
                # Reported against setup-first-blocks rather than against epochs.count:
                # the epochs that matter are the ones past the setup phase, and the target
                # height is usually driven by the setup budget rather than by the count.
                setup = int(
                    self.effective_params.get(
                        "setup-first-blocks", self.profile.setup_first_blocks
                    )
                )
                measured = max(0, epoch - self.profile.epoch_of_height(setup))
                log_step(
                    "height %d / %d — buried epoch %d (%d past the setup phase)"
                    % (tip, target, epoch, measured)
                )
                last_report = epoch
            if tip >= target:
                return tip
            self.refuel()
            time.sleep(5.0)

        tip = self.tip()
        self.log.note("drive timed out", tip, target=target)
        log_step("WARNING: timed out at height %d, target was %d" % (tip, target))
        return tip

    def refuel(self) -> None:
        """Top up any node that has fallen below the floor. Admin -> node only."""
        from event_log import EVENT_GAS_REFUELLED

        for node in self.profile.nodes:
            if node.is_admin:
                continue
            try:
                balance = self.client(node.node_id).native_balance()
            except (RpcError, RpcTransportError):
                continue
            if balance >= self.profile.gas_floor:
                continue
            ok, result = self.admin_rpc.try_call(
                "sendtoaddress", self.addresses[node.node_id], self.profile.gas_topup
            )
            if ok:
                self.log.emit(
                    EVENT_GAS_REFUELLED,
                    self.tip(),
                    {
                        "node_id": node.node_id,
                        "role": node.role,
                        "balance_before": balance,
                        "amount": self.profile.gas_topup,
                        "txid": result,
                    },
                    node_address=self.addresses[node.node_id],
                )

    def stop_children(self) -> None:
        """Signal the traffic daemons and the observer, then wait."""
        if self._stopping:
            return
        self._stopping = True
        (self.run_dir / "STOP").write_text("stop\n", encoding="utf-8")
        for name, process in self.children:
            if process.poll() is None:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                except OSError:
                    process.terminate()
        deadline = time.time() + self.profile.runtime["shutdown_grace_s"]
        for name, process in self.children:
            remaining = max(1, int(deadline - time.time()))
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                log_step("child %s did not stop; killing" % name)
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except OSError:
                    process.kill()

    # -- manifest ----------------------------------------------------------------------

    def write_manifest(self, final_height: int, status: str, error: str = "") -> None:
        manifest = self.profile.manifest()
        manifest.update(
            {
                "run_dir": str(self.run_dir),
                "chain_home": str(self.chain_home),
                "status": status,
                "error": error,
                "final_height": final_height,
                "treasury_address": self.treasury,
                "addresses": self.addresses,
                "clusters": self.profile.cluster_assignment(),
                "effective_chain_params": self.effective_params,
                "effective_setup_first_blocks": int(
                    self.effective_params.get("setup-first-blocks", 0) or 0
                ),
                "rpc_transport": TRANSPORT,
                "measured_epochs": self.profile.last_buried_epoch(final_height),
                "wpoa_activated": self.wpoa_activated,
                "stability_margin": 6,
                # The resolved plan, with the addresses and the observed initial weights
                # folded in — the same object written to malicious_manifest.json, repeated
                # here so a reader of the run manifest alone sees who misbehaved.
                "malicious_plan": self.profile.malicious_plan(
                    addresses=self.addresses,
                    initial_weights=self.initial_weights or None,
                ),
            }
        )
        write_json(self.run_dir / "manifest.json", manifest)


def run(profile: Profile, run_dir: Path, chain_home: Path) -> int:
    orchestrator = Orchestrator(profile, run_dir, chain_home)
    status, error, final_height = "ok", "", 0
    try:
        orchestrator.create_chain()
        orchestrator.start_admin()
        orchestrator.make_treasury()
        orchestrator.restart_admin_with_treasury()
        orchestrator.start_admin_daemon()
        # join -> grant -> launch, in that order: a joining node exits on its first run
        # and only serves RPC once it has been granted connect (Create-Blockchain.md 5).
        orchestrator.join_peers()
        orchestrator.grant_global_permissions()
        orchestrator.launch_peers()
        orchestrator.create_streams()
        # Entity permissions only exist once their entity does, so this pass has to
        # follow stream creation rather than ride along with the global one.
        orchestrator.grant_stream_permissions()
        orchestrator.seed_gas()
        orchestrator.register_membership()
        orchestrator.assign_esg()
        orchestrator.observe_registry_activation()
        orchestrator.start_traffic()
        final_height = orchestrator.drive()
    except BootstrapError as exc:
        status, error = "failed", str(exc)
        log_step("FAILED: %s" % exc)
    except (NodeStartError, RpcTransportError) as exc:
        status, error = "environment", str(exc)
        log_step("ENVIRONMENT FAILURE: %s" % exc)
    except KeyboardInterrupt:
        status, error = "interrupted", "interrupted by the operator"
        log_step("interrupted")
    finally:
        try:
            orchestrator.stop_children()
            final_height = max(final_height, orchestrator.tip())
            orchestrator.write_manifest(final_height, status, error)
        finally:
            # Teardown lives in shutdown/stop_network.py so that an interrupted run can
            # be cleaned up with exactly the same code path from the command line.
            sys.path.insert(0, str(REPO_ROOT / "test" / "shutdown"))
            from stop_network import stop_network  # noqa: E402

            report = stop_network(profile, run_dir, chain_home, snapshot=True)
            log_step("nodes stopped: %s" % json.dumps(report.get("nodes", {})))
            orchestrator.log.note("nodes stopped", final_height, **report)
            orchestrator.log.close()

    if status == "ok":
        log_step("run complete at height %d -> %s" % (final_height, run_dir))
        return EXIT_OK
    if status == "environment":
        return EXIT_ENVIRONMENT
    if status == "interrupted":
        return EXIT_INCOMPLETE
    return EXIT_RUNTIME


def run_analysis(profile: Profile, run_dir: Path) -> int:
    """phase 1 -> phase 2 -> phase 3 -> plots, in the one process that owns the run.

    Chained here so that a single command takes a profile and produces a report. Each
    phase is still independently runnable against a finished run directory — which is
    what one wants when re-analysing without re-running the network.

    A failure in one phase stops the chain: phase 2 on absent phase-1 tables would
    produce empty tables rather than an error, and empty tables read as "nothing
    happened".
    """
    analysis_dir = REPO_ROOT / "test" / "analysis" / "pipeline"
    steps = [
        ("phase1", [sys.executable, str(analysis_dir / "phase1_collect.py")]),
        ("phase2", [sys.executable, str(analysis_dir / "phase2_aggregate.py")]),
        ("phase3", [sys.executable, str(analysis_dir / "phase3_analyze.py")]),
        ("plots", [sys.executable, str(REPO_ROOT / "test" / "plotting" / "generate_plots.py")]),
    ]
    common = ["--config", str(profile.path), "--run-dir", str(run_dir)]
    for name, command in steps:
        log_step("running %s" % name)
        result = subprocess.run(command + common, cwd=str(REPO_ROOT))
        if result.returncode != 0:
            # phase 3 returns 2 when a critical consistency check failed: the analysis
            # itself completed and its report is worth reading, so the chain continues to
            # the plots and the code is carried out to the caller.
            if name == "phase3" and result.returncode == 2:
                log_step("phase3 reported a critical consistency failure — see report.md")
                subprocess.run(steps[-1][1] + common, cwd=str(REPO_ROOT))
                return EXIT_INCOMPLETE
            log_step("%s failed with code %d" % (name, result.returncode))
            return EXIT_RUNTIME
    return EXIT_OK


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", required=True, help="path to the profile YAML")
    parser.add_argument("--run-dir", default=None, help="override the run directory")
    parser.add_argument("--chain-home", default=None, help="override the datadir root")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate the profile, print the derived plan, and stop",
    )
    parser.add_argument(
        "--no-analyze",
        action="store_true",
        help="stop after the shutdown instead of running phase1-3 and the plots",
    )
    args = parser.parse_args(argv)

    try:
        profile = load_profile(args.config)
    except ConfigError as exc:
        print("[bootstrap] configuration error: %s" % exc, file=sys.stderr)
        return EXIT_CONFIG

    run_dir = (
        Path(args.run_dir)
        if args.run_dir
        else REPO_ROOT / profile.runtime["results_root"] / make_run_id(profile.chain_name)
    )
    chain_home = (
        Path(args.chain_home)
        if args.chain_home
        else Path(profile.runtime["chain_home"] or (run_dir / "chains"))
    )

    if args.dry_run:
        plan = profile.manifest()
        plan["run_dir"] = str(run_dir)
        plan["chain_home"] = str(chain_home)
        print(json.dumps(plan, indent=2, default=str))
        return EXIT_OK

    run_dir.mkdir(parents=True, exist_ok=True)
    chain_home.mkdir(parents=True, exist_ok=True)
    log_step("run directory: %s" % run_dir)
    log_step(
        "plan: %d nodes (1 admin, %d CA, %d miners, %d companies), %d epochs of %d blocks, "
        "target height %d, RPC transport %s"
        % (
            profile.node_count,
            profile.ca_count,
            profile.miner_count,
            profile.company_count,
            profile.epoch_count,
            profile.epoch_length,
            profile.target_height,
            TRANSPORT,
        )
    )
    code = run(profile, run_dir, chain_home)
    if args.no_analyze:
        log_step("analysis skipped (--no-analyze); run it later with:")
        log_step("    python3 test/analysis/pipeline/phase1_collect.py --config %s --run-dir %s"
                 % (profile.path, run_dir))
        return code
    if code not in (EXIT_OK, EXIT_INCOMPLETE):
        log_step("the network run failed, so there is nothing worth analysing")
        return code

    analysis_code = run_analysis(profile, run_dir)
    log_step("report:              %s/analysis/phase3/report.md" % run_dir)
    log_step("headline comparison: %s/analysis/phase3/weight_vs_election.md" % run_dir)
    log_step("figures:             %s/analysis/plots/" % run_dir)
    return code if code != EXIT_OK else analysis_code


if __name__ == "__main__":
    raise SystemExit(main())
