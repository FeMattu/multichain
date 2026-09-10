"""The netns fabric, actually built. Needs CAP_NET_ADMIN.

Skipped without privileges, and the skip says why. Everything here creates
real namespaces and real qdiscs, so each test tears its own session down in a
finally block — a leaked namespace would silently impair the next run.
"""

from __future__ import annotations

import subprocess

import pytest

from experiments.paths import CONFIG_ROOT
from experiments.plan import build_plan
from experiments.runtime.fabric.netns import NetnsFabric
from experiments.runtime.shell import Runner

pytestmark = [pytest.mark.requires_root, pytest.mark.slow]

PREFIX = "poesiatest"


def _plan(tmp_path, descriptor="smoke-3n"):
    import yaml

    document = yaml.safe_load(
        (CONFIG_ROOT / "experiments" / ("%s.yaml" % descriptor)).read_text(encoding="utf-8"))
    document.setdefault("fabric", {})["namespace_prefix"] = PREFIX
    # Keep well away from anything a real run may be using.
    document["fabric"]["subnet"] = "11.9.0.0/24"
    document["fabric"]["link_subnet"] = "10.98.0.0/16"
    document["fabric"]["mgmt_subnet"] = "172.31.9.0/24"
    path = tmp_path / "descriptor.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return build_plan(path)


@pytest.fixture
def fabric(tmp_path):
    plan = _plan(tmp_path)
    runner = Runner()
    NetnsFabric.destroy_session(runner, PREFIX)
    built = NetnsFabric(plan, runner, run_root=tmp_path / "run")
    built.build()
    try:
        yield built
    finally:
        built.teardown()
        NetnsFabric.destroy_session(runner, PREFIX)


def test_namespaces_exist_after_build(fabric):
    listing = subprocess.run(["ip", "-o", "netns", "list"],
                             capture_output=True, text=True).stdout
    for node in fabric.nodes.values():
        assert node.namespace in listing


def test_a_node_can_reach_every_other_over_the_emulated_plane(fabric):
    ids = list(fabric.nodes)
    source = ids[0]
    for target in ids[1:]:
        address = fabric.nodes[target].ip
        result = fabric.runner.in_netns(
            fabric.nodes[source].namespace,
            ["ping", "-c", "2", "-W", "3", address], check=False, timeout_s=30)
        assert result.ok, "%s cannot reach %s (%s):\n%s" % (
            source, target, address, result.stdout + result.stderr)


def test_the_host_reaches_every_node_over_the_management_plane(fabric):
    for node in fabric.nodes.values():
        result = fabric.runner.run(
            ["ping", "-c", "2", "-W", "3", node.mgmt_ip], check=False, timeout_s=30)
        assert result.ok, "the host cannot reach %s at %s" % (node.id, node.mgmt_ip)


def test_the_configured_delay_actually_applies(fabric):
    """The point of the whole exercise: ping must show the emulated latency."""
    ids = list(fabric.nodes)
    source, target = ids[0], ids[-1]
    if source == target:
        pytest.skip("a single node has nothing to measure against")
    result = fabric.runner.in_netns(
        fabric.nodes[source].namespace,
        ["ping", "-c", "5", "-W", "5", fabric.nodes[target].ip],
        check=False, timeout_s=40)
    assert result.ok, result.stdout + result.stderr
    line = [ln for ln in result.stdout.splitlines() if "rtt min/avg/max" in ln]
    assert line, result.stdout
    average = float(line[0].split("=")[1].split("/")[1])
    # Two access hops plus a backbone hop of the smoke topology: a few ms.
    # The assertion is loose on purpose - it checks that netem is in the path
    # at all, not that the kernel hits a precise figure.
    assert average > 0.5, "no emulated delay is being applied (avg %.3f ms)" % average
    assert average < 500, "delay far above the configuration (avg %.3f ms)" % average


def test_management_plane_is_not_impaired(fabric):
    """Collector traffic must not pay the emulated latency."""
    node = next(iter(fabric.nodes.values()))
    result = fabric.runner.run(
        ["ping", "-c", "5", "-W", "5", node.mgmt_ip], check=False, timeout_s=40)
    assert result.ok
    line = [ln for ln in result.stdout.splitlines() if "rtt min/avg/max" in ln]
    average = float(line[0].split("=")[1].split("/")[1])
    assert average < 2.0, "the management plane is impaired (avg %.3f ms)" % average


def test_teardown_removes_everything(tmp_path):
    plan = _plan(tmp_path)
    runner = Runner()
    built = NetnsFabric(plan, runner, run_root=tmp_path / "run")
    built.build()
    built.teardown()
    listing = subprocess.run(["ip", "-o", "netns", "list"],
                             capture_output=True, text=True).stdout
    assert PREFIX not in listing
    links = subprocess.run(["ip", "-o", "link", "show"],
                           capture_output=True, text=True).stdout
    assert "pe1a" not in links


def test_destroy_session_works_without_the_object_that_built_it(tmp_path):
    """Cleanup must work from a fresh process after a crash."""
    plan = _plan(tmp_path)
    NetnsFabric(plan, Runner(), run_root=tmp_path / "run").build()
    removed = NetnsFabric.destroy_session(Runner(), PREFIX)
    assert removed > 0
    listing = subprocess.run(["ip", "-o", "netns", "list"],
                             capture_output=True, text=True).stdout
    assert PREFIX not in listing


def test_applying_a_partition_stops_the_traffic(fabric, tmp_path):
    from experiments.runtime.netem.apply import apply_profile, restore
    from experiments.topology.generator import profile_from_file

    ids = list(fabric.nodes)
    source, target = ids[0], ids[-1]
    profile = profile_from_file(CONFIG_ROOT / "network-profiles" / "partitioned.yaml")
    apply_profile(fabric, profile, tmp_path / "run")
    result = fabric.runner.in_netns(
        fabric.nodes[source].namespace,
        ["ping", "-c", "2", "-W", "2", fabric.nodes[target].ip],
        check=False, timeout_s=20)
    assert not result.ok, "the partition did not stop the traffic"

    restore(fabric, fabric.plan.topology, tmp_path / "run")
    result = fabric.runner.in_netns(
        fabric.nodes[source].namespace,
        ["ping", "-c", "3", "-W", "3", fabric.nodes[target].ip],
        check=False, timeout_s=30)
    assert result.ok, "restore did not lift the partition"


def test_netem_events_are_recorded_with_both_clocks(fabric, tmp_path):
    import json

    from experiments.runtime.netem.apply import apply_profile
    from experiments.topology.generator import profile_from_file

    run_root = tmp_path / "run"
    profile = profile_from_file(CONFIG_ROOT / "network-profiles" / "degraded.yaml")
    apply_profile(fabric, profile, run_root)
    events = (run_root / "runtime" / "netem-events.jsonl").read_text(encoding="utf-8")
    entry = json.loads(events.strip().splitlines()[-1])
    assert entry["profile"] == "degraded"
    assert entry["timestamp_wallclock"] and entry["timestamp_monotonic"]
    assert entry["forward"] != entry["reverse"], "asymmetry was lost"
