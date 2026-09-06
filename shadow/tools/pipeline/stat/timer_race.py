"""Timer-race tests (thesis Prop. 5.17 and 5.18).

* KS of the observed margin G = D(2) - D(1) against 2*Dmax*Beta(1, n), the
  prediction of Prop. 5.18 under iid-uniform delays (declared invalid by the
  thesis itself for concentrated weights, hence also:)
* KS of G against the EXACT distribution of G under the implemented sortition
  with the in-force weights of each round (Monte Carlo, E_i ~ Exp(1)).
* Prop. 5.17: score(2) - score(1) | argmin = i  ~  Exp(W - w_i)  (KS per class).
* Inversion bound: (3/2) * (n*sigma/Dmax)^(2/3) for each declared sigma.
"""

import math

import numpy as np

try:
    from scipy import stats as _st
    USING_SCIPY = True
except ImportError:                                   # pragma: no cover
    _st = None
    USING_SCIPY = False

MC_DRAWS_DEFAULT = 20000


def ks_beta_margin(margins, dmax, n_candidates):
    """KS test of G against 2*Dmax*Beta(1, n)."""
    g = np.asarray([m for m in margins if m is not None], dtype=float)
    if len(g) < 3 or not USING_SCIPY or not dmax or n_candidates < 2:
        return {"ks_beta_stat": "", "ks_beta_p": "", "ks_beta_n": len(g),
                "ks_beta_note": "not computable: n < 3 or scipy missing or n_candidates < 2"}
    dist = _st.beta(1, n_candidates, loc=0, scale=2.0 * dmax)
    res = _st.kstest(g, dist.cdf)
    return {"ks_beta_stat": float(res.statistic), "ks_beta_p": float(res.pvalue), "ks_beta_n": len(g),
            "ks_beta_note": "iid-uniform delays assumed (Prop. 5.18); invalid for concentrated weights",
            "beta_mean_G_s": float(dist.mean()), "observed_mean_G_s": float(g.mean()),
            "observed_median_G_s": float(np.median(g))}


def simulate_delays(weff_matrix, w_tot, tbt, delta, lam, phi, draws, seed=0):
    """Delays of every candidate for `draws` replicas of each round.
    weff_matrix: (R, n) effective weights per round; phi: (R,) or scalar.
    Returns array (draws, R, n)."""
    rng = np.random.default_rng(seed)
    W = np.asarray(weff_matrix, dtype=float)
    R, n = W.shape
    E = rng.exponential(1.0, size=(draws, R, n))
    with np.errstate(divide="ignore", invalid="ignore"):
        score = np.where(W[None] > 0, E / np.where(W[None] > 0, W[None], 1.0), np.inf)
    wt = np.asarray(w_tot, dtype=float).reshape(1, R, 1)
    norm = 1.0 - np.exp(-wt * score)
    ph = np.asarray(phi, dtype=float).reshape(1, -1, 1) if np.ndim(phi) else float(phi)
    D = tbt + delta * tbt * (2.0 * norm - 1.0) + lam * ph
    return np.clip(D, 0.0, 100000.0)


def ks_exact_mc_margin(margins, weff_matrix, w_tot, tbt, delta, lam, phi, draws=MC_DRAWS_DEFAULT, seed=0):
    """KS of the observed G against G simulated with the real per-round weights.
    The simulated sample pools one draw per round per replica (draws * R values),
    so the reference distribution is the mixture over the rounds actually played."""
    g = np.asarray([m for m in margins if m is not None], dtype=float)
    W = np.asarray(weff_matrix, dtype=float)
    if len(g) < 3 or W.ndim != 2 or W.shape[0] == 0 or W.shape[1] < 2 or not USING_SCIPY:
        return {"ks_mc_stat": "", "ks_mc_p": "", "ks_mc_n": len(g), "mc_draws": "",
                "ks_mc_note": "not computable: n < 3 or no weight matrix or scipy missing"}
    per_round = max(1, int(math.ceil(draws / W.shape[0])))
    D = simulate_delays(W, w_tot, tbt, delta, lam, phi, per_round, seed)
    Ds = np.sort(D, axis=2)
    G = (Ds[:, :, 1] - Ds[:, :, 0]).ravel()
    res = _st.ks_2samp(g, G)
    return {"ks_mc_stat": float(res.statistic), "ks_mc_p": float(res.pvalue), "ks_mc_n": len(g),
            "mc_draws": int(G.size), "mc_mean_G_s": float(G.mean()), "mc_median_G_s": float(np.median(G)),
            "ks_mc_note": "exact model: E_i~Exp(1), score=E/g(w_eff), same W_tot and Phi as the round"}


def mc_inversion_probability(weff_matrix, w_tot, tbt, delta, lam, phi, sigma, draws=MC_DRAWS_DEFAULT, seed=0):
    """Probability that additive N(0, sigma^2) noise on every delay changes the
    argmin, under the exact model with the real per-round weights."""
    W = np.asarray(weff_matrix, dtype=float)
    if W.ndim != 2 or W.shape[0] == 0 or W.shape[1] < 2 or not sigma:
        return ""
    per_round = max(1, int(math.ceil(draws / W.shape[0])))
    D = simulate_delays(W, w_tot, tbt, delta, lam, phi, per_round, seed)
    rng = np.random.default_rng(seed + 1)
    noisy = D + rng.normal(0.0, sigma, size=D.shape)
    inv = np.argmin(D, axis=2) != np.argmin(noisy, axis=2)
    return float(inv.mean())


def prop517_test(gaps_by_winner, w_tot_by_winner, weff_by_winner):
    """KS per winner class of score(2)-score(1) against Exp(rate = W - w_i).
    gaps_by_winner: {addr: [gap...]}; w_tot_by_winner / weff_by_winner: {addr: [values per gap]}."""
    rows = []
    for addr, gaps in gaps_by_winner.items():
        g = np.asarray(gaps, dtype=float)
        rates = np.asarray(w_tot_by_winner[addr], dtype=float) - np.asarray(weff_by_winner[addr], dtype=float)
        row = {"winner_class": addr, "n": len(g)}
        if len(g) < 3 or not USING_SCIPY or np.any(rates <= 0):
            row.update({"ks_stat": "", "ks_p": "", "note": "not computable: n < 3 or W - w_i <= 0"})
            rows.append(row)
            continue
        # rates may vary across rounds (weights change): standardise by the round's rate,
        # then test against Exp(1) -- exact under the proposition
        z = g * rates
        res = _st.kstest(z, "expon")
        row.update({"ks_stat": float(res.statistic), "ks_p": float(res.pvalue),
                    "mean_gap_x_rate": float(z.mean()), "expected_mean": 1.0,
                    "note": "gap standardised by (W - w_i) of its round, tested against Exp(1)"})
        rows.append(row)
    return rows


def inversion_bound(n, sigma, dmax):
    """(3/2) * (n*sigma/Dmax)^(2/3), capped at 1."""
    if sigma is None or sigma == "" or not dmax or not n:
        return ""
    return min(1.0, 1.5 * (n * float(sigma) / dmax) ** (2.0 / 3.0))
