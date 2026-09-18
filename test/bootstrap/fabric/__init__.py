"""The network fabric: how the harness places its nodes and how it reaches them.

There are two regimes, and the whole point of this package is that everything *above* it
cannot tell them apart:

``native``
    Every node is a process on one host, in one network namespace, dialling loopback.
    Latency and jitter are whatever the host's scheduler happens to do, which is to say
    approximately nothing. This is the baseline of correctness: it isolates the protocol
    from every network variable, so an observed change has exactly one candidate
    explanation.

``core``
    Every *site* of a topology is its own network namespace, the cables between them are
    veth pairs carrying netem, and the nodes placed at a site run inside it. This is where
    delay, jitter and loss are a subject rather than a nuisance.

The seam is deliberately narrow. A fabric answers four questions and nothing else:

* **How do I run a command as this node?** ``wrap()`` returns an argv prefix — empty in
  the native regime, an entry into the node's namespace under CORE. That is what lets
  ``node_process.py`` keep its ``subprocess`` calls, its ``daemon.out`` redirection and
  its retry ladder exactly as they were.
* **How do I signal this node's daemon?** ``signal()``. Not ``os.kill``, because a CORE
  node is a *PID* namespace too: the pid MultiChain writes into its pid file is
  meaningful only inside the node, and signalling it from outside would hit an unrelated
  process or nothing at all.
* **What extra flags does this node need?** ``extra_node_args()`` — which address to bind,
  which to advertise, which to accept RPC from. Empty in the native regime.
* **What did I actually build?** ``describe()``, which becomes ``<run>/fabric.json``.

Where a node *is* — its RPC address and its peer-to-peer address — is not asked of the
fabric at all. It is on :class:`~config_loader.Profile`, because the traffic daemons are
separate processes that re-load the profile from YAML and must resolve a node without
constructing an emulator client, or starting anything, or being able to.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Protocol, runtime_checkable


class FabricError(RuntimeError):
    """The network could not be built, or could not be torn down cleanly."""


@runtime_checkable
class Fabric(Protocol):
    """What the orchestrator may ask of a network, in either regime."""

    #: ``native`` | ``core``. Recorded in the run manifest: a result whose regime has to
    #: be inferred from the profile name is not evidence.
    name: str

    def start(self) -> None:
        """Build the network and leave it ready. Idempotent."""

    def stop(self) -> None:
        """Tear it down. Must not raise: it runs in a ``finally``."""

    def wrap(self, node_id: str) -> List[str]:
        """An argv prefix that runs a command as ``node_id`` sees the network."""

    def signal(self, node_id: str, pid: int, sig: int) -> None:
        """Send ``sig`` to ``pid`` in the namespace ``pid`` is meaningful in."""

    def extra_node_args(self, node_id: str) -> List[str]:
        """``multichaind`` flags this regime requires of this node."""

    def describe(self) -> Dict[str, Any]:
        """What was built, for ``<run>/fabric.json``."""


def build(profile, run_dir=None) -> Fabric:
    """The fabric a profile asks for.

    ``core`` is imported lazily and only when it is asked for, so a machine with no CORE
    daemon — and no ``core.api.grpc`` at all — still runs every native profile. A missing
    emulator must be an error for the profile that wanted one, never for the others.
    """
    backend = profile.fabric_backend
    if backend == "native":
        from .native import NativeFabric

        return NativeFabric(profile)
    if backend == "core":
        try:
            from .core import CoreFabric
        except ImportError as exc:
            raise FabricError(
                "this profile asks for the CORE fabric, and CORE's Python API is not "
                "importable here (%s). The emulator, its namespaces and netem live in "
                "the project's container: run this through ./docker/mcsim." % exc
            ) from exc
        return CoreFabric(profile, run_dir)
    raise FabricError(
        "unknown fabric backend %r. Known backends: native, core." % backend
    )


def default_signal(pid: int, sig: int) -> None:
    """Signal a pid in this process's own namespace."""
    os.kill(pid, sig)


__all__ = ["Fabric", "FabricError", "build", "default_signal"]
