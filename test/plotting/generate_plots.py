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

Weight <-> election diagnostics (each drawn from the same phase-3 table its test read):

10. ``p_value_uniformity.png`` — histogram of the per-epoch goodness-of-fit p-values with the
    uniform expectation, KS vs U(0,1) and a binomial test on the rejection count.
11. ``wilson_violation_heatmap.png`` — epoch x validator, red where the entitled share fell
    outside the 95% Wilson interval, with row/column violation totals.
12. ``residual_boxplot_by_validator.png`` — per-validator boxplot of ``p_hat - p_theoretical``
    over all epochs, with zero drawn and the observation count per validator.

The malicious-miner experiment (only when a ``malicious`` section ran; otherwise each says so):

13. ``malus_action_funnel.png`` — opportunity -> attempt -> RPC accepted -> confirmed ->
    valid malus, by kind, with counts.
14. ``malus_state_trajectory.png`` — per-epoch M, Psi, raw and effective weight for the
    malicious miners, with confirmed-action epochs marked.
15. ``malus_detection_latency.png`` — ECDFs of detection latency (blocks) and activation
    latency (epochs).
16. ``malus_weight_effect.png`` — relative change of effective weight, malicious vs honest,
    median + IQR + transparent individual trajectories.
17. ``malus_invariant_audit.png`` — epoch x validator grid of the malus invariants, green
    for hold and red for violated.

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


def _fmt(value: Any, digits: int = 4) -> str:
    """Format a value for a figure caption, blanking anything not finite."""
    if value in (None, ""):
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "-"
    return ("%%.%df" % digits) % number


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

        # Weight <-> election diagnostics (phase 3), each paired with its own test table.
        self.pvalue_uniformity = read_table(self.phase3 / "weight_election_pvalue_uniformity.csv")
        self.wilson_coverage = read_table(self.phase3 / "weight_election_wilson_coverage.csv")
        self.residuals = read_table(self.phase3 / "weight_election_residuals.csv")

        # The malicious-miner experiment (phase 2 ground truth + phase 3 statistics).
        self.malus_state = read_table(self.phase2 / "malus_state.csv")
        self.malus_actions = read_table(self.phase2 / "malus_actions.csv")
        self.malus_funnel = read_table(self.phase3 / "malus_funnel.csv")
        self.malus_latency = read_table(self.phase3 / "malus_latency.csv")
        self.malus_weight_effect = read_table(self.phase3 / "malus_weight_effect.csv")
        self.malus_invariants = read_table(self.phase3 / "malus_invariants.csv")

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

    # -- 10. weight <-> election diagnostics -------------------------------------------

    def plot_pvalue_uniformity(self) -> None:
        path = self.out / "p_value_uniformity.png"
        pvals = [f(r.get("gof_p_value")) for r in self.tests
                 if r.get("epoch") not in ("", "all", None) and f(r.get("gof_p_value")) is not None]
        stats = self.pvalue_uniformity[0] if self.pvalue_uniformity else {}
        if not pvals:
            self.record(empty(path, "Per-epoch p-value uniformity",
                              "no per-epoch goodness-of-fit p-value was computed"))
            return
        fig, ax = plt.subplots(figsize=FIGSIZE)
        bins = 10
        ax.hist(pvals, bins=bins, range=(0.0, 1.0), color=PALETTE[0], alpha=0.8,
                edgecolor="white", label="observed p-values")
        expected = len(pvals) / bins
        ax.axhline(expected, color=PALETTE[1], lw=1.6, ls="--",
                   label="uniform expectation (%.2f/bin)" % expected)
        ax.axvline(0.05, color=PALETTE[3], lw=1.0, ls=":", label="alpha = 0.05")
        ax.set_xlabel("goodness-of-fit p-value")
        ax.set_ylabel("epochs")
        ax.set_title("Per-epoch p-values against the uniform null of a weighted election")
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.25)
        note = (
            "N = %s epochs, k = %s rejections at alpha = %s (%.2f expected). "
            "KS vs U(0,1): D = %s, p = %s. Binomial on the rejection count: p = %s. "
            "A weighted election makes these p-values ~U(0,1); a spike near 0 is a "
            "mis-specified null."
            % (
                stats.get("n_epochs", len(pvals)),
                stats.get("n_rejections", "-"),
                stats.get("alpha", "0.05"),
                float(stats.get("expected_rejections") or 0.0),
                _fmt(stats.get("ks_statistic_vs_uniform")),
                _fmt(stats.get("ks_p_value")),
                _fmt(stats.get("binomial_p_value_rejection_count")),
            )
        )
        self.record(finish(fig, path, note))

    def plot_wilson_violation_heatmap(self) -> None:
        path = self.out / "wilson_violation_heatmap.png"
        rows = [r for r in self.wilson_coverage if r.get("epoch") not in ("", None)]
        rows = [r for r in rows if b(r.get("inside_wilson95")) is not None]
        if not rows:
            self.record(empty(path, "Wilson coverage violations",
                              "no (epoch, validator) interval had both a weight and blocks"))
            return
        epochs = sorted({i(r["epoch"]) for r in rows if i(r["epoch"]) is not None})
        validators = sorted({r["validator_address"] for r in rows})
        vio = {(i(r["epoch"]), r["validator_address"]): b(r.get("violation")) for r in rows}
        grid = [[1.0 if vio.get((e, v)) else 0.0 for e in epochs] for v in validators]

        fig, ax = plt.subplots(figsize=(max(8, len(epochs) * 0.5), max(4, len(validators) * 0.5)))
        ax.imshow(grid, aspect="auto", cmap="Reds", vmin=0.0, vmax=1.0)
        ax.set_xticks(range(len(epochs)))
        ax.set_xticklabels(epochs, fontsize=7)
        ax.set_yticks(range(len(validators)))
        ax.set_yticklabels([short(v) for v in validators], fontsize=7)
        # Row/column totals in the tick labels.
        col_tot = [sum(1 for v in validators if vio.get((e, v))) for e in epochs]
        row_tot = [sum(1 for e in epochs if vio.get((e, v))) for v in validators]
        ax.set_xticklabels(["%s\n(%d)" % (e, t) for e, t in zip(epochs, col_tot)], fontsize=7)
        ax.set_yticklabels(["%s (%d)" % (short(v), t) for v, t in zip(validators, row_tot)],
                           fontsize=7)
        ax.set_xlabel("epoch (column total = violations)")
        ax.set_ylabel("validator (row total = violations)")
        ax.set_title("Where the entitled share fell outside the 95% Wilson interval (red)")
        total = sum(col_tot)
        self.record(finish(
            fig, path,
            "A red cell is an epoch-validator where p_theoretical fell outside the observed "
            "share's 95%% Wilson interval. %d of %d cells; about %.1f are expected by chance "
            "at alpha = 0.05." % (total, len(epochs) * len(validators), 0.05 * len(rows)),
        ))

    def plot_residual_boxplot(self) -> None:
        path = self.out / "residual_boxplot_by_validator.png"
        rows = [r for r in self.residuals if f(r.get("residual")) is not None]
        if not rows:
            self.record(empty(path, "Residuals by validator",
                              "no (p_hat - p_theoretical) residuals were computed"))
            return
        by_validator: Dict[str, List[float]] = defaultdict(list)
        for r in rows:
            by_validator[r["validator_address"]].append(f(r["residual"]))
        validators = sorted(by_validator)
        data = [by_validator[v] for v in validators]
        colours = colour_map(validators)
        fig, ax = plt.subplots(figsize=(max(8, len(validators) * 1.1), 6))
        bp = ax.boxplot(data, patch_artist=True, showmeans=True)
        for patch, v in zip(bp["boxes"], validators):
            patch.set_facecolor(colours[v])
            patch.set_alpha(0.6)
        ax.axhline(0.0, color="black", lw=1.2, ls="--", label="zero (perfect match)")
        ax.set_xticks(range(1, len(validators) + 1))
        ax.set_xticklabels(["%s\n(n=%d)" % (short(v), len(by_validator[v])) for v in validators],
                           fontsize=7)
        ax.set_ylabel("residual  p_hat - p_theoretical")
        ax.set_title("Election-share residuals by validator, across all measured epochs")
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.25)
        self.record(finish(
            fig, path,
            "Each box is one validator's residuals over the measured epochs; the count is "
            "in the tick label. A box centred on zero is a validator elected at its "
            "entitled rate; a consistent offset is over- or under-representation.",
        ))

    # -- 11. the malicious-miner experiment --------------------------------------------

    def _malus_ran(self) -> bool:
        return any(f(r.get("attempts")) for r in self.malus_funnel) or bool(self.malus_actions)

    def plot_malus_funnel(self) -> None:
        path = self.out / "malus_action_funnel.png"
        if not self._malus_ran():
            self.record(empty(path, "Malus action funnel",
                              "no malicious experiment ran on this profile"))
            return
        stages = ["opportunities", "attempts", "sent", "confirmed", "valid_malus"]
        labels = ["opportunity", "attempt", "RPC accepted", "confirmed", "valid malus"]
        by_scope = {r.get("scope"): r for r in self.malus_funnel}
        fig, ax = plt.subplots(figsize=FIGSIZE)
        width = 0.38
        offsets = {"selfwrite": -width / 2, "badweight": width / 2}
        drawn = False
        for kind, off in offsets.items():
            row = by_scope.get(kind)
            if not row:
                continue
            values = [i(row.get(s)) or 0 for s in stages]
            xs = [k + off for k in range(len(stages))]
            ax.bar(xs, values, width=width,
                   color=PALETTE[0] if kind == "selfwrite" else PALETTE[1], label=kind)
            for x, v in zip(xs, values):
                if v:
                    ax.text(x, v, str(v), ha="center", va="bottom", fontsize=7)
            drawn = True
        # The 'all' row supplies the opportunity count (not defined per kind).
        all_row = by_scope.get("all", {})
        opp = i(all_row.get("opportunities"))
        if opp:
            ax.axhline(opp, color=PALETTE[3], lw=1.0, ls=":", label="opportunities (%d)" % opp)
        if not drawn:
            self.record(empty(path, "Malus action funnel", "the funnel table carried no rows"))
            return
        ax.set_xticks(range(len(stages)))
        ax.set_xticklabels(labels)
        ax.set_ylabel("count")
        ax.set_title("Malicious action funnel, by kind")
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.25)
        attempts = i(all_row.get("attempts")) or 0
        valid = i(all_row.get("valid_malus")) or 0
        self.record(finish(
            fig, path,
            "Each stage is a strict subset of the one before. Of %d attempts, %d became a "
            "valid malus (%s)."
            % (attempts, valid, _fmt((valid / attempts) if attempts else None)),
        ))

    def plot_malus_trajectory(self) -> None:
        path = self.out / "malus_state_trajectory.png"
        rows = [r for r in self.malus_state if i(r.get("epoch")) is not None]
        malicious = sorted({r["address"] for r in rows if b(r.get("is_malicious")) is True})
        if not rows or not malicious:
            self.record(empty(path, "Malus state trajectory",
                              "no malicious miner had a malus trajectory to plot"))
            return
        colours = colour_map(malicious)
        # Confirmed-action epochs, to mark on the panels.
        action_epochs = sorted({i(r.get("confirm_epoch")) for r in self.malus_actions
                                if b(r.get("confirmed")) and i(r.get("confirm_epoch")) is not None})
        fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharex=True)
        panels = [
            ("M", "accumulator M", axes[0][0]),
            ("psi", "correction Psi", axes[0][1]),
            ("weight_raw", "raw weight w", axes[1][0]),
            ("weight_effective", "effective weight w_eff", axes[1][1]),
        ]
        for col, title, ax in panels:
            for address in malicious:
                series = sorted(
                    ((i(r["epoch"]), f(r.get(col))) for r in rows
                     if r["address"] == address and f(r.get(col)) is not None),
                    key=lambda t: t[0],
                )
                if series:
                    ax.plot([e for e, _ in series], [v for _, v in series],
                            marker="o", ms=3, color=colours[address], label=short(address))
            for e in action_epochs:
                ax.axvline(e, color="#999999", lw=0.6, ls=":", alpha=0.7)
            ax.set_title(title)
            ax.grid(alpha=0.25)
        axes[0][0].legend(fontsize=7)
        axes[1][0].set_xlabel("epoch")
        axes[1][1].set_xlabel("epoch")
        fig.suptitle("Malus state trajectory for the malicious miners "
                     "(dotted lines: epochs with a confirmed malicious action)")
        self.record(finish(
            fig, path,
            "M is the decaying severity, Psi = max(0, 1 - M/M_max) the correction, and "
            "w_eff = round(w * Psi) the weight the election consumes. Dotted verticals mark "
            "epochs in which a malicious action confirmed.",
        ))

    def plot_malus_latency(self) -> None:
        path = self.out / "malus_detection_latency.png"
        det = [f(r.get("detection_latency_blocks")) for r in self.malus_actions
               if b(r.get("reported")) and f(r.get("detection_latency_blocks")) is not None]
        act = [f(r.get("activation_latency_epochs")) for r in self.malus_actions
               if f(r.get("activation_latency_epochs")) is not None]
        if not det and not act:
            self.record(empty(path, "Malus detection latency",
                              "no confirmed malicious action was detected, so there is no "
                              "latency to plot"))
            return
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
        for ax, data, title, unit, colour in (
            (ax1, det, "detection latency", "blocks", PALETTE[0]),
            (ax2, act, "activation latency", "epochs", PALETTE[2]),
        ):
            if data:
                xs = sorted(data)
                ys = [(k + 1) / len(xs) for k in range(len(xs))]
                ax.step(xs, ys, where="post", color=colour, lw=1.8)
                ax.scatter(xs, ys, s=18, color=colour)
                ax.set_ylim(0, 1.05)
            else:
                ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes)
            ax.set_xlabel("%s (%s)" % (title, unit))
            ax.set_ylabel("ECDF")
            ax.set_title(title)
            ax.grid(alpha=0.25)
        fig.suptitle("Detection latency (confirmation → first report) and activation latency")
        self.record(finish(
            fig, path,
            "Detection latency is measured in blocks from an action's confirmation to its "
            "first report; activation latency in epochs (the protocol applies a proved "
            "malus from the epoch after the offence, so 1 is the minimum).",
        ))

    def plot_malus_weight_effect(self) -> None:
        path = self.out / "malus_weight_effect.png"
        rows = [r for r in self.malus_weight_effect if f(r.get("rel_change_w_eff")) is not None]
        if not rows:
            self.record(empty(path, "Malus effect on effective weight",
                              "no validator had an effective-weight trajectory to compare"))
            return
        groups = {"malicious": [], "honest": []}
        for r in rows:
            key = "malicious" if b(r.get("is_malicious")) is True else "honest"
            groups[key].append(f(r["rel_change_w_eff"]))
        fig, ax = plt.subplots(figsize=FIGSIZE)
        positions = {"malicious": 1, "honest": 2}
        colours = {"malicious": PALETTE[1], "honest": PALETTE[2]}
        for name, pos in positions.items():
            values = groups[name]
            if not values:
                continue
            # Transparent individual trajectories jittered around the group position.
            jitter = [pos + (h % 7 - 3) * 0.03 for h in range(len(values))]
            ax.scatter(jitter, values, color=colours[name], alpha=0.35, s=30)
            med = sorted(values)[len(values) // 2]
            q1 = sorted(values)[len(values) // 4]
            q3 = sorted(values)[(3 * len(values)) // 4]
            ax.plot([pos - 0.2, pos + 0.2], [med, med], color=colours[name], lw=2.4)
            ax.plot([pos, pos], [q1, q3], color=colours[name], lw=1.2)
        ax.axhline(0.0, color="black", lw=1.0, ls="--")
        ax.set_xticks(list(positions.values()))
        ax.set_xticklabels(["malicious (n=%d)" % len(groups["malicious"]),
                            "honest (n=%d)" % len(groups["honest"])])
        ax.set_ylabel("relative change in effective weight (first → last epoch)")
        ax.set_title("Effect of the malus on effective weight: malicious vs honest")
        ax.grid(axis="y", alpha=0.25)
        self.record(finish(
            fig, path,
            "Thick bar: group median; thin bar: IQR; points: individual validators "
            "(transparent). The matched-by-band comparison is in "
            "phase3/malus_effectiveness.md.",
        ))

    def plot_malus_invariant_audit(self) -> None:
        path = self.out / "malus_invariant_audit.png"
        rows = [r for r in self.malus_invariants if i(r.get("epoch")) is not None]
        if not rows:
            self.record(empty(path, "Malus invariant audit",
                              "no malus state was sampled, so there is nothing to audit"))
            return
        epochs = sorted({i(r["epoch"]) for r in rows})
        validators = sorted({r["address"] for r in rows})
        checks = ["invariant_psi_in_unit", "invariant_weff_matches", "invariant_clean_psi_one"]

        def cell_ok(e: int, v: str) -> Optional[bool]:
            entry = next((r for r in rows if i(r["epoch"]) == e and r["address"] == v), None)
            if entry is None:
                return None
            oks = [b(entry.get(c)) for c in checks]
            if any(o is False for o in oks):
                return False
            if all(o is True for o in oks):
                return True
            return None

        # 1 = all invariants hold (green), 0 = a violation (red), 0.5 = not evaluable.
        grid = []
        violations = 0
        for v in validators:
            row = []
            for e in epochs:
                ok = cell_ok(e, v)
                row.append(1.0 if ok is True else (0.0 if ok is False else 0.5))
                if ok is False:
                    violations += 1
            grid.append(row)
        from matplotlib.colors import ListedColormap  # local: only this plot needs it
        cmap = ListedColormap(["#c0392b", "#dddddd", "#2ecc71"])
        fig, ax = plt.subplots(figsize=(max(8, len(epochs) * 0.5), max(4, len(validators) * 0.5)))
        ax.imshow(grid, aspect="auto", cmap=cmap, vmin=0.0, vmax=1.0)
        ax.set_xticks(range(len(epochs)))
        ax.set_xticklabels(epochs, fontsize=7)
        ax.set_yticks(range(len(validators)))
        ax.set_yticklabels([short(v) for v in validators], fontsize=7)
        ax.set_xlabel("epoch")
        ax.set_ylabel("validator")
        ax.set_title("Malus invariants per (epoch, validator): green = hold, red = violated")
        self.record(finish(
            fig, path,
            "Invariants: Psi in [0,1]; w_eff = round(w * Psi); and no proved malus => "
            "Psi = 1. %d violation(s) across %d cells." % (violations, len(epochs) * len(validators)),
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
        # Weight <-> election diagnostics.
        self.plot_pvalue_uniformity()
        self.plot_wilson_violation_heatmap()
        self.plot_residual_boxplot()
        # The malicious-miner experiment.
        self.plot_malus_funnel()
        self.plot_malus_trajectory()
        self.plot_malus_latency()
        self.plot_malus_weight_effect()
        self.plot_malus_invariant_audit()

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
