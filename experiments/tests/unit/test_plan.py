"""Resolving an experiment descriptor into a plan."""

from __future__ import annotations

import pytest
import yaml

from experiments.chain_params import ChainParams
from experiments.exit_codes import ConfigError
from experiments.paths import CONFIG_ROOT
from experiments.plan import build_plan

DESCRIPTORS = sorted((CONFIG_ROOT / "experiments").glob("*.yaml"))


@pytest.mark.parametrize("path", DESCRIPTORS, ids=lambda p: p.stem)
def test_every_shipped_descriptor_resolves(path):
    plan = build_plan(path)
    assert plan.enabled_nodes
    assert plan.admin
    assert plan.miners
    assert plan.cas


def test_the_default_composition_is_seven_ten_three():
    for name in ("regional", "national", "continental", "intercontinental"):
        plan = build_plan(CONFIG_ROOT / "experiments" / ("%s.yaml" % name))
        assert len(plan.enabled_nodes) == 20, name
        assert len(plan.miners) == 7, name
        assert len(plan.companies) == 10, name
        # 'admin' in the brief's sense: one governance node plus two CAs.
        assert len(plan.by_role("admin")) + len(plan.cas) == 3, name


def test_addresses_follow_the_historical_layout():
    plan = build_plan(CONFIG_ROOT / "experiments" / "regional.yaml")
    assert plan.admin.ip.endswith(".10")
    assert plan.cas[0].ip.endswith(".11")
    assert plan.miners[0].ip.endswith(".21")
    assert plan.companies[0].ip.endswith(".31")


def test_addresses_are_unique():
    plan = build_plan(CONFIG_ROOT / "experiments" / "intercontinental.yaml")
    addresses = [n.ip for n in plan.enabled_nodes]
    assert len(set(addresses)) == len(addresses)


def test_setup_first_blocks_matches_the_documented_worked_example():
    """README of the historical suite: tbt=10, epoch 12, traffic at 340 -> 64."""
    plan = build_plan(CONFIG_ROOT / "experiments" / "regional.yaml")
    assert plan.setup_first_blocks == 64
    assert plan.schedule.duration_s == 3500.0


def test_seed_override_changes_the_derived_seeds():
    a = build_plan(CONFIG_ROOT / "experiments" / "regional.yaml", seed_override=1)
    b = build_plan(CONFIG_ROOT / "experiments" / "regional.yaml", seed_override=2)
    assert a.node("m1").seed != b.node("m1").seed


def test_same_seed_gives_the_same_plan():
    a = build_plan(CONFIG_ROOT / "experiments" / "regional.yaml", seed_override=99)
    b = build_plan(CONFIG_ROOT / "experiments" / "regional.yaml", seed_override=99)
    assert [n.as_dict() for n in a.nodes] == [n.as_dict() for n in b.nodes]


def test_peers_are_derived_when_absent():
    plan = build_plan(CONFIG_ROOT / "experiments" / "regional.yaml")
    company = plan.companies[0]
    assert set(company.peers) == {m.id for m in plan.miners} | {plan.admin.id}
    assert company.id not in company.peers


def test_heterogeneity_is_present_and_differs_between_nodes():
    """Without it the W_k would be identical and the experiment would prove nothing."""
    plan = build_plan(CONFIG_ROOT / "experiments" / "regional.yaml")
    assert len({m.reconcile_rate for m in plan.miners}) > 1
    assert len({c.tx_interval_s for c in plan.companies}) > 1


def _write(tmp_path, document):
    path = tmp_path / "x.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def _base(**overrides):
    document = {
        "name": "t", "topology": "experiments/configs/topologies/smoke-3n.yaml",
        "chain_params": "experiments/configs/chain-params/smoke.dat",
        "multichain": {}, "schedule": {"duration_s": 600},
        "nodes": [
            {"id": "m1", "role": "miner", "location": "firenze"},
            {"id": "c1", "role": "company", "location": "pisa", "cluster": "m1"},
            {"id": "admin", "role": "admin", "location": "bologna"},
            {"id": "ca1", "role": "ca", "location": "bologna"},
        ],
    }
    document.update(overrides)
    return document


def test_two_admins_are_refused(tmp_path):
    document = _base()
    document["nodes"].append({"id": "admin2", "role": "admin", "location": "bologna"})
    with pytest.raises(ConfigError) as caught:
        build_plan(_write(tmp_path, document))
    assert "admin" in str(caught.value)


def test_no_ca_is_refused_with_the_consequence_stated(tmp_path):
    document = _base()
    document["nodes"] = [n for n in document["nodes"] if n["role"] != "ca"]
    with pytest.raises(ConfigError) as caught:
        build_plan(_write(tmp_path, document))
    assert "ESG" in str(caught.value)


def test_company_without_a_cluster_is_refused(tmp_path):
    document = _base()
    document["nodes"][1].pop("cluster")
    with pytest.raises(ConfigError) as caught:
        build_plan(_write(tmp_path, document))
    assert "cluster" in str(caught.value)


def test_company_in_an_unknown_cluster_is_refused(tmp_path):
    document = _base()
    document["nodes"][1]["cluster"] = "m9"
    with pytest.raises(ConfigError):
        build_plan(_write(tmp_path, document))


def test_node_at_an_unknown_location_is_refused(tmp_path):
    document = _base()
    document["nodes"][0]["location"] = "atlantis"
    with pytest.raises(ConfigError) as caught:
        build_plan(_write(tmp_path, document))
    assert "atlantis" in str(caught.value)


def test_out_of_order_schedule_is_refused(tmp_path):
    document = _base(schedule={"grant_s": 10, "first_launch_s": 100, "duration_s": 600})
    with pytest.raises(ConfigError) as caught:
        build_plan(_write(tmp_path, document))
    assert "before" in str(caught.value)


def test_duration_shorter_than_the_bootstrap_is_refused(tmp_path):
    document = _base(schedule={"duration_s": 10})
    with pytest.raises(ConfigError):
        build_plan(_write(tmp_path, document))


def test_setup_below_the_derived_minimum_is_refused(tmp_path):
    params = tmp_path / "p.dat"
    original = (CONFIG_ROOT / "chain-params" / "tbt10s-sqrt.dat").read_text()
    params.write_text(original.replace("SETUP_FIRST_BLOCKS=auto", "SETUP_FIRST_BLOCKS=5"),
                      encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        ChainParams.load(params).setup_first_blocks(traffic_start_s=340)
    assert "stall" in caught.value.hint
