"""Goodness of fit: are the blocks won distributed as weighted sortition says?

Wilson (:mod:`wilson`) asks about one validator at a time. This module asks the joint
question — given the weights in force, is the *whole* vector of block counts a plausible
draw? — which is the one that actually tests the sortition.

Three estimators, dispatched rather than chosen by hand, because each is wrong outside its
range:

* **Asymptotic chi-square**, when every expected count is at least 5. The classical
  statistic ``sum (O-E)²/E`` with ``df = k-1``. Below that threshold the chi-square
  approximation to the statistic's null distribution is poor in the direction that
  manufactures significance, so it is not used there.
* **Exact multinomial enumeration**, when there are at most 3 classes. Every composition of
  the block total across the classes is enumerated and its multinomial probability summed
  wherever the statistic is at least the observed one. No approximation at all — feasible
  only because the number of compositions explodes past three classes.
* **Monte Carlo**, otherwise. ``MC_GOF`` multinomial draws under the null, p-value
  ``(hits + 1) / (draws + 1)``.

**The round-by-round variant is not a refinement, it is a correction.** A validator's share
can change *inside* an epoch: a weight record confirms, malus is applied, the validator set
changes. Pooling such an epoch into one multinomial with a single share vector tests a null
that was never in force. :func:`mc_round_by_round_pvalue` simulates each round with the
shares that actually governed *that round*, which is the only honest test when
``share_changed_within_epoch`` is true.

Alongside the p-value, three distances that stay meaningful when the p-value does not:
mean absolute error, maximum absolute error, and total variation ``sum|p̂-p|/2``. A p-value
answers "is this distinguishable from the null"; these answer "by how much", and in a smoke
run with few blocks the second question is usually the more informative one.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

import numpy as np

from . import ALPHA, ANALYSIS_SEED, MC_GOF, chi2_sf

#: Below this expected count the asymptotic chi-square is not trusted.
MIN_EXPECTED = 5.0

#: At most this many classes can be enumerated exactly in reasonable time.
MAX_EXACT_CLASSES = 3


def chi2_statistic(observed: Sequence[float], expected: Sequence[float]) -> float:
    """``sum (O-E)²/E``, skipping classes with zero expectation.

    A zero-expectation class cannot contribute: it means a validator with no weight, which
    the selector could not have drawn. Including it would divide by zero to punish an
    observation that cannot occur.
    """
    total = 0.0
    for obs, exp in zip(observed, expected):
        if exp and exp > 0:
            total += (obs - exp) ** 2 / exp
    return total


def distances(observed: Sequence[float], expected: Sequence[float]) -> Dict[str, Optional[float]]:
    """Effect sizes in probability units, independent of the block count."""
    n = sum(observed)
    if n <= 0:
        return {"MAE_p": None, "MaxAE_p": None, "TV": None}
    errors = [abs(o / n - e / n) for o, e in zip(observed, expected)]
    return {
        "MAE_p": sum(errors) / len(errors),
        "MaxAE_p": max(errors),
        "TV": sum(errors) / 2.0,
    }


def _compositions(total: int, classes: int):
    """Every way of splitting ``total`` into ``classes`` non-negative integers."""
    if classes == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in _compositions(total - first, classes - 1):
            yield (first,) + rest


def exact_multinomial_pvalue(observed: Sequence[int], probs: Sequence[float]) -> tuple:
    """``(p_value, statistic, n_outcomes)`` by full enumeration."""
    n = int(sum(observed))
    k = len(probs)
    expected = [n * p for p in probs]
    stat_obs = chi2_statistic(observed, expected)
    log_probs = [math.log(p) if p > 0 else float("-inf") for p in probs]
    total, outcomes = 0.0, 0
    for composition in _compositions(n, k):
        outcomes += 1
        log_pmf = math.lgamma(n + 1)
        impossible = False
        for count, log_p in zip(composition, log_probs):
            log_pmf -= math.lgamma(count + 1)
            if count:
                if log_p == float("-inf"):
                    impossible = True
                    break
                log_pmf += count * log_p
        if impossible:
            continue
        if chi2_statistic(composition, expected) >= stat_obs - 1e-9:
            total += math.exp(log_pmf)
    return min(1.0, total), stat_obs, outcomes


def mc_multinomial_pvalue(
    observed: Sequence[int],
    probs: Sequence[float],
    draws: int = MC_GOF,
    seed: int = ANALYSIS_SEED,
) -> tuple:
    """``(p_value, statistic)`` by simulating the null multinomial."""
    n = int(sum(observed))
    expected = np.array([n * p for p in probs], dtype=float)
    stat_obs = chi2_statistic(observed, expected)
    if n <= 0:
        return None, stat_obs
    rng = np.random.default_rng(seed)
    simulated = rng.multinomial(n, np.asarray(probs, dtype=float), size=draws)
    with np.errstate(divide="ignore", invalid="ignore"):
        contributions = np.where(expected > 0, (simulated - expected) ** 2 / expected, 0.0)
    stats = contributions.sum(axis=1)
    hits = int(np.sum(stats >= stat_obs - 1e-9))
    return (hits + 1) / (draws + 1), stat_obs


def mc_round_by_round_pvalue(
    observed: Sequence[int],
    share_matrix: Sequence[Sequence[float]],
    draws: int = MC_GOF,
    seed: int = ANALYSIS_SEED,
) -> tuple:
    """``(p_value, statistic, expected)`` with the shares that governed each round.

    ``share_matrix`` is ``rounds x classes``: row *r* holds the shares in force for round
    *r*. The expected count of class *j* is the column sum, which is the correct
    expectation for a sum of independent non-identical draws — and is generally **not**
    ``n * mean_share``, which is what pooling would assume.

    Use this whenever an epoch's shares moved. It is the only variant whose null matches
    what the chain actually did.
    """
    shares = np.asarray(share_matrix, dtype=float)
    if shares.ndim != 2 or shares.shape[0] == 0:
        return None, None, None
    rounds, classes = shares.shape
    expected = shares.sum(axis=0)
    stat_obs = chi2_statistic(observed, expected)

    rng = np.random.default_rng(seed)
    cumulative = np.cumsum(shares, axis=1)
    cumulative[:, -1] = 1.0
    counts = np.zeros((draws, classes), dtype=np.int64)
    # Chunked so that a long epoch cannot allocate a draws x rounds float array outright.
    chunk = max(1, min(draws, 4_000_000 // max(1, rounds)))
    done = 0
    while done < draws:
        size = min(chunk, draws - done)
        uniforms = rng.random((size, rounds))
        picks = (uniforms[:, :, None] > cumulative[None, :, :]).sum(axis=2)
        np.clip(picks, 0, classes - 1, out=picks)
        for j in range(classes):
            counts[done:done + size, j] = (picks == j).sum(axis=1)
        done += size

    with np.errstate(divide="ignore", invalid="ignore"):
        contributions = np.where(expected > 0, (counts - expected) ** 2 / expected, 0.0)
    stats = contributions.sum(axis=1)
    hits = int(np.sum(stats >= stat_obs - 1e-9))
    return (hits + 1) / (draws + 1), stat_obs, expected.tolist()


def gof_test(
    observed: Sequence[int],
    expected: Sequence[float],
    alpha: float = ALPHA,
    mc_draws: int = MC_GOF,
    seed: int = ANALYSIS_SEED,
) -> Dict[str, object]:
    """Dispatch to the right estimator and report the whole decision, not just the p-value.

    ``gof_method`` names which estimator ran, so a reader can tell an exact result from an
    asymptotic one without inferring it from the class count.
    """
    observed = [int(o) for o in observed]
    expected = [float(e) for e in expected]
    n = sum(observed)
    classes = len(observed)
    row: Dict[str, object] = {
        "n_blocks": n,
        "n_classes": classes,
        "min_expected": min(expected) if expected else None,
        "gof_chi2": None,
        "gof_df": max(0, classes - 1),
        "gof_method": None,
        "gof_p_value": None,
        "gof_reject_alpha05": None,
        "gof_exact_outcomes": None,
        "gof_mc_draws": None,
    }
    row.update(distances(observed, expected))

    if n <= 0 or classes < 2:
        row["gof_method"] = "not computable"
        row["gof_note"] = (
            "not computable: %s"
            % ("no blocks in this epoch" if n <= 0 else "fewer than two validators")
        )
        return row

    total_expected = sum(expected)
    if total_expected <= 0:
        row["gof_method"] = "not computable"
        row["gof_note"] = "not computable: every expected count is zero (no weight in force)"
        return row
    probs = [e / total_expected for e in expected]

    if min(expected) >= MIN_EXPECTED:
        statistic = chi2_statistic(observed, expected)
        row.update(
            {
                "gof_method": "chi2_asymptotic",
                "gof_chi2": statistic,
                "gof_p_value": chi2_sf(statistic, classes - 1),
            }
        )
    elif classes <= MAX_EXACT_CLASSES:
        p_value, statistic, outcomes = exact_multinomial_pvalue(observed, probs)
        row.update(
            {
                "gof_method": "exact_multinomial_enumeration",
                "gof_chi2": statistic,
                "gof_p_value": p_value,
                "gof_exact_outcomes": outcomes,
            }
        )
    else:
        p_value, statistic = mc_multinomial_pvalue(observed, probs, mc_draws, seed)
        row.update(
            {
                "gof_method": "monte_carlo_multinomial",
                "gof_chi2": statistic,
                "gof_p_value": p_value,
                "gof_mc_draws": mc_draws,
            }
        )
        row["gof_note"] = (
            "the smallest expected count is %.2f (< %.0f), so the asymptotic chi-square "
            "was not used" % (min(expected), MIN_EXPECTED)
        )

    if row["gof_p_value"] is not None:
        row["gof_reject_alpha05"] = bool(row["gof_p_value"] < alpha)
    return row


def pooled_expected(share_matrix: Sequence[Sequence[float]]) -> List[float]:
    """Column sums of a round-by-round share matrix: the correct expected counts."""
    shares = np.asarray(share_matrix, dtype=float)
    if shares.ndim != 2 or shares.size == 0:
        return []
    return shares.sum(axis=0).tolist()


__all__ = [
    "MAX_EXACT_CLASSES",
    "MIN_EXPECTED",
    "chi2_statistic",
    "distances",
    "exact_multinomial_pvalue",
    "gof_test",
    "mc_multinomial_pvalue",
    "mc_round_by_round_pvalue",
    "pooled_expected",
]
