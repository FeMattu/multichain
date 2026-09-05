"""Goodness of fit of observed block counts to theoretical selection shares.

Method choice (declared in every output row):
  chi2_asymptotic                  when min expected count >= 5
  exact_multinomial_enumeration    otherwise, when the number of classes <= 3
                                   (all C(B+k-1, k-1) compositions are enumerated)
  monte_carlo (N draws)            otherwise
Additionally a round-by-round Monte Carlo that respects per-round shares is
offered for epochs whose in-force shares change inside the epoch.

Distances: MAE, MaxAE, total variation between p_hat and p.
"""

import math

import numpy as np

try:
    from scipy import stats as _st
    USING_SCIPY = True
except ImportError:                                   # pragma: no cover
    _st = None
    USING_SCIPY = False

MIN_EXPECTED = 5.0
MC_DRAWS_DEFAULT = 20000


def chi2_statistic(observed, expected):
    obs = np.asarray(observed, dtype=float)
    exp = np.asarray(expected, dtype=float)
    mask = exp > 0
    return float(np.sum((obs[mask] - exp[mask]) ** 2 / exp[mask]))


def distances(observed, expected):
    obs = np.asarray(observed, dtype=float)
    exp = np.asarray(expected, dtype=float)
    n = obs.sum()
    if n <= 0:
        return {"MAE_p": "", "MaxAE_p": "", "TV": ""}
    p_hat, p = obs / n, exp / exp.sum()
    d = np.abs(p_hat - p)
    return {"MAE_p": float(d.mean()), "MaxAE_p": float(d.max()), "TV": float(d.sum() / 2)}


def _compositions(total, k):
    """All k-tuples of non-negative ints summing to total (k <= 3 in practice)."""
    if k == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in _compositions(total - first, k - 1):
            yield (first,) + rest


def exact_multinomial_pvalue(observed, probs):
    """Exact p-value: total probability of all outcomes whose chi-square
    statistic is >= the observed one (chi-square ordering)."""
    obs = np.asarray(observed, dtype=int)
    p = np.asarray(probs, dtype=float)
    p = p / p.sum()
    n, k = int(obs.sum()), len(obs)
    exp = n * p
    stat_obs = chi2_statistic(obs, exp)
    comps = np.array(list(_compositions(n, k)), dtype=float)
    logpmf = math.lgamma(n + 1) - np.sum([math.lgamma(1)] * 0)      # placeholder for clarity
    with np.errstate(divide="ignore"):
        logp = np.where(p > 0, np.log(p), -np.inf)
    lg = np.vectorize(math.lgamma)
    logpmf = math.lgamma(n + 1) - lg(comps + 1).sum(axis=1) + np.where(
        comps > 0, comps * logp, 0.0).sum(axis=1)
    pmf = np.exp(logpmf)
    stats = np.sum(np.where(exp > 0, (comps - exp) ** 2 / np.where(exp > 0, exp, 1.0), 0.0), axis=1)
    pval = float(pmf[stats >= stat_obs - 1e-9].sum())
    return min(1.0, pval), stat_obs, len(comps)


def mc_multinomial_pvalue(observed, probs, draws=MC_DRAWS_DEFAULT, seed=0):
    obs = np.asarray(observed, dtype=int)
    p = np.asarray(probs, dtype=float)
    p = p / p.sum()
    n = int(obs.sum())
    exp = n * p
    stat_obs = chi2_statistic(obs, exp)
    rng = np.random.default_rng(seed)
    sims = rng.multinomial(n, p, size=draws)
    stats = np.sum(np.where(exp > 0, (sims - exp) ** 2 / np.where(exp > 0, exp, 1.0), 0.0), axis=1)
    pval = float((np.sum(stats >= stat_obs - 1e-9) + 1) / (draws + 1))
    return pval, stat_obs


def mc_round_by_round_pvalue(observed, share_matrix, draws=MC_DRAWS_DEFAULT, seed=0):
    """Monte Carlo GoF where round r selects class j with probability
    share_matrix[r, j] (rounds are independent, not identically distributed).
    The statistic is chi-square against E_j = sum_r share[r, j]."""
    obs = np.asarray(observed, dtype=int)
    S = np.asarray(share_matrix, dtype=float)
    S = S / S.sum(axis=1, keepdims=True)
    exp = S.sum(axis=0)
    stat_obs = chi2_statistic(obs, exp)
    rng = np.random.default_rng(seed)
    cum = np.cumsum(S, axis=1)
    u = rng.random((draws, S.shape[0]))
    picks = (u[:, :, None] > cum[None, :, :]).sum(axis=2)          # class index per round
    counts = np.stack([(picks == j).sum(axis=1) for j in range(S.shape[1])], axis=1)
    stats = np.sum(np.where(exp > 0, (counts - exp) ** 2 / np.where(exp > 0, exp, 1.0), 0.0), axis=1)
    pval = float((np.sum(stats >= stat_obs - 1e-9) + 1) / (draws + 1))
    return pval, stat_obs, exp


def gof_test(observed, expected, alpha=0.05, mc_draws=MC_DRAWS_DEFAULT, seed=0):
    """Dispatch on the expected counts; returns a dict with the method used."""
    obs = np.asarray(observed, dtype=float)
    exp = np.asarray(expected, dtype=float)
    keep = exp > 0
    obs_k, exp_k = obs[keep], exp[keep]
    n = int(obs.sum())
    out = {"n_blocks": n, "n_classes": int(keep.sum()), "min_expected": float(exp_k.min()) if len(exp_k) else "",
           "chi2_stat": "", "df": "", "gof_method": "", "p_value": "", "reject_alpha": "",
           "exact_outcomes_enumerated": "", "mc_draws": ""}
    if n == 0 or len(exp_k) < 2:
        out["gof_method"] = "not computable: fewer than 2 classes with positive expectation or no blocks"
        return out
    out["chi2_stat"] = chi2_statistic(obs_k, exp_k)
    out["df"] = int(len(exp_k) - 1)
    probs = exp_k / exp_k.sum()
    if exp_k.min() >= MIN_EXPECTED and USING_SCIPY:
        out["gof_method"] = "chi2_asymptotic"
        out["p_value"] = float(_st.chi2.sf(out["chi2_stat"], out["df"]))
    elif len(exp_k) <= 3:
        pval, _s, n_out = exact_multinomial_pvalue(obs_k.astype(int), probs)
        out["gof_method"] = "exact_multinomial_enumeration"
        out["p_value"] = pval
        out["exact_outcomes_enumerated"] = n_out
    else:
        pval, _s = mc_multinomial_pvalue(obs_k.astype(int), probs, draws=mc_draws, seed=seed)
        out["gof_method"] = "monte_carlo_multinomial"
        out["p_value"] = pval
        out["mc_draws"] = mc_draws
    out["reject_alpha"] = int(out["p_value"] < alpha)
    out.update(distances(obs_k, exp_k))
    return out
