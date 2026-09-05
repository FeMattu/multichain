"""Concentration indices on a vector of shares: HHI, effective number, Nakamoto coefficient, Gini, entropy."""

import math

import numpy as np


def hhi(shares):
    s = np.asarray([x for x in shares if x is not None], dtype=float)
    if s.sum() <= 0:
        return ""
    s = s / s.sum()
    return float(np.sum(s * s))


def n_eff(shares):
    h = hhi(shares)
    return (1.0 / h) if h not in ("", 0) else ""


def nakamoto(shares, threshold):
    """Smallest number of validators whose cumulative share reaches `threshold`."""
    s = sorted((x for x in shares if x is not None), reverse=True)
    tot = sum(s)
    if tot <= 0:
        return ""
    acc = 0.0
    for i, v in enumerate(s, 1):
        acc += v / tot
        if acc >= threshold - 1e-12:
            return i
    return len(s)


def gini(values):
    vals = sorted(float(v) for v in values if v is not None and float(v) >= 0)
    n, total = len(vals), sum(vals)
    if n < 2 or total <= 0:
        return 0.0
    cum = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(vals))
    return cum / (n * total)


def normalized_entropy(values):
    vals = [float(v) for v in values if v is not None and float(v) > 0]
    total = sum(vals)
    if len(vals) < 2 or total <= 0:
        return 0.0
    h = -sum((v / total) * math.log(v / total) for v in vals)
    return h / math.log(len(vals))


def concentration_row(shares, prefix):
    return {
        prefix + "HHI": hhi(shares), prefix + "N_eff": n_eff(shares),
        prefix + "nakamoto_1_3": nakamoto(shares, 1.0 / 3.0),
        prefix + "nakamoto_1_2": nakamoto(shares, 0.5),
        prefix + "nakamoto_2_3": nakamoto(shares, 2.0 / 3.0),
        prefix + "gini": gini(shares), prefix + "entropy_norm": normalized_entropy(shares),
    }
