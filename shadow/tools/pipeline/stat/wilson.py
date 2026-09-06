"""Wilson score interval for a binomial proportion (no normal approximation of p-hat)."""

import math

Z95 = 1.959963984540054


def wilson_interval(k, n, z=Z95):
    """(low, high) of the Wilson interval for k successes out of n trials.
    Returns (None, None) when n == 0."""
    if not n or n <= 0:
        return None, None
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def wilson_row(k, n, z=Z95):
    lo, hi = wilson_interval(k, n, z)
    return {"p_hat": (k / n) if n else "", "wilson_low": lo if lo is not None else "",
            "wilson_high": hi if hi is not None else "", "n": n}
