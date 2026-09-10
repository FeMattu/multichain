"""Starting, supervising and stopping the real MultiChain processes.

Every process the harness starts is registered here before it is started, so
that the cleanup path can terminate it even if the run died between the spawn
and the bookkeeping. That ordering is the whole reliability story: a daemon
the harness forgot about keeps a datadir locked and the next run fails with a
message about the database rather than about the leak.

Stopping is graceful first — the ``stop`` RPC lets MultiChain flush its
databases, and a datadir killed mid-write comes back as
``Corrupted block database detected`` — then ``SIGTERM``, then ``SIGKILL``.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from ...plan import ExperimentPlan, NodePlan
from .rpc import RpcClient

LOG = logging.getLogger("experiments.runtime.multichain.lifecycle")

GRACEFUL_RPC_WAIT_S = 20.0
SIGTERM_WAIT_S = 15.0


@dataclass
class ManagedProcess:
    """One process the harness owns."""

    node_id: str
    kind: str                     # daemon | role
    label: str
    argv: list[str]
    handle: subprocess.Popen | None
    log_path: Path
    started_at: float = field(default_factory=time.time)
    restarts: int = 0

    @property
    def pid(self) -> int | None:
        return self.handle.pid if self.handle else None

    def alive(self) -> bool:
        return self.handle is not None and self.handle.poll() is None

    @property
    def returncode(self) -> int | None:
        return None if self.handle is None else self.handle.poll()

    def as_dict(self) -> dict:
        return {
            "node_id": self.node_id, "kind": self.kind, "label": self.label,
            "pid": self.pid, "alive": self.alive(), "returncode": self.returncode,
            "restarts": self.restarts, "log": str(self.log_path),
            "argv": list(self.argv),
        }


class ProcessRegistry:
    """Everything the harness started, in start order."""

    def __init__(self) -> None:
        self.processes: list[ManagedProcess] = []

    def add(self, process: ManagedProcess) -> ManagedProcess:
        self.processes.append(process)
        return process

    def daemons(self) -> list[ManagedProcess]:
        return [p for p in self.processes if p.kind == "daemon"]

    def for_node(self, node_id: str) -> list[ManagedProcess]:
        return [p for p in self.processes if p.node_id == node_id]

    def alive(self) -> list[ManagedProcess]:
        return [p for p in self.processes if p.alive()]

    def dead_unexpectedly(self) -> list[ManagedProcess]:
        """Daemons that exited on their own: the interesting kind of failure."""
        return [p for p in self.daemons() if not p.alive() and p.returncode not in (0, None)]

    def as_dict(self) -> list[dict]:
        return [p.as_dict() for p in self.processes]


def role_environment(plan: ExperimentPlan, node: NodePlan, run_root: Path, *,
                     daemon: str, treasury_address: str,
                     setup_first_blocks: int) -> dict:
    """The environment every role script reads.

    Peers are addressed by their EMULATED ip: a role script's RPC to another
    node is part of the experiment's traffic and must travel the impaired
    paths. Only the harness's own collectors, which run on the host, use the
    management plane.
    """
    miners = [n.id for n in plan.miners]
    companies = [n.id for n in plan.companies]
    cas = [n.id for n in plan.cas]
    env = {
        "POESIA_RUN": str(run_root),
        "POESIA_CHAIN": plan.multichain.chain,
        "POESIA_DAEMON": daemon,
        "POESIA_SEED": "%s@%s:%d" % (plan.multichain.chain, plan.admin.ip, plan.admin.p2p_port),
        "POESIA_HOST": node.id,
        "POESIA_ROLE": node.role,
        "POESIA_IP": node.ip,
        "POESIA_ADMIN": plan.admin.id,
        "POESIA_ADMIN_IP": plan.admin.ip,
        "POESIA_RPCPORT": plan.multichain.rpc_port,
        "POESIA_P2PPORT": plan.multichain.p2p_port,
        "POESIA_RPCUSER": plan.multichain.rpc_user,
        "POESIA_RPCPASS": plan.multichain.rpc_password,
        "POESIA_MINERS": " ".join(miners),
        "POESIA_COMPANIES": " ".join(companies),
        "POESIA_CAS": " ".join(cas),
        "POESIA_TREASURY": treasury_address,
        "POESIA_EPOCHLEN": plan.epoch_length,
        "POESIA_RNG_SEED": plan.seed,
        "POESIA_SETUPBLOCKS": setup_first_blocks,
        "POESIA_STREAM": plan.multichain.stream,
        "POESIA_CLUSTER": node.cluster,
        "POESIA_GAS_COMPANY": plan.workload["gas_company"],
        "POESIA_GAS_MINER": plan.workload["gas_miner"],
        "POESIA_GAS_THRESHOLD": plan.workload["gas_threshold"],
        "POESIA_GAS_TOPUP": plan.workload["gas_topup"],
        "POESIA_REFILL_EVERY": plan.workload["refill_every_s"],
        "POESIA_EPOCH_POLL": plan.workload["epoch_poll_s"],
        "POESIA_EPOCH_MARGIN": plan.workload["epoch_margin_blocks"],
        "POESIA_RECONCILE_RESERVE": plan.workload["reconcile_reserve_gas"],
    }
    for peer in plan.enabled_nodes:
        env["POESIA_IP_%s" % peer.id] = peer.ip
    if node.role == "miner" and node.reconcile_rate is not None:
        env["POESIA_RECONCILE_RATE"] = node.reconcile_rate
    if node.role == "company" and node.tx_interval_s is not None:
        env["POESIA_TX_INTERVAL"] = node.tx_interval_s
    if node.role == "ca":
        index = [c.id for c in plan.cas].index(node.id) + 1
        env["POESIA_CA_INDEX"] = index
        env["POESIA_CA_COUNT"] = len(plan.cas)
    return {k: str(v) for k, v in env.items()}


def start_daemon(fabric, plan: ExperimentPlan, node: NodePlan, argv: list[str],
                 run_root: Path, registry: ProcessRegistry, env: dict) -> ManagedProcess:
    log_path = run_root / "logs" / node.id / "multichaind.stdout.log"
    process = ManagedProcess(
        node_id=node.id, kind="daemon", label="multichaind", argv=argv,
        handle=None, log_path=log_path,
    )
    registry.add(process)   # registered BEFORE the spawn, so cleanup sees it
    process.handle = fabric.spawn(node.id, argv, stdout=log_path, env=env)
    LOG.info("started multichaind on %s (pid %s)", node.id, process.pid)
    return process


def start_role(fabric, node: NodePlan, script: Path, phase: str, run_root: Path,
               registry: ProcessRegistry, env: dict) -> ManagedProcess:
    argv = ["/usr/bin/env", "bash", str(script)]
    if phase:
        argv.append(phase)
    label = "%s:%s" % (script.stem, phase or "-")
    log_path = run_root / "logs" / node.id / ("role-%s.log" % (phase or script.stem))
    process = ManagedProcess(
        node_id=node.id, kind="role", label=label, argv=argv,
        handle=None, log_path=log_path,
    )
    registry.add(process)
    process.handle = fabric.spawn(node.id, argv, stdout=log_path, env=env)
    LOG.info("started %s on %s (pid %s)", label, node.id, process.pid)
    return process


def stop_daemon_gracefully(client: RpcClient, node_id: str) -> bool:
    """Ask the daemon to stop over RPC and give it time to flush.

    Worth the wait: a datadir killed mid-write comes back as
    ``Corrupted block database detected`` and the run's own artefacts become
    unreadable, which loses the data the run existed to produce.
    """
    _, error = client.try_call("stop", timeout_s=10.0)
    if error is not None:
        LOG.debug("stop RPC to %s did not answer: %s", node_id, error)
        return False
    deadline = time.monotonic() + GRACEFUL_RPC_WAIT_S
    while time.monotonic() < deadline:
        if not client.is_up():
            return True
        time.sleep(1.0)
    return False


def terminate(process: ManagedProcess, *, sigterm_wait_s: float = SIGTERM_WAIT_S) -> str:
    """SIGTERM, then SIGKILL. Returns what it took."""
    if process.handle is None or not process.alive():
        return "already stopped"
    try:
        os.killpg(os.getpgid(process.handle.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        try:
            process.handle.terminate()
        except Exception:  # noqa: BLE001 - best effort
            return "unreachable"
    try:
        process.handle.wait(timeout=sigterm_wait_s)
        return "SIGTERM"
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(os.getpgid(process.handle.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            process.handle.kill()
        except Exception:  # noqa: BLE001
            return "unreachable"
    try:
        process.handle.wait(timeout=5)
    except subprocess.TimeoutExpired:
        return "SIGKILL (still running)"
    return "SIGKILL"


def stop_all(registry: ProcessRegistry, clients: dict[str, RpcClient]) -> dict:
    """Stop everything, roles first, daemons last and gracefully.

    Roles go first so that no traffic generator is still publishing while the
    daemons flush, which would otherwise leave unconfirmed transactions the
    collectors then report as data loss.
    """
    report: dict = {"roles": {}, "daemons": {}}
    for process in reversed(registry.processes):
        if process.kind == "role" and process.alive():
            report["roles"][process.label + "@" + process.node_id] = terminate(process)
    for process in reversed(registry.daemons()):
        if not process.alive():
            report["daemons"][process.node_id] = "already stopped"
            continue
        client = clients.get(process.node_id)
        if client is not None and stop_daemon_gracefully(client, process.node_id):
            report["daemons"][process.node_id] = "stopped over RPC"
            continue
        report["daemons"][process.node_id] = terminate(process)
    return report
