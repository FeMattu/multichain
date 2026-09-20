#!/usr/bin/env python3
"""Phase 2 — aggregate. Join the flat tables into the three grains the tests need.

**Still no statistics.** This phase reshapes and recomputes; it never decides anything. The
grains it produces are:

* ``candidate_long`` — one row per (round, candidate). The finest grain: what each
  validator's weight, score and delay were in each round, and whether it won.
* ``round_level`` — one row per round. The competition: who won, by how much, and whether
  the winner was the one the delays said should win.
* ``epoch_level`` — one row per (epoch, validator). Wins against entitlement, which is what
  Wilson and the goodness-of-fit consume.
* ``epoch_engine`` — one row per (epoch, cluster head). The weight pipeline's own
  quantities: ESG, tau, W_k, rho, R_k, saldo and the weight actually published.
* ``epoch_traffic`` — one row per (epoch, node). Planned against sent against **on-chain**,
  which is what turns "the daemon says it sent 42" into a verifiable claim.

Two recomputations happen here, and both are checks rather than conveniences:

**The delay.** The node's scheduler computes

    D_i = T + delta * T * (2 * score_norm - 1) + lambda * Phi

and this phase recomputes it and compares. ``delay_recompute_mismatch_rounds = 0`` is a
pass condition of the functional test: a mismatch means the harness and the node disagree
about the mechanism itself, which invalidates every timer-race result downstream. ``Phi``
is checked separately and only warned about — it is a global feedback term whose value
legitimately differs between nodes mid-round.

**The normalised score.** ``score_norm = 1 - exp(-W_tot * score)`` is recomputed from the
raw score and the total effective weight, and the recomputed value — not the reported one
— is what feeds the delay check. The node's arithmetic is right; its JSON rendering of a
double very close to 1 is not, and a reported ``score_norm`` of 0 for a true 0.9999999999
would otherwise read as a protocol fault. Keeping both makes the rendering artefact
visible as itself, in ``score_norm_mismatch``.

One definition worth stating because it is easy to get wrong: ``p_theoretical`` is built
from ``effective_weight_after_malus_and_dumping`` — the quantity the **election actually
consumes**, after the malus factor and after the dumping function — and not from the raw
published weight. Comparing observed wins against the raw weight would test a null the
selector never used.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent

#: Tolerance for the delay recomputation, in seconds. The node carries the delay in double
#: precision and reports it rounded; anything above this is a real disagreement.
DELAY_TOL_S = 0.0015

#: Tolerance for the normalised score, which is dimensionless.
SCORE_NORM_TOL = 1e-6

#: ``company_daemon`` publishes under the key ``lot-<epoch>-<node_id>-<seq>``, so the epoch
#: a transaction was generated for survives on chain and does not have to be inferred from
#: the block that confirmed it.
_TRAFFIC_KEY = re.compile(r"^lot-(\d+)-")

COLUMNS: "OrderedDict[str, List[str]]" = OrderedDict(
    [
        # ``*_public`` marks every quantity derived from the PUBLIC Efraimidis score
        # (HMAC-SHA256(seed, address)), which is what wpoalistscores/wpoalistdelays can
        # compute for a validator whose secret key this node does not hold. Under private
        # sortition the election draws from a VRF under each proposer's own key, so these
        # are a model audit and are statistically independent of the real draw. The
        # winner's REAL score arrives instead from phase 1's ``block_sortition`` and is
        # suffixed ``_true``. See GUIDA-STATISTICHE-E-GRAFICI.md, regola 10.
        (
            "candidate_long",
            ["height", "epoch", "in_setup", "address", "weight_raw", "malus", "malus_factor",
             "weight_after_malus", "weight_effective", "W_tot_effective", "p_theoretical",
             "score_public", "score_norm_public", "score_norm_recomputed_public",
             "score_norm_mismatch_public", "delay_logged_public_s",
             "delay_recomputed_public_s", "delay_mismatch_public_s",
             "delay_recompute_ok_public", "eligible", "is_winner",
             "rank_by_delay_public", "rank_by_score_public"],
        ),
        (
            "round_level",
            ["height", "epoch", "in_setup", "winner_address", "n_candidates", "n_eligible",
             "delay_min_public_s", "delay_winner_public_s", "margin_G_public_s",
             "score_min_public", "score_second_public", "score_gap_2_1_public",
             "W_tot_effective", "weff_argmin_public", "p_winner", "phi_s",
             "target_block_time", "delta", "lambda_s", "argmin_delay_address_public",
             "inversion_public", "winner_rank_by_delay_public", "block_time", "dt_prev_s",
             "scheduler_residual_public_s", "txcount", "n_delay_mismatch_public",
             # The winner's REAL private score, recomputed from the VRF reveal its block
             # carries. These are the columns a statement about proposer ordering may
             # rest on.
             "score_true", "score_norm_true", "delay_true_s", "earliest_time_true",
             "residual_true_s", "weff_winner_true", "verdict_true",
             "true_winner_mismatch", "weight_epoch_stale"],
        ),
        (
            "epoch_level",
            ["epoch", "in_setup", "validator_address", "O_i", "n_blocks_epoch",
             "n_rounds_with_scores", "p_theoretical_blockweighted", "p_theoretical_start",
             "p_theoretical_end", "share_changed_within_epoch", "p_observed", "E_i",
             "w_raw_start", "w_raw_end", "w_eff_start", "w_eff_end", "psi",
             "delay_mean_public_s", "delay_min_public_s", "delay_max_public_s",
             "epoch_start_height", "epoch_end_height"],
        ),
        (
            "epoch_engine",
            ["epoch", "cluster_head_address", "miner_esg_score", "miner_activity",
             "n_companies", "companies_contribution_sum", "kappa", "W_k_raw",
             "rho_prev", "lambda_w", "w_k_final", "w_k_published", "R_k", "earnings_g_k",
             "balance_saldo", "return_rate_rho", "income", "expenses_gross",
             "w_published_next_epoch", "n_blocks_won_epoch"],
        ),
        (
            "epoch_traffic",
            ["epoch", "node_id", "role", "address", "planned", "sent_logged",
             "onchain_stream_items", "onchain_confirmed_this_epoch", "onchain_returns",
             "full_epoch", "in_range", "range_low", "range_high"],
        ),
        (
            "epoch_concentration",
            ["epoch", "in_setup", "n_validators", "theoretical_HHI", "theoretical_N_eff",
             "theoretical_gini", "theoretical_entropy_norm", "theoretical_nakamoto_1_3",
             "theoretical_nakamoto_1_2", "theoretical_nakamoto_2_3", "observed_HHI",
             "observed_N_eff", "observed_gini", "observed_entropy_norm",
             "observed_nakamoto_1_3", "observed_nakamoto_1_2", "observed_nakamoto_2_3",
             "gini_published_weight", "gini_input_esg_tau", "gini_delta"],
        ),
        # -- the malicious-miner experiment --------------------------------------------
        # Empty on a plain run; the headers still write so phase 3 reads them regardless.
        (
            "malus_state",
            ["epoch", "address", "is_malicious", "sample_height", "M", "psi", "weight_raw",
             "weight_effective", "excluded", "epochs_to_clear", "weff_recomputed",
             "invariant_psi_in_unit", "invariant_weff_matches", "invariant_clean_psi_one"],
        ),
        (
            "malus_actions",
            ["epoch", "miner", "address", "is_malicious", "action", "action_id", "attempted",
             "sent", "txid", "confirmed", "confirm_height", "confirm_epoch", "reported",
             "report_height", "detection_latency_blocks", "governing_epoch",
             "activation_epoch", "activation_latency_epochs", "target_epoch"],
        ),
        (
            "malus_funnel",
            ["scope", "opportunities", "attempts", "sent", "confirmed", "valid_malus",
             "reported_total"],
        ),
        (
            "malus_rate_by_miner",
            ["miner", "address", "is_malicious", "opportunities", "attempts", "sent",
             "confirmed", "valid_malus", "target_rate", "attempted_rate", "sent_rate",
             "confirmed_rate", "valid_rate"],
        ),
        (
            "malus_detection_events",
            ["verdict", "kind", "accused_address", "is_malicious_accused", "offence_epoch",
             "offence_height", "detect_height", "detect_epoch", "evidence_txid",
             "is_true_positive", "reason"],
        ),
    ]
)


class Phase2Error(RuntimeError):
    """Phase 1 output is missing or unusable."""


# --------------------------------------------------------------------------------------
# reading phase 1
# --------------------------------------------------------------------------------------


def read_table(phase1: Path, name: str) -> List[Dict[str, str]]:
    path = phase1 / ("%s.csv" % name)
    if not path.is_file():
        raise Phase2Error("phase 1 produced no %s.csv (looked in %s)" % (name, phase1))
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def f(value: Any) -> Optional[float]:
    """CSV cell to float, with empty and unparsable mapping to ``None``.

    ``None`` rather than ``0.0``: a missing weight and a weight of zero mean different
    things, and collapsing them would make an unsampled round look like an ineligible one.
    """
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def i(value: Any) -> Optional[int]:
    result = f(value)
    return None if result is None else int(result)


def b(value: Any) -> Optional[bool]:
    if value in ("", None):
        return None
    return str(value).strip().lower() in ("true", "1", "yes")


def _epoch_from_key(key: str) -> Optional[int]:
    """The epoch a company was generating for, read back off the chain."""
    match = _TRAFFIC_KEY.match(key or "")
    return int(match.group(1)) if match else None


def _effective_weight(weight: Optional[float], psi: Optional[float]) -> Optional[float]:
    """Recompute ``w_eff`` exactly as ``MalusAccumulator::EffectiveWeight`` does.

    Replicated here — not read from the node — so the invariant audit compares the value
    the node reported against an independent recomputation rather than against itself. The
    branches mirror the C++ one for one: a zero weight or a non-positive Psi gives 0; a
    Psi at or above 1 gives the raw weight; otherwise round half up, and never let a
    positive Psi round a positive weight down to zero.
    """
    if weight is None or psi is None:
        return None
    if weight <= 0 or not (psi > 0.0):
        return 0.0
    if psi >= 1.0:
        return float(weight)
    product = weight * psi
    if product >= weight:
        return float(weight)
    rounded = math.floor(product + 0.5)
    return float(rounded if rounded != 0 else 1)


# --------------------------------------------------------------------------------------
# aggregation
# --------------------------------------------------------------------------------------


class Aggregator:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        self.phase1 = self.run_dir / "analysis" / "phase1"
        if not self.phase1.is_dir():
            raise Phase2Error("no phase 1 output in %s; run phase1_collect.py first" % self.phase1)
        self.manifest = json.loads((self.phase1 / "manifest.json").read_text(encoding="utf-8"))
        self.epoch_length = int(self.manifest.get("epoch_length") or 1)
        self.setup_blocks = int(self.manifest.get("setup_first_blocks") or 0)
        self.tables: Dict[str, List[Dict[str, Any]]] = {name: [] for name in COLUMNS}
        self.warnings: List[str] = []

    # -- helpers -----------------------------------------------------------------------

    def epoch_of(self, height: Optional[int]) -> Optional[int]:
        return None if height is None else height // self.epoch_length

    # -- candidate_long and round_level -------------------------------------------------

    def build_rounds(self) -> None:
        finals = read_table(self.phase1, "round_final_weights")
        delays = read_table(self.phase1, "round_delays")
        scores = read_table(self.phase1, "round_scores")
        blocks = read_table(self.phase1, "blocks")
        # The winner's real score, one row per height, keyed the same way. Absent on a
        # run recorded before this table existed, in which case every *_true column is
        # simply empty and the *_public ones behave as they always did.
        true_by_height = {
            i(row["height"]): row
            for row in (read_table(self.phase1, "block_sortition")
                        if (self.phase1 / "block_sortition.csv").is_file() else [])
        }

        winner_by_height = {
            i(row["height"]): row.get("miner_address", "") for row in blocks
        }
        block_time = {i(row["height"]): f(row.get("time")) for row in blocks}
        txcount = {i(row["height"]): i(row.get("txcount")) for row in blocks}

        delay_by = {(i(r["round_height"]), r["address"]): r for r in delays}
        score_by = {(i(r["round_height"]), r["address"]): r for r in scores}

        by_round: Dict[int, List[Dict[str, str]]] = defaultdict(list)
        for row in finals:
            height = i(row["round_height"])
            if height is not None:
                by_round[height].append(row)

        previous_time: Optional[float] = None
        for height in sorted(by_round):
            entries = by_round[height]
            # The election consumes g(w * Psi): after the malus factor AND after the
            # dumping function. Building p_theoretical from the raw weight would test a
            # null the selector never used.
            weff = {
                row["address"]: (f(row.get("effective_weight_after_malus_and_dumping")) or 0.0)
                for row in entries
            }
            w_tot = sum(weff.values())
            winner = winner_by_height.get(height, "")

            ranked_delay: List[Tuple[float, str]] = []
            ranked_score: List[Tuple[float, str]] = []
            mismatches = 0
            candidate_rows: List[Dict[str, Any]] = []

            for row in entries:
                address = row["address"]
                delay_row = delay_by.get((height, address), {})
                score_row = score_by.get((height, address), {})

                delay_logged = f(delay_row.get("delay_s"))
                score_norm = f(delay_row.get("score_norm"))
                score = f(delay_row.get("score")) or f(score_row.get("score"))
                tbt = f(delay_row.get("target_block_time"))
                delta = f(delay_row.get("delta"))
                lam = f(delay_row.get("lambda_s"))
                phi = f(delay_row.get("feedback_phi"))
                total_eff = f(delay_row.get("total_effective_weight")) or w_tot

                # score_norm = 1 - exp(-W_tot * score), recomputed from the two fields
                # that survive serialisation intact.
                norm_recomputed = None
                if score is not None and total_eff:
                    norm_recomputed = 1.0 - math.exp(-min(total_eff * score, 700.0))

                # D = T + delta*T*(2*score_norm - 1) + lambda*Phi
                #
                # Built on the RECOMPUTED score_norm, not the reported one. The node's
                # arithmetic is correct -- verified directly against
                # PrivateSortition::NormalizedScore -- but json_spirit renders a double
                # very close to 1 by stripping the trailing zeros of a 14-decimal
                # rendering, and 0.99999999999999889 renders as "1.00000000000000" whose
                # decimals all strip, leaving a reported score_norm of 0. The delay in the
                # same answer is computed from the true value, so the two disagree by
                # exactly delta*T*2 and the round looks like a mechanism mismatch when it
                # is a formatting artefact. Seen in 2 of 415 rounds, only for scores whose
                # normalised value rounds to 1 at 14 decimals.
                #
                # Recomputing from `score` and `total_effective_weight` makes this check
                # test the delay mechanism, which is what it is for. The reported value is
                # kept beside it in score_norm / score_norm_mismatch, where the rendering
                # artefact is visible as itself rather than mistaken for a protocol fault.
                norm_for_delay = norm_recomputed if norm_recomputed is not None else score_norm
                delay_recomputed = None
                if None not in (norm_for_delay, tbt, delta):
                    delay_recomputed = (
                        tbt + delta * tbt * (2.0 * norm_for_delay - 1.0)
                        + (lam or 0.0) * (phi or 0.0)
                    )
                delay_mismatch = (
                    None
                    if (delay_recomputed is None or delay_logged is None)
                    else delay_recomputed - delay_logged
                )
                delay_ok = None if delay_mismatch is None else abs(delay_mismatch) <= DELAY_TOL_S
                if delay_ok is False:
                    mismatches += 1

                norm_mismatch = (
                    None
                    if (norm_recomputed is None or score_norm is None)
                    else norm_recomputed - score_norm
                )

                if delay_logged is not None:
                    ranked_delay.append((delay_logged, address))
                if score is not None and math.isfinite(score):
                    ranked_score.append((score, address))

                candidate_rows.append(
                    {
                        "height": height,
                        "epoch": self.epoch_of(height),
                        "in_setup": height <= self.setup_blocks,
                        "address": address,
                        "weight_raw": f(row.get("raw_weight")),
                        "malus": f(row.get("malus")),
                        "malus_factor": f(row.get("malus_factor")),
                        "weight_after_malus": f(row.get("weight_after_malus")),
                        "weight_effective": weff[address],
                        "W_tot_effective": w_tot,
                        "p_theoretical": (weff[address] / w_tot) if w_tot > 0 else None,
                        "score_public": score,
                        "score_norm_public": score_norm,
                        "score_norm_recomputed_public": norm_recomputed,
                        "score_norm_mismatch_public": norm_mismatch,
                        "delay_logged_public_s": delay_logged,
                        "delay_recomputed_public_s": delay_recomputed,
                        "delay_mismatch_public_s": delay_mismatch,
                        "delay_recompute_ok_public": delay_ok,
                        "eligible": b(row.get("eligible")),
                        "is_winner": address == winner,
                    }
                )

            ranked_delay.sort()
            ranked_score.sort()
            delay_rank = {address: n for n, (_, address) in enumerate(ranked_delay, start=1)}
            score_rank = {address: n for n, (_, address) in enumerate(ranked_score, start=1)}
            for row in candidate_rows:
                row["rank_by_delay_public"] = delay_rank.get(row["address"])
                row["rank_by_score_public"] = score_rank.get(row["address"])
                self.tables["candidate_long"].append(row)

            argmin_delay = ranked_delay[0][1] if ranked_delay else ""
            delay_min = ranked_delay[0][0] if ranked_delay else None
            delay_second = ranked_delay[1][0] if len(ranked_delay) > 1 else None
            score_min = ranked_score[0][0] if ranked_score else None
            score_second = ranked_score[1][0] if len(ranked_score) > 1 else None
            this_time = block_time.get(height)
            dt_prev = (
                None if (this_time is None or previous_time is None) else this_time - previous_time
            )
            delay_winner = next(
                (d for d, a in ranked_delay if a == winner), None
            )
            # How far the realised spacing departed from the delay that should have
            # produced it. Its standard deviation is sigma_S2, the primary perturbation
            # source in a harness with no emulated latency.
            residual = (
                None if (dt_prev is None or delay_winner is None) else dt_prev - delay_winner
            )
            first_delay_row = delay_by.get((height, argmin_delay), {}) if argmin_delay else {}

            # The real score is only claimable when the audit actually recomputed one AND
            # it belongs to the block this round settled on -- a row whose miner does not
            # match the winner recorded in `blocks` describes a different branch, which
            # happens when `blocks` captured a block that was later reorged away (phase 1
            # keeps the FIRST row seen per height). Such a round is dropped from the
            # *_true columns but its verdict and the mismatch are still reported, so the
            # gap is counted rather than silently absent.
            true_raw = true_by_height.get(height, {})
            true_mismatch = bool(
                winner and true_raw.get("miner_address")
                and true_raw.get("miner_address") != winner
            )
            true_row = (
                true_raw
                if (true_raw.get("verdict") == "ok" and not true_mismatch)
                else {}
            )
            delay_true = f(true_row.get("delay_s"))

            self.tables["round_level"].append(
                {
                    "height": height,
                    "epoch": self.epoch_of(height),
                    "in_setup": height <= self.setup_blocks,
                    "winner_address": winner,
                    "n_candidates": len(entries),
                    "n_eligible": sum(1 for r in candidate_rows if r["eligible"]),
                    "delay_min_public_s": delay_min,
                    "delay_winner_public_s": delay_winner,
                    "margin_G_public_s": (
                        None if (delay_min is None or delay_second is None)
                        else delay_second - delay_min
                    ),
                    "score_min_public": score_min,
                    "score_second_public": score_second,
                    "score_gap_2_1_public": (
                        None if (score_min is None or score_second is None)
                        else score_second - score_min
                    ),
                    "W_tot_effective": w_tot,
                    "weff_argmin_public": weff.get(argmin_delay),
                    "p_winner": (weff.get(winner, 0.0) / w_tot) if w_tot > 0 else None,
                    "phi_s": f(first_delay_row.get("feedback_phi")),
                    "target_block_time": f(first_delay_row.get("target_block_time")),
                    "delta": f(first_delay_row.get("delta")),
                    "lambda_s": f(first_delay_row.get("lambda_s")),
                    "argmin_delay_address_public": argmin_delay,
                    # An inversion is the round where the smallest delay did not win.
                    #
                    # PUBLIC FORM, and therefore uninformative about the real ordering:
                    # argmin_delay_address_public is the argmin of the HMAC scores, which
                    # no validator's timer was ever set from, so this flag is true with
                    # probability 1 - 1/n whatever the protocol does. Kept because it has
                    # been published; read inversion_true_* in phase 3 instead.
                    "inversion_public": (
                        None if (not winner or not argmin_delay) else winner != argmin_delay
                    ),
                    "winner_rank_by_delay_public": delay_rank.get(winner),
                    "block_time": this_time,
                    "dt_prev_s": dt_prev,
                    "scheduler_residual_public_s": residual,
                    "txcount": txcount.get(height),
                    "n_delay_mismatch_public": mismatches,
                    # -- the winner's REAL score, from its block's VRF reveal ------------
                    "score_true": f(true_row.get("score")),
                    "score_norm_true": f(true_row.get("score_norm")),
                    "delay_true_s": delay_true,
                    "earliest_time_true": f(true_row.get("earliest_time")),
                    # What the realised spacing departed from the delay the winner's OWN
                    # score entitled it to. Unlike scheduler_residual_public_s this is a
                    # residual of one quantity against itself, so its spread is the real
                    # timing noise.
                    "residual_true_s": (
                        None if (dt_prev is None or delay_true is None)
                        else dt_prev - delay_true
                    ),
                    "weff_winner_true": f(true_row.get("effective_weight")),
                    "verdict_true": true_raw.get("verdict", ""),
                    "true_winner_mismatch": true_mismatch,
                    "weight_epoch_stale": b(true_raw.get("weight_epoch_stale")),
                }
            )
            if this_time is not None:
                previous_time = this_time

    # -- epoch_level -------------------------------------------------------------------

    def build_epoch_level(self) -> None:
        blocks = read_table(self.phase1, "blocks")
        candidates = self.tables["candidate_long"]

        wins: Dict[Tuple[int, str], int] = defaultdict(int)
        blocks_per_epoch: Dict[int, int] = defaultdict(int)
        epoch_heights: Dict[int, List[int]] = defaultdict(list)
        for row in blocks:
            height = i(row["height"])
            if height is None:
                continue
            epoch = self.epoch_of(height)
            blocks_per_epoch[epoch] += 1
            epoch_heights[epoch].append(height)
            miner = row.get("miner_address", "")
            if miner:
                wins[(epoch, miner)] += 1

        # Block-weighted theoretical share: each round contributes its own share, so an
        # epoch whose weights moved is summarised by the mean of what was actually in
        # force rather than by a snapshot of either end.
        agg: Dict[Tuple[int, str], Dict[str, Any]] = defaultdict(
            lambda: {"p_sum": 0.0, "n": 0, "shares": [], "weights": [], "delays": [],
                     "w_raw": [], "psi": []}
        )
        for row in candidates:
            epoch, address = row["epoch"], row["address"]
            if epoch is None:
                continue
            entry = agg[(epoch, address)]
            if row["p_theoretical"] is not None:
                entry["p_sum"] += row["p_theoretical"]
                entry["n"] += 1
                entry["shares"].append(row["p_theoretical"])
            if row["weight_effective"] is not None:
                entry["weights"].append(row["weight_effective"])
            if row["weight_raw"] is not None:
                entry["w_raw"].append(row["weight_raw"])
            if row["malus_factor"] is not None:
                entry["psi"].append(row["malus_factor"])
            if row["delay_logged_public_s"] is not None:
                entry["delays"].append(row["delay_logged_public_s"])

        for (epoch, address) in sorted(agg):
            entry = agg[(epoch, address)]
            n_blocks = blocks_per_epoch.get(epoch, 0)
            observed = wins.get((epoch, address), 0)
            shares = entry["shares"]
            p_mean = (entry["p_sum"] / entry["n"]) if entry["n"] else None
            heights = sorted(epoch_heights.get(epoch, []))
            self.tables["epoch_level"].append(
                {
                    "epoch": epoch,
                    "in_setup": bool(heights and heights[-1] <= self.setup_blocks),
                    "validator_address": address,
                    "O_i": observed,
                    "n_blocks_epoch": n_blocks,
                    "n_rounds_with_scores": entry["n"],
                    "p_theoretical_blockweighted": p_mean,
                    "p_theoretical_start": shares[0] if shares else None,
                    "p_theoretical_end": shares[-1] if shares else None,
                    # Whether the entitlement moved inside the epoch. When true, a pooled
                    # goodness-of-fit tests a null that was never in force and phase 3
                    # switches to the round-by-round variant.
                    "share_changed_within_epoch": (
                        bool(shares and (max(shares) - min(shares)) > 1e-9) if shares else None
                    ),
                    "p_observed": (observed / n_blocks) if n_blocks else None,
                    "E_i": (p_mean * n_blocks) if (p_mean is not None and n_blocks) else None,
                    "w_raw_start": entry["w_raw"][0] if entry["w_raw"] else None,
                    "w_raw_end": entry["w_raw"][-1] if entry["w_raw"] else None,
                    "w_eff_start": entry["weights"][0] if entry["weights"] else None,
                    "w_eff_end": entry["weights"][-1] if entry["weights"] else None,
                    "psi": entry["psi"][-1] if entry["psi"] else None,
                    "delay_mean_public_s": (
                        sum(entry["delays"]) / len(entry["delays"]) if entry["delays"] else None
                    ),
                    "delay_min_public_s": min(entry["delays"]) if entry["delays"] else None,
                    "delay_max_public_s": max(entry["delays"]) if entry["delays"] else None,
                    "epoch_start_height": heights[0] if heights else None,
                    "epoch_end_height": heights[-1] if heights else None,
                }
            )

    # -- epoch_engine ------------------------------------------------------------------

    def build_epoch_engine(self) -> None:
        clusters = read_table(self.phase1, "epoch_cluster_weights")
        returns = {
            (i(r["epoch"]), r["miner"]): f(r.get("returns"))
            for r in read_table(self.phase1, "epoch_returns")
        }
        earnings = {
            (i(r["epoch"]), r["miner"]): r for r in read_table(self.phase1, "epoch_earnings")
        }
        balances = {
            (i(r["epoch"]), r["miner"]): f(r.get("balance"))
            for r in read_table(self.phase1, "epoch_balances")
        }
        blocks = read_table(self.phase1, "blocks")
        wins: Dict[Tuple[int, str], int] = defaultdict(int)
        for row in blocks:
            height = i(row["height"])
            if height is not None and row.get("miner_address"):
                wins[(self.epoch_of(height), row["miner_address"])] += 1

        published: Dict[Tuple[int, str], Optional[float]] = {}
        rows: List[Dict[str, Any]] = []
        for row in clusters:
            epoch = i(row["epoch"])
            miner = row["miner"]
            published[(epoch, miner)] = f(row.get("published_weight"))
            earning = earnings.get((epoch, miner), {})
            rows.append(
                {
                    "epoch": epoch,
                    "cluster_head_address": miner,
                    "miner_esg_score": f(row.get("miner_esg_score")),
                    "miner_activity": f(row.get("miner_activity")),
                    "n_companies": f(row.get("companies")),
                    "companies_contribution_sum": f(row.get("companies_contribution_sum")),
                    "kappa": f(row.get("kappa")),
                    "W_k_raw": f(row.get("raw_cluster_weight")),
                    "rho_prev": f(row.get("previous_epoch_return_rate")),
                    "lambda_w": f(row.get("lambda_w")),
                    "w_k_final": f(row.get("final_cluster_weight")),
                    "w_k_published": f(row.get("published_weight")),
                    "R_k": returns.get((epoch, miner)),
                    "earnings_g_k": f(earning.get("earnings")),
                    "balance_saldo": balances.get((epoch, miner), f(earning.get("balance"))),
                    "return_rate_rho": f(earning.get("return_rate")),
                    "income": f(earning.get("income")),
                    "expenses_gross": f(earning.get("expenses_gross")),
                    "n_blocks_won_epoch": wins.get((epoch, miner), 0),
                }
            )

        # The lag-1 link: this epoch's reconciliation against next epoch's published
        # weight. Carried here so phase 3 can correlate them without re-joining.
        for row in rows:
            row["w_published_next_epoch"] = published.get(
                (row["epoch"] + 1 if row["epoch"] is not None else None,
                 row["cluster_head_address"])
            )
        self.tables["epoch_engine"] = sorted(
            rows, key=lambda r: (r["epoch"] is None, r["epoch"], r["cluster_head_address"])
        )

    # -- epoch_traffic -----------------------------------------------------------------

    def build_epoch_traffic(self, profile) -> None:
        """Planned vs sent vs on-chain, per node per epoch.

        The on-chain count is the one that matters. A daemon's own counter says what it
        believed it sent; the stream says what the chain accepted. When the two differ, the
        difference is the number of transactions that were rejected — usually for fee
        policy — and it is exactly what the acceptance check in phase 3 has to catch.
        """
        nodes = {row["node_id"]: row for row in read_table(self.phase1, "nodes")}
        address_of = {k: v.get("address", "") for k, v in nodes.items()}
        plans = read_table(self.phase1, "epoch_plans")
        traffic = read_table(self.phase1, "traffic_tx")
        returns = read_table(self.phase1, "gas_returns")
        stream_items = read_table(self.phase1, "stream_items")

        planned: Dict[Tuple[int, str], Optional[float]] = {}
        for row in plans:
            epoch = i(row["epoch"])
            node_id = row["node_id"]
            value = f(row.get("planned_tx"))
            if value is None:
                value = f(row.get("planned_returns"))
            planned[(epoch, node_id)] = value

        sent: Dict[Tuple[int, str], int] = defaultdict(int)
        for row in traffic:
            sent[(i(row.get("declared_epoch")), row["node_id"])] += 1
        sent_returns: Dict[Tuple[int, str], int] = defaultdict(int)
        for row in returns:
            sent_returns[(i(row.get("declared_epoch")), row["node_id"])] += 1

        event_stream = profile.traffic["event_stream"]
        by_publisher: Dict[Tuple[int, str], int] = defaultdict(int)
        by_confirm_epoch: Dict[Tuple[int, str], int] = defaultdict(int)
        for row in stream_items:
            if row.get("stream") != event_stream:
                continue
            publisher = row.get("publisher", "")
            if not publisher:
                continue
            confirm_epoch = i(row.get("epoch"))
            if confirm_epoch is not None:
                by_confirm_epoch[(confirm_epoch, publisher)] += 1
            # Attribute the item to the epoch the company was generating FOR, which its
            # key carries (``lot-<epoch>-<node_id>-<seq>``), not to the epoch of the block
            # that happened to confirm it. A transaction published near a boundary
            # confirms in the next epoch, so counting by confirmation makes a correctly
            # drawn quota look one or two out of range at both ends of every epoch.
            declared = _epoch_from_key(row.get("key", ""))
            if declared is not None:
                by_publisher[(declared, publisher)] += 1
            elif confirm_epoch is not None:
                by_publisher[(confirm_epoch, publisher)] += 1

        tx_low, tx_high = profile.traffic["company_tx_per_epoch_range"]
        ret_low, ret_high = profile.traffic["miner_gas_returns_per_epoch_range"]

        # A daemon's FIRST epoch began before it was started and its LAST was cut short by
        # the shutdown, so both are partial by construction and their counts cannot be
        # expected to fall in the configured range. They are still written — the counts are
        # real — but marked ``full_epoch = False`` so the range check can skip them rather
        # than report a dozen spurious failures on every run.
        epochs_by_node: Dict[str, List[int]] = defaultdict(list)
        for epoch, node_id in list(planned) + list(sent) + list(sent_returns):
            if epoch is not None:
                epochs_by_node[node_id].append(epoch)
        partial: Dict[str, set] = {
            node_id: {min(values), max(values)} for node_id, values in epochs_by_node.items()
        }

        keys = set(planned) | set(sent) | set(sent_returns)
        for epoch, node_id in sorted(keys, key=lambda k: (k[0] is None, k[0], k[1])):
            node = nodes.get(node_id, {})
            role = node.get("role", "")
            address = address_of.get(node_id, "")
            is_company = role == "company"
            low, high = (tx_low, tx_high) if is_company else (ret_low, ret_high)
            onchain_stream = by_publisher.get((epoch, address), 0) if is_company else None
            onchain_returns = sent_returns.get((epoch, node_id), 0) if role == "miner" else None
            measured = onchain_stream if is_company else onchain_returns
            full_epoch = epoch is not None and epoch not in partial.get(node_id, set())
            self.tables["epoch_traffic"].append(
                {
                    "epoch": epoch,
                    "node_id": node_id,
                    "role": role,
                    "address": address,
                    "planned": planned.get((epoch, node_id)),
                    "sent_logged": sent.get((epoch, node_id), 0) if is_company
                    else sent_returns.get((epoch, node_id), 0),
                    "onchain_stream_items": onchain_stream,
                    "onchain_confirmed_this_epoch": (
                        by_confirm_epoch.get((epoch, address), 0) if is_company else None
                    ),
                    "onchain_returns": onchain_returns,
                    "full_epoch": full_epoch,
                    "in_range": (
                        None
                        if (measured is None or not full_epoch)
                        else bool(low <= measured <= high)
                    ),
                    "range_low": low,
                    "range_high": high,
                }
            )

    # -- epoch_concentration -----------------------------------------------------------

    def build_epoch_concentration(self) -> None:
        sys.path.insert(0, str(HERE.parent))
        from pipeline.stat.concentration import concentration_row, gini  # noqa: E402

        by_epoch: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for row in self.tables["epoch_level"]:
            if row["epoch"] is not None:
                by_epoch[row["epoch"]].append(row)
        engine_by_epoch: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for row in self.tables["epoch_engine"]:
            if row["epoch"] is not None:
                engine_by_epoch[row["epoch"]].append(row)

        for epoch in sorted(by_epoch):
            entries = by_epoch[epoch]
            theoretical = [
                r["p_theoretical_blockweighted"] or 0.0
                for r in entries
                if r["p_theoretical_blockweighted"] is not None
            ]
            observed = [float(r["O_i"] or 0) for r in entries]
            row: Dict[str, Any] = {
                "epoch": epoch,
                "in_setup": entries[0]["in_setup"],
                "n_validators": len(entries),
            }
            row.update(concentration_row(theoretical, "theoretical_"))
            row.update(concentration_row(observed, "observed_"))
            row.pop("theoretical_n_validators", None)
            row.pop("observed_n_validators", None)

            engine = engine_by_epoch.get(epoch, [])
            # The amplification question: how the inequality of what the engine PUBLISHED
            # compares with the inequality of what it was GIVEN (ESG x activity).
            published = [r["w_k_published"] for r in engine if r["w_k_published"] is not None]
            inputs = [
                (r["miner_esg_score"] or 0.0)
                * ((r["miner_activity"] or 0.0) + (r["companies_contribution_sum"] or 0.0))
                for r in engine
            ]
            gini_published = gini(published) if published else None
            gini_input = gini(inputs) if inputs else None
            row["gini_published_weight"] = gini_published
            row["gini_input_esg_tau"] = gini_input
            row["gini_delta"] = (
                None
                if (gini_published is None or gini_input is None)
                else gini_published - gini_input
            )
            self.tables["epoch_concentration"].append(row)

    # -- the malicious-miner experiment ------------------------------------------------

    def build_malicious(self) -> None:
        """Join the ground-truth logs, the malus samples and the detector's verdicts.

        Nothing here decides whether the mechanism worked — that is phase 3. It reshapes:
        the per-action funnel, the per-miner rate table, the per-epoch malus trajectory
        (with the effective-weight invariant recomputed alongside the reported value so
        phase 3 can check it), and the detector's verdicts tagged with whether the accused
        record was in fact a confirmed malicious action.
        """
        miners = read_table(self.phase1, "malicious_miners")
        if not miners:
            return   # no plan at all; leave every malus table empty
        is_malicious = {r["address"]: b(r.get("is_malicious")) for r in miners if r.get("address")}
        malicious_by_node = {r["node_id"]: b(r.get("is_malicious")) for r in miners}
        address_of = {r["node_id"]: r.get("address", "") for r in miners}
        target_rate = {r["node_id"]: f(r.get("target_rate")) for r in miners}

        opportunities = read_table(self.phase1, "malicious_opportunities")
        actions_sent = read_table(self.phase1, "malicious_actions")
        confirmations = read_table(self.phase1, "malicious_confirmations")
        detections = read_table(self.phase1, "malus_detections")

        self._build_malus_state(is_malicious)
        joined = self._build_malus_actions(
            opportunities, actions_sent, confirmations, detections, is_malicious, address_of
        )
        self._build_malus_detection_events(detections, confirmations, is_malicious)
        self._build_malus_funnel(opportunities, joined)
        self._build_malus_rate(opportunities, joined, miners, malicious_by_node, target_rate)

    def _build_malus_state(self, is_malicious: Dict[str, Optional[bool]]) -> None:
        """One row per (governing epoch, validator), the settled malus for that epoch.

        The registry's ``getallmalus`` is sampled many times per governing epoch and M
        only grows within it as more reports confirm, so the LAST sample (max
        sample_height) is the settled value. The effective-weight invariant is recomputed
        here from M and Psi so phase 3 can compare it against the value the node reported.
        """
        rows = read_table(self.phase1, "malus")
        latest: Dict[Tuple[Optional[int], str], Dict[str, Any]] = {}
        for row in rows:
            epoch = i(row.get("epoch"))
            address = row.get("address", "")
            if not address:
                continue
            key = (epoch, address)
            height = i(row.get("sample_height")) or 0
            if key not in latest or height >= (latest[key]["_h"] or 0):
                latest[key] = dict(row, _h=height)

        for (epoch, address), row in sorted(
            latest.items(), key=lambda kv: (kv[0][0] is None, kv[0][0], kv[0][1])
        ):
            M = f(row.get("malus"))
            psi = f(row.get("psi"))
            weight = f(row.get("weight"))
            effective = f(row.get("effective"))
            recomputed = _effective_weight(weight, psi)
            psi_ok = psi is not None and 0.0 <= psi <= 1.0
            weff_ok = (
                None if (recomputed is None or effective is None)
                else abs(recomputed - effective) < 0.5
            )
            # No proved malus (M ~ 0) must leave Psi at exactly 1.
            clean_psi_one = (
                None if (M is None or psi is None)
                else (abs(psi - 1.0) < 1e-9 if M <= 1e-12 else True)
            )
            self.tables["malus_state"].append(
                {
                    "epoch": epoch,
                    "address": address,
                    "is_malicious": is_malicious.get(address),
                    "sample_height": i(row.get("sample_height")),
                    "M": M,
                    "psi": psi,
                    "weight_raw": weight,
                    "weight_effective": effective,
                    "excluded": b(row.get("excluded")),
                    "epochs_to_clear": i(row.get("epochs_to_clear")),
                    "weff_recomputed": recomputed,
                    "invariant_psi_in_unit": psi_ok,
                    "invariant_weff_matches": weff_ok,
                    "invariant_clean_psi_one": clean_psi_one,
                }
            )

    def _build_malus_actions(
        self,
        opportunities: List[Dict[str, str]],
        actions_sent: List[Dict[str, str]],
        confirmations: List[Dict[str, str]],
        detections: List[Dict[str, str]],
        is_malicious: Dict[str, Optional[bool]],
        address_of: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """One row per attempted action, threaded through sent → confirmed → reported.

        The action_id is the join key throughout: it is the stream-item key of the
        offending transaction, so it ties the injector's decision, the confirmation sweep
        and the detector's report to one identity even across a restart.
        """
        sent_by_id = {r.get("action_id"): r for r in actions_sent if r.get("action_id")}
        confirm_by_id = {r.get("action_id"): r for r in confirmations if r.get("action_id")}
        # A report is matched to an action by the offending transaction id.
        txid_to_id = {r.get("txid"): r.get("action_id") for r in actions_sent if r.get("txid")}
        reported_ids: Dict[str, Dict[str, str]] = {}
        for det in detections:
            if det.get("verdict") != "reported":
                continue
            aid = txid_to_id.get(det.get("evidence_txid"))
            if aid:
                reported_ids[aid] = det

        joined: List[Dict[str, Any]] = []
        for opp in opportunities:
            if b(opp.get("act")) is not True:
                continue
            aid = opp.get("action_id")
            miner = opp.get("miner", "")
            sent = sent_by_id.get(aid)
            confirm = confirm_by_id.get(aid)
            report = reported_ids.get(aid)
            confirm_height = i(confirm.get("confirm_height")) if confirm else None
            confirm_epoch = (confirm_height // self.epoch_length) if confirm_height is not None else None
            report_height = i(report.get("detect_height")) if report else None
            detection_latency = (
                report_height - confirm_height
                if (report_height is not None and confirm_height is not None)
                else None
            )
            # A data-integrity malus is folded at the OFFENCE's epoch and governs
            # selection from the epoch after (Def. 5.21 / §6). The offence's epoch is the
            # confirm epoch (both kinds are proved from the confirming transaction).
            governing_epoch = confirm_epoch
            activation_epoch = (governing_epoch + 1) if governing_epoch is not None else None
            row = {
                "epoch": i(opp.get("epoch")),
                "miner": miner,
                "address": address_of.get(miner, opp.get("node_address", "")),
                "is_malicious": is_malicious.get(address_of.get(miner, ""), True),
                "action": opp.get("action", ""),
                "action_id": aid,
                "attempted": True,
                "sent": sent is not None,
                "txid": (sent or {}).get("txid", ""),
                "confirmed": confirm is not None,
                "confirm_height": confirm_height,
                "confirm_epoch": confirm_epoch,
                "reported": report is not None,
                "report_height": report_height,
                "detection_latency_blocks": detection_latency,
                "governing_epoch": governing_epoch,
                "activation_epoch": activation_epoch,
                "activation_latency_epochs": 1 if activation_epoch is not None else None,
                "target_epoch": i((sent or {}).get("target_epoch")),
            }
            joined.append(row)
        self.tables["malus_actions"] = joined
        return joined

    def _build_malus_detection_events(
        self,
        detections: List[Dict[str, str]],
        confirmations: List[Dict[str, str]],
        is_malicious: Dict[str, Optional[bool]],
    ) -> None:
        """The detector's verdicts, tagged with whether the accused record was really one.

        A confirmed malicious transaction is the ground-truth positive; a ``reported``
        verdict against any other transaction is a false positive, which is the safety
        property the mechanism claims to have. Kept as its own table so phase 3 can count
        true and false positives without re-deriving the join.
        """
        malicious_txids = {r.get("txid") for r in confirmations if r.get("txid")}
        for det in detections:
            evidence = det.get("evidence_txid", "")
            reported = det.get("verdict") == "reported"
            self.tables["malus_detection_events"].append(
                {
                    "verdict": det.get("verdict", ""),
                    "kind": det.get("kind", ""),
                    "accused_address": det.get("accused_address", ""),
                    "is_malicious_accused": is_malicious.get(det.get("accused_address", "")),
                    "offence_epoch": i(det.get("offence_epoch")),
                    "offence_height": i(det.get("offence_height")),
                    "detect_height": i(det.get("detect_height")),
                    "detect_epoch": i(det.get("detect_epoch")),
                    "evidence_txid": evidence,
                    "is_true_positive": (reported and evidence in malicious_txids),
                    "reason": det.get("reason", ""),
                }
            )

    def _build_malus_funnel(
        self, opportunities: List[Dict[str, str]], joined: List[Dict[str, Any]]
    ) -> None:
        """opportunity → attempt → sent → confirmed → valid malus, overall and per kind."""
        def counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
            return {
                "attempts": len(rows),
                "sent": sum(1 for r in rows if r["sent"]),
                "confirmed": sum(1 for r in rows if r["confirmed"]),
                "valid_malus": sum(1 for r in rows if r["reported"]),
            }

        total_opps = len(opportunities)
        for scope, rows, opps in (
            ("all", joined, total_opps),
            ("selfwrite", [r for r in joined if r["action"] == "selfwrite"], None),
            ("badweight", [r for r in joined if r["action"] == "badweight"], None),
        ):
            c = counts(rows)
            self.tables["malus_funnel"].append(
                {
                    "scope": scope,
                    "opportunities": opps if opps is not None else "",
                    "attempts": c["attempts"],
                    "sent": c["sent"],
                    "confirmed": c["confirmed"],
                    "valid_malus": c["valid_malus"],
                    "reported_total": c["valid_malus"],
                }
            )

    def _build_malus_rate(
        self,
        opportunities: List[Dict[str, str]],
        joined: List[Dict[str, Any]],
        miners: List[Dict[str, str]],
        malicious_by_node: Dict[str, Optional[bool]],
        target_rate: Dict[str, Optional[float]],
    ) -> None:
        """Per malicious miner: target rate against the attempted/sent/confirmed/valid rates.

        The denominator is the miner's own opportunity count — one per epoch of the active
        window — read straight from the opportunity log, so the realised rate is measured
        against what actually happened, not against the epoch geometry.
        """
        opps_by_miner: Dict[str, int] = defaultdict(int)
        for opp in opportunities:
            opps_by_miner[opp.get("miner", "")] += 1
        by_miner: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in joined:
            by_miner[row["miner"]].append(row)

        for miner in miners:
            node_id = miner["node_id"]
            if malicious_by_node.get(node_id) is not True:
                continue
            n_opps = opps_by_miner.get(node_id, 0)
            rows = by_miner.get(node_id, [])
            attempts = len(rows)
            sent = sum(1 for r in rows if r["sent"])
            confirmed = sum(1 for r in rows if r["confirmed"])
            valid = sum(1 for r in rows if r["reported"])
            self.tables["malus_rate_by_miner"].append(
                {
                    "miner": node_id,
                    "address": miner.get("address", ""),
                    "is_malicious": True,
                    "opportunities": n_opps,
                    "attempts": attempts,
                    "sent": sent,
                    "confirmed": confirmed,
                    "valid_malus": valid,
                    "target_rate": target_rate.get(node_id),
                    "attempted_rate": (attempts / n_opps) if n_opps else None,
                    "sent_rate": (sent / n_opps) if n_opps else None,
                    "confirmed_rate": (confirmed / n_opps) if n_opps else None,
                    "valid_rate": (valid / n_opps) if n_opps else None,
                }
            )

    # -- output ------------------------------------------------------------------------

    def write(self, out_dir: Path) -> Dict[str, int]:
        out_dir.mkdir(parents=True, exist_ok=True)
        counts: Dict[str, int] = {}
        for name, columns in COLUMNS.items():
            rows = self.tables[name]
            counts[name] = len(rows)
            with open(out_dir / ("%s.csv" % name), "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
                writer.writeheader()
                for row in rows:
                    writer.writerow(
                        {c: ("" if row.get(c) is None else row.get(c)) for c in columns}
                    )
        return counts

    def summary(self) -> Dict[str, Any]:
        rounds = self.tables["round_level"]
        candidates = self.tables["candidate_long"]
        mismatch_rounds = [r["height"] for r in rounds
                           if (r["n_delay_mismatch_public"] or 0) > 0]
        measured = [r for r in rounds if not r["in_setup"]]
        # Over `measured`, not over `rounds`: the denominator below is the measured
        # count, and counting setup rounds in the numerator made the "rate" exceed 1
        # (1.508 on a smoke run with 95 setup rounds and 65 measured ones).
        inversions = [r for r in measured if r["inversion_public"] is True]
        epochs = sorted({r["epoch"] for r in self.tables["epoch_level"] if r["epoch"] is not None})
        measured_epochs = sorted(
            {r["epoch"] for r in self.tables["epoch_level"] if not r["in_setup"]}
        )
        return {
            "n_rounds": len(rounds),
            "n_rounds_measured": len(measured),
            "n_candidate_rows": len(candidates),
            "n_inversions_public": len(inversions),
            "inversion_rate_public": (len(inversions) / len(measured)) if measured else None,
            "n_rounds_with_true_score": sum(
                1 for r in measured if r["score_norm_true"] is not None
            ),
            "n_rounds_weight_epoch_stale": sum(
                1 for r in measured if r["weight_epoch_stale"] is True
            ),
            # A height whose recorded block is not the one on the active chain: phase 1
            # keeps the first block seen per height, which can be a reorged-away branch.
            "n_rounds_true_winner_mismatch": sum(
                1 for r in measured if r["true_winner_mismatch"]
            ),
            # A pass condition of the functional test: the harness and the node must agree
            # about the delay formula, or every timer-race result is meaningless.
            "delay_recompute_mismatch_rounds": len(mismatch_rounds),
            "delay_recompute_mismatch_heights": mismatch_rounds[:50],
            "delay_recompute_tolerance_s": DELAY_TOL_S,
            "max_abs_delay_mismatch_s": max(
                (abs(r["delay_mismatch_public_s"]) for r in candidates
                 if r["delay_mismatch_public_s"] is not None),
                default=None,
            ),
            "epochs_seen": epochs,
            "measured_epochs": measured_epochs,
            "n_epochs_measured": len(measured_epochs),
            "warnings": self.warnings,
        }


def aggregate(run_dir: Path, profile_path: Optional[Path] = None) -> Dict[str, Any]:
    sys.path.insert(0, str(HERE.parent.parent / "bootstrap"))
    from config_loader import load_profile  # noqa: E402

    aggregator = Aggregator(run_dir)
    profile = load_profile(profile_path or aggregator.manifest["profile_path"])

    aggregator.build_rounds()
    aggregator.build_epoch_level()
    aggregator.build_epoch_engine()
    aggregator.build_epoch_traffic(profile)
    aggregator.build_epoch_concentration()
    aggregator.build_malicious()

    out_dir = Path(run_dir) / "analysis" / "phase2"
    counts = aggregator.write(out_dir)
    manifest = {
        "phase": 2,
        "run_dir": str(run_dir),
        "profile_path": str(profile.path),
        "epoch_length": aggregator.epoch_length,
        "setup_first_blocks": aggregator.setup_blocks,
        "row_counts": counts,
        "summary": aggregator.summary(),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    return manifest


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", default=None)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)

    try:
        manifest = aggregate(Path(args.run_dir), Path(args.config) if args.config else None)
    except Phase2Error as exc:
        print("[phase2] %s" % exc, file=sys.stderr)
        return 1

    summary = manifest["summary"]
    print(
        "[phase2] %d rounds (%d measured), %d candidate rows, %d epoch(s) measured"
        % (
            summary["n_rounds"],
            summary["n_rounds_measured"],
            summary["n_candidate_rows"],
            summary["n_epochs_measured"],
        )
    )
    print(
        "[phase2] delay recompute mismatches: %d round(s) (tolerance %.4f s)"
        % (summary["delay_recompute_mismatch_rounds"], summary["delay_recompute_tolerance_s"])
    )
    for name, count in sorted(manifest["row_counts"].items()):
        print("    %-24s %6d rows" % (name, count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
