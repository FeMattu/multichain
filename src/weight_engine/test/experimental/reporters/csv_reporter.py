# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# csv_reporter.py -- writes the six analysis artifacts to output/. Each writer
# takes already-collected rows (the orchestrator owns data gathering) and emits a
# self-describing CSV suitable for Excel / pandas. Idempotent: output/ is recreated
# from scratch at the start of every run (see reset_output).

import csv
import os
import shutil


def reset_output(outdir):
    """Recreate outdir from scratch (idempotency rule: never append to a prior run)."""
    if os.path.isdir(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir)


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

    def epochs_summary(self, rows):
        return self._write("epochs_summary.csv", [
            "epoch", "mode", "block_height", "proposer_miner", "proposer_method",
            "weight_M1", "weight_M2", "weight_M3", "weight_M4",
            "prob_M1", "prob_M2", "prob_M3", "prob_M4",
            "tx_count", "reconciliation_done", "timestamp"], rows)

    def esg_scores(self, rows):
        return self._write("esg_scores.csv", [
            "epoch", "company_id", "miner_id", "esg_score", "cluster_id",
            "stream_txid"], rows)

    def transactions(self, rows):
        return self._write("transactions.csv", [
            "epoch", "block_height", "txid", "sender", "receiver", "type",
            "amount", "confirmed"], rows)

    def weights_evolution(self, rows):
        return self._write("weights_evolution.csv", [
            "epoch", "miner_id", "raw_weight", "normalized_weight",
            "selection_probability", "was_selected_proposer",
            "delta_weight_from_prev_epoch"], rows)

    def wpoa_proposer_log(self, rows):
        return self._write("wpoa_proposer_log.csv", [
            "epoch", "selected_proposer", "selection_probability_at_time",
            "theoretical_expected_proposer", "match_expected",
            "total_selections_M1", "total_selections_M2",
            "total_selections_M3", "total_selections_M4",
            "cumulative_deviation_from_expected"], rows)
