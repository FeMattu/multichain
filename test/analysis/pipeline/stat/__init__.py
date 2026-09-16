"""The statistical layer: pure functions over phase-2 tables.

Every test in this package is written from its closed form. ``scipy`` is present in the
container and is deliberately **not** imported: a thesis result whose p-value depends on
which version of a library happened to be installed is harder to defend than one whose
arithmetic is visible in the file. The special functions the tests need — the chi-square
survival function, the Kolmogorov distribution, Student's *t* tail, the exact binomial
tail — live here, in one place, rather than being re-derived in each module.

The implementations are the standard ones: a series/continued-fraction pair for the
regularised incomplete gamma and the regularised incomplete beta (Numerical Recipes
§6.2/§6.4), and the alternating series for the Kolmogorov limit distribution. Each is
accurate to roughly 1e-12 over the range these tests use, which is several orders of
magnitude finer than the Monte-Carlo resolution of ``1/(draws+1)`` that bounds the
results anyway.

Shared conventions
------------------
* A quantity that cannot be computed is returned as ``None`` with a ``*_note`` field
  saying why, never as ``0`` or ``NaN``. A zero that means "no data" is indistinguishable
  from a zero that means "no effect", and the second is a result.
* Monte-Carlo p-values are ``(hits + 1) / (draws + 1)``. The ``+1`` keeps the estimate
  unbiased and stops a p-value of exactly 0 being reported for a finite simulation.
* Every generator is seeded from :data:`ANALYSIS_SEED`, which is fixed and independent of
  the experiment's own seed, so re-running the analysis on the same data reproduces the
  same numbers while a different network seed still exercises the identical procedure.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

# --------------------------------------------------------------------------------------
# Methodological constants. NOT profile fields — see test/config/schema.md 1.2.
# --------------------------------------------------------------------------------------

#: Significance level for every test in phase 3.
ALPHA = 0.05

#: Monte-Carlo draws for the goodness-of-fit dispatch.
MC_GOF = 20_000

#: Monte-Carlo draws for the streak test.
MC_STREAK = 10_000

#: RNG seed for the tests themselves. Independent of the experiment seed in the profile.
ANALYSIS_SEED = 20260905

#: The two-sided 95% normal quantile, to the precision Wilson's interval deserves.
Z95 = 1.959963984540054

_EPS = 1e-300
_MAX_ITERATIONS = 500


# --------------------------------------------------------------------------------------
# Incomplete gamma -> chi-square
# --------------------------------------------------------------------------------------


def _gamma_p_series(a: float, x: float) -> float:
    """Regularised lower incomplete gamma P(a, x) by series. Converges fast for x < a+1."""
    term = 1.0 / a
    total = term
    for n in range(1, _MAX_ITERATIONS):
        term *= x / (a + n)
        total += term
        if abs(term) < abs(total) * 1e-16:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gamma_q_continued_fraction(a: float, x: float) -> float:
    """Regularised upper incomplete gamma Q(a, x) by continued fraction (x >= a+1)."""
    b = x + 1.0 - a
    c = 1.0 / _EPS
    d = 1.0 / b
    h = d
    for i in range(1, _MAX_ITERATIONS):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < _EPS:
            d = _EPS
        c = b + an / c
        if abs(c) < _EPS:
            c = _EPS
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-16:
            break
    return h * math.exp(-x + a * math.log(x) - math.lgamma(a))


def gamma_q(a: float, x: float) -> float:
    """Regularised upper incomplete gamma Q(a, x) = 1 - P(a, x)."""
    if x < 0 or a <= 0:
        raise ValueError("gamma_q needs a > 0 and x >= 0")
    if x == 0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gamma_p_series(a, x)
    return _gamma_q_continued_fraction(a, x)


def chi2_sf(statistic: float, df: int) -> Optional[float]:
    """Upper tail of the chi-square distribution: P(X >= statistic).

    Returns ``None`` for a degenerate ``df``, which is how a one-class table arrives
    here: with a single validator there is nothing to test and no p-value to report.
    """
    if df is None or df < 1:
        return None
    if statistic is None or not math.isfinite(statistic):
        return None
    if statistic <= 0:
        return 1.0
    return max(0.0, min(1.0, gamma_q(df / 2.0, statistic / 2.0)))


# --------------------------------------------------------------------------------------
# Incomplete beta -> Student's t
# --------------------------------------------------------------------------------------


def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < _EPS:
        d = _EPS
    d = 1.0 / d
    h = d
    for m in range(1, _MAX_ITERATIONS):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < _EPS:
            d = _EPS
        c = 1.0 + aa / c
        if abs(c) < _EPS:
            c = _EPS
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < _EPS:
            d = _EPS
        c = 1.0 + aa / c
        if abs(c) < _EPS:
            c = _EPS
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-16:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + b * math.log1p(-x) + a * math.log(x)
    ) * _betacf(b, a, 1.0 - x) / b


def t_sf_two_sided(t: float, df: float) -> Optional[float]:
    """Two-sided tail of Student's t: P(|T| >= |t|)."""
    if df is None or df <= 0 or t is None or not math.isfinite(t):
        return None
    return betainc(df / 2.0, 0.5, df / (df + t * t))


def normal_cdf(x: float) -> float:
    """Standard normal CDF, via erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def normal_sf_two_sided(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2.0))


# --------------------------------------------------------------------------------------
# Kolmogorov-Smirnov
# --------------------------------------------------------------------------------------


def kolmogorov_sf(lam: float) -> float:
    """Q(lambda) = 2 * sum_{k>=1} (-1)^(k-1) exp(-2 k^2 lambda^2).

    The asymptotic distribution of the KS statistic. Below lambda ~ 0.2 the series is
    numerically useless and the true value is 1 to machine precision, so it short-circuits.
    """
    if lam <= 0:
        return 1.0
    if lam < 0.2:
        return 1.0
    total = 0.0
    for k in range(1, 101):
        term = math.exp(-2.0 * k * k * lam * lam)
        total += (-1.0) ** (k - 1) * term
        if term < 1e-18:
            break
    return max(0.0, min(1.0, 2.0 * total))


def ks_pvalue_one_sample(d: float, n: int) -> Optional[float]:
    """p-value for a one-sample KS statistic, with the Stephens small-sample correction."""
    if n <= 0 or d is None or not math.isfinite(d):
        return None
    root = math.sqrt(n)
    return kolmogorov_sf((root + 0.12 + 0.11 / root) * d)


def ks_pvalue_two_sample(d: float, n1: int, n2: int) -> Optional[float]:
    """p-value for a two-sample KS statistic, using the effective sample size."""
    if n1 <= 0 or n2 <= 0 or d is None or not math.isfinite(d):
        return None
    effective = math.sqrt(n1 * n2 / float(n1 + n2))
    return kolmogorov_sf((effective + 0.12 + 0.11 / effective) * d)


def ks_statistic_against_cdf(sample: Sequence[float], cdf) -> Optional[float]:
    """One-sample KS distance between ``sample`` and a callable CDF."""
    values = sorted(float(v) for v in sample if v is not None and math.isfinite(float(v)))
    n = len(values)
    if n == 0:
        return None
    worst = 0.0
    for i, value in enumerate(values):
        theoretical = cdf(value)
        worst = max(worst, abs(theoretical - i / n), abs((i + 1) / n - theoretical))
    return worst


def ks_statistic_two_sample(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    """Two-sample KS distance, by a merged walk over both sorted samples."""
    xs = sorted(float(v) for v in a if v is not None and math.isfinite(float(v)))
    ys = sorted(float(v) for v in b if v is not None and math.isfinite(float(v)))
    if not xs or not ys:
        return None
    i = j = 0
    worst = 0.0
    while i < len(xs) and j < len(ys):
        if xs[i] <= ys[j]:
            i += 1
        else:
            j += 1
        worst = max(worst, abs(i / len(xs) - j / len(ys)))
    return worst


# --------------------------------------------------------------------------------------
# Exact binomial tail
# --------------------------------------------------------------------------------------


def binom_sf_inclusive(k: int, n: int, p: float = 0.5) -> Optional[float]:
    """P(X >= k) for X ~ Binomial(n, p), summed exactly.

    Used by the sign test in ``longitudinal.py``. Exact rather than normal-approximated
    because the informative-pair counts in a smoke run are routinely under 20, where the
    approximation is visibly wrong in the direction that manufactures significance.
    """
    if n <= 0:
        return None
    if k > n:
        # P(X >= k) with k above the number of trials is exactly 0, not "unknown". The
        # distinction matters: the caller computes the lower tail as 1 - P(X >= k+1), and
        # a validator that won *every* block in an epoch lands on k = n + 1 here. Returning
        # None there raised a TypeError on the first run long enough to produce one.
        return 0.0
    if k <= 0:
        return 1.0
    total = 0.0
    log_p = math.log(p) if p > 0 else float("-inf")
    log_q = math.log1p(-p) if p < 1 else float("-inf")
    for i in range(k, n + 1):
        log_term = (
            math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * log_p + (n - i) * log_q
        )
        total += math.exp(log_term)
    return max(0.0, min(1.0, total))


# --------------------------------------------------------------------------------------
# Correlation
# --------------------------------------------------------------------------------------


def pearson(xs: Sequence[float], ys: Sequence[float]) -> tuple:
    """(r, p, n). ``(None, None, n)`` for fewer than 3 points or a constant series."""
    pairs = [
        (float(x), float(y))
        for x, y in zip(xs, ys)
        if x is not None and y is not None
        and math.isfinite(float(x)) and math.isfinite(float(y))
    ]
    n = len(pairs)
    if n < 3:
        return None, None, n
    mean_x = sum(p[0] for p in pairs) / n
    mean_y = sum(p[1] for p in pairs) / n
    sxx = sum((p[0] - mean_x) ** 2 for p in pairs)
    syy = sum((p[1] - mean_y) ** 2 for p in pairs)
    sxy = sum((p[0] - mean_x) * (p[1] - mean_y) for p in pairs)
    if sxx <= 0 or syy <= 0:
        return None, None, n
    r = sxy / math.sqrt(sxx * syy)
    r = max(-1.0, min(1.0, r))
    if abs(r) >= 1.0:
        return r, 0.0, n
    t = r * math.sqrt((n - 2) / (1.0 - r * r))
    return r, t_sf_two_sided(t, n - 2), n


def _ranks(values: Sequence[float]) -> list:
    """Mid-ranks, so ties do not bias the Spearman coefficient."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        shared = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = shared
        i = j + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> tuple:
    """(rho, p, n) — Pearson on mid-ranks. ``(None, None, n)`` when not computable."""
    pairs = [
        (float(x), float(y))
        for x, y in zip(xs, ys)
        if x is not None and y is not None
        and math.isfinite(float(x)) and math.isfinite(float(y))
    ]
    n = len(pairs)
    if n < 3:
        return None, None, n
    return pearson(_ranks([p[0] for p in pairs]), _ranks([p[1] for p in pairs]))


def linear_fit(xs: Sequence[float], ys: Sequence[float]) -> tuple:
    """Ordinary least squares ``(slope, intercept, n)``."""
    pairs = [
        (float(x), float(y))
        for x, y in zip(xs, ys)
        if x is not None and y is not None
        and math.isfinite(float(x)) and math.isfinite(float(y))
    ]
    n = len(pairs)
    if n < 2:
        return None, None, n
    mean_x = sum(p[0] for p in pairs) / n
    mean_y = sum(p[1] for p in pairs) / n
    sxx = sum((p[0] - mean_x) ** 2 for p in pairs)
    if sxx <= 0:
        return None, None, n
    sxy = sum((p[0] - mean_x) * (p[1] - mean_y) for p in pairs)
    slope = sxy / sxx
    return slope, mean_y - slope * mean_x, n


__all__ = [
    "ALPHA",
    "ANALYSIS_SEED",
    "MC_GOF",
    "MC_STREAK",
    "Z95",
    "betainc",
    "binom_sf_inclusive",
    "chi2_sf",
    "gamma_q",
    "kolmogorov_sf",
    "ks_pvalue_one_sample",
    "ks_pvalue_two_sample",
    "ks_statistic_against_cdf",
    "ks_statistic_two_sample",
    "linear_fit",
    "normal_cdf",
    "normal_sf_two_sided",
    "pearson",
    "spearman",
    "t_sf_two_sided",
]
