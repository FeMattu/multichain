#!/usr/bin/env python3
# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# plots.py — static figures for a recorded functional run.
# =============================================================================
# we_stats.py answers the statistical questions and writes the tables. This module
# draws them. It is deliberately a SEPARATE module and a separate dependency:
#
#   * we_stats.py is standard-library ONLY, on purpose, so that it runs on a bare node
#     host where numpy/scipy/matplotlib are not installed. That property is worth more
#     than the convenience of one module, so plotting must not be able to take the
#     analysis down with it.
#   * therefore a MISSING MATPLOTLIB IS NOT A FAILURE HERE. This module reports that it
#     cannot draw and exits 0. A run whose statistics passed must not be failed by the
#     absence of a drawing library — the verdicts live in report.md either way.
#
# Every figure is a file on disk. No interactivity, no display backend: the Agg backend
# is forced before pyplot is imported, because importing pyplot on a host with no DISPLAY
# picks an interactive backend and fails at figure creation rather than at import, which
# is a far more confusing error.
#
# Inputs, all optional — whatever is present is drawn, and anything missing is reported
# as skipped rather than invented:
#
#   weights.csv       epoch, address, weight          (raw, per epoch)
#   gas.csv           epoch, node, role, balance      (raw, per epoch)
#   distribution.csv  address, weight_share, observed_share, ci95_low, ci95_high, …
#   epoch_stats.csv   epoch, weight_cv, weight_gini, validators, …
#   restitution.csv   epoch, node, role, address, amount, txid   (raw, per epoch)
#   malus.csv         epoch, address, kind, family, points        (raw, per epoch)
#
# Output: <run-dir>/plots/*.png, plus a plots/README.md naming what each one shows and
# which table it came from — so a figure is never separated from its provenance.
#
# Usage:
#   plots.py <run-dir>
#   plots.py <run-dir> --format svg
#
# Exit code: 0 when the figures were drawn OR matplotlib is unavailable; 1 only if the
# run directory itself is unreadable.

from __future__ import annotations

import argparse
import csv
import os
import sys

# The palette is fixed rather than left to the library default so that the same validator
# keeps the same colour across figures in one run, and across runs with the same roles.
ROLE_COLOURS = {
    "admin": "#4c72b0",
    "miner": "#dd8452",
    "company": "#55a868",
    "ca": "#c44e52",
    "?": "#8c8c8c",
}

FAMILY_COLOURS = {
    "behavioural": "#dd8452",
    "data-integrity": "#4c72b0",
}


def _read(path):
    """Rows of a CSV as dicts, or [] when the file is absent or empty.

    Absence is ordinary: a run that recorded no malus has no malus.csv, and that must
    read as "nothing to draw" rather than as an error.
    """
    if not os.path.isfile(path):
        return []
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            return [r for r in csv.DictReader(fh)]
    except OSError:
        return []


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _short(address, n=8):
    """Addresses are 34 characters and unreadable on an axis; the first n disambiguate."""
    return address[:n] if address else "?"


def _finish(plt, fig, path, title, note=None):
    fig.suptitle(title, fontsize=11)
    if note:
        fig.text(0.5, 0.005, note, ha="center", fontsize=7, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return os.path.basename(path)


# ---------------------------------------------------------------------------
# The figures
# ---------------------------------------------------------------------------

def _weights_over_time(plt, run, out, fmt):
    """w_k per cluster per epoch — the trajectory the feedback is supposed to move.

    One line per validator. This is the figure that shows whether the restitution
    feedback did anything at all: under a uniform scaling every line moves together, and
    the lines only SEPARATE if rho differed between clusters.
    """
    rows = _read(os.path.join(run, "weights.csv"))
    if not rows:
        return None
    series = {}
    for r in rows:
        series.setdefault(r.get("address", "?"), []).append(
            (_num(r.get("epoch")), _num(r.get("weight")))
        )
    if not series:
        return None
    fig, ax = plt.subplots(figsize=(9, 5))
    for addr in sorted(series):
        pts = sorted(series[addr])
        ax.plot([p[0] for p in pts], [p[1] for p in pts],
                marker="o", markersize=3, linewidth=1.2, label=_short(addr))
    ax.set_xlabel("epoch")
    ax.set_ylabel("published weight $w_k$")
    ax.grid(alpha=0.3)
    if len(series) <= 14:
        ax.legend(fontsize=7, ncol=2)
    path = os.path.join(out, "weights_over_time.%s" % fmt)
    return _finish(plt, fig, path, "Published weight per cluster, by epoch",
                   "source: weights.csv (getallweights, sampled once per epoch)")


def _election_share_vs_weight(plt, run, out, fmt):
    """Observed election share against the share w_k/W_tot predicts, with 95% CIs.

    This is the mandate's explicit comparison, and the CI is what makes it readable: a
    bar that misses the diagonal by less than its own interval is sampling noise, not a
    finding. Drawing it without the interval would invite exactly the wrong reading.
    """
    rows = _read(os.path.join(run, "distribution.csv"))
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: -_num(r.get("weight_share")))
    labels = [_short(r.get("address")) for r in rows]
    expected = [_num(r.get("weight_share")) * 100 for r in rows]
    observed = [_num(r.get("observed_share")) * 100 for r in rows]
    lo = [max(0.0, o - _num(r.get("ci95_low")) * 100) for o, r in zip(observed, rows)]
    hi = [max(0.0, _num(r.get("ci95_high")) * 100 - o) for o, r in zip(observed, rows)]

    idx = list(range(len(rows)))
    width = 0.38
    fig, ax = plt.subplots(figsize=(max(7, len(rows) * 0.9), 5))
    ax.bar([i - width / 2 for i in idx], expected, width,
           label="expected ($w_k/W_{tot}$)", color="#8c8c8c")
    ax.bar([i + width / 2 for i in idx], observed, width,
           yerr=[lo, hi], capsize=3, label="observed", color="#4c72b0")
    ax.set_xticks(idx)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("share of proposals (%)")
    ax.grid(alpha=0.3, axis="y")
    ax.legend(fontsize=8)
    path = os.path.join(out, "election_share_vs_weight.%s" % fmt)
    return _finish(plt, fig, path,
                   "Observed election share vs the share the weight predicts",
                   "source: distribution.csv; error bars are 95% Wilson score intervals")


def _gas_by_role(plt, run, out, fmt):
    """Native balance per epoch, one panel per role.

    Split by role rather than pooled, because the roles have opposite expected shapes and
    pooling them hides both: a miner's balance should climb on fees, a company's should
    fall and be stepped back up by refuels, and the admin's should fall monotonically.
    Pooled on one axis the admin's premine flattens everything else to a line at zero.
    """
    rows = _read(os.path.join(run, "gas.csv"))
    if not rows:
        return None
    by_role = {}
    for r in rows:
        role = r.get("role", "?") or "?"
        by_role.setdefault(role, {}).setdefault(r.get("node", "?"), []).append(
            (_num(r.get("epoch")), _num(r.get("balance")))
        )
    roles = [r for r in ("admin", "miner", "company", "ca") if r in by_role]
    roles += [r for r in sorted(by_role) if r not in roles]
    if not roles:
        return None
    fig, axes = plt.subplots(1, len(roles), figsize=(4.2 * len(roles), 4), squeeze=False)
    for ax, role in zip(axes[0], roles):
        colour = ROLE_COLOURS.get(role, "#8c8c8c")
        for node in sorted(by_role[role], key=lambda v: _num(v, 0)):
            pts = sorted(by_role[role][node])
            ax.plot([p[0] for p in pts], [p[1] for p in pts],
                    linewidth=1.0, alpha=0.75, color=colour)
        ax.set_title("%s  (n=%d)" % (role, len(by_role[role])), fontsize=9)
        ax.set_xlabel("epoch")
        ax.grid(alpha=0.3)
    axes[0][0].set_ylabel("native balance (GAS)")
    path = os.path.join(out, "gas_by_role.%s" % fmt)
    return _finish(plt, fig, path, "GAS balance trajectory, by role",
                   "source: gas.csv (getbalance on every node, once per epoch)")


def _weight_dispersion(plt, run, out, fmt):
    """Per-epoch dispersion of the weight vector: CV and Gini on one axis.

    Two measures because they disagree usefully. The CV moves with a single outlier; the
    Gini moves with the whole distribution. Both flat means the weights are not
    responding to anything, which is the inert-feedback signature.
    """
    rows = _read(os.path.join(run, "epoch_stats.csv"))
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: _num(r.get("epoch")))
    epochs = [_num(r.get("epoch")) for r in rows]
    cv = [_num(r.get("weight_cv")) for r in rows]
    gini = [_num(r.get("weight_gini")) for r in rows]
    if not epochs:
        return None
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(epochs, cv, marker="o", markersize=3, linewidth=1.2,
            label="coefficient of variation", color="#4c72b0")
    ax.plot(epochs, gini, marker="s", markersize=3, linewidth=1.2,
            label="Gini", color="#dd8452")
    ax.set_xlabel("epoch")
    ax.set_ylabel("dispersion of the weight vector")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    path = os.path.join(out, "weight_dispersion.%s" % fmt)
    return _finish(plt, fig, path, "Weight dispersion across clusters, by epoch",
                   "source: epoch_stats.csv")


def _restitution_over_time(plt, run, out, fmt):
    """R_k per miner per epoch — the input side of the feedback.

    Paired with weights_over_time, this is what makes a claim about the feedback
    falsifiable: R_k moving while w_k does not is a broken pipeline, and both flat is an
    inert one. Drawn from the restitution transfers the harness issued and verified
    on-chain, since NO RPC EXPOSES R_k (weightverifyweights returns published,
    published_epoch, recomputed and verdict, and nothing else).
    """
    rows = _read(os.path.join(run, "restitution.csv"))
    if not rows:
        return None
    series = {}
    for r in rows:
        key = r.get("address") or r.get("node") or "?"
        e = _num(r.get("epoch"))
        series.setdefault(key, {})
        series[key][e] = series[key].get(e, 0.0) + _num(r.get("amount"))
    if not series:
        return None
    fig, ax = plt.subplots(figsize=(9, 5))
    for key in sorted(series):
        pts = sorted(series[key].items())
        ax.plot([p[0] for p in pts], [p[1] for p in pts],
                marker="o", markersize=3, linewidth=1.2, label=_short(key))
    ax.set_xlabel("epoch")
    ax.set_ylabel("$R_k$ — GAS returned to the treasury")
    ax.grid(alpha=0.3)
    if len(series) <= 14:
        ax.legend(fontsize=7, ncol=2)
    path = os.path.join(out, "restitution_over_time.%s" % fmt)
    return _finish(plt, fig, path, "Restitution to the treasury per miner, by epoch",
                   "source: restitution.csv (miner -> treasury transfers, chain-verified)")


def _malus_by_family(plt, run, out, fmt):
    """Malus counts per kind, coloured by family.

    Drawn even when every count is zero, and that is the point: on an honest run the
    expected figure is an empty one, and an empty bar chart with all four kinds named is
    a much stronger statement than a missing file. The four kinds are always shown, so a
    kind that is never reported is visibly zero rather than absent.
    """
    rows = _read(os.path.join(run, "malus.csv"))
    kinds = [("equiv", "behavioural"), ("delay", "behavioural"),
             ("selfwrite", "data-integrity"), ("badweight", "data-integrity")]
    counts = {k: 0 for k, _ in kinds}
    for r in rows:
        k = (r.get("kind") or "").strip()
        if k in counts:
            counts[k] += 1
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar([k for k, _ in kinds], [counts[k] for k, _ in kinds],
           color=[FAMILY_COLOURS[f] for _, f in kinds])
    ax.set_ylabel("malus records accepted")
    ax.grid(alpha=0.3, axis="y")
    total = sum(counts.values())
    if total == 0:
        ax.set_ylim(0, 1)
        ax.text(0.5, 0.5, "no malus recorded — the expected result on an honest run",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=9, color="#555555")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in FAMILY_COLOURS.values()]
    ax.legend(handles, list(FAMILY_COLOURS), fontsize=8, title="family", title_fontsize=8)
    path = os.path.join(out, "malus_by_family.%s" % fmt)
    return _finish(plt, fig, path, "Malus records by kind and family",
                   "source: malus.csv; all four kinds are shown even at zero")


FIGURES = [
    ("weights_over_time", _weights_over_time,
     "w_k per cluster per epoch", "weights.csv"),
    ("election_share_vs_weight", _election_share_vs_weight,
     "observed vs expected election share, 95% Wilson CIs", "distribution.csv"),
    ("gas_by_role", _gas_by_role,
     "native balance trajectory, one panel per role", "gas.csv"),
    ("weight_dispersion", _weight_dispersion,
     "per-epoch CV and Gini of the weight vector", "epoch_stats.csv"),
    ("restitution_over_time", _restitution_over_time,
     "R_k per miner per epoch", "restitution.csv"),
    ("malus_by_family", _malus_by_family,
     "malus records by kind, coloured by family", "malus.csv"),
]


def generate(run_dir, fmt="png"):
    """Draw every figure whose input is present. Returns (drawn, skipped, reason)."""
    try:
        import matplotlib
        matplotlib.use("Agg")           # BEFORE pyplot: see the module header
        import matplotlib.pyplot as plt
    except Exception as exc:            # ImportError, and backend failures too
        return [], [name for name, _, _, _ in FIGURES], \
            "matplotlib is not available (%s)" % exc

    out = os.path.join(run_dir, "plots")
    try:
        os.makedirs(out, exist_ok=True)
    except OSError as exc:
        return [], [name for name, _, _, _ in FIGURES], "cannot create %s (%s)" % (out, exc)

    drawn, skipped = [], []
    for name, fn, _desc, source in FIGURES:
        try:
            produced = fn(plt, run_dir, out, fmt)
        except Exception as exc:
            # One figure that cannot be drawn must not cost the others. The reason is
            # reported rather than swallowed.
            skipped.append("%s (%s: %s)" % (name, type(exc).__name__, exc))
            continue
        if produced:
            drawn.append(produced)
        else:
            skipped.append("%s (no %s)" % (name, source))

    _write_index(out, drawn, skipped)
    return drawn, skipped, None


def _write_index(out, drawn, skipped):
    """A figure separated from its provenance is not evidence, so each one is named."""
    lines = ["# Figures", "",
             "Generated by `test/functional/lib/stats/plots.py` from the recorded run's",
             "tables. Re-runnable at any time without a network:", "",
             "```bash",
             "python3 test/functional/lib/stats/plots.py test/output/<run>",
             "```", ""]
    if drawn:
        lines += ["| figure | shows | source table |", "|---|---|---|"]
        by_file = {name: (desc, src) for name, _, desc, src in FIGURES}
        for f in drawn:
            stem = os.path.splitext(f)[0]
            desc, src = by_file.get(stem, ("", ""))
            lines.append("| `%s` | %s | `%s` |" % (f, desc, src))
        lines.append("")
    if skipped:
        lines += ["**Not drawn** (input absent — declared, not invented):", ""]
        lines += ["* %s" % s for s in skipped]
        lines.append("")
    try:
        with open(os.path.join(out, "README.md"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser(description="Draw the figures for a recorded run.")
    ap.add_argument("run_dir")
    ap.add_argument("--format", default="png", choices=("png", "svg"))
    args = ap.parse_args()

    if not os.path.isdir(args.run_dir):
        sys.stderr.write("no such run directory: %s\n" % args.run_dir)
        return 1

    drawn, skipped, reason = generate(args.run_dir, args.format)
    if reason:
        # NOT a failure: we_stats.py is standard-library only by design, and a host
        # without matplotlib must still be able to run and pass the analysis.
        print("plots: skipped — %s" % reason)
        print("plots: the statistical verdicts are unaffected; see report.md")
        return 0
    for f in drawn:
        print("plots: %s" % os.path.join(args.run_dir, "plots", f))
    for s in skipped:
        print("plots: skipped %s" % s)
    print("plots: %d figure(s) written to %s" % (len(drawn), os.path.join(args.run_dir, "plots")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
