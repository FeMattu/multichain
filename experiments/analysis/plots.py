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
}


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


def generate(run_root: Path, plan) -> dict:
    """Draw what this run supports. Returns produced and skipped, with reasons."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        LOG.warning("matplotlib is not installed: no figure was produced")
        return {"produced": [], "skipped": {name: "matplotlib is not installed"
                                            for name in FIGURES}}

    run_root = Path(run_root)
    metrics = run_root / "metrics"
    plots = run_root / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    produced, skipped = [], {}

    for name, drawer in (
        ("01_traiettoria_pesi.png", _weights_trajectory),
        ("02_quota_per_epoca.png", _share_per_epoch),
        ("03_chi2_vs_tbt.png", _chi2_vs_tbt),
        ("04_margine_prop518.png", _margin),
        ("05_block_time.png", _block_time),
        ("06_eccesso_miner_pesante.png", _heaviest_excess),
    ):
        try:
            reason = drawer(plt, metrics, plots / name, plan)
        except Exception as exc:  # noqa: BLE001 - a figure must not sink the report
            reason = "drawing failed: %s" % exc
            LOG.warning("%s: %s", name, reason)
        if reason:
            skipped[name] = reason
            LOG.info("%s not drawn: %s", name, reason)
        else:
            produced.append(str(plots / name))
    LOG.info("figures: %d drawn, %d skipped", len(produced), len(skipped))
    return {"produced": produced, "skipped": skipped}


def _finish(plt, figure, axes, path: Path, title: str) -> None:
    axes.set_title(title)
    axes.grid(alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=120)
    plt.close(figure)


def _weights_trajectory(plt, metrics: Path, path: Path, plan) -> str:
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


def _share_per_epoch(plt, metrics: Path, path: Path, plan) -> str:
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


def _chi2_vs_tbt(plt, metrics: Path, path: Path, plan) -> str:
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


def _margin(plt, metrics: Path, path: Path, plan) -> str:
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


def _block_time(plt, metrics: Path, path: Path, plan) -> str:
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


def _heaviest_excess(plt, metrics: Path, path: Path, plan) -> str:
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
