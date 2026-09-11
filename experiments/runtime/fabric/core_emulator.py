"""CORE Network Emulator backend, driven through its gRPC API.

CORE owns the session: the harness describes the topology to it, asks it to
start, and then runs the MultiChain binaries inside the namespaces CORE
created. This is the primary backend of the brief, and the division of labour
is deliberate — CORE is better at building and supervising an emulated network
than a script is, and it gives the topology a GUI a reviewer can open.

Five details that are easy to get wrong and are handled here:

* the module is called ``core_emulator`` rather than ``core`` on purpose. CORE
  installs a top-level Python package named ``core``; a sibling module of the
  same name inside this package would shadow it under some import orders and
  produce a confusing ``ImportError`` deep in the gRPC client.
* ``InterfaceHelper`` lives in ``core.api.grpc.client``, not in ``wrappers``.
* every switch endpoint of a link needs an explicit, incrementing
  ``Interface``. CORE numbers interfaces per node and rejects a repeated id,
  so leaving ``iface2`` unset asks for interface 0 on the same switch once per
  link and all but the first are refused — in the daemon's log, from a thread
  pool, so the session still starts with a location nothing can reach.
* CORE does not register its node namespaces under ``/var/run/netns``;
  ``vnoded`` holds them and CORE reaches them over a control socket. The
  harness addresses nodes with ``nsenter``, so this backend attaches a handle
  for each node after the session starts. See :meth:`_attach_namespaces`.
* CORE builds the emulated plane and nothing else. The collectors and the RPC
  client run outside the session, so this backend builds the same management
  bridge the netns backend builds. See :meth:`_build_management_plane`.

CORE applies impairment through its own link model, symmetrically per link.
An asymmetric profile is refused rather than half-applied; use the netns
backend for those.

If CORE's Python API is not importable, or no daemon answers, ``preflight``
says so in a single sentence and the caller either falls back to ``netns``
(``backend: auto``) or stops with exit code 2 (``backend: core``).
"""

from __future__ import annotations

import ipaddress
import logging
from pathlib import Path

from ...exit_codes import EnvironmentError_, RuntimeFailure
from ...topology.models import Impairment
from ..netem.profiles import spec_from_impairment
from .base import Fabric, LinkEndpoint, RealizedLink, RealizedNode
from .netns import IFNAME_MAX, _safe

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
        self._attached_namespaces: list[str] = []
        # The management plane, named exactly as the netns backend names it so
        # that NetnsFabric.destroy_session - which is what
        # `results clean` and clean_experiment.sh call - sweeps up after a CORE
        # run that died too.
        prefix = _safe(plan.fabric.namespace_prefix, 24)
        self.bridge = _safe("%s-mgmt" % prefix, IFNAME_MAX)
        self._prefix = prefix
        self._mgmt_net = ipaddress.ip_network(plan.fabric.mgmt_subnet, strict=False)
        self._mgmt_hosts = iter(list(self._mgmt_net.hosts()))
        self.host_mgmt_ip = str(next(self._mgmt_hosts))
        self._mgmt_interfaces: list[str] = []

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

        self._add_links(session, core_client, wrappers, location_nodes)
        self._client.start_session(session)
        self._attach_namespaces(session)
        self._record(location_nodes)
        self._build_management_plane()
        self.apply_impairment()

    def _build_management_plane(self) -> None:
        """A flat, unimpaired bridge joining the harness to every CORE node.

        CORE builds the emulated plane and nothing else. The harness's
        collectors and its RPC client run in the root namespace, and the
        emulated subnet is only routable inside the session — so without this
        every poll fails, the daemons look dead, and a run completes with no
        RPC from anyone while the nodes are in fact perfectly healthy.

        CORE has a control network of its own that could serve, but it is
        session-wide configuration that changes what CORE builds. A bridge
        beside the session changes nothing CORE is measuring, and it is the
        same plane, with the same addresses and the same name, that the netns
        backend builds - so the collectors, the role scripts and the cleanup
        do not need to know which fabric they are talking to.
        """
        if not self.plan.fabric.host_uplink:
            LOG.info("host uplink disabled: collectors must run inside the fabric")
            return
        self.runner.ip("link", "del", self.bridge, check=False)
        self.runner.ip("link", "add", self.bridge, "type", "bridge",
                       what="create management bridge")
        self.runner.ip("addr", "add", "%s/%d" % (self.host_mgmt_ip, self._mgmt_net.prefixlen),
                       "dev", self.bridge)
        self.runner.ip("link", "set", self.bridge, "up")
        for position, plan_node in enumerate(self.plan.enabled_nodes):
            if plan_node.expected_state == "absent":
                continue
            realized = self.nodes.get(plan_node.id)
            if realized is None:
                continue
            mgmt_ip = str(next(self._mgmt_hosts))
            host_side = _safe("mg%d-%s" % (position, self._prefix), IFNAME_MAX)
            temp = "mgp%d" % position
            node_ns = realized.namespace
            self.runner.ip("link", "del", host_side, check=False)
            self.runner.ip("link", "add", host_side, "type", "veth", "peer", "name", temp,
                           what="management veth for %s" % plan_node.id)
            self.runner.ip("link", "set", host_side, "master", self.bridge)
            self.runner.ip("link", "set", host_side, "up")
            self.runner.ip("link", "set", temp, "netns", node_ns)
            self.runner.in_netns(node_ns, ["ip", "link", "set", temp, "name", "mgmt0"])
            self.runner.in_netns(node_ns, ["ip", "addr", "add",
                                           "%s/%d" % (mgmt_ip, self._mgmt_net.prefixlen),
                                           "dev", "mgmt0"])
            self.runner.in_netns(node_ns, ["ip", "link", "set", "mgmt0", "up"])
            realized.mgmt_ip = mgmt_ip
            realized.interfaces.append("mgmt0")
            self._mgmt_interfaces.append(host_side)
        LOG.info("management plane on %s: host %s, %d nodes",
                 self.bridge, self.host_mgmt_ip, len(self._mgmt_interfaces))

    def _attach_namespaces(self, session) -> None:
        """Register CORE's node namespaces under ``/var/run/netns``.

        CORE does not put them there. ``vnoded`` holds each node's namespace
        open and CORE reaches it over a control socket in the session
        directory, so ``ip netns list`` is empty during a CORE session and
        ``nsenter --net=/var/run/netns/<name>`` fails with "No such file or
        directory" — which is every node unreachable and not one daemon
        started.

        Everything else in this harness addresses a node that way: exec_argv,
        spawn, the collectors, the per-interface tc calls. ``ip netns attach``
        makes the missing handle out of the pid vnoded recorded, which is the
        smaller change and the better one: it binds only the NET namespace, so
        the nodes keep sharing the run directory the role scripts, the
        collectors and the analysis pipeline all write into.
        """
        # `dir` is filled in by the daemon, so it is on the session CORE hands
        # back rather than on the one we built.
        directory = getattr(session, "dir", "") or ""
        if not directory:
            started = self._client.get_session(session.id)
            directory = getattr(started, "dir", "") or "/tmp/pycore.%s" % session.id

        for plan_id, core_node in self._core_nodes.items():
            name = _core_namespace(core_node)
            pid_file = Path(directory) / ("%s.pid" % name)
            try:
                pid = pid_file.read_text().strip()
            except OSError as exc:
                raise RuntimeFailure(
                    "CORE started but node %s (%s) has no pid file at %s (%s), so its "
                    "namespace cannot be registered" % (plan_id, name, pid_file, exc),
                    hint="check /var/log/core/core-daemon.log",
                ) from exc
            # A run killed hard leaves its handle behind, and `attach` onto a
            # name that already exists fails with "File exists" at build time
            # of every later run. The name belongs to this node, so the only
            # thing this can remove is a leftover.
            self.runner.run(["ip", "netns", "del", name], privileged=True, check=False)
            self.runner.run(
                ["ip", "netns", "attach", name, pid],
                privileged=True, check=True,
                what="register the namespace of CORE node %s" % name,
            )
            self._attached_namespaces.append(name)
        LOG.info("registered %d CORE node namespaces under /var/run/netns",
                 len(self._attached_namespaces))

    def _add_links(self, session, core_client, wrappers, location_nodes) -> None:
        """Topology links between locations, plus one access link per node.

        ``InterfaceHelper`` comes from the *client* module, not from
        ``wrappers``: wrappers holds the data classes CORE exchanges
        (``Interface``, ``LinkOptions``), while the helper that allocates
        addresses out of a prefix is part of the client API.
        """
        iface_helper = core_client.InterfaceHelper(
            ip4_prefix=self.plan.fabric.link_subnet,
            ip6_prefix=None,
        )

        # CORE numbers interfaces per node and treats a repeated id as an
        # error, not as an append: a second link that leaves iface2 unset
        # asks for interface 0 on the switch again and the daemon answers
        # "node(N) interface(0) already exists". It answers it in ITS log,
        # through a thread pool, so start_session still returns and the only
        # symptom here is a session with one link missing and a location
        # nothing can reach. Every switch endpoint therefore gets its own
        # explicit, incrementing interface.
        switch_ifaces: dict[int, int] = {}

        def switch_iface(node):
            next_id = switch_ifaces.get(node.id, 0)
            switch_ifaces[node.id] = next_id + 1
            return wrappers.Interface(next_id)

        index = 0
        for link in self.plan.topology.links:
            if not link.enabled:
                continue
            index += 1
            options = _link_options(wrappers, link.impairment_forward)
            source, target = location_nodes[link.source], location_nodes[link.target]
            session.add_link(
                node1=source,
                node2=target,
                iface1=switch_iface(source),
                iface2=switch_iface(target),
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
            session.add_link(node1=core_node, node2=switch, iface1=iface,
                             iface2=switch_iface(switch))

    def _record(self, location_nodes) -> None:
        for plan_node in self.plan.enabled_nodes:
            if plan_node.expected_state == "absent":
                continue
            core_node = self._core_nodes[plan_node.id]
            self.nodes[plan_node.id] = RealizedNode(
                id=plan_node.id,
                namespace=_core_namespace(core_node),
                ip=plan_node.ip,
                # Filled in by _build_management_plane, which runs next: the
                # node has no address off the emulated plane until then.
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
        """CORE applies the symmetric part; the reverse half it cannot.

        CORE's link options are per link, not per direction, so an asymmetric
        profile loses its reverse half here.

        This used to install the missing qdisc with ``tc`` in "the namespace
        CORE created" at the target end of the link. There is no such
        namespace: a location is a CORE SWITCH, which is a bridge in the root
        namespace, and the calls went to ``/var/run/netns/r<location>`` with
        ``check=False`` — so they failed, every time, silently, and the run
        reported an asymmetric profile it had never applied.

        Refusing is the honest answer, and it matches how this harness treats
        the rest of the fabric question: a run whose impairment is quietly not
        what the descriptor asked for is worse than one that does not start.
        Use ``fabric.backend: netns`` for an asymmetric topology — it installs
        per-direction qdiscs on both veth ends and is exercised by the tests.
        """
        if self._asymmetric_interfaces:
            raise EnvironmentError_(
                "the topology has %d asymmetric link(s), and the CORE backend can only "
                "apply the symmetric half: CORE's link options are per link, not per "
                "direction." % len(self._asymmetric_interfaces),
                hint="run this topology on fabric.backend: netns, which applies "
                     "per-direction impairment on both ends of every link",
            )
        return 0

    def clear_impairment(self) -> int:
        # Nothing to clear: CORE owns every qdisc it installed and drops them
        # with the session, and apply_impairment never installs one itself.
        return 0

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
        # The management plane is this fabric's, not CORE's, so stopping the
        # session would leave the bridge and its veth ends behind. Deleting a
        # veth end takes its peer with it, node side included.
        for host_side in self._mgmt_interfaces:
            self.runner.ip("link", "del", host_side, check=False)
        self._mgmt_interfaces.clear()
        self.runner.ip("link", "del", self.bridge, check=False)

        # The handles next: they are bind mounts this fabric made, and one
        # left behind makes the next run's `ip netns attach` fail on a name
        # that is already taken.
        for name in self._attached_namespaces:
            self.runner.run(["ip", "netns", "del", name], privileged=True, check=False,
                            what="release the namespace handle of %s" % name)
        self._attached_namespaces.clear()

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
