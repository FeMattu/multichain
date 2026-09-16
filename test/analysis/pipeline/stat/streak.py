"""Streaks: are runs of consecutive wins explicable by weighted sortition alone?

Weighted sortition draws independently each round, so streaks are expected — a validator
with 40% of the weight wins three in a row about 6% of the time. The question is never
"were there streaks" but "were there **more** streaks, or longer ones, than independent
weighted draws produce".

The wrong way to answer it is a closed form under equal shares. Shares are neither equal
nor constant here: they move with the weight engine's epoch boundary, with malus, and with
the validator set. So the null is simulated with **the shares that actually governed each
round** — the same round-by-round discipline as :func:`gof.mc_round_by_round_pvalue`.

Two statistics, because they catch different faults:

* ``L_max`` — the longest run of consecutive wins by one validator. Sensitive to a
  validator that occasionally seizes the chain for a stretch.
* ``repeat_prob`` — the fraction of adjacent round pairs won by the same validator.
  Sensitive to a mild, persistent stickiness spread over the whole run, which ``L_max``
  would miss entirely.

A high ``repeat_prob`` with an unremarkable ``L_max`` is the signature of round-robin
leaking through — which is exactly what ``mining-diversity`` at its stock 0.3 produces, and
why the profiles set it to 0.

p-values are ``(hits + 1) / (draws + 1)`` and one-sided: only *more* streaking than the null
is a finding. Fewer consecutive wins than independent draws would give is what a round-robin
looks like, so :func:`observed_streaks` also reports the lower tail separately rather than
hiding it inside a two-sided number.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

from . import ANALYSIS_SEED, MC_STREAK


def observed_streaks(winners: Sequence[str]) -> Dict[str, object]:
    """``L_max`` and the repeat rate of an observed winner sequence.

    The sequence must be in round order. A gap — a round whose winner is unknown — breaks
    a streak rather than joining its neighbours, because pretending two separated wins
    were consecutive would invent the very thing being measured.
    """
    sequence = [w for w in winners if w]
    n = len(sequence)
    if n == 0:
        return {
            "L_max_observed": None,
            "repeat_prob_observed": None,
            "n_rounds": 0,
            "n_repeats": None,
            "note": "not computable: no round has a recorded winner",
        }
    longest = current = 1
    repeats = 0
    for previous, this in zip(sequence, sequence[1:]):
        if this == previous:
            current += 1
            repeats += 1
            longest = max(longest, current)
        else:
            current = 1
    return {
        "L_max_observed": longest,
        "repeat_prob_observed": (repeats / (n - 1)) if n > 1 else None,
        "n_rounds": n,
        "n_repeats": repeats,
        "note": "",
    }


def _longest_runs(picks: np.ndarray) -> np.ndarray:
    """Longest run per simulated replica. ``picks`` is ``draws x rounds`` of class indices."""
    draws, rounds = picks.shape
    if rounds == 0:
        return np.zeros(draws, dtype=np.int64)
    longest = np.ones(draws, dtype=np.int64)
    current = np.ones(draws, dtype=np.int64)
    for r in range(1, rounds):
        same = picks[:, r] == picks[:, r - 1]
        current = np.where(same, current + 1, 1)
        np.maximum(longest, current, out=longest)
    return longest


def mc_streaks(
    share_matrix: Sequence[Sequence[float]],
    lmax_observed: Optional[int],
    repeat_observed: Optional[float],
    draws: int = MC_STREAK,
    seed: int = ANALYSIS_SEED,
) -> Dict[str, object]:
    """Simulate the winner sequence under weighted sortition and compare.

    ``share_matrix`` is ``rounds x validators``: row *r* holds the shares in force for
    round *r*. Rows are re-normalised defensively — a row of zeros would otherwise make
    the inverse-CDF pick the last class every time and quietly manufacture a streak.
    """
    shares = np.asarray(share_matrix, dtype=float)
    if shares.ndim != 2 or shares.shape[0] < 2:
        return {
            "L_max_mc_mean": None,
            "L_max_mc_p95": None,
            "L_max_mc_p_value": None,
            "repeat_prob_mc_mean": None,
            "repeat_prob_mc_p_value": None,
            "streak_mc_draws": 0,
            "note": "not computable: fewer than two rounds with shares in force",
        }

    rounds, classes = shares.shape
    totals = shares.sum(axis=1, keepdims=True)
    usable = (totals > 0).ravel()
    if not usable.any():
        return {
            "L_max_mc_mean": None,
            "L_max_mc_p95": None,
            "L_max_mc_p_value": None,
            "repeat_prob_mc_mean": None,
            "repeat_prob_mc_p_value": None,
            "streak_mc_draws": 0,
            "note": "not computable: every round has zero total weight",
        }
    shares = shares[usable] / totals[usable]
    rounds = shares.shape[0]

    cumulative = np.cumsum(shares, axis=1)
    cumulative[:, -1] = 1.0
    rng = np.random.default_rng(seed)

    lmax = np.empty(draws, dtype=np.int64)
    repeats = np.empty(draws, dtype=float)
    chunk = max(1, min(draws, 4_000_000 // max(1, rounds)))
    done = 0
    while done < draws:
        size = min(chunk, draws - done)
        uniforms = rng.random((size, rounds))
        picks = (uniforms[:, :, None] > cumulative[None, :, :]).sum(axis=2)
        np.clip(picks, 0, classes - 1, out=picks)
        lmax[done:done + size] = _longest_runs(picks)
        repeats[done:done + size] = (picks[:, 1:] == picks[:, :-1]).sum(axis=1) / (rounds - 1)
        done += size

    row: Dict[str, object] = {
        "L_max_mc_mean": float(lmax.mean()),
        "L_max_mc_p95": float(np.percentile(lmax, 95)),
        "repeat_prob_mc_mean": float(repeats.mean()),
        "streak_mc_draws": draws,
        "streak_mc_rounds": int(rounds),
        "note": "",
    }
    row["L_max_mc_p_value"] = (
        None
        if lmax_observed is None
        else (int(np.sum(lmax >= lmax_observed)) + 1) / (draws + 1)
    )
    row["repeat_prob_mc_p_value"] = (
        None
        if repeat_observed is None
        else (int(np.sum(repeats >= repeat_observed)) + 1) / (draws + 1)
    )
    # The lower tail is reported separately rather than folded into a two-sided p-value:
    # fewer repeats than independent draws would give is the signature of a round robin,
    # which is a different finding from "too streaky", not a milder version of it.
    row["repeat_prob_mc_p_value_lower"] = (
        None
        if repeat_observed is None
        else (int(np.sum(repeats <= repeat_observed)) + 1) / (draws + 1)
    )
    return row


def streak_row(
    winners: Sequence[str],
    share_matrix: Sequence[Sequence[float]],
    draws: int = MC_STREAK,
    seed: int = ANALYSIS_SEED,
) -> Dict[str, object]:
    """Observed statistics and their simulated null, in one row."""
    row = dict(observed_streaks(winners))
    row.update(
        mc_streaks(
            share_matrix,
            row.get("L_max_observed"),
            row.get("repeat_prob_observed"),
            draws,
            seed,
        )
    )
    return row


def winners_and_shares(rounds: Sequence[Dict[str, object]], validators: Sequence[str]) -> tuple:
    """Turn phase-2 round rows into ``(winner_sequence, share_matrix)``.

    Rounds with no recorded winner or no weight in force are dropped from **both**, so the
    simulated sequence has the same length as the observed one and the comparison is
    like-for-like.
    """
    winners: List[str] = []
    matrix: List[List[float]] = []
    index = {address: i for i, address in enumerate(validators)}
    for entry in rounds:
        winner = entry.get("winner_address")
        weights = entry.get("weights") or {}
        if not winner or winner not in index:
            continue
        row = [float(weights.get(address, 0.0) or 0.0) for address in validators]
        if sum(row) <= 0:
            continue
        winners.append(str(winner))
        matrix.append(row)
    return winners, matrix


__all__ = ["mc_streaks", "observed_streaks", "streak_row", "winners_and_shares"]
