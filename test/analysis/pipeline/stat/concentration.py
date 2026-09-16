"""Concentration: how much of the mining power, or of the weight, sits with how few.

A weighted consensus can pass every goodness-of-fit test and still be a bad outcome: if
the weights themselves are concentrated, the election faithfully reproduces that
concentration. These indices measure the thing the p-values are silent about.

Five, because they disagree usefully:

* **HHI** — ``sum s_i²``. Dominated by the largest holders; the standard concentration
  measure in the antitrust literature that ESG scoring borrows its language from.
* **N_eff = 1/HHI** — "how many equal-sized validators would produce this HHI". The one
  number to quote to someone who has not met HHI. 4 validators with shares
  (0.7, 0.1, 0.1, 0.1) give N_eff ≈ 1.9: a four-validator chain that behaves like a
  two-validator one.
* **Nakamoto coefficient** — how few validators it takes to reach 1/3, 1/2, 2/3 of the
  total. The safety-relevant one: it answers "how many must collude", which neither HHI
  nor Gini does. Reported at all three thresholds because 1/3 and 2/3 are the BFT bounds
  and 1/2 is the majority one.
* **Gini** — inequality irrespective of scale, comparable across runs with different
  validator counts. Insensitive to *which* validator is large, which is exactly why it is
  reported next to Nakamoto rather than instead of it.
* **Normalised entropy** — ``-sum p ln p / ln k``, 1 for a perfectly flat distribution and
  0 for total concentration. The natural complement to HHI, and the one that degrades
  gracefully as `k` grows.

Everything is computed over both the **theoretical** shares (what the weights entitled) and
the **observed** ones (what the blocks delivered). The gap between the two pairs is the
interesting quantity: theoretical concentration is a property of the weight engine,
observed concentration is a property of the election, and a large divergence points at the
sortition rather than at the weights.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence

#: The thresholds the Nakamoto coefficient is reported at. 1/3 and 2/3 are the classical
#: BFT bounds; 1/2 is simple majority.
NAKAMOTO_THRESHOLDS = ((1.0 / 3.0, "1_3"), (0.5, "1_2"), (2.0 / 3.0, "2_3"))


def _normalise(values: Iterable[float]) -> List[float]:
    """Non-negative values scaled to sum to 1. Empty when there is nothing to normalise."""
    clean = [max(0.0, float(v)) for v in values if v is not None and math.isfinite(float(v))]
    total = sum(clean)
    if total <= 0:
        return []
    return [v / total for v in clean]


def hhi(values: Sequence[float]) -> Optional[float]:
    """Herfindahl-Hirschman index on normalised shares: ``sum s_i²``, in ``[1/k, 1]``."""
    shares = _normalise(values)
    if not shares:
        return None
    return sum(s * s for s in shares)


def n_eff(values: Sequence[float]) -> Optional[float]:
    """Effective number of validators, ``1/HHI``."""
    index = hhi(values)
    if index is None or index <= 0:
        return None
    return 1.0 / index


def nakamoto(values: Sequence[float], threshold: float) -> Optional[int]:
    """Fewest validators whose combined share reaches ``threshold``."""
    shares = sorted(_normalise(values), reverse=True)
    if not shares:
        return None
    cumulative = 0.0
    for i, share in enumerate(shares, start=1):
        cumulative += share
        if cumulative >= threshold - 1e-12:
            return i
    return len(shares)


def gini(values: Sequence[float]) -> Optional[float]:
    """Gini coefficient over the raw values, ``0`` (equal) to ``1`` (all with one).

    Returns ``0.0`` rather than ``None`` for a single validator: one validator *is*
    perfectly equal to itself, and propagating ``None`` would blank a whole column in
    every single-miner epoch of the setup phase.
    """
    clean = sorted(
        max(0.0, float(v)) for v in values if v is not None and math.isfinite(float(v))
    )
    n = len(clean)
    total = sum(clean)
    if n < 2 or total <= 0:
        return 0.0
    weighted = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(clean))
    return weighted / (n * total)


def normalized_entropy(values: Sequence[float]) -> Optional[float]:
    """Shannon entropy of the shares divided by ``ln k``: ``1`` flat, ``0`` concentrated."""
    shares = _normalise(values)
    if len(shares) < 2:
        return None
    entropy = -sum(s * math.log(s) for s in shares if s > 0)
    return entropy / math.log(len(shares))


def concentration_row(values: Sequence[float], prefix: str = "") -> Dict[str, object]:
    """Every index at once, with a common prefix so two sets can share a row."""
    row: Dict[str, object] = {
        "%sHHI" % prefix: hhi(values),
        "%sN_eff" % prefix: n_eff(values),
        "%sgini" % prefix: gini(values),
        "%sentropy_norm" % prefix: normalized_entropy(values),
        "%sn_validators" % prefix: len(_normalise(values)),
    }
    for threshold, label in NAKAMOTO_THRESHOLDS:
        row["%snakamoto_%s" % (prefix, label)] = nakamoto(values, threshold)
    return row


def divergence_row(
    theoretical: Sequence[float], observed: Sequence[float]
) -> Dict[str, object]:
    """How far the delivered concentration drifted from the entitled one.

    Positive means the election concentrated power *more* than the weights did. A
    consistent positive drift is a property of the sortition, not of the weight engine,
    and is the reason both sets are carried through the pipeline rather than just one.
    """
    out: Dict[str, object] = {}
    for name, function in (
        ("HHI", hhi),
        ("gini", gini),
        ("entropy_norm", normalized_entropy),
        ("N_eff", n_eff),
    ):
        left, right = function(theoretical), function(observed)
        out["delta_%s" % name] = None if (left is None or right is None) else right - left
    return out


__all__ = [
    "NAKAMOTO_THRESHOLDS",
    "concentration_row",
    "divergence_row",
    "gini",
    "hhi",
    "n_eff",
    "nakamoto",
    "normalized_entropy",
]
