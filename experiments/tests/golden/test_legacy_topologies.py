"""The migration must be lossless, and this is what proves it.

Exporting each migrated ``configs/topologies/legacy-*.yaml`` must reproduce
the historical ``.gml`` **byte for byte**. A description of a topology can be
wrong; a byte comparison cannot.

If one of these fails after an intended change to the latency model or to the
exporter, the fixtures must be regenerated deliberately and the change
explained in ``docs/migration-from-shadow.md``. Updating them silently would
throw away the only evidence that a new run is comparable with the archived
campaign.
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest

from experiments.paths import CONFIG_ROOT
from experiments.topology import exporters, legacy
from experiments.topology.generator import build_topology
from experiments.topology.validator import validate_topology

FIXTURES = Path(__file__).parent / "legacy-gml"

#: Worst end-to-end RTT documented for each level in the historical README.
DOCUMENTED_RTT = {
    "legacy-regional-10n": 10.0,
    "legacy-national-10n": 22.0,
    "legacy-continental-10n": 44.7,
    "legacy-intercontinental-10n": 112.0,
    "legacy-global-10n": 407.0,
}

NAMES = sorted(DOCUMENTED_RTT)


@pytest.mark.parametrize("name", NAMES)
def test_export_reproduces_the_historical_gml_byte_for_byte(name):
    topology = build_topology(CONFIG_ROOT / "topologies" / ("%s.yaml" % name))
    produced = exporters.to_gml(topology)
    expected = (FIXTURES / ("%s.gml" % name)).read_text(encoding="utf-8")
    if produced != expected:
        diff = "\n".join(difflib.unified_diff(
            expected.splitlines(), produced.splitlines(),
            "historical", "regenerated", lineterm="", n=1))
        pytest.fail("%s no longer reproduces its historical .gml:\n%s" % (name, diff[:3000]))


@pytest.mark.parametrize("name", NAMES)
def test_worst_rtt_matches_the_documented_value(name):
    topology = build_topology(CONFIG_ROOT / "topologies" / ("%s.yaml" % name))
    report = validate_topology(topology)
    assert report.max_rtt_ms == pytest.approx(DOCUMENTED_RTT[name], abs=0.5)


@pytest.mark.parametrize("name", NAMES)
def test_legacy_gml_node_ids_are_preserved(name):
    """Archived edge tables key on these ids; renumbering would break them."""
    topology = build_topology(CONFIG_ROOT / "topologies" / ("%s.yaml" % name))
    parsed = legacy.parse_gml((FIXTURES / ("%s.gml" % name)).read_text(encoding="utf-8"))
    historical = {int(node["id"]) for node in parsed["nodes"]}
    migrated = {loc.legacy_gml_id for loc in topology.locations}
    assert migrated == historical


@pytest.mark.parametrize("name", NAMES)
def test_every_legacy_topology_has_ten_locations(name):
    topology = build_topology(CONFIG_ROOT / "topologies" / ("%s.yaml" % name))
    assert len(topology.locations) == 10


def test_the_twenty_node_levels_keep_the_historical_locations():
    """Each 20-node level must still contain its 10-node ancestor's sites."""
    pairs = [("regional", "legacy-regional-10n"),
             ("national", "legacy-national-10n"),
             ("continental", "legacy-continental-10n")]
    for new_name, old_name in pairs:
        new = build_topology(CONFIG_ROOT / "topologies" / ("%s.yaml" % new_name))
        old = build_topology(CONFIG_ROOT / "topologies" / ("%s.yaml" % old_name))
        new_coords = {(round(loc.lat, 4), round(loc.lon, 4))
                      for loc in new.locations if loc.lat is not None}
        for location in old.locations:
            assert (round(location.lat, 4), round(location.lon, 4)) in new_coords, \
                "%s lost the historical site %s" % (new_name, location.label)
