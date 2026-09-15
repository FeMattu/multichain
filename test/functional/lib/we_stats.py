#!/usr/bin/env python3
# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# we_stats.py — statistical analysis for the functional runs.
# =============================================================================
# Turns the raw per-epoch snapshots a functional suite records into the statistics a
# thesis chapter needs: a Monte Carlo validation of the election algorithm, a chi-square
# on the proposers the run actually produced, concentration and fairness measures, and
# per-epoch time series for the weight, gas and verification pipelines.
#
# WHY BOTH A MONTE CARLO AND AN EMPIRICAL TEST, since they look like the same test twice.
# They answer different questions, and neither is sufficient alone:
#
#   * the EMPIRICAL chi-square asks "did THIS BINARY, on THIS RUN, elect proposers in
#     proportion to their weights?". It tests the compiled selector, the VRF, the beacon
#     and the weight pipeline end to end -- but its sample is however many blocks the run
#     mined, which for a skewed weight vector is far too small to say anything about the
#     light validators. A 5000-block run gives a 1%-weight validator an expectation of
#     50 blocks; a 0.1% validator gets 5, and the test is powerless on it.
#   * the MONTE CARLO asks "is the FORMULA right?". It re-implements the
#     Efraimidis-Spirakis transformation from wpoa_selector.h in Python and draws it as
#     many times as asked, so the sample size is a parameter rather than an accident.
#     It cannot catch a bug in the C++ -- it is not running the C++ -- but it is the only
#     way to test the tail of a skewed weight vector at all.
#
# Together: the Monte Carlo says the algorithm is sound at any sample size, the empirical
# test says the implementation matches it on the sample available. A disagreement between
# them localises the fault to the implementation rather than the design.
#
# Sole dependency is the standard library, matching analyze_distribution.py. No numpy or
# scipy: the chi-square p-values come from a regularised incomplete gamma implemented
# below, which is exact enough for the degrees of freedom involved and keeps this
# runnable on a bare node host.
#
# Usage:
#   we_stats.py <run-dir>                 analyse a recorded run, write the report in place
#   we_stats.py <run-dir> --draws 200000  a larger Monte Carlo sample
#   we_stats.py --selfcheck               validate the statistics against known answers
#
# Inputs, all optional -- whatever is present is analysed:
#   meta.json        the run's parameters
#   proposers.csv    height,miner
#   weights.csv      epoch,address,weight
#   epochs.csv       epoch,height,verified_epoch,mismatch,not_a_cluster,other_epoch,...
#   gas.csv          epoch,node,role,balance
#   refuels.csv      epoch,node,role,before,after,amount,txid
#
# Outputs, in the same directory:
#   report.md        the readable report
#   summary.txt      the same verdicts as plain text
#   montecarlo.csv   one row per Monte Carlo scenario
#   distribution.csv one row per validator: weight, expected, observed, deviation
#   concentration.csv Gini / entropy / top-share, for weights and for proposals
#   epoch_stats.csv  per-epoch aggregates
#   gas_stats.csv    per-node gas trajectory summary
#
# Exit code: 0 if every statistical verdict passed, 1 otherwise. A run with no data to
# analyse is NOT a pass -- it exits 2, so an empty directory cannot be mistaken for
# success.

import argparse
import csv
import json
import math
import os
import random
import sys
from collections import Counter, defaultdict

TWO64 = 18446744073709551616.0      # 2^64, exact in double, as in the C++ source


# =============================================================================
# Statistics — chi-square without scipy
# =============================================================================

def _lower_gamma_reg(s, x):
    """Regularised lower incomplete gamma P(s, x), by series or continued fraction.

    The switch at x < s+1 is the standard one (Numerical Recipes 6.2): the series
    converges quickly below it, the continued fraction above.
    """
    if x < 0 or s <= 0:
        return float("nan")
    if x == 0:
        return 0.0
    if x < s + 1.0:
        # series
        ap, total, delta = s, 1.0 / s, 1.0 / s
        for _ in range(10000):
            ap += 1.0
            delta *= x / ap
            total += delta
            if abs(delta) < abs(total) * 1e-15:
                break
        return total * math.exp(-x + s * math.log(x) - math.lgamma(s))
    # continued fraction for Q(s,x), then P = 1 - Q
    tiny = 1e-300
    b, c, d = x + 1.0 - s, 1.0 / tiny, 1.0 / (x + 1.0 - s)
    h = d
    for i in range(1, 10000):
        an = -i * (i - s)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    q = math.exp(-x + s * math.log(x) - math.lgamma(s)) * h
    return 1.0 - q


def chi2_sf(chi2, df):
    """P(X > chi2) for X ~ chi-square with df degrees of freedom — the p-value."""
    if df <= 0:
        return float("nan")
    if chi2 <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - _lower_gamma_reg(df / 2.0, chi2 / 2.0)))


def chi2_gof(observed, expected):
    """Chi-square goodness of fit.

    Returns (chi2, df, p, usable_classes, dropped). Classes with an expectation below 5
    are EXCLUDED and counted: the chi-square approximation is not valid there, and
    silently including them is how a test comes to report a large statistic that means
    nothing. Reporting the count is what lets a reader see the test's real power.
    """
    chi2, used, dropped = 0.0, 0, 0
    for key in expected:
        e = expected[key]
        if e < 5.0:
            dropped += 1
            continue
        o = observed.get(key, 0)
        chi2 += (o - e) ** 2 / e
        used += 1
    df = used - 1
    if df < 1:
        return (chi2, 0, float("nan"), used, dropped)
    return (chi2, df, chi2_sf(chi2, df), used, dropped)


def gini(values):
    """Gini coefficient of a non-negative list. 0 = perfectly equal, ->1 = concentrated."""
    v = sorted(float(x) for x in values if x is not None)
    n = len(v)
    if n == 0 or sum(v) <= 0:
        return 0.0
    cum = sum((2 * i - n + 1) * x for i, x in enumerate(v))
    return cum / (n * sum(v))


def norm_entropy(counts):
    """Shannon entropy of a distribution, normalised to [0,1] against the uniform.

    1.0 means every participant proposed equally often; 0.0 means one took everything.
    Read ALONGSIDE the chi-square, never instead of it: under weighted selection the
    target is NOT uniformity, so a low value is expected when the weights are skewed.
    It is a description of concentration, not a verdict.
    """
    total = sum(counts)
    if total <= 0 or len(counts) <= 1:
        return 0.0
    h = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            h -= p * math.log(p)
    return h / math.log(len(counts))


def mean_stdev(values):
    v = [float(x) for x in values]
    n = len(v)
    if n == 0:
        return (0.0, 0.0)
    m = sum(v) / n
    if n < 2:
        return (m, 0.0)
    return (m, math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1)))


def wilson_interval(k, n, z=1.959963985):
    """Wilson score interval for a binomial proportion — the per-validator share bound.

    Preferred over the normal approximation because the shares here are often small and
    the counts modest, exactly where the normal interval misbehaves (and can run below
    zero).
    """
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


# =============================================================================
# The election algorithm, re-implemented from src/wpoa/wpoa_selector.h
# =============================================================================
# Line for line with the C++, deliberately: a paraphrase that happened to be equivalent
# would not be evidence of anything. The entropy is random.getrandbits(64) rather than a
# VRF output, which is precisely the test the design calls for -- Prop. 5.11 requires the
# VRF to be indistinguishable from uniform, so substituting a uniform source tests the
# algorithm ABOVE the randomness source.

def apply_dumping(weight, dump_function):
    """g(.) of Def. 5.9 — WPoASelector::ApplyDumping."""
    if dump_function == "sqrt":
        return math.sqrt(float(weight))
    if dump_function == "log":
        return math.log(1.0 + float(weight))
    return float(weight)


def score_from_entropy64(d, weight, dump_function="none"):
    """WPoASelector::ScoreFromEntropy64.

    u = (d+1)/2^64 in (0,1];  E = -ln(u) ~ Exp(1);  score = E / g(w).

    A zero weight returns +inf BEFORE any division, exactly as the source does: that is
    how Cor. 5.4 (a zero-weight candidate is never elected) holds by construction rather
    than by an explicit exclusion branch.
    """
    if weight == 0:
        return float("inf")
    u = (float(d) + 1.0) / TWO64
    return -math.log(u) / apply_dumping(weight, dump_function)


def select_proposer(rng, weights, dump_function="none"):
    """argmin of the score, ties broken on the lexicographically smaller address — the
    total order that makes the result independent of map iteration order."""
    best_addr, best_score = None, None
    for addr in sorted(weights):
        s = score_from_entropy64(rng.getrandbits(64), weights[addr], dump_function)
        if best_score is None or s < best_score or (s == best_score and addr < best_addr):
            best_addr, best_score = addr, s
    return best_addr


def monte_carlo(weights, draws, seed, dump_function="none"):
    """Draw `draws` elections and compare the frequencies with w_i / W_tot (Teor. 5.3)."""
    rng = random.Random(seed)
    counts = Counter()
    for _ in range(draws):
        counts[select_proposer(rng, weights, dump_function)] += 1
    total_w = sum(weights.values())
    expected = {a: draws * w / total_w for a, w in weights.items()} if total_w else {}
    chi2, df, p, used, dropped = chi2_gof(counts, expected)
    zero_selected = sum(counts[a] for a, w in weights.items() if w == 0)
    return {
        "counts": counts, "expected": expected, "chi2": chi2, "df": df, "p": p,
        "classes_used": used, "classes_dropped": dropped,
        "zero_weight_selections": zero_selected,
        "draws": draws, "seed": seed, "dump": dump_function,
    }


def static_scenarios():
    """Scenarios that hold regardless of any run, each testing something the empirical
    chi-square on a real run cannot."""
    return [
        ("uniform-3",
         {"n1": 100, "n2": 100, "n3": 100},
         "the degenerate case: with equal weights wPoA must reduce to an equiprobable draw"),
        ("skewed-95-4-1",
         {"n1": 95, "n2": 4, "n3": 1},
         "the case a real run cannot test: the smallest class only reaches a usable "
         "expectation with many draws"),
        ("zero-weight",
         {"n1": 60, "n2": 40, "n_zero": 0},
         "Cor. 5.4 directly: a zero-weight candidate must have EXACTLY zero selections, "
         "not merely few"),
        ("tie-plus-zero",
         {"n1": 50, "n2": 50, "n_zero": 0},
         "Cor. 5.4 still holds when the remaining candidates are indistinguishable"),
        ("long-tail-10",
         {("n%02d" % i): w for i, w in enumerate([500, 250, 120, 60, 30, 15, 8, 4, 2, 1])},
         "a decade of weights spanning 500:1, the shape a mature weight pipeline "
         "produces once the feedback has separated the clusters"),
    ]


# =============================================================================
# Reading a recorded run
# =============================================================================

def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _num(row, key, default=0.0):
    try:
        return float(row.get(key) or default)
    except (TypeError, ValueError):
        return default


def load_run(run_dir):
    run = {"dir": run_dir, "meta": {}}
    meta_path = os.path.join(run_dir, "meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, encoding="utf-8") as fh:
                run["meta"] = json.load(fh)
        except Exception:
            run["meta"] = {}
    run["proposers"] = _read_csv(os.path.join(run_dir, "proposers.csv"))
    run["weights"] = _read_csv(os.path.join(run_dir, "weights.csv"))
    run["epochs"] = _read_csv(os.path.join(run_dir, "epochs.csv"))
    run["gas"] = _read_csv(os.path.join(run_dir, "gas.csv"))
    run["refuels"] = _read_csv(os.path.join(run_dir, "refuels.csv"))
    return run


def final_weights(run):
    """address -> weight, from the latest epoch present in weights.csv."""
    by_epoch = defaultdict(dict)
    for r in run["weights"]:
        try:
            e = int(float(r.get("epoch") or 0))
        except (TypeError, ValueError):
            continue
        addr = r.get("address") or ""
        if addr:
            by_epoch[e][addr] = int(_num(r, "weight"))
    if not by_epoch:
        return {}
    return by_epoch[max(by_epoch)]


# =============================================================================
# Analyses
# =============================================================================

def analyse_distribution(run):
    """Empirical proposer distribution vs the weights that produced it."""
    weights = final_weights(run)
    counts = Counter()
    for r in run["proposers"]:
        m = (r.get("miner") or "").strip()
        if m:
            counts[m] += 1
    total_blocks = sum(counts.values())
    total_w = sum(weights.values())
    if not weights or total_w <= 0 or total_blocks == 0:
        return None

    rows = []
    expected = {}
    for addr, w in sorted(weights.items(), key=lambda kv: -kv[1]):
        exp = total_blocks * w / total_w
        expected[addr] = exp
        obs = counts.get(addr, 0)
        lo, hi = wilson_interval(obs, total_blocks)
        rows.append({
            "address": addr, "weight": w,
            "weight_share": w / total_w,
            "expected_blocks": exp, "observed_blocks": obs,
            "observed_share": obs / total_blocks,
            "ratio": (obs / exp) if exp > 0 else float("nan"),
            "deviation": obs / total_blocks - w / total_w,
            "ci95_low": lo, "ci95_high": hi,
            "expected_share_in_ci": lo <= (w / total_w) <= hi,
        })
    # Proposers with no weight entry are a finding in their own right.
    unknown = {a: c for a, c in counts.items() if a not in weights}
    chi2, df, p, used, dropped = chi2_gof(counts, expected)
    return {
        "rows": rows, "chi2": chi2, "df": df, "p": p,
        "classes_used": used, "classes_dropped": dropped,
        "total_blocks": total_blocks, "unknown_proposers": unknown,
        "counts": counts, "weights": weights,
    }


def analyse_concentration(run, dist):
    out = []
    weights = final_weights(run)
    if weights:
        out.append({"series": "weights", "n": len(weights),
                    "gini": gini(list(weights.values())),
                    "normalised_entropy": norm_entropy(list(weights.values())),
                    "max_share": (max(weights.values()) / sum(weights.values()))
                                 if sum(weights.values()) else 0.0})
    if dist:
        counts = [dist["counts"].get(a, 0) for a in dist["weights"]]
        total = sum(counts)
        out.append({"series": "proposals", "n": len(counts),
                    "gini": gini(counts),
                    "normalised_entropy": norm_entropy(counts),
                    "max_share": (max(counts) / total) if total else 0.0})
    return out


def analyse_epochs(run):
    """Per-epoch series, plus the weight dispersion that shows whether the feedback moved."""
    by_epoch = defaultdict(dict)
    for r in run["weights"]:
        try:
            e = int(float(r.get("epoch") or 0))
        except (TypeError, ValueError):
            continue
        addr = r.get("address") or ""
        if addr:
            by_epoch[e][addr] = _num(r, "weight")

    rows = []
    for r in run["epochs"]:
        try:
            e = int(float(r.get("epoch") or 0))
        except (TypeError, ValueError):
            continue
        w = list(by_epoch.get(e, {}).values())
        m, sd = mean_stdev(w)
        rows.append({
            "epoch": e,
            "height": int(_num(r, "height")),
            "verified_epoch": int(_num(r, "verified_epoch")),
            "mismatch": int(_num(r, "mismatch")),
            "not_a_cluster": int(_num(r, "not_a_cluster")),
            "other_epoch": int(_num(r, "other_epoch")),
            "refuels": int(_num(r, "refuels")),
            "validators": len(w),
            "weight_mean": m, "weight_stdev": sd,
            "weight_cv": (sd / m) if m else 0.0,
            "weight_min": min(w) if w else 0.0,
            "weight_max": max(w) if w else 0.0,
            "weight_gini": gini(w) if w else 0.0,
        })
    rows.sort(key=lambda x: x["epoch"])
    return rows


def analyse_gas(run):
    by_node = defaultdict(list)
    roles = {}
    for r in run["gas"]:
        node = r.get("node") or ""
        if not node:
            continue
        by_node[node].append(_num(r, "balance"))
        roles[node] = r.get("role") or "?"
    refuels = Counter()
    for r in run["refuels"]:
        refuels[r.get("node") or ""] += 1
    rows = []
    for node, series in sorted(by_node.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        m, sd = mean_stdev(series)
        rows.append({
            "node": node, "role": roles.get(node, "?"),
            "samples": len(series),
            "balance_first": series[0] if series else 0.0,
            "balance_last": series[-1] if series else 0.0,
            "balance_min": min(series) if series else 0.0,
            "balance_mean": m, "balance_stdev": sd,
            "refuels": refuels.get(node, 0),
            "ran_dry": 1 if (series and min(series) <= 0) else 0,
        })
    return rows


# =============================================================================
# Reporting
# =============================================================================

def _w(path, rows, fields):
    if not rows:
        return None
    with open(path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        wr.writeheader()
        for r in rows:
            wr.writerow(r)
    return path


def _verdict(ok):
    return "PASS" if ok else "FAIL"


def build_report(run, mc_results, dist, conc, epochs, gas, alpha):
    meta = run["meta"]
    L, verdicts = [], []
    ap = L.append

    name = meta.get("experiment", os.path.basename(run["dir"].rstrip("/")))
    ap("# Functional run — statistical report")
    ap("")
    ap("**Experiment:** `%s`  " % name)
    if meta.get("started"):
        ap("**Started:** %s  " % meta["started"])
    if meta.get("finished"):
        ap("**Finished:** %s  " % meta["finished"])
    ap("**Significance level:** alpha = %g (a p-value BELOW this rejects the null)" % alpha)
    ap("")
    ap("> Read the two election tests together. The **Monte Carlo** validates the")
    ap("> *formula* at a sample size we choose; the **empirical chi-square** validates the")
    ap("> *compiled binary* at whatever sample the run produced. Neither is sufficient")
    ap("> alone: the first is not running the C++, and the second has no power in the tail")
    ap("> of a skewed weight vector.")
    ap("")

    if meta.get("parameters"):
        ap("## Parameters")
        ap("")
        ap("| Parameter | Value |")
        ap("|---|---|")
        for k in sorted(meta["parameters"]):
            ap("| `%s` | `%s` |" % (k, meta["parameters"][k]))
        ap("")

    # ---- Monte Carlo --------------------------------------------------------
    ap("## 1. Monte Carlo validation of the election algorithm")
    ap("")
    ap("Re-implements `WPoASelector::ScoreFromEntropy64` and `ApplyDumping` from")
    ap("`src/wpoa/wpoa_selector.h` in Python, drawing 64-bit entropy from a uniform source")
    ap("in place of the VRF — which is the intended test, since Prop. 5.11 requires the VRF")
    ap("to be indistinguishable from uniform. Null hypothesis: `Pr[i elected] = w_i / W_tot`")
    ap("(Teor. 5.3).")
    ap("")
    ap("| Scenario | Draws | chi2 | df | p | Classes (used/dropped) | Zero-weight picks | Verdict |")
    ap("|---|---:|---:|---:|---:|---:|---:|---|")
    for key, res, note in mc_results:
        ok = True
        if res["df"] >= 1 and not math.isnan(res["p"]):
            ok = res["p"] >= alpha
        zero_ok = res["zero_weight_selections"] == 0
        ok = ok and zero_ok
        verdicts.append(("monte-carlo:%s" % key, ok))
        ap("| `%s` | %d | %.3f | %d | %s | %d/%d | %d | %s |" % (
            key, res["draws"], res["chi2"], res["df"],
            ("%.4f" % res["p"]) if not math.isnan(res["p"]) else "n/a",
            res["classes_used"], res["classes_dropped"],
            res["zero_weight_selections"], _verdict(ok)))
    ap("")
    for key, res, note in mc_results:
        ap("- **`%s`** — %s" % (key, note))
    ap("")
    ap("A dropped class is one whose expectation fell below 5, where the chi-square")
    ap("approximation does not hold; it is excluded and counted rather than silently")
    ap("inflating the statistic. **Zero-weight picks must be exactly 0** (Cor. 5.4): the")
    ap("score returns `+inf` before any division, so a single selection would mean the")
    ap("guarantee had become a probabilistic one.")
    ap("")

    # ---- empirical ----------------------------------------------------------
    ap("## 2. Empirical proposer distribution (this run, this binary)")
    ap("")
    if not dist:
        ap("_No proposer or weight data recorded — nothing to test._")
        ap("")
        verdicts.append(("empirical-distribution", False))
    else:
        ok = True
        if dist["df"] >= 1 and not math.isnan(dist["p"]):
            ok = dist["p"] >= alpha
        if dist["unknown_proposers"]:
            ok = False
        verdicts.append(("empirical-distribution", ok))
        ap("Blocks in the sample: **%d**. chi2 = **%.3f**, df = %d, p = %s → **%s**"
           % (dist["total_blocks"], dist["chi2"], dist["df"],
              ("%.4f" % dist["p"]) if not math.isnan(dist["p"]) else "n/a", _verdict(ok)))
        ap("")
        ap("Classes used %d, dropped %d (expectation < 5 — no power there, by construction)."
           % (dist["classes_used"], dist["classes_dropped"]))
        ap("")
        ap("| Validator | Weight | Share | Expected | Observed | obs/exp | Dev | 95%% CI | Share in CI |")
        ap("|---|---:|---:|---:|---:|---:|---:|---|---|")
        for r in dist["rows"]:
            ap("| `%s` | %d | %.4f | %.1f | %d | %s | %+.4f | [%.4f, %.4f] | %s |" % (
                r["address"][:12] + "…", r["weight"], r["weight_share"],
                r["expected_blocks"], r["observed_blocks"],
                ("%.3f" % r["ratio"]) if not math.isnan(r["ratio"]) else "n/a",
                r["deviation"], r["ci95_low"], r["ci95_high"],
                "yes" if r["expected_share_in_ci"] else "**no**"))
        ap("")
        never = [r for r in dist["rows"] if r["observed_blocks"] == 0]
        if never:
            ap("**Validators that never proposed (%d).** Not a failure by itself — under"
               % len(never))
            ap("weighted random selection a light validator legitimately may not win in a")
            ap("finite sample. Judge each against its expectation:")
            ap("")
            for r in never:
                pnever = math.exp(dist["total_blocks"] * math.log(1 - r["weight_share"])) \
                    if 0 < r["weight_share"] < 1 else float("nan")
                ap("- `%s`: weight %d (share %.4f), expected %.1f blocks, P(never) ≈ %s"
                   % (r["address"][:12] + "…", r["weight"], r["weight_share"],
                      r["expected_blocks"],
                      ("%.3g" % pnever) if not math.isnan(pnever) else "n/a"))
            ap("")
        if dist["unknown_proposers"]:
            ap("**Proposers with no weight entry — a finding.** Under wPoA every proposer")
            ap("must be in the weight map:")
            ap("")
            for a, c in dist["unknown_proposers"].items():
                ap("- `%s`: %d block(s)" % (a, c))
            ap("")

    # ---- concentration ------------------------------------------------------
    ap("## 3. Concentration and fairness")
    ap("")
    if conc:
        ap("| Series | n | Gini | Normalised entropy | Max share |")
        ap("|---|---:|---:|---:|---:|")
        for c in conc:
            ap("| %s | %d | %.4f | %.4f | %.4f |"
               % (c["series"], c["n"], c["gini"], c["normalised_entropy"], c["max_share"]))
        ap("")
        ap("Descriptive, **not** verdicts. Under weighted selection the target is not")
        ap("uniformity, so a Gini above 0 is expected and correct — the question the")
        ap("chi-square answers is whether the concentration MATCHES the weights. What is")
        ap("worth watching across runs is the *gap* between the two rows: proposals much")
        ap("more concentrated than weights would suggest the selector is amplifying.")
    else:
        ap("_No data._")
    ap("")

    # ---- epochs -------------------------------------------------------------
    ap("## 4. Per-epoch series")
    ap("")
    if epochs:
        bad = sum(e["mismatch"] + e["not_a_cluster"] for e in epochs)
        verdicts.append(("verification-clean", bad == 0))
        ap("Epochs recorded: **%d** (%d → %d). Invalid verdicts across the run: **%d** → **%s**"
           % (len(epochs), epochs[0]["epoch"], epochs[-1]["epoch"], bad, _verdict(bad == 0)))
        ap("")
        cvs = [e["weight_cv"] for e in epochs if e["validators"] > 1]
        if cvs:
            m, sd = mean_stdev(cvs)
            ap("Weight dispersion (coefficient of variation) across epochs: mean %.4f, sd %.4f,"
               % (m, sd))
            ap("range [%.4f, %.4f]. A CV that stays flat at 0 means the restitution feedback"
               % (min(cvs), max(cvs)))
            ap("never moved — check that the native currency is actually enabled, or the")
            ap("weights are a constant multiple of W_k and the run proved nothing about rho.")
            ap("")
        ap("| Epoch | Height | Verified | Validators | Mean w | CV | Gini | Mismatch | Not-a-cluster | Other-epoch | Refuels |")
        ap("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        step = max(1, len(epochs) // 40)     # keep the table readable on long runs
        for e in epochs[::step]:
            ap("| %d | %d | %d | %d | %.1f | %.4f | %.4f | %d | %d | %d | %d |" % (
                e["epoch"], e["height"], e["verified_epoch"], e["validators"],
                e["weight_mean"], e["weight_cv"], e["weight_gini"],
                e["mismatch"], e["not_a_cluster"], e["other_epoch"], e["refuels"]))
        if step > 1:
            ap("")
            ap("_(every %dth epoch shown; `epoch_stats.csv` has them all)_" % step)
    else:
        ap("_No per-epoch data._")
    ap("")

    # ---- gas ----------------------------------------------------------------
    ap("## 5. Native currency (GAS)")
    ap("")
    if gas:
        dry = [g for g in gas if g["ran_dry"]]
        verdicts.append(("no-node-ran-dry", not dry))
        ap("Nodes tracked: **%d**. Total refuels: **%d**. Nodes that hit zero: **%d** → **%s**"
           % (len(gas), sum(g["refuels"] for g in gas), len(dry), _verdict(not dry)))
        ap("")
        ap("A node at zero cannot publish anything — membership, ESG, or a transfer to the")
        ap("treasury — so it silently stops contributing and the run measures a smaller")
        ap("network than it reports.")
        ap("")
        ap("| Node | Role | First | Last | Min | Mean | SD | Refuels | Dry |")
        ap("|---:|---|---:|---:|---:|---:|---:|---:|---|")
        for g in gas:
            ap("| %s | %s | %.2f | %.2f | %.2f | %.2f | %.2f | %d | %s |" % (
                g["node"], g["role"], g["balance_first"], g["balance_last"],
                g["balance_min"], g["balance_mean"], g["balance_stdev"],
                g["refuels"], "**yes**" if g["ran_dry"] else "no"))
    else:
        ap("_No gas data._")
    ap("")

    # ---- verdict ------------------------------------------------------------
    ap("## Verdict")
    ap("")
    ap("| Check | Result |")
    ap("|---|---|")
    for name_, ok in verdicts:
        ap("| `%s` | **%s** |" % (name_, _verdict(ok)))
    ap("")
    all_ok = all(ok for _, ok in verdicts)
    ap("**Overall: %s**" % ("PASS" if all_ok else "FAIL"))
    ap("")
    ap("---")
    ap("")
    ap("Generated by `test/functional/lib/we_stats.py`. Raw data alongside this file:")
    ap("`montecarlo.csv`, `distribution.csv`, `concentration.csv`, `epoch_stats.csv`,")
    ap("`gas_stats.csv`.")
    return "\n".join(L) + "\n", verdicts, all_ok


def write_outputs(run_dir, run, mc_results, dist, conc, epochs, gas, alpha):
    md, verdicts, all_ok = build_report(run, mc_results, dist, conc, epochs, gas, alpha)
    with open(os.path.join(run_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(md)

    lines = ["FUNCTIONAL RUN — STATISTICAL SUMMARY", "=" * 44, ""]
    name = run["meta"].get("experiment", os.path.basename(run_dir.rstrip("/")))
    lines.append("experiment : %s" % name)
    lines.append("alpha      : %g" % alpha)
    lines.append("")
    for key, res, _ in mc_results:
        lines.append("monte-carlo %-16s chi2=%9.3f df=%2d p=%s zero-picks=%d"
                     % (key, res["chi2"], res["df"],
                        ("%.4f" % res["p"]) if not math.isnan(res["p"]) else "  n/a",
                        res["zero_weight_selections"]))
    if dist:
        lines.append("empirical   %-16s chi2=%9.3f df=%2d p=%s blocks=%d"
                     % ("proposers", dist["chi2"], dist["df"],
                        ("%.4f" % dist["p"]) if not math.isnan(dist["p"]) else "  n/a",
                        dist["total_blocks"]))
    lines.append("")
    for name_, ok in verdicts:
        lines.append("  %-28s %s" % (name_, _verdict(ok)))
    lines.append("")
    lines.append("OVERALL: %s" % ("PASS" if all_ok else "FAIL"))
    with open(os.path.join(run_dir, "summary.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    mc_rows = []
    for key, res, note in mc_results:
        for addr in sorted(res["expected"]):
            mc_rows.append({
                "scenario": key, "address": addr,
                "weight": res["expected"] and "",
                "draws": res["draws"], "seed": res["seed"], "dump": res["dump"],
                "expected": res["expected"][addr], "observed": res["counts"].get(addr, 0),
                "chi2": res["chi2"], "df": res["df"], "p": res["p"],
                "note": note,
            })
    _w(os.path.join(run_dir, "montecarlo.csv"), mc_rows,
       ["scenario", "address", "draws", "seed", "dump", "expected", "observed",
        "chi2", "df", "p", "note"])
    if dist:
        _w(os.path.join(run_dir, "distribution.csv"), dist["rows"],
           ["address", "weight", "weight_share", "expected_blocks", "observed_blocks",
            "observed_share", "ratio", "deviation", "ci95_low", "ci95_high",
            "expected_share_in_ci"])
    _w(os.path.join(run_dir, "concentration.csv"), conc,
       ["series", "n", "gini", "normalised_entropy", "max_share"])
    _w(os.path.join(run_dir, "epoch_stats.csv"), epochs,
       ["epoch", "height", "verified_epoch", "validators", "weight_mean", "weight_stdev",
        "weight_cv", "weight_min", "weight_max", "weight_gini", "mismatch",
        "not_a_cluster", "other_epoch", "refuels"])
    _w(os.path.join(run_dir, "gas_stats.csv"), gas,
       ["node", "role", "samples", "balance_first", "balance_last", "balance_min",
        "balance_mean", "balance_stdev", "refuels", "ran_dry"])
    return all_ok


# =============================================================================
# Self-check — the statistics, against answers known in advance
# =============================================================================

def selfcheck():
    ok = True

    def check(label, cond, detail=""):
        nonlocal ok
        print("  %-46s %s%s" % (label, "PASS" if cond else "FAIL",
                                ("  " + detail) if detail and not cond else ""))
        ok = ok and cond

    print("we_stats.py self-check")
    print("-" * 66)

    # chi-square survival, against textbook critical values
    check("chi2_sf(3.841, 1) ~= 0.05", abs(chi2_sf(3.841, 1) - 0.05) < 5e-4)
    check("chi2_sf(5.991, 2) ~= 0.05", abs(chi2_sf(5.991, 2) - 0.05) < 5e-4)
    check("chi2_sf(11.070, 5) ~= 0.05", abs(chi2_sf(11.070, 5) - 0.05) < 5e-4)
    check("chi2_sf(15.507, 8) ~= 0.05", abs(chi2_sf(15.507, 8) - 0.05) < 5e-4)
    check("chi2_sf(0, 3) == 1", chi2_sf(0, 3) == 1.0)

    # Gini, against closed forms
    check("gini([1,1,1,1]) == 0", abs(gini([1, 1, 1, 1])) < 1e-12)
    check("gini([0,0,0,1]) == 0.75", abs(gini([0, 0, 0, 1]) - 0.75) < 1e-12)

    # entropy
    check("norm_entropy([1,1,1,1]) == 1", abs(norm_entropy([1, 1, 1, 1]) - 1.0) < 1e-12)
    check("norm_entropy([1,0,0,0]) == 0", abs(norm_entropy([1, 0, 0, 0])) < 1e-12)

    # Wilson interval brackets the point estimate
    lo, hi = wilson_interval(50, 100)
    check("wilson(50,100) brackets 0.5", lo < 0.5 < hi)

    # Cor. 5.4 — a zero weight is never elected, and the score says +inf first
    check("score_from_entropy64(d, 0) == +inf", score_from_entropy64(12345, 0) == float("inf"))
    r = monte_carlo({"a": 60, "b": 40, "z": 0}, 20000, 1)
    check("zero-weight never elected over 20k draws", r["zero_weight_selections"] == 0)
    check("uniform weights give p >= 0.01", monte_carlo({"a": 1, "b": 1, "c": 1}, 20000, 2)["p"] >= 0.01)

    # A DELIBERATELY WRONG algorithm must be rejected: without this, a chi-square that
    # can only ever pass would look like a passing test.
    rng = random.Random(3)
    weights = {"a": 90, "b": 10}
    biased = Counter()
    for _ in range(20000):
        biased["a" if rng.random() < 0.5 else "b"] += 1   # ignores the weights
    exp = {"a": 20000 * 0.9, "b": 20000 * 0.1}
    chi2, df, p, _, _ = chi2_gof(biased, exp)
    check("an unweighted draw is REJECTED against 90/10", p < 1e-6, "p=%.3g" % p)

    print("-" * 66)
    print("self-check: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# =============================================================================

def main():
    ap = argparse.ArgumentParser(description="Statistics for a functional run.")
    ap.add_argument("run_dir", nargs="?", help="directory holding the recorded run")
    ap.add_argument("--draws", type=int, default=int(os.environ.get("WE_STATS_DRAWS", 50000)),
                    help="Monte Carlo draws per scenario (default 50000)")
    ap.add_argument("--seed", type=int, default=int(os.environ.get("WE_STATS_SEED", 20260916)),
                    help="Monte Carlo seed, so a report is reproducible")
    ap.add_argument("--alpha", type=float, default=float(os.environ.get("WE_STATS_ALPHA", 0.01)),
                    help="significance level (default 0.01)")
    ap.add_argument("--dump", default="none", choices=["none", "sqrt", "log"],
                    help="dumping function g(.) to validate")
    ap.add_argument("--selfcheck", action="store_true",
                    help="validate the statistics against known answers and exit")
    args = ap.parse_args()

    if args.selfcheck:
        return selfcheck()
    if not args.run_dir:
        ap.error("run_dir is required unless --selfcheck is given")
    if not os.path.isdir(args.run_dir):
        sys.stderr.write("no such directory: %s\n" % args.run_dir)
        return 2

    run = load_run(args.run_dir)
    if not (run["proposers"] or run["weights"] or run["epochs"] or run["gas"]):
        sys.stderr.write(
            "%s holds no recorded data (proposers.csv / weights.csv / epochs.csv / "
            "gas.csv all absent or empty).\nRefusing to emit a report: an empty run must "
            "not read as a passing one.\n" % args.run_dir)
        return 2

    # Monte Carlo: the declared scenarios, plus the run's own weight vector — the one
    # configuration a report about THIS run most needs tested at a decent sample size,
    # since the run itself could not.
    scenarios = static_scenarios()
    fw = final_weights(run)
    if fw and sum(fw.values()) > 0 and len(fw) >= 2:
        scenarios.append(
            ("this-run-weights", dict(fw),
             "the weight vector this run actually produced, drawn %d times instead of the "
             "%d blocks the run mined -- if the empirical test and this one disagree, the "
             "fault is in the implementation, not the design"
             % (args.draws, len(run["proposers"]))))

    mc_results = [(key, monte_carlo(w, args.draws, args.seed + i, args.dump), note)
                  for i, (key, w, note) in enumerate(scenarios)]

    dist = analyse_distribution(run)
    conc = analyse_concentration(run, dist)
    epochs = analyse_epochs(run)
    gas = analyse_gas(run)

    all_ok = write_outputs(args.run_dir, run, mc_results, dist, conc, epochs, gas, args.alpha)
    print("statistical report written to %s" % os.path.join(args.run_dir, "report.md"))
    print("  summary: %s" % os.path.join(args.run_dir, "summary.txt"))
    print("  overall: %s" % ("PASS" if all_ok else "FAIL"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
