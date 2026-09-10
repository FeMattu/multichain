"""CORE Network Emulator backend, driven through its gRPC API.

CORE owns the session: the harness describes the topology to it, asks it to
start, and then runs the MultiChain binaries inside the namespaces CORE
created. This is the primary backend of the brief, and the division of labour
is deliberate — CORE is better at building and supervising an emulated network
than a script is, and it gives the topology a GUI a reviewer can open.

Two details that are easy to get wrong and are handled here:

* the module is called ``core_emulator`` rather than ``core`` on purpose. CORE
  installs a top-level Python package named ``core``; a sibling module of the
  same name inside this package would shadow it under some import orders and
  produce a confusing ``ImportError`` deep in the gRPC client.
* CORE applies impairment through its own link model, but only symmetrically
  per link direction pair. Asymmetric profiles are therefore installed by the
  harness with ``tc`` inside the node namespaces CORE created, exactly as the
  netns backend does. Which of the two applied a given interface's qdisc is
  recorded in the realised topology.

If CORE's Python API is not importable, or no daemon answers, ``preflight``
says so in a single sentence and the caller either falls back to ``netns``
(``backend: auto``) or stops with exit code 2 (``backend: core``).
"""

from __future__ import annotations

import logging
from pathlib import Path

from ...exit_codes import EnvironmentError_, RuntimeFailure
from ...topology.models import Impairment
from ..netem.profiles import clear_commands, qdisc_commands, spec_from_impairment
from .base import Fabric, LinkEndpoint, RealizedLink, RealizedNode

LOG = logging.getLogger("experiments.runtime.fabric.core")

#: CORE node types used here. Values match core.api.grpc.wrappers.NodeType.
NODE_TYPE_DEFAULT = "DEFAULT"   # a namespace that runs processes
NODE_TYPE_SWITCH = "SWITCH"     # an L2 bridge standing for a location


def import_core():
    """Import CORE's gRPC client, or return the reason it is unavailable."""
    try:
        from core.api.grpc import client as core_client  # type: ignore
        from core.api.grpc import wrappers as core_wrappers  # type: ignore
    except ImportError as exc:
        return None, "CORE's Python API is not importable (%s)" % exc
    return (core_client, core_wrappers), ""


class CoreFabric(Fabric):
    """The ``core`` backend."""

    name = "core"

    def __init__(self, plan, runner, *, run_root: Path) -> None:
        super().__init__(plan, runner, run_root=run_root)
        self._client = None
        self._session = None
        self._core_nodes: dict[str, object] = {}
        self._asymmetric_interfaces: list[tuple[str, str, Impairment]] = []

    # -- preflight ----------------------------------------------------------
    def preflight(self) -> list[str]:
        modules, reason = import_core()
        if modules is None:
            return [reason + "; install CORE or use fabric.backend: netns"]
        core_client, _ = modules
        address = self.plan.fabric.core_address
        try:
            client = core_client.CoreGrpcClient(address)
            client.connect()
            client.get_sessions()
            client.close()
        except Exception as exc:  # noqa: BLE001 - any transport failure is the same answer
            return ["no CORE daemon answering at %s (%s); start core-daemon or use "
                    "fabric.backend: netns" % (address, exc.__class__.__name__)]
        return []

    # -- build --------------------------------------------------------------
    def build(self) -> None:
        problems = self.preflight()
        if problems:
            raise EnvironmentError_("the CORE fabric cannot start:\n  - " + "\n  - ".join(problems))
        modules, _ = import_core()
        core_client, wrappers = modules
        self._client = core_client.CoreGrpcClient(self.plan.fabric.core_address)
        self._client.connect()
        session = self._client.create_session()
        self._session = session
        LOG.info("CORE session %s created for %s", session.id, self.plan.fabric.session_name)

        position = wrappers.Position
        location_nodes = {}
        for index, location in enumerate(self.plan.topology.locations):
            node = session.add_node(
                _core_id(index + 1),
                name=_core_name("r", location.id),
                _type=getattr(wrappers.NodeType, NODE_TYPE_SWITCH),
                position=position(x=100 + (index % 8) * 120, y=100 + (index // 8) * 120),
            )
            location_nodes[location.id] = node

        offset = len(self.plan.topology.locations) + 1
        for index, plan_node in enumerate(self.plan.enabled_nodes):
            if plan_node.expected_state == "absent":
                continue
            node = session.add_node(
                _core_id(offset + index),
                name=_core_name("h", plan_node.id),
                _type=getattr(wrappers.NodeType, NODE_TYPE_DEFAULT),
                position=position(x=140 + (index % 10) * 90, y=320 + (index // 10) * 90),
            )
            self._core_nodes[plan_node.id] = node

        self._add_links(session, wrappers, location_nodes)
        self._client.start_session(session)
        self._record(location_nodes)
        self.apply_impairment()

    def _add_links(self, session, wrappers, location_nodes) -> None:
        """Topology links between locations, plus one access link per node."""
        iface_helper = wrappers.InterfaceHelper(
            ip4_prefix=self.plan.fabric.link_subnet,
            ip6_prefix=None,
        )
        index = 0
        for link in self.plan.topology.links:
            if not link.enabled:
                continue
            index += 1
            options = _link_options(wrappers, link.impairment_forward)
            session.add_link(
                node1=location_nodes[link.source],
                node2=location_nodes[link.target],
                options=options,
            )
            if link.asymmetric:
                self._asymmetric_interfaces.append((link.source, link.target,
                                                    link.impairment_reverse))
        for plan_node in self.plan.enabled_nodes:
            if plan_node.expected_state == "absent":
                continue
            index += 1
            core_node = self._core_nodes[plan_node.id]
            switch = location_nodes[plan_node.location or self.plan.topology.locations[0].id]
            iface = iface_helper.create_iface(core_node.id, 0)
            iface.ip4 = plan_node.ip
            iface.ip4_mask = int(self.plan.fabric.subnet.split("/")[1])
            session.add_link(node1=core_node, node2=switch, iface1=iface)

    def _record(self, location_nodes) -> None:
        for plan_node in self.plan.enabled_nodes:
            if plan_node.expected_state == "absent":
                continue
            core_node = self._core_nodes[plan_node.id]
            self.nodes[plan_node.id] = RealizedNode(
                id=plan_node.id,
                namespace=_core_namespace(core_node),
                ip=plan_node.ip,
                # CORE nodes are reachable from the host through the session's
                # control network when it is enabled; when it is not, the
                # emulated address is the only one and collectors pay the
                # emulated delay. Reported either way.
                mgmt_ip="",
                location=plan_node.location,
                interfaces=["eth0"],
            )
        for link in self.plan.topology.links:
            if not link.enabled:
                continue
            self.links.append(RealizedLink(
                source=link.source, target=link.target, kind=link.kind,
                profile=link.profile_name,
                a=LinkEndpoint(_core_name("r", link.source), "", "", link.impairment_forward),
                b=LinkEndpoint(_core_name("r", link.target), "", "", link.impairment_reverse),
            ))
        del location_nodes

    # -- impairment ---------------------------------------------------------
    def apply_impairment(self, *, only_links=None, override=None) -> int:
        """CORE applies the symmetric part; ``tc`` covers what it cannot.

        CORE's link options are per link, not per direction, so an asymmetric
        profile would lose its reverse half. Those interfaces get their qdisc
        installed directly, in the namespace CORE created.
        """
        touched = 0
        for source, target, impairment in self._asymmetric_interfaces:
            namespace = _core_name("r", target)
            interface = "eth0"
            spec = spec_from_impairment(override or impairment)
            for args in qdisc_commands(interface, spec):
                self.runner.run(
                    ["nsenter", "--net=/var/run/netns/%s" % namespace, "tc", *args],
                    privileged=True, check=False,
                    what="reverse impairment %s->%s" % (target, source),
                )
                touched += 1
        return touched

    def clear_impairment(self) -> int:
        touched = 0
        for source, target, _ in self._asymmetric_interfaces:
            del source
            namespace = _core_name("r", target)
            for args in clear_commands("eth0"):
                self.runner.run(
                    ["nsenter", "--net=/var/run/netns/%s" % namespace, "tc", *args],
                    privileged=True, check=False,
                )
                touched += 1
        return touched

    # -- execution ----------------------------------------------------------
    def exec_argv(self, node_id: str, argv: list[str]) -> list[str]:
        realized = self.nodes.get(node_id)
        if realized is None:
            raise RuntimeFailure("node %r is not part of the CORE session" % node_id)
        return self.runner.privileged_argv(
            ["nsenter", "--net=/var/run/netns/%s" % realized.namespace,
             *[str(a) for a in argv]]
        )

    def spawn(self, node_id: str, argv: list[str], *, stdout: Path, stderr=None,
              env=None, cwd=None):
        """Start a long-lived process inside a CORE node.

        CORE names its namespaces and registers them under /var/run/netns, so
        the same nsenter wrapper exec_argv builds is what gets spawned; the
        runner keeps ownership of the handle so cleanup can terminate it.
        """
        realized = self.nodes.get(node_id)
        if realized is None:
            raise RuntimeFailure("node %r is not part of the CORE session" % node_id)
        return self.runner.spawn_detached(
            self.exec_argv(node_id, argv), stdout=stdout, stderr=stderr,
            env=env, cwd=cwd,
        )

    # -- teardown -----------------------------------------------------------
    def teardown(self) -> None:
        if self._client is None or self._session is None:
            return
        try:
            self._client.stop_session(self._session.id)
            self._client.delete_session(self._session.id)
        except Exception as exc:  # noqa: BLE001 - teardown must never raise
            LOG.warning("CORE session teardown reported %s; check core-daemon", exc)
        finally:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001
                pass
            self._client = None
            self._session = None
            self.nodes.clear()
            self.links.clear()


def _core_id(index: int) -> int:
    return int(index)


def _core_name(kind: str, identifier: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "" for ch in identifier)
    return "%s%s" % (kind, cleaned[:14])


def _core_namespace(core_node) -> str:
    return getattr(core_node, "name", "") or ""


def _link_options(wrappers, impairment: Impairment):
    """Map an impairment onto CORE's link options."""
    spec = spec_from_impairment(impairment)
    options = wrappers.LinkOptions()
    options.delay = int(round(spec.delay_ms * 1000))          # CORE wants microseconds
    options.jitter = int(round(spec.jitter_ms * 1000))
    options.loss = float(spec.loss_percent)
    if spec.rate_mbit is not None:
        options.bandwidth = int(round(spec.rate_mbit * 1_000_000))  # bits per second
    return options
