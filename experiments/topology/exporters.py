"""Serialise a resolved topology for the emulator, the analysis and the archive.

Three formats, three consumers:

``to_realized_json``  the run's own record of what was actually built, links
                      and impairments included. It is what ``runtime/
                      topology-realized.json`` holds and what a reader should
                      trust over the descriptor, because a descriptor can name
                      a profile that a CLI flag then overrode.
``to_gml``            the GML the analysis pipeline already knows how to read
                      (``topology_latency`` / ``topology_edges`` in phase 1),
                      and the format CORE imports directly. Emitted with the
                      integer-microsecond magnitudes and canonical multi-line
                      blocks the historical files used, so old and new runs
                      produce byte-comparable edge tables.
``to_edges_csv``      the flat edge list, one row per direction.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Impairment, Topology


def _short_label(label: str) -> str:
    """``HUB_US_New_York`` -> ``New_York``; anything else unchanged."""
    parts = label.split("_")
    if parts and parts[0] == "HUB":
        return "_".join(parts[2:])
    return label


def to_realized_json(topology: Topology, *, extra: dict | None = None) -> dict:
    """Full description of the built network, ready to be written to disk."""
    document = {
        "name": topology.name,
        "description": topology.description,
        "source": topology.source,
        "latency_model": {
            "propagation_ms_per_km": topology.latency_model.propagation_ms_per_km,
            "routing_factor": topology.latency_model.routing_factor,
            "overhead_backbone_ms": topology.latency_model.overhead_backbone_ms,
            "overhead_access_ms": topology.latency_model.overhead_access_ms,
            "loopback_ms": topology.latency_model.loopback_ms,
        },
        "locations": [
            {
                "id": loc.id,
                "label": loc.label,
                "kind": loc.kind,
                "scope": loc.scope,
                "region": loc.region,
                "country": loc.country,
                "continent": loc.continent,
                "lat": loc.lat,
                "lon": loc.lon,
                "legacy_gml_id": loc.legacy_gml_id,
            }
            for loc in topology.locations
        ],
        "links": [
            {
                "source": link.source,
                "target": link.target,
                "kind": link.kind,
                "profile": link.profile_name,
                "enabled": link.enabled,
                "distance_km": link.distance_km,
                "asymmetric": link.asymmetric,
                "forward": link.impairment_forward.as_dict(),
                "reverse": link.impairment_reverse.as_dict(),
            }
            for link in topology.links
        ],
    }
    if extra:
        document.update(extra)
    return document


def write_realized_json(topology: Topology, path: Path, *, extra: dict | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_realized_json(topology, extra=extra), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return path


def _us(ms: float) -> int:
    """Milliseconds to whole microseconds.

    The historical files used integer microseconds because Shadow's GML parser
    rejected fractional magnitudes. The unit is kept for continuity: the edge
    tables of an old and a new run then carry the same numbers.
    """
    return int(round(float(ms) * 1000))



def _rate(mbps: float) -> str:
    """Render a capacity the way the historical files did: Gbit when whole."""
    value = float(mbps)
    if value >= 1000 and abs(value / 1000 - round(value / 1000)) < 1e-9:
        return "%d Gbit" % round(value / 1000)
    return "%d Mbit" % int(round(value))


def to_gml(topology: Topology) -> str:
    """GML with node ids taken from ``legacy_gml_id`` where one exists.

    Preserving the legacy ids matters: the historical ``topology_edges.csv``
    rows are keyed on them, and a reader comparing an old campaign to a new one
    should not have to translate.
    """
    ids: dict[str, int] = {}
    next_id = 0
    for loc in topology.locations:
        if loc.legacy_gml_id is not None:
            ids[loc.id] = loc.legacy_gml_id
            next_id = max(next_id, loc.legacy_gml_id + 1)
    for loc in topology.locations:
        if loc.id not in ids:
            ids[loc.id] = next_id
            next_id += 1

    lines = ["graph [", "  directed 0"]
    for loc in topology.locations:
        down = loc.bandwidth_down_mbps or (
            topology.defaults.get("bandwidth_hub_mbps", 1000.0)
            if loc.is_hub
            else topology.defaults.get("bandwidth_leaf_mbps", 200.0)
        )
        up = loc.bandwidth_up_mbps or (down if loc.is_hub else min(down, 50.0))
        lines += [
            "  node [",
            "    id %d" % ids[loc.id],
            '    label "%s"' % (loc.label or loc.id),
            '    host_bandwidth_down "%s"' % _rate(down),
            '    host_bandwidth_up "%s"' % _rate(up),
            "  ]",
        ]

    loopback_us = _us(topology.latency_model.loopback_ms)
    for loc in topology.locations:
        lines += [
            "  edge [",
            "    source %d" % ids[loc.id],
            "    target %d" % ids[loc.id],
            '    label "loop_%s"' % _short_label(loc.label or loc.id),
            '    latency "%d us"' % loopback_us,
            '    jitter "0 us"',
            "    packet_loss 0.0",
            "  ]",
        ]

    for link in topology.links:
        if not link.enabled:
            continue
        fwd = link.impairment_forward
        src = topology.location(link.source)
        dst = topology.location(link.target)
        label = "%s-%s" % (
            _short_label(src.label or src.id),
            _short_label(dst.label or dst.id),
        )
        lines += [
            "  edge [",
            "    source %d" % ids[link.source],
            "    target %d" % ids[link.target],
            '    label "%s"' % label,
            '    latency "%d us"' % _us(fwd.delay.mean_ms),
            '    jitter "%d us"' % _us(fwd.delay.jitter_ms),
            "    packet_loss %.7f" % (fwd.loss.percent / 100.0),
            "  ]",
        ]
    lines.append("]")
    return "\n".join(lines) + "\n"


def write_gml(topology: Topology, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_gml(topology), encoding="utf-8")
    return path


EDGE_COLUMNS = [
    "source", "target", "direction", "kind", "profile", "enabled",
    "distance_km", "delay_ms", "jitter_ms", "distribution", "loss_percent",
    "bandwidth_mbps", "queue_limit_packets", "partition",
]


def _edge_row(link, direction: str, imp: Impairment) -> dict:
    return {
        "source": link.source if direction == "forward" else link.target,
        "target": link.target if direction == "forward" else link.source,
        "direction": direction,
        "kind": link.kind,
        "profile": link.profile_name,
        "enabled": int(link.enabled),
        "distance_km": "" if link.distance_km is None else link.distance_km,
        "delay_ms": imp.delay.mean_ms,
        "jitter_ms": imp.delay.jitter_ms,
        "distribution": imp.delay.distribution,
        "loss_percent": imp.loss.percent,
        "bandwidth_mbps": "" if imp.bandwidth.mbps is None else imp.bandwidth.mbps,
        "queue_limit_packets": imp.queue.limit_packets,
        "partition": int(imp.partition),
    }


def to_edge_rows(topology: Topology) -> list[dict]:
    """One row per direction of every link, enabled or not."""
    rows = []
    for link in topology.links:
        rows.append(_edge_row(link, "forward", link.impairment_forward))
        rows.append(_edge_row(link, "reverse", link.impairment_reverse))
    return rows


def write_edges_csv(topology: Topology, path: Path) -> Path:
    import csv

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EDGE_COLUMNS)
        writer.writeheader()
        writer.writerows(to_edge_rows(topology))
    return path
