"""Wilson score interval — the headline test of this harness.

**What it answers.** A validator held a final weight `w_k` in epoch *e*, which entitles it
to a share `p_theoretical = w_k / sum_j w_j` of that epoch's blocks. It actually won `O_i`
of the `B` blocks produced. Is the observed share compatible with the entitled one?

**Why Wilson and not the normal interval.** The textbook `p ± z sqrt(p(1-p)/n)` is wrong
exactly where this harness lives: small `n`, and shares near 0 or 1. It produces intervals
that run past 0 or past 1, and it collapses to zero width when a validator won no blocks
at all — which is precisely the observation that most needs an interval. Wilson's interval
is derived by inverting the score test instead of the Wald test, so it stays inside [0, 1]
by construction, has sensible width at `O_i = 0` and `O_i = B`, and needs no continuity
fudge.

    centre = (p̂ + z²/2n) / (1 + z²/n)
    half   = z · sqrt( p̂(1-p̂)/n + z²/4n² ) / (1 + z²/n)

A closed form, no library: ``z = 1.959963984540054`` is the two-sided 95% normal quantile
and everything else is arithmetic.

**How to read the result.** ``p_theoretical_inside_wilson95`` is the per-epoch, per-validator
verdict. It is *not* a hypothesis test over the whole epoch — for that, see
:mod:`gof`, which tests all validators jointly and is the right instrument for
"is this distribution the weighted one?". The interval answers the narrower and more
useful question of *which* validator is out of line, and by how much.

A caution that belongs with the number rather than in a footnote: with `V` validators per
epoch, roughly `0.05 · V` intervals will exclude the true share by chance alone. Counting
"how many epochs had at least one exclusion" across a long run and calling it a finding is
a multiple-comparisons error. :func:`coverage_summary` reports the expected exclusion count
alongside the observed one for that reason.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence

from . import Z95, binom_sf_inclusive


def wilson_interval(successes: int, trials: int, z: float = Z95) -> tuple:
    """``(low, high)`` for the 95% Wilson score interval. ``(None, None)`` when n = 0."""
    if trials is None or trials <= 0:
        return None, None
    successes = max(0, min(int(successes), int(trials)))
    n = float(trials)
    p = successes / n
    z2 = z * z
    denominator = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / denominator
    half = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def wilson_row(
    successes: int, trials: int, p_theoretical: Optional[float] = None, z: float = Z95
) -> Dict[str, object]:
    """One validator-epoch, as a row.

    ``abs_error_p`` and ``excess_p`` are kept separately on purpose: the absolute error is
    what the goodness-of-fit distances aggregate, while the signed excess is what makes a
    plot of "who is over-represented" readable.
    """
    low, high = wilson_interval(successes, trials, z)
    p_hat = (successes / trials) if trials else None
    row: Dict[str, object] = {
        "O_i": int(successes),
        "n_blocks": int(trials),
        "p_hat": p_hat,
        "wilson95_low": low,
        "wilson95_high": high,
        "wilson95_width": None if low is None else high - low,
    }
    if p_theoretical is None or p_hat is None:
        row.update(
            {
                "p_theoretical": p_theoretical,
                "E_i": None,
                "abs_error_p": None,
                "excess_p": None,
                "p_theoretical_inside_wilson95": None,
                "binomial_two_sided_p": None,
            }
        )
        return row

    inside = low <= p_theoretical <= high
    row.update(
        {
            "p_theoretical": p_theoretical,
            "E_i": p_theoretical * trials,
            "abs_error_p": abs(p_hat - p_theoretical),
            "excess_p": p_hat - p_theoretical,
            "p_theoretical_inside_wilson95": inside,
            "binomial_two_sided_p": binomial_two_sided(successes, trials, p_theoretical),
        }
    )
    return row


def binomial_two_sided(successes: int, trials: int, p: float) -> Optional[float]:
    """Exact two-sided binomial p-value, by the doubled-smaller-tail convention.

    Reported beside the interval because the two disagree in an informative way: the
    interval is an inversion of the *score* test and the p-value here is exact, so a share
    that sits just inside the interval with a p-value near 0.05 is a genuine borderline
    case rather than a rounding artefact.
    """
    if trials <= 0 or p is None or not (0.0 <= p <= 1.0):
        return None
    if p in (0.0, 1.0):
        expected = p * trials
        return 1.0 if abs(successes - expected) < 1e-12 else 0.0
    upper = binom_sf_inclusive(successes, trials, p)
    lower = 1.0 - binom_sf_inclusive(successes + 1, trials, p)
    if upper is None or lower is None:
        return None
    return min(1.0, 2.0 * min(upper, lower))


def epoch_rows(
    observed: Dict[str, int],
    weights: Dict[str, float],
    n_blocks: Optional[int] = None,
    z: float = Z95,
) -> List[Dict[str, object]]:
    """Wilson rows for one epoch: every validator with a weight, in address order.

    ``weights`` is the **final** per-epoch weight (``wpoalistfinalweights``), i.e. the one
    the election actually consumes — after the malus factor and after the dumping
    function. Using the raw published weight instead would compare the observed share
    against an entitlement the selector never saw.

    A validator carrying a weight but winning nothing still gets a row: its absence from
    the block list is the observation.
    """
    total_weight = sum(float(w) for w in weights.values() if w is not None)
    blocks = n_blocks if n_blocks is not None else sum(observed.values())
    rows: List[Dict[str, object]] = []
    for address in sorted(weights):
        weight = float(weights[address] or 0.0)
        share = (weight / total_weight) if total_weight > 0 else None
        row = wilson_row(observed.get(address, 0), blocks, share, z)
        row["validator_address"] = address
        row["weight_final"] = weight
        rows.append(row)
    return rows


def coverage_summary(rows: Iterable[Dict[str, object]], alpha: float = 0.05) -> Dict[str, object]:
    """How often the entitled share fell outside its interval, against how often it should.

    With `V` intervals at 95%, about `0.05·V` exclusions are expected under a perfectly
    weighted election. Reporting the expectation next to the count is what stops the
    observed number being read as a finding on its own.
    """
    checked = [r for r in rows if r.get("p_theoretical_inside_wilson95") is not None]
    outside = [r for r in checked if not r["p_theoretical_inside_wilson95"]]
    n = len(checked)
    if n == 0:
        return {
            "n_intervals": 0,
            "n_outside": 0,
            "coverage_rate": None,
            "expected_outside": None,
            "excess_outside": None,
            "note": "not computable: no validator-epoch had both a weight and a block count",
        }
    expected = alpha * n
    return {
        "n_intervals": n,
        "n_outside": len(outside),
        "coverage_rate": (n - len(outside)) / n,
        "expected_outside": expected,
        "excess_outside": len(outside) - expected,
        "outside_addresses": sorted({str(r.get("validator_address", "")) for r in outside}),
        "note": (
            "%.1f exclusions are expected by chance at alpha=%.2f over %d intervals; "
            "treat the count as a finding only well above that" % (expected, alpha, n)
        ),
    }


def mean_width(rows: Sequence[Dict[str, object]]) -> Optional[float]:
    """Mean interval width — the run's resolution.

    A run whose intervals are all 0.4 wide cannot distinguish a weighted election from a
    uniform one no matter what the p-values say, and this is the number that shows it.
    """
    widths = [r["wilson95_width"] for r in rows if r.get("wilson95_width") is not None]
    return (sum(widths) / len(widths)) if widths else None


__all__ = [
    "binomial_two_sided",
    "coverage_summary",
    "epoch_rows",
    "mean_width",
    "wilson_interval",
    "wilson_row",
]
