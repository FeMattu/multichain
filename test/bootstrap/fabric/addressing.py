"""Who gets which address, decided before anything is started.

The plan is a **pure function of the topology file**. Nothing here asks the emulator, so
``--dry-run`` prints the whole address map on a machine with no CORE daemon, and a child
process that re-loads the profile derives exactly what the orchestrator derived. What the
emulator actually assigned is still read back and written to ``<run>/fabric.json`` at
start: a derivation that is not written down is not evidence.

Three planes, three prefixes, and they are deliberately far apart in the address space so
that a packet capture says which plane it came from without a lookup:

    10.60.0.<site>/32        the site's identity, on `lo`
    10.61.<link>.0/30        one point-to-point subnet per cable
    172.30.0.<site>/24       the control plane, assigned by CORE

**A site's identity is the address chain nodes bind to**, not an address per chain node.
Every chain node at a site runs in that site's namespace, so they share its addresses and
are told apart by port — which is exactly what the profile's ``base_port + index`` map
already guarantees. Two nodes at one location are two processes at one place, which is
what co-location means.

Routing is therefore only ever *to a /32*: each site holds one route per other site and
none for the /30s, which no traffic is ever addressed to. That keeps the table at N-1
entries, makes it trivially inspectable, and means a route that is missing shows up as one
unreachable peer rather than as a subtly slower path.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from .topology import Topology, TopologyError

#: The identity plane. One /32 per site, on loopback, reachable through the routes below.
IDENTITY_PREFIX = "10.60.0"

#: The point-to-point plane. ``10.61.<link index>.0/30``: .1 is the link's source end,
#: .2 its target end. 256 cables, which is an order of magnitude past any map here.
LINK_PREFIX = "10.61"

#: The control plane, handed to CORE as a session option. CORE gives node *i* the address
#: ``prefix + i`` and puts ``prefix + 254`` in the container's root namespace, which is
#: what lets the orchestrator and the traffic daemons stay ordinary processes.
CONTROL_NETWORK = "172.30.0.0/24"
CONTROL_PREFIX = "172.30.0"

#: Interfaces are named per endpoint in link order: the first cable of a site is its
#: eth0, the second its eth1. CORE needs the number, the operator needs the name.
IFACE_TEMPLATE = "eth%d"

MAX_SITES = 250
MAX_LINKS = 250


class AddressError(ValueError):
    """A map that does not fit the plan. Raised with the number that overflowed."""


@dataclass(frozen=True)
class SiteAddress:
    """One site's three addresses and its position in every derived index."""

    site_id: str
    index: int              # 1-based; also the CORE node id and the control host part
    identity: str           # 10.60.0.<index>
    control: str            # 172.30.0.<index>

    @property
    def identity_cidr(self) -> str:
        return "%s/32" % self.identity


@dataclass(frozen=True)
class LinkAddress:
    """One cable's /30 and the interface it lands on at each end."""

    index: int              # 0-based, fixes the /30
    source: str
    target: str
    source_ip: str
    target_ip: str
    prefix_len: int
    source_iface: str
    target_iface: str
    source_iface_id: int
    target_iface_id: int

    def far_end(self, site_id: str) -> str:
        """The address to send to, seen from ``site_id``."""
        if site_id == self.source:
            return self.target_ip
        if site_id == self.target:
            return self.source_ip
        raise AddressError("%s is not an endpoint of this link" % site_id)

    def near_iface(self, site_id: str) -> str:
        if site_id == self.source:
            return self.source_iface
        if site_id == self.target:
            return self.target_iface
        raise AddressError("%s is not an endpoint of this link" % site_id)


@dataclass(frozen=True)
class Route:
    """One static route: reach ``destination`` through ``via``, sourced as ``src``.

    ``src`` is not decoration. Without it the kernel would source a packet from the /30
    address of whichever interface it left by, the peer would see a different address for
    every path, and MultiChain's peer table would fill with addresses that answer nothing.
    """

    destination: str        # a /32
    via: str
    dev: str
    src: str


class AddressPlan:
    """The whole map's addressing, derived once and answered from memory."""

    def __init__(self, topology: Topology) -> None:
        if len(topology.order) > MAX_SITES:
            raise AddressError(
                "%d sites: the identity plane %s.0/24 holds at most %d"
                % (len(topology.order), IDENTITY_PREFIX, MAX_SITES)
            )
        if len(topology.links) > MAX_LINKS:
            raise AddressError(
                "%d links: the point-to-point plane %s.0.0/16 holds at most %d /30s"
                % (len(topology.links), LINK_PREFIX, MAX_LINKS)
            )
        self.topology = topology

        # Sites are numbered from 1 in the order the file lists them, so the numbering is
        # a property of the map rather than of the run, and two runs of the same map put
        # the same node at the same address.
        self.sites: Dict[str, SiteAddress] = {}
        for position, site_id in enumerate(topology.order, start=1):
            self.sites[site_id] = SiteAddress(
                site_id=site_id,
                index=position,
                identity="%s.%d" % (IDENTITY_PREFIX, position),
                control="%s.%d" % (CONTROL_PREFIX, position),
            )

        # Interface ids restart at 0 per site and advance in link order.
        next_iface: Dict[str, int] = {site_id: 0 for site_id in topology.order}
        self.links: List[LinkAddress] = []
        for index, link in enumerate(topology.links):
            network = ipaddress.ip_network("%s.%d.0/30" % (LINK_PREFIX, index))
            hosts = list(network.hosts())
            source_id = next_iface[link.source]
            target_id = next_iface[link.target]
            next_iface[link.source] += 1
            next_iface[link.target] += 1
            self.links.append(
                LinkAddress(
                    index=index,
                    source=link.source,
                    target=link.target,
                    source_ip=str(hosts[0]),
                    target_ip=str(hosts[1]),
                    prefix_len=30,
                    source_iface=IFACE_TEMPLATE % source_id,
                    target_iface=IFACE_TEMPLATE % target_id,
                    source_iface_id=source_id,
                    target_iface_id=target_id,
                )
            )

        self._by_site: Dict[str, List[LinkAddress]] = {s: [] for s in topology.order}
        for link in self.links:
            self._by_site[link.source].append(link)
            self._by_site[link.target].append(link)

    # -- lookups -----------------------------------------------------------------------

    def site(self, site_id: str) -> SiteAddress:
        try:
            return self.sites[site_id]
        except KeyError:
            raise AddressError("no site %r in this plan" % site_id) from None

    def identity(self, site_id: str) -> str:
        """The address chain nodes at this site bind to and advertise."""
        return self.site(site_id).identity

    def control(self, site_id: str) -> str:
        """The address the harness reaches this site's RPC ports on."""
        return self.site(site_id).control

    def links_of(self, site_id: str) -> List[LinkAddress]:
        return list(self._by_site.get(site_id, ()))

    def link_between(self, a: str, b: str) -> LinkAddress:
        for link in self.links:
            if {link.source, link.target} == {a, b}:
                return link
        raise AddressError("no link between %r and %r" % (a, b))

    # -- routing -----------------------------------------------------------------------

    def routes(self) -> Dict[str, List[Route]]:
        """``{site: [Route, ...]}`` — one route per other site, over the shortest path."""
        hops = self.topology.next_hops()
        out: Dict[str, List[Route]] = {}
        for site_id in self.topology.order:
            here = self.site(site_id)
            entries: List[Route] = []
            for target, first_hop in sorted(hops[site_id].items()):
                cable = self.link_between(site_id, first_hop)
                entries.append(
                    Route(
                        destination=self.site(target).identity_cidr,
                        via=cable.far_end(site_id),
                        dev=cable.near_iface(site_id),
                        src=here.identity,
                    )
                )
            out[site_id] = entries
        return out

    # -- evidence ----------------------------------------------------------------------

    def as_dict(self) -> Dict[str, object]:
        return {
            "identity_prefix": "%s.0/24" % IDENTITY_PREFIX,
            "link_prefix": "%s.0.0/16" % LINK_PREFIX,
            "control_network": CONTROL_NETWORK,
            "sites": {
                site_id: {
                    "index": address.index,
                    "identity": address.identity,
                    "control": address.control,
                    "interfaces": [
                        {
                            "name": cable.near_iface(site_id),
                            "ip4": cable.source_ip if cable.source == site_id else cable.target_ip,
                            "prefix_len": cable.prefix_len,
                            "peer_site": cable.target if cable.source == site_id else cable.source,
                        }
                        for cable in self.links_of(site_id)
                    ],
                }
                for site_id, address in self.sites.items()
            },
            "links": [
                {
                    "index": cable.index,
                    "source": cable.source,
                    "target": cable.target,
                    "source_ip": cable.source_ip,
                    "target_ip": cable.target_ip,
                    "prefix_len": cable.prefix_len,
                }
                for cable in self.links
            ],
        }


def plan_for(topology: Topology) -> AddressPlan:
    return AddressPlan(topology)


__all__ = [
    "AddressError",
    "AddressPlan",
    "CONTROL_NETWORK",
    "CONTROL_PREFIX",
    "IDENTITY_PREFIX",
    "LINK_PREFIX",
    "LinkAddress",
    "Route",
    "SiteAddress",
    "plan_for",
]
