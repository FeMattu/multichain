"""The run: build the network, bootstrap the chain, measure, tear down.

One object owns the whole lifecycle, and it owns it as a context manager so
that there is exactly one cleanup path. Ctrl+C, a crashed daemon, a CORE
failure, a missing file and a normal finish all leave through the same
``__exit__``, which stops the processes, clears the impairment, destroys the
fabric, updates the manifest and leaves every log and artefact in place.

The one thing cleanup never does is delete results. A run that failed at
minute forty still holds forty minutes of debug logs, and those are usually
the reason it failed.
"""

from __future__ import annotations

import logging
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import FrameType

from ..exit_codes import IncompleteData, RuntimeFailure
from ..logging_setup import kv
from ..plan import ExperimentPlan
from ..topology import exporters
from ..topology.validator import validate_topology
from .fabric import make_fabric
from .fabric.base import Fabric
from .manifest import Manifest
from .multichain import health, initialize, install, treasury as treasury_mod
from .multichain.lifecycle import (
    ProcessRegistry,
    role_environment,
    start_daemon,
    start_role,
    stop_all,
)
from .multichain.rpc import RpcClient
from .shell import Runner

LOG = logging.getLogger("experiments.runtime.session")

ROLE_SCRIPTS = {
    "first_launch": "first_launch.sh",
    "admin": "admin.sh",
    "miner": "miner.sh",
    "company": "company.sh",
    "ca": "ca.sh",
}


class Interrupted(RuntimeFailure):
    """Ctrl+C or SIGTERM reached the harness."""


@dataclass
class Session:
    """A single run, from empty directory to archived artefacts."""

    plan: ExperimentPlan
    run_id: str
    run_root: Path
    runner: Runner
    roles_dir: Path
    fabric: Fabric | None = None
    manifest: Manifest | None = None
    registry: ProcessRegistry = field(default_factory=ProcessRegistry)
    clients: dict[str, RpcClient] = field(default_factory=dict)
    binaries: dict = field(default_factory=dict)
    treasury: object | None = None
    init_result: object | None = None
    interrupted: bool = False
    _previous_handlers: dict = field(default_factory=dict)

    # -- context management -------------------------------------------------
    def __enter__(self) -> "Session":
        self._install_signal_handlers()
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        status = "completed"
        if self.interrupted:
            status = "interrupted"
        elif exc_type is not None:
            status = "failed"
        self.cleanup(status=status, error=str(exc) if exc else "")
        self._restore_signal_handlers()
        return False

    def _install_signal_handlers(self) -> None:
        def handler(signum: int, frame: FrameType | None) -> None:
            del frame
            if self.interrupted:      # a second Ctrl+C means "now"
                LOG.warning("second signal %d: aborting cleanup", signum)
                raise KeyboardInterrupt
            self.interrupted = True
            LOG.warning("signal %d received: stopping the run and cleaning up", signum)
            raise Interrupted("interrupted by signal %d" % signum)

        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                self._previous_handlers[signum] = signal.signal(signum, handler)
            except ValueError:      # not the main thread
                pass

    def _restore_signal_handlers(self) -> None:
        for signum, previous in self._previous_handlers.items():
            try:
                signal.signal(signum, previous)
            except ValueError:
                pass

    # -- directories --------------------------------------------------------
    def prepare_directories(self) -> None:
        for relative in ("config", "runtime", "logs", "raw", "raw/metrics",
                         "metrics", "plots", "reports"):
            (self.run_root / relative).mkdir(parents=True, exist_ok=True)
        (self.run_root / "runtime" / "shared").mkdir(parents=True, exist_ok=True)
        for node in self.plan.enabled_nodes:
            (self.run_root / "logs" / node.id).mkdir(parents=True, exist_ok=True)

    def snapshot_config(self) -> None:
        """Copy the exact inputs into the run, so it stays readable alone."""
        import shutil

        target = self.run_root / "config"
        shutil.copy2(self.plan.descriptor_path, target / "experiment.yaml")
        shutil.copy2(self.plan.topology_path, target / "topology.yaml")
        shutil.copy2(self.plan.chain_params.path, target / "chain-params.dat")
        profiles = target / "network-profiles"
        profiles.mkdir(exist_ok=True)
        from ..paths import CONFIG_ROOT

        for profile in sorted((CONFIG_ROOT / "network-profiles").glob("*.y*ml")):
            shutil.copy2(profile, profiles / profile.name)
        exporters.write_gml(self.plan.topology, target / "topology.gml")
        exporters.write_edges_csv(self.plan.topology, target / "topology-edges.csv")

    # -- phases -------------------------------------------------------------
    def validate(self) -> None:
        report = validate_topology(self.plan.topology)
        for warning in report.warnings:
            LOG.warning("topology: %s", warning)
        if report.errors:
            raise RuntimeFailure(
                "the topology is not usable:\n  - " + "\n  - ".join(report.errors)
            )
        LOG.info("topology ok: %s", kv(
            locations=len(self.plan.topology.locations),
            links=len(self.plan.topology.links),
            max_rtt_ms=report.max_rtt_ms,
        ))

    def resolve_binaries(self) -> None:
        self.binaries = install.require_all(self.plan.multichain)

    def build_network(self, *, backend: str | None = None) -> None:
        self.fabric = make_fabric(self.plan, self.runner, run_root=self.run_root,
                                  backend=backend)
        self.fabric.build()
        exporters.write_realized_json(
            self.plan.topology,
            self.run_root / "runtime" / "topology-realized.json",
            extra={"fabric": self.fabric.realized()},
        )
        self.clients = {
            node.id: RpcClient(
                self.fabric.rpc_endpoint(node),
                self.plan.multichain.rpc_user, self.plan.multichain.rpc_password,
                node_id=node.id,
            )
            for node in self.plan.enabled_nodes
            if node.expected_state != "absent"
        }

    def initialize_chain(self) -> None:
        self.treasury = treasury_mod.load(self.plan.multichain.treasury_file)
        if self.treasury is None:
            LOG.warning(
                "no treasury address at %s: R_k will be zero for the whole run",
                self.plan.multichain.treasury_file,
            )
        else:
            for warning in treasury_mod.check_compatible(self.treasury, self.plan.chain_params):
                LOG.warning("treasury: %s", warning)
        self.init_result = initialize.prepare_chain(
            self.plan, self.run_root,
            util_binary=self.binaries["multichain-util"].path,
            treasury=self.treasury, runner=self.runner,
        )
        if self.manifest:
            self.manifest.set(chain_initialization=self.init_result.as_dict())

    # -- the schedule -------------------------------------------------------
    def run_schedule(self) -> dict:
        """Execute the bootstrap timeline and hold until the run is over."""
        assert self.fabric is not None
        schedule = self.plan.schedule
        started = time.monotonic()
        report = health.HealthReport()

        def wait_until(mark: float, label: str) -> None:
            remaining = mark - (time.monotonic() - started)
            if remaining > 0:
                LOG.info("waiting %.0fs until %s", remaining, label)
                self._sleep(remaining)

        daemon = self.binaries["multichaind"].path
        setup_blocks = getattr(self.init_result, "effective_setup_first_blocks",
                               self.plan.setup_first_blocks)
        treasury_address = getattr(self.treasury, "address", "") if self.treasury else ""

        def env_for(node):
            return role_environment(
                self.plan, node, self.run_root, daemon=daemon,
                treasury_address=treasury_address, setup_first_blocks=setup_blocks,
            )

        # t=0 - the admin seals the genesis and starts mining alone.
        admin = self.plan.admin
        start_daemon(
            self.fabric, self.plan, admin,
            initialize.daemon_argv(self.plan, admin, self.run_root,
                                   daemon_binary=daemon, seed_endpoint=None),
            self.run_root, self.registry, env_for(admin),
        )
        report.add(health.wait_daemons({admin.id: self.clients[admin.id]}, timeout_s=180))
        self._record_health(report, "admin-genesis")

        # t=first_launch - every other node collects its address and exits.
        wait_until(schedule.first_launch_s, "first launch")
        seed = initialize.seed_endpoint(self.plan)
        for node in self.plan.enabled_nodes:
            if node.id == admin.id or node.expected_state == "absent":
                continue
            start_role(self.fabric, node, self.roles_dir / ROLE_SCRIPTS["first_launch"],
                       "", self.run_root, self.registry, {**env_for(node), "POESIA_SEED": seed})

        # t=grant - permissions, streams, the CA role and the initial GAS.
        wait_until(schedule.grant_s, "grant")
        start_role(self.fabric, admin, self.roles_dir / ROLE_SCRIPTS["admin"], "grant",
                   self.run_root, self.registry, env_for(admin))

        # t=join - the real daemons join and sync.
        wait_until(schedule.join_s, "join")
        for node in self.plan.enabled_nodes:
            if node.id == admin.id or node.expected_state == "absent":
                continue
            start_daemon(
                self.fabric, self.plan, node,
                initialize.daemon_argv(self.plan, node, self.run_root,
                                       daemon_binary=daemon, seed_endpoint=seed),
                self.run_root, self.registry, env_for(node),
            )
        report.add(health.wait_daemons(self.clients, timeout_s=240))
        minimum_peers = int(self.plan.expected.get("min_peers", 1))
        report.add(health.wait_peers(self.clients, minimum_peers, timeout_s=180))
        self._record_health(report, "join")

        # t=register - ESG certificates and cluster membership.
        wait_until(schedule.register_s, "register")
        for node in self.plan.cas:
            start_role(self.fabric, node, self.roles_dir / ROLE_SCRIPTS["ca"], "",
                       self.run_root, self.registry, env_for(node))
        for node in self.plan.miners:
            start_role(self.fabric, node, self.roles_dir / ROLE_SCRIPTS["miner"], "register",
                       self.run_root, self.registry, env_for(node))
        for node in self.plan.companies:
            start_role(self.fabric, node, self.roles_dir / ROLE_SCRIPTS["company"], "register",
                       self.run_root, self.registry, env_for(node))

        # t=traffic - workload, reconciliation, GAS refill and epoch sampling.
        wait_until(schedule.traffic_s, "traffic")
        for node in self.plan.companies:
            start_role(self.fabric, node, self.roles_dir / ROLE_SCRIPTS["company"], "traffic",
                       self.run_root, self.registry, env_for(node))
        for node in self.plan.miners:
            start_role(self.fabric, node, self.roles_dir / ROLE_SCRIPTS["miner"], "reconcile",
                       self.run_root, self.registry, env_for(node))
        start_role(self.fabric, admin, self.roles_dir / ROLE_SCRIPTS["admin"], "refill",
                   self.run_root, self.registry, env_for(admin))
        start_role(self.fabric, admin, self.roles_dir / ROLE_SCRIPTS["admin"], "epoch_watch",
                   self.run_root, self.registry, env_for(admin))

        # The gate that decides whether wPoA can take over at all.
        report.add(health.wait_weights_published(
            self.clients[admin.id],
            timeout_s=max(300.0, setup_blocks * self.plan.target_block_time * 0.5),
        ))
        self._record_health(report, "weights")

        # Measurement window.
        self._supervise(until=schedule.snapshot_s, started=started)

        # Final snapshot, well before the daemons stop.
        start_role(self.fabric, admin, self.roles_dir / ROLE_SCRIPTS["admin"], "snapshot",
                   self.run_root, self.registry, env_for(admin))
        self._supervise(until=schedule.duration_s, started=started)

        report.add(health.check_consistency(self.clients))
        self._record_health(report, "final")
        return report.as_dict()

    def _supervise(self, *, until: float, started: float) -> None:
        """Sleep to a mark, noticing daemons that die on the way."""
        poll = 5.0
        while True:
            elapsed = time.monotonic() - started
            if elapsed >= until:
                return
            dead = self.registry.dead_unexpectedly()
            if dead:
                for process in dead:
                    LOG.error("daemon on %s exited with %s; see %s",
                              process.node_id, process.returncode, process.log_path)
                    if self.manifest:
                        self.manifest.error(
                            "daemon on %s exited with %s" % (process.node_id, process.returncode),
                            phase="measurement",
                        )
            self._sleep(min(poll, until - elapsed))

    def _sleep(self, seconds: float) -> None:
        """Interruptible sleep: a signal must not wait out a long interval."""
        deadline = time.monotonic() + max(0.0, seconds)
        while time.monotonic() < deadline:
            if self.interrupted:
                raise Interrupted("interrupted while waiting")
            time.sleep(min(1.0, deadline - time.monotonic()))

    def _record_health(self, report: health.HealthReport, phase: str) -> None:
        if self.manifest:
            self.manifest.phase(
                phase, "ok" if report.ok else "degraded", health=report.as_dict(),
            )

    # -- cleanup ------------------------------------------------------------
    def cleanup(self, *, status: str, error: str = "") -> dict:
        """Stop everything and record the outcome. Never raises, never deletes."""
        summary: dict = {"status": status}
        try:
            summary["processes"] = stop_all(self.registry, self.clients)
        except Exception as exc:  # noqa: BLE001 - cleanup must finish
            LOG.error("stopping processes reported %s", exc)
            summary["processes_error"] = str(exc)
        if self.fabric is not None:
            try:
                summary["impairment_cleared"] = self.fabric.clear_impairment()
            except Exception as exc:  # noqa: BLE001
                LOG.error("clearing impairment reported %s", exc)
                summary["impairment_error"] = str(exc)
            try:
                self.fabric.teardown()
                summary["fabric"] = "destroyed"
            except Exception as exc:  # noqa: BLE001
                LOG.error("fabric teardown reported %s", exc)
                summary["fabric_error"] = str(exc)
        if self.manifest is not None:
            if error:
                self.manifest.error(error, phase="cleanup")
            self.manifest.finish(
                status,
                processes=self.registry.as_dict(),
                cleanup=summary,
            )
        LOG.info("run %s finished: %s", self.run_id, status)
        return summary

    # -- verification -------------------------------------------------------
    def verify_artefacts(self) -> None:
        """Fail with exit code 4 when a run produced too little to analyse."""
        metrics = self.run_root / "raw" / "metrics"
        required = ["blocks.json", "final_height.txt"]
        missing = [name for name in required if not (metrics / name).is_file()]
        if missing:
            raise IncompleteData(
                "the run produced no usable snapshot (missing %s in %s)"
                % (", ".join(missing), metrics),
                hint="check logs/<admin>/role-snapshot.log; the final snapshot is the "
                     "primary source of every metric",
            )
