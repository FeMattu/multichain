"""The map: sites, links, and what a link does to a packet.

A topology file names *places* and the cables between them. It says nothing about
MultiChain: which chain node sits where is the profile's business (``nodes[].location``),
and one site may carry several chain nodes or none at all.

Two things are computed here and nowhere else:

* **The impairment of a link** — either derived from the endpoints' coordinates through
  the physical model below, or taken from a named link profile. Never both, and the
  realised value records which of the two it was, because a delay that cannot be traced
  back to a model or to a stated assumption is not evidence.
* **The routing** — shortest paths over the link graph, weighted by one-way delay. The
  fabric turns them into static routes. There is no routing daemon on purpose: a
  protocol's convergence time is wall-clock nondeterminism, and it would land in the one
  part of a measurement harness that must not have any.

Nothing here imports CORE, or touches the network. It is arithmetic over two YAML files,
so it can be unit-tested and printed by ``--dry-run`` on a machine with no emulator.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

#: Mean Earth radius (IUGG). The model's published check points were computed with a
#: spherical Earth, so an ellipsoidal distance would move them by a few tenths of a
#: percent and silently break the comparison with them.
EARTH_RADIUS_KM = 6371.0088

#: Jitter is **not** a field of ``latency_model``: the maps carry none. The seven link
#: profiles that do state one sit between 0.14 and 0.17 of their own delay
#: (2.1/0.3, 5.1/0.8, 10.4/2.0, 45.8/8.0), so a derived link takes the middle of that
#: band. This is a declared assumption, not a measurement, and ``config/schema.md`` says
#: so wherever a derived number is reported.
DERIVED_JITTER_RATIO = 0.15

#: Below this a jitter value is noise against the scheduler itself, and netem rejects a
#: distribution with no jitter term at all.
DERIVED_JITTER_FLOOR_MS = 0.02

#: netem's packet limit for a derived link. The shipped profiles use 1000 everywhere
#: except the intercontinental one; a queue this size is ~12 ms of a 1 Gbit link, deep
#: enough not to be the bottleneck and shallow enough not to hide one.
DERIVED_QUEUE_PACKETS = 1000

#: Correlation of the derived jitter's normal distribution, in percent. The profiles that
#: state one use 25.
DERIVED_JITTER_CORRELATION = 25

_LINK_KINDS = ("backbone", "access")
_SITE_KINDS = ("hub", "leaf")


class TopologyError(ValueError):
    """A map that cannot be realised. Raised with a message naming the offending id."""


# --------------------------------------------------------------------------------------
# The pieces
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Site:
    """One place on the map. Becomes exactly one namespace in the fabric."""

    id: str
    kind: str          # hub | leaf
    lat: float
    lon: float
    label: str = ""
    scope: str = ""
    region: str = ""
    country: str = ""
    continent: str = ""

    @property
    def is_hub(self) -> bool:
        return self.kind == "hub"


@dataclass(frozen=True)
class Link:
    """One cable. ``kind`` selects which overhead and which capacity apply."""

    source: str
    target: str
    kind: str          # backbone | access

    @property
    def endpoints(self) -> Tuple[str, str]:
        return (self.source, self.target)


@dataclass(frozen=True)
class Impairment:
    """What one direction of a link does to a packet.

    ``origin`` is either ``derived:latency-model`` or ``profile:<name>``, and is carried
    all the way into ``<run>/fabric.json``: the number alone does not say whether it is a
    consequence of the geography or a decision somebody took.
    """

    delay_ms: float
    jitter_ms: float = 0.0
    loss_percent: float = 0.0
    bandwidth_mbps: Optional[float] = None
    queue_packets: int = DERIVED_QUEUE_PACKETS
    correlation_percent: int = 0
    distribution: str = ""
    origin: str = "derived:latency-model"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "delay_ms": round(self.delay_ms, 4),
            "jitter_ms": round(self.jitter_ms, 4),
            "loss_percent": round(self.loss_percent, 6),
            "bandwidth_mbps": self.bandwidth_mbps,
            "queue_packets": self.queue_packets,
            "origin": self.origin,
        }


@dataclass(frozen=True)
class RealisedLink:
    """A link with its two directions resolved.

    ``reverse`` is ``None`` for a symmetric link, which is the common case. It is set only
    by an asymmetric profile, and then the two directions are genuinely different qdiscs:
    averaging them would be a third network that nobody configured.
    """

    link: Link
    distance_km: float
    forward: Impairment
    reverse: Optional[Impairment] = None
    partition: bool = False

    @property
    def is_asymmetric(self) -> bool:
        return self.reverse is not None

    def as_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "source": self.link.source,
            "target": self.link.target,
            "kind": self.link.kind,
            "distance_km": round(self.distance_km, 3),
            "forward": self.forward.as_dict(),
        }
        if self.reverse is not None:
            out["reverse"] = self.reverse.as_dict()
        if self.partition:
            out["partition"] = True
        return out


# --------------------------------------------------------------------------------------
# Distance
# --------------------------------------------------------------------------------------


def great_circle_km(a: Site, b: Site) -> float:
    """Haversine distance between two sites, in kilometres."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, h)))


# --------------------------------------------------------------------------------------
# The map
# --------------------------------------------------------------------------------------


@dataclass
class Topology:
    """A validated map, with the delay model it carries."""

    name: str
    path: Path
    latency_model: Dict[str, float]
    defaults: Dict[str, float]
    sites: Dict[str, Site]
    links: List[Link]
    #: Insertion order of the sites, which fixes every index the address plan derives.
    order: List[str] = field(default_factory=list)

    # -- geometry ----------------------------------------------------------------------

    def site(self, site_id: str) -> Site:
        try:
            return self.sites[site_id]
        except KeyError:
            raise TopologyError(
                "no site %r in %s. Known sites: %s"
                % (site_id, self.path.name, ", ".join(sorted(self.sites)))
            ) from None

    def distance_km(self, a: str, b: str) -> float:
        return great_circle_km(self.site(a), self.site(b))

    def neighbours(self, site_id: str) -> List[str]:
        out = []
        for link in self.links:
            if link.source == site_id:
                out.append(link.target)
            elif link.target == site_id:
                out.append(link.source)
        return out

    # -- the physical model ------------------------------------------------------------

    def derived_delay_ms(self, link: Link) -> float:
        """``propagation · D · routing_factor + overhead``, one way.

        The overhead is the switching and aggregation term, which is not proportional to
        distance: 0.5 ms on a backbone hop, 1.0 ms on an access one.
        """
        model = self.latency_model
        distance = self.distance_km(link.source, link.target)
        overhead = (
            model["overhead_backbone_ms"]
            if link.kind == "backbone"
            else model["overhead_access_ms"]
        )
        return model["propagation_ms_per_km"] * distance * model["routing_factor"] + overhead

    def derived_loss_percent(self, link: Link) -> float:
        """Access loss is a constant; backbone loss grows with distance.

        The model states both as fractions, so they are multiplied out to the percent
        netem wants at the one place that knows which is which.
        """
        model = self.latency_model
        if link.kind == "access":
            return float(model["loss_access"]) * 100.0
        distance = self.distance_km(link.source, link.target)
        fraction = float(model["loss_backbone_base"]) + float(
            model["loss_backbone_per_km"]
        ) * distance
        return fraction * 100.0

    def derived_bandwidth_mbps(self, link: Link) -> float:
        return float(
            self.defaults["bandwidth_hub_mbps"]
            if link.kind == "backbone"
            else self.defaults["bandwidth_leaf_mbps"]
        )

    def derive(self, link: Link) -> RealisedLink:
        """One link's impairment, from the geography alone."""
        delay = self.derived_delay_ms(link)
        return RealisedLink(
            link=link,
            distance_km=self.distance_km(link.source, link.target),
            forward=Impairment(
                delay_ms=delay,
                jitter_ms=max(DERIVED_JITTER_FLOOR_MS, delay * DERIVED_JITTER_RATIO),
                loss_percent=self.derived_loss_percent(link),
                bandwidth_mbps=self.derived_bandwidth_mbps(link),
                queue_packets=DERIVED_QUEUE_PACKETS,
                correlation_percent=DERIVED_JITTER_CORRELATION,
                distribution="normal",
                origin="derived:latency-model",
            ),
        )

    def realise(
        self, profile: Optional["LinkProfile"] = None, apply_to: str = "all"
    ) -> List[RealisedLink]:
        """Every link, resolved.

        ``profile`` overrides the derived model rather than adding to it, on the links
        ``apply_to`` selects. Overriding *some* links is what makes the two operating-point
        profiles usable at all: ``partitioned`` applied to every link is a dead network,
        and ``degraded`` applied to every link is not a geography.
        """
        if apply_to not in ("all", "backbone", "access"):
            raise TopologyError(
                "network_profile.apply_to must be all, backbone or access, got %r" % apply_to
            )
        out = []
        for link in self.links:
            if profile is not None and apply_to in ("all", link.kind):
                out.append(profile.realise(link, self.distance_km(link.source, link.target)))
            else:
                out.append(self.derive(link))
        return out

    # -- routing -----------------------------------------------------------------------

    def next_hops(self) -> Dict[str, Dict[str, str]]:
        """``{from_site: {to_site: first_hop_site}}`` over shortest paths.

        Weighted by one-way delay, so the path a packet takes is the fast one rather than
        the one with fewest hops — which is what a real network would do and what makes
        the emulated end-to-end delay match the model's own prediction.

        Dijkstra from every source: 20 sites and 34 links, so the cost is irrelevant and
        an all-pairs table is far easier to turn into static routes than a path search.
        """
        weights: Dict[Tuple[str, str], float] = {}
        adjacency: Dict[str, List[str]] = {site_id: [] for site_id in self.sites}
        for link in self.links:
            cost = self.derived_delay_ms(link)
            for a, b in (link.endpoints, link.endpoints[::-1]):
                # A parallel link is not an error; the faster one wins, as it would.
                key = (a, b)
                if cost < weights.get(key, math.inf):
                    weights[key] = cost
                if b not in adjacency[a]:
                    adjacency[a].append(b)

        table: Dict[str, Dict[str, str]] = {}
        for source in self.order:
            distance: Dict[str, float] = {source: 0.0}
            first: Dict[str, str] = {}
            queue: List[Tuple[float, str]] = [(0.0, source)]
            seen: set = set()
            while queue:
                cost, here = heapq.heappop(queue)
                if here in seen:
                    continue
                seen.add(here)
                for neighbour in adjacency[here]:
                    if neighbour in seen:
                        continue
                    step = cost + weights[(here, neighbour)]
                    if step < distance.get(neighbour, math.inf):
                        distance[neighbour] = step
                        # The first hop of the path to `here` is inherited; a neighbour of
                        # the source is its own first hop.
                        first[neighbour] = first.get(here, neighbour)
                        heapq.heappush(queue, (step, neighbour))
            unreachable = sorted(set(self.sites) - seen)
            if unreachable:
                raise TopologyError(
                    "%s: site %r cannot reach %s. Every site must be reachable, or the "
                    "nodes placed there would never join the chain."
                    % (self.path.name, source, ", ".join(unreachable))
                )
            table[source] = {
                target: hop for target, hop in first.items() if target != source
            }
        return table

    def path_delay_ms(self, source: str, target: str) -> float:
        """One-way delay of the shortest path, for the wall-clock budgets."""
        if source == target:
            return 0.0
        hops = self.next_hops()
        total, here = 0.0, source
        # Bounded by the number of sites: next_hops() has already proved connectivity.
        for _ in range(len(self.sites)):
            if here == target:
                return total
            hop = hops[here][target]
            total += min(
                self.derived_delay_ms(link)
                for link in self.links
                if set(link.endpoints) == {here, hop}
            )
            here = hop
        return total

    @property
    def worst_path_delay_ms(self) -> float:
        """The slowest one-way path on the map.

        This is what the bootstrap budgets have to survive: the setup phase is a sequence
        of transactions that must confirm, and at 45.8 ms a hop that sequence is a great
        deal slower than it is on loopback.
        """
        return max(
            (
                self.path_delay_ms(a, b)
                for a in self.order
                for b in self.order
                if a != b
            ),
            default=0.0,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "sites": len(self.sites),
            "hubs": sum(1 for s in self.sites.values() if s.is_hub),
            "links": len(self.links),
            "worst_path_delay_ms": round(self.worst_path_delay_ms, 3),
        }


# --------------------------------------------------------------------------------------
# Link profiles
# --------------------------------------------------------------------------------------


@dataclass
class LinkProfile:
    """A named decision about what a link does, from ``config/network-profiles/``.

    Asymmetry is expressed by the *shape*: a profile with ``forward``/``reverse`` blocks is
    asymmetric, one without is not. There is no ``direction`` field to disagree with that.
    """

    name: str
    path: Path
    forward: Impairment
    reverse: Optional[Impairment] = None
    partition: bool = False

    def realise(self, link: Link, distance_km: float) -> RealisedLink:
        return RealisedLink(
            link=link,
            distance_km=distance_km,
            forward=self.forward,
            reverse=self.reverse,
            partition=self.partition,
        )


def _impairment_from(raw: Dict[str, Any], origin: str, where: str) -> Impairment:
    delay = _require_mapping(raw.get("delay"), "%s.delay" % where)
    loss = _require_mapping(raw.get("loss"), "%s.loss" % where)
    bandwidth = _require_mapping(raw.get("bandwidth"), "%s.bandwidth" % where)
    queue = _require_mapping(raw.get("queue"), "%s.queue" % where)
    return Impairment(
        delay_ms=float(delay.get("mean_ms", 0.0)),
        jitter_ms=float(delay.get("jitter_ms", 0.0)),
        loss_percent=float(loss.get("percent", 0.0)),
        bandwidth_mbps=float(bandwidth["mbps"]) if "mbps" in bandwidth else None,
        queue_packets=int(queue.get("limit_packets", DERIVED_QUEUE_PACKETS)),
        correlation_percent=int(delay.get("correlation_percent", 0)),
        distribution=str(delay.get("distribution", "")),
        origin=origin,
    )


def load_link_profile(path: str | Path) -> LinkProfile:
    """Read one ``network-profiles/<name>.yaml``."""
    profile_path = Path(path)
    if not profile_path.is_file():
        raise TopologyError("no such network profile: %s" % profile_path)
    raw = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise TopologyError("%s must contain a YAML mapping" % profile_path)

    name = str(raw.get("name") or profile_path.stem)
    origin = "profile:%s" % name
    allowed = {"name", "delay", "loss", "bandwidth", "queue", "forward", "reverse", "partition"}
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise TopologyError(
            "%s has unknown key(s): %s. Allowed: %s"
            % (profile_path.name, ", ".join(unknown), ", ".join(sorted(allowed)))
        )

    if "forward" in raw or "reverse" in raw:
        if "forward" not in raw or "reverse" not in raw:
            raise TopologyError(
                "%s declares only one direction. An asymmetric profile needs both "
                "`forward` and `reverse`; a symmetric one needs neither." % profile_path.name
            )
        return LinkProfile(
            name=name,
            path=profile_path,
            forward=_impairment_from(raw["forward"], origin, "%s.forward" % name),
            reverse=_impairment_from(raw["reverse"], origin, "%s.reverse" % name),
            partition=bool(raw.get("partition", False)),
        )
    return LinkProfile(
        name=name,
        path=profile_path,
        forward=_impairment_from(raw, origin, name),
        partition=bool(raw.get("partition", False)),
    )


# --------------------------------------------------------------------------------------
# Loading a map
# --------------------------------------------------------------------------------------

_REQUIRED_MODEL_KEYS = (
    "propagation_ms_per_km",
    "routing_factor",
    "overhead_backbone_ms",
    "overhead_access_ms",
    "loss_access",
    "loss_backbone_base",
    "loss_backbone_per_km",
)


def _require_mapping(raw: Any, where: str) -> Dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise TopologyError("%s must be a mapping, got %s" % (where, type(raw).__name__))
    return raw


def load_topology(path: str | Path) -> Topology:
    """Read and validate a map. Every rejection names the offending id."""
    topo_path = Path(path)
    if not topo_path.is_file():
        raise TopologyError("no such topology: %s" % topo_path)
    raw = yaml.safe_load(topo_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TopologyError("%s must contain a YAML mapping at the top level" % topo_path)

    allowed = {"name", "latency_model", "defaults", "nodes", "links"}
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise TopologyError(
            "%s has unknown top-level key(s): %s. Allowed: %s"
            % (topo_path.name, ", ".join(unknown), ", ".join(sorted(allowed)))
        )

    model = _require_mapping(raw.get("latency_model"), "latency_model")
    missing = [key for key in _REQUIRED_MODEL_KEYS if key not in model]
    if missing:
        raise TopologyError(
            "%s: latency_model is missing %s. Without them a link's impairment cannot be "
            "derived and the map can only be used with an explicit network_profile."
            % (topo_path.name, ", ".join(missing))
        )
    defaults = _require_mapping(raw.get("defaults"), "defaults")
    for key in ("bandwidth_hub_mbps", "bandwidth_leaf_mbps"):
        if key not in defaults:
            raise TopologyError("%s: defaults.%s is required" % (topo_path.name, key))

    sites: Dict[str, Site] = {}
    order: List[str] = []
    for entry in raw.get("nodes") or []:
        entry = _require_mapping(entry, "nodes[]")
        site_id = entry.get("id")
        if not isinstance(site_id, str) or not site_id:
            raise TopologyError("%s: every site needs a non-empty id" % topo_path.name)
        if site_id in sites:
            raise TopologyError("%s: duplicate site id %r" % (topo_path.name, site_id))
        kind = entry.get("kind")
        if kind not in _SITE_KINDS:
            raise TopologyError(
                "%s: site %r has kind %r, must be one of %s"
                % (topo_path.name, site_id, kind, ", ".join(_SITE_KINDS))
            )
        for key in ("lat", "lon"):
            if not isinstance(entry.get(key), (int, float)) or isinstance(entry.get(key), bool):
                raise TopologyError(
                    "%s: site %r has no numeric %s, so no delay can be derived for its "
                    "links" % (topo_path.name, site_id, key)
                )
        sites[site_id] = Site(
            id=site_id,
            kind=kind,
            lat=float(entry["lat"]),
            lon=float(entry["lon"]),
            label=str(entry.get("label", "")),
            scope=str(entry.get("scope", "")),
            region=str(entry.get("region", "")),
            country=str(entry.get("country", "")),
            continent=str(entry.get("continent", "")),
        )
        order.append(site_id)
    if not sites:
        raise TopologyError("%s declares no sites" % topo_path.name)

    links: List[Link] = []
    seen_pairs: set = set()
    for entry in raw.get("links") or []:
        entry = _require_mapping(entry, "links[]")
        source, target, kind = entry.get("source"), entry.get("target"), entry.get("kind")
        for label, value in (("source", source), ("target", target)):
            if value not in sites:
                raise TopologyError(
                    "%s: link %s %r names no site on this map"
                    % (topo_path.name, label, value)
                )
        if source == target:
            raise TopologyError("%s: link from %r to itself" % (topo_path.name, source))
        if kind not in _LINK_KINDS:
            raise TopologyError(
                "%s: link %s-%s has kind %r, must be one of %s"
                % (topo_path.name, source, target, kind, ", ".join(_LINK_KINDS))
            )
        pair = frozenset((source, target))
        if pair in seen_pairs:
            raise TopologyError(
                "%s: duplicate link between %r and %r. Two cables between the same pair "
                "would each get their own qdisc and the effective delay would depend on "
                "which one the kernel chose." % (topo_path.name, source, target)
            )
        seen_pairs.add(pair)
        links.append(Link(source=source, target=target, kind=kind))
    if not links:
        raise TopologyError("%s declares no links" % topo_path.name)

    topology = Topology(
        name=str(raw.get("name") or topo_path.stem),
        path=topo_path,
        latency_model={k: float(v) for k, v in model.items()},
        defaults={k: float(v) for k, v in defaults.items()},
        sites=sites,
        links=links,
        order=order,
    )
    # Connectivity is checked here rather than at fabric start, so a broken map is a
    # configuration error with a --dry-run in front of it, not a half-built network.
    topology.next_hops()
    return topology


__all__ = [
    "DERIVED_JITTER_FLOOR_MS",
    "DERIVED_JITTER_RATIO",
    "DERIVED_QUEUE_PACKETS",
    "EARTH_RADIUS_KM",
    "Impairment",
    "Link",
    "LinkProfile",
    "RealisedLink",
    "Site",
    "Topology",
    "TopologyError",
    "great_circle_km",
    "load_link_profile",
    "load_topology",
]
