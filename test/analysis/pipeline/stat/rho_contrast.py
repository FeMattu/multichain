"""The controlled experiment on rho: does the restitution rate reach the weight and the election?

Designed for a run whose profile sets ``traffic.miner_return_overrides``: there some
miners are told to return a lot and others little, in phases, so the differences in rho
between miners are a treatment and not epoch-to-epoch noise. Phase 3 runs it on those
runs by default, and on any other run only when asked (``--rho-contrast``), so the output
of every existing run is unchanged unless the flag is given.

The counterfactual is the same run without the feedback channel. For each round, the
weight in force of every validator is traced back to the WeightEngine row that produced
it (same address, same published weight), and that row's ratio
``W_k_raw / w_k_final = 1 / (lambda * rho_prev + 1 - lambda)`` removes the feedback
factor. What remains is the weight the engine would have published with ``lambda = 0``,
everything else (ESG, tau, malus, dumping) unchanged. Its normalised share ``p_raw`` is
the null "rho has no effect"; ``p_theoretical`` is the null "the election follows the
rho-corrected weight". The observed winners are tested against both.

Causal lag, from the engine's own alignment: the WeightEngine epoch ``k`` reads the
blocks of block-epoch ``k - 1`` and is in force from early in block-epoch ``k``; its
factor uses ``rho`` of engine epoch ``k - 1``, i.e. the restitutions of block-epoch
``k - 2``. The phase a round is *treated* with is therefore the restitution phase of
block-epoch ``engine_epoch_in_force - 2``, which is read from the data, not assumed.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

#: Engine epoch in force -> block-epoch whose restitutions produced its factor.
RESTITUTION_LAG = 2


def phase_index(phases: Sequence[Dict[str, Any]], epoch: int) -> int:
    """0 before the miner's first override phase, else 1 + the index of the phase in force."""
    index = 0
    for k, phase in enumerate(phases):
        if int(phase["from_epoch"]) <= epoch:
            index = k + 1
    return index


def engine_lookup(engine_rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, int], Dict[str, Any]]:
    """``(address, published weight) -> engine row``, with the feedback factor precomputed."""
    table: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for row in engine_rows:
        try:
            published = int(round(float(row["w_k_published"])))
            final = float(row["w_k_final"])
            raw = float(row["W_k_raw"])
        except (KeyError, TypeError, ValueError):
            continue
        if final <= 0 or raw <= 0:
            continue
        table[(row["cluster_head_address"], published)] = {
            "engine_epoch": int(row["epoch"]),
            "factor": final / raw,
            "rho_prev": _float(row.get("rho_prev")),
        }
    return table


def round_shares(
    candidates: Sequence[Dict[str, Any]],
    lookup: Dict[Tuple[str, int], Dict[str, Any]],
) -> Dict[int, Dict[str, Dict[str, Any]]]:
    """``height -> address -> {p_theoretical, p_raw, engine_epoch, factor}``.

    A round is kept only if EVERY candidate's weight traces back to an engine row: a
    partial round would give ``p_raw`` shares that do not sum to one.
    """
    by_height: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        by_height[int(row["height"])].append(row)
    out: Dict[int, Dict[str, Dict[str, Any]]] = {}
    for height, rows in by_height.items():
        entries: Dict[str, Dict[str, Any]] = {}
        complete = True
        for row in rows:
            weff = _float(row.get("weight_effective"))
            p_theo = _float(row.get("p_theoretical"))
            published = _float(row.get("weight_raw"))
            if weff is None or p_theo is None or published is None:
                complete = False
                break
            hit = lookup.get((row["address"], int(round(published))))
            if hit is None:
                complete = False
                break
            entries[row["address"]] = {
                "p_theoretical": p_theo,
                "weight_no_feedback": weff / hit["factor"],
                "engine_epoch": hit["engine_epoch"],
                "factor": hit["factor"],
                "is_winner": str(row.get("is_winner")) == "True",
            }
        # Exactly one winner, or the round is not an election that happened: the tip's
        # own round is evaluated before anyone has mined it.
        if not complete or not entries or sum(e["is_winner"] for e in entries.values()) != 1:
            continue
        total = sum(e["weight_no_feedback"] for e in entries.values())
        if total <= 0:
            continue
        for entry in entries.values():
            entry["p_raw"] = entry["weight_no_feedback"] / total
        out[height] = entries
    return out


def _float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def likelihood_ratio_test(
    with_feedback: Sequence[Sequence[float]],
    without_feedback: Sequence[Sequence[float]],
    winners: Sequence[int],
    draws: int,
    seed: int,
) -> Dict[str, Any]:
    """Log-likelihood ratio of the observed winners, feedback against no feedback.

    ``LLR = sum_rounds log( p_with[winner] / p_without[winner] )``. For two simple
    hypotheses it is the most powerful test (Neyman-Pearson), and unlike a chi-square on
    totals it uses WHICH round each block was won in: a feedback that raises a miner's
    share in some epochs and lowers it in others cancels in the totals, not here.

    Both nulls are simulated round by round with the shares actually in force:
    ``p_without`` gives the p-value of "rho has no effect" (large LLR is evidence
    against it); ``p_with`` gives where the observation falls under the feedback model
    (it should be a typical value, not an extreme one).
    """
    pw = np.asarray(with_feedback, dtype=float)
    pn = np.asarray(without_feedback, dtype=float)
    pw = pw / pw.sum(axis=1, keepdims=True)
    pn = pn / pn.sum(axis=1, keepdims=True)
    rounds = pw.shape[0]
    log_ratio = np.log(pw / pn)
    idx = np.arange(rounds)
    observed = float(log_ratio[idx, np.asarray(winners)].sum())
    rng = np.random.default_rng(seed)

    def simulate(shares: np.ndarray) -> np.ndarray:
        cumulative = np.cumsum(shares, axis=1)
        cumulative[:, -1] = 1.0
        out = np.empty(draws)
        chunk = max(1, min(draws, 2_000_000 // max(1, rounds)))
        done = 0
        while done < draws:
            size = min(chunk, draws - done)
            picks = (rng.random((size, rounds))[:, :, None] > cumulative[None]).sum(axis=2)
            np.clip(picks, 0, shares.shape[1] - 1, out=picks)
            out[done:done + size] = log_ratio[idx[None, :], picks].sum(axis=1)
            done += size
        return out

    under_none = simulate(pn)
    under_feedback = simulate(pw)
    sd_none = float(under_none.std())
    return {
        "n_rounds": rounds,
        "llr_observed": observed,
        "llr_mean_without_feedback": float(under_none.mean()),
        "llr_sd_without_feedback": sd_none,
        "p_value_without_feedback": (int((under_none >= observed - 1e-12).sum()) + 1) / (draws + 1),
        "z_vs_without_feedback": (observed - float(under_none.mean())) / sd_none if sd_none > 0 else None,
        "llr_mean_with_feedback": float(under_feedback.mean()),
        "llr_sd_with_feedback": float(under_feedback.std()),
        "quantile_under_feedback": float((under_feedback <= observed).mean()),
        "draws": draws,
    }
