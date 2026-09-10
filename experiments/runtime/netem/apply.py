"""Applying an impairment to a network that is already running.

Separate from the fabric's own ``build`` step because changing conditions
mid-run is an experiment in itself: partitioning a link at a known height,
degrading one peer's uplink, or lifting an impairment to see how fast the
chain reconverges. Every change is recorded in ``runtime/netem-events.jsonl``
with both clocks, so the analysis can align a change in behaviour with the
change in conditions that caused it.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from ...topology.models import Impairment, NetworkProfile
from .profiles import describe, spec_from_impairment

LOG = logging.getLogger("experiments.runtime.netem.apply")

EVENTS_FILE = "netem-events.jsonl"


def record_event(run_root: Path, event: dict) -> None:
    """Append one impairment change to the run's event log."""
    path = Path(run_root) / "runtime" / EVENTS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp_wallclock": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "timestamp_monotonic": round(time.monotonic(), 6),
        **event,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, default=str) + "\n")


def apply_profile(fabric, profile: NetworkProfile, run_root: Path, *,
                  links: list[tuple[str, str]] | None = None) -> dict:
    """Install one profile on some or all of the fabric's links.

    ``links`` selects link endpoints by location id; ``None`` means every
    link. An asymmetric profile keeps its two directions: the forward
    impairment goes on the source-side interface, the reverse on the target
    side, because netem shapes egress only.
    """
    touched = 0
    selected = None if links is None else {frozenset(pair) for pair in links}
    for link in fabric.links:
        if link.kind == "node-access":
            continue
        if selected is not None and frozenset((link.source, link.target)) not in selected:
            continue
        link.a.impairment = profile.forward
        link.b.impairment = profile.reverse
        touched += 1
    interfaces = fabric.apply_impairment(only_links=links)
    event = {
        "action": "apply-profile",
        "profile": profile.name,
        "direction": profile.direction,
        "links": "all" if links is None else ["%s--%s" % pair for pair in links],
        "links_touched": touched,
        "interfaces_touched": interfaces,
        "forward": describe(spec_from_impairment(profile.forward)),
        "reverse": describe(spec_from_impairment(profile.reverse)),
        "source": profile.source,
    }
    record_event(run_root, event)
    LOG.info("applied profile %s to %d links (%d interfaces)",
             profile.name, touched, interfaces)
    return event


def apply_override(fabric, impairment: Impairment, run_root: Path, *,
                   links: list[tuple[str, str]] | None = None,
                   label: str = "override") -> dict:
    """Install a one-off impairment without naming a profile."""
    interfaces = fabric.apply_impairment(only_links=links, override=impairment)
    event = {
        "action": "apply-override",
        "label": label,
        "links": "all" if links is None else ["%s--%s" % pair for pair in links],
        "interfaces_touched": interfaces,
        "impairment": describe(spec_from_impairment(impairment)),
    }
    record_event(run_root, event)
    return event


def partition(fabric, run_root: Path, links: list[tuple[str, str]]) -> dict:
    """Drop every packet on the named links, keeping them in the topology."""
    return apply_override(
        fabric, Impairment(partition=True), run_root, links=links, label="partition",
    )


def restore(fabric, topology, run_root: Path) -> dict:
    """Put every link back to the impairment its own topology declares.

    Needed because apply_profile() overwrites the endpoints' stored
    impairment; without re-reading the topology, "restore" would reinstall
    whatever was applied last rather than the declared conditions.
    """
    # Keyed on the ordered pair, not on a frozenset: a realised link keeps the
    # orientation of the topology link it came from, and for an asymmetric
    # profile swapping the two directions would be a different network.
    declared = {
        (link.source, link.target): (link.impairment_forward, link.impairment_reverse)
        for link in topology.links
    }
    for link in fabric.links:
        if link.kind == "node-access":
            continue
        pair = declared.get((link.source, link.target))
        if pair is None:
            continue
        link.a.impairment, link.b.impairment = pair
    interfaces = fabric.apply_impairment()
    event = {"action": "restore-topology", "interfaces_touched": interfaces}
    record_event(run_root, event)
    LOG.info("restored the topology's own impairment on %d interfaces", interfaces)
    return event
