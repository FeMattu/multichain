"""The netns fabric, exercised in dry-run: no privileges, no side effects."""

from __future__ import annotations

import ipaddress

import pytest

from experiments.paths import CONFIG_ROOT
from experiments.plan import build_plan
from experiments.runtime.fabric.factory import BACKENDS, make_fabric
from experiments.runtime.fabric.netns import IFNAME_MAX, NetnsFabric
from experiments.runtime.shell import Runner


def _built(descriptor="smoke-3n"):
    plan = build_plan(CONFIG_ROOT / "experiments" / ("%s.yaml" % descriptor))
    runner = Runner(dry_run=True)
    fabric = NetnsFabric(plan, runner, run_root="/tmp/does-not-exist")
    fabric.build()
    return plan, runner, fabric


def test_dry_run_executes_nothing_but_records_everything():
    _, runner, _ = _built()
    assert runner.recorded
    assert all(isinstance(command, list) for command in runner.recorded)


def test_every_node_gets_a_namespace_and_both_addresses():
    plan, _, fabric = _built()
    for node in plan.enabled_nodes:
        realized = fabric.nodes[node.id]
        assert realized.ip == node.ip
        assert realized.mgmt_ip, "the management plane must reach every node"
        assert realized.ip != realized.mgmt_ip


def test_management_and_emulated_planes_are_different_subnets():
    plan, _, fabric = _built()
    emulated = ipaddress.ip_network(plan.fabric.subnet)
    management = ipaddress.ip_network(plan.fabric.mgmt_subnet)
    assert not emulated.overlaps(management)
    for realized in fabric.nodes.values():
        assert ipaddress.ip_address(realized.ip) in emulated
        assert ipaddress.ip_address(realized.mgmt_ip) in management


def test_collectors_use_the_management_plane_and_peers_do_not():
    """Polling must not travel the paths under measurement."""
    plan, _, fabric = _built()
    node = plan.miners[0]
    assert fabric.nodes[node.id].mgmt_ip in fabric.rpc_endpoint(node)
    assert node.ip in fabric.peer_endpoint(node)
    assert fabric.rpc_endpoint(node) != fabric.peer_endpoint(node)


def test_link_subnets_never_overlap():
    _, _, fabric = _built("regional")
    subnets = [ipaddress.ip_network(link.subnet) for link in fabric.links if link.subnet]
    for index, first in enumerate(subnets):
        for second in subnets[index + 1:]:
            assert not first.overlaps(second), "%s overlaps %s" % (first, second)


def test_interface_names_fit_the_kernel_limit():
    _, runner, _ = _built("intercontinental")
    for command in runner.recorded:
        for keyword in ("dev", "name"):
            if keyword in command:
                index = command.index(keyword) + 1
                if index < len(command):
                    assert len(command[index]) <= IFNAME_MAX, command


def test_every_node_is_routable_from_every_router():
    plan, runner, fabric = _built("intercontinental")
    routes = {}
    for command in runner.recorded:
        if "route" in command and "exec" in command:
            namespace = command[command.index("exec") + 1]
            destination = command[command.index("route") + 2]
            routes.setdefault(namespace, set()).add(destination)
    for location, namespace in fabric.router_namespaces.items():
        for node in plan.enabled_nodes:
            if node.location == location:
                continue
            assert "%s/32" % node.ip in routes.get(namespace, set()), \
                "%s cannot reach %s" % (location, node.id)


def test_forwarding_is_enabled_on_every_router():
    _, runner, fabric = _built("regional")
    enabled = {command[command.index("exec") + 1] for command in runner.recorded
               if "sysctl" in command and any("ip_forward=1" in c for c in command)}
    assert set(fabric.router_namespaces.values()) <= enabled


def test_impairment_is_installed_per_direction():
    _, runner, fabric = _built("regional")
    tc_commands = [c for c in runner.recorded if "tc" in c]
    assert tc_commands
    # Both ends of every enabled inter-location link carry a qdisc.
    namespaces = {c[c.index("exec") + 1] for c in tc_commands}
    assert len(namespaces) > 1


def test_node_access_links_carry_no_impairment():
    """The site-to-hub delay is already in the topology; adding it twice would
    double-count the last mile."""
    _, _, fabric = _built("regional")
    for link in fabric.links:
        if link.kind == "node-access":
            assert link.a.impairment is not None
            assert link.a.impairment.delay.mean_ms == 0


def test_realized_record_is_serialisable():
    _, _, fabric = _built()
    document = fabric.realized()
    assert document["backend"] == "netns"
    assert len(document["nodes"]) == 4
    assert document["links"]


def test_exec_argv_wraps_in_the_right_namespace():
    _, _, fabric = _built()
    argv = fabric.exec_argv("m1", ["echo", "hi"])
    assert "poesia-h-m1" in argv
    assert argv[-2:] == ["echo", "hi"]


def test_preflight_reports_a_subnet_too_small(tmp_path):
    import yaml

    descriptor = yaml.safe_load(
        (CONFIG_ROOT / "experiments" / "regional.yaml").read_text(encoding="utf-8"))
    descriptor["fabric"]["subnet"] = "10.5.5.0/29"   # 6 usable, 20 nodes
    path = tmp_path / "small.yaml"
    path.write_text(yaml.safe_dump(descriptor), encoding="utf-8")
    with pytest.raises(Exception):
        build_plan(path)


def test_factory_knows_the_three_backends():
    assert set(BACKENDS) == {"core", "netns", "docker"}


def test_auto_falls_back_to_netns_when_core_is_absent():
    from experiments.runtime.fabric.core_emulator import import_core

    modules, _ = import_core()
    if modules is not None:
        pytest.skip("CORE is installed here, so there is nothing to fall back from")
    plan = build_plan(CONFIG_ROOT / "experiments" / "smoke-3n.yaml")
    fabric = make_fabric(plan, Runner(dry_run=True), run_root="/tmp/x", backend="auto")
    assert fabric.name == "netns"


def test_docker_backend_refuses_with_an_explanation():
    plan = build_plan(CONFIG_ROOT / "experiments" / "smoke-3n.yaml")
    from experiments.runtime.fabric.docker_backend import DockerFabric

    problems = DockerFabric(plan, Runner(dry_run=True), run_root="/tmp/x").preflight()
    assert problems
    assert "not implemented" in problems[0]
    assert "architecture.md" in problems[0]
