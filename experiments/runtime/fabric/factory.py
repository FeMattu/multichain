"""Choosing a backend, and saying clearly why the choice was made."""

from __future__ import annotations

import logging
from pathlib import Path

from ...exit_codes import ConfigError, EnvironmentError_
from ...plan import ExperimentPlan
from ..core.environment_check import require_core_or_consent
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
                backend: str | None = None, allow_fallback: bool = False,
                assume_yes: bool = False) -> Fabric:
    """Instantiate the requested backend, resolving ``auto`` through consent.

    There is deliberately NO silent path from CORE to netns. A run that
    quietly changed backend would look, be labelled and be compared exactly
    like one that did not, and the only record would be a log line. When CORE
    is unavailable and the backend is ``auto``, the decision goes to the user:
    an interactive prompt, or ``--allow-fallback-without-core``. Neither, and
    nothing starts. See runtime/core/environment_check.py.
    """
    if plan.mode == "docker" and (backend or plan.fabric.backend) != "docker":
        LOG.info("mode: docker selects the docker backend regardless of fabric.backend")
        backend = "docker"
    choice = backend or plan.fabric.backend or "auto"
    if choice not in BACKENDS and choice != "auto":
        raise ConfigError(
            "unknown fabric backend %r; known: %s" % (choice, ", ".join(sorted(BACKENDS)))
        )

    # The consent gate. It returns a concrete backend or raises; for an
    # explicit choice it simply echoes it back without consulting CORE.
    resolved, status = require_core_or_consent(
        requested_backend=choice,
        address=plan.fabric.core_address,
        allow_fallback=allow_fallback,
        assume_yes=assume_yes,
    )

    fabric = BACKENDS[resolved](plan, runner, run_root=run_root)
    problems = fabric.preflight()
    if problems:
        raise EnvironmentError_(
            "the %s fabric cannot run here:\n  - %s" % (resolved, "\n  - ".join(problems)),
            hint="run experiments/scripts/check_environment.sh for the full report",
        )
    how = "explicitly requested" if choice != "auto" else (
        "auto: CORE available" if resolved == "core" else "auto: fallback authorised")
    LOG.info("fabric backend: %s (%s)", resolved, how)
    fabric.core_status = status
    return fabric
