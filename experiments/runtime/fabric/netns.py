"""Linux network-namespace fabric: veth pairs, static routes and tc/netem.

These are the primitives CORE drives too; here the harness drives them itself,
so a machine without CORE can still run the real binaries over a real emulated
network.

Shape of what gets built
------------------------

Two independent planes, and keeping them apart is the point:

**The emulated plane** carries everything the experiment measures — P2P
traffic and node-to-node RPC. One namespace per topology *location* acts as a
router; one namespace per *node* holds ``multichaind``. Every topology link
becomes a veth pair on its own /30, every node attaches to its location's
router on another /30, and each router forwards with static routes computed
from the minimum-delay paths of the topology. A node's identity is a /32 on
its loopback (``11.0.0.x``), so its address does not change with the path.

**The management plane** is a plain bridge in the root namespace with one
veth to every node, no impairment at all. It exists so the harness's own
collectors can poll RPC without travelling — and perturbing — the paths they
are measuring. Nodes never use it to reach each other.

Impairment goes on the emulated plane only, egress-side, one direction per
interface: the forward impairment of a link on the interface at its source
end, the reverse on the interface at its target end.

Cleanup
-------

Deleting a namespace deletes every interface inside it and every veth peer
attached to one, so teardown is a loop over namespace names plus the bridge.
It works from a fresh process given only the session prefix, which is what
lets ``clean_experiment.sh`` recover from a crash.
"""

from __future__ import annotations

import ipaddress
import logging
import re
from pathlib import Path

from ...exit_codes import EnvironmentError_, RuntimeFailure
from ...topology.models import Impairment
from ...topology.validator import next_hops
from ..netem.profiles import clear_commands, qdisc_commands, spec_from_impairment
from ..shell import which
from .base import Fabric, LinkEndpoint, RealizedLink, RealizedNode

LOG = logging.getLogger("experiments.runtime.fabric.netns")

#: Linux caps interface names at 15 characters (IFNAMSIZ - 1).
IFNAME_MAX = 15


def _safe(text: str, limit: int) -> str:
    """Shorten a name deterministically without losing uniqueness by accident."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if len(cleaned) <= limit:
        return cleaned
    digest = 0
    for byte in cleaned.encode():
        digest = (digest * 131 + byte) & 0xFFFF
    keep = limit - 5
    return "%s-%04x" % (cleaned[:keep], digest)


class NetnsFabric(Fabric):
    """The ``netns`` backend."""

    name = "netns"

    def __init__(self, plan, runner, *, run_root: Path) -> None:
        super().__init__(plan, runner, run_root=run_root)
        prefix = plan.fabric.namespace_prefix
        self.prefix = _safe(prefix, 24)
        self.bridge = _safe("%s-mgmt" % self.prefix, IFNAME_MAX)
        self._link_pool = ipaddress.ip_network(plan.fabric.link_subnet, strict=False).subnets(
            new_prefix=30
        )
        self._mgmt_net = ipaddress.ip_network(plan.fabric.mgmt_subnet, strict=False)
        self._mgmt_hosts = iter(list(self._mgmt_net.hosts()))
        self.host_mgmt_ip = str(next(self._mgmt_hosts))
        self.router_namespaces: dict[str, str] = {}
        self._router_interfaces: dict[str, list[str]] = {}
        self._impaired: list[tuple[str, str, Impairment, str]] = []

    # -- naming -------------------------------------------------------------
    def node_namespace(self, node_id: str) -> str:
        return "%s-h-%s" % (self.prefix, node_id)

    def router_namespace(self, location: str) -> str:
        return "%s-r-%s" % (self.prefix, _safe(location, 20))

    @staticmethod
    def link_interface(index: int) -> str:
        return "l%d" % index

    # -- preflight ----------------------------------------------------------
    def preflight(self) -> list[str]:
        problems = []
        for tool in ("ip", "tc"):
            if which(tool) is None:
                problems.append(
                    "%s is not installed (iproute2); the netns fabric cannot build links" % tool
                )
        if not self.runner.dry_run and not self.runner.is_root and not self.runner.sudo:
            problems.append("creating namespaces needs root and sudo is unavailable")
        if not Path("/proc/sys/net/ipv4/ip_forward").exists():
            problems.append("/proc/sys/net/ipv4 is missing: no IPv4 stack to configure")
        nodes = self.plan.enabled_nodes
        try:
            subnet = ipaddress.ip_network(self.plan.fabric.subnet, strict=False)
        except ValueError as exc:
            problems.append("fabric.subnet is not a network: %s" % exc)
        else:
            if subnet.num_addresses - 2 < len(nodes):
                problems.append(
                    "fabric.subnet %s holds %d usable addresses for %d nodes"
                    % (subnet, subnet.num_addresses - 2, len(nodes))
                )
        if self._mgmt_net.num_addresses - 2 < len(nodes) + 1:
            problems.append(
                "fabric.mgmt_subnet %s is too small for %d nodes plus the host"
                % (self._mgmt_net, len(nodes))
            )
        return problems

    # -- build --------------------------------------------------------------
    def build(self) -> None:
        problems = self.preflight()
        if problems:
            raise EnvironmentError_(
                "the netns fabric cannot start:\n  - " + "\n  - ".join(problems)
            )
        self.runner.require_privileges()
        LOG.info("building netns fabric: %d locations, %d nodes",
                 len(self.plan.topology.locations), len(self.plan.enabled_nodes))
        self._create_namespaces()
        self._create_backbone_links()
        self._attach_nodes()
        self._install_routes()
        self._build_management_plane()
        applied = self.apply_impairment()
        LOG.info("fabric up: %d links, impairment on %d interfaces",
                 len(self.links), applied)

    def _create_namespaces(self) -> None:
        for location in self.plan.topology.locations:
            namespace = self.router_namespace(location.id)
            self.router_namespaces[location.id] = namespace
            self._router_interfaces.setdefault(location.id, [])
            self.runner.ip("netns", "add", namespace, what="create router %s" % location.id)
            self.runner.in_netns(namespace, ["ip", "link", "set", "lo", "up"])
            self.runner.in_netns(
                namespace, ["sysctl", "-q", "-w", "net.ipv4.ip_forward=1"],
                what="enable forwarding on %s" % namespace,
            )
            self._relax_rp_filter(namespace)
        for node in self.plan.enabled_nodes:
            if node.expected_state == "absent":
                LOG.info("node %s is declared absent: no namespace created", node.id)
                continue
            namespace = self.node_namespace(node.id)
            self.runner.ip("netns", "add", namespace, what="create node %s" % node.id)
            self.runner.in_netns(namespace, ["ip", "link", "set", "lo", "up"])
            # Identity address on the loopback: independent of the path taken.
            self.runner.in_netns(
                namespace, ["ip", "addr", "add", "%s/32" % node.ip, "dev", "lo"],
                what="address node %s" % node.id,
            )
            self._relax_rp_filter(namespace)


    def _relax_rp_filter(self, namespace: str) -> None:
        """Turn off strict reverse-path filtering in a namespace.

        With a mesh of hubs a packet's return path need not be the interface it
        arrived on, and strict rp_filter (the default on many distributions)
        silently drops such packets. Silently is the problem: there is no log,
        no ICMP, just a connection that never establishes. Loose mode would
        also do; off is chosen because the fabric is a closed emulated network
        with no untrusted source to protect against.
        """
        for key in ("net.ipv4.conf.all.rp_filter", "net.ipv4.conf.default.rp_filter"):
            self.runner.in_netns(namespace, ["sysctl", "-q", "-w", "%s=0" % key],
                                 check=False)

    def _next_link_subnet(self) -> ipaddress.IPv4Network:
        try:
            return next(self._link_pool)
        except StopIteration:  # pragma: no cover - only with a tiny link_subnet
            raise RuntimeFailure(
                "fabric.link_subnet %s ran out of /30s" % self.plan.fabric.link_subnet
            ) from None

    def _veth(self, index: int, ns_a: str, ns_b: str) -> tuple[str, str, ipaddress.IPv4Network,
                                                               str, str]:
        """Create one veth pair between two namespaces on a fresh /30."""
        temp_a, temp_b = "pe%da" % index, "pe%db" % index
        iface = self.link_interface(index)
        subnet = self._next_link_subnet()
        addr_a, addr_b = list(subnet.hosts())[:2]
        self.runner.ip("link", "add", temp_a, "type", "veth", "peer", "name", temp_b,
                       what="veth for link %d" % index)
        self.runner.ip("link", "set", temp_a, "netns", ns_a)
        self.runner.ip("link", "set", temp_b, "netns", ns_b)
        for namespace, temp, address in ((ns_a, temp_a, addr_a), (ns_b, temp_b, addr_b)):
            self.runner.in_netns(namespace, ["ip", "link", "set", temp, "name", iface])
            self.runner.in_netns(
                namespace, ["ip", "addr", "add", "%s/%d" % (address, subnet.prefixlen),
                            "dev", iface])
            self.runner.in_netns(namespace, ["ip", "link", "set", iface, "up"])
        return iface, iface, subnet, str(addr_a), str(addr_b)

    def _create_backbone_links(self) -> None:
        index = 0
        for link in self.plan.topology.links:
            if not link.enabled:
                LOG.info("link %s--%s is disabled: not created", link.source, link.target)
                continue
            if link.kind == "access" and self._location_has_nodes(link.source):
                # An access link whose leaf carries nodes is still a
                # router-to-router link here: nodes attach to their own
                # location's router, never directly to a remote one.
                pass
            ns_a = self.router_namespaces[link.source]
            ns_b = self.router_namespaces[link.target]
            index += 1
            iface_a, iface_b, subnet, addr_a, addr_b = self._veth(index, ns_a, ns_b)
            self._router_interfaces[link.source].append(iface_a)
            self._router_interfaces[link.target].append(iface_b)
            self.links.append(RealizedLink(
                source=link.source, target=link.target, kind=link.kind,
                profile=link.profile_name, subnet=str(subnet), index=index,
                a=LinkEndpoint(ns_a, iface_a, addr_a, link.impairment_forward),
                b=LinkEndpoint(ns_b, iface_b, addr_b, link.impairment_reverse),
            ))
        self._link_index = index

    def _location_has_nodes(self, location: str) -> bool:
        return any(n.location == location for n in self.plan.enabled_nodes)

    def _attach_nodes(self) -> None:
        """One access veth per node, from its namespace to its location's router."""
        index = self._link_index
        self._node_gateway: dict[str, str] = {}
        self._node_access: dict[str, tuple[str, str]] = {}
        for node in self.plan.enabled_nodes:
            if node.expected_state == "absent":
                continue
            location = node.location or self.plan.topology.locations[0].id
            router_ns = self.router_namespaces[location]
            node_ns = self.node_namespace(node.id)
            index += 1
            subnet = self._next_link_subnet()
            node_addr, router_addr = list(subnet.hosts())[:2]
            temp_a, temp_b = "pe%da" % index, "pe%db" % index
            router_iface = self.link_interface(index)
            self.runner.ip("link", "add", temp_a, "type", "veth", "peer", "name", temp_b,
                           what="access veth for %s" % node.id)
            self.runner.ip("link", "set", temp_a, "netns", node_ns)
            self.runner.ip("link", "set", temp_b, "netns", router_ns)
            self.runner.in_netns(node_ns, ["ip", "link", "set", temp_a, "name", "eth0"])
            self.runner.in_netns(node_ns, ["ip", "addr", "add",
                                           "%s/%d" % (node_addr, subnet.prefixlen), "dev", "eth0"])
            self.runner.in_netns(node_ns, ["ip", "link", "set", "eth0", "up"])
            self.runner.in_netns(router_ns, ["ip", "link", "set", temp_b, "name", router_iface])
            self.runner.in_netns(router_ns, ["ip", "addr", "add",
                                             "%s/%d" % (router_addr, subnet.prefixlen),
                                             "dev", router_iface])
            self.runner.in_netns(router_ns, ["ip", "link", "set", router_iface, "up"])
            # The node reaches the whole experiment subnet through its router.
            #
            # `src` is load-bearing, not decoration. Without it the kernel picks
            # the interface address - the /30 link address - as the source of
            # every outgoing packet, because that is the address on the
            # outgoing device. No other node has a route back to a /30, so the
            # SYN arrives and the SYN-ACK is undeliverable: the symptom is
            # "Couldn't connect to the seed node", several minutes into a run,
            # with both daemons apparently healthy. Pinning src to the node's
            # identity /32 makes every packet come from an address the whole
            # fabric can route.
            self.runner.in_netns(node_ns, ["ip", "route", "add", self.plan.fabric.subnet,
                                           "via", str(router_addr), "dev", "eth0",
                                           "src", node.ip])
            # The router reaches this node's /32 directly on the access link.
            self.runner.in_netns(router_ns, ["ip", "route", "add", "%s/32" % node.ip,
                                             "via", str(node_addr), "dev", router_iface])
            self._router_interfaces[location].append(router_iface)
            self._node_gateway[node.id] = str(router_addr)
            self._node_access[node.id] = (node_ns, "eth0")
            self.nodes[node.id] = RealizedNode(
                id=node.id, namespace=node_ns, ip=node.ip, mgmt_ip="",
                location=location, interfaces=["lo", "eth0"],
            )
            # An access link is impaired too: its profile is what the topology
            # says about the last mile.
            access = self._access_impairment(location)
            self.links.append(RealizedLink(
                source=node.id, target=location, kind="node-access",
                profile=access[2], subnet=str(subnet), index=index,
                a=LinkEndpoint(node_ns, "eth0", str(node_addr), access[0]),
                b=LinkEndpoint(router_ns, router_iface, str(router_addr), access[1]),
            ))
        self._link_index = index

    def _access_impairment(self, location: str) -> tuple[Impairment, Impairment, str]:
        """Impairment of the hop between a node and its own location's router.

        The topology already models the site-to-hub link when the location is a
        leaf; the node-to-site hop is inside the site, so it gets the ``lan``
        profile if one is defined and no impairment otherwise. Modelling it
        twice would double-count the access delay the historical latency model
        already contains.
        """
        del location
        none = Impairment()
        return none, none, "none:intra-site"

    def _install_routes(self) -> None:
        """Static routes on every router, following the minimum-delay paths."""
        hops = next_hops(self.plan.topology)
        address_of: dict[tuple[str, str], str] = {}
        for link in self.links:
            if link.kind == "node-access":
                continue
            address_of[(link.source, link.target)] = link.b.address
            address_of[(link.target, link.source)] = link.a.address
        interface_of: dict[tuple[str, str], str] = {}
        for link in self.links:
            if link.kind == "node-access":
                continue
            interface_of[(link.source, link.target)] = link.a.interface
            interface_of[(link.target, link.source)] = link.b.interface

        for location, namespace in self.router_namespaces.items():
            for node in self.plan.enabled_nodes:
                if node.expected_state == "absent" or node.location == location:
                    continue  # already routed on the access link
                destination = node.location
                hop = hops.get(location, {}).get(destination)
                if hop is None:
                    LOG.warning(
                        "no path from %s to %s: node %s is unreachable from there",
                        location, destination, node.id)
                    continue
                via = address_of.get((location, hop))
                dev = interface_of.get((location, hop))
                if via is None or dev is None:  # pragma: no cover - defensive
                    LOG.warning("no interface from %s towards %s", location, hop)
                    continue
                self.runner.in_netns(
                    namespace,
                    ["ip", "route", "replace", "%s/32" % node.ip, "via", via, "dev", dev],
                    what="route %s -> %s" % (location, node.id),
                )

    def _build_management_plane(self) -> None:
        """A flat, unimpaired bridge joining the host to every node."""
        if not self.plan.fabric.host_uplink:
            LOG.info("host uplink disabled: collectors must run inside the fabric")
            return
        self.runner.ip("link", "add", self.bridge, "type", "bridge",
                       what="create management bridge")
        self.runner.ip("addr", "add", "%s/%d" % (self.host_mgmt_ip, self._mgmt_net.prefixlen),
                       "dev", self.bridge)
        self.runner.ip("link", "set", self.bridge, "up")
        for position, node in enumerate(self.plan.enabled_nodes):
            if node.expected_state == "absent":
                continue
            mgmt_ip = str(next(self._mgmt_hosts))
            host_side = _safe("mg%d-%s" % (position, self.prefix), IFNAME_MAX)
            temp = "mgp%d" % position
            node_ns = self.node_namespace(node.id)
            self.runner.ip("link", "add", host_side, "type", "veth", "peer", "name", temp,
                           what="management veth for %s" % node.id)
            self.runner.ip("link", "set", host_side, "master", self.bridge)
            self.runner.ip("link", "set", host_side, "up")
            self.runner.ip("link", "set", temp, "netns", node_ns)
            self.runner.in_netns(node_ns, ["ip", "link", "set", temp, "name", "mgmt0"])
            self.runner.in_netns(node_ns, ["ip", "addr", "add",
                                           "%s/%d" % (mgmt_ip, self._mgmt_net.prefixlen),
                                           "dev", "mgmt0"])
            self.runner.in_netns(node_ns, ["ip", "link", "set", "mgmt0", "up"])
            if node.id in self.nodes:
                self.nodes[node.id].mgmt_ip = mgmt_ip
                self.nodes[node.id].interfaces.append("mgmt0")

    # -- impairment ---------------------------------------------------------
    def apply_impairment(self, *, only_links: list[tuple[str, str]] | None = None,
                         override: Impairment | None = None) -> int:
        wanted = None if only_links is None else {frozenset(p) for p in only_links}
        touched = 0
        for link in self.links:
            if link.kind == "node-access":
                continue
            if wanted is not None and frozenset((link.source, link.target)) not in wanted:
                continue
            for endpoint in (link.a, link.b):
                impairment = override if override is not None else endpoint.impairment
                if impairment is None:
                    continue
                spec = spec_from_impairment(impairment)
                for args in qdisc_commands(endpoint.interface, spec):
                    self.runner.in_netns(
                        endpoint.namespace, ["tc", *args],
                        what="netem on %s/%s" % (endpoint.namespace, endpoint.interface),
                    )
                    touched += 1
        return touched

    def clear_impairment(self) -> int:
        touched = 0
        for link in self.links:
            for endpoint in (link.a, link.b):
                for args in clear_commands(endpoint.interface):
                    # A missing qdisc is not an error here: clearing must be
                    # safe to run twice, and after a partial build.
                    self.runner.in_netns(endpoint.namespace, ["tc", *args], check=False)
                    touched += 1
        return touched

    # -- execution ----------------------------------------------------------
    def exec_argv(self, node_id: str, argv: list[str]) -> list[str]:
        namespace = self.node_namespace(node_id)
        return self.runner.privileged_argv(
            ["ip", "netns", "exec", namespace, *[str(a) for a in argv]]
        )

    def spawn(self, node_id: str, argv: list[str], *, stdout: Path,
              stderr: Path | None = None, env: dict | None = None,
              cwd: Path | None = None):
        return self.runner.spawn_in_netns(
            self.node_namespace(node_id), argv, stdout=stdout, stderr=stderr,
            env=env, cwd=cwd,
        )

    # -- teardown -----------------------------------------------------------
    def teardown(self) -> None:
        self.destroy_session(self.runner, self.prefix, self.bridge)
        self.nodes.clear()
        self.links.clear()

    @staticmethod
    def existing_namespaces(runner, prefix: str) -> list[str]:
        """Namespaces belonging to a session, discovered from the system.

        Reads the live list rather than remembering it, so cleanup works from a
        process that never built anything.
        """
        result = runner.run(["ip", "-o", "netns", "list"], privileged=True, check=False)
        names = []
        for line in result.stdout.splitlines():
            name = line.split()[0] if line.split() else ""
            if name.startswith(prefix + "-"):
                names.append(name)
        return names

    @classmethod
    def destroy_session(cls, runner, prefix: str, bridge: str | None = None) -> int:
        """Remove every namespace and the bridge of a session. Idempotent."""
        removed = 0
        for namespace in cls.existing_namespaces(runner, prefix):
            runner.ip("netns", "del", namespace, check=False)
            removed += 1
        bridge = bridge or _safe("%s-mgmt" % prefix, IFNAME_MAX)
        runner.ip("link", "del", bridge, check=False)
        # Veth ends left in the root namespace by a build that died halfway.
        listing = runner.run(["ip", "-o", "link", "show"], privileged=True, check=False)
        for line in listing.stdout.splitlines():
            match = re.match(r"^\d+:\s+((?:pe|mgp|mg)\S*?)[@:]", line)
            if match:
                runner.ip("link", "del", match.group(1), check=False)
                removed += 1
        if removed:
            LOG.info("removed %d leftover objects for session prefix %r", removed, prefix)
        return removed
