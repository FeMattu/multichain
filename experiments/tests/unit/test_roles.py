"""The node controllers: life cycle, workload resolution, supervision."""

from __future__ import annotations

import json

import pytest

from experiments.paths import CONFIG_ROOT
from experiments.plan import build_plan
from experiments.runtime.multichain.lifecycle import role_environment, workload_for
from experiments.runtime.roles import CONTROLLERS, controller_for
from experiments.runtime.roles.base import RoleContext, context_from_env


@pytest.fixture
def plan():
    return build_plan(CONFIG_ROOT / "experiments" / "e2e-5n.yaml")


def _context(tmp_path, node_id="m1", role="miner", **extra):
    return RoleContext(
        node_id=node_id, role=role, ip="11.0.0.21", run_root=tmp_path,
        chain="poesiatest", rpc_port=27000, p2p_port=27001,
        rpc_user="u", rpc_password="p", admin_id="admin", admin_ip="11.0.0.10",
        miners=["m1", "m2"], companies=["c1"], cas=["ca1"],
        ip_by_node={"m1": "11.0.0.21", "m2": "11.0.0.22", "admin": "11.0.0.10"},
        **extra)


def test_there_is_a_controller_for_every_role():
    assert set(CONTROLLERS) == {"admin", "miner", "company", "ca"}


def test_an_unknown_role_fails_loudly(tmp_path):
    with pytest.raises(SystemExit):
        controller_for("wizard", _context(tmp_path))


def test_every_controller_implements_the_life_cycle(tmp_path):
    for role in CONTROLLERS:
        controller = controller_for(role, _context(tmp_path, role=role))
        for method in ("setup", "loop", "teardown", "run"):
            assert callable(getattr(controller, method)), (role, method)


def test_the_controller_writes_its_own_log(tmp_path):
    controller = controller_for("miner", _context(tmp_path))
    controller.log.info("hello")
    path = tmp_path / "logs" / "m1" / "role_controller.log"
    assert path.is_file()
    assert "hello" in path.read_text(encoding="utf-8")


def test_the_workload_of_a_node_overrides_its_role(plan):
    """A node's own field wins over the role block, which wins over the default."""
    c1 = plan.node("c1")
    c2 = plan.node("c2")
    assert workload_for(plan, c1)["tx_interval_seconds"] == 4
    assert workload_for(plan, c2)["tx_interval_seconds"] == 9
    # from workload.roles.company, which neither node overrides
    assert workload_for(plan, c1)["burst_probability"] == 0.05


def test_miners_get_their_own_reconciliation_rate(plan):
    rates = {n.id: workload_for(plan, n)["reconcile_rate"] for n in plan.miners}
    assert rates == {"m1": 0.95, "m2": 0.25}
    assert len(set(rates.values())) > 1, "identical rates make rho_k unobservable"


def test_each_ca_gets_its_slice(plan):
    for index, node in enumerate(plan.cas, start=1):
        workload = workload_for(plan, node)
        assert workload["ca_index"] == index
        assert workload["ca_count"] == len(plan.cas)


def test_the_environment_round_trips_into_a_context(plan, tmp_path, monkeypatch):
    node = plan.node("c1")
    env = role_environment(plan, node, tmp_path, daemon="/bin/true",
                           treasury_address="1TREASURY", setup_first_blocks=60)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("POESIA_DURATION", "120")
    context = context_from_env()
    assert context.node_id == "c1"
    assert context.role == "company"
    assert context.cluster == "m1"
    assert context.treasury == "1TREASURY"
    assert context.ip_by_node["m1"] == plan.node("m1").ip
    assert context.workload["tx_interval_seconds"] == 4
    assert context.duration_s == 120


def test_the_workload_survives_json_round_trip(plan, tmp_path):
    node = plan.node("m1")
    env = role_environment(plan, node, tmp_path, daemon="/bin/true",
                           treasury_address="", setup_first_blocks=60)
    assert json.loads(env["POESIA_WORKLOAD_JSON"])["reconcile_rate"] == 0.95


def test_the_controller_addresses_peers_by_their_emulated_ip(tmp_path):
    """Node-to-node RPC must travel the impaired paths: it is the experiment."""
    controller = controller_for("miner", _context(tmp_path))
    assert "11.0.0.22" in controller.client("m2").url
    assert "11.0.0.10" in controller.client("admin").url


def test_csv_append_writes_the_header_once(tmp_path):
    controller = controller_for("miner", _context(tmp_path))
    header = ["a", "b"]
    controller.csv_append("t.csv", [1, 2], header=header)
    controller.csv_append("t.csv", [3, 4], header=header)
    lines = (tmp_path / "raw" / "metrics" / "t.csv").read_text().strip().splitlines()
    assert lines == ["a,b", "1,2", "3,4"]


def test_write_json_uses_the_rpc_envelope(tmp_path):
    """The analysis reads {"result": ...}, as curl produced it."""
    controller = controller_for("admin", _context(tmp_path, node_id="admin", role="admin"))
    controller.write_json("x.json", [1, 2, 3])
    payload = json.loads((tmp_path / "raw" / "metrics" / "x.json").read_text())
    assert payload["result"] == [1, 2, 3]
    assert "error" in payload


def test_epoch_numbering_matches_the_protocol(tmp_path):
    controller = controller_for("miner", _context(tmp_path, epoch_length=12))
    assert controller.epoch_of(0) == 1
    assert controller.epoch_of(11) == 1
    assert controller.epoch_of(12) == 2


def test_the_ca_score_does_not_depend_on_how_many_cas_there_are(tmp_path):
    """The same run with one, two or three CAs must produce the same scores."""
    one = controller_for("ca", _context(tmp_path, node_id="ca1", role="ca", seed=42))
    three = controller_for("ca", _context(tmp_path, node_id="ca1", role="ca", seed=42))
    three.count, three.index = 3, 1
    assert one._score(5) == three._score(5)


def test_the_ca_score_is_strictly_inside_zero_and_one_hundred(tmp_path):
    """Def. 6.1 needs ESG > 0: a zero would zero the whole cluster's weight."""
    controller = controller_for("ca", _context(tmp_path, node_id="ca1", role="ca"))
    for position in range(1, 200):
        score = controller._score(position)
        assert 0 < score < 100
