"""What every fabric must provide, and the records it hands back.

A fabric has exactly four jobs, in this order: build the network, tell the
harness how to reach and how to run things inside it, re-apply impairment on
demand, and tear itself down completely — including after a crash, from a
different process, given only the session name.

That last requirement is why :meth:`Fabric.destroy` is a classmethod-style
operation on a name rather than on live state: ``scripts/clean_experiment.sh``
must be able to clean up a session whose Python process is long gone.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path

from ...plan import ExperimentPlan, NodePlan
from ...topology.models import Impairment


@dataclass
class LinkEndpoint:
    """One side of a realised link."""

    namespace: str
    interface: str
    address: str = ""
    #: The impairment installed on this interface's egress, i.e. the direction
    #: leaving this endpoint.
    impairment: Impairment | None = None


@dataclass
class RealizedLink:
    """A link as it was actually built."""

    source: str
    target: str
    kind: str
    profile: str
    a: LinkEndpoint
    b: LinkEndpoint
    subnet: str = ""
    index: int = 0

    def as_dict(self) -> dict:
        return {
            "source": self.source, "target": self.target, "kind": self.kind,
            "profile": self.profile, "subnet": self.subnet, "index": self.index,
            "a": {"namespace": self.a.namespace, "interface": self.a.interface,
                  "address": self.a.address},
            "b": {"namespace": self.b.namespace, "interface": self.b.interface,
                  "address": self.b.address},
        }


@dataclass
class RealizedNode:
    """A MultiChain node as it was actually placed."""

    id: str
    namespace: str
    ip: str
    mgmt_ip: str
    location: str
    interfaces: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "namespace": self.namespace, "ip": self.ip,
            "mgmt_ip": self.mgmt_ip, "location": self.location,
            "interfaces": list(self.interfaces),
        }


@dataclass
class FabricStatus:
    """What a fabric reports about itself."""

    backend: str
    session: str
    up: bool
    node_count: int
    link_count: int
    detail: dict = field(default_factory=dict)


class Fabric(abc.ABC):
    """Build, address, impair and destroy an emulated network."""

    #: Short backend name, as it appears in configuration and in the manifest.
    name: str = "abstract"

    def __init__(self, plan: ExperimentPlan, runner, *, run_root: Path) -> None:
        self.plan = plan
        self.runner = runner
        self.run_root = Path(run_root)
        self.nodes: dict[str, RealizedNode] = {}
        self.links: list[RealizedLink] = []

    # -- lifecycle ----------------------------------------------------------
    @abc.abstractmethod
    def preflight(self) -> list[str]:
        """Return the reasons this backend cannot run here. Empty means ready."""

    @abc.abstractmethod
    def build(self) -> None:
        """Create namespaces/containers, links and routes, and apply impairment."""

    @abc.abstractmethod
    def teardown(self) -> None:
        """Remove everything this fabric created. Must be idempotent."""

    # -- addressing and execution ------------------------------------------
    @abc.abstractmethod
    def exec_argv(self, node_id: str, argv: list[str]) -> list[str]:
        """Wrap ``argv`` so it runs inside ``node_id``'s network context."""

    @abc.abstractmethod
    def spawn(self, node_id: str, argv: list[str], *, stdout: Path,
              stderr: Path | None = None, env: dict | None = None,
              cwd: Path | None = None):
        """Start a long-lived process inside a node. Returns a handle or None."""

    def rpc_endpoint(self, node: NodePlan) -> str:
        """Where the *controlling host* reaches this node's RPC.

        Deliberately different from the address nodes use for each other. The
        harness's own polling must not travel the impaired paths it is
        measuring, or every collector would perturb the observation; node to
        node traffic does travel them, because that is the experiment.
        """
        realized = self.nodes.get(node.id)
        host = realized.mgmt_ip if realized and realized.mgmt_ip else node.ip
        return "http://%s:%d/" % (host, node.rpc_port)

    def peer_endpoint(self, node: NodePlan) -> str:
        """Where *another node* reaches this node's RPC: the emulated address."""
        return "http://%s:%d/" % (node.ip, node.rpc_port)

    # -- impairment ---------------------------------------------------------
    @abc.abstractmethod
    def apply_impairment(self, *, only_links: list[tuple[str, str]] | None = None,
                         override: Impairment | None = None) -> int:
        """(Re-)install the impairment. Returns the number of interfaces touched."""

    @abc.abstractmethod
    def clear_impairment(self) -> int:
        """Remove every qdisc the fabric installed. Returns interfaces touched."""

    # -- reporting ----------------------------------------------------------
    def status(self) -> FabricStatus:
        return FabricStatus(
            backend=self.name,
            session=self.plan.fabric.session_name,
            up=bool(self.nodes),
            node_count=len(self.nodes),
            link_count=len(self.links),
        )

    def realized(self) -> dict:
        """Serialisable record of what was built, for ``topology-realized.json``."""
        return {
            "backend": self.name,
            "session": self.plan.fabric.session_name,
            "nodes": [n.as_dict() for n in self.nodes.values()],
            "links": [link.as_dict() for link in self.links],
        }
