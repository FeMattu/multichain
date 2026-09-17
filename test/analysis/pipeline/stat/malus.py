"""Statistics specific to the malicious-miner experiment.

Pure functions over already-aggregated rows, in the same closed-form, dependency-free
style as the rest of ``stat/``. Nothing here reads a file or a chain, and every quantity
returned is either a number or ``None`` with a reason — never a ``0`` standing in for
"no data", because a detection rate of 0 over zero actions is not the same fact as a
detection rate of 0 over fifty.

The three states an action can be in are kept rigorously distinct throughout, because
conflating them is the single easiest way to overstate the mechanism:

``attempted``
    the injector's controller decided to act (ground truth, from the miner's own log);
``confirmed``
    the action's transaction reached a block (ground truth, still);
``valid malus``
    an honest node's ``reportmalus`` predicate accepted the evidence and a report was
    published (the detector's verdict, produced without reading the ground truth).

Precision, recall and F1 below are always measured against **confirmed** actions as the
positive class, never attempted ones: an action that never confirmed cannot carry a malus,
so counting it as a missed detection would penalise the detector for the chain's timing.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

from . import Z95


def rate(numerator: int, denominator: int) -> Optional[float]:
    """A share, or ``None`` when there is nothing to take a share of."""
    return (numerator / denominator) if denominator else None


def detection_metrics(
    true_positive: int, false_positive: int, false_negative: int
) -> Dict[str, object]:
    """Precision, recall and F1 for the detector, with the counts they came from.

    * TP — a confirmed malicious action the detector reported;
    * FP — a report against a record that was **not** a confirmed malicious action (an
      honest record wrongly accused: the mechanism's safety property says this is 0);
    * FN — a confirmed malicious action the detector never reported.

    Each metric is ``None`` when its denominator is empty, so "no false positives because
    there were no reports at all" reads differently from "precision 1.0 over 40 reports".
    """
    tp, fp, fn = int(true_positive), int(false_positive), int(false_negative)
    precision = rate(tp, tp + fp)
    recall = rate(tp, tp + fn)
    if precision is None or recall is None or (precision + recall) == 0:
        f1: Optional[float] = None
    else:
        f1 = 2.0 * precision * recall / (precision + recall)
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "n_reports": tp + fp,
        "n_confirmed_positives": tp + fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def latency_summary(latencies: Sequence[Optional[float]]) -> Dict[str, object]:
    """Count, mean, median and the quartiles of a detection/activation latency sample."""
    values = sorted(float(x) for x in latencies if x is not None and math.isfinite(float(x)))
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "median": None, "p25": None, "p75": None,
                "min": None, "max": None}

    def quantile(q: float) -> float:
        if n == 1:
            return values[0]
        pos = q * (n - 1)
        lo = int(math.floor(pos))
        hi = min(lo + 1, n - 1)
        frac = pos - lo
        return values[lo] * (1 - frac) + values[hi] * frac

    return {
        "n": n,
        "mean": sum(values) / n,
        "median": quantile(0.5),
        "p25": quantile(0.25),
        "p75": quantile(0.75),
        "min": values[0],
        "max": values[-1],
    }


def ecdf(values: Sequence[float]) -> List[Dict[str, float]]:
    """The empirical CDF as ``(x, F(x))`` steps — the table a step plot and its reader share."""
    xs = sorted(float(x) for x in values if x is not None and math.isfinite(float(x)))
    n = len(xs)
    return [{"x": x, "f": (k + 1) / n} for k, x in enumerate(xs)] if n else []


def rate_convergence(target: Optional[float], realised: Optional[float],
                     n_opportunities: int) -> Dict[str, object]:
    """How far the realised attempt rate landed from its target, with a Wilson band.

    The band is what turns "0.13 against a target of 0.15" from an apparent miss into what
    it usually is — sampling noise over a handful of opportunities. When the realised rate
    sits inside the interval, the controller hit its target to the resolution the run
    allows.
    """
    if target is None or realised is None or n_opportunities <= 0:
        return {"target": target, "realised": realised, "abs_error": None,
                "wilson95_low": None, "wilson95_high": None, "target_inside": None}
    successes = int(round(realised * n_opportunities))
    low, high = _wilson(successes, n_opportunities)
    return {
        "target": target,
        "realised": realised,
        "abs_error": abs(realised - target),
        "wilson95_low": low,
        "wilson95_high": high,
        "target_inside": (low <= target <= high),
    }


def _wilson(successes: int, trials: int, z: float = Z95) -> tuple:
    if trials <= 0:
        return None, None
    p = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    centre = (p + z2 / (2 * trials)) / denom
    half = z * math.sqrt(p * (1 - p) / trials + z2 / (4 * trials * trials)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def relative_change(before: Optional[float], after: Optional[float]) -> Optional[float]:
    """``(after - before) / before``, or ``None`` when ``before`` is missing or zero."""
    if before is None or after is None or before == 0:
        return None
    return (after - before) / before


def median(values: Sequence[float]) -> Optional[float]:
    xs = sorted(float(x) for x in values if x is not None and math.isfinite(float(x)))
    n = len(xs)
    if n == 0:
        return None
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def iqr(values: Sequence[float]) -> Optional[tuple]:
    summary = latency_summary(list(values))
    if summary["n"] == 0:
        return None
    return (summary["p25"], summary["p75"])


__all__ = [
    "detection_metrics",
    "ecdf",
    "iqr",
    "latency_summary",
    "median",
    "rate",
    "rate_convergence",
    "relative_change",
]
