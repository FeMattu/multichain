"""Sealing ``params.dat`` and laying out the per-node data directories.

This is the only step that touches the chain before any daemon starts, and it
is deliberately small: ``multichain-util create`` writes ``params.dat``, the
harness edits the keys that ``create`` does not take as flags, and each node
gets a ``multichain.conf``. Everything else — the genesis itself, permissions,
streams, ESG, membership, GAS — happens on the running network, because that
is where it happens in reality.

Two things here are load-bearing and were learned the hard way in the Shadow
suite:

* ``multichain-util`` may **raise** ``setup-first-blocks`` to a floor it
  derives at genesis. The effective value is therefore re-read from the written
  ``params.dat`` and it, not the configured one, decides the measurement
  window. Skipping the re-read shortens the window silently.
* ``maxtxfee`` must be raised together with ``minimum-relay-fee``. The wallet
  caps a transaction's fee at 0.1 native units by default; with a relay fee of
  0.2 GAS per 1000 bytes every stream publication above ~500 bytes exceeds
  that cap and ``CreateTransaction`` refuses it. The symptom is a network that
  looks healthy while no record is ever published.
"""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from ...chain_params import ChainParams, read_params_dat
from ...exit_codes import RuntimeFailure
from ...plan import ExperimentPlan
from .treasury import Treasury

LOG = logging.getLogger("experiments.runtime.multichain.initialize")


@dataclass
class InitResult:
    """What sealing the chain produced."""

    params_path: Path
    configured_setup_first_blocks: int
    effective_setup_first_blocks: int
    effective_params: dict
    treasury_address: str
    log_path: Path

    @property
    def setup_was_raised(self) -> bool:
        return self.effective_setup_first_blocks > self.configured_setup_first_blocks

    def as_dict(self) -> dict:
        return {
            "params_path": str(self.params_path),
            "configured_setup_first_blocks": self.configured_setup_first_blocks,
            "effective_setup_first_blocks": self.effective_setup_first_blocks,
            "setup_was_raised_at_genesis": self.setup_was_raised,
            "treasury_address": self.treasury_address,
            "chain_params": self.effective_params,
        }


def prepare_chain(plan: ExperimentPlan, run_root: Path, *, util_binary: str,
                  treasury: Treasury | None, runner) -> InitResult:
    """Create ``params.dat`` for the admin and a ``multichain.conf`` for everyone."""
    chain = plan.multichain.chain
    admin = plan.admin
    data_root = run_root / "runtime" / "data"
    admin_datadir = data_root / admin.id
    admin_datadir.mkdir(parents=True, exist_ok=True)
    log_path = run_root / "logs" / "initialize.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    argv = [util_binary, "create", chain, "-datadir=%s" % admin_datadir]
    argv += plan.chain_params.util_flags()
    if treasury is not None:
        argv.append("-weighttreasuryaddress=%s" % treasury.address)

    LOG.info("creating chain %s in %s", chain, admin_datadir)
    result = runner.run(argv, check=False, timeout_s=300, what="multichain-util create")
    log_path.write_text(
        "$ %s\n\n--- stdout ---\n%s\n--- stderr ---\n%s\n"
        % (" ".join(argv), result.stdout, result.stderr), encoding="utf-8",
    )
    if not result.ok:
        raise RuntimeFailure(
            "multichain-util create failed (rc=%d); see %s\n%s"
            % (result.returncode, log_path, (result.stderr or result.stdout).strip()[:600])
        )

    params_path = admin_datadir / chain / "params.dat"
    if not runner.dry_run and not params_path.is_file():
        raise RuntimeFailure("params.dat was not written; see %s" % log_path)

    configured = plan.setup_first_blocks
    if not runner.dry_run:
        _apply_edits(params_path, plan.chain_params, setup_first_blocks=configured)
        effective = read_params_dat(params_path)
    else:
        effective = {}
    effective_setup = int(effective.get("setup-first-blocks", configured) or configured)
    if effective_setup > configured:
        LOG.warning(
            "multichain-util raised setup-first-blocks from %d to %d at genesis; the "
            "measurement window follows the effective value", configured, effective_setup)

    _write_node_configs(plan, data_root)

    return InitResult(
        params_path=params_path,
        configured_setup_first_blocks=configured,
        effective_setup_first_blocks=effective_setup,
        effective_params=effective,
        treasury_address=treasury.address if treasury else "",
        log_path=log_path,
    )


def _apply_edits(params_path: Path, chain_params: ChainParams, *,
                 setup_first_blocks: int) -> None:
    """Rewrite the keys ``multichain-util create`` does not take as flags."""
    text = params_path.read_text(encoding="utf-8")
    for name, value in chain_params.params_dat_edits(setup_first_blocks=setup_first_blocks):
        pattern = re.compile(r"^(%s\s*=\s*)[^\s#]+" % re.escape(name), re.M)
        text, count = pattern.subn(lambda m: m.group(1) + value, text)
        if count == 0:
            LOG.warning("params.dat has no key %r; %s=%s was not applied", name, name, value)
    params_path.write_text(text, encoding="utf-8")


def _write_node_configs(plan: ExperimentPlan, data_root: Path) -> None:
    """One ``multichain.conf`` per node: RPC credentials and the fee cap."""
    chain = plan.multichain.chain
    body = (
        "# Generated by experiments.runtime.multichain.initialize - do not edit by hand.\n"
        "rpcuser=%s\n"
        "rpcpassword=%s\n"
        "rpcallowip=0.0.0.0/0\n"
        "# maxtxfee: the wallet's default cap is 0.1 native units. With\n"
        "# minimum-relay-fee = %s raw per 1000 bytes, every stream publication above\n"
        "# ~500 bytes would need more than that and CreateTransaction would refuse it\n"
        "# with \"Transaction too large for fee policy\" - which hits publish, not send,\n"
        "# so the network looks healthy while no record is ever published.\n"
        "maxtxfee=%s\n"
        % (plan.multichain.rpc_user, plan.multichain.rpc_password,
           plan.chain_params.get("MINIMUM_RELAY_FEE", "?"), plan.multichain.max_tx_fee)
    )
    for node in plan.enabled_nodes:
        directory = data_root / node.id / chain
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "multichain.conf").write_text(body, encoding="utf-8")


def daemon_argv(plan: ExperimentPlan, node, run_root: Path, *, daemon_binary: str,
                seed_endpoint: str | None) -> list[str]:
    """Command line of one ``multichaind``.

    ``-externalip`` is the emulated address, never the management one: it is
    what the node advertises to its peers, so peering must travel the impaired
    paths. ``-dnsseed=0 -discover=0`` keep the peer set exactly as declared.
    """
    datadir = run_root / "runtime" / "data" / node.id
    first_argument = seed_endpoint if seed_endpoint else plan.multichain.chain
    argv = [
        daemon_binary, first_argument,
        "-datadir=%s" % datadir,
        "-port=%d" % node.p2p_port,
        "-rpcport=%d" % node.rpc_port,
        "-externalip=%s" % node.ip,
        "-dnsseed=0",
        "-discover=0",
    ]
    if plan.multichain.debug:
        argv.append("-debug=%s" % plan.multichain.debug)
    for peer in node.peers:
        try:
            argv.append("-addnode=%s" % plan.node(peer).ip)
        except KeyError:
            LOG.warning("node %s lists unknown peer %r", node.id, peer)
    return argv


def first_launch_argv(plan: ExperimentPlan, node, run_root: Path, *,
                      daemon_binary: str, seed_endpoint: str) -> list[str]:
    """Phase one of the permissioned join.

    On a permissioned chain a node's first start does not enter the network:
    it creates the wallet, prints its address and exits, waiting for the
    administrator to grant it permissions. ``-shortoutput`` reduces that to the
    address alone, which the role script captures into ``shared/<node>.addr``.
    """
    datadir = run_root / "runtime" / "data" / node.id
    return [
        daemon_binary, seed_endpoint,
        "-datadir=%s" % datadir,
        "-port=%d" % node.p2p_port,
        "-rpcport=%d" % node.rpc_port,
        "-externalip=%s" % node.ip,
        "-dnsseed=0", "-discover=0", "-shortoutput",
    ]


def seed_endpoint(plan: ExperimentPlan) -> str:
    """``<chain>@<admin ip>:<p2p port>`` — how a node finds the network."""
    admin = plan.admin
    return "%s@%s:%d" % (plan.multichain.chain, admin.ip, admin.p2p_port)


def clean_data(run_root: Path) -> None:
    """Remove the data tree of a previous attempt at the same run id."""
    data_root = run_root / "runtime" / "data"
    if data_root.exists():
        shutil.rmtree(data_root)
