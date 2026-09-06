#!/usr/bin/env python3
"""Render sections A, B and C of the per-experiment report from the phase-3 sheets.

Usage:
    python3 tools/pipeline/make_report.py <experiment_dir> [<experiment_dir> ...] [--force]

An <experiment_dir> is a directory such as ``risultati/run6-tbt-10s/regionale`` that
contains ``phase3/``.  The script writes ``<experiment_dir>/report.md`` holding the
header (A), the per-epoch per-validator detail (B) and the per-epoch trend (C),
followed by the two anchors ``<!-- D -->`` and ``<!-- E -->`` that a human (or the
model driving this prompt) fills in.

The script only *formats* what phase 3 already computed.  The single arithmetic it
performs is the ratio ``n_recompute_match / n_clusters`` of one and the same row,
explicitly allowed by the report specification.
"""

import argparse
import csv
import json
import os
import sys

# --------------------------------------------------------------------------- #
# formatting helpers
# --------------------------------------------------------------------------- #

DASH = "—"          # em dash
NDASH = "–"         # en dash, used inside height ranges

GOF_METHOD_SHORT = {
    "chi2_asymptotic": "chi2",
    "exact_multinomial_enumeration": "exact",
    "monte_carlo_multinomial": "mc",
}


def num(value):
    """Parse a CSV cell (or a manifest value) into a float, or None when it is absent."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    value = str(value).strip()
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def integer(value):
    v = num(value)
    return None if v is None else int(round(v))


def f3(value):
    """Probabilities and shares: 3 decimals."""
    v = num(value)
    return DASH if v is None else "%.3f" % v


def f2(value):
    """Indices such as N_eff, and seconds: 2 decimals."""
    v = num(value)
    return DASH if v is None else "%.2f" % v


def fp(value):
    """p-values: 3 significant digits, everything below 0.001 collapsed."""
    v = num(value)
    if v is None:
        return DASH
    if v < 0.001:
        return "< 0.001"
    return "%.3g" % v


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def epoch_key(row):
    """Sort key that keeps the pooled ``all`` row last."""
    e = row.get("epoch", "")
    return (1, 0) if e == "all" else (0, int(e))


# --------------------------------------------------------------------------- #
# section A
# --------------------------------------------------------------------------- #

def section_a(summary, epochs):
    measured = integer(summary.get("measured_epochs"))
    fully = integer(summary.get("fully_measured_epochs"))
    n_measured = integer(summary.get("n_measured_blocks"))
    final_height = integer(summary.get("final_height"))
    setup = integer(summary.get("setup_blocks"))
    malus_records = integer(summary.get("malus_registry_records"))

    epoch_range = "%d%s%d" % (epochs[0], NDASH, epochs[-1]) if epochs else DASH
    malus_state = "enabled" if str(summary.get("malus_enabled")).lower() == "true" else "disabled"

    lines = [
        "# %s / %s" % (summary["experiment_id"], summary["area"]),
        "",
        "| | |",
        "|---|---|",
        "| Target block time | %s s |" % integer(summary.get("target_block_time")),
        "| Damping function (dumpfunction) | %s |" % summary.get("dumpfunction"),
        "| Malus | %s, registry empty (%d records) |" % (malus_state, malus_records)
        if malus_records == 0 else
        "| Malus | %s, %d registry records |" % (malus_state, malus_records),
        "| Epoch length | %d blocks |" % integer(summary.get("weight_epoch_length")),
        "| Measured epochs | %d (%d fully measured), epochs %s |" % (measured, fully, epoch_range),
        "| Blocks | %d measured of %d total (setup %d), final height %d |"
        % (n_measured, final_height, setup, final_height),
        "| Sortition | delta %s, lambda %s, RANDAO lookback %s |"
        % (summary.get("wpoa_sortition_delta"), summary.get("wpoa_sortition_lambda"),
           summary.get("wpoa_randao_lookback")),
        "| Weight engine | kappa %s, alpha %s, lambda_w %s |"
        % (summary.get("weight_kappa"), summary.get("weight_alpha"), summary.get("weight_lambda")),
    ]
    return lines


# --------------------------------------------------------------------------- #
# section B
# --------------------------------------------------------------------------- #

def commentary(epoch, test, vals, liveness, gini_row, we_rows, pooled_inversion):
    """Build the 1-3 commentary lines below one epoch table, in priority order."""
    out = []

    # 1. goodness of fit rejected
    if integer(test.get("gof_reject_alpha05")) == 1:
        worst = max(vals, key=lambda r: num(r.get("abs_error_p")) or 0.0)
        out.append(
            "GoF rejected at alpha = 0.05 (`%s`, p = %s); the deviation is carried by %s, "
            "which won %d blocks against %s expected."
            % (test.get("gof_method"), fp(test.get("gof_p_value")), worst["validator_host"],
               integer(worst.get("O_i")), f2(worst.get("E_i")))
        )

    # 2. expected share outside the Wilson interval
    outside = [r for r in vals if integer(r.get("p_theoretical_inside_wilson95")) == 0]
    if outside:
        parts = ["%s (observed %s, CI [%s, %s], expected %s)"
                 % (r["validator_host"], f3(r.get("p_hat")), f3(r.get("wilson95_low")),
                    f3(r.get("wilson95_high")), f3(r.get("p_theoretical_blockweighted")))
                 for r in outside]
        out.append("Expected share outside the Wilson 95 %% CI for %s." % "; ".join(parts))

    # 3. validity: time bar violations and rejected blocks
    tbv = integer(test.get("time_bar_violations")) or 0
    rej = integer(test.get("n_rejects")) or 0
    if tbv > 0 or rej > 0:
        bits = []
        if tbv > 0:
            bits.append("%d time-bar violations" % tbv)
        if rej > 0:
            bits.append("%d rejected blocks (%s)" % (rej, test.get("rejects_by_reason")))
        out.append("Validity: %s." % ", ".join(bits))

    # 4. weight-engine integrity
    we_bits = []
    mismatch = integer(gini_row.get("n_recompute_mismatch")) if gini_row else None
    if mismatch:
        affected = [r for r in we_rows if integer(r.get("recompute_match")) == 0]
        detail = ", ".join("%s (implied raw delta over esg_miner %s)"
                           % (r["cluster_head_host"], r.get("implied_raw_delta_over_esg_miner"))
                           for r in affected)
        we_bits.append("%d of %s published weights were not reproduced by the independent "
                       "recomputation: %s" % (mismatch, gini_row.get("n_clusters"), detail))
    failed = integer(gini_row.get("n_hosts_verification_failed_log")) if gini_row else None
    if failed:
        we_bits.append("%d nodes logged a failed independent verification" % failed)
    if we_bits:
        out.append("Weight engine: %s." % "; ".join(we_bits))

    # 5. inversion rate well above the pooled rate
    rate = num(test.get("inversion_rate"))
    if rate is not None and pooled_inversion and rate >= 1.5 * pooled_inversion:
        out.append(
            "Inversion rate %s against a pooled %s for the run (%s x); %s of the inverted "
            "rounds coincided with a competing block."
            % (f3(rate), f3(pooled_inversion), f2(rate / pooled_inversion),
               integer(test.get("inversion_with_fork_n")))
        )

    # 6. consecutive-win streak above the Monte Carlo of the sortition alone
    lmax_p = num(test.get("L_max_mc_p_value"))
    rep_p = num(test.get("repeat_prob_mc_p_value"))
    streak_bits = []
    if lmax_p is not None and lmax_p < 0.05:
        streak_bits.append("longest streak %s blocks against a Monte Carlo mean of %s (p = %s)"
                           % (integer(test.get("L_max_observed")), f2(test.get("L_max_mc_mean")),
                              fp(lmax_p)))
    if rep_p is not None and rep_p < 0.05:
        streak_bits.append("repeat probability %s against a Monte Carlo mean of %s (p = %s)"
                           % (f3(test.get("repeat_prob_observed")),
                              f3(test.get("repeat_prob_mc_mean")), fp(rep_p)))
    if streak_bits:
        out.append("Streaks: %s." % "; ".join(streak_bits))

    # 7. a validator that lost most of the rounds it should have won
    for r in liveness:
        argmin = integer(r.get("n_rounds_theoretical_argmin")) or 0
        rate_missed = num(r.get("MissedTurnRate"))
        if argmin >= 3 and rate_missed is not None and rate_missed >= 0.5:
            out.append("%s lost %d of the %d rounds in which it held the smallest delay "
                       "(MissedTurnRate %s)."
                       % (r["validator_host"], integer(r.get("n_rounds_theoretical_argmin_lost")),
                          argmin, f3(rate_missed)))

    if not out:
        return ["Compatible with the expectation, no relevant deviation."]
    return out[:3]


def section_b(epochs, tests_by_epoch, vals_by_epoch, live_by_epoch,
              gini_by_epoch, we_by_epoch, epoch_length, pooled_inversion):
    lines = ["## Epoch by epoch, per validator", ""]
    for e in epochs:
        test = tests_by_epoch.get(e, {})
        vals = vals_by_epoch.get(e, [])
        we_rows = we_by_epoch.get(e, [])

        n_blocks = integer(test.get("n_blocks"))
        if we_rows and num(we_rows[0].get("epoch_start_height")) is not None:
            h0 = integer(we_rows[0]["epoch_start_height"])
            h1 = integer(we_rows[0]["epoch_end_height"])
        else:
            h0, h1 = (e - 1) * epoch_length, e * epoch_length - 1
        buried = "buried" if integer(test.get("epoch_buried")) == 1 else "not buried"

        heading = "#### Epoch %d %s %d blocks, heights %d%s%d, %s" % (
            e, DASH, n_blocks, h0, NDASH, h1, buried)
        if integer(test.get("share_changes_within_epoch")) == 1:
            heading += " %s weights changed inside the epoch" % DASH

        lines += [heading, "", "| node | p_expected | p_observed | verdict |", "|---|---|---|---|"]
        for r in vals:
            inside = integer(r.get("p_theoretical_inside_wilson95")) == 1
            verdict = "expected %s Wilson 95 %% CI [%s, %s]" % (
                "inside" if inside else "OUTSIDE",
                f3(r.get("wilson95_low")), f3(r.get("wilson95_high")))
            lines.append("| %s | %s | %s | %s |" % (
                r["validator_host"], f3(r.get("p_theoretical_blockweighted")),
                f3(r.get("p_hat")), verdict))
        lines.append("")
        lines += commentary(e, test, vals, live_by_epoch.get(e, []),
                            gini_by_epoch.get(e), we_rows, pooled_inversion)
        lines.append("")
    return lines


# --------------------------------------------------------------------------- #
# section C
# --------------------------------------------------------------------------- #

def section_c(epochs, tests_by_epoch, gini_by_epoch, gini_epochs, setup_blocks):
    lines = [
        "## Trend by epoch",
        "",
        "| epoch | blocks | GoF p (method) | HHI | N_eff | Nakamoto ½ | timer race KS p "
        "| inversion rate | block success | WE conformity |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for e in epochs:
        t = tests_by_epoch.get(e, {})
        method = GOF_METHOD_SHORT.get(t.get("gof_method"), t.get("gof_method") or DASH)
        star = "*" if integer(t.get("gof_reject_alpha05")) == 1 else ""
        gof = "%s%s (%s)" % (fp(t.get("gof_p_value")), star, method)

        g = gini_by_epoch.get(e)
        if g is None or integer(g.get("n_recompute_match")) is None or integer(g.get("n_clusters")) is None:
            conformity = DASH
        else:
            conformity = "%d/%d" % (integer(g["n_recompute_match"]), integer(g["n_clusters"]))

        lines.append("| %d | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            e, integer(t.get("n_blocks")), gof,
            f3(t.get("p_hat_HHI")), f2(t.get("p_hat_N_eff")),
            integer(t.get("p_hat_nakamoto_1_2")),
            fp(t.get("ks_mc_p")), f3(t.get("inversion_rate")),
            f3(t.get("BlockSuccessRate")), conformity))

    outside = sorted(set(gini_epochs) - set(epochs))
    lines.append("")
    if outside:
        listed = ", ".join(str(x) for x in outside)
        plural = len(outside) > 1
        lines.append(
            "%d weight-engine epoch%s fall%s outside the measured range (epoch%s %s): "
            "%s a setup epoch or the trailing partial epoch, not missing data."
            % (len(outside), "s" if plural else "", "" if plural else "s",
               "s" if plural else "", listed, "they are" if plural else "it is"))
    else:
        lines.append("Every weight-engine epoch falls inside the measured range.")

    # a cluster that published no weight lowers the ratio by absence, not by mismatch
    partial = []
    for e in epochs:
        g = gini_by_epoch.get(e)
        if g is None:
            continue
        n_pub, n_cl = integer(g.get("n_published")), integer(g.get("n_clusters"))
        if n_pub is not None and n_cl is not None and n_pub < n_cl:
            partial.append((e, n_cl - n_pub, n_cl))
    if partial:
        listed = ", ".join("epoch %d (%d of %d)" % (e, k, n) for e, k, n in partial)
        lines.append(
            "Clusters that published no weight at all, and therefore lower the conformity ratio "
            "by absence rather than by mismatch: %s." % listed)
    return lines


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #

def render(exp_dir):
    p3 = os.path.join(exp_dir, "phase3")
    manifest_path = os.path.join(p3, "manifest.json")
    with open(manifest_path, encoding="utf-8") as handle:
        summary = json.load(handle)["summary"]

    tests = read_csv(os.path.join(p3, "wpoa_epoch_tests.csv"))
    vals = read_csv(os.path.join(p3, "wpoa_epoch_validators.csv"))
    live = read_csv(os.path.join(p3, "wpoa_epoch_liveness_validators.csv"))
    gini = read_csv(os.path.join(p3, "weight_engine_gini.csv"))
    we = read_csv(os.path.join(p3, "weight_engine_epoch.csv"))

    tests_by_epoch = {int(r["epoch"]): r for r in tests if r["epoch"] != "all"}
    pooled_test = next((r for r in tests if r["epoch"] == "all"), {})
    pooled_inversion = num(pooled_test.get("inversion_rate"))

    epochs = sorted(tests_by_epoch)
    epoch_length = integer(summary.get("weight_epoch_length"))

    vals_by_epoch, live_by_epoch, we_by_epoch = {}, {}, {}
    for r in vals:
        if r["epoch"] != "all":
            vals_by_epoch.setdefault(int(r["epoch"]), []).append(r)
    for r in live:
        if r["epoch"] != "all":
            live_by_epoch.setdefault(int(r["epoch"]), []).append(r)
    for r in we:
        we_by_epoch.setdefault(int(r["epoch"]), []).append(r)
    # the sheets are not ordered by host; sort so every report lines up row by row
    for bucket, key in ((vals_by_epoch, "validator_host"), (live_by_epoch, "validator_host"),
                        (we_by_epoch, "cluster_head_host")):
        for rows in bucket.values():
            rows.sort(key=lambda r: r[key])
    gini_by_epoch = {int(r["epoch"]): r for r in gini}

    body = []
    body += section_a(summary, epochs)
    body += ["", ""]
    body += section_b(epochs, tests_by_epoch, vals_by_epoch, live_by_epoch,
                      gini_by_epoch, we_by_epoch, epoch_length, pooled_inversion)
    body += [""]
    body += section_c(epochs, tests_by_epoch, gini_by_epoch, sorted(gini_by_epoch),
                      integer(summary.get("setup_blocks")))
    body += ["", "", "## How the system behaved", "", "<!-- D -->", "",
             "", "## Notable facts and anomalies", "", "<!-- E -->", ""]
    return "\n".join(body) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("experiments", nargs="+")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing report.md")
    args = ap.parse_args()

    for exp_dir in args.experiments:
        exp_dir = exp_dir.rstrip("/")
        out = os.path.join(exp_dir, "report.md")
        if os.path.exists(out) and not args.force:
            print("skip (report.md exists): %s" % out)
            continue
        if not os.path.exists(os.path.join(exp_dir, "phase3", "manifest.json")):
            print("skip (no phase3/manifest.json): %s" % exp_dir, file=sys.stderr)
            continue
        with open(out, "w", encoding="utf-8") as handle:
            handle.write(render(exp_dir))
        print("written: %s" % out)


if __name__ == "__main__":
    main()
