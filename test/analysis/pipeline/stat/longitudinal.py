"""Longitudinal checks: does the relationship between weight and wins hold over time?

Everything else in this package looks at one epoch. These look *across* epochs, which is
where the WeightEngine's feedback loop lives and where a slow drift — the kind no single
epoch's p-value would catch — becomes visible.

Four instruments:

**1. First-versus-last gains.** The earliest and the latest fully measured epoch, side by
side, per validator: entitled share, observed share, and the Wilson interval around each.
Reported with the intervals rather than as bare deltas, because a "gain" smaller than the
interval width is not a gain.

**2. Sign test on monotonicity.** Across consecutive epoch pairs, did the observed share
move in the *same direction* as the effective weight? Pairs where either delta is zero
carry no information and are dropped. The p-value is the **exact** binomial tail — with a
dozen informative pairs, which is typical for a smoke run, the normal approximation is
wrong in the direction that manufactures significance. This test makes no assumption about
functional form, which is exactly why it is the first one to look at.

**3. Binomial logit GLM, fitted by hand.** Regress wins on ``log(weight)``::

    logit(p_i) = beta0 + beta1 * log(w_eff_i)

Weighted sortition implies **beta1 = 1**: doubling the weight should double the odds ratio.
That is a sharp, falsifiable prediction, and the Wald interval around ``beta1`` is the
statement of it. Fitted with iteratively reweighted least squares in about thirty lines —
no ``statsmodels`` — so the estimator is inspectable rather than delegated.

**4. Pairwise log-ratio regression.** For every validator pair in every epoch,
``log(O_i/O_j)`` against ``log(p_i/p_j)``. Under proportional selection this is the identity
line: **slope 1, intercept 0**. Its advantage over the GLM is that it is invariant to the
number of blocks in the epoch and to any multiplicative bias affecting all validators
equally — a systematic distortion shows up as a slope away from 1 even when every
individual epoch passes its own goodness-of-fit test.

A note that belongs next to the numbers: with few epochs these have little power. Reporting
``n_points`` beside every coefficient is not decoration; a slope of 0.6 from four points
says nothing at all.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import binom_sf_inclusive, linear_fit, pearson, spearman
from .wilson import wilson_interval


def gains(
    first: Dict[str, Tuple[int, int, float]],
    last: Dict[str, Tuple[int, int, float]],
) -> List[Dict[str, object]]:
    """First versus last fully measured epoch, per validator.

    Each mapping is ``address -> (O, B, p_theoretical)``: wins, blocks in the epoch, and
    the entitled share. Validators present in only one of the two epochs still get a row —
    a validator that appeared or vanished is a finding, not a missing value.
    """
    rows: List[Dict[str, object]] = []
    for address in sorted(set(first) | set(last)):
        row: Dict[str, object] = {"validator_address": address}
        for label, source in (("first", first), ("last", last)):
            entry = source.get(address)
            if entry is None:
                row.update(
                    {
                        "O_%s" % label: None,
                        "n_blocks_%s" % label: None,
                        "p_theoretical_%s" % label: None,
                        "p_hat_%s" % label: None,
                        "wilson_low_%s" % label: None,
                        "wilson_high_%s" % label: None,
                        "present_%s" % label: False,
                    }
                )
                continue
            wins, blocks, theoretical = entry
            low, high = wilson_interval(wins, blocks)
            row.update(
                {
                    "O_%s" % label: wins,
                    "n_blocks_%s" % label: blocks,
                    "p_theoretical_%s" % label: theoretical,
                    "p_hat_%s" % label: (wins / blocks) if blocks else None,
                    "wilson_low_%s" % label: low,
                    "wilson_high_%s" % label: high,
                    "present_%s" % label: True,
                }
            )
        p_first, p_last = row.get("p_hat_first"), row.get("p_hat_last")
        t_first, t_last = row.get("p_theoretical_first"), row.get("p_theoretical_last")
        row["gain_observed"] = (
            None if (p_first is None or p_last is None) else p_last - p_first
        )
        row["gain_theoretical"] = (
            None if (t_first is None or t_last is None) else t_last - t_first
        )
        if None in (row.get("wilson_low_first"), row.get("wilson_low_last")):
            row["intervals_overlap"] = None
        else:
            row["intervals_overlap"] = not (
                row["wilson_high_first"] < row["wilson_low_last"]
                or row["wilson_high_last"] < row["wilson_low_first"]
            )
        rows.append(row)
    return rows


def monotonicity(series: Sequence[Tuple[int, float, float]]) -> Dict[str, object]:
    """Exact sign test: does the observed share move with the effective weight?

    ``series`` is ``(epoch, w_eff, p_hat)`` in epoch order. A pair is *informative* only
    when both deltas are non-zero; a flat weight tells us nothing about direction, and
    counting it as agreement or disagreement would be inventing information.
    """
    ordered = sorted(
        (e, w, p) for e, w, p in series
        if w is not None and p is not None
        and math.isfinite(float(w)) and math.isfinite(float(p))
    )
    total = max(0, len(ordered) - 1)
    informative = concordant = 0
    for (_, w0, p0), (_, w1, p1) in zip(ordered, ordered[1:]):
        dw, dp = w1 - w0, p1 - p0
        if dw == 0 or dp == 0:
            continue
        informative += 1
        if (dw > 0) == (dp > 0):
            concordant += 1

    row: Dict[str, object] = {
        "n_pairs_total": total,
        "n_pairs_informative": informative,
        "n_concordant": concordant,
        "concordance_rate": (concordant / informative) if informative else None,
        "sign_test_p_greater": None,
        "note": "",
    }
    if informative == 0:
        row["note"] = (
            "not computable: no consecutive epoch pair had both the weight and the "
            "observed share change"
        )
        return row
    row["sign_test_p_greater"] = binom_sf_inclusive(concordant, informative, 0.5)
    if informative < 6:
        row["note"] = (
            "only %d informative pair(s): the exact test is correct but has very little "
            "power at this size" % informative
        )
    return row


def binomial_logit_glm(
    successes: Sequence[int], trials: Sequence[int], x: Sequence[float]
) -> Dict[str, object]:
    """Binomial logit GLM by IRLS. ``H0: beta1 = 1``, which weighted sortition implies.

    Iteratively reweighted least squares is Fisher scoring for a GLM: at each step, form
    the working response ``z = eta + (y - m*mu) / w`` and the working weight
    ``w = m*mu*(1-mu)``, then solve the weighted normal equations. It converges in a
    handful of iterations for well-posed data and is stopped at 50 rather than allowed to
    cycle.

    Returned with ``converged`` and ``n_points`` because a non-converged fit or a
    four-point one must not be read as a coefficient.
    """
    rows = [
        (int(k), int(n), float(v))
        for k, n, v in zip(successes, trials, x)
        if n and n > 0 and v is not None and math.isfinite(float(v))
    ]
    out: Dict[str, object] = {
        "beta0": None,
        "beta1": None,
        "beta1_se": None,
        "beta1_ci_low": None,
        "beta1_ci_high": None,
        "beta1_consistent_with_1": None,
        "deviance": None,
        "n_points": len(rows),
        "converged": False,
        "note": "",
    }
    if len(rows) < 3:
        out["note"] = "not computable: fewer than 3 usable points"
        return out
    if len({r[2] for r in rows}) < 2:
        out["note"] = "not computable: the regressor is constant"
        return out

    y = np.array([r[0] for r in rows], dtype=float)
    m = np.array([r[1] for r in rows], dtype=float)
    design = np.column_stack([np.ones(len(rows)), np.array([r[2] for r in rows])])

    observed_p = np.clip(y / m, 1e-6, 1 - 1e-6)
    beta = np.array([math.log(observed_p.mean() / (1 - observed_p.mean())), 0.0])
    information = None
    for _ in range(50):
        eta = design @ beta
        mu = 1.0 / (1.0 + np.exp(-np.clip(eta, -500, 500)))
        weight = np.maximum(m * mu * (1 - mu), 1e-12)
        z = eta + (y - m * mu) / weight
        information = design.T @ (weight[:, None] * design)
        try:
            new_beta = np.linalg.solve(information, design.T @ (weight * z))
        except np.linalg.LinAlgError:
            out["note"] = "not computable: the information matrix is singular"
            return out
        if np.max(np.abs(new_beta - beta)) < 1e-9:
            beta = new_beta
            out["converged"] = True
            break
        beta = new_beta

    eta = design @ beta
    mu = np.clip(1.0 / (1.0 + np.exp(-np.clip(eta, -500, 500))), 1e-12, 1 - 1e-12)
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(y > 0, y * np.log(y / (m * mu)), 0.0) + np.where(
            m - y > 0, (m - y) * np.log((m - y) / (m * (1 - mu))), 0.0
        )
    out["deviance"] = float(2.0 * np.sum(terms))
    out["beta0"], out["beta1"] = float(beta[0]), float(beta[1])
    try:
        covariance = np.linalg.inv(information)
        se = float(math.sqrt(max(0.0, covariance[1, 1])))
        out["beta1_se"] = se
        out["beta1_ci_low"] = out["beta1"] - 1.959963984540054 * se
        out["beta1_ci_high"] = out["beta1"] + 1.959963984540054 * se
        out["beta1_consistent_with_1"] = bool(
            out["beta1_ci_low"] <= 1.0 <= out["beta1_ci_high"]
        )
    except np.linalg.LinAlgError:
        out["note"] = "coefficient estimated, but its standard error is not computable"
    if not out["converged"] and not out["note"]:
        out["note"] = "IRLS did not converge within 50 iterations; treat beta1 as indicative"
    return out


def log_ratio_rows(epoch_table: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    """Pairwise log-ratios, one row per (epoch, i, j).

    Only pairs where **both** validators won at least one block are usable: a zero win
    count makes the observed log-ratio infinite. Excluded pairs are recorded with a note
    rather than dropped silently, because the exclusion is itself informative — many such
    pairs means the run was too short to resolve the ratios at all.
    """
    rows: List[Dict[str, object]] = []
    by_epoch: Dict[object, List[Dict[str, object]]] = {}
    for entry in epoch_table:
        by_epoch.setdefault(entry.get("epoch"), []).append(entry)

    for epoch in sorted(by_epoch, key=lambda e: (e is None, e)):
        entries = sorted(by_epoch[epoch], key=lambda e: str(e.get("validator_address", "")))
        for i, left in enumerate(entries):
            for right in entries[i + 1:]:
                o_i = left.get("O_i") or 0
                o_j = right.get("O_i") or 0
                p_i = left.get("p_theoretical")
                p_j = right.get("p_theoretical")
                row: Dict[str, object] = {
                    "epoch": epoch,
                    "validator_i": left.get("validator_address"),
                    "validator_j": right.get("validator_address"),
                    "O_i": o_i,
                    "O_j": o_j,
                    "log_ratio_observed": None,
                    "log_ratio_theoretical": None,
                    "note": "",
                }
                if o_i > 0 and o_j > 0:
                    row["log_ratio_observed"] = math.log(o_i / o_j)
                else:
                    row["note"] = "not computable: a validator won no block in this epoch"
                if p_i and p_j and p_i > 0 and p_j > 0:
                    row["log_ratio_theoretical"] = math.log(p_i / p_j)
                elif not row["note"]:
                    row["note"] = "not computable: a validator had no weight in this epoch"
                rows.append(row)
    return rows


def log_ratio_fit(rows: Sequence[Dict[str, object]]) -> Dict[str, object]:
    """Regress observed log-ratios on theoretical ones. ``H0: slope = 1, intercept = 0``."""
    xs, ys = [], []
    for row in rows:
        x, y = row.get("log_ratio_theoretical"), row.get("log_ratio_observed")
        if x is None or y is None:
            continue
        xs.append(float(x))
        ys.append(float(y))

    out: Dict[str, object] = {
        "n_pairs": len(xs),
        "slope": None,
        "intercept": None,
        "pearson_r": None,
        "pearson_p": None,
        "spearman_rho": None,
        "spearman_p": None,
        "note": "H0 of proportionality: slope = 1 and intercept = 0",
    }
    if len(xs) < 3:
        out["note"] = "not computable: fewer than 3 usable validator pairs"
        return out
    slope, intercept, _ = linear_fit(xs, ys)
    out["slope"], out["intercept"] = slope, intercept
    out["pearson_r"], out["pearson_p"], _ = pearson(xs, ys)
    out["spearman_rho"], out["spearman_p"], _ = spearman(xs, ys)
    return out


def lag1_spearman(
    pairs: Sequence[Tuple[float, float]]
) -> Dict[str, object]:
    """Spearman of a reconciliation factor at epoch *e* against the weight at *e+1*.

    The WeightEngine's only endogenous feedback: ``w_k^(e) = W_k^(e) * [rho^(e-1)*lambda +
    (1-lambda)]``, so ``rho`` at one epoch should predict the published weight at the next.
    Spearman rather than Pearson because the relationship is monotone by construction but
    not linear — ``W_k`` moves underneath it.

    With ``lambda = 0`` the bracket is constant and **no correlation is expected**: that is
    the configuration being inert, not the engine failing.
    """
    xs = [float(a) for a, b in pairs if a is not None and b is not None]
    ys = [float(b) for a, b in pairs if a is not None and b is not None]
    rho, p_value, n = spearman(xs, ys)
    return {
        "n_pairs": n,
        "spearman_rho": rho,
        "spearman_p": p_value,
        "note": (
            ""
            if n >= 3
            else "not computable: fewer than 3 (rho_e, w_{e+1}) pairs"
        ),
    }


def gini_delta_slope(epochs: Sequence[float], deltas: Sequence[float]) -> Dict[str, object]:
    """Slope of ``Gini(published) - Gini(input)`` over time.

    A positive slope means the engine is progressively concentrating weight relative to its
    own inputs; a flat one means it is transmitting the input inequality without adding to
    it. This is the amplification question, and it is a trend rather than a level, so the
    slope is the statistic and the level is not.
    """
    slope, intercept, n = linear_fit(epochs, deltas)
    rho, p_value, _ = spearman(epochs, deltas)
    return {
        "n_epochs": n,
        "slope": slope,
        "intercept": intercept,
        "spearman_rho": rho,
        "spearman_p": p_value,
        "note": (
            "positive slope = the engine concentrates weight beyond its input inequality"
            if n >= 3
            else "not computable: fewer than 3 epochs with both Gini values"
        ),
    }


__all__ = [
    "binomial_logit_glm",
    "gains",
    "gini_delta_slope",
    "lag1_spearman",
    "log_ratio_fit",
    "log_ratio_rows",
    "monotonicity",
]
