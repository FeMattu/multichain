"""Topology model, generator, validator and exporters."""

from __future__ import annotations

import pytest

from experiments.exit_codes import ConfigError
from experiments.paths import CONFIG_ROOT
from experiments.topology import exporters, legacy
from experiments.topology.generator import build_topology, load_profiles
from experiments.topology.models import LatencyModel, haversine_km
from experiments.topology.validator import (
    connected_components,
    next_hops,
    rtt_between,
    shortest_paths,
    validate_topology,
)

TOPOLOGIES = sorted((CONFIG_ROOT / "topologies").glob("*.yaml"))


def test_latency_model_reproduces_the_validated_points():
    """The model is the historical one; these are its published check points."""
    model = LatencyModel()
    milan_ny = haversine_km(45.4642, 9.19, 40.7128, -74.0060)
    assert round(2 * model.one_way_ms(milan_ny, access=False), 1) == 91.5
    milan_madrid = haversine_km(45.4642, 9.19, 40.4168, -3.7038)
    assert round(2 * model.one_way_ms(milan_madrid, access=False), 1) == pytest.approx(17.6, abs=0.2)


def test_haversine_is_symmetric_and_zero_on_itself():
    assert haversine_km(45.0, 9.0, 45.0, 9.0) == 0.0
    assert haversine_km(45.0, 9.0, 40.0, -74.0) == pytest.approx(
        haversine_km(40.0, -74.0, 45.0, 9.0))


@pytest.mark.parametrize("path", TOPOLOGIES, ids=lambda p: p.stem)
def test_every_shipped_topology_resolves_and_is_connected(path):
    topology = build_topology(path)
    report = validate_topology(topology)
    assert report.errors == []
    assert report.connected
    assert report.max_rtt_ms > 0


def test_the_four_levels_form_a_monotone_geography_axis():
    rtts = {}
    for name in ("regional", "national", "continental", "intercontinental"):
        topology = build_topology(CONFIG_ROOT / "topologies" / ("%s.yaml" % name))
        rtts[name] = validate_topology(topology).max_rtt_ms
    ordered = [rtts["regional"], rtts["national"], rtts["continental"],
               rtts["intercontinental"]]
    assert ordered == sorted(ordered), rtts


def test_twenty_node_levels_have_seven_hubs_and_thirteen_leaves():
    for name in ("regional", "national", "continental", "intercontinental"):
        topology = build_topology(CONFIG_ROOT / "topologies" / ("%s.yaml" % name))
        hubs = [loc for loc in topology.locations if loc.is_hub]
        assert len(topology.locations) == 20, name
        assert len(hubs) == 7, name


def test_profiles_load_and_declare_their_source():
    profiles = load_profiles()
    assert {"lan", "regional", "national", "continental", "intercontinental",
            "degraded", "partitioned"} <= set(profiles)
    for name, profile in profiles.items():
        assert profile.source.strip(), "%s declares no source" % name


def test_asymmetric_profile_keeps_two_directions():
    degraded = load_profiles()["degraded"]
    assert not degraded.symmetric
    assert degraded.forward.delay.mean_ms != degraded.reverse.delay.mean_ms
    assert degraded.forward.bandwidth.mbps != degraded.reverse.bandwidth.mbps


def test_partition_profile_drops_everything():
    partitioned = load_profiles()["partitioned"]
    assert partitioned.forward.partition
    assert partitioned.forward.loss.percent == 100


def test_profile_override_can_make_a_symmetric_profile_asymmetric():
    base = load_profiles()["continental"]
    merged = base.merged({"forward": {"delay": {"mean_ms": 5}},
                          "reverse": {"delay": {"mean_ms": 50}}})
    assert merged.forward.delay.mean_ms == 5
    assert merged.reverse.delay.mean_ms == 50
    # Untouched fields survive the merge.
    assert merged.forward.loss.percent == base.forward.loss.percent


def test_unknown_profile_is_a_config_error(tmp_path):
    document = tmp_path / "t.yaml"
    document.write_text(
        "name: t\nnodes:\n"
        "  - {id: a, lat: 45.0, lon: 9.0}\n  - {id: b, lat: 46.0, lon: 9.0}\n"
        "links:\n  - {source: a, target: b, profile: no-such-profile}\n",
        encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        build_topology(document)
    assert "no-such-profile" in str(caught.value)


def test_link_to_unknown_location_is_a_config_error(tmp_path):
    document = tmp_path / "t.yaml"
    document.write_text(
        "name: t\nnodes:\n"
        "  - {id: a, lat: 45.0, lon: 9.0}\n  - {id: b, lat: 46.0, lon: 9.0}\n"
        "links:\n  - {source: a, target: nowhere}\n", encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        build_topology(document)
    assert "nowhere" in str(caught.value)


def test_a_link_without_coordinates_or_profile_is_refused(tmp_path):
    document = tmp_path / "t.yaml"
    document.write_text(
        "name: t\nnodes:\n  - {id: a}\n  - {id: b}\nlinks:\n  - {source: a, target: b}\n",
        encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        build_topology(document)
    assert "coordinates" in str(caught.value)


def test_disabled_link_splits_the_graph_and_is_reported():
    topology = build_topology(CONFIG_ROOT / "topologies" / "smoke-3n.yaml")
    topology.links[0] = type(topology.links[0])(
        **{**topology.links[0].__dict__, "enabled": False})
    report = validate_topology(topology, require_connected=True)
    assert not report.connected
    assert any("not connected" in e for e in report.errors)


def test_partitioned_direction_is_excluded_from_the_paths(tmp_path):
    document = tmp_path / "t.yaml"
    document.write_text(
        "name: t\nnodes:\n"
        "  - {id: a, lat: 45.0, lon: 9.0}\n  - {id: b, lat: 46.0, lon: 9.0}\n"
        "links:\n  - {source: a, target: b, profile: partitioned}\n", encoding="utf-8")
    topology = build_topology(document)
    assert len(connected_components(topology)) == 2


def test_next_hops_cover_every_reachable_destination():
    topology = build_topology(CONFIG_ROOT / "topologies" / "continental.yaml")
    hops = next_hops(topology)
    distances = shortest_paths(topology)
    for source in topology.location_ids:
        reachable = set(distances[source]) - {source}
        assert reachable <= set(hops[source]), source


def test_next_hops_are_stable_across_calls():
    topology = build_topology(CONFIG_ROOT / "topologies" / "national.yaml")
    assert next_hops(topology) == next_hops(topology)


def test_rtt_between_a_subset_never_exceeds_the_whole():
    topology = build_topology(CONFIG_ROOT / "topologies" / "regional.yaml")
    hubs = [loc.id for loc in topology.locations if loc.is_hub]
    assert rtt_between(topology, hubs) <= validate_topology(topology).max_rtt_ms


def test_gml_export_round_trips_through_the_reader():
    topology = build_topology(CONFIG_ROOT / "topologies" / "continental.yaml")
    text = exporters.to_gml(topology)
    parsed = legacy.parse_gml(text)
    assert len(parsed["nodes"]) == len(topology.locations)
    # One self-loop per location plus one edge per enabled link.
    expected = len(topology.locations) + sum(1 for _ in topology.enabled_links())
    assert len(parsed["edges"]) == expected


def test_gml_export_is_deterministic():
    topology = build_topology(CONFIG_ROOT / "topologies" / "intercontinental.yaml")
    assert exporters.to_gml(topology) == exporters.to_gml(topology)


def test_gml_latencies_are_whole_microseconds():
    """The historical constraint, kept so old and new edge tables compare."""
    topology = build_topology(CONFIG_ROOT / "topologies" / "regional.yaml")
    for line in exporters.to_gml(topology).splitlines():
        stripped = line.strip()
        if stripped.startswith('latency "'):
            magnitude = stripped.split('"')[1].split()[0]
            assert magnitude.isdigit(), stripped


def test_edge_rows_carry_both_directions():
    topology = build_topology(CONFIG_ROOT / "topologies" / "smoke-3n.yaml")
    rows = exporters.to_edge_rows(topology)
    assert len(rows) == 2 * len(topology.links)
    assert {r["direction"] for r in rows} == {"forward", "reverse"}
