"""Impairment to tc: the mapping that decides what the network actually does."""

from __future__ import annotations

from experiments.runtime.netem.profiles import (
    NetemSpec,
    clear_commands,
    describe,
    netem_args,
    qdisc_commands,
    spec_from_impairment,
)
from experiments.topology.generator import load_profiles
from experiments.topology.models import Bandwidth, Delay, Impairment, Loss, Queue


def test_identity_spec_installs_nothing():
    assert qdisc_commands("eth0", NetemSpec()) == []
    assert NetemSpec().is_identity


def test_plain_delay_attaches_netem_at_the_root():
    spec = NetemSpec(delay_ms=10.0)
    commands = qdisc_commands("eth0", spec)
    assert len(commands) == 1
    assert commands[0][:5] == ["qdisc", "replace", "dev", "eth0", "root"]
    assert "netem" in commands[0]


def test_bandwidth_puts_tbf_first_and_netem_below_it():
    """Order matters: netem above tbf would delay the pre-shaping stream."""
    spec = NetemSpec(delay_ms=10.0, rate_mbit=100.0)
    commands = qdisc_commands("eth0", spec)
    assert len(commands) == 2
    root, child = commands
    assert "tbf" in root and "root" in root
    assert "netem" in child and "parent" in child
    assert root.index("handle") < len(root)


def test_tbf_burst_scales_with_the_rate():
    """A burst below rate/HZ makes the link run under its configured rate."""
    slow = qdisc_commands("eth0", NetemSpec(rate_mbit=1.0))[0]
    fast = qdisc_commands("eth0", NetemSpec(rate_mbit=1000.0))[0]
    slow_burst = int(slow[slow.index("burst") + 1])
    fast_burst = int(fast[fast.index("burst") + 1])
    assert fast_burst > slow_burst
    assert slow_burst >= 1500


def test_jitter_only_appears_with_a_delay_term():
    without = netem_args(NetemSpec(loss_percent=1.0))
    assert "delay" not in without
    with_jitter = netem_args(NetemSpec(delay_ms=10.0, jitter_ms=2.0))
    assert "delay" in with_jitter
    assert "distribution" in with_jitter


def test_distribution_is_omitted_without_jitter():
    args = netem_args(NetemSpec(delay_ms=10.0, jitter_ms=0.0))
    assert "distribution" not in args


def test_uniform_distribution_is_expressed_by_omission():
    """netem's default has no table file; naming it would be rejected."""
    args = netem_args(NetemSpec(delay_ms=10.0, jitter_ms=2.0, distribution="uniform"))
    assert "distribution" not in args


def test_no_argument_uses_exponent_notation():
    """tc rejects '1e-05ms'; every magnitude must be fixed-point."""
    spec = NetemSpec(delay_ms=0.00001, jitter_ms=0.002, loss_percent=0.00002,
                     rate_mbit=0.001)
    for command in qdisc_commands("eth0", spec):
        for token in command:
            assert "e-" not in token and "e+" not in token, token


def test_partition_becomes_total_loss_not_a_missing_interface():
    spec = spec_from_impairment(Impairment(partition=True))
    assert spec.loss_percent == 100
    assert not spec.is_identity
    assert "loss" in netem_args(spec)


def test_asymmetric_profile_produces_two_different_command_sets():
    degraded = load_profiles()["degraded"]
    forward = qdisc_commands("eth0", spec_from_impairment(degraded.forward))
    reverse = qdisc_commands("eth0", spec_from_impairment(degraded.reverse))
    assert forward != reverse


def test_every_shipped_profile_maps_to_valid_commands():
    for name, profile in load_profiles().items():
        for impairment in (profile.forward, profile.reverse):
            for command in qdisc_commands("eth0", spec_from_impairment(impairment)):
                assert command[0] == "qdisc", name
                assert "dev" in command, name


def test_queue_limit_reaches_the_netem_arguments():
    spec = spec_from_impairment(Impairment(delay=Delay(mean_ms=1),
                                           queue=Queue(limit_packets=77)))
    args = netem_args(spec)
    assert args[args.index("limit") + 1] == "77"


def test_clear_removes_the_root_qdisc():
    assert clear_commands("eth0") == [["qdisc", "del", "dev", "eth0", "root"]]


def test_describe_is_human_readable():
    spec = spec_from_impairment(Impairment(
        delay=Delay(mean_ms=45.8, jitter_ms=8.0), loss=Loss(percent=0.15),
        bandwidth=Bandwidth(mbps=1000)))
    text = describe(spec)
    assert "45.8ms" in text and "loss" in text and "1000mbit" in text
