"""Typed model of an emulated topology and of the impairment applied to it.

Three objects and nothing else:

``NetworkProfile``  what a link does to a packet, per direction.
``Location``        a point of presence: coordinates, scope, capacity.
``Topology``        locations plus links, with the physical delay model that
                    derives a link's delay from the two endpoints' coordinates
                    when the link does not name a profile explicitly.

The delay model is the one the Shadow suite used, kept identical on purpose:
it is what makes a regional run and an intercontinental run comparable, and
changing it would silently invalidate every historical comparison.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Iterable, Iterator

EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class LatencyModel:
    """Great-circle distance to one-way delay.

        one_way_ms = propagation_ms_per_km * D_km * routing_factor + overhead

    ``propagation_ms_per_km`` is fibre propagation (v ~ 2e5 km/s),
    ``routing_factor`` accounts for the physical path being longer than the
    straight line, and the overhead is the non-distance switching cost, larger
    on the access link than on the backbone.

    Validated against real measurements (README of the historical suite):
    Bologna-Geneva 840 km -> 12.8 ms model vs ~9.5 ms real; Milan-New York
    6464 km -> 91.5 ms model vs ~90 ms real. Slightly pessimistic on short
    hops, accurate on the long ones that dominate the experiment.
    """

    propagation_ms_per_km: float = 0.005
    routing_factor: float = 1.4
    overhead_backbone_ms: float = 0.5
    overhead_access_ms: float = 1.0
    loopback_ms: float = 0.2
    loss_access: float = 0.0004
    loss_backbone_base: float = 0.0002
    loss_backbone_per_km: float = 2.0e-7

    def one_way_ms(self, distance_km: float, *, access: bool) -> float:
        overhead = self.overhead_access_ms if access else self.overhead_backbone_ms
        return self.propagation_ms_per_km * distance_km * self.routing_factor + overhead

    def loss_fraction(self, distance_km: float, *, access: bool) -> float:
        if access:
            return self.loss_access
        return self.loss_backbone_base + self.loss_backbone_per_km * distance_km

    @classmethod
    def from_dict(cls, data: dict | None) -> "LatencyModel":
        return cls(**(data or {}))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class Delay:
    mean_ms: float = 0.0
    jitter_ms: float = 0.0
    correlation_percent: float = 0.0
    distribution: str = "normal"


@dataclass(frozen=True)
class Loss:
    percent: float = 0.0
    correlation_percent: float = 0.0


@dataclass(frozen=True)
class Bandwidth:
    mbps: float | None = None
    burst_bytes: int | None = None


@dataclass(frozen=True)
class Queue:
    limit_packets: int = 1000


@dataclass(frozen=True)
class Impairment:
    """What one direction of a link does to a packet."""

    delay: Delay = field(default_factory=Delay)
    loss: Loss = field(default_factory=Loss)
    bandwidth: Bandwidth = field(default_factory=Bandwidth)
    queue: Queue = field(default_factory=Queue)
    partition: bool = False

    @classmethod
    def from_dict(cls, data: dict | None) -> "Impairment":
        data = data or {}
        return cls(
            delay=Delay(**(data.get("delay") or {})),
            loss=Loss(**(data.get("loss") or {})),
            bandwidth=Bandwidth(**(data.get("bandwidth") or {})),
            queue=Queue(**(data.get("queue") or {})),
            partition=bool(data.get("partition", False)),
        )

    def as_dict(self) -> dict:
        return {
            "delay": {
                "mean_ms": self.delay.mean_ms,
                "jitter_ms": self.delay.jitter_ms,
                "correlation_percent": self.delay.correlation_percent,
                "distribution": self.delay.distribution,
            },
            "loss": {
                "percent": self.loss.percent,
                "correlation_percent": self.loss.correlation_percent,
            },
            "bandwidth": {"mbps": self.bandwidth.mbps, "burst_bytes": self.bandwidth.burst_bytes},
            "queue": {"limit_packets": self.queue.limit_packets},
            "partition": self.partition,
        }


@dataclass(frozen=True)
class NetworkProfile:
    """A named impairment, symmetric or not.

    ``source`` is not decoration: the harness reports it in every manifest so
    that a delay value can always be traced back to the measurement or the
    assumption it came from.
    """

    name: str
    description: str = ""
    source: str = ""
    direction: str = "bidirectional"
    seed: int | None = None
    forward: Impairment = field(default_factory=Impairment)
    reverse: Impairment = field(default_factory=Impairment)

    @property
    def symmetric(self) -> bool:
        return self.direction == "bidirectional"

    @classmethod
    def from_dict(cls, data: dict) -> "NetworkProfile":
        direction = data.get("direction", "bidirectional")
        if direction == "asymmetric":
            forward = Impairment.from_dict(data.get("forward"))
            reverse = Impairment.from_dict(data.get("reverse"))
        else:
            shared = Impairment.from_dict(data)
            forward = reverse = shared
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            source=data.get("source", ""),
            direction=direction,
            seed=data.get("seed"),
            forward=forward,
            reverse=reverse,
        )

    def merged(self, overrides: dict | None) -> "NetworkProfile":
        """Return a copy with per-link overrides applied.

        Overrides use the same shape as a profile file. A symmetric profile
        overridden with ``forward``/``reverse`` becomes asymmetric.
        """
        if not overrides:
            return self
        data = {
            "name": self.name,
            "description": overrides.get("description", self.description),
            "source": overrides.get("source", self.source),
            "direction": overrides.get("direction", self.direction),
            "seed": overrides.get("seed", self.seed),
        }
        if "forward" in overrides or "reverse" in overrides:
            data["direction"] = "asymmetric"
            data["forward"] = _merge_impairment(self.forward, overrides.get("forward"))
            data["reverse"] = _merge_impairment(self.reverse, overrides.get("reverse"))
            return NetworkProfile(
                name=data["name"], description=data["description"], source=data["source"],
                direction="asymmetric", seed=data["seed"],
                forward=Impairment.from_dict(data["forward"]),
                reverse=Impairment.from_dict(data["reverse"]),
            )
        merged = Impairment.from_dict(_merge_impairment(self.forward, overrides))
        return NetworkProfile(
            name=data["name"], description=data["description"], source=data["source"],
            direction="bidirectional", seed=data["seed"], forward=merged, reverse=merged,
        )


def _merge_impairment(base: Impairment, overrides: dict | None) -> dict:
    """Deep-merge an override dict onto an impairment, key by key."""
    out = base.as_dict()
    for section in ("delay", "loss", "bandwidth", "queue"):
        if overrides and section in overrides and overrides[section] is not None:
            out[section] = {**out[section], **overrides[section]}
    if overrides and "partition" in overrides:
        out["partition"] = bool(overrides["partition"])
    return out


@dataclass(frozen=True)
class Location:
    """A point of presence in the emulated network."""

    id: str
    label: str = ""
    kind: str = "leaf"
    scope: str = "regional"
    region: str = ""
    country: str = ""
    continent: str = ""
    lat: float | None = None
    lon: float | None = None
    legacy_gml_id: int | None = None
    bandwidth_down_mbps: float | None = None
    bandwidth_up_mbps: float | None = None

    @property
    def is_hub(self) -> bool:
        return self.kind == "hub"


@dataclass(frozen=True)
class Link:
    """One edge of the topology, with the impairment already resolved."""

    source: str
    target: str
    kind: str = "backbone"
    profile_name: str = ""
    impairment_forward: Impairment = field(default_factory=Impairment)
    impairment_reverse: Impairment = field(default_factory=Impairment)
    enabled: bool = True
    distance_km: float | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.source, self.target)

    @property
    def asymmetric(self) -> bool:
        return self.impairment_forward != self.impairment_reverse


@dataclass
class Topology:
    """Locations plus links. Node placement is not part of it."""

    name: str
    description: str = ""
    source: str = ""
    latency_model: LatencyModel = field(default_factory=LatencyModel)
    locations: list[Location] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    defaults: dict = field(default_factory=dict)

    def location(self, location_id: str) -> Location:
        for loc in self.locations:
            if loc.id == location_id:
                return loc
        raise KeyError(location_id)

    @property
    def location_ids(self) -> list[str]:
        return [loc.id for loc in self.locations]

    def enabled_links(self) -> Iterator[Link]:
        return (link for link in self.links if link.enabled)

    def neighbours(self, location_id: str) -> list[str]:
        out = []
        for link in self.enabled_links():
            if link.source == location_id:
                out.append(link.target)
            elif link.target == location_id:
                out.append(link.source)
        return out

    def with_links(self, links: Iterable[Link]) -> "Topology":
        return replace(self, links=list(links))
