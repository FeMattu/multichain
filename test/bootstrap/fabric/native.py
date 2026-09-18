"""The native regime: every node a process on one host, dialling loopback.

This backend builds nothing and tears nothing down. It exists so that the behaviour the
harness had before there was a fabric at all is **stated** rather than implied: the empty
prefix, the direct ``os.kill``, the single host address shared by every node. Each of
those was previously a literal somewhere in the call path, and a literal is invisible
until something else needs to be true.

There is deliberately no network emulation here — no netem, no jitter, no link delay.
That is the design and not a limitation: it isolates the protocol from every network
variable, so a change in an observed quantity has exactly one candidate explanation. The
CORE backend is where the network becomes a subject.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List


class NativeFabric:
    """A network that is already there."""

    name = "native"

    def __init__(self, profile) -> None:
        self.profile = profile

    # -- lifecycle ---------------------------------------------------------------------

    def start(self) -> None:
        """Nothing to build: the loopback interface is the whole network."""

    def stop(self) -> None:
        """Nothing to tear down. Leaving a run does not disturb the host."""

    # -- running as a node -------------------------------------------------------------

    def wrap(self, node_id: str) -> List[str]:
        """No prefix. Every node already runs where the orchestrator runs."""
        return []

    def signal(self, node_id: str, pid: int, sig: int) -> None:
        """The pid is in this namespace, so it means what it says."""
        os.kill(pid, sig)

    def extra_node_args(self, node_id: str) -> List[str]:
        """None.

        Binding, advertising and RPC access are all defaults here: one interface, one
        address, and MultiChain's own default of accepting RPC on loopback only — which
        is exactly right when the orchestrator is on that loopback.
        """
        return []

    # -- evidence ----------------------------------------------------------------------

    def describe(self) -> Dict[str, Any]:
        return {
            "backend": self.name,
            "host": self.profile.host,
            "emulation": None,
            "nodes": {
                node.node_id: {
                    "rpc": "%s:%d" % (self.profile.rpc_host(node.node_id), node.rpc_port),
                    "p2p": "%s:%d" % (self.profile.data_host(node.node_id), node.port),
                }
                for node in self.profile.nodes
            },
        }


__all__ = ["NativeFabric"]
