"""The campaign's figures, regenerated from a run's own tables.

Names follow the historical ones where the content is conceptually the same,
because the thesis and the archived reports refer to them. Where a figure
cannot be drawn from a single run — `03_chi2_vs_tbt` needs several
target-block-times, which is a campaign, not a run — it is **not silently
omitted**: the function records why, the report says so, and
docs/migration-from-shadow.md carries the substitution.

Everything is drawn from the tables in `metrics/`, never recomputed here. A
plot that disagreed with the CSV beside it would be worse than no plot.
"""

from __future__ import annotations

import csv
import logging
from collections import defaultdict
from pathlib import Path

LOG = logging.getLogger("experiments.analysis.plots")

#: Historical name -> what it shows. Kept as a table so the report can list
#: what was produced and what was skipped, with the reason.
FIGURES = {
    "01_traiettoria_pesi.png": "published weight per validator, epoch by epoch",
    "02_quota_per_epoca.png": "observed block share against weight share, per epoch",
    "03_chi2_vs_tbt.png": "chi-square against target-block-time (needs several runs)",
    "04_margine_prop518.png": "distribution of the timer-race margin G",
    "05_block_time.png": "inter-block interval against the target",
    "06_eccesso_miner_pesante.png": "the heaviest validator: observed minus expected share",
    # The emulation's own figures. They have no counterpart in the archive:
    # a simulator with one final snapshot could not draw a time series, and a
    # simulator with configured latencies had nothing to measure against.
    # Numbered from 10 so they never collide with the historical set.
    "10_altezza_per_nodo.png": "chain height per node over wall-clock time",
    "11_propagazione_blocchi.png": "distribution of block propagation time across nodes",
    "12_ritardi_link.png": "one-way delay actually installed on the emulated links",
}

#: Which family a figure belongs to. The historical ones are redrawn from the
#: campaign sheets; the emulation ones from the sampler's own series.
HISTORICAL_FIGURES = [name for name in FIGURES if name < "10_"]
EMULATION_FIGURES = [name for name in FIGURES if name >= "10_"]


def _rows(path: Path) -> list:
    path = Path(path)
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


#: Every figure, in drawing order. The tuple is (name, drawer).
DRAWERS = [
    ("01_traiettoria_pesi.png", "_weights_trajectory"),
    ("02_quota_per_epoca.png", "_share_per_epoch"),
    ("03_chi2_vs_tbt.png", "_chi2_vs_tbt"),
    ("04_margine_prop518.png", "_margin"),
    ("05_block_time.png", "_block_time"),
    ("06_eccesso_miner_pesante.png", "_heaviest_excess"),
    ("10_altezza_per_nodo.png", "_height_per_node"),
    ("11_propagazione_blocchi.png", "_block_propagation"),
    ("12_ritardi_link.png", "_link_delays"),
]


def generate(run_root: Path, plan) -> dict:
    """Draw what this run supports.

    Three outcomes, kept apart because they mean different things:

    * ``produced``  the figure is on disk;
    * ``skipped``   the data for it is legitimately absent, with the reason;
    * ``failed``    the drawer raised, which is a bug and is logged as one.

    Folding the last two together - which this did - makes a crash read like
    an empty table in every report that lists what was drawn.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        LOG.error("matplotlib is not installed: none of the %d figures was "
                  "produced. Install it (requirements.txt) and re-run "
                  "'report generate'.", len(FIGURES))
        return {"produced": [], "failed": {},
                "skipped": {name: "matplotlib is not installed" for name in FIGURES}}

    run_root = Path(run_root)
    metrics = run_root / "metrics"
    plots = run_root / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    produced, skipped, failed = [], {}, {}

    for name, drawer_name in DRAWERS:
        drawer = globals()[drawer_name]
        try:
            reason = drawer(plt, metrics, plots / name, plan, run_root)
        except Exception as exc:  # noqa: BLE001 - a figure must not sink the report
            failed[name] = "%s: %s" % (type(exc).__name__, exc)
            LOG.error("%s NOT DRAWN - the drawer raised %s: %s. This is a bug "
                      "in %s, not missing data.",
                      name, type(exc).__name__, exc, drawer_name)
            _close_all(plt)
            continue
        if reason:
            skipped[name] = reason
            LOG.warning("%s not drawn: %s", name, reason)
        else:
            produced.append(str(plots / name))
    level = LOG.error if failed else LOG.info
    level("figures: %d drawn, %d skipped for want of data, %d FAILED",
          len(produced), len(skipped), len(failed))
    return {"produced": produced, "skipped": skipped, "failed": failed}


def _close_all(plt) -> None:
    """A drawer that raised mid-figure leaves it open; matplotlib warns after
    twenty of those and the report run leaks memory for no reason."""
    try:
        plt.close("all")
    except Exception:  # noqa: BLE001
        pass


def _finish(plt, figure, axes, path: Path, title: str) -> None:
    axes.set_title(title)
    axes.grid(alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=120)
    plt.close(figure)


def _weights_trajectory(plt, metrics: Path, path: Path, plan, run_root: Path) -> str:
    rows = _rows(metrics / "weights_trajectory.csv")
    if not rows:
        return "weights_trajectory.csv is empty: no weight was ever published"
    series = defaultdict(list)
    for row in rows:
        epoch, weight = _number(row.get("epoca")), _number(row.get("peso"))
        if epoch is not None and weight is not None:
            series[row.get("host", "?")].append((epoch, weight))
    if not series:
        return "weights_trajectory.csv holds no usable (epoch, weight) pair"
    figure, axes = plt.subplots(figsize=(9, 5))
    for host, points in sorted(series.items()):
        points.sort()
        axes.plot([p[0] for p in points], [p[1] for p in points],
                  marker="o", markersize=3, label=host, linewidth=1.2)
    axes.set_xlabel("epoch")
    axes.set_ylabel("published weight")
    axes.legend(fontsize=8)
    _finish(plt, figure, axes, path,
            "Weight trajectory - %s" % plan.scenario)
    return ""


def _share_per_epoch(plt, metrics: Path, path: Path, plan, run_root: Path) -> str:
    rows = _rows(metrics / "epoch_shares.csv")
    if not rows:
        return "epoch_shares.csv is empty: no epoch closed inside the wPoA window"
    observed, expected = defaultdict(list), defaultdict(list)
    for row in rows:
        epoch = _number(row.get("epoca"))
        host = row.get("host", "?")
        share = _number(row.get("quota_osservata_epoca"))
        weight_share = _number(row.get("quota_peso_epoca"))
        if epoch is None:
            continue
        if share is not None:
            observed[host].append((epoch, share))
        if weight_share is not None:
            expected[host].append((epoch, weight_share))
    if not observed:
        return "epoch_shares.csv holds no observed share"
    figure, axes = plt.subplots(figsize=(9, 5))
    colours = {}
    for host, points in sorted(observed.items()):
        points.sort()
        line, = axes.plot([p[0] for p in points], [p[1] for p in points],
                          marker="o", markersize=3, label="%s observed" % host)
        colours[host] = line.get_color()
    for host, points in sorted(expected.items()):
        points.sort()
        axes.plot([p[0] for p in points], [p[1] for p in points], linestyle="--",
                  color=colours.get(host), alpha=0.7, label="%s expected" % host)
    axes.set_xlabel("epoch")
    axes.set_ylabel("share of blocks / of weight")
    axes.set_ylim(0, 1)
    axes.legend(fontsize=7, ncol=2)
    _finish(plt, figure, axes, path,
            "Observed vs expected share per epoch - %s" % plan.scenario)
    return ""


def _chi2_vs_tbt(plt, metrics: Path, path: Path, plan, run_root: Path) -> str:
    """Chi-square against target-block-time.

    A campaign figure: one run is one point, and a scatter of one point
    carries no information. It is drawn only when the table holds more than
    one target-block-time, which happens when the campaign view is built.
    """
    rows = _rows(metrics / "chisq.csv")
    points = [(_number(r.get("tbt")), _number(r.get("chi2_ricalcolato")
                                              or r.get("chi2_summary")),
               r.get("livello", ""))
              for r in rows]
    points = [p for p in points if p[0] is not None and p[1] is not None]
    if len({p[0] for p in points}) < 2:
        return ("needs several target-block-times and this run has one; "
                "build it with 'analysis campaign' over runs at different tbt")
    figure, axes = plt.subplots(figsize=(8, 5))
    by_level = defaultdict(list)
    for tbt, chi2, level in points:
        by_level[level].append((tbt, chi2))
    for level, series in sorted(by_level.items()):
        series.sort()
        axes.plot([s[0] for s in series], [s[1] for s in series],
                  marker="o", label=level or "run")
    axes.axhline(5.991, color="crimson", linestyle=":",
                 label="critical 5% (df=2)")
    axes.set_xlabel("target-block-time (s)")
    axes.set_ylabel("chi-square")
    axes.legend(fontsize=8)
    _finish(plt, figure, axes, path, "Chi-square against target-block-time")
    return ""


def _margin(plt, metrics: Path, path: Path, plan, run_root: Path) -> str:
    rows = _rows(metrics / "sortition_margins.csv")
    if not rows:
        return ("sortition_margins.csv is empty: the sortition delays come from "
                "debug.log, so the nodes must run with -debug=wpoa")
    row = rows[0]
    values = {
        "mean": _number(row.get("G_medio_s")),
        "median": _number(row.get("G_mediano_s")),
        "min": _number(row.get("G_min_s")),
        "p05": _number(row.get("G_p05_s")),
    }
    band = _number(row.get("banda_dmax_s"))
    if all(v is None for v in values.values()):
        return "sortition_margins.csv holds no usable G value"
    figure, axes = plt.subplots(figsize=(8, 5))
    names = [k for k, v in values.items() if v is not None]
    axes.bar(names, [values[k] for k in names], color="#4477aa")
    if band:
        axes.axhline(band, color="darkgreen", linestyle="--",
                     label="band Dmax = %.2f s" % band)
    axes.axhline(0.1, color="crimson", linestyle=":",
                 label="0.1 s: below this the network decides, not the score")
    axes.set_ylabel("timer-race margin G (s)")
    axes.legend(fontsize=8)
    fraction = _number(row.get("frazione_G_sotto_100ms"))
    subtitle = "" if fraction is None else "  (%.1f%% of rounds under 100 ms)" % (
        100 * fraction)
    _finish(plt, figure, axes, path,
            "Prop. 5.18 - timer-race margin%s" % subtitle)
    return ""


def _block_time(plt, metrics: Path, path: Path, plan, run_root: Path) -> str:
    rows = _rows(metrics / "block_times.csv")
    if not rows:
        return "block_times.csv is empty"
    row = rows[0]
    mean = _number(row.get("dt_medio_s"))
    if mean is None:
        return "block_times.csv holds no mean interval"
    target = _number(row.get("target_s")) or plan.target_block_time
    stats = {"mean": mean, "median": _number(row.get("dt_mediana_s")),
             "min": _number(row.get("dt_min_s")), "max": _number(row.get("dt_max_s"))}
    stats = {k: v for k, v in stats.items() if v is not None}
    figure, axes = plt.subplots(figsize=(8, 5))
    axes.bar(list(stats), list(stats.values()), color="#66aa77")
    axes.axhline(target, color="crimson", linestyle="--",
                 label="target %.0f s" % target)
    deviation = _number(row.get("dt_sd_s"))
    if deviation is not None and "mean" in stats:
        axes.errorbar(["mean"], [stats["mean"]], yerr=[deviation], fmt="none",
                      ecolor="black", capsize=6, label="sd %.2f s" % deviation)
    axes.set_ylabel("inter-block interval (s)")
    axes.legend(fontsize=8)
    gap = _number(row.get("scarto_pct"))
    subtitle = "" if gap is None else "  (%+.1f%% against target)" % gap
    _finish(plt, figure, axes, path,
            "Block time - %s%s" % (plan.scenario, subtitle))
    return ""


def _heaviest_excess(plt, metrics: Path, path: Path, plan, run_root: Path) -> str:
    """How far the heaviest validator departs from its expected share.

    The single number that says whether the weighting is doing what it
    claims: if the heaviest node systematically takes more than its weight
    entitles it to, the damping is not working.
    """
    rows = _rows(metrics / "epoch_shares.csv")
    if not rows:
        return "epoch_shares.csv is empty: no epoch closed inside the wPoA window"
    by_epoch = defaultdict(list)
    for row in rows:
        epoch = _number(row.get("epoca"))
        weight_share = _number(row.get("quota_peso_epoca"))
        share = _number(row.get("quota_osservata_epoca"))
        if epoch is None or weight_share is None or share is None:
            continue
        by_epoch[epoch].append((weight_share, share, row.get("host", "?")))
    points = []
    for epoch in sorted(by_epoch):
        heaviest = max(by_epoch[epoch], key=lambda item: item[0])
        points.append((epoch, heaviest[1] - heaviest[0], heaviest[2]))
    if not points:
        return "epoch_shares.csv holds no epoch with both shares"
    figure, axes = plt.subplots(figsize=(9, 5))
    axes.bar([p[0] for p in points], [p[1] for p in points],
             color=["#cc6677" if p[1] > 0 else "#4477aa" for p in points])
    axes.axhline(0, color="black", linewidth=0.8)
    axes.set_xlabel("epoch")
    axes.set_ylabel("observed share - expected share")
    hosts = sorted({p[2] for p in points})
    _finish(plt, figure, axes, path,
            "Heaviest validator, excess over its weight (%s)" % ", ".join(hosts))
    return ""


# ---------------------------------------------------------------------------
# The emulation's own figures
#
# These three were produced by `reporting._plots` until commit f527222
# replaced the call to it with `plots.generate` and left the function behind,
# uncalled. From then on no run drew them: the two runs that have them on disk
# predate that commit, and the one that came after has an empty `plots/`. They
# are restored here, in the module that owns figures, and `reporting._plots`
# is gone.
#
# They read the sampler's series, not the campaign sheets, so they survive a
# run whose admin snapshot never happened - which is exactly the run that most
# needs a picture of what did happen.
# ---------------------------------------------------------------------------

def _height_per_node(plt, metrics: Path, path: Path, plan, run_root: Path) -> str:
    """Chain height against wall-clock time, one line per node.

    The x axis is the sampler's monotonic clock, in seconds from the start of
    the run. There is no simulated time here and no scale factor: a second on
    this axis is a second of the machine's clock.
    """
    rows = _rows(metrics / "node_observations.csv")
    if not rows:
        return ("node_observations.csv is empty: the sampler recorded nothing, "
                "so there is no height series to draw")
    series = defaultdict(list)
    for row in rows:
        height = _number(row.get("block_height"))
        monotonic = _number(row.get("timestamp_monotonic"))
        node = row.get("node_id", "")
        if height is None or monotonic is None or not node:
            continue
        series[node].append((monotonic, height))
    if not series:
        return ("node_observations.csv holds no (node, monotonic, height) "
                "triple: the columns are present but never filled")
    origin = min(points[0][0] for points in
                 (sorted(v) for v in series.values()) if points)
    figure, axes = plt.subplots(figsize=(10, 5))
    for node, points in sorted(series.items()):
        points.sort()
        axes.plot([p[0] - origin for p in points], [p[1] for p in points],
                  label=node, linewidth=1)
    axes.set_xlabel("wall-clock time since the first sample (s)")
    axes.set_ylabel("block height")
    if len(series) <= 12:
        axes.legend(fontsize=7, ncol=2)
    _finish(plt, figure, axes, path,
            "Chain height per node - %s" % plan.scenario)
    return ""


def _block_propagation(plt, metrics: Path, path: Path, plan, run_root: Path) -> str:
    """How long a block took to reach every node that saw it.

    Bounded below by the sampling interval, so it is an upper bound rather
    than a wire measurement; the axis label says so and so does the catalogue.
    """
    values = [_number(row.get("propagation_time"))
              for row in _rows(metrics / "block_propagation.csv")]
    values = [v for v in values if v is not None]
    if not values:
        return ("block_propagation.csv is empty: no block was seen by two "
                "nodes, so no propagation time could be measured")
    figure, axes = plt.subplots(figsize=(8, 4.5))
    axes.hist(values, bins=min(40, max(5, len(values) // 4)), color="#4477aa")
    axes.set_xlabel("propagation time (s, upper bound: >= the 10 s sampling interval)")
    axes.set_ylabel("blocks")
    _finish(plt, figure, axes, path,
            "Block propagation across nodes - %s (n=%d)" % (plan.scenario, len(values)))
    return ""


def _link_delays(plt, metrics: Path, path: Path, plan, run_root: Path) -> str:
    """The one-way delay netem actually installed, per directed link.

    Read from `netem_conditions.csv`, which is written from
    `runtime/topology-realized.json` - what the kernel was told, not what the
    topology file asked for. The two differ whenever a link failed to come up.
    """
    values = [_number(row.get("netem_delay_ms"))
              for row in _rows(metrics / "netem_conditions.csv")]
    values = [v for v in values if v is not None]
    if not values:
        return ("netem_conditions.csv is empty: runtime/topology-realized.json "
                "was never written, so no impairment was recorded as installed")
    figure, axes = plt.subplots(figsize=(8, 4.5))
    axes.hist(values, bins=min(30, max(5, len(values) // 2)), color="#aa7744")
    axes.set_xlabel("configured one-way delay (ms)")
    axes.set_ylabel("directed links")
    _finish(plt, figure, axes, path,
            "Emulated link delays - %s" % plan.topology.name)
    return ""
