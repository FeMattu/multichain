"""The run manifest: what ran, on what, with which code.

Written early and rewritten at every phase boundary, so that a run killed
half-way still leaves a manifest describing how far it got and why it stopped.
A manifest with ``status: interrupted`` is far more useful than none.

Every field is either observed or explicitly absent. Nothing is inferred: if
the CORE version cannot be read the field is an empty string, not a guess.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..paths import REPO_ROOT

LOG = logging.getLogger("experiments.runtime.manifest")

#: The only temporal model these runs have. Written into every manifest so a
#: reader never has to infer it, and so a Shadow-era column and an emulated one
#: can never be compared by accident.
TEMPORAL_MODEL = "wall_clock_emulation"

SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git(*args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _core_version() -> str:
    for argv in (["core-daemon", "--version"], ["core-cli", "--version"]):
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        text = (proc.stdout or proc.stderr).strip()
        if text:
            return text.splitlines()[0][:120]
    return ""


def _kernel_modules() -> dict:
    """Whether the kernel can actually do what the fabric asks of it."""
    out = {}
    for module in ("sch_netem", "sch_tbf", "veth"):
        path = Path("/sys/module") / module
        out[module] = "loaded" if path.exists() else "not loaded"
    return out


@dataclass
class Manifest:
    """The run's own record of itself."""

    run_id: str
    path: Path
    data: dict = field(default_factory=dict)

    @classmethod
    def create(cls, run_id: str, run_root: Path, plan, *, backend: str,
               binaries: dict, extra: dict | None = None) -> "Manifest":
        summary = plan.summary()
        data = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "status": "starting",
            "scenario": plan.scenario,
            "experiment": plan.name,
            "description": plan.description,
            "topology": plan.topology.name,
            "topology_file": str(plan.topology_path),
            "chain_params_file": str(plan.chain_params.path),
            "descriptor": str(plan.descriptor_path),
            "seed": plan.seed,
            "mode": plan.mode,
            # The temporal model is declared, not inferred. Every earlier
            # campaign ran under Shadow, where time was simulated; a reader
            # who assumes the same of these runs will compare a simulated
            # duration with a wall-clock one and call the difference a result.
            "temporal_model": TEMPORAL_MODEL,
            # `fabric_backend` is what the harness has always called it and
            # what the reports key on. The three `network_backend_*` keys are
            # the interface the brief fixes: what was asked for, what was
            # used, and whether a human authorised the difference.
            "fabric_backend": backend,
            "network_backend_requested": backend,
            "network_backend_used": backend,
            "fallback_confirmed": False,
            "fallback_reason": None,
            "rpc_collector_mode": "",
            "git_commit": _git("rev-parse", "HEAD"),
            "git_commit_short": _git("rev-parse", "--short", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "git_dirty": bool(_git("status", "--porcelain")),
            "multichain_binaries": {name: info.as_dict() for name, info in binaries.items()},
            "multichain_binary": binaries.get("multichaind").path if binaries.get("multichaind") else "",
            "multichain_binary_hash": (
                binaries.get("multichaind").sha256 if binaries.get("multichaind") else ""
            ),
            "multichain_version": (
                binaries.get("multichaind").version if binaries.get("multichaind") else ""
            ),
            "chain": plan.multichain.chain,
            "os": "%s %s" % (platform.system(), platform.release()),
            "os_pretty": _os_pretty(),
            "kernel": platform.release(),
            "kernel_modules": _kernel_modules(),
            "python": platform.python_version(),
            "core_version": _core_version(),
            "hostname": platform.node(),
            "cpu_count": os.cpu_count(),
            "started_at": _utc_now(),
            "started_at_wallclock": _utc_now(),
            "started_at_monotonic": time.monotonic(),
            "ended_at": "",
            "ended_at_wallclock": "",
            "duration_wallclock_s": None,
            "duration_wallclock_seconds": None,
            "node_count": summary["node_count"],
            "miner_count": summary["miner_count"],
            "company_count": summary["company_count"],
            "admin_count": summary["admin_count"],
            "target_block_time_s": summary["target_block_time_s"],
            "epoch_length_blocks": summary["epoch_length_blocks"],
            "dump_function": summary["dump_function"],
            "setup_first_blocks": summary["setup_first_blocks"],
            "measure_blocks": summary["measure_blocks"],
            "planned_duration_s": summary["duration_s"],
            "schedule": plan.schedule.as_dict(),
            "nodes": [node.as_dict() for node in plan.nodes],
            "phases": [],
            "health": {},
            "processes": [],
            "errors": [],
        }
        if extra:
            data.update(extra)
        manifest = cls(run_id=run_id, path=run_root / "manifest.json", data=data)
        manifest.write()
        return manifest

    @classmethod
    def load(cls, run_root: Path) -> "Manifest":
        path = Path(run_root) / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(run_id=data.get("run_id", path.parent.name), path=path, data=data)

    # -- mutation -----------------------------------------------------------
    def set(self, **fields) -> None:
        self.data.update(fields)
        self.write()

    def phase(self, name: str, status: str, **fields) -> None:
        """Record a phase boundary. Called even when the phase failed."""
        entry = {"name": name, "status": status, "at": _utc_now()}
        entry.update(fields)
        self.data.setdefault("phases", []).append(entry)
        self.data["status"] = "running" if status == "ok" else self.data.get("status", "running")
        self.write()
        LOG.info("phase %s: %s", name, status)

    def error(self, message: str, *, phase: str = "") -> None:
        self.data.setdefault("errors", []).append(
            {"at": _utc_now(), "phase": phase, "message": str(message)[:2000]}
        )
        self.write()

    def finish(self, status: str, **fields) -> None:
        started = self.data.get("started_at_monotonic")
        self.data["status"] = status
        self.data["ended_at"] = _utc_now()
        self.data["ended_at_wallclock"] = self.data["ended_at"]
        if isinstance(started, (int, float)):
            self.data["duration_wallclock_s"] = round(time.monotonic() - started, 3)
            self.data["duration_wallclock_seconds"] = self.data["duration_wallclock_s"]
        self.data.update(fields)
        self.write()

    def write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(self.data, indent=2, default=str) + "\n",
                             encoding="utf-8")
        # Atomic replace: a manifest half-written by a run that was killed
        # while writing it is the one artefact that must never be corrupt.
        temporary.replace(self.path)


def _os_pretty() -> str:
    path = Path("/etc/os-release")
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""
