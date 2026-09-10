"""Import the historical Shadow topology descriptions.

Two legacy shapes are understood:

``level JSON``  ``shadow/config/levels/<level>.json`` and the sibling
                ``config/topologies/intercontinental-global.json``: a node list
                with ``id``/``label``/``host``/``role``/``lat``/``lon`` plus two
                edge lists, ``backbone`` and ``access``.
``GML``         the generated ``.gml`` files, read for their explicit latency,
                jitter, packet_loss and bandwidth attributes. Used to recover a
                topology whose level JSON no longer exists, and to check that a
                converted topology reproduces the original numbers.

The converter is deliberately lossless on everything the emulator can use:
coordinates, labels, roles, the backbone/access split and the original GML node
ids all survive into the new descriptor, the last one as ``legacy_gml_id`` so
old and new edge tables stay cross-referenceable.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

COUNTRY_BY_HINT = {
    "IT": "italy", "DE": "germany", "ES": "spain", "US": "united-states",
    "SG": "singapore", "BR": "brazil", "FR": "france", "GB": "united-kingdom",
    "NL": "netherlands", "PL": "poland", "CH": "switzerland", "PT": "portugal",
    "CA": "canada", "JP": "japan", "ZA": "south-africa",
}


def slugify(text: str) -> str:
    """``HUB_US_New_York`` -> ``new-york``; ``La_Spezia`` -> ``la-spezia``."""
    parts = text.split("_")
    if parts and parts[0] == "HUB":
        parts = parts[2:]
    joined = " ".join(parts)
    normalised = unicodedata.normalize("NFKD", joined).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalised).strip("-").lower()
    return slug or "location"


def _country_hint(label: str) -> str:
    parts = label.split("_")
    if len(parts) >= 3 and parts[0] == "HUB" and parts[1] in COUNTRY_BY_HINT:
        return COUNTRY_BY_HINT[parts[1]]
    return ""


def level_json_to_topology(
    data: dict,
    *,
    name: str,
    scope: str,
    country_default: str = "",
    continent_default: str = "",
    source: str = "",
) -> dict:
    """Convert a legacy level descriptor into the new topology document.

    Returns a plain dict ready to be dumped as YAML and validated against
    ``topology.schema.json``. Host placement is *not* part of it: the caller
    gets the ``host``/``role``/``cluster`` mapping back separately, because in
    the new model that information belongs to the experiment, not to the map.
    """
    locations: list[dict] = []
    id_by_legacy: dict[int, str] = {}
    seen: set[str] = set()
    for node in data["nodes"]:
        label = node.get("label", str(node["id"]))
        slug = slugify(label)
        suffix = 2
        while slug in seen:
            slug = "%s-%d" % (slugify(label), suffix)
            suffix += 1
        seen.add(slug)
        id_by_legacy[node["id"]] = slug
        entry: dict[str, Any] = {
            "id": slug,
            "label": label,
            "kind": "hub" if node.get("role") == "miner" else "leaf",
            "scope": scope,
            "legacy_gml_id": node["id"],
        }
        country = _country_hint(label) or country_default
        if country:
            entry["country"] = country
        if continent_default:
            entry["continent"] = continent_default
        if node.get("lat") is not None:
            entry["lat"] = node["lat"]
            entry["lon"] = node["lon"]
        locations.append(entry)

    links: list[dict] = []
    for pair in data.get("backbone", []):
        links.append({
            "source": id_by_legacy[pair[0]],
            "target": id_by_legacy[pair[1]],
            "kind": "backbone",
        })
    for pair in data.get("access", []):
        links.append({
            "source": id_by_legacy[pair[0]],
            "target": id_by_legacy[pair[1]],
            "kind": "access",
        })

    placement = [
        {
            "host": node.get("host", ""),
            "role": node.get("role", ""),
            "location": id_by_legacy[node["id"]],
            "cluster": node.get("cluster", ""),
        }
        for node in data["nodes"]
        if node.get("host")
    ]

    document = {
        "name": name,
        "description": data.get("description", ""),
        "source": source or data.get("source", ""),
        "latency_model": {
            "propagation_ms_per_km": 0.005,
            "routing_factor": 1.4,
            "overhead_backbone_ms": 0.5,
            "overhead_access_ms": 1.0,
            "loopback_ms": 0.2,
            "loss_access": 0.0004,
            "loss_backbone_base": 0.0002,
            "loss_backbone_per_km": 2.0e-07,
        },
        "defaults": {"bandwidth_hub_mbps": 1000.0, "bandwidth_leaf_mbps": 200.0},
        "nodes": locations,
        "links": links,
    }
    return {"topology": document, "placement": placement}


GML_NODE_RE = re.compile(r"node\s*\[(.*?)\]", re.S)
GML_EDGE_RE = re.compile(r"edge\s*\[(.*?)\]", re.S)
GML_ATTR_RE = re.compile(r'(\w+)\s+(?:"([^"]*)"|([-\d.eE+]+))')
# re.findall returns "" (not None) for a group that did not participate, so the
# quoted branch is distinguished by emptiness, not by identity.


def parse_gml(text: str) -> dict:
    """Minimal GML reader for the historical files.

    networkx would do, but it is an optional dependency here and the files are
    machine-generated with a fixed shape: reading them directly keeps the
    converter usable in a bare environment.
    """
    nodes, edges = [], []
    for body in GML_NODE_RE.findall(text):
        attrs = {k: (s if s != "" else n) for k, s, n in GML_ATTR_RE.findall(body)}
        nodes.append(attrs)
    for body in GML_EDGE_RE.findall(text):
        attrs = {k: (s if s != "" else n) for k, s, n in GML_ATTR_RE.findall(body)}
        edges.append(attrs)
    return {"nodes": nodes, "edges": edges}


def gml_quantity_ms(value: str) -> float:
    """``"200 us"`` -> 0.2; ``"3 ms"`` -> 3.0; a bare number is milliseconds."""
    text = str(value).strip().strip('"')
    match = re.match(r"^([-\d.eE+]+)\s*(us|ms|s)?$", text)
    if not match:
        return 0.0
    magnitude = float(match.group(1))
    unit = match.group(2) or "ms"
    return {"us": magnitude / 1000.0, "ms": magnitude, "s": magnitude * 1000.0}[unit]


def gml_edge_table(path: Path | str) -> list[dict]:
    """Edge list of a legacy ``.gml``, in milliseconds and percent.

    Used by the migration check to prove that the converted YAML reproduces the
    original file's numbers rather than merely looking similar.
    """
    parsed = parse_gml(Path(path).read_text(encoding="utf-8"))
    labels = {n["id"]: n.get("label", n["id"]) for n in parsed["nodes"]}
    rows = []
    for edge in parsed["edges"]:
        if edge["source"] == edge["target"]:
            continue
        rows.append({
            "source": labels.get(edge["source"], edge["source"]),
            "target": labels.get(edge["target"], edge["target"]),
            "delay_ms": round(gml_quantity_ms(edge.get("latency", "0 ms")), 6),
            "jitter_ms": round(gml_quantity_ms(edge.get("jitter", "0 us")), 6),
            "loss_percent": round(float(edge.get("packet_loss", 0.0)) * 100.0, 9),
        })
    return sorted(rows, key=lambda r: (r["source"], r["target"]))


def load_legacy_level(path: Path | str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
