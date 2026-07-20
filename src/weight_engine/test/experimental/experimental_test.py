#!/usr/bin/env python3
# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# experimental_test.py -- entry point for the WeightEngine experimental simulation.
#
# Drives a real local MultiChain network (1 admin + N miner nodes) through a
# configurable number of epochs, in ONE of two modes selected by a MANDATORY flag:
#
#   --mode=wpoa    master switch on  -> the engine's weights drive weighted
#                                       proposer selection.
#   --mode=native  master off        -> native round-robin mining, while the engine
#                                       still computes + publishes w_k to wpoa-weights.
#
# It never reimplements the weight math: the admin publishes the public inputs (ESG,
# membership, per-epoch reconciliation) through the sanctioned admin RPCs, the nodes
# compute w_k, and this harness READS the results (getallweights + the engine's
# per-epoch debug.log lines) and the mined blocks. Everything is written to
# output/*.csv and output/experiment.log for offline analysis.
#
# Design notes:
#  * A tx's epoch is the epoch of its CONFIRMING block (resolved from the block
#    index), so a transfer submitted near an epoch boundary is attributed to where
#    it actually landed -- not assumed.
#  * Per-epoch weights come from the miners' "[WeightEngine] epoch E ... w_k = W"
#    log lines (authoritative + epoch-tagged); getallweights gives the live total.
#  * "proposer of an epoch" is the miner that mined the MOST blocks in that epoch
#    (an epoch spans many blocks); the full per-miner tally is in wpoa_proposer_log.
#  * selection_probability is the theoretical w_k / sum w_k. The consensus selector
#    additionally applies whale-compression at election time, so observed shares
#    track these probabilities without being identical (see weight_engine.h).

import collections
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import config
from reporters.log_reporter import LogReporter
from reporters.csv_reporter import CsvReporter, reset_output
from helpers.chain_setup import Network, looks_txid
from helpers.participants import ParticipantRegistry
from helpers.stream_writer import StreamWriter
from helpers.tx_simulator import TxSimulator
from helpers.weight_reader import WeightReader
from helpers.esg_generator import generate_scores


def parse_mode(argv):
    """Return the mandatory mode, or print an error and exit(2) if missing/invalid."""
    mode = None
    for a in argv[1:]:
        if a.startswith("--mode="):
            mode = a.split("=", 1)[1].strip()
        elif a in ("-h", "--help"):
            _usage(0)
    if mode not in config.VALID_MODES:
        sys.stderr.write("ERROR: a valid --mode is REQUIRED.\n\n")
        _usage(2)
    return mode


def _usage(code):
    sys.stderr.write(
        "usage: experimental_test.py --mode=wpoa|native\n\n"
        "  --mode=wpoa    weighted proposer selection driven by the engine's w_k\n"
        "  --mode=native  native round-robin mining; engine still publishes w_k\n\n"
        "Tunables are environment variables (see config.py): WE_SEED, WE_MINERS,\n"
        "WE_EPOCHS, WE_EPOCH_LENGTH, WE_SETUP_BLOCKS, WE_BLOCK_TIME, ...\n")
    sys.exit(code)


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Experiment(object):
    def __init__(self, mode):
        self.mode = mode
        self.outdir = os.path.join(HERE, "output")
        reset_output(self.outdir)
        self.log = LogReporter(os.path.join(self.outdir, "experiment.log"))
        self.csv = CsvReporter(self.outdir)
        self.net = Network(mode, self.log)
        self.reg = None
        # collected data
        self.esg_pub = {}          # label -> (addr, score, txid)
        self.tx_records = []       # list of tx dicts
        self.recon_done = {}       # epoch -> bool
        self.epochs = []           # simulated epoch indices
        self.method = ("wpoa-weighted" if mode == "wpoa" else "native-roundrobin")

    # -- orchestration ------------------------------------------------------
    def run(self):
        self.log.header(self.mode, [
            ("seed", config.SEED),
            ("miners", config.NUM_MINERS),
            ("companies", config.NUM_MINERS * config.COMPANIES_PER_MINER),
            ("epochs", config.NUM_EPOCHS),
            ("epoch_len", config.EPOCH_LENGTH),
            ("margin", config.STABILITY_MARGIN),
            ("kappa/alpha/lambda", "%g / %g / %g" % (config.KAPPA, config.ALPHA, config.LAMBDA)),
        ])
        try:
            self._setup_chain()
            self._publish_static_inputs()
            self._warmup_weights()
            self._run_epochs()
            self._harvest_and_report()
            return 0
        except Exception as exc:               # never leave a network running
            self.log.error("fatal: %s" % exc)
            import traceback
            self.log.error(traceback.format_exc())
            return 1
        finally:
            self.net.teardown()
            self.log.close()

    def _setup_chain(self):
        self.net.start()
        self.reg = ParticipantRegistry(self.net, self.log)
        self.reg.build()
        self.wr = WeightReader(self.net, self.reg, self.log)
        self.sw = StreamWriter(self.net, self.reg, self.log)
        self.txsim = TxSimulator(self.net, self.reg, self.log)

    def _publish_static_inputs(self):
        self.sw.ensure_write_permission()
        scores = generate_scores()
        self.esg_pub = self.sw.publish_esg(scores)
        membership = self.sw.publish_membership()
        last_mtx = [x[2] for x in membership if x[2]]
        if last_mtx:
            self.net.wait_confirmed(self.net.admin, last_mtx[-1])
        # fund participants so they can transact (produce activity tau).
        self.tx_records += self.txsim.setup()
        # the miners publish w_k here; the admin (not a cluster miner) must create it.
        self.net.ensure_wpoa_weights_stream()
        # the admin must never propose a block.
        self.net.demote_admin_from_mining()

    def _warmup_weights(self):
        """Wait until every miner has published a weight, so wPoA selection has a
        weight map to work from before the sampled epochs begin."""
        self.log.info("warm-up: waiting for all %d miners to publish a weight ..."
                      % config.NUM_MINERS)
        w = self.wr.wait_all_miners_weighted()
        got = len(self.reg.miner_address_set().intersection(w.keys()))
        if got < config.NUM_MINERS:
            self.log.warn("only %d/%d miners weighted after warm-up (continuing)"
                          % (got, config.NUM_MINERS))
        else:
            self.log.info("all miners weighted: %s" % w)

    def _run_epochs(self):
        # In wpoa mode the sampled epochs must lie AFTER the native setup phase, or
        # they would be round-robin-mined (setup) rather than weight-selected. Weights
        # are already established (warm-up), so driving through the rest of setup is
        # safe -- no deadlock. Native mode is indifferent, so we skip the wait.
        if self.mode == "wpoa":
            self.net.wait_height(config.SETUP_FIRST_BLOCKS + 2,
                                 stallmsg="waiting for the native setup phase to end")
        h0 = self.net.admin.block_count()
        start_epoch = config.height_to_epoch(h0) + 1
        self.epochs = list(range(start_epoch, start_epoch + config.NUM_EPOCHS))
        self.log.info("sampling epochs %d..%d (tip=%d)" %
                      (self.epochs[0], self.epochs[-1], h0))

        for e in self.epochs:
            start, end = config.epoch_range(e)
            self.net.wait_height(start, stallmsg="waiting to enter epoch %d" % e)
            self.tx_records += self.txsim.generate_epoch_txs(e)
            recon = self.sw.publish_reconciliation(e)
            self.recon_done[e] = any(t for (_, t) in recon.values())
            for mlabel, (amount, txid) in recon.items():
                self.tx_records.append({"epoch": e, "txid": txid, "sender": "admin",
                                        "receiver": mlabel, "type": "reconciliation",
                                        "amount": amount})
            self.net.wait_height(end + 1, stallmsg="mining epoch %d" % e)

        # bury the last epoch so every sampled epoch's weight gets published.
        last_end = config.epoch_range(self.epochs[-1])[1]
        bury_to = last_end + config.STABILITY_MARGIN + 2
        self.log.info("driving to height %d to bury the last epoch ..." % bury_to)
        self.net.wait_height(bury_to, stallmsg="burying last epoch")
        # give the miners' engine threads a moment to publish the last epoch.
        self.wr.wait_all_miners_weighted(timeout=30)

    # -- reporting ----------------------------------------------------------
    def _harvest_and_report(self):
        miners = self.reg.miner_labels()
        hi = config.epoch_range(self.epochs[-1])[1]

        epoch_weights = self.wr.epoch_weights_from_logs()          # {epoch:{miner:w}}
        # scan from block 1 so funding/setup txs (mined before the first sampled
        # epoch) also resolve their confirming height; proposer tallies below key by
        # epoch, so the extra pre-sampling heights are simply ignored.
        txid2h, h2prop = self.wr.block_tx_index(1, hi)            # tx->height, height->proposer

        # proposer tally per epoch (from actual confirming heights).
        epoch_proposers = collections.defaultdict(collections.Counter)
        for h, lbl in h2prop.items():
            if lbl is None:
                continue
            epoch_proposers[config.height_to_epoch(h)][lbl] += 1

        self._write_esg_scores()
        self._write_transactions(txid2h)
        self._write_epochs_summary(miners, epoch_weights, epoch_proposers, txid2h)
        self._write_weights_evolution(miners, epoch_weights, epoch_proposers)
        if self.mode == "wpoa":
            self._write_wpoa_proposer_log(miners, epoch_weights, epoch_proposers)
        self._write_summary(epoch_weights, epoch_proposers)

    def _weights_for(self, epoch_weights, miners, e):
        """{miner: weight} for epoch e (missing -> 0) and its normalized probs."""
        w = dict((m, epoch_weights.get(e, {}).get(m, 0)) for m in miners)
        p = WeightReader.normalized(w)
        return w, p

    def _modal_proposer(self, epoch_proposers, e):
        c = epoch_proposers.get(e)
        return c.most_common(1)[0][0] if c else ""

    def _write_esg_scores(self):
        # ESG is static (published once, pre-simulation): epoch 0 marks that.
        rows = []
        for m in range(config.NUM_MINERS):
            mlabel = config.miner_id(m)
            # the miner's own certified score (company_id == miner label).
            addr, score, txid = self.esg_pub.get(mlabel, (None, None, None))
            rows.append([0, mlabel, mlabel, score, mlabel, txid or ""])
            for c in range(config.COMPANIES_PER_MINER):
                clabel = config.company_id(m, c)
                addr, score, txid = self.esg_pub.get(clabel, (None, None, None))
                rows.append([0, clabel, mlabel, score, mlabel, txid or ""])
        self.csv.esg_scores(rows)

    def _write_transactions(self, txid2h):
        rows = []
        for t in self.tx_records:
            txid = t.get("txid")
            h = txid2h.get(txid) if txid else None
            confirmed = h is not None
            # attribute to the confirming block's epoch when known.
            epoch = config.height_to_epoch(h) if confirmed else t.get("epoch")
            rows.append([epoch, h if confirmed else "", txid or "", t["sender"],
                         t["receiver"], t["type"], t["amount"],
                         "yes" if confirmed else "no"])
        self.csv.transactions(rows)

    def _tx_count_in_epoch(self, txid2h, e):
        n = 0
        for t in self.tx_records:
            txid = t.get("txid")
            if not txid or t["type"] in ("funding", "reconciliation"):
                continue
            h = txid2h.get(txid)
            if h is not None and config.height_to_epoch(h) == e:
                n += 1
        return n

    def _write_epochs_summary(self, miners, epoch_weights, epoch_proposers, txid2h):
        rows = []
        for e in self.epochs:
            w, p = self._weights_for(epoch_weights, miners, e)
            _, end = config.epoch_range(e)
            proposer = self._modal_proposer(epoch_proposers, e)
            wcols = [w.get(config.miner_id(i), 0) for i in range(4)]
            pcols = ["%.4f" % p.get(config.miner_id(i), 0.0) for i in range(4)]
            rows.append([e, self.mode, end, proposer, self.method]
                        + wcols + pcols
                        + [self._tx_count_in_epoch(txid2h, e),
                           "yes" if self.recon_done.get(e) else "no", _now()])
            if self.mode == "native":
                expected = max(w, key=lambda k: w[k]) if any(w.values()) else ""
                self.log.info("epoch %d: round-robin proposer=%s ; wPoA would favour=%s"
                              % (e, proposer, expected))
        self.csv.epochs_summary(rows)

    def _write_weights_evolution(self, miners, epoch_weights, epoch_proposers):
        rows = []
        prev = {}
        for e in self.epochs:
            w, p = self._weights_for(epoch_weights, miners, e)
            proposer = self._modal_proposer(epoch_proposers, e)
            for m in miners:
                delta = w[m] - prev.get(m, w[m]) if prev else 0
                rows.append([e, m, w[m], "%.4f" % p[m], "%.4f" % p[m],
                             "yes" if m == proposer else "no", delta])
            prev = w
        self.csv.weights_evolution(rows)

    def _write_wpoa_proposer_log(self, miners, epoch_weights, epoch_proposers):
        rows = []
        cum = collections.Counter()
        for e in self.epochs:
            w, p = self._weights_for(epoch_weights, miners, e)
            proposer = self._modal_proposer(epoch_proposers, e)
            expected = max(w, key=lambda k: w[k]) if any(w.values()) else ""
            for m, n in epoch_proposers.get(e, {}).items():
                if m in miners:
                    cum[m] += n
            total_blocks = sum(cum.values()) or 1
            # cumulative L1 deviation between observed share and expected (weight) share.
            dev = 0.0
            for m in miners:
                obs = cum[m] / float(total_blocks)
                dev += abs(obs - p[m])
            rows.append([e, proposer, "%.4f" % p.get(proposer, 0.0), expected,
                         "yes" if proposer == expected else "no"]
                        + [cum[config.miner_id(i)] for i in range(4)]
                        + ["%.4f" % dev])
        self.csv.wpoa_proposer_log(rows)

    def _write_summary(self, epoch_weights, epoch_proposers):
        total = collections.Counter()
        for e in self.epochs:
            for m, n in epoch_proposers.get(e, {}).items():
                total[m] += n
        stats = [("mode", self.mode),
                 ("epochs sampled", "%d..%d" % (self.epochs[0], self.epochs[-1])),
                 ("transactions recorded", len(self.tx_records)),
                 ("blocks by miner", dict(total)),
                 ("final getallweights", self.wr.get_all_weights())]
        self.log.summary(stats)
        for k, v in stats:
            self.log.info("SUMMARY %s: %s" % (k, v))


def main():
    mode = parse_mode(sys.argv)
    return Experiment(mode).run()


if __name__ == "__main__":
    sys.exit(main())
