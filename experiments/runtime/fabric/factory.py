"""Choosing a backend, and saying clearly why the choice was made."""

from __future__ import annotations

import logging
from pathlib import Path

from ...exit_codes import ConfigError, EnvironmentError_
from ...plan import ExperimentPlan
from .base import Fabric
from .core_emulator import CoreFabric
from .docker_backend import DockerFabric
from .netns import NetnsFabric

LOG = logging.getLogger("experiments.runtime.fabric")

BACKENDS = {"core": CoreFabric, "netns": NetnsFabric, "docker": DockerFabric}


def available_backends(plan: ExperimentPlan, runner, *, run_root: Path) -> dict[str, list[str]]:
    """Every backend and the reasons it cannot run, for ``env check``."""
    report = {}
    for name, factory in BACKENDS.items():
        try:
            report[name] = factory(plan, runner, run_root=run_root).preflight()
        except Exception as exc:  # noqa: BLE001 - a broken backend is just unavailable
            report[name] = ["%s: %s" % (exc.__class__.__name__, exc)]
    return report


def make_fabric(plan: ExperimentPlan, runner, *, run_root: Path,
                backend: str | None = None) -> Fabric:
    """Instantiate the requested backend, or resolve ``auto``.

    ``auto`` prefers CORE, because it is the primary backend, and falls back to
    ``netns`` with an explicit log line saying what CORE was missing. It never
    falls back silently: a run whose backend was chosen for it must be able to
    say so from its own log and manifest.
    """
    if plan.mode == "docker" and (backend or plan.fabric.backend) != "docker":
        LOG.info("mode: docker selects the docker backend regardless of fabric.backend")
        backend = "docker"
    choice = backend or plan.fabric.backend or "auto"

    if choice != "auto":
        if choice not in BACKENDS:
            raise ConfigError(
                "unknown fabric backend %r; known: %s" % (choice, ", ".join(sorted(BACKENDS)))
            )
        fabric = BACKENDS[choice](plan, runner, run_root=run_root)
        problems = fabric.preflight()
        if problems:
            raise EnvironmentError_(
                "fabric.backend is %r but it cannot run here:\n  - %s"
                % (choice, "\n  - ".join(problems))
            )
        LOG.info("fabric backend: %s (explicitly requested)", choice)
        return fabric

    core = CoreFabric(plan, runner, run_root=run_root)
    core_problems = core.preflight()
    if not core_problems:
        LOG.info("fabric backend: core (auto)")
        return core
    netns = NetnsFabric(plan, runner, run_root=run_root)
    netns_problems = netns.preflight()
    if netns_problems:
        raise EnvironmentError_(
            "no usable fabric backend.\n  core:\n    - %s\n  netns:\n    - %s"
            % ("\n    - ".join(core_problems), "\n    - ".join(netns_problems))
        )
    LOG.info("fabric backend: netns (auto; CORE unavailable: %s)", core_problems[0])
    return netns
