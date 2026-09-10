"""Impairment -> ``tc`` command lines.

Pure functions: they build argument lists and never execute anything, which is
what makes the mapping testable without root. :mod:`experiments.runtime.netem.apply`
runs what they produce.

**Direction.** netem shapes *egress* only. A link's forward impairment is
therefore applied on the interface at the source end, and its reverse
impairment on the interface at the target end. That is how an asymmetric
profile becomes two different qdiscs rather than an average of the two.

**Layering.** When a profile constrains bandwidth, the shaper has to come
first and netem hang below it, so that the delay is added to packets that have
already been paced:

    root  ->  tbf rate/burst/latency  ->  netem delay/jitter/loss

With no bandwidth limit netem is attached at the root directly. Doing it the
other way round (netem at the root, tbf below) makes the delay apply to the
pre-shaping stream and the effective latency drifts with the queue.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...topology.models import Impairment

#: netem's distribution tables shipped by iproute2. ``uniform`` is netem's
#: default and has no table file, so it is expressed by omitting the keyword.
DISTRIBUTIONS = {"normal", "pareto", "paretonormal"}

#: Below this, a jitter value is noise the scheduler cannot honour anyway.
MIN_JITTER_MS = 0.001


@dataclass(frozen=True)
class NetemSpec:
    """The impairment of one direction, in the units ``tc`` speaks."""

    delay_ms: float = 0.0
    jitter_ms: float = 0.0
    delay_correlation_percent: float = 0.0
    distribution: str = "normal"
    loss_percent: float = 0.0
    loss_correlation_percent: float = 0.0
    rate_mbit: float | None = None
    burst_bytes: int | None = None
    limit_packets: int = 1000

    @property
    def is_identity(self) -> bool:
        """True when the spec would not change a packet, so no qdisc is needed."""
        return (
            self.delay_ms <= 0
            and self.jitter_ms <= 0
            and self.loss_percent <= 0
            and self.rate_mbit is None
        )


def spec_from_impairment(impairment: Impairment) -> NetemSpec:
    """Convert the topology model's impairment into a ``tc`` spec.

    A partition is expressed as 100% loss rather than as a missing interface:
    the link keeps its shape, so a partitioned run stays comparable with a
    healthy one link by link, and the partition can be lifted at run time
    without rebuilding the fabric.
    """
    loss = 100.0 if impairment.partition else float(impairment.loss.percent)
    distribution = impairment.delay.distribution
    if distribution not in DISTRIBUTIONS and distribution != "uniform":
        distribution = "normal"
    return NetemSpec(
        delay_ms=float(impairment.delay.mean_ms),
        jitter_ms=float(impairment.delay.jitter_ms),
        delay_correlation_percent=float(impairment.delay.correlation_percent),
        distribution=distribution,
        loss_percent=loss,
        loss_correlation_percent=float(impairment.loss.correlation_percent),
        rate_mbit=None if impairment.bandwidth.mbps is None else float(impairment.bandwidth.mbps),
        burst_bytes=impairment.bandwidth.burst_bytes,
        limit_packets=int(impairment.queue.limit_packets),
    )


def _fmt(value: float) -> str:
    """Compact fixed-point: ``tc`` rejects exponent notation."""
    text = "%.6f" % float(value)
    text = text.rstrip("0").rstrip(".")
    return text or "0"


def netem_args(spec: NetemSpec) -> list[str]:
    """The ``netem ...`` fragment of a ``tc qdisc`` command line."""
    args = ["netem", "limit", str(spec.limit_packets)]
    if spec.delay_ms > 0 or spec.jitter_ms > MIN_JITTER_MS:
        args += ["delay", "%sms" % _fmt(spec.delay_ms)]
        if spec.jitter_ms > MIN_JITTER_MS:
            args.append("%sms" % _fmt(spec.jitter_ms))
            if spec.delay_correlation_percent > 0:
                args.append("%s%%" % _fmt(spec.delay_correlation_percent))
            # 'distribution' is only meaningful together with a jitter term.
            if spec.distribution != "uniform":
                args += ["distribution", spec.distribution]
    if spec.loss_percent > 0:
        args += ["loss", "%s%%" % _fmt(spec.loss_percent)]
        if spec.loss_correlation_percent > 0:
            args.append("%s%%" % _fmt(spec.loss_correlation_percent))
    return args


def _burst_bytes(spec: NetemSpec) -> int:
    """Token bucket burst.

    A tbf burst smaller than rate/HZ makes the bucket refill slower than the
    configured rate and the link silently runs below it. One tenth of a second
    of traffic is the usual safe choice; the floor of 1500 bytes keeps a single
    MTU-sized packet from stalling.
    """
    if spec.burst_bytes:
        return int(spec.burst_bytes)
    rate_bytes_per_s = (spec.rate_mbit or 0.0) * 1e6 / 8.0
    return max(1500, int(rate_bytes_per_s / 10))


def qdisc_commands(interface: str, spec: NetemSpec) -> list[list[str]]:
    """``tc`` argument lists that install ``spec`` on ``interface``.

    Returned without the leading ``tc`` and without any namespace wrapper: the
    caller decides where they run.
    """
    if spec.is_identity:
        return []
    if spec.rate_mbit is None:
        return [["qdisc", "replace", "dev", interface, "root", *netem_args(spec)]]
    burst = _burst_bytes(spec)
    return [
        [
            "qdisc", "replace", "dev", interface, "root", "handle", "1:",
            "tbf", "rate", "%smbit" % _fmt(spec.rate_mbit),
            "burst", str(burst),
            # tbf needs a queue bound; expressed in packets so it tracks the
            # profile's queue.limit_packets rather than an arbitrary latency.
            "limit", str(max(spec.limit_packets, 1) * 1500),
        ],
        [
            "qdisc", "replace", "dev", interface, "parent", "1:1", "handle", "10:",
            *netem_args(spec),
        ],
    ]


def clear_commands(interface: str) -> list[list[str]]:
    """``tc`` argument lists that remove every qdisc from ``interface``."""
    return [["qdisc", "del", "dev", interface, "root"]]


def describe(spec: NetemSpec) -> str:
    """One-line human summary, used in logs and in the realized topology."""
    parts = []
    if spec.delay_ms or spec.jitter_ms:
        piece = "%sms" % _fmt(spec.delay_ms)
        if spec.jitter_ms > MIN_JITTER_MS:
            piece += " +/-%sms %s" % (_fmt(spec.jitter_ms), spec.distribution)
        parts.append("delay " + piece)
    if spec.loss_percent:
        parts.append("loss %s%%" % _fmt(spec.loss_percent))
    if spec.rate_mbit:
        parts.append("rate %smbit" % _fmt(spec.rate_mbit))
    return ", ".join(parts) or "no impairment"
