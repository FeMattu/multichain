"""Keeping one controller alive per node, for the whole experiment.

The regression this fixes: nodes were started and then left to themselves. A
controller that dies at minute three of a forty-minute run takes its node's
entire contribution with it — a company stops generating the traffic that
drives tau_i, a miner stops reconciling and its rho_k silently becomes 1 —
and nothing in the output says so. The weights then look like a protocol
result rather than a dead process.

So: every controller is supervised, a crash is restarted, and both the crash
and the restart are recorded. ``process_restarts`` in the metrics is that
count, and a run whose analysis looks odd can be checked against it.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

LOG = logging.getLogger("experiments.runtime.roles.scheduler")

#: Give up after this many restarts of the same node. A controller failing in
#: a tight loop is a bug, and restarting it forever would bury the evidence
#: under a million log lines.
MAX_RESTARTS = 5

#: Wait before a restart, so a node whose daemon is still coming up is not
#: hammered.
RESTART_BACKOFF_S = 5.0


@dataclass
class ControllerHandle:
    node_id: str
    role: str
    argv: list
    env: dict
    log_path: Path
    handle: object = None
    restarts: int = 0
    exited_at: float = 0.0
    last_returncode: int | None = None
    given_up: bool = False

    def alive(self) -> bool:
        return self.handle is not None and self.handle.poll() is None

    def as_dict(self) -> dict:
        return {"node_id": self.node_id, "role": self.role,
                "pid": getattr(self.handle, "pid", None), "alive": self.alive(),
                "restarts": self.restarts, "last_returncode": self.last_returncode,
                "given_up": self.given_up, "log": str(self.log_path)}


class RoleScheduler:
    """Starts every node's controller and keeps it running."""

    def __init__(self, fabric, plan, run_root: Path, *, environment_for,
                 poll_s: float = 5.0) -> None:
        self.fabric = fabric
        self.plan = plan
        self.run_root = Path(run_root)
        self.environment_for = environment_for
        self.poll_s = poll_s
        self.handles: dict = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- start --------------------------------------------------------------
    def start_all(self, *, duration_s: float, tick_s: float = 5.0) -> None:
        for node in self.plan.enabled_nodes:
            if node.expected_state == "absent":
                LOG.info("node %s is declared absent: no controller", node.id)
                continue
            self.start(node, duration_s=duration_s, tick_s=tick_s)
        LOG.info("started %d node controllers", len(self.handles))

    def start(self, node, *, duration_s: float, tick_s: float) -> ControllerHandle:
        env = dict(self.environment_for(node))
        env["POESIA_DURATION"] = str(duration_s)
        env["POESIA_TICK"] = str(tick_s)
        env["PYTHONUNBUFFERED"] = "1"
        log_path = self.run_root / "logs" / node.id / "role_controller.stdout.log"
        handle = ControllerHandle(
            node_id=node.id, role=node.role,
            argv=["python3", "-m", "experiments.runtime.roles"],
            env=env, log_path=log_path,
        )
        self.handles[node.id] = handle
        self._spawn(handle)
        return handle

    def _spawn(self, handle: ControllerHandle) -> None:
        handle.log_path.parent.mkdir(parents=True, exist_ok=True)
        handle.handle = self.fabric.spawn(
            handle.node_id, handle.argv, stdout=handle.log_path,
            env=handle.env, cwd=self._repo_root(),
        )
        LOG.info("controller for %s (%s) started: pid %s", handle.node_id,
                 handle.role, getattr(handle.handle, "pid", "dry-run"))

    @staticmethod
    def _repo_root() -> Path:
        from ...paths import REPO_ROOT

        return REPO_ROOT

    # -- supervise ----------------------------------------------------------
    def supervise_in_background(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="role-scheduler",
                                        daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.check_once()
            self._stop.wait(self.poll_s)

    def check_once(self) -> int:
        """Restart whatever died. Returns how many were restarted."""
        restarted = 0
        for handle in self.handles.values():
            if handle.given_up or handle.alive() or handle.handle is None:
                continue
            code = handle.handle.poll()
            handle.last_returncode = code
            # Exit 0 is a controller that finished its own duration, which is
            # the normal end of a run, not a crash.
            if code == 0:
                handle.given_up = True
                LOG.info("controller for %s finished cleanly", handle.node_id)
                continue
            if handle.restarts >= MAX_RESTARTS:
                handle.given_up = True
                LOG.error("controller for %s died %d times (last rc=%s); giving up. "
                          "That node stops contributing from now on - see %s",
                          handle.node_id, handle.restarts, code, handle.log_path)
                continue
            handle.restarts += 1
            LOG.warning("controller for %s exited with %s: restart %d of %d",
                        handle.node_id, code, handle.restarts, MAX_RESTARTS)
            time.sleep(RESTART_BACKOFF_S)
            self._spawn(handle)
            restarted += 1
        return restarted

    # -- stop ---------------------------------------------------------------
    def stop_all(self, *, timeout_s: float = 30.0) -> dict:
        """Ask every controller to finish, then make sure it did.

        SIGTERM first: the controllers install a handler and run their own
        teardown, which for the admin is the final chain snapshot. Killing
        that outright loses the run's primary data source.
        """
        from ..multichain.lifecycle import terminate_popen

        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

        for handle in self.handles.values():
            if handle.alive():
                handle.given_up = True    # a deliberate stop is not a crash
                try:
                    handle.handle.terminate()
                except Exception:  # noqa: BLE001
                    pass

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if not any(h.alive() for h in self.handles.values()):
                break
            time.sleep(0.5)

        report = {}
        for node_id, handle in self.handles.items():
            report[node_id] = (terminate_popen(handle.handle) if handle.alive()
                               else "stopped")
        LOG.info("all controllers stopped")
        return report

    # -- reporting ----------------------------------------------------------
    def summary(self) -> dict:
        total_restarts = sum(h.restarts for h in self.handles.values())
        return {
            "controllers": len(self.handles),
            "restarts_total": total_restarts,
            "gave_up": [h.node_id for h in self.handles.values() if h.given_up
                        and h.restarts >= MAX_RESTARTS],
            "detail": [h.as_dict() for h in self.handles.values()],
        }

    def write_summary(self) -> Path:
        path = self.run_root / "runtime" / "role-controllers.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.summary(), indent=2) + "\n", encoding="utf-8")
        return path
