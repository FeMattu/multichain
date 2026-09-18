"""The timer race: does the sortition delay mechanism behave as the thesis says?

Under private sortition every eligible validator scores itself, converts the score into a
mining delay, and waits. The smallest delay wins the round. The quantity of interest is the
**margin** ``G = D_(2) - D_(1)``, the gap between the fastest and the second fastest: it is
the window inside which any perturbation — scheduler jitter, propagation, clock skew — can
invert the outcome.

Three tests, deliberately unequal in status.

**1. KS against Beta(1, n) — the straw man.** If every validator had the same weight, the
normalised delays would be n i.i.d. uniforms and the margin would follow Beta(1, n) scaled
to the band. It is *expected to reject* whenever the weights are not uniform, and it is
computed precisely so the report can show it rejecting rather than leave a reader wondering
whether anyone checked. Reading its rejection as a defect is the mistake it exists to
prevent.

**2. KS against the simulated exact distribution — the real test.** The same delays are
simulated from the model the node actually implements::

    E_i    ~ Exponential(1)
    score  = E_i / w_eff_i                     (Efraimidis-Spirakis)
    norm   = 1 - exp(-W_tot * score)
    D_i    = T + delta*T*(2*norm - 1) + lambda*Phi

with the weights that were in force in each round. This is the null that should *not* be
rejected, and it is the one to read.

**3. Prop. 5.17 — the analytic check.** The standardised gap between the two best scores,
``z = (score_(2) - score_(1)) * (W_tot - w_(1))``, is Exponential(1) under the model. It
tests the score stage directly, before the delay transform, so a failure here and a pass in
test 2 localises the fault to the transform rather than to the draw.

**The inversion bound.** ``P[inversion] <= (3/2) * (n*sigma/D_max)^(2/3)`` (Prop. 5.18),
where ``sigma`` is the standard deviation of the perturbation. Two sources:

* ``S1`` — propagation/topology. **Not measured by this version of the harness.** No
  caller supplies ``topology_latencies``, so it is reported as 0 in either regime — which
  is an absence of measurement, not a measurement that came out small. A native run has no
  emulated latency for it to carry; an emulated one does, and carrying it through to here
  is separate work that has not been done. Until it is, no run of either regime can say
  anything about a latency-driven inversion.
* ``S2`` — the standard deviation of the scheduler residual, i.e. how far actual block
  spacing departs from the delay that was supposed to produce it. **This is the primary
  source here**, and the one the bound is evaluated with.

The bound is a bound, so a Monte-Carlo estimate of the inversion probability under Gaussian
noise of the same ``sigma`` is reported beside it. When the two disagree by orders of
magnitude, the bound is loose — which is a property of the bound, not a finding about the
chain.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

import numpy as np

from . import (
    ANALYSIS_SEED,
    MC_GOF,
    ks_pvalue_one_sample,
    ks_pvalue_two_sample,
    ks_statistic_against_cdf,
    ks_statistic_two_sample,
)


def beta_1_n_cdf(n: int, scale: float):
    """CDF of Beta(1, n) scaled to ``[0, scale]``: ``1 - (1 - x/scale)^n``, in closed form.

    Beta(1, n) is the one case where no special function is needed at all — the incomplete
    beta collapses to a power — so this is exact rather than approximated.
    """
    def cdf(x: float) -> float:
        if scale <= 0:
            return 1.0
        t = min(1.0, max(0.0, x / scale))
        return 1.0 - (1.0 - t) ** n

    return cdf


def ks_beta_margin(
    margins: Sequence[float], dmax: float, n_candidates: int
) -> Dict[str, object]:
    """Test 1 — the straw man. KS of the observed margins against Beta(1, n)."""
    values = [float(g) for g in margins if g is not None and math.isfinite(float(g))]
    row: Dict[str, object] = {
        "ks_beta_stat": None,
        "ks_beta_p": None,
        "ks_beta_n": len(values),
        "ks_beta_mean_G_s": (sum(values) / len(values)) if values else None,
        "ks_beta_expected_mean_G_s": None,
        "ks_beta_note": "",
    }
    if len(values) < 3 or n_candidates < 2 or dmax <= 0:
        row["ks_beta_note"] = (
            "not computable: needs at least 3 margins, 2 candidates and a positive band "
            "(have %d margins, %d candidates, D_max=%s)" % (len(values), n_candidates, dmax)
        )
        return row
    scale = 2.0 * dmax
    statistic = ks_statistic_against_cdf(values, beta_1_n_cdf(n_candidates, scale))
    row["ks_beta_stat"] = statistic
    row["ks_beta_p"] = ks_pvalue_one_sample(statistic, len(values))
    row["ks_beta_expected_mean_G_s"] = scale / (n_candidates + 1)
    row["ks_beta_note"] = (
        "STRAW MAN: Beta(1,n) assumes uniform weights. Rejection is EXPECTED whenever the "
        "weights are not uniform and is not a defect; read ks_mc_* instead."
    )
    return row


def simulate_delays(
    weff_matrix: Sequence[Sequence[float]],
    tbt: float,
    delta: float,
    lam: float,
    phi: float,
    draws: int,
    seed: int = ANALYSIS_SEED,
) -> np.ndarray:
    """Delays under the model the node implements. Returns ``draws x rounds x candidates``.

    Rounds with no positive weight are dropped by the caller; a zero weight inside a round
    would divide by zero and is mapped to ``+inf``, which is exactly what the selector does
    with it (a zero-weight validator can never win).
    """
    weights = np.asarray(weff_matrix, dtype=float)
    rounds, candidates = weights.shape
    rng = np.random.default_rng(seed)
    exponentials = rng.exponential(1.0, size=(draws, rounds, candidates))
    with np.errstate(divide="ignore", invalid="ignore"):
        scores = np.where(weights > 0, exponentials / np.maximum(weights, 1e-300), np.inf)
    w_tot = weights.sum(axis=1, keepdims=True)
    normalised = 1.0 - np.exp(-w_tot * np.minimum(scores, 1e6))
    delays = tbt + delta * tbt * (2.0 * normalised - 1.0) + lam * phi
    return np.clip(delays, 0.0, 100000.0)


def ks_exact_mc_margin(
    margins: Sequence[float],
    weff_matrix: Sequence[Sequence[float]],
    tbt: float,
    delta: float,
    lam: float,
    phi: float,
    draws: int = MC_GOF,
    seed: int = ANALYSIS_SEED,
) -> Dict[str, object]:
    """Test 2 — the real one. Two-sample KS against the simulated exact distribution."""
    values = [float(g) for g in margins if g is not None and math.isfinite(float(g))]
    weights = np.asarray(weff_matrix, dtype=float)
    row: Dict[str, object] = {
        "ks_mc_stat": None,
        "ks_mc_p": None,
        "ks_mc_n": len(values),
        "ks_mc_draws": 0,
        "ks_mc_mean_G_s": None,
        "ks_mc_note": "",
    }
    if len(values) < 3 or weights.ndim != 2 or weights.shape[0] == 0 or weights.shape[1] < 2:
        row["ks_mc_note"] = (
            "not computable: needs at least 3 margins and a round x candidate weight "
            "matrix with 2 or more candidates"
        )
        return row

    rounds = weights.shape[0]
    per_round = max(1, int(math.ceil(draws / rounds)))
    delays = simulate_delays(weights, tbt, delta, lam, phi, per_round, seed)
    ordered = np.sort(delays, axis=2)
    simulated = (ordered[:, :, 1] - ordered[:, :, 0]).ravel()
    simulated = simulated[np.isfinite(simulated)]
    if simulated.size == 0:
        row["ks_mc_note"] = "not computable: every simulated round had a single candidate"
        return row

    statistic = ks_statistic_two_sample(values, simulated.tolist())
    row["ks_mc_stat"] = statistic
    row["ks_mc_p"] = ks_pvalue_two_sample(statistic, len(values), int(simulated.size))
    row["ks_mc_draws"] = int(simulated.size)
    row["ks_mc_mean_G_s"] = float(simulated.mean())
    row["ks_mc_note"] = (
        "REFERENCE TEST: simulated from the implemented sortition with the weights in "
        "force each round. This is the null that should NOT be rejected."
    )
    return row


def prop517_test(
    gaps_by_winner: Dict[str, Sequence[float]],
    w_tot_by_winner: Dict[str, Sequence[float]],
    weff_by_winner: Dict[str, Sequence[float]],
) -> List[Dict[str, object]]:
    """Test 3 — Prop. 5.17. Per winner class, standardised score gap against Exp(1).

    ``z = (score_(2) - score_(1)) * (W_tot - w_(1))`` is Exponential(1) under the model, so
    its mean should be 1 and a KS against Exp(1) should not reject. Split by winner because
    a single validator's scoring being wrong is a different fault from the mechanism being
    wrong, and pooling would hide the first inside the second.
    """
    rows: List[Dict[str, object]] = []
    for winner in sorted(gaps_by_winner):
        gaps = list(gaps_by_winner.get(winner) or [])
        totals = list(w_tot_by_winner.get(winner) or [])
        weights = list(weff_by_winner.get(winner) or [])
        standardised: List[float] = []
        for gap, total, weight in zip(gaps, totals, weights):
            if gap is None or total is None or weight is None:
                continue
            rate = float(total) - float(weight)
            if rate <= 0 or not math.isfinite(float(gap)):
                continue
            standardised.append(float(gap) * rate)

        row: Dict[str, object] = {
            "winner_class": winner,
            "n": len(standardised),
            "ks_stat": None,
            "ks_p": None,
            "mean_standardised_gap": None,
            "expected_mean": 1.0,
            "note": "",
        }
        if len(standardised) < 3:
            row["note"] = "not computable: fewer than 3 usable rounds for this winner"
            rows.append(row)
            continue
        statistic = ks_statistic_against_cdf(
            standardised, lambda x: 1.0 - math.exp(-x) if x > 0 else 0.0
        )
        row["ks_stat"] = statistic
        row["ks_p"] = ks_pvalue_one_sample(statistic, len(standardised))
        row["mean_standardised_gap"] = sum(standardised) / len(standardised)
        rows.append(row)
    return rows


def inversion_bound(n_candidates: int, sigma: float, dmax: float) -> Optional[float]:
    """Prop. 5.18: ``min(1, (3/2) * (n*sigma/D_max)^(2/3))``."""
    if n_candidates < 2 or sigma is None or dmax is None or dmax <= 0 or sigma < 0:
        return None
    return min(1.0, 1.5 * (n_candidates * float(sigma) / float(dmax)) ** (2.0 / 3.0))


def mc_inversion_probability(
    weff_matrix: Sequence[Sequence[float]],
    tbt: float,
    delta: float,
    lam: float,
    phi: float,
    sigma: float,
    draws: int = MC_GOF,
    seed: int = ANALYSIS_SEED,
) -> Optional[float]:
    """How often Gaussian noise of this ``sigma`` changes the winner.

    Additive noise on the delays, then a comparison of the argmin before and after. The
    noise generator is offset from the delay generator's seed so the two are independent
    rather than correlated by construction.
    """
    weights = np.asarray(weff_matrix, dtype=float)
    if weights.ndim != 2 or weights.shape[0] == 0 or weights.shape[1] < 2:
        return None
    if sigma is None or sigma <= 0:
        return 0.0
    rounds = weights.shape[0]
    per_round = max(1, int(math.ceil(draws / rounds)))
    delays = simulate_delays(weights, tbt, delta, lam, phi, per_round, seed)
    rng = np.random.default_rng(seed + 1)
    noisy = delays + rng.normal(0.0, float(sigma), size=delays.shape)
    return float(np.mean(np.argmin(delays, axis=2) != np.argmin(noisy, axis=2)))


def sigma_rows(
    scheduler_residuals: Sequence[float],
    inversion_gaps: Sequence[float],
    topology_latencies: Sequence[float] = (),
) -> List[Dict[str, object]]:
    """The perturbation budget, one row per source.

    ``S1`` is reported with an explicit note rather than omitted: a reader must be able to
    see that it was measured and found structurally absent, not that it was forgotten.
    """
    def sd(values: Sequence[float]) -> Optional[float]:
        clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
        if len(clean) < 2:
            return None
        mean = sum(clean) / len(clean)
        return math.sqrt(sum((v - mean) ** 2 for v in clean) / (len(clean) - 1))

    return [
        {
            "source": "S1_topology",
            "sigma_s": sd(topology_latencies) or 0.0,
            "n": len(topology_latencies),
            "note": (
                "spread of the end-to-end propagation between validator pairs, over the "
                "shortest paths of the emulated map. This is how far apart two validators "
                "are in seeing the same block, which is what the bound is about -- not the "
                "spread of individual cables, which would count a link between two sites "
                "hosting no validator."
                if len(topology_latencies) >= 2 else
                "no propagation to measure: a native run has every node in one process, so "
                "there is no map and no path between validators. Reported as 0 because it "
                "is absent in this regime, not because it was measured and came out small."
            ),
        },
        {
            "source": "S2_scheduler_residual_sd",
            "sigma_s": sd(scheduler_residuals),
            "n": len(scheduler_residuals),
            "note": "PRIMARY source here: how far block spacing departs from its delay.",
        },
        {
            "source": "S2b_inversion_gap",
            "sigma_s": sd(inversion_gaps),
            "n": len(inversion_gaps),
            "note": "Spread of the margin on the rounds that actually inverted.",
        },
    ]


__all__ = [
    "beta_1_n_cdf",
    "inversion_bound",
    "ks_beta_margin",
    "ks_exact_mc_margin",
    "mc_inversion_probability",
    "prop517_test",
    "sigma_rows",
    "simulate_delays",
]
