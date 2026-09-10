"""The real end-to-end: three MultiChain nodes on an emulated network.

This is the only test that can claim an end-to-end result, and it is the only
one that refuses to be faked. It needs CAP_NET_ADMIN and the MultiChain
binaries; without either it skips, saying which. A mock would make the report
green and mean nothing.

What it asserts is the shortest chain of causation the larger runs measure:
the fabric comes up, the genesis is sealed, the nodes join and peer, at least
one block is produced, the artefacts land where the analysis expects them, and
the cleanup leaves no namespace behind.
"""

from __future__ import annotations

import json

import pytest

from experiments.paths import CONFIG_ROOT, ROLES_ROOT
from experiments.plan import build_plan
from experiments.runtime.fabric.netns import NetnsFabric
from experiments.runtime.multichain import health, install
from experiments.runtime.manifest import Manifest
from experiments.runtime.session import Session
from experiments.runtime.shell import Runner

pytestmark = [pytest.mark.requires_root, pytest.mark.requires_multichain,
              pytest.mark.slow]

PREFIX = "poesiasmoke"


def _descriptor(tmp_path, duration: float):
    import yaml

    document = yaml.safe_load(
        (CONFIG_ROOT / "experiments" / "smoke-3n.yaml").read_text(encoding="utf-8"))
    document["fabric"] = {
        "backend": "netns", "namespace_prefix": PREFIX,
        "subnet": "11.8.0.0/24", "link_subnet": "10.97.0.0/16",
        "mgmt_subnet": "172.31.8.0/24", "host_uplink": True,
    }
    document["schedule"] = {
        "first_launch_s": 8, "grant_s": 20, "join_s": 40, "register_s": 60,
        "traffic_s": 75, "snapshot_before_stop_s": 20,
        "duration_s": duration, "measure_epochs": 1,
    }
    path = tmp_path / "smoke.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_three_real_nodes_produce_a_block(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_ROOT", str(tmp_path / "results"))
    descriptor = _descriptor(tmp_path, duration=420)
    plan = build_plan(descriptor)
    runner = Runner()
    NetnsFabric.destroy_session(runner, PREFIX)

    binaries = install.require_all(plan.multichain)
    run_root = tmp_path / "results" / "run-smoke"
    run_root.mkdir(parents=True, exist_ok=True)

    with Session(plan=plan, run_id="run-smoke", run_root=run_root, runner=runner,
                 roles_dir=ROLES_ROOT, binaries=binaries) as session:
        session.prepare_directories()
        session.snapshot_config()
        session.manifest = Manifest.create("run-smoke", run_root, plan,
                                           backend="netns", binaries=binaries)
        session.validate()
        session.build_network(backend="netns")
        session.initialize_chain()

        # 1. params.dat was sealed with the wPoA parameters.
        params = (run_root / "runtime" / "data" / plan.admin.id /
                  plan.multichain.chain / "params.dat")
        assert params.is_file(), "multichain-util produced no params.dat"
        text = params.read_text(encoding="utf-8")
        assert "enable-wpoa" in text
        assert "setup-first-blocks" in text

        report = session.run_schedule()

    # 2. the daemons answered and peered.
    checks = {c["name"]: c for c in report["checks"]}
    assert checks["daemons responding"]["ok"], checks["daemons responding"]
    assert checks["peer connectivity"]["ok"], checks["peer connectivity"]

    # 3. at least one block exists, and the analysis can find it.
    blocks_json = run_root / "raw" / "metrics" / "blocks.json"
    assert blocks_json.is_file(), "the admin's final snapshot was not taken"
    blocks = json.loads(blocks_json.read_text(encoding="utf-8")).get("result") or []
    assert len(blocks) >= 1, "no block was produced"

    # 4. logs were archived and the run described itself.
    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] in ("completed", "failed", "interrupted")
    assert manifest["multichain_binary"], "the manifest does not say which binary ran"
    assert manifest["logs"]["files"] > 0

    # 5. observations were collected.
    observations = run_root / "raw" / "observations" / "node_observations.csv"
    assert observations.is_file()
    assert len(observations.read_text(encoding="utf-8").splitlines()) > 1

    # 6. nothing was left behind.
    assert NetnsFabric.existing_namespaces(runner, PREFIX) == []


def test_cleanup_after_an_interruption_leaves_no_namespace(tmp_path, monkeypatch):
    """Ctrl+C in the middle of the bootstrap must still tear the fabric down."""
    monkeypatch.setenv("EXPERIMENT_ROOT", str(tmp_path / "results"))
    descriptor = _descriptor(tmp_path, duration=600)
    plan = build_plan(descriptor)
    runner = Runner()
    NetnsFabric.destroy_session(runner, PREFIX)
    binaries = install.require_all(plan.multichain)
    run_root = tmp_path / "results" / "run-interrupt"
    run_root.mkdir(parents=True, exist_ok=True)

    class Interrupt(Exception):
        pass

    try:
        with Session(plan=plan, run_id="run-interrupt", run_root=run_root,
                     runner=runner, roles_dir=ROLES_ROOT, binaries=binaries) as session:
            session.prepare_directories()
            session.snapshot_config()
            session.manifest = Manifest.create("run-interrupt", run_root, plan,
                                               backend="netns", binaries=binaries)
            session.build_network(backend="netns")
            session.initialize_chain()
            raise Interrupt("simulated Ctrl+C")
    except Interrupt:
        pass

    assert NetnsFabric.existing_namespaces(runner, PREFIX) == []
    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    # Results are preserved, never deleted, by the cleanup path.
    assert (run_root / "config" / "experiment.yaml").is_file()


def test_health_checks_report_a_missing_node(tmp_path, monkeypatch):
    """An unreachable node must fail a check, not be silently skipped."""
    monkeypatch.setenv("EXPERIMENT_ROOT", str(tmp_path / "results"))
    from experiments.runtime.multichain.rpc import RpcClient

    clients = {"ghost": RpcClient("http://127.0.0.1:1/", "u", "p", node_id="ghost")}
    check = health.wait_daemons(clients, timeout_s=3, poll_s=1)
    assert not check.ok
    assert "ghost" in check.detail
