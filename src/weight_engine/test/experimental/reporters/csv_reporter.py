# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# csv_reporter.py -- writes the analysis artifacts to output/. Each writer takes
# already-collected rows (the orchestrator owns data gathering) and emits a
# self-describing CSV suitable for Excel / pandas. Idempotent: output/ is recreated
# from scratch at the start of every run (see reset_output).
#
# CHANGED FROM THE ORIGINAL (Apuana SB) SETUP:
#  * the per-miner columns of epochs_summary / wpoa_proposer_log are now DERIVED from
#    config.NUM_MINERS instead of being hard-coded to M1..M4, so the MyLedger topology
#    (ClusterMinerA..E) needs no further edits when the cluster count changes;
#  * five new artifacts carry the MyLedger data the report needs:
#      config_sheet.csv     -- the static configuration ("Foglio di configurazione")
#      cluster_economics.csv-- per epoch x cluster: the Vers_2 summary columns
#                              (Tx Miner, Impatto Cluster, Delay, Guadagno, Resi,
#                              Giacenza, %Reso, Total GAIN) plus the pipeline detail
#                              and the engine cross-check
#      company_activity.csv -- per epoch x azienda: Tx utente, Impatto utente, ESG
#      epoch_checks.csv     -- the five per-epoch model invariants, epoch by epoch
#      assertions.csv       -- the run-level invariant checks and their verdicts.

import csv
import os
import shutil

import config


def reset_output(outdir):
    """Recreate outdir from scratch (idempotency rule: never append to a prior run)."""
    if os.path.isdir(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir)


def _miner_cols(prefix):
    """['weight_ClusterMinerA', ...] -- one column per configured cluster."""
    return ["%s_%s" % (prefix, config.miner_id(i)) for i in range(config.NUM_MINERS)]


class CsvReporter(object):
    def __init__(self, outdir):
        self.outdir = outdir

    def _write(self, name, header, rows):
        path = os.path.join(self.outdir, name)
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            for row in rows:
                w.writerow(row)
        return path

    def _write_dicts(self, name, fields, rows):
        """Write dict rows in `fields` order, tolerating missing keys."""
        return self._write(name, fields, [[r.get(k, "") for k in fields] for r in rows])

    # -- per-epoch consensus view ------------------------------------------
    def epochs_summary(self, rows):
        return self._write("epochs_summary.csv",
                           ["epoch", "mode", "block_height", "proposer_miner",
                            "proposer_method"]
                           + _miner_cols("weight") + _miner_cols("prob")
                           + ["tx_count", "theta", "reconciliation_done", "timestamp"],
                           rows)

    def esg_scores(self, rows):
        return self._write("esg_scores.csv", [
            "epoch", "company_id", "miner_id", "esg_score", "cluster_id",
            "stream_txid"], rows)

    def transactions(self, rows):
        return self._write("transactions.csv", [
            "epoch", "block_height", "txid", "sender", "receiver", "type",
            "amount_gas", "confirmed"], rows)

    def weights_evolution(self, rows):
        return self._write("weights_evolution.csv", [
            "epoch", "miner_id", "raw_weight", "normalized_weight",
            "selection_probability", "was_selected_proposer",
            "delta_weight_from_prev_epoch"], rows)

    def wpoa_proposer_log(self, rows):
        return self._write("wpoa_proposer_log.csv",
                           ["epoch", "selected_proposer",
                            "selection_probability_at_time",
                            "theoretical_expected_proposer", "match_expected"]
                           + _miner_cols("total_selections")
                           + ["cumulative_deviation_from_expected"], rows)

    # -- MyLedger economics -------------------------------------------------
    CONFIG_FIELDS = ["cluster", "letter", "esg_cluster", "iso_certificate",
                     "reso_rate_nominal", "companies", "esg_companies"]

    # Column order: the Vers_2 cluster-summary columns first, in sheet order, then the
    # audit / engine-cross-check detail. `delay_msec` is the per-mille normalized
    # weight (Vers_2's "Delay in msec"); the measured latency is `block_interval_ms`.
    CLUSTER_FIELDS = ["epoch", "cluster", "letter", "esg", "iso",
                      # --- Vers_2 cluster summary row ---
                      "tx_miner", "impatto_cluster", "delay_msec",
                      "guadagno", "resi", "giacenza", "pct_reso", "total_gain",
                      # --- pipeline detail ---
                      "theta", "sum_impatto_utente", "raw_weight", "final_weight",
                      "feedback_bracket", "delay_raw", "delay_final", "p_k",
                      "giacenza_prev", "available", "rho",
                      "resi_target", "resi_requested", "resi_onchain",
                      "reso_rate_nominal", "saldo_onchain",
                      # --- consensus outcome (not an input) ---
                      "blocks_mined", "validated_in_blocks", "block_interval_ms",
                      # --- engine cross-check ---
                      "engine_weight", "engine_prob", "w_k_expected",
                      "w_k_expected_int", "weight_match", "selected_proposer",
                      # --- provenance ---
                      "alloc_txid", "recon_txid", "recon_stream_txid",
                      "recon_stream_confirmed"]

    COMPANY_FIELDS = ["epoch", "cluster", "company", "display", "tx_utente",
                      "esg", "impatto_utente"]

    ASSERTION_FIELDS = ["check", "scope", "verdict", "detail"]

    EPOCH_CHECK_FIELDS = ["epoch", "check", "verdict", "detail"]

    def config_sheet(self, rows):
        """The static configuration ('Foglio di configurazione'): one row per cluster.
        `companies` / `esg_companies` are ';'-joined lists so the sheet round-trips
        through a flat CSV without a second file."""
        return self._write_dicts("config_sheet.csv", self.CONFIG_FIELDS, rows)

    def cluster_economics(self, rows):
        return self._write_dicts("cluster_economics.csv", self.CLUSTER_FIELDS, rows)

    def company_activity(self, rows):
        return self._write_dicts("company_activity.csv", self.COMPANY_FIELDS, rows)

    def assertions(self, rows):
        return self._write_dicts("assertions.csv", self.ASSERTION_FIELDS, rows)

    def epoch_checks(self, rows):
        """The five per-epoch model invariants, one row per (epoch, check). `rows` are
        the dicts economics.verify_epoch_invariants returns."""
        return self._write("epoch_checks.csv", self.EPOCH_CHECK_FIELDS,
                           [[r.get("epoch", ""), r.get("check", ""),
                             "PASS" if r.get("ok") else "FAIL", r.get("detail", "")]
                            for r in rows])
