"""Docker mode: declared, dispatched, not yet built.

The brief allows Docker as an optional mode and asks that, if it cannot be
made reliable in the first pass, the interface be left in place for it. This
is that interface, and this docstring is the reason it is still a stub rather
than a half-working backend.

What works today and why it is not enough
-----------------------------------------

Running ``multichaind`` in a container is trivial: ``docker/`` already builds
an image with the toolchain and the binaries. What is *not* trivial is the
part this harness exists for.

* A container's network namespace can be handed to CORE or to the netns
  fabric (``docker run --net=none`` then move a veth in), so impairment is not
  the obstacle.
* The obstacle is the run directory. Every role script, every collector and
  the whole analysis pipeline address one shared filesystem layout —
  ``<run>/runtime/data/<node>``, ``<run>/logs/<node>``, and the ``shared/``
  directory the two-phase join uses to exchange addresses. Reproducing that
  across twenty containers means either bind-mounting the run root into all of
  them (which makes the container isolation cosmetic) or rewriting the
  collectors to fetch through the Docker API (which makes the two modes
  produce different artefacts, and comparability is the whole point).

Neither is a small change, and a backend that quietly produces slightly
different CSVs would be worse than none. The decision to record is therefore:
``native`` first, Docker behind this interface, and the choice of which of the
two designs above to take is left explicit in docs/architecture.md.

What ``mode: docker`` does today is fail at configuration time with that
explanation, rather than at minute forty of a run.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ...exit_codes import EnvironmentError_
from .base import Fabric

UNSUPPORTED = (
    "mode: docker is declared but not implemented. The obstacle is not the "
    "network - a container namespace can be linked into the fabric - but the "
    "shared run directory the role scripts, the collectors and the analysis "
    "pipeline all address. See experiments/docs/architecture.md, "
    "'Why native first', for the two candidate designs. Use mode: native."
)


class DockerFabric(Fabric):
    """Placeholder that fails early and explains itself."""

    name = "docker"

    def preflight(self) -> list[str]:
        problems = [UNSUPPORTED]
        if shutil.which("docker") is None:
            problems.append("docker is not installed either")
        return problems

    def build(self) -> None:
        raise EnvironmentError_(UNSUPPORTED)

    def teardown(self) -> None:
        return None

    def exec_argv(self, node_id: str, argv: list[str]) -> list[str]:
        raise EnvironmentError_(UNSUPPORTED)

    def spawn(self, node_id: str, argv: list[str], *, stdout: Path, stderr=None,
              env=None, cwd=None):
        raise EnvironmentError_(UNSUPPORTED)

    def apply_impairment(self, *, only_links=None, override=None) -> int:
        raise EnvironmentError_(UNSUPPORTED)

    def clear_impairment(self) -> int:
        return 0
