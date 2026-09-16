#!/usr/bin/env python3
"""Figures for a finished run. Reads phase 2 and phase 3 only — never raw data.

That restriction is the point. A plot drawn from the raw logs could show something no test
ever saw, and a reader would have no way to tell which of the two to believe. Everything
here is drawn from a table that a test also read, so a figure and a p-value can never
disagree about the same quantity.

    python3 test/plotting/generate_plots.py --config <profile> --run-dir <run>

Figures, in the order they are produced:

1. ``weight_vs_election.png`` — **the headline.** Entitled share against observed share per
   epoch, with the Wilson band drawn around the observation. This is the figure the whole
   experiment is for, so it is drawn first and largest.
2. ``weights_over_time.png`` — raw, effective and final weight per miner per epoch. Three
   panels, because the three differ by exactly the two transformations the protocol
   applies (malus, then dumping), and seeing them apart is how one tells which stage moved.
3. ``election_share_distribution.png`` — observed share per validator, per epoch and
   cumulative.
4. ``concentration_over_time.png`` — HHI, Nakamoto and Gini, theoretical against observed.
5. ``esg_scores.png`` — the certified scores, by role.
6. ``gini_delta_trajectory.png`` — Gini(published) − Gini(input) with its regression line:
   does the engine amplify the inequality it is given?
7. ``margin_distribution.png`` — the timer-race margin, observed against the simulated
   exact distribution.
8. ``rho_vs_next_weight.png`` — the WeightEngine's lag-1 feedback as a scatter.
9. ``traffic_per_epoch.png`` — planned against sent against on-chain, which is where a
   silent publish failure becomes visible.

Matplotlib only, ``Agg`` backend, no seaborn and no styling beyond a shared palette: these
are diagnostic figures, and a figure that needs a legend to decode its colours has failed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "analysis"))

#: A colour-blind-safe qualitative palette (Okabe-Ito). Validators are coloured by their
#: position in a sorted address list, so the same validator keeps its colour across every
#: figure of a run.
PALETTE = [
    "#0072B2", "#D55E00", "#009E73", "#CC79A7",
    "#E69F00", "#56B4E9", "#F0E442", "#000000",
]

FIGSIZE = (11, 6)
DPI = 130


def read_table(path: Path) -> List[Dict[str, str]]:
    if not path.is_file():
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def f(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def i(value: Any) -> Optional[int]:
    result = f(value)
    return None if result is None else int(result)


def b(value: Any) -> Optional[bool]:
    if value in (None, ""):
        return None
    return str(value).strip().lower() in ("true", "1", "yes")


def short(address: str, width: int = 10) -> str:
    return (address or "")[:width]


def colour_map(addresses: Sequence[str]) -> Dict[str, str]:
    return {a: PALETTE[n % len(PALETTE)] for n, a in enumerate(sorted(set(addresses)))}


def finish(fig, path: Path, note: str = "") -> Path:
    """Save, and stamp the figure with the caveat a reader needs to have with it."""
    if note:
        fig.text(0.01, 0.01, note, fontsize=7, color="#555555", va="bottom")
    fig.tight_layout(rect=(0, 0.03 if note else 0, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def empty(path: Path, title: str, reason: str) -> Path:
    """A figure that says why it is empty, instead of an empty figure.

    A missing PNG makes a reader wonder whether the script crashed; a blank one makes them
    wonder whether the quantity was zero. This says which.
    """
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.axis("off")
    ax.text(0.5, 0.6, title, ha="center", va="center", fontsize=13)
    ax.text(0.5, 0.3, reason, ha="center", va="center", fontsize=9, color="#B00020", wrap=True)
    return finish(fig, path)


class Plotter:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        self.phase2 = self.run_dir / "analysis" / "phase2"
        self.phase3 = self.run_dir / "analysis" / "phase3"
        self.out = self.run_dir / "analysis" / "plots"
        self.out.mkdir(parents=True, exist_ok=True)

        self.epoch_level = read_table(self.phase2 / "epoch_level.csv")
        self.epoch_engine = read_table(self.phase2 / "epoch_engine.csv")
        self.epoch_conc = read_table(self.phase2 / "epoch_concentration.csv")
        self.epoch_traffic = read_table(self.phase2 / "epoch_traffic.csv")
        self.round_level = read_table(self.phase2 / "round_level.csv")
        self.validators = read_table(self.phase3 / "wpoa_epoch_validators.csv")
        self.tests = read_table(self.phase3 / "wpoa_epoch_tests.csv")
        self.gini = read_table(self.phase3 / "weight_engine_gini.csv")
        self.gini_summary = read_table(self.phase3 / "weight_engine_gini_summary.csv")
        self.correlations = read_table(self.phase3 / "weight_engine_correlations.csv")
        self.timer = read_table(self.phase3 / "wpoa_timer_race.csv")
        self.esg = read_table(self.run_dir / "analysis" / "phase1" / "esg_events.csv")
        self.written: List[Path] = []

    def record(self, path: Path) -> None:
        self.written.append(path)

    # -- 1. the headline ---------------------------------------------------------------

    def plot_weight_vs_election(self) -> None:
        path = self.out / "weight_vs_election.png"
        rows = [r for r in self.validators if r.get("epoch") not in ("", "all", None)]
        if not rows:
            self.record(empty(path, "Weight vs probability of election",
                              "no fully measured epoch: every round fell inside the setup "
                              "phase, where native round robin governs"))
            return

        addresses = sorted({r["validator_address"] for r in rows})
        colours = colour_map(addresses)
        epochs = sorted({i(r["epoch"]) for r in rows if i(r["epoch"]) is not None})

        fig, (ax_bar, ax_scatter) = plt.subplots(
            1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": [1.6, 1]}
        )

        # Left: paired bars per epoch, with the Wilson interval on the observed bar.
        width = 0.8 / max(1, len(addresses))
        for n, address in enumerate(addresses):
            xs, theoretical, observed, low, high = [], [], [], [], []
            for epoch in epochs:
                row = next(
                    (r for r in rows
                     if i(r["epoch"]) == epoch and r["validator_address"] == address),
                    None,
                )
                if row is None:
                    continue
                xs.append(epoch + (n - (len(addresses) - 1) / 2) * width)
                theoretical.append(f(row.get("p_theoretical")) or 0.0)
                p_hat = f(row.get("p_hat")) or 0.0
                observed.append(p_hat)
                low.append(max(0.0, p_hat - (f(row.get("wilson95_low")) or p_hat)))
                high.append(max(0.0, (f(row.get("wilson95_high")) or p_hat) - p_hat))
            if not xs:
                continue
            ax_bar.bar(xs, observed, width=width * 0.9, color=colours[address],
                       label=short(address), alpha=0.85,
                       yerr=[low, high], capsize=2, error_kw={"lw": 0.8, "ecolor": "#333333"})
            # The entitlement as a tick on top of the bar it should match.
            ax_bar.scatter(xs, theoretical, marker="_", s=90, color="black", zorder=5,
                           linewidths=1.4)

        ax_bar.set_xlabel("epoch")
        ax_bar.set_ylabel("share of blocks")
        ax_bar.set_title("Observed share (bars, 95% Wilson) vs entitled share (black ticks)")
        ax_bar.set_xticks(epochs)
        ax_bar.legend(fontsize=7, ncol=2)
        ax_bar.grid(axis="y", alpha=0.25)

        # Right: the identity plot. On target means on the diagonal.
        for address in addresses:
            points = [
                (f(r.get("p_theoretical")), f(r.get("p_hat")))
                for r in rows
                if r["validator_address"] == address
            ]
            points = [(x, y) for x, y in points if x is not None and y is not None]
            if points:
                ax_scatter.scatter(
                    [p[0] for p in points], [p[1] for p in points],
                    color=colours[address], s=36, alpha=0.85, label=short(address),
                )
        limit = 1.0
        ax_scatter.plot([0, limit], [0, limit], "k--", lw=1, label="perfect agreement")
        ax_scatter.set_xlabel("entitled share (final weight)")
        ax_scatter.set_ylabel("observed share")
        ax_scatter.set_title("Entitled vs observed, one point per validator-epoch")
        ax_scatter.grid(alpha=0.25)
        ax_scatter.legend(fontsize=7)

        rejects = sum(1 for t in self.tests if b(t.get("gof_reject_alpha05")))
        note = (
            "Entitlement is the effective weight after malus and dumping — what the "
            "election consumes. Goodness of fit rejected in %d of %d epoch(s) at alpha=0.05. "
            "Wide intervals mean the run is short, not that the election is fair."
            % (rejects, len(self.tests))
        )
        self.record(finish(fig, path, note))

    # -- 2. weights over time ----------------------------------------------------------

    def plot_weights_over_time(self) -> None:
        path = self.out / "weights_over_time.png"
        rows = [r for r in self.epoch_level if i(r.get("epoch")) is not None]
        if not rows:
            self.record(empty(path, "Weight per miner per epoch", "no epoch-level rows"))
            return
        addresses = sorted({r["validator_address"] for r in rows})
        colours = colour_map(addresses)
        published = defaultdict(dict)
        for row in self.epoch_engine:
            epoch = i(row.get("epoch"))
            if epoch is not None:
                published[row.get("cluster_head_address", "")][epoch] = f(row.get("w_k_published"))

        fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharex=True)
        panels = [
            ("raw (published on wpoa-weights)", lambda a, e: published.get(a, {}).get(e)),
            ("after malus (w x Psi)", None),
            ("final, after dumping (what the election uses)", None),
        ]
        for address in addresses:
            series = sorted(
                (i(r["epoch"]), r) for r in rows if r["validator_address"] == address
            )
            epochs = [e for e, _ in series]
            raw = [published.get(address, {}).get(e) for e in epochs]
            after_malus = [
                (f(r.get("w_raw_end")) or 0.0) * (f(r.get("psi")) if f(r.get("psi")) is not None else 1.0)
                for _, r in series
            ]
            final = [f(r.get("w_eff_end")) for _, r in series]
            for ax, values in zip(axes, (raw, after_malus, final)):
                pairs = [(e, v) for e, v in zip(epochs, values) if v is not None]
                if pairs:
                    ax.plot([p[0] for p in pairs], [p[1] for p in pairs],
                            marker="o", ms=3.5, color=colours[address], label=short(address))
        for ax, (title, _) in zip(axes, panels):
            ax.set_title(title, fontsize=10)
            ax.set_xlabel("epoch")
            ax.grid(alpha=0.25)
        axes[0].set_ylabel("weight")
        axes[0].legend(fontsize=7)
        fig.suptitle("Weight per miner per epoch, at each stage of the transformation")
        self.record(finish(
            fig, path,
            "The three panels differ by exactly the two transformations the protocol "
            "applies: the malus factor, then the dumping function.",
        ))

    # -- 3. election share distribution ------------------------------------------------

    def plot_election_share(self) -> None:
        path = self.out / "election_share_distribution.png"
        rows = [r for r in self.epoch_level if b(r.get("in_setup")) is False]
        if not rows:
            self.record(empty(path, "Election share", "no measured epoch"))
            return
        addresses = sorted({r["validator_address"] for r in rows})
        colours = colour_map(addresses)
        epochs = sorted({i(r["epoch"]) for r in rows if i(r["epoch"]) is not None})

        fig, (ax_bar, ax_pie) = plt.subplots(1, 2, figsize=(13, 5.5),
                                             gridspec_kw={"width_ratios": [2, 1]})
        bottom = [0.0] * len(epochs)
        for address in addresses:
            values = []
            for epoch in epochs:
                row = next((r for r in rows
                            if i(r["epoch"]) == epoch and r["validator_address"] == address), None)
                values.append((f(row.get("p_observed")) if row else 0.0) or 0.0)
            ax_bar.bar(epochs, values, bottom=bottom, color=colours[address],
                       label=short(address), width=0.75)
            bottom = [a + b for a, b in zip(bottom, values)]
        ax_bar.set_xlabel("epoch")
        ax_bar.set_ylabel("share of blocks won")
        ax_bar.set_title("Observed share per validator, per epoch")
        ax_bar.set_xticks(epochs)
        ax_bar.legend(fontsize=7, ncol=2)
        ax_bar.grid(axis="y", alpha=0.25)

        totals = defaultdict(int)
        for row in rows:
            totals[row["validator_address"]] += i(row.get("O_i")) or 0
        if sum(totals.values()) > 0:
            labels = [short(a) for a in addresses]
            ax_pie.pie(
                [totals[a] for a in addresses],
                labels=labels,
                colors=[colours[a] for a in addresses],
                autopct="%1.1f%%",
                textprops={"fontsize": 8},
            )
            ax_pie.set_title("Cumulative share over the whole run")
        else:
            ax_pie.axis("off")
        self.record(finish(fig, path))

    # -- 4. concentration --------------------------------------------------------------

    def plot_concentration(self) -> None:
        path = self.out / "concentration_over_time.png"
        rows = [r for r in self.epoch_conc if i(r.get("epoch")) is not None]
        if not rows:
            self.record(empty(path, "Concentration", "no concentration rows"))
            return
        epochs = [i(r["epoch"]) for r in rows]
        fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
        for ax, (label, theoretical_key, observed_key) in zip(
            axes,
            [
                ("HHI", "theoretical_HHI", "observed_HHI"),
                ("Nakamoto coefficient (1/2)", "theoretical_nakamoto_1_2", "observed_nakamoto_1_2"),
                ("Gini", "theoretical_gini", "observed_gini"),
            ],
        ):
            ax.plot(epochs, [f(r.get(theoretical_key)) for r in rows],
                    marker="o", ms=3.5, color=PALETTE[0], label="theoretical (weights)")
            ax.plot(epochs, [f(r.get(observed_key)) for r in rows],
                    marker="s", ms=3.5, color=PALETTE[1], label="observed (blocks)")
            ax.set_title(label, fontsize=10)
            ax.set_xlabel("epoch")
            ax.grid(alpha=0.25)
            ax.legend(fontsize=7)
        fig.suptitle("Concentration of mining power: entitled against delivered")
        self.record(finish(
            fig, path,
            "A gap between the two lines is a property of the election; a rising "
            "theoretical line is a property of the weight engine.",
        ))

    # -- 5. ESG ------------------------------------------------------------------------

    def plot_esg(self) -> None:
        path = self.out / "esg_scores.png"
        if not self.esg:
            self.record(empty(path, "Certified ESG scores", "no ESG publication recorded"))
            return
        by_role = defaultdict(list)
        for row in self.esg:
            score = f(row.get("esg_score"))
            if score is not None:
                by_role[row.get("target_role", "?")].append(
                    (row.get("target_node_id", ""), score)
                )
        fig, ax = plt.subplots(figsize=FIGSIZE)
        offset = 0
        ticks, labels = [], []
        for n, role in enumerate(sorted(by_role)):
            entries = sorted(by_role[role])
            xs = list(range(offset, offset + len(entries)))
            ax.bar(xs, [e[1] for e in entries], color=PALETTE[n % len(PALETTE)], label=role)
            ticks.extend(xs)
            labels.extend(e[0] for e in entries)
            offset += len(entries) + 1
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=7)
        ax.set_ylabel("certified ESG score")
        ax.set_title("ESG scores certified by the Certification Authorities")
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.25)
        self.record(finish(
            fig, path,
            "A miner with no certified score computes W_k = 0 and publishes the "
            "positivity floor of 1, which would make the sortition uniform.",
        ))

    # -- 6. Gini delta -----------------------------------------------------------------

    def plot_gini_delta(self) -> None:
        path = self.out / "gini_delta_trajectory.png"
        rows = [
            r for r in self.gini
            if i(r.get("epoch")) is not None and f(r.get("gini_delta")) is not None
        ]
        if len(rows) < 2:
            self.record(empty(path, "Gini(published) - Gini(input)",
                              "fewer than two epochs carry both Gini values"))
            return
        epochs = [i(r["epoch"]) for r in rows]
        deltas = [f(r["gini_delta"]) for r in rows]
        fig, ax = plt.subplots(figsize=FIGSIZE)
        ax.plot(epochs, deltas, marker="o", ms=4, color=PALETTE[0], label="Gini(published) - Gini(input)")
        ax.axhline(0.0, color="black", lw=0.8, ls="--", label="no amplification")

        summary = self.gini_summary[0] if self.gini_summary else {}
        slope, intercept = f(summary.get("slope")), f(summary.get("intercept"))
        if slope is not None and intercept is not None:
            xs = [min(epochs), max(epochs)]
            ax.plot(xs, [slope * x + intercept for x in xs], color=PALETTE[1], lw=1.5,
                    label="regression, slope = %.5f" % slope)
        ax.set_xlabel("epoch")
        ax.set_ylabel("Gini difference")
        ax.set_title("Does the engine amplify the inequality of its own inputs?")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.25)
        self.record(finish(
            fig, path,
            "Above zero: the published weights are more unequal than the ESG x activity "
            "inputs that produced them. A rising slope means the gap widens over time.",
        ))

    # -- 7. margin ---------------------------------------------------------------------

    def plot_margin(self) -> None:
        path = self.out / "margin_distribution.png"
        margins = [
            f(r.get("margin_G_s"))
            for r in self.round_level
            if b(r.get("in_setup")) is False and f(r.get("margin_G_s")) is not None
        ]
        if len(margins) < 3:
            self.record(empty(path, "Timer-race margin",
                              "fewer than three measured rounds carry a margin"))
            return
        timer = self.timer[0] if self.timer else {}
        fig, ax = plt.subplots(figsize=FIGSIZE)
        ax.hist(margins, bins=min(30, max(5, len(margins) // 3)), color=PALETTE[0],
                alpha=0.8, density=True, label="observed margin G")
        mean_observed = sum(margins) / len(margins)
        ax.axvline(mean_observed, color=PALETTE[1], lw=1.5,
                   label="observed mean = %.4f s" % mean_observed)
        mc_mean = f(timer.get("ks_mc_mean_G_s"))
        if mc_mean is not None:
            ax.axvline(mc_mean, color=PALETTE[2], lw=1.5, ls="--",
                       label="simulated exact mean = %.4f s" % mc_mean)
        ax.set_xlabel("margin between the two fastest delays, seconds")
        ax.set_ylabel("density")
        ax.set_title("Timer-race margin: the window in which an inversion can occur")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.25)
        self.record(finish(
            fig, path,
            "Reference test: KS against the simulated exact distribution, p = %s. The "
            "Beta(1,n) comparison is a straw man and is expected to reject with "
            "non-uniform weights." % (timer.get("ks_mc_p") or "-"),
        ))

    # -- 8. feedback -------------------------------------------------------------------

    def plot_rho_feedback(self) -> None:
        path = self.out / "rho_vs_next_weight.png"
        points: List[Tuple[float, float, str]] = []
        for row in self.epoch_engine:
            rho = f(row.get("return_rate_rho"))
            nxt = f(row.get("w_published_next_epoch"))
            if rho is not None and nxt is not None:
                points.append((rho, nxt, row.get("cluster_head_address", "")))
        if len(points) < 3:
            self.record(empty(path, "WeightEngine lag-1 feedback",
                              "fewer than three (rho_e, w_{e+1}) pairs: with lambda = 0, or "
                              "with no restitution, this channel is inert by construction"))
            return
        colours = colour_map([p[2] for p in points])
        fig, ax = plt.subplots(figsize=FIGSIZE)
        for address in sorted({p[2] for p in points}):
            subset = [p for p in points if p[2] == address]
            ax.scatter([p[0] for p in subset], [p[1] for p in subset],
                       color=colours[address], s=40, alpha=0.85, label=short(address))
        pooled = next((c for c in self.correlations
                       if c.get("cluster_head_address") == "(pooled)"), {})
        ax.set_xlabel("restitution rate rho at epoch e")
        ax.set_ylabel("weight published at epoch e+1")
        ax.set_title("The WeightEngine's only endogenous feedback channel")
        ax.legend(fontsize=7)
        ax.grid(alpha=0.25)
        self.record(finish(
            fig, path,
            "Pooled lag-1 Spearman rho = %s (p = %s, n = %s)."
            % (pooled.get("spearman_rho", "-"), pooled.get("spearman_p", "-"),
               pooled.get("n_pairs", "-")),
        ))

    # -- 9. traffic --------------------------------------------------------------------

    def plot_traffic(self) -> None:
        path = self.out / "traffic_per_epoch.png"
        rows = [r for r in self.epoch_traffic if r.get("role") == "company"]
        if not rows:
            self.record(empty(path, "Company traffic per epoch", "no company traffic rows"))
            return
        by_epoch = defaultdict(lambda: {"planned": 0.0, "sent": 0.0, "onchain": 0.0})
        for row in rows:
            epoch = i(row.get("epoch"))
            if epoch is None:
                continue
            by_epoch[epoch]["planned"] += f(row.get("planned")) or 0.0
            by_epoch[epoch]["sent"] += f(row.get("sent_logged")) or 0.0
            by_epoch[epoch]["onchain"] += f(row.get("onchain_stream_items")) or 0.0
        epochs = sorted(by_epoch)
        fig, ax = plt.subplots(figsize=FIGSIZE)
        width = 0.27
        ax.bar([e - width for e in epochs], [by_epoch[e]["planned"] for e in epochs],
               width=width, color=PALETTE[0], label="planned by the daemons")
        ax.bar(epochs, [by_epoch[e]["sent"] for e in epochs],
               width=width, color=PALETTE[1], label="sent (daemon counter)")
        ax.bar([e + width for e in epochs], [by_epoch[e]["onchain"] for e in epochs],
               width=width, color=PALETTE[2], label="on chain (stream items)")
        ax.set_xlabel("epoch")
        ax.set_ylabel("informative transactions")
        ax.set_title("Company traffic: planned, sent and actually on chain")
        ax.set_xticks(epochs)
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.25)
        self.record(finish(
            fig, path,
            "A gap between 'sent' and 'on chain' is the number of publishes the chain "
            "rejected — usually fee policy — and it depresses tau without any error.",
        ))

    # -- driver ------------------------------------------------------------------------

    def run(self) -> List[Path]:
        self.plot_weight_vs_election()
        self.plot_weights_over_time()
        self.plot_election_share()
        self.plot_concentration()
        self.plot_esg()
        self.plot_gini_delta()
        self.plot_margin()
        self.plot_rho_feedback()
        self.plot_traffic()

        index = self.out / "README.md"
        lines = ["# Figures", "",
                 "Drawn from `analysis/phase2` and `analysis/phase3` only — never from raw "
                 "data, so a figure and a test can never disagree about the same quantity.",
                 ""]
        for path in self.written:
            lines.append("- [`%s`](%s)" % (path.name, path.name))
        lines.append("")
        index.write_text("\n".join(lines), encoding="utf-8")
        return self.written


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", default=None, help="accepted for interface symmetry")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    if not (run_dir / "analysis" / "phase3").is_dir():
        print(
            "[plots] no phase 3 output in %s; run phase3_analyze.py first" % run_dir,
            file=sys.stderr,
        )
        return 1
    written = Plotter(run_dir).run()
    print("[plots] %d figure(s) in %s" % (len(written), run_dir / "analysis" / "plots"))
    for path in written:
        print("    %s" % path.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
