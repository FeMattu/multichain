#!/usr/bin/env python3
# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# experimental_test.py -- entry point for the WeightEngine experimental simulation.
#
# Drives a real local MultiChain network modelled on MyLedger -- 1 ADMIN node (the
# Apuana SB stand-in) + 5 cluster miners (ClusterMinerA..E), 10 aziende per cluster --
# through a configurable number of epochs, in ONE of two modes selected by a
# MANDATORY flag:
#
#   --mode=wpoa    master switch on  -> the engine's weights drive weighted
#                                       proposer selection.
#   --mode=native  master off        -> native round-robin mining, while the engine
#                                       still computes + publishes w_k to wpoa-weights.
#
# It never reimplements the weight math for consensus purposes: the ADMIN publishes
# the public inputs (ESG, membership, per-epoch reconciliation) through the sanctioned
# admin RPCs, the nodes compute w_k, and this harness READS the results
# (getallweights + the engine's per-epoch debug.log lines) and the mined blocks.
#
# WHAT CHANGED FROM THE ORIGINAL (Apuana SB) SUITE
#  * Topology is MyLedger's: 5 clusters x 10 aziende, integer ESG in [10,20], and an
#    ADMIN that is also the reconciliation counterparty.
#  * The economics are real and on chain (helpers/economics.py): GAS (1 GAS = 1 EUR)
#    is a divisible asset, every transaction costs ALPHA = 0.2 GAS, the FEEPOOL settles
#    Guadagno_k = TxMiner_k * ALPHA to each miner, the miner returns Resi_k to the
#    ADMIN, and Giacenza_k is read back as the miner's balance after that transfer.
#  * Reconciliation is fully AUTOMATED at each epoch boundary and the amount published
#    to the reconciliation stream is the amount read back off chain -- never a random
#    draw, as it was before.
#  * The run ends with an invariant pass (see _verify) written to assertions.csv.
#
# Design notes:
#  * A tx's epoch is the epoch of its CONFIRMING block (resolved from the block
#    index), so a transfer near an epoch boundary is attributed to where it
#    actually landed -- not assumed.
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
from helpers.chain_setup import Network
from helpers.participants import ParticipantRegistry
from helpers.stream_writer import StreamWriter
from helpers.tx_simulator import TxSimulator
from helpers.weight_reader import WeightReader
from helpers.economics import EconomicsEngine
from helpers.esg_generator import generate_scores, cluster_config_rows


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
        "WE_COMPANIES, WE_EPOCHS, WE_EPOCH_LENGTH, WE_TX_MIN, WE_TX_MAX,\n"
        "WE_RESO_RATES, WE_SETUP_BLOCKS, WE_BLOCK_TIME, ...\n")
    sys.exit(code)


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _rank_concordance(a, b):
    """Fraction of unordered key pairs that `a` and `b` order the same way (a tie in
    one must be a tie in the other to count). 1.0 for identical orderings, 0.0 for
    exactly reversed. None when there is no pair to compare."""
    keys = sorted(set(a) & set(b))
    pairs = concordant = 0
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            x, y = keys[i], keys[j]
            pairs += 1
            sa = (a[x] > a[y]) - (a[x] < a[y])
            sb = (b[x] > b[y]) - (b[x] < b[y])
            if sa == sb:
                concordant += 1
    return (concordant / float(pairs)) if pairs else None


class Experiment(object):
    def __init__(self, mode):
        self.mode = mode
        self.outdir = os.path.join(HERE, "output")
        reset_output(self.outdir)
        self.log = LogReporter(os.path.join(self.outdir, "experiment.log"))
        self.csv = CsvReporter(self.outdir)
        self.net = Network(mode, self.log)
        self.reg = None
        self.econ = None
        # collected data
        self.esg = {}              # label -> certified ESG score
        self.esg_pub = {}          # label -> (addr, score, txid)
        self.tx_records = []       # list of tx dicts
        self.recon_done = {}       # epoch -> bool
        self._cons = None          # cached conservation_report (57 balance reads)
        self.epochs = []           # simulated epoch indices
        self.method = ("wpoa-weighted" if mode == "wpoa" else "native-roundrobin")

    # -- orchestration ------------------------------------------------------
    def run(self):
        self.log.header(self.mode, [
            ("seed", config.SEED),
            ("clusters", config.NUM_MINERS),
            ("aziende", config.num_companies()),
            ("epochs", config.NUM_EPOCHS),
            ("epoch_len", config.EPOCH_LENGTH),
            ("margin", config.STABILITY_MARGIN),
            ("kappa/alpha/lambda", "%g / %g / %g" % (config.KAPPA, config.ALPHA, config.LAMBDA)),
            ("gas", "%s (1 GAS = %g EUR, alpha = %g GAS/tx)"
             % (config.GAS_ASSET_NAME, config.GAS_PER_EURO, config.ALPHA)),
            ("esg range", "%d..%d" % (config.ESG_MIN, config.ESG_MAX)),
            ("tx/azienda", "%d..%d" % (config.TX_PER_COMPANY_MIN, config.TX_PER_COMPANY_MAX)),
            ("reso rates", ", ".join("%s=%.2f" % (config.cluster_letter(i), config.reso_rate(i))
                                     for i in range(config.NUM_MINERS))),
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
        self.esg = generate_scores()
        self.esg_pub = self.sw.publish_esg(self.esg)
        membership = self.sw.publish_membership()
        last_mtx = [x[2] for x in membership if x[2]]
        if last_mtx:
            self.net.wait_confirmed(self.net.admin, last_mtx[-1])
        # issue GAS and fund participants so they can transact (produce activity tau).
        self.tx_records += self.txsim.setup()
        # the miners publish w_k here; the ADMIN (not a cluster miner) must create it.
        self.net.ensure_wpoa_weights_stream()
        # the ADMIN must never propose a block.
        self.net.demote_admin_from_mining()
        # the economics/reconciliation engine needs the ESG map and the stream writer.
        self.econ = EconomicsEngine(self.net, self.reg, self.sw, self.wr,
                                    self.log, self.esg)

    def _warmup_weights(self):
        """Wait until every miner has published a weight, so wPoA selection has a
        weight map to work from before the sampled epochs begin."""
        self.log.info("warm-up: waiting for all %d cluster miners to publish a weight ..."
                      % config.NUM_MINERS)
        w = self.wr.wait_all_miners_weighted()
        got = len(self.reg.miner_address_set().intersection(w.keys()))
        if got < config.NUM_MINERS:
            self.log.warn("only %d/%d miners weighted after warm-up (continuing)"
                          % (got, config.NUM_MINERS))
        else:
            self.log.info("all cluster miners weighted: %s" % w)

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
        self.econ.snapshot_opening_balances()
        # Index the setup blocks, so the funding / ESG / membership transactions resolve
        # their confirming height in transactions.csv instead of reading as unconfirmed.
        # From here on the index stays contiguous: close_epoch extends it each epoch.
        self.econ.extend_index(h0)

        for e in self.epochs:
            start, end = config.epoch_range(e)
            self.net.wait_height(start, stallmsg="waiting to enter epoch %d" % e)
            self.tx_records += self.txsim.generate_epoch_txs(e)
            # Settlement + reconciliation happen only once the epoch's last block is
            # mined: TxMiner (hence Guadagno) is not defined until then.
            self.net.wait_height(end + 1, stallmsg="mining epoch %d" % e)
            rows, _ = self.econ.close_epoch(e, self.tx_records)
            self.recon_done[e] = all(r["recon_stream_txid"] for r in rows)

        # The settlement/reconciliation transfers are part of the ledger too. They are
        # appended once, here: close_epoch's activity count deliberately ignores them
        # (they are settlement, not network traffic), while the engine-tau replay and
        # transactions.csv both need them.
        self.tx_records += list(self.econ.settlement_tx)

        # bury the last epoch so every sampled epoch's weight gets published.
        last_end = config.epoch_range(self.epochs[-1])[1]
        bury_to = last_end + config.STABILITY_MARGIN + 2
        self.log.info("driving to height %d to bury the last epoch ..." % bury_to)
        self.net.wait_height(bury_to, stallmsg="burying last epoch")
        # give the miners' engine threads a moment to publish the last epoch.
        self.wr.wait_all_miners_weighted(timeout=30)
        # index the burial tail so late-confirming transfers resolve their epoch.
        self.econ.extend_index(self.net.admin.block_count())

    # -- reporting ----------------------------------------------------------
    def _harvest_and_report(self):
        miners = self.reg.miner_labels()
        epoch_weights = self.wr.epoch_weights_from_logs()          # {epoch:{miner:w}}

        # proposer tally per epoch, from the cumulative block index the economics
        # engine already built (heights 0..tip), so no block is read twice.
        epoch_proposers = collections.defaultdict(collections.Counter)
        for h, b in self.econ.block_idx.items():
            if b.get("miner"):
                epoch_proposers[config.height_to_epoch(h)][b["miner"]] += 1

        self._replay_for_crosscheck(epoch_weights, epoch_proposers)

        self._write_config_sheet()
        self._write_esg_scores()
        self._write_transactions()
        self._write_epochs_summary(miners, epoch_weights, epoch_proposers)
        self._write_weights_evolution(miners, epoch_weights, epoch_proposers)
        if self.mode == "wpoa":
            self._write_wpoa_proposer_log(miners, epoch_weights, epoch_proposers)
        self.csv.cluster_economics(self.econ.cluster_rows)
        self.csv.company_activity(self.econ.company_rows)
        self._verify(epoch_weights)
        self._write_summary(epoch_proposers)

    def _replay_for_crosscheck(self, epoch_weights, epoch_proposers):
        """Fill each cluster_economics row with the engine's published weight and with
        the harness-recomputed W_k / A_k (see EconomicsEngine's mirror caveat)."""
        by_key = dict(((r["epoch"], r["cluster"]), r) for r in self.econ.cluster_rows)
        state = {}
        for e in self.epochs:
            tau = self.econ.engine_tau(e, self.tx_records)
            # the ABSOLUTE epoch, so the feedback bracket applies exactly as it does on
            # the node (which always replays from epoch 1) -- see replay_epoch.
            replay, state = self.econ.replay_epoch(e, tau, state, e)
            w = dict((m, epoch_weights.get(e, {}).get(m, 0))
                     for m in self.reg.miner_labels())
            p = WeightReader.normalized(w)
            proposer = self._modal_proposer(epoch_proposers, e)
            for m, rep in replay.items():
                row = by_key.get((e, m))
                if row is None:
                    continue
                row["engine_weight"] = w.get(m, 0)
                row["engine_prob"] = round(p.get(m, 0.0), 6)
                row["selected_proposer"] = "yes" if m == proposer else "no"
                row["raw_weight_recomputed"] = round(rep["raw_weight"], 6)
                row["allocation_recomputed"] = round(rep["allocation"], 6)

    def _weights_for(self, epoch_weights, miners, e):
        """{miner: weight} for epoch e (missing -> 0) and its normalized probs."""
        w = dict((m, epoch_weights.get(e, {}).get(m, 0)) for m in miners)
        p = WeightReader.normalized(w)
        return w, p

    def _modal_proposer(self, epoch_proposers, e):
        c = epoch_proposers.get(e)
        return c.most_common(1)[0][0] if c else ""

    def _theta_of(self, e):
        return sum(r["tx_utente"] for r in self.econ.company_rows if r["epoch"] == e)

    # -- writers ------------------------------------------------------------
    def _write_config_sheet(self):
        rows = []
        for c in cluster_config_rows(self.esg):
            rows.append({
                "cluster": c["miner"], "letter": c["letter"],
                "esg_cluster": c["esg"], "iso_certificate": c["iso"],
                "reso_rate_nominal": c["reso_rate"],
                "companies": ";".join(x["label"] for x in c["companies"]),
                "esg_companies": ";".join(str(x["esg"]) for x in c["companies"]),
            })
        self.csv.config_sheet(rows)

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

    def _write_transactions(self):
        rows = []
        for t in self.tx_records:
            txid = t.get("txid")
            h = self.econ.txid2h.get(txid) if txid else None
            confirmed = h is not None
            # attribute to the confirming block's epoch when known.
            epoch = config.height_to_epoch(h) if confirmed else t.get("epoch")
            rows.append([epoch, h if confirmed else "", txid or "", t["sender"],
                         t["receiver"], t["type"], t["amount"],
                         "yes" if confirmed else "no"])
        self.csv.transactions(rows)

    def _write_epochs_summary(self, miners, epoch_weights, epoch_proposers):
        rows = []
        for e in self.epochs:
            w, p = self._weights_for(epoch_weights, miners, e)
            _, end = config.epoch_range(e)
            proposer = self._modal_proposer(epoch_proposers, e)
            theta = self._theta_of(e)
            tx_count = theta + sum(r["tau_miner_signed"] for r in self.econ.cluster_rows
                                   if r["epoch"] == e)
            rows.append([e, self.mode, end, proposer, self.method]
                        + [w.get(m, 0) for m in miners]
                        + ["%.4f" % p.get(m, 0.0) for m in miners]
                        + [tx_count, theta,
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
                        + [cum[m] for m in miners]
                        + ["%.4f" % dev])
        self.csv.wpoa_proposer_log(rows)

    # -- invariants ---------------------------------------------------------
    def _verify(self, epoch_weights):
        """Check the experiment's invariants and write assertions.csv. Every check is
        recorded with its verdict and evidence; a failure is logged as an ERROR but
        does not abort the run, so the artifacts are always complete."""
        checks = []

        def add(name, scope, ok, detail):
            checks.append({"check": name, "scope": scope,
                           "verdict": "PASS" if ok else "FAIL", "detail": detail})
            (self.log.info if ok else self.log.error)(
                "ASSERT %-28s %-14s %s -- %s" % (name, scope,
                                                 "PASS" if ok else "FAIL", detail))

        miners = self.reg.miner_labels()
        rows_by_epoch = collections.defaultdict(dict)
        for r in self.econ.cluster_rows:
            rows_by_epoch[r["epoch"]][r["cluster"]] = r

        # 1. weight ordering vs the ESG + activity composite (and vs the replay).
        conc_raw, conc_w, compared = [], [], 0
        for e in self.epochs:
            w = dict((m, epoch_weights.get(e, {}).get(m, 0)) for m in miners)
            if not any(w.values()):
                continue
            rows = rows_by_epoch.get(e, {})
            if len(rows) < 2:
                continue
            composite = dict((m, rows[m]["esg"] * (rows[m]["tau_miner_signed"]
                                                   + rows[m]["impatto_cluster"]))
                             for m in rows)
            replayed = dict((m, rows[m].get("raw_weight_recomputed", 0.0)) for m in rows)
            c1 = _rank_concordance(w, composite)
            c2 = _rank_concordance(w, replayed)
            if c1 is not None:
                conc_raw.append(c1)
            if c2 is not None:
                conc_w.append(c2)
            compared += 1
        mean_raw = (sum(conc_raw) / len(conc_raw)) if conc_raw else 0.0
        mean_w = (sum(conc_w) / len(conc_w)) if conc_w else 0.0
        add("weight_ranking", "ESG+NumTx composite", mean_raw >= config.RANK_CONCORDANCE_MIN,
            "mean pairwise concordance %.4f over %d epochs (min %.2f); "
            "vs harness replay of W_k: %.4f"
            % (mean_raw, compared, config.RANK_CONCORDANCE_MIN, mean_w))

        # 2. conformity rate in [0, 100] %.
        bad = [(r["epoch"], r["cluster"], r["pct_reso"]) for r in self.econ.cluster_rows
               if not (-config.GAS_EPS <= r["pct_reso"] <= 100.0 + config.GAS_EPS)]
        add("conformity_rate_range", "all epochs x clusters", not bad,
            "all %d rows in [0,100]%%" % len(self.econ.cluster_rows) if not bad
            else "out of range: %s" % bad[:5])

        # 3. cumulative gain never decreases (Guadagno >= 0 every epoch).
        viol = []
        for m in miners:
            seq = [r["total_gain"] for r in sorted(
                (x for x in self.econ.cluster_rows if x["cluster"] == m),
                key=lambda x: x["epoch"])]
            for i in range(1, len(seq)):
                if seq[i] < seq[i - 1] - config.GAS_EPS:
                    viol.append((m, i, seq[i - 1], seq[i]))
        add("total_gain_monotonic", "per cluster", not viol,
            "monotonic across %d epochs for all %d clusters" % (len(self.epochs), len(miners))
            if not viol else "decreases: %s" % viol[:5])

        # 4. GAS conservation, entirely from chain reads.
        cons = self._conservation()
        tol = max(config.GAS_EPS * 100, 10 ** -config.GAS_DECIMALS)
        # Every non-coinbase transaction in the sampled epochs is validated by exactly
        # one cluster, so the per-cluster TxMiner tallies must add up to an independent
        # recount straight off the block index.
        add("tx_validated_once", "sampled epochs",
            cons["validated_total"] == cons["blocks_validated"]
            and cons["blocks_foreign"] == 0,
            "sum TxMiner %d vs blocks recount %d; %d block(s) with no cluster-miner "
            "proposer" % (cons["validated_total"], cons["blocks_validated"],
                          cons["blocks_foreign"]))
        # Guadagno is charged per VALIDATED transaction. That is more than Theta: the
        # settlement, reconciliation and governance traffic in those blocks is validated
        # too, so alpha*Theta is reported for comparison, not as an equality.
        overhead = cons["validated_total"] - cons["theta_total"]
        add("gas_fees_match_validation", "network",
            abs(cons["guadagno_total"] - config.ALPHA * cons["validated_total"])
            <= tol * len(self.epochs),
            "sum Guadagno %.4f = alpha * %d validated tx; azienda activity Theta=%d "
            "(alpha*Theta %.4f), so %d tx (%.1f%%) are settlement/governance traffic"
            % (cons["guadagno_total"], cons["validated_total"], cons["theta_total"],
               cons["alpha_theta"], overhead,
               (100.0 * overhead / cons["validated_total"]) if cons["validated_total"] else 0.0))
        add("gas_returned_to_admin", "ADMIN address",
            abs(cons["admin_delta"] - cons["resi_total"]) <= tol * len(self.epochs),
            "ADMIN balance delta %.4f vs sum Resi read off chain %.4f"
            % (cons["admin_delta"], cons["resi_total"]))
        add("gas_supply_conserved", "all addresses",
            abs(cons["on_network"] - cons["issued"]) <= tol * 10,
            "balances now %.4f vs issued supply %.4f (delta %.4f)"
            % (cons["on_network"], cons["issued"],
               cons["on_network"] - cons["issued"]))
        add("feepool_paid_out", "FEEPOOL address",
            abs(cons["feepool_delta"] + cons["guadagno_total"]) <= tol * len(self.epochs),
            "FEEPOOL balance delta %.4f vs -sum Guadagno %.4f"
            % (cons["feepool_delta"], -cons["guadagno_total"]))

        self.csv.assertions(checks)
        failed = [c["check"] for c in checks if c["verdict"] == "FAIL"]
        if failed:
            self.log.error("INVARIANTS FAILED: %s (see output/assertions.csv)" % failed)
        else:
            self.log.info("all %d invariants hold" % len(checks))
        return checks

    def _conservation(self):
        """conservation_report(), read once and reused: it costs one balance query per
        participant and both the invariant pass and the summary need it."""
        if self._cons is None:
            self._cons = self.econ.conservation_report()
        return self._cons

    def _write_summary(self, epoch_proposers):
        total = collections.Counter()
        for e in self.epochs:
            for m, n in epoch_proposers.get(e, {}).items():
                total[m] += n
        cons = self._conservation()
        http_calls, cli_calls = self.net.rpc_stats()
        stats = [("mode", self.mode),
                 ("epochs sampled", "%d..%d" % (self.epochs[0], self.epochs[-1])),
                 ("transactions recorded", len(self.tx_records)),
                 ("Theta (total company tx)", cons["theta_total"]),
                 ("Guadagno total (GAS)", cons["guadagno_total"]),
                 ("Resi total (GAS)", cons["resi_total"]),
                 ("Total GAIN per cluster", dict(self.econ.total_gain)),
                 ("blocks by miner", dict(total)),
                 ("rpc calls (http/cli)", "%d / %d" % (http_calls, cli_calls)),
                 ("final getallweights", self.wr.get_all_weights())]
        self.log.summary(stats)
        for k, v in stats:
            self.log.info("SUMMARY %s: %s" % (k, v))


def main():
    mode = parse_mode(sys.argv)
    return Experiment(mode).run()


if __name__ == "__main__":
    sys.exit(main())
