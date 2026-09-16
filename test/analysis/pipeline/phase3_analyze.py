#!/usr/bin/env python3
"""Phase 3 — analyze. The only phase that runs a test.

Reads ``analysis/phase2`` (and ``phase1/config.csv`` for the parameter table), writes
``analysis/phase3``: the test tables, the consistency checks, a ``report.md``, and a
separate ``weight_vs_election.md`` for the comparison that is the point of the whole
experiment.

**Constants, fixed in code and shared with the thesis**::

    ALPHA        = 0.05
    MC_GOF       = 20000     Monte-Carlo draws, goodness of fit
    MC_STREAK    = 10000     Monte-Carlo draws, streak test
    ANALYSIS_SEED = 20260905 RNG seed for the tests

The analysis seed is deliberately **independent** of the experiment seed in the profile.
The profile's seed controls the network and the traffic; this one controls the tests. Two
runs with different network seeds are then comparable under an identical test procedure,
and re-running the analysis on the same data reproduces the same numbers exactly.

**Which epochs are tested.** Only those whose rounds lie entirely past
``setup-first-blocks``. Below that height the chain is governed by native MultiChain
round-robin, not by wPoA: including those blocks would test the weighted election on
rounds it did not decide. The count of excluded epochs is reported rather than silently
applied.

**The consistency checks are not hypothesis tests.** They are non-regression checks meant
to fail loudly when the collection or the pipeline has a bug — a NaN, a negative weight, a
phantom miner, an ESG score that never reached the stream, a transaction count outside its
configured range. A statistical result computed on top of a failed consistency check is
not worth reading, which is why they are printed first.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from pipeline.stat import ALPHA, ANALYSIS_SEED, MC_GOF, MC_STREAK  # noqa: E402
from pipeline.stat import concentration as CONC  # noqa: E402
from pipeline.stat import gof as GOF  # noqa: E402
from pipeline.stat import longitudinal as LONG  # noqa: E402
from pipeline.stat import streak as STREAK  # noqa: E402
from pipeline.stat import timer_race as TIMER  # noqa: E402
from pipeline.stat import wilson as WILSON  # noqa: E402


class Phase3Error(RuntimeError):
    """Phase 2 output is missing or unusable."""


def read_table(phase2: Path, name: str) -> List[Dict[str, str]]:
    path = phase2 / ("%s.csv" % name)
    if not path.is_file():
        raise Phase3Error("phase 2 produced no %s.csv (looked in %s)" % (name, phase2))
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def f(value: Any) -> Optional[float]:
    if value in (None, ""):
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
    if value in (None, ""):
        return None
    return str(value).strip().lower() in ("true", "1", "yes")


def r6(value: Any) -> Any:
    """Round for presentation; blank anything not finite."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        return "" if not math.isfinite(value) else round(value, 6)
    return value


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: r6(row.get(c, "")) for c in columns})


# --------------------------------------------------------------------------------------
# the analysis
# --------------------------------------------------------------------------------------


class Analysis:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        self.phase1 = self.run_dir / "analysis" / "phase1"
        self.phase2 = self.run_dir / "analysis" / "phase2"
        self.out = self.run_dir / "analysis" / "phase3"
        if not self.phase2.is_dir():
            raise Phase3Error(
                "no phase 2 output in %s; run phase2_aggregate.py first" % self.phase2
            )
        self.manifest2 = json.loads((self.phase2 / "manifest.json").read_text(encoding="utf-8"))
        self.manifest1 = json.loads((self.phase1 / "manifest.json").read_text(encoding="utf-8"))

        self.candidates = read_table(self.phase2, "candidate_long")
        self.rounds = read_table(self.phase2, "round_level")
        self.epoch_level = read_table(self.phase2, "epoch_level")
        self.epoch_engine = read_table(self.phase2, "epoch_engine")
        self.epoch_traffic = read_table(self.phase2, "epoch_traffic")
        self.epoch_conc = read_table(self.phase2, "epoch_concentration")

        self.tables: Dict[str, List[Dict[str, Any]]] = {}
        self.checks: List[Dict[str, Any]] = []
        self.summary: Dict[str, Any] = {}

        # wPoA only governs past setup-first-blocks; earlier rounds were decided by the
        # native round robin and must not be tested as if they were elections.
        self.measured_epochs = sorted(
            {
                i(r["epoch"])
                for r in self.epoch_level
                if b(r.get("in_setup")) is False and i(r["epoch"]) is not None
            }
        )
        self.excluded_epochs = sorted(
            {
                i(r["epoch"])
                for r in self.epoch_level
                if b(r.get("in_setup")) is True and i(r["epoch"]) is not None
            }
        )

    # -- helpers -----------------------------------------------------------------------

    def epoch_rows(self, epoch: Optional[int]) -> List[Dict[str, str]]:
        if epoch is None:
            return [r for r in self.epoch_level if b(r.get("in_setup")) is False]
        return [r for r in self.epoch_level if i(r["epoch"]) == epoch]

    def rounds_of(self, epoch: Optional[int]) -> List[Dict[str, str]]:
        if epoch is None:
            return [r for r in self.rounds if b(r.get("in_setup")) is False]
        return [r for r in self.rounds if i(r["epoch"]) == epoch]

    def share_matrix(
        self, epoch: Optional[int], validators: Sequence[str]
    ) -> Tuple[List[str], List[List[float]]]:
        """``(winners, rounds x validators shares)`` for the rounds of an epoch.

        Built from ``candidate_long``, so the shares are the ones that were in force in
        each individual round rather than an epoch average. This is what makes the
        round-by-round goodness-of-fit and the streak simulation test the right null.
        """
        wanted = {i(r["height"]) for r in self.rounds_of(epoch)}
        winner_of = {i(r["height"]): r.get("winner_address", "") for r in self.rounds_of(epoch)}
        by_height: Dict[int, Dict[str, float]] = defaultdict(dict)
        for row in self.candidates:
            height = i(row["height"])
            if height in wanted:
                share = f(row.get("p_theoretical"))
                if share is not None:
                    by_height[height][row["address"]] = share
        winners: List[str] = []
        matrix: List[List[float]] = []
        for height in sorted(by_height):
            shares = [by_height[height].get(a, 0.0) for a in validators]
            if sum(shares) <= 0:
                continue
            winner = winner_of.get(height, "")
            if not winner:
                continue
            winners.append(winner)
            matrix.append(shares)
        return winners, matrix

    # -- 1. the headline: weight vs election -------------------------------------------

    def analyse_validators(self) -> None:
        """Wilson per (epoch, validator) — the comparison this experiment exists for."""
        rows: List[Dict[str, Any]] = []
        for epoch in self.measured_epochs + [None]:
            entries = self.epoch_rows(epoch)
            for entry in entries:
                observed = i(entry.get("O_i")) or 0
                blocks = i(entry.get("n_blocks_epoch")) or 0
                share = f(entry.get("p_theoretical_blockweighted"))
                if epoch is None:
                    # Pooled over every measured epoch: sum the wins and the blocks, and
                    # weight the entitlement by the blocks it applied to.
                    continue
                row = WILSON.wilson_row(observed, blocks, share)
                row.update(
                    {
                        "epoch": epoch,
                        "validator_address": entry.get("validator_address", ""),
                        "w_raw_end": f(entry.get("w_raw_end")),
                        "w_eff_end": f(entry.get("w_eff_end")),
                        "psi": f(entry.get("psi")),
                        "share_changed_within_epoch": b(entry.get("share_changed_within_epoch")),
                        "n_rounds_with_scores": i(entry.get("n_rounds_with_scores")),
                    }
                )
                rows.append(row)

        # The pooled row set, over all measured epochs at once.
        pooled: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"O": 0.0, "B": 0.0, "pB": 0.0}
        )
        for entry in self.epoch_level:
            if b(entry.get("in_setup")) is not False:
                continue
            address = entry.get("validator_address", "")
            blocks = i(entry.get("n_blocks_epoch")) or 0
            share = f(entry.get("p_theoretical_blockweighted"))
            pooled[address]["O"] += i(entry.get("O_i")) or 0
            pooled[address]["B"] += blocks
            if share is not None:
                pooled[address]["pB"] += share * blocks
        # Every validator of a measured epoch is credited that epoch's whole block count,
        # so the pooled denominator is the same for all of them and the shares still sum
        # to 1. Taking the max is therefore reading it, not estimating it.
        block_total = max((v["B"] for v in pooled.values()), default=0)
        for address in sorted(pooled):
            entry = pooled[address]
            share = (entry["pB"] / entry["B"]) if entry["B"] else None
            row = WILSON.wilson_row(int(entry["O"]), int(entry["B"]), share)
            row.update({"epoch": "all", "validator_address": address})
            rows.append(row)

        self.tables["wpoa_epoch_validators"] = rows
        self.summary["wilson_coverage"] = WILSON.coverage_summary(
            [r for r in rows if r.get("epoch") != "all"], ALPHA
        )
        self.summary["wilson_mean_width"] = WILSON.mean_width(rows)
        self.summary["pooled_blocks_measured"] = block_total

    # -- 2. per-epoch joint tests ------------------------------------------------------

    def analyse_epochs(self) -> None:
        rows: List[Dict[str, Any]] = []
        for epoch in self.measured_epochs + [None]:
            entries = self.epoch_rows(epoch)
            entries = [e for e in entries if f(e.get("p_theoretical_blockweighted")) is not None]
            if not entries:
                continue
            validators = [e.get("validator_address", "") for e in entries]

            if epoch is None:
                # Pool by validator across every measured epoch.
                merged: Dict[str, Dict[str, float]] = defaultdict(
                    lambda: {"O": 0.0, "E": 0.0}
                )
                for entry in self.epoch_level:
                    if b(entry.get("in_setup")) is not False:
                        continue
                    address = entry.get("validator_address", "")
                    merged[address]["O"] += i(entry.get("O_i")) or 0
                    expected = f(entry.get("E_i"))
                    if expected is not None:
                        merged[address]["E"] += expected
                validators = sorted(merged)
                observed = [int(merged[a]["O"]) for a in validators]
                expected = [merged[a]["E"] for a in validators]
            else:
                observed = [i(e.get("O_i")) or 0 for e in entries]
                expected = [f(e.get("E_i")) or 0.0 for e in entries]

            row: Dict[str, Any] = {
                "epoch": "all" if epoch is None else epoch,
                "n_validators": len(validators),
                "n_blocks": sum(observed),
            }
            row.update(GOF.gof_test(observed, expected, ALPHA, MC_GOF, ANALYSIS_SEED))

            winners, matrix = self.share_matrix(epoch, validators)
            row["share_changes_within_epoch"] = any(
                b(e.get("share_changed_within_epoch")) for e in entries
            )
            if matrix and row["share_changes_within_epoch"]:
                # The shares moved inside the epoch, so the pooled multinomial tests a null
                # that was never in force. The round-by-round variant is the honest one.
                p_value, statistic, expected_rb = GOF.mc_round_by_round_pvalue(
                    [winners.count(a) for a in validators], matrix, MC_GOF, ANALYSIS_SEED
                )
                row["gof_mc_round_by_round_p"] = p_value
                row["gof_mc_round_by_round_draws"] = MC_GOF
            else:
                row["gof_mc_round_by_round_p"] = None
                row["gof_mc_round_by_round_draws"] = None

            row.update(STREAK.streak_row(winners, matrix, MC_STREAK, ANALYSIS_SEED))
            theoretical = [f(e.get("p_theoretical_blockweighted")) or 0.0 for e in entries] \
                if epoch is not None else expected
            row.update(CONC.concentration_row(theoretical, "p_theoretical_"))
            row.update(CONC.concentration_row([float(o) for o in observed], "p_hat_"))
            row.update(CONC.divergence_row(theoretical, [float(o) for o in observed]))

            round_rows = self.rounds_of(epoch)
            row["n_rounds"] = len(round_rows)
            row["delay_recompute_mismatch_rounds"] = sum(
                1 for r in round_rows if (i(r.get("n_delay_mismatch")) or 0) > 0
            )
            inversions = [r for r in round_rows if b(r.get("inversion")) is True]
            decided = [r for r in round_rows if b(r.get("inversion")) is not None]
            row["inversion_n"] = len(inversions)
            row["inversion_rounds"] = len(decided)
            row["inversion_rate"] = (len(inversions) / len(decided)) if decided else None
            low, high = WILSON.wilson_interval(len(inversions), len(decided))
            row["inversion_wilson95_low"] = low
            row["inversion_wilson95_high"] = high
            rows.append(row)

        self.tables["wpoa_epoch_tests"] = rows

    # -- 3. timer race -----------------------------------------------------------------

    def analyse_timer_race(self) -> None:
        measured = [r for r in self.rounds if b(r.get("in_setup")) is False]
        margins = [f(r.get("margin_G_s")) for r in measured]
        margins = [m for m in margins if m is not None]

        tbt = next((f(r.get("target_block_time")) for r in measured
                    if f(r.get("target_block_time")) is not None), None) or 0.0
        delta = next((f(r.get("delta")) for r in measured
                      if f(r.get("delta")) is not None), None) or 0.0
        lam = next((f(r.get("lambda_s")) for r in measured
                    if f(r.get("lambda_s")) is not None), None) or 0.0
        phi = next((f(r.get("phi_s")) for r in measured
                    if f(r.get("phi_s")) is not None), None) or 0.0
        # The band half-width: the largest perturbation the delay mechanism can absorb.
        dmax = delta * tbt if (delta and tbt) else None

        counts = [i(r.get("n_candidates")) or 0 for r in measured]
        n_candidates = max(counts) if counts else 0

        row: Dict[str, Any] = {
            "n_rounds_measured": len(measured),
            "n_margins": len(margins),
            "target_block_time": tbt,
            "delta": delta,
            "lambda": lam,
            "phi": phi,
            "D_max": dmax,
            "n_candidates": n_candidates,
            "G_mean_s": (sum(margins) / len(margins)) if margins else None,
            "G_median_s": sorted(margins)[len(margins) // 2] if margins else None,
        }
        row.update(TIMER.ks_beta_margin(margins, dmax or 0.0, n_candidates))

        heights = {i(r["height"]) for r in measured}
        by_height: Dict[int, Dict[str, float]] = defaultdict(dict)
        for candidate in self.candidates:
            height = i(candidate["height"])
            if height in heights:
                weight = f(candidate.get("weight_effective"))
                if weight is not None:
                    by_height[height][candidate["address"]] = weight
        addresses = sorted({a for entry in by_height.values() for a in entry})
        matrix = [
            [by_height[h].get(a, 0.0) for a in addresses]
            for h in sorted(by_height)
            if sum(by_height[h].values()) > 0
        ]
        row.update(
            TIMER.ks_exact_mc_margin(margins, matrix, tbt, delta, lam, phi, MC_GOF, ANALYSIS_SEED)
        )
        self.tables["wpoa_timer_race"] = [row]

        # Prop. 5.17, split by winner.
        gaps: Dict[str, List[float]] = defaultdict(list)
        totals: Dict[str, List[float]] = defaultdict(list)
        weights: Dict[str, List[float]] = defaultdict(list)
        for entry in measured:
            winner = entry.get("winner_address", "")
            gap = f(entry.get("score_gap_2_1"))
            total = f(entry.get("W_tot_effective"))
            weight = f(entry.get("weff_argmin"))
            if winner and gap is not None and total is not None and weight is not None:
                gaps[winner].append(gap)
                totals[winner].append(total)
                weights[winner].append(weight)
        self.tables["wpoa_prop517"] = TIMER.prop517_test(gaps, totals, weights)

        # The perturbation budget and the inversion bound.
        residuals = [f(r.get("scheduler_residual_s")) for r in measured]
        residuals = [r for r in residuals if r is not None]
        inversion_gaps = [
            f(r.get("margin_G_s")) for r in measured if b(r.get("inversion")) is True
        ]
        inversion_gaps = [g for g in inversion_gaps if g is not None]
        sigma_rows = TIMER.sigma_rows(residuals, inversion_gaps, [])
        self.tables["wpoa_sigma"] = sigma_rows

        sigma_s2 = next(
            (r["sigma_s"] for r in sigma_rows if r["source"] == "S2_scheduler_residual_sd"), None
        )
        row["inversion_bound_sigma_S1"] = 0.0
        row["inversion_bound_sigma_S2"] = sigma_s2
        row["inversion_bound"] = TIMER.inversion_bound(n_candidates, sigma_s2 or 0.0, dmax or 0.0)
        row["inversion_mc_prob_gaussian_sigma_S2"] = (
            TIMER.mc_inversion_probability(
                matrix, tbt, delta, lam, phi, sigma_s2 or 0.0, MC_GOF, ANALYSIS_SEED
            )
            if matrix
            else None
        )
        inversions = [r for r in measured if b(r.get("inversion")) is True]
        decided = [r for r in measured if b(r.get("inversion")) is not None]
        row["inversion_observed_n"] = len(inversions)
        row["inversion_observed_rate"] = (len(inversions) / len(decided)) if decided else None

    # -- 4. longitudinal ---------------------------------------------------------------

    def analyse_longitudinal(self) -> None:
        if len(self.measured_epochs) < 2:
            self.tables["wpoa_longitudinal_validators"] = []
            self.tables["wpoa_longitudinal_fits"] = [
                {
                    "fit": "all",
                    "note": "not computable: fewer than two fully measured epochs",
                }
            ]
            self.tables["wpoa_longitudinal_logratios"] = []
            return

        first_epoch, last_epoch = self.measured_epochs[0], self.measured_epochs[-1]

        def snapshot(epoch: int) -> Dict[str, Tuple[int, int, float]]:
            out: Dict[str, Tuple[int, int, float]] = {}
            for entry in self.epoch_rows(epoch):
                share = f(entry.get("p_theoretical_blockweighted"))
                if share is None:
                    continue
                out[entry.get("validator_address", "")] = (
                    i(entry.get("O_i")) or 0,
                    i(entry.get("n_blocks_epoch")) or 0,
                    share,
                )
            return out

        self.tables["wpoa_longitudinal_validators"] = LONG.gains(
            snapshot(first_epoch), snapshot(last_epoch)
        )

        # Sign test, per validator, over the whole measured stretch.
        series: Dict[str, List[Tuple[int, float, float]]] = defaultdict(list)
        for entry in self.epoch_level:
            if b(entry.get("in_setup")) is not False:
                continue
            epoch = i(entry.get("epoch"))
            weight = f(entry.get("w_eff_end"))
            observed = f(entry.get("p_observed"))
            if epoch is not None and weight is not None and observed is not None:
                series[entry.get("validator_address", "")].append((epoch, weight, observed))

        fits: List[Dict[str, Any]] = []
        for address in sorted(series):
            row = {"fit": "monotonicity", "validator_address": address}
            row.update(LONG.monotonicity(series[address]))
            fits.append(row)

        # GLM on the pooled measured epochs.
        successes, trials, log_weights = [], [], []
        for entry in self.epoch_level:
            if b(entry.get("in_setup")) is not False:
                continue
            weight = f(entry.get("w_eff_end"))
            blocks = i(entry.get("n_blocks_epoch"))
            if weight and weight > 0 and blocks:
                successes.append(i(entry.get("O_i")) or 0)
                trials.append(blocks)
                log_weights.append(math.log(weight))
        glm = {"fit": "binomial_logit_glm_log_weight", "validator_address": "(pooled)"}
        glm.update(LONG.binomial_logit_glm(successes, trials, log_weights))
        glm["h0"] = "beta1 = 1 (weighted sortition: odds proportional to weight)"
        fits.append(glm)

        # Pairwise log-ratio regression.
        table = []
        for entry in self.epoch_level:
            if b(entry.get("in_setup")) is not False:
                continue
            table.append(
                {
                    "epoch": i(entry.get("epoch")),
                    "validator_address": entry.get("validator_address", ""),
                    "O_i": i(entry.get("O_i")) or 0,
                    "p_theoretical": f(entry.get("p_theoretical_blockweighted")),
                }
            )
        logratios = LONG.log_ratio_rows(table)
        self.tables["wpoa_longitudinal_logratios"] = logratios
        fit = {"fit": "log_ratio_regression", "validator_address": "(pairs)"}
        fit.update(LONG.log_ratio_fit(logratios))
        fits.append(fit)
        self.tables["wpoa_longitudinal_fits"] = fits

    # -- 5. the weight engine ----------------------------------------------------------

    def analyse_weight_engine(self) -> None:
        rows = [dict(r) for r in self.epoch_engine]
        for row in rows:
            for key in (
                "miner_esg_score", "miner_activity", "n_companies",
                "companies_contribution_sum", "W_k_raw", "rho_prev", "lambda_w",
                "w_k_final", "w_k_published", "R_k", "earnings_g_k", "balance_saldo",
                "return_rate_rho", "income", "expenses_gross", "w_published_next_epoch",
            ):
                row[key] = f(row.get(key))
            row["epoch"] = i(row.get("epoch"))
        self.tables["weight_engine_epoch"] = rows

        # The lag-1 feedback: rho at epoch e against the weight published at e+1. The
        # WeightEngine's only endogenous channel, and the reason lambda exists.
        by_cluster: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        pooled: List[Tuple[float, float]] = []
        for row in rows:
            rho = row.get("return_rate_rho")
            next_weight = row.get("w_published_next_epoch")
            if rho is not None and next_weight is not None:
                by_cluster[row.get("cluster_head_address", "")].append((rho, next_weight))
                pooled.append((rho, next_weight))

        correlations: List[Dict[str, Any]] = []
        for address in sorted(by_cluster):
            entry = {"cluster_head_address": address}
            entry.update(LONG.lag1_spearman(by_cluster[address]))
            correlations.append(entry)
        pooled_row = {"cluster_head_address": "(pooled)"}
        pooled_row.update(LONG.lag1_spearman(pooled))
        correlations.append(pooled_row)
        self.tables["weight_engine_correlations"] = correlations

        # Gini(published) - Gini(input) over time, and its slope.
        gini_rows = [
            {
                "epoch": i(r.get("epoch")),
                "in_setup": b(r.get("in_setup")),
                "gini_published_weight": f(r.get("gini_published_weight")),
                "gini_input_esg_tau": f(r.get("gini_input_esg_tau")),
                "gini_delta": f(r.get("gini_delta")),
            }
            for r in self.epoch_conc
        ]
        self.tables["weight_engine_gini"] = gini_rows
        usable = [r for r in gini_rows if r["gini_delta"] is not None and r["epoch"] is not None]
        self.tables["weight_engine_gini_summary"] = [
            LONG.gini_delta_slope(
                [r["epoch"] for r in usable], [r["gini_delta"] for r in usable]
            )
        ]

    # -- 6. consistency checks ---------------------------------------------------------

    def run_checks(self) -> None:
        """Non-regression checks. These fail loudly; they are not hypothesis tests."""

        def check(name: str, ok: Optional[bool], detail: str, critical: bool = True) -> None:
            self.checks.append(
                {"check": name, "passed": ok, "critical": critical, "detail": detail}
            )

        # -- no NaN, no negative, no phantom validator ---------------------------------
        bad: List[str] = []
        known = {
            r.get("address", "")
            for r in read_table(self.phase1, "miners")
            if r.get("address")
        }
        registry = read_table(self.phase1, "registry_weights")
        phantom = sorted(
            {r["address"] for r in registry if known and r["address"] not in known}
        )
        for row in registry:
            weight = f(row.get("weight"))
            if weight is None or weight < 0:
                bad.append("%s@%s=%r" % (row["address"], row["sample_height"], row.get("weight")))
        check(
            "registry_weights_finite_and_positive",
            not bad,
            "ok: %d weight samples, all finite and >= 0" % len(registry)
            if not bad
            else "%d bad value(s): %s" % (len(bad), ", ".join(bad[:5])),
        )
        check(
            "no_phantom_validator_in_registry",
            not phantom,
            "ok: every weighted address is a known miner"
            if not phantom
            else "%d address(es) carry a weight but are absent from listminers: %s"
            % (len(phantom), ", ".join(phantom[:5])),
        )

        malus = read_table(self.phase1, "malus")
        bad_malus = [
            r["address"]
            for r in malus
            if f(r.get("malus")) is None
            or (f(r.get("malus")) or 0) < 0
            or not (0.0 <= (f(r.get("psi")) if f(r.get("psi")) is not None else -1) <= 1.0)
        ]
        check(
            "malus_finite_and_psi_in_unit_interval",
            not bad_malus,
            "ok: %d malus samples, every Psi in [0,1]" % len(malus)
            if not bad_malus
            else "%d bad row(s): %s" % (len(bad_malus), ", ".join(sorted(set(bad_malus))[:5])),
        )

        # -- the delay recomputation ---------------------------------------------------
        mismatch = self.manifest2["summary"]["delay_recompute_mismatch_rounds"]
        check(
            "delay_recompute_mismatch_rounds_is_zero",
            mismatch == 0,
            "ok: the recomputed delay matches the logged one in every round "
            "(tolerance %.4f s)" % self.manifest2["summary"]["delay_recompute_tolerance_s"]
            if mismatch == 0
            else "%d round(s) disagree; max |delta| = %s s. The harness and the node "
            "disagree about the delay formula, so every timer-race result below is "
            "unsafe." % (mismatch, self.manifest2["summary"].get("max_abs_delay_mismatch_s")),
        )

        # Phi is a global feedback term that legitimately differs between nodes mid-round,
        # so a disagreement is logged and does not fail the run.
        phi_values = {f(r.get("phi_s")) for r in self.rounds if f(r.get("phi_s")) is not None}
        check(
            "phi_consistent",
            len(phi_values) <= 1,
            "ok: a single Phi value across every round (%s)" % (phi_values or "none")
            if len(phi_values) <= 1
            else "%d distinct Phi values seen; logged, not fatal" % len(phi_values),
            critical=False,
        )

        # -- ESG round trip ------------------------------------------------------------
        esg_events = read_table(self.phase1, "esg_events")
        stream_items = read_table(self.phase1, "stream_items")
        esg_txids = {r["txid"] for r in esg_events if r.get("txid")}
        on_stream = {
            r["txid"] for r in stream_items if r.get("stream") == "weight-engine-esg"
        }
        missing = sorted(esg_txids - on_stream)
        check(
            "every_esg_publication_reached_the_stream",
            not missing,
            "ok: %d ESG publication(s), all present on weight-engine-esg" % len(esg_txids)
            if not missing
            else "%d publication(s) never appeared on the stream: %s"
            % (len(missing), ", ".join(missing[:3])),
        )

        certified = {r["target_address"] for r in esg_events if r.get("target_address")}
        reflected = {
            r["address"]
            for r in read_table(self.phase1, "epoch_contributions")
            if f(r.get("esg_score"))
        }
        reflected |= {
            r["miner"]
            for r in read_table(self.phase1, "epoch_cluster_weights")
            if f(r.get("miner_esg_score"))
        }
        not_reflected = sorted(certified - reflected)
        check(
            "certified_scores_reflected_in_the_engine",
            not not_reflected,
            "ok: every certified address shows a non-zero ESG in the engine's own view"
            if not not_reflected
            else "%d certified address(es) show no ESG within an epoch: %s"
            % (len(not_reflected), ", ".join(not_reflected[:5])),
            critical=False,
        )

        # -- traffic in range ----------------------------------------------------------
        traffic = [r for r in self.epoch_traffic if b(r.get("in_range")) is not None]
        out_of_range = [r for r in traffic if b(r.get("in_range")) is False]
        check(
            "traffic_counts_within_configured_range",
            not out_of_range,
            "ok: %d complete (epoch, node) pairs, every on-chain count inside its "
            "configured range (partial first and last epochs excluded)" % len(traffic)
            if not out_of_range
            else "%d of %d (epoch, node) pairs outside range, e.g. %s"
            % (
                len(out_of_range),
                len(traffic),
                "; ".join(
                    "%s epoch %s: %s not in [%s,%s]"
                    % (
                        r["node_id"],
                        r["epoch"],
                        r.get("onchain_stream_items") or r.get("onchain_returns"),
                        r["range_low"],
                        r["range_high"],
                    )
                    for r in out_of_range[:3]
                ),
            ),
            critical=False,
        )

        # -- no forbidden flow ---------------------------------------------------------
        returns = read_table(self.phase1, "gas_returns")
        miner_addresses = {
            r["address"]
            for r in read_table(self.phase1, "nodes")
            if r.get("role") == "miner" and r.get("address")
        }
        wrong_actor = [
            r for r in returns if r.get("node_address") and r["node_address"] not in miner_addresses
        ]
        check(
            "only_miners_pay_the_treasury",
            not wrong_actor,
            "ok: all %d treasury payments came from a miner, which is the only actor "
            "whose R_k the engine reads" % len(returns)
            if not wrong_actor
            else "%d payment(s) came from a non-miner and would credit a key no cluster "
            "reads" % len(wrong_actor),
        )

        # -- the run produced something to test ----------------------------------------
        check(
            "at_least_one_fully_measured_epoch",
            bool(self.measured_epochs),
            "ok: %d epoch(s) measured past setup-first-blocks (%s)"
            % (len(self.measured_epochs), self.measured_epochs)
            if self.measured_epochs
            else "no epoch lies entirely past setup-first-blocks=%s, so nothing below "
            "tests the weighted election. Raise epochs.count or lower "
            "chain.setup-first-blocks."
            % self.manifest1.get("setup_first_blocks"),
        )

    # -- reports -----------------------------------------------------------------------

    def write_weight_vs_election(self) -> Path:
        """The dedicated report for the comparison this experiment exists for."""
        path = self.out / "weight_vs_election.md"
        rows = [r for r in self.tables["wpoa_epoch_validators"] if r.get("epoch") != "all"]
        pooled = [r for r in self.tables["wpoa_epoch_validators"] if r.get("epoch") == "all"]
        tests = self.tables["wpoa_epoch_tests"]
        coverage = self.summary.get("wilson_coverage", {})

        lines: List[str] = []
        lines.append("# Weight versus probability of election")
        lines.append("")
        lines.append(
            "> The headline comparison of this experiment. For each epoch and each "
            "validator: the share of blocks the **final weight** entitled it to, against "
            "the share it actually won, with a 95% Wilson interval around the observed "
            "share and a joint goodness-of-fit test over all validators of the epoch."
        )
        lines.append("")
        lines.append("## What is being compared")
        lines.append("")
        lines.append(
            "`p_theoretical` is built from `effective_weight_after_malus_and_dumping` — "
            "the quantity the election **actually consumes**, after the malus factor and "
            "after the dumping function — and is block-weighted across the rounds of the "
            "epoch, so an epoch whose weights moved is summarised by what was in force "
            "rather than by a snapshot of either end."
        )
        lines.append("")
        lines.append(
            "`p_hat = O_i / B` is the observed share. The Wilson interval is the "
            "95% score interval around it; it stays inside [0,1] and has sensible width "
            "at `O_i = 0`, where the textbook interval collapses to zero."
        )
        lines.append("")
        if self.excluded_epochs:
            lines.append(
                "**Epochs %s are excluded**: their rounds lie at or below "
                "`setup-first-blocks = %s`, where the chain is governed by native "
                "MultiChain round robin rather than by wPoA. Testing them would measure "
                "the wrong mechanism."
                % (self.excluded_epochs, self.manifest1.get("setup_first_blocks"))
            )
            lines.append("")

        lines.append("## Per-epoch, per-validator")
        lines.append("")
        lines.append(
            "| epoch | validator | w_final | p_theoretical | O_i | B | p_hat | "
            "Wilson 95% | inside? |"
        )
        lines.append("|---|---|---:|---:|---:|---:|---:|---|---|")
        for row in rows:
            inside = row.get("p_theoretical_inside_wilson95")
            lines.append(
                "| %s | `%s` | %s | %s | %s | %s | %s | [%s, %s] | %s |"
                % (
                    row.get("epoch"),
                    str(row.get("validator_address", ""))[:12],
                    _fmt(row.get("w_eff_end"), 0),
                    _fmt(row.get("p_theoretical"), 4),
                    row.get("O_i"),
                    row.get("n_blocks"),
                    _fmt(row.get("p_hat"), 4),
                    _fmt(row.get("wilson95_low"), 4),
                    _fmt(row.get("wilson95_high"), 4),
                    "yes" if inside else ("no" if inside is False else "-"),
                )
            )
        lines.append("")

        lines.append("## Pooled over every measured epoch")
        lines.append("")
        lines.append("| validator | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |")
        lines.append("|---|---:|---:|---:|---:|---|---|")
        for row in pooled:
            inside = row.get("p_theoretical_inside_wilson95")
            lines.append(
                "| `%s` | %s | %s | %s | %s | [%s, %s] | %s |"
                % (
                    str(row.get("validator_address", ""))[:12],
                    _fmt(row.get("p_theoretical"), 4),
                    row.get("O_i"),
                    row.get("n_blocks"),
                    _fmt(row.get("p_hat"), 4),
                    _fmt(row.get("wilson95_low"), 4),
                    _fmt(row.get("wilson95_high"), 4),
                    "yes" if inside else ("no" if inside is False else "-"),
                )
            )
        lines.append("")

        lines.append("## Joint test per epoch (chi-square / exact / Monte Carlo)")
        lines.append("")
        lines.append(
            "| epoch | blocks | validators | method | statistic | p | reject at 0.05 | "
            "TV | round-by-round p |"
        )
        lines.append("|---|---:|---:|---|---:|---:|---|---:|---:|")
        for row in tests:
            lines.append(
                "| %s | %s | %s | %s | %s | %s | %s | %s | %s |"
                % (
                    row.get("epoch"),
                    row.get("n_blocks"),
                    row.get("n_validators"),
                    row.get("gof_method"),
                    _fmt(row.get("gof_chi2"), 3),
                    _fmt(row.get("gof_p_value"), 4),
                    "YES" if row.get("gof_reject_alpha05") else "no",
                    _fmt(row.get("TV"), 4),
                    _fmt(row.get("gof_mc_round_by_round_p"), 4),
                )
            )
        lines.append("")

        lines.append("## How to read this")
        lines.append("")
        lines.append(
            "- **The interval, not the point.** A `p_hat` far from `p_theoretical` means "
            "nothing if the interval is wide; with a handful of blocks per epoch it "
            "usually is. The mean interval width here is **%s**, which is the resolution "
            "of this run." % _fmt(self.summary.get("wilson_mean_width"), 4)
        )
        lines.append(
            "- **Multiple comparisons.** %s of %s intervals excluded the entitled share; "
            "about %s are expected to by chance alone at alpha = %.2f. Only a count well "
            "above the expectation is a finding."
            % (
                coverage.get("n_outside"),
                coverage.get("n_intervals"),
                _fmt(coverage.get("expected_outside"), 1),
                ALPHA,
            )
        )
        lines.append(
            "- **The joint test is the real one.** The per-validator intervals say *which* "
            "validator is out of line; the chi-square says whether the epoch as a whole is "
            "distinguishable from weighted sortition."
        )
        lines.append(
            "- **Round-by-round when the shares moved.** Where an epoch's shares changed "
            "mid-epoch, the pooled multinomial tests a null that was never in force, and "
            "the round-by-round Monte-Carlo p-value in the last column is the one to read."
        )
        lines.append("")
        lines.append(
            "The corresponding figure is `plots/weight_vs_election.png`, produced by "
            "`plotting/generate_plots.py`."
        )
        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def write_report(self) -> Path:
        path = self.out / "report.md"
        lines: List[str] = []
        critical_failures = [
            c for c in self.checks if c["critical"] and c["passed"] is False
        ]

        lines.append("# Functional run report")
        lines.append("")
        lines.append("| | |")
        lines.append("|---|---|")
        lines.append("| run | `%s` |" % self.run_dir.name)
        lines.append("| chain | `%s` |" % self.manifest1.get("chain_name"))
        lines.append("| experiment seed | %s |" % self.manifest1.get("seed"))
        lines.append("| final height | %s |" % self.manifest1.get("final_height"))
        lines.append("| epoch length | %s blocks |" % self.manifest1.get("epoch_length"))
        lines.append("| setup-first-blocks | %s |" % self.manifest1.get("setup_first_blocks"))
        lines.append("| epochs measured | %s |" % (self.measured_epochs or "none"))
        lines.append("| epochs excluded (setup phase) | %s |" % (self.excluded_epochs or "none"))
        lines.append(
            "| test constants | alpha=%.2f, MC_GOF=%d, MC_STREAK=%d, seed=%d |"
            % (ALPHA, MC_GOF, MC_STREAK, ANALYSIS_SEED)
        )
        lines.append("")
        lines.append(
            "**Overall: %s**"
            % (
                "PASS — every critical consistency check holds"
                if not critical_failures
                else "FAIL — %d critical consistency check(s) failed; the statistics below "
                "are not safe to read" % len(critical_failures)
            )
        )
        lines.append("")

        lines.append("## 1. Consistency checks")
        lines.append("")
        lines.append(
            "Non-regression checks, not hypothesis tests. They exist to fail loudly when "
            "the collection or the pipeline has a bug."
        )
        lines.append("")
        lines.append("| check | critical | result | detail |")
        lines.append("|---|---|---|---|")
        for entry in self.checks:
            lines.append(
                "| `%s` | %s | %s | %s |"
                % (
                    entry["check"],
                    "yes" if entry["critical"] else "no",
                    "PASS" if entry["passed"] else ("FAIL" if entry["passed"] is False else "-"),
                    entry["detail"],
                )
            )
        lines.append("")

        lines.append("## 2. Weight versus probability of election")
        lines.append("")
        lines.append(
            "> **This is the comparison the experiment exists for, and it has a report of "
            "its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary "
            "below is the short form."
        )
        lines.append("")
        coverage = self.summary.get("wilson_coverage", {})
        lines.append(
            "- %s of %s validator-epoch Wilson intervals contained the entitled share "
            "(%s expected to fail by chance at alpha = %.2f)."
            % (
                (coverage.get("n_intervals") or 0) - (coverage.get("n_outside") or 0),
                coverage.get("n_intervals"),
                _fmt(coverage.get("expected_outside"), 1),
                ALPHA,
            )
        )
        lines.append("- Mean interval width: **%s**." % _fmt(self.summary.get("wilson_mean_width"), 4))
        rejects = [t for t in self.tables["wpoa_epoch_tests"] if t.get("gof_reject_alpha05")]
        lines.append(
            "- Goodness of fit rejected in %d of %d epoch(s) at alpha = %.2f."
            % (len(rejects), len(self.tables["wpoa_epoch_tests"]), ALPHA)
        )
        lines.append("")

        lines.append("## 3. Concentration")
        lines.append("")
        lines.append("| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for row in self.tables["wpoa_epoch_tests"]:
            lines.append(
                "| %s | %s | %s | %s | %s | %s |"
                % (
                    row.get("epoch"),
                    _fmt(row.get("p_theoretical_HHI"), 4),
                    _fmt(row.get("p_hat_HHI"), 4),
                    _fmt(row.get("p_hat_N_eff"), 2),
                    row.get("p_hat_nakamoto_1_2"),
                    _fmt(row.get("p_hat_gini"), 4),
                )
            )
        lines.append("")

        lines.append("## 4. Streaks")
        lines.append("")
        lines.append("| epoch | L_max obs | L_max MC mean | p | repeat obs | repeat MC mean | p |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for row in self.tables["wpoa_epoch_tests"]:
            lines.append(
                "| %s | %s | %s | %s | %s | %s | %s |"
                % (
                    row.get("epoch"),
                    row.get("L_max_observed"),
                    _fmt(row.get("L_max_mc_mean"), 2),
                    _fmt(row.get("L_max_mc_p_value"), 4),
                    _fmt(row.get("repeat_prob_observed"), 4),
                    _fmt(row.get("repeat_prob_mc_mean"), 4),
                    _fmt(row.get("repeat_prob_mc_p_value"), 4),
                )
            )
        lines.append("")

        lines.append("## 5. Timer race")
        lines.append("")
        timer = (self.tables.get("wpoa_timer_race") or [{}])[0]
        lines.append("| quantity | value |")
        lines.append("|---|---|")
        for label, key, digits in (
            ("rounds measured", "n_rounds_measured", 0),
            ("margins observed", "n_margins", 0),
            ("mean margin G (s)", "G_mean_s", 5),
            ("KS vs Beta(1,n) — straw man, p", "ks_beta_p", 5),
            ("KS vs simulated exact — reference, p", "ks_mc_p", 5),
            ("sigma S1 (topology)", "inversion_bound_sigma_S1", 6),
            ("sigma S2 (scheduler residual)", "inversion_bound_sigma_S2", 6),
            ("inversion bound (Prop. 5.18)", "inversion_bound", 5),
            ("inversion probability, MC with sigma_S2", "inversion_mc_prob_gaussian_sigma_S2", 5),
            ("inversions observed", "inversion_observed_n", 0),
            ("inversion rate observed", "inversion_observed_rate", 5),
        ):
            lines.append("| %s | %s |" % (label, _fmt(timer.get(key), digits)))
        lines.append("")
        lines.append(
            "The Beta(1,n) test is a **straw man**: it assumes uniform weights and is "
            "expected to reject whenever they are not uniform. The reference test is the "
            "KS against the simulated exact distribution of the implemented sortition."
        )
        lines.append("")
        lines.append(
            "**S1 is structurally negligible in this harness** — every node is a local "
            "process and there is no emulated latency, so a run here cannot speak to "
            "latency-driven inversion. S2, the scheduler residual, is the primary source."
        )
        lines.append("")

        lines.append("## 6. Longitudinal")
        lines.append("")
        for row in self.tables.get("wpoa_longitudinal_fits", []):
            if row.get("fit") == "binomial_logit_glm_log_weight":
                lines.append(
                    "- **GLM logit on log(weight)**: beta1 = %s (95%% CI [%s, %s], n = %s, "
                    "converged = %s). H0 of weighted sortition is beta1 = 1 — %s."
                    % (
                        _fmt(row.get("beta1"), 4),
                        _fmt(row.get("beta1_ci_low"), 4),
                        _fmt(row.get("beta1_ci_high"), 4),
                        row.get("n_points"),
                        row.get("converged"),
                        "consistent" if row.get("beta1_consistent_with_1")
                        else ("NOT consistent" if row.get("beta1_consistent_with_1") is False
                              else "not computable"),
                    )
                )
            elif row.get("fit") == "log_ratio_regression":
                lines.append(
                    "- **Pairwise log-ratio regression**: slope = %s, intercept = %s, "
                    "Pearson r = %s (p = %s), n = %s pairs. Proportional selection implies "
                    "slope 1 and intercept 0."
                    % (
                        _fmt(row.get("slope"), 4),
                        _fmt(row.get("intercept"), 4),
                        _fmt(row.get("pearson_r"), 4),
                        _fmt(row.get("pearson_p"), 4),
                        row.get("n_pairs"),
                    )
                )
        signs = [r for r in self.tables.get("wpoa_longitudinal_fits", [])
                 if r.get("fit") == "monotonicity" and r.get("sign_test_p_greater") is not None]
        if signs:
            lines.append(
                "- **Sign test (weight ↔ share monotonicity)**: %d validator(s) tested; "
                "p-values %s."
                % (
                    len(signs),
                    ", ".join(_fmt(s.get("sign_test_p_greater"), 4) for s in signs[:6]),
                )
            )
        lines.append("")

        lines.append("## 7. WeightEngine feedback")
        lines.append("")
        pooled = next(
            (r for r in self.tables.get("weight_engine_correlations", [])
             if r.get("cluster_head_address") == "(pooled)"),
            {},
        )
        lines.append(
            "- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* "
            "(the engine's only endogenous feedback channel): rho = %s, p = %s, n = %s."
            % (
                _fmt(pooled.get("spearman_rho"), 4),
                _fmt(pooled.get("spearman_p"), 4),
                pooled.get("n_pairs"),
            )
        )
        gini_summary = (self.tables.get("weight_engine_gini_summary") or [{}])[0]
        lines.append(
            "- **Gini(published) − Gini(input) trajectory**: slope = %s over %s epoch(s) "
            "(Spearman rho = %s, p = %s). A positive slope means the engine concentrates "
            "weight beyond the inequality of its own inputs."
            % (
                _fmt(gini_summary.get("slope"), 6),
                gini_summary.get("n_epochs"),
                _fmt(gini_summary.get("spearman_rho"), 4),
                _fmt(gini_summary.get("spearman_p"), 4),
            )
        )
        lines.append("")

        lines.append("## 8. Method notes")
        lines.append("")
        lines.append(
            "- Only epochs entirely past `setup-first-blocks` are tested: below that "
            "height the chain runs under native MultiChain round robin, not wPoA."
        )
        lines.append(
            "- `p_theoretical` uses the effective weight after malus and dumping — what "
            "the election consumes — not the raw published weight."
        )
        lines.append(
            "- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of "
            "exactly 0 is never reported for a finite simulation."
        )
        lines.append(
            "- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov "
            "distribution, Student's t, the exact binomial tail and the IRLS logit fit "
            "are all computed from their closed forms in `stat/`."
        )
        lines.append(
            "- The analysis seed (%d) is independent of the experiment seed (%s): the "
            "network and the tests are separately reproducible."
            % (ANALYSIS_SEED, self.manifest1.get("seed"))
        )
        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    # -- driver ------------------------------------------------------------------------

    def run(self) -> Dict[str, Any]:
        self.out.mkdir(parents=True, exist_ok=True)
        self.analyse_validators()
        self.analyse_epochs()
        self.analyse_timer_race()
        self.analyse_longitudinal()
        self.analyse_weight_engine()
        self.run_checks()

        for name, rows in self.tables.items():
            columns: List[str] = []
            for row in rows:
                for key in row:
                    if key not in columns:
                        columns.append(key)
            write_csv(self.out / ("%s.csv" % name), rows, columns or ["empty"])
        write_csv(
            self.out / "consistency_checks.csv",
            self.checks,
            ["check", "critical", "passed", "detail"],
        )

        self.write_weight_vs_election()
        self.write_report()

        critical_failures = [c["check"] for c in self.checks if c["critical"] and c["passed"] is False]
        manifest = {
            "phase": 3,
            "run_dir": str(self.run_dir),
            "constants": {
                "alpha": ALPHA,
                "mc_gof": MC_GOF,
                "mc_streak": MC_STREAK,
                "analysis_seed": ANALYSIS_SEED,
            },
            "measured_epochs": self.measured_epochs,
            "excluded_epochs_in_setup": self.excluded_epochs,
            "row_counts": {name: len(rows) for name, rows in self.tables.items()},
            "checks_passed": sum(1 for c in self.checks if c["passed"]),
            "checks_total": len(self.checks),
            "critical_failures": critical_failures,
            "summary": self.summary,
        }
        (self.out / "manifest.json").write_text(
            json.dumps(manifest, indent=2, default=str), encoding="utf-8"
        )
        return manifest


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int,)) or digits == 0:
        try:
            return "%d" % int(value)
        except (TypeError, ValueError):
            return str(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "-"
    return ("%%.%df" % digits) % number


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", default=None)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)

    try:
        manifest = Analysis(Path(args.run_dir)).run()
    except Phase3Error as exc:
        print("[phase3] %s" % exc, file=sys.stderr)
        return 1

    print(
        "[phase3] %d/%d consistency checks passed; epochs measured: %s"
        % (manifest["checks_passed"], manifest["checks_total"], manifest["measured_epochs"])
    )
    if manifest["critical_failures"]:
        print("[phase3] CRITICAL FAILURES: %s" % ", ".join(manifest["critical_failures"]))
    print("[phase3] report:            %s/analysis/phase3/report.md" % args.run_dir)
    print("[phase3] headline comparison: %s/analysis/phase3/weight_vs_election.md" % args.run_dir)
    return 2 if manifest["critical_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
