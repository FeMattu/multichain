"""Longitudinal checks across epochs: gains, monotonicity, binomial logit GLM, pairwise log-ratios."""

import math

import numpy as np

try:
    from scipy import stats as _st
    USING_SCIPY = True
except ImportError:                                   # pragma: no cover
    _st = None
    USING_SCIPY = False

from .wilson import wilson_interval


def gains(first, last):
    """first/last: dicts addr -> (O, B, p_theoretical). Returns rows per validator."""
    rows = []
    for a in sorted(set(first) | set(last)):
        o0, b0, p0 = first.get(a, (0, 0, None))
        o1, b1, p1 = last.get(a, (0, 0, None))
        ph0 = o0 / b0 if b0 else None
        ph1 = o1 / b1 if b1 else None
        lo0, hi0 = wilson_interval(o0, b0)
        lo1, hi1 = wilson_interval(o1, b1)
        rows.append({"validator_address": a,
                     "p_theoretical_first": p0 if p0 is not None else "", "p_hat_first": ph0 if ph0 is not None else "",
                     "wilson_low_first": lo0 if lo0 is not None else "", "wilson_high_first": hi0 if hi0 is not None else "",
                     "p_theoretical_last": p1 if p1 is not None else "", "p_hat_last": ph1 if ph1 is not None else "",
                     "wilson_low_last": lo1 if lo1 is not None else "", "wilson_high_last": hi1 if hi1 is not None else "",
                     "gain_observed": (ph1 - ph0) if (ph0 is not None and ph1 is not None) else "",
                     "gain_theoretical": (p1 - p0) if (p0 is not None and p1 is not None) else "",
                     "intervals_overlap": int(not (hi0 < lo1 or hi1 < lo0)) if (lo0 is not None and lo1 is not None) else ""})
    return rows


def monotonicity(series):
    """series: list of (epoch, w_eff, p_hat) for one validator, epoch-ordered.
    Counts consecutive-epoch pairs where the sign of dw and of dp_hat agree
    (ties in either excluded) and runs an exact binomial sign test vs 1/2."""
    pairs = [(series[i][1] - series[i - 1][1], series[i][2] - series[i - 1][2]) for i in range(1, len(series))
             if series[i][1] is not None and series[i - 1][1] is not None
             and series[i][2] is not None and series[i - 1][2] is not None]
    informative = [(dw, dp) for dw, dp in pairs if dw != 0 and dp != 0]
    conc = sum(1 for dw, dp in informative if (dw > 0) == (dp > 0))
    n = len(informative)
    p = ""
    if n and USING_SCIPY:
        p = float(_st.binomtest(conc, n, 0.5, alternative="greater").pvalue) if hasattr(_st, "binomtest") \
            else float(_st.binom_test(conc, n, 0.5, alternative="greater"))
    return {"n_pairs_total": len(pairs), "n_pairs_informative": n, "n_concordant": conc,
            "concordance_rate": (conc / n) if n else "", "sign_test_p_greater": p}


def binomial_logit_glm(successes, trials, x):
    """logit(E[O/B]) = b0 + b1 * x fitted by IRLS (binomial GLM, weights = trials).
    Returns b1 and its Wald 95% CI, b0, deviance, n. No statsmodels needed."""
    y = np.asarray(successes, dtype=float)
    m = np.asarray(trials, dtype=float)
    X = np.column_stack([np.ones(len(x)), np.asarray(x, dtype=float)])
    keep = m > 0
    y, m, X = y[keep], m[keep], X[keep]
    if len(y) < 3 or np.ptp(X[:, 1]) == 0:
        return {"beta1": "", "beta1_se": "", "beta1_ci_low": "", "beta1_ci_high": "", "beta0": "",
                "n_points": int(len(y)), "converged": "", "note": "not computable: < 3 points or constant regressor"}
    beta = np.zeros(2)
    p_obs = np.clip(y / m, 1e-6, 1 - 1e-6)
    beta[0] = float(np.log(p_obs.mean() / (1 - p_obs.mean())))
    converged = False
    for _ in range(50):
        eta = X @ beta
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = m * mu * (1 - mu)
        z = eta + (y - m * mu) / np.maximum(w, 1e-12)
        XtW = X.T * w
        try:
            new = np.linalg.solve(XtW @ X, XtW @ z)
        except np.linalg.LinAlgError:
            break
        if np.max(np.abs(new - beta)) < 1e-9:
            beta = new
            converged = True
            break
        beta = new
    eta = X @ beta
    mu = 1.0 / (1.0 + np.exp(-eta))
    w = m * mu * (1 - mu)
    try:
        cov = np.linalg.inv((X.T * w) @ X)
        se1 = float(math.sqrt(cov[1, 1]))
    except np.linalg.LinAlgError:
        se1 = float("nan")
    with np.errstate(divide="ignore", invalid="ignore"):
        dev = 2 * np.nansum(np.where(y > 0, y * np.log(y / (m * mu)), 0.0)
                            + np.where(m - y > 0, (m - y) * np.log((m - y) / (m - m * mu)), 0.0))
    return {"beta1": float(beta[1]), "beta1_se": se1, "beta1_ci_low": float(beta[1] - 1.96 * se1),
            "beta1_ci_high": float(beta[1] + 1.96 * se1), "beta0": float(beta[0]),
            "deviance": float(dev), "n_points": int(len(y)), "converged": int(converged),
            "note": "binomial GLM with logit link, IRLS; H0 of proportionality: beta1 = 1 with x = log(w_eff/W_tot)"}


def log_ratio_rows(epoch_table):
    """epoch_table: list of dicts with epoch, address, O, B, p_theoretical.
    For every pair (i, j) and epoch with O_i, O_j > 0: log(p_hat_i/p_hat_j) vs log(p_i/p_j)."""
    by_epoch = {}
    for r in epoch_table:
        by_epoch.setdefault(r["epoch"], []).append(r)
    rows = []
    for e, rs in sorted(by_epoch.items()):
        rs = sorted(rs, key=lambda r: r["address"])
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                a, b = rs[i], rs[j]
                if a["B"] and b["B"] and a["O"] > 0 and b["O"] > 0 and a["p"] and b["p"]:
                    rows.append({"epoch": e, "validator_i": a["address"], "validator_j": b["address"],
                                 "log_ratio_observed": math.log((a["O"] / a["B"]) / (b["O"] / b["B"])),
                                 "log_ratio_theoretical": math.log(a["p"] / b["p"]),
                                 "O_i": a["O"], "O_j": b["O"], "B": a["B"]})
                else:
                    rows.append({"epoch": e, "validator_i": a["address"], "validator_j": b["address"],
                                 "log_ratio_observed": "", "log_ratio_theoretical":
                                 math.log(a["p"] / b["p"]) if (a["p"] and b["p"]) else "",
                                 "O_i": a["O"], "O_j": b["O"], "B": a["B"],
                                 "note": "not computable: a zero count in the epoch"})
    return rows


def log_ratio_fit(rows):
    xs = [r["log_ratio_theoretical"] for r in rows if r["log_ratio_observed"] != "" and r["log_ratio_theoretical"] != ""]
    ys = [r["log_ratio_observed"] for r in rows if r["log_ratio_observed"] != "" and r["log_ratio_theoretical"] != ""]
    if len(xs) < 3 or np.ptp(xs) == 0:
        return {"n_pairs": len(xs), "slope": "", "intercept": "", "pearson_r": "", "pearson_p": "",
                "spearman_rho": "", "spearman_p": "", "note": "not computable: < 3 pairs or constant x"}
    slope, intercept = np.polyfit(xs, ys, 1)
    out = {"n_pairs": len(xs), "slope": float(slope), "intercept": float(intercept)}
    if USING_SCIPY:
        pr = _st.pearsonr(xs, ys)
        sr = _st.spearmanr(xs, ys)
        out.update({"pearson_r": float(pr[0]), "pearson_p": float(pr[1]),
                    "spearman_rho": float(sr[0]), "spearman_p": float(sr[1])})
    else:
        out.update({"pearson_r": "", "pearson_p": "", "spearman_rho": "", "spearman_p": ""})
    out["note"] = "H0 of proportionality: slope = 1, intercept = 0"
    return out
