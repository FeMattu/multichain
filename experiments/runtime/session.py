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

import json
import logging
import os
import signal
import time
from datetime import datetime, timezone
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
    terminate,
)
from .roles.scheduler import RoleScheduler
from .multichain.rpc import RpcClient
from .shell import Runner

LOG = logging.getLogger("experiments.runtime.session")

#: The only bash left in the run path. It wraps ONE multichaind invocation -
#: phase one of the permissioned join, which prints the wallet address and
#: exits - and is not protocol logic. Everything a node does afterwards is a
#: Python controller under runtime/roles/.
FIRST_LAUNCH_SCRIPT = "first_launch.sh"


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
    connectivity: dict = field(default_factory=dict)
    scheduler: object | None = None
    #: The running sampler, when there is one. Set by the caller so the
    #: collectors can ask the scheduler whether each controller is alive.
    sampler: object | None = None
    controller_tick_s: float = 5.0
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
            if self.interrupted:
                # A second Ctrl+C means "stop waiting for the graceful path".
                # It must NOT mean "leave twenty namespaces and twenty daemons
                # behind": that is what the next run would inherit. Tear the
                # fabric down hard, then re-raise.
                LOG.warning("second signal %d: skipping the graceful stop", signum)
                self._emergency_teardown()
                raise KeyboardInterrupt
            self.interrupted = True
            LOG.warning("signal %d received: stopping the run and cleaning up "
                        "(a second Ctrl+C skips the graceful stop)", signum)
            raise Interrupted("interrupted by signal %d" % signum)

        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                self._previous_handlers[signum] = signal.signal(signum, handler)
            except ValueError:      # not the main thread
                pass

    def _emergency_teardown(self) -> None:
        """Last-resort removal of the fabric. Best effort, never raises."""
        try:
            for process in self.registry.processes:
                if process.alive():
                    terminate(process, sigterm_wait_s=0.5)
        except BaseException:  # noqa: BLE001
            pass
        try:
            if self.fabric is not None:
                self.fabric.teardown()
                LOG.warning("fabric destroyed by the emergency path")
        except BaseException:  # noqa: BLE001
            LOG.error("the emergency teardown could not remove the fabric; "
                      "run experiments/scripts/clean_experiment.sh")
        try:
            if self.manifest is not None:
                self.manifest.finish("interrupted",
                                     cleanup={"status": "emergency teardown"})
        except BaseException:  # noqa: BLE001
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
        too_short = self.plan.duration_warning()
        if too_short:
            LOG.warning("schedule: %s", too_short)

    def resolve_binaries(self) -> None:
        self.binaries = install.require_all(self.plan.multichain)

    def build_network(self, *, backend: str | None = None,
                      allow_fallback: bool = False, assume_yes: bool = False) -> None:
        self.fabric = make_fabric(self.plan, self.runner, run_root=self.run_root,
                                  backend=backend, allow_fallback=allow_fallback,
                                  assume_yes=assume_yes)
        self.fabric.build()
        self._record_backend_choice(requested=backend or self.plan.fabric.backend,
                                    allow_fallback=allow_fallback,
                                    assume_yes=assume_yes)
        self._verify_connectivity()
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

    def _record_backend_choice(self, *, requested: str, allow_fallback: bool,
                               assume_yes: bool) -> None:
        """What was asked for, what runs, and who authorised the difference.

        A run that changed backend is comparable with one that did not only if
        the manifest says so. The gate already refuses to make the choice on
        its own; this records the choice it was given.
        """
        used = getattr(self.fabric, "name", "") or requested
        status = getattr(self.fabric, "core_status", None)
        fell_back = requested == "auto" and used != "core"
        self.manifest.set(
            network_backend_requested=requested,
            network_backend_used=used,
            fabric_backend=used,
            fallback_confirmed=bool(fell_back and (allow_fallback or assume_yes)),
            fallback_reason=("; ".join(status.problems)
                             if fell_back and status is not None and status.problems
                             else None),
        )

    def _verify_connectivity(self) -> None:
        """Prove the fabric carries packets before a single daemon starts.

        A partition the topology declares is expected and is not a failure;
        anything else is, and it is far cheaper to learn here than from a
        daemon log two minutes later.
        """
        if self.runner.dry_run:
            return
        declared_partitions = any(
            link.impairment_forward.partition or link.impairment_reverse.partition
            or not link.enabled
            for link in self.plan.topology.links
        )
        report = self.fabric.verify_connectivity()
        self.connectivity = report
        if report["ok"]:
            LOG.info("connectivity verified: %s", kv(pairs=report["checked"]))
            return
        summary = ", ".join(
            "%s->%s" % (f["from"], f["to"]) for f in report["failures"][:8]
        )
        if declared_partitions:
            LOG.warning(
                "%d of %d node pairs cannot reach each other (%s); the topology "
                "declares a partition, so this may be intended",
                len(report["failures"]), report["checked"], summary)
            return
        raise RuntimeFailure(
            "the fabric was built but does not carry traffic: %d of %d node pairs "
            "cannot reach each other (%s).\n"
            "No daemon was started, because on this network none of them could "
            "join the chain.\n"
            "First things to check: 'ip netns exec %s ip route' (the route to the "
            "experiment subnet must carry 'src <node ip>'), then rp_filter and "
            "ip_forward on the routers."
            % (len(report["failures"]), report["checked"], summary,
               self.fabric.nodes[report["failures"][0]["from"]].namespace),
        )

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
            start_role(self.fabric, node, self.roles_dir / FIRST_LAUNCH_SCRIPT,
                       "", self.run_root, self.registry, {**env_for(node), "POESIA_SEED": seed})

        # t=grant - the admin controller takes over: its setup() grants every
        # permission, creates the streams and funds the network, and then it
        # keeps running for the rest of the experiment, refilling GAS and
        # sampling each buried epoch.
        wait_until(schedule.grant_s, "grant")
        remaining = max(60.0, schedule.duration_s - (time.monotonic() - started))
        self.scheduler = RoleScheduler(
            self.fabric, self.plan, self.run_root,
            environment_for=env_for, poll_s=5.0,
        )
        if self.sampler is not None:
            self.sampler.controller_probe = self.scheduler.controller_alive
        self.scheduler.start(admin, duration_s=remaining, tick_s=self.controller_tick_s)

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

        # t=register - every other node's controller starts. Its setup()
        # registers membership or publishes the ESG scores; its loop() then
        # generates the workload and reconciles for the rest of the run.
        # There is no separate "traffic" phase any more: a controller that is
        # alive is working, which is exactly the property that was missing.
        wait_until(schedule.register_s, "register")
        remaining = max(60.0, schedule.duration_s - (time.monotonic() - started))
        for node in self.plan.cas + self.plan.miners + self.plan.companies:
            if node.expected_state == "absent":
                continue
            self.scheduler.start(node, duration_s=remaining,
                                 tick_s=self.controller_tick_s)
        self.scheduler.supervise_in_background()
        LOG.info("%d node controllers running under supervision",
                 len(self.scheduler.handles))

        # The gate that decides whether wPoA can take over at all.
        report.add(health.wait_weights_published(
            self.clients[admin.id],
            timeout_s=max(300.0, setup_blocks * self.plan.target_block_time * 0.5),
        ))
        self._record_health(report, "weights")

        # Measurement window. The controllers work; this only watches for
        # daemons that die and for controllers the scheduler had to restart.
        self._supervise(until=schedule.duration_s, started=started)

        # Stopping the controllers is what produces the final snapshot: the
        # admin's teardown() writes blocks.json and the rest. It must happen
        # while the daemons are still up, which is why it is here and not in
        # cleanup().
        LOG.info("stopping the node controllers (the admin takes its final snapshot)")
        self.scheduler.stop_all(timeout_s=90.0)
        self.scheduler.write_summary()
        summary = self.scheduler.summary()
        if summary["restarts_total"]:
            LOG.warning("%d controller restart(s) during the run: %s",
                        summary["restarts_total"],
                        ", ".join("%s x%d" % (d["node_id"], d["restarts"])
                                  for d in summary["detail"] if d["restarts"]))
        report.add(health.Check(
            "node controllers", not summary["gave_up"],
            detail="" if not summary["gave_up"]
            else "gave up on: " + ", ".join(summary["gave_up"]),
            values=summary))

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
        """Stop everything and record the outcome. Never raises, never deletes.

        Every step is individually guarded and the manifest is finalised from a
        ``finally``. That ordering was learned from a real interrupted run: a
        second Ctrl+C arriving while the daemons were being stopped propagated
        out of here, so the manifest was left saying ``status: running`` with
        no ``cleanup`` section at all - the one record that had to survive was
        the one that did not.
        """
        summary: dict = {"status": status}
        try:
            if self.scheduler is not None:
                try:
                    summary["controllers"] = self.scheduler.stop_all(timeout_s=45.0)
                    summary["controller_summary"] = self.scheduler.summary()
                    self.scheduler.write_summary()
                except BaseException as exc:  # noqa: BLE001
                    LOG.error("stopping the controllers reported %s", exc)
                    summary["controllers_error"] = str(exc)
            # Before anything is stopped: once the daemons are down, nobody can
            # say what state they were in, and a run that ended badly is
            # exactly the one where that matters.
            try:
                self._write_node_status()
            except BaseException as exc:  # noqa: BLE001
                LOG.error("recording the node status reported %s", exc)
            try:
                summary["processes"] = stop_all(self.registry, self.clients)
            except BaseException as exc:  # noqa: BLE001 - including KeyboardInterrupt
                LOG.error("stopping processes reported %s", exc)
                summary["processes_error"] = str(exc)
            if self.fabric is not None:
                try:
                    summary["impairment_cleared"] = self.fabric.clear_impairment()
                except BaseException as exc:  # noqa: BLE001
                    LOG.error("clearing impairment reported %s", exc)
                    summary["impairment_error"] = str(exc)
                try:
                    self.fabric.teardown()
                    summary["fabric"] = "destroyed"
                except BaseException as exc:  # noqa: BLE001
                    LOG.error("fabric teardown reported %s", exc)
                    summary["fabric_error"] = str(exc)
            summary["results_owner"] = self._restore_ownership()
        finally:
            if self.manifest is not None:
                try:
                    if error:
                        self.manifest.error(error, phase="cleanup")
                    self.manifest.finish(
                        status,
                        processes=self.registry.as_dict(),
                        cleanup=summary,
                        connectivity=self.connectivity,
                    )
                except BaseException as exc:  # noqa: BLE001
                    LOG.error("could not finalise the manifest: %s", exc)
            LOG.info("run %s finished: %s", self.run_id, status)
        return summary

    def _write_node_status(self) -> Path:
        """The last known state of every node, as one file.

        `role-controllers.json` says what the scheduler saw and the manifest
        says what the harness started; neither answers "what was node m1 doing
        when this ended". This does, per node, in the order a reader asks:
        was its daemon up, was its controller up, and how far had its chain
        got.
        """
        status = {}
        for node in self.plan.enabled_nodes:
            daemons = [p for p in self.registry.for_node(node.id)
                       if p.kind == "daemon"]
            entry = {
                "node_id": node.id,
                "role": node.role,
                "expected_state": node.expected_state,
                "daemon_alive": bool(any(p.alive() for p in daemons)),
                "daemon_returncode": daemons[-1].returncode if daemons else None,
                "daemon_restarts": sum(p.restarts for p in daemons),
                "controller_alive": (self.scheduler.controller_alive(node.id)
                                     if self.scheduler is not None else ""),
                "block_height": None,
                "peer_count": None,
                "rpc_reachable": False,
            }
            client = self.clients.get(node.id)
            if client is not None:
                try:
                    entry["block_height"] = int(client.call("getblockcount"))
                    entry["rpc_reachable"] = True
                    peers = client.call("getpeerinfo")
                    entry["peer_count"] = len(peers) if isinstance(peers, list) else None
                except Exception as exc:  # noqa: BLE001 - an unreachable node is a fact
                    entry["rpc_error"] = str(exc)
            status[node.id] = entry
        path = self.run_root / "runtime" / "node-status.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "run_id": self.run_id,
            "recorded_at_wallclock": datetime.now(timezone.utc).isoformat(),
            "temporal_model": "wall_clock_emulation",
            "nodes": status,
        }, indent=2, default=str), encoding="utf-8")
        LOG.info("node status recorded for %d nodes: %s", len(status), path)
        return path

    def _restore_ownership(self) -> str:
        """Give the run directory back to the user who invoked sudo.

        A run started with `sudo -E` leaves a root-owned results tree, and the
        analysis - which needs no privileges and should not have them - then
        cannot write into it. Chowning back is the difference between a run
        that can be analysed and one that can only be read.
        """
        uid, gid = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
        if not uid or os.geteuid() != 0:
            return "unchanged"
        try:
            target_uid, target_gid = int(uid), int(gid or uid)
        except ValueError:
            return "unchanged"
        changed = 0
        for path in [self.run_root, *self.run_root.rglob("*")]:
            try:
                os.chown(path, target_uid, target_gid)
                changed += 1
            except OSError:
                continue
        LOG.info("results handed back to uid %s (%d paths)", target_uid, changed)
        return "chown %s:%s on %d paths" % (target_uid, target_gid, changed)

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
