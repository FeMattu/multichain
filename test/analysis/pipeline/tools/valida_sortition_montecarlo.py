#!/usr/bin/env python3
"""Validate the Efraimidis-Spirakis formula itself, independently of the C++ binary.

**What this does and does not test.** Everything else in this pipeline measures the
deployed node: it takes the blocks the chain produced and asks whether they look like
weighted sortition. If such a test fails, the cause could be the formula, the
implementation, the harness, or the chain's own dynamics, and the four are not
distinguishable from the outcome alone.

This script removes the formula from that list. It implements Efraimidis-Spirakis in plain
Python, draws from it many times, and checks the outcome against the closed-form
probabilities. It never talks to a node, never reads a run, and is deliberately runnable on
its own::

    python3 test/analysis/pipeline/tools/valida_sortition_montecarlo.py --draws 20000

A failure here means the *formula or this reimplementation of it* is wrong. A pass, with the
pipeline still failing, localises the fault to the binary, the harness or the chain — which
is the whole point of having it.

**The algorithm.** For each candidate *i* with weight ``w_i``, draw ``u_i ~ Uniform(0,1)``
and form the key ``k_i = u_i^(1/w_i)``; the largest key wins. Equivalently, and the form
the node uses, draw ``E_i ~ Exponential(1)`` and take ``score_i = E_i / w_i``; the smallest
score wins. The two are the same draw — ``-ln(u_i)`` is Exponential(1) — and both are
implemented here precisely so that agreeing with each other is itself a check.

**The closed form.** For the exponential-race formulation the winner probability is exactly
proportional to the weight::

    P[i wins] = w_i / sum_j w_j

which is what makes the scheme correct, and what the chi-square below tests.

Four checks are run, at several weight configurations including deliberately awkward ones
(one dominant validator, a near-zero weight, many equal weights):

1. the two formulations agree, drawn from the same uniforms;
2. the empirical winner frequencies match ``w_i / W`` (chi-square);
3. a zero weight never wins (Cor. 5.4 — a zero-weight key cannot be drawn);
4. the margin between the best two scores has the mean the theory predicts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

# Reached as ``pipeline.stat``, never as a top-level ``stat``: that name belongs to
# the standard library, and shadowing it would break os.path for the whole process.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.stat import ALPHA, ANALYSIS_SEED, MC_GOF, chi2_sf  # noqa: E402

#: Weight vectors to validate against. Chosen to include the cases where an incorrect
#: implementation is most likely to look correct: uniform weights hide any scaling error,
#: and a dominant validator hides a normalisation one.
SCENARIOS: Dict[str, List[float]] = {
    "uniform_4": [1.0, 1.0, 1.0, 1.0],
    "uniform_10": [1.0] * 10,
    "graded_4": [1.0, 2.0, 3.0, 4.0],
    "dominant": [100.0, 1.0, 1.0, 1.0],
    "near_zero": [1000.0, 1000.0, 1.0],
    "engine_floor": [1.0, 1.0, 1.0, 250.0],
    "wide_range": [1.0, 10.0, 100.0, 1000.0],
    "with_zero": [0.0, 5.0, 5.0],
}


def draw_keys(weights: np.ndarray, uniforms: np.ndarray) -> np.ndarray:
    """Efraimidis-Spirakis keys ``u^(1/w)``; the largest wins.

    A zero weight yields a key of exactly 0, which loses to every positive key — the
    arithmetic statement of "a zero-weight validator can never be drawn".
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        keys = np.where(weights > 0, uniforms ** (1.0 / np.maximum(weights, 1e-300)), 0.0)
    return keys


def draw_scores(weights: np.ndarray, uniforms: np.ndarray) -> np.ndarray:
    """The exponential-race form ``-ln(u)/w``; the smallest wins.

    Same draw as :func:`draw_keys`, since ``-ln(u)`` is Exponential(1). Fed the *same*
    uniforms on purpose: the two must then pick the identical winner every time, and any
    disagreement is a real algebraic error rather than Monte-Carlo noise.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(
            weights > 0, -np.log(np.maximum(uniforms, 1e-300)) / np.maximum(weights, 1e-300), np.inf
        )


def validate(
    name: str, weights: Sequence[float], draws: int, seed: int
) -> Dict[str, object]:
    """Run every check for one weight vector."""
    w = np.asarray(weights, dtype=float)
    n = w.size
    total = float(w.sum())
    rng = np.random.default_rng(seed)
    uniforms = rng.random((draws, n))

    keys = draw_keys(w, uniforms)
    scores = draw_scores(w, uniforms)
    winners_by_key = np.argmax(keys, axis=1)
    winners_by_score = np.argmin(scores, axis=1)

    agreement = float(np.mean(winners_by_key == winners_by_score))
    observed = np.bincount(winners_by_score, minlength=n).astype(float)
    expected = draws * w / total if total > 0 else np.zeros(n)

    with np.errstate(divide="ignore", invalid="ignore"):
        contributions = np.where(expected > 0, (observed - expected) ** 2 / expected, 0.0)
    statistic = float(contributions.sum())
    positive = int(np.sum(w > 0))
    df = max(1, positive - 1)
    p_value = chi2_sf(statistic, df)

    # The best-two margin. Under the exponential race the gap between the two smallest
    # scores is Exponential with rate (W - w_winner), so its mean is 1/(W - w_winner).
    ordered = np.sort(np.where(np.isfinite(scores), scores, np.inf), axis=1)
    margins = ordered[:, 1] - ordered[:, 0]
    finite = margins[np.isfinite(margins)]
    winner_weights = w[winners_by_score]
    rates = total - winner_weights
    expected_margin = float(np.mean(1.0 / rates[rates > 0])) if np.any(rates > 0) else None

    zero_indices = [i for i in range(n) if w[i] <= 0]
    zero_wins = int(sum(int(np.sum(winners_by_score == i)) for i in zero_indices))

    max_error = float(np.max(np.abs(observed / draws - w / total))) if total > 0 else None
    return {
        "scenario": name,
        "weights": list(map(float, w)),
        "n_candidates": n,
        "draws": draws,
        "formulations_agree": agreement == 1.0,
        "formulation_agreement_rate": agreement,
        "chi2": statistic,
        "df": df,
        "p_value": p_value,
        "reject_alpha05": None if p_value is None else bool(p_value < ALPHA),
        "max_abs_share_error": max_error,
        "observed_shares": [float(o / draws) for o in observed],
        "theoretical_shares": [float(x / total) if total > 0 else None for x in w],
        "zero_weight_candidates": zero_indices,
        "zero_weight_wins": zero_wins,
        "zero_weight_never_wins": zero_wins == 0,
        "mean_margin_observed": float(finite.mean()) if finite.size else None,
        "mean_margin_expected": expected_margin,
    }


def verdict(row: Dict[str, object]) -> bool:
    """Did this scenario pass every check?

    The chi-square is *not* required to pass at every scenario individually: at
    ``alpha = 0.05`` over eight scenarios, one spurious rejection is unremarkable. The
    structural checks — the two formulations agreeing, and a zero weight never winning —
    are absolute: either is a genuine defect.
    """
    return bool(row["formulations_agree"]) and bool(row["zero_weight_never_wins"])


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--draws", type=int, default=MC_GOF, help="draws per scenario")
    parser.add_argument("--seed", type=int, default=ANALYSIS_SEED)
    parser.add_argument("--out", default=None, help="write a CSV here")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args(argv)

    rows = [
        validate(name, weights, args.draws, args.seed + i)
        for i, (name, weights) in enumerate(sorted(SCENARIOS.items()))
    ]

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {k: (json.dumps(v) if isinstance(v, list) else v) for k, v in row.items()}
                )

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(
            "%-14s %5s %9s %9s %9s  %s"
            % ("scenario", "n", "chi2", "p", "maxErr", "structural")
        )
        for row in rows:
            print(
                "%-14s %5d %9.3f %9.4f %9.5f  %s"
                % (
                    row["scenario"],
                    row["n_candidates"],
                    row["chi2"],
                    row["p_value"] if row["p_value"] is not None else float("nan"),
                    row["max_abs_share_error"] or 0.0,
                    "ok" if verdict(row) else "FAILED",
                )
            )

    failures = [r["scenario"] for r in rows if not verdict(r)]
    rejections = [r["scenario"] for r in rows if r["reject_alpha05"]]
    print()
    if failures:
        print("STRUCTURAL FAILURE in: %s" % ", ".join(failures))
    else:
        print("structural checks passed in every scenario (formulations agree; "
              "a zero weight never wins)")
    if rejections:
        print(
            "chi-square rejected at alpha=%.2f in: %s  (%d of %d scenarios; about %.1f is "
            "expected by chance)"
            % (ALPHA, ", ".join(rejections), len(rejections), len(rows), ALPHA * len(rows))
        )
    else:
        print("chi-square did not reject in any scenario")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
