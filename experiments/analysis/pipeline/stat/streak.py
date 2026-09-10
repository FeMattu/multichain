"""Consecutive-win streaks: observed L_max and repeat probability vs Monte Carlo of the sortition alone."""

import numpy as np

MC_DRAWS_DEFAULT = 10000


def observed_streaks(winner_sequence):
    seq = list(winner_sequence)
    if not seq:
        return {"L_max_observed": "", "repeat_prob_observed": "", "n": 0}
    lmax = cur = 1
    repeats = 0
    for i in range(1, len(seq)):
        if seq[i] == seq[i - 1]:
            cur += 1
            repeats += 1
        else:
            cur = 1
        lmax = max(lmax, cur)
    return {"L_max_observed": lmax, "repeat_prob_observed": repeats / (len(seq) - 1) if len(seq) > 1 else "",
            "n": len(seq)}


def _lmax_rows(picks):
    """L_max for each row of a (draws, R) integer array."""
    draws, R = picks.shape
    lmax = np.ones(draws, dtype=int)
    cur = np.ones(draws, dtype=int)
    for r in range(1, R):
        same = picks[:, r] == picks[:, r - 1]
        cur = np.where(same, cur + 1, 1)
        lmax = np.maximum(lmax, cur)
    return lmax


def mc_streaks(share_matrix, lmax_obs, repeat_obs, draws=MC_DRAWS_DEFAULT, seed=0):
    """Simulate the winner sequence round by round with the in-force shares."""
    S = np.asarray(share_matrix, dtype=float)
    if S.ndim != 2 or S.shape[0] < 2:
        return {"L_max_mc_mean": "", "L_max_mc_p95": "", "L_max_mc_p_value": "",
                "repeat_prob_mc_mean": "", "repeat_prob_mc_p_value": "", "mc_draws": "",
                "note": "not computable: fewer than 2 rounds"}
    S = S / S.sum(axis=1, keepdims=True)
    rng = np.random.default_rng(seed)
    cum = np.cumsum(S, axis=1)
    u = rng.random((draws, S.shape[0]))
    picks = (u[:, :, None] > cum[None, :, :]).sum(axis=2)
    lmax = _lmax_rows(picks)
    rep = (picks[:, 1:] == picks[:, :-1]).mean(axis=1)
    out = {"L_max_mc_mean": float(lmax.mean()), "L_max_mc_p95": float(np.percentile(lmax, 95)),
           "L_max_mc_p_value": float((np.sum(lmax >= lmax_obs) + 1) / (draws + 1)) if lmax_obs != "" else "",
           "repeat_prob_mc_mean": float(rep.mean()),
           "repeat_prob_mc_p_value": float((np.sum(rep >= repeat_obs) + 1) / (draws + 1)) if repeat_obs != "" else "",
           "mc_draws": draws, "note": "sortition alone, in-force shares round by round; p = Pr[MC >= observed]"}
    return out
