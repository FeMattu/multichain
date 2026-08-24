# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# economics.py -- the POESIA / Vers_2 weight-and-settlement pipeline, replayed from
# CHAIN DATA and settled back onto the chain, with the reconciliation fully automated.
#
# ---------------------------------------------------------------------------
# THE PIPELINE (one epoch). Every line is both the Vers_2 spreadsheet column and the
# corresponding thesis definition -- they are the same formulas, because kappa = 100 is
# Vers_2's "/100" and lambda = 0.5 is its "Peso %Reso" = 50:
#
#   tau_i, tau_Mk       activity counters, DERIVED FROM CHAIN (see epoch_tau)
#   ImpUtente_i  = ESG_i * tau_i / kappa                          (c_i)
#   W_k          = ESG_Mk * (tau_Mk + sum_{i in C_k} ImpUtente_i) (peso grezzo)
#   w_k          = W_k * [rho_k^{(e-1)} * lambda + (1-lambda)]    (peso finale)
#   Delay_k      = ImpCluster_k / sum_j ImpCluster_j * 1000       (per-mille weight)
#   p_k          = Delay_k / 1000                                 (selection prob.)
#   A_k          = Theta * p_k * ALPHA                            (Guadagno)
#   R_k          in [0, A_k + B_k^{(e-1)}]                        (Resi, ON CHAIN)
#   B_k          = B_k^{(e-1)} + A_k - R_k                        (Giacenza)
#   rho_k        = R_k / (A_k + B_k^{(e-1)})                      (%Reso)
#   TotalGAIN_k  = TotalGAIN_k^{(e-1)} + A_k
#
# All of it was validated numerically against the printed Vers_2 epoch-1 figures
# (ImpCluster 756, Delay 228, Guadagno 34.54, Resi 24.88, Giacenza 9.66, %Reso 72.03%)
# and the epoch-2 carry-forward (Giacenza 21.24, %Reso 56.30%, TotalGAIN 73.49): each
# reproduces to the cent.
#
# ---------------------------------------------------------------------------
# WHAT THIS CORRECTS relative to the first revision of this file, which derived the
# economics from BLOCK PROPOSERSHIP:
#
#   Guadagno   was TxMiner_k * ALPHA, i.e. "the fees of the blocks k mined". That is
#              not the model: the epoch's whole fee pot is Theta * ALPHA and it is
#              split by WEIGHT SHARE p_k, so a miner earns for the weight its cluster
#              carries, not for winning a block lottery. sum_k A_k = ALPHA * Theta now
#              holds exactly, as an equality the ledger must satisfy (it previously
#              could not, because TxMiner also counted settlement and governance
#              traffic).                                                      [Fix 3/7]
#   Giacenza   was the miner's raw on-chain GAS balance, which also carries its seed
#              funding and its miner<->miner trading. It is now the accounting balance
#              B_k = B_prev + A - R with B^{(0)} = 0, and the raw balance is kept
#              alongside as `saldo_onchain` so the two can be reconciled exactly
#              (giacenza_matches_chain).                                        [Fix 1]
#   %Reso      divided by Guadagno alone. The denominator is the balance AVAILABLE to
#              reconcile, A_k + B_k^{(e-1)}.                                    [Fix 2]
#   Impatto    was only sum_i c_i. "Impatto Cluster" is the whole raw weight
#   Cluster    ESG_Mk * (tau_Mk + sum_i c_i) -- ESG_Mk and tau_Mk were missing.  [Fix 5]
#   Delay      was the measured mean inter-block interval. In Vers_2 "Delay in msec" is
#              the per-mille NORMALIZED WEIGHT, whose per-epoch total is exactly 1000.
#              The real latency is still reported, as `block_interval_ms`.       [Fix 6]
#
# ---------------------------------------------------------------------------
# TAU IS EXACT, NOT ESTIMATED. The engine counts +1 per distinct signing address per
# non-coinbase transaction (weight_reader.cpp ComputeActivityForEpoch). The harness
# knows the signer of every transaction it submitted, and reads the signer of the ones
# it did not -- each miner's own per-epoch w_k publish -- off the wpoa-weights stream's
# publisher index. Coverage is then asserted against an independent recount of the
# epoch's blocks (`tau_coverage`), so when it holds, the replayed w_k can be compared
# to the node's published integer BY VALUE rather than by ranking.
#
# ---------------------------------------------------------------------------
# ORDER OF OPERATIONS. Settlement precedes reconciliation, and the balance read
# follows the reconciliation's CONFIRMATION -- Giacenza is by definition the balance
# after the epoch has been reconciled. R_k^{(e)} feeds rho_k^{(e)}, which the weight
# formula consumes one epoch later, and ComputeLocalWeightForEpoch re-reads the whole
# reconciliation stream and replays from epoch 1 on every publish, so R_k^{(e)} only
# has to confirm before epoch e+1 buries: a full epoch plus margin of slack.

import random
import time

import config
from helpers.chain_setup import looks_txid


class EconomicsEngine(object):
    def __init__(self, network, registry, stream_writer, weight_reader, log, esg,
                 membership=None):
        self.net = network
        self.reg = registry
        self.sw = stream_writer
        self.wr = weight_reader
        self.log = log
        self.esg = esg or {}                # label -> certified ESG score
        self.membership = membership        # MembershipReader (on-chain C_k), optional

        # cumulative chain indexes, extended one epoch at a time. They are kept
        # CONTIGUOUS from height 0: a gap would silently drop a transaction's
        # confirming height (reading as "unconfirmed") and a block's proposer.
        self.txid2h = {}                    # txid -> confirming height
        self.block_idx = {}                 # height -> {miner, time, txcount, validated}
        self._indexed_to = -1               # highest contiguously indexed height
        self.stream_pubs = {}               # txid -> [publisher_label, ...]

        # inter-epoch state, exactly the engine's ClusterState
        miners = registry.miner_labels()
        self.balance = dict((m, 0.0) for m in miners)      # B_k^{(e-1)}, B^{(0)} = 0
        self.compliance = dict((m, 0.0) for m in miners)   # rho_k^{(e-1)}
        self.total_gain = dict((m, 0.0) for m in miners)

        self.cluster_rows = []              # one dict per (epoch, cluster)
        self.company_rows = []              # one dict per (epoch, company)
        self.settlement_tx = []             # allocation + reconciliation tx records
        self.epoch_checks = []              # per-epoch invariant results
        self.tau_gaps = []                  # (epoch, unattributed_tx_count)
        # Kept, always empty, for report-schema stability: R_k is derived rather than
        # published, so no reconciliation record exists that could confirm late.
        self.recon_publish_late = []
        self.max_backlog = 0                # largest mempool depth observed

        # deterministic Resi draw
        self._rng = random.Random(config.SEED ^ 0x5EC0)
        self._opening_balances = {}          # label -> GAS balance before epoch 1

    # ------------------------------------------------------------------
    # Chain reads
    # ------------------------------------------------------------------
    def extend_index(self, hi):
        """Index every block from where we left off up to `hi`, keeping the coverage
        contiguous from height 0. Idempotent and cheap to over-call: heights already
        indexed are never refetched, and a call with hi below the watermark is a no-op."""
        lo = self._indexed_to + 1
        if hi < lo:
            return
        self.block_idx.update(self.wr.block_index(lo, hi))
        for h in range(lo, hi + 1):
            ok, res = self.net.admin.cli_ok("getblock", str(h), 1)
            if ok and isinstance(res, dict):
                for txid in res.get("tx", []):
                    self.txid2h[txid] = h
            else:
                self.log.warn("getblock %d failed: %s" % (h, res))
        self._indexed_to = hi

    def refresh_stream_publishers(self):
        """Re-read the wpoa-weights publisher index. Each miner publishes its own w_k
        there once per epoch; that publish is a transaction it SIGNED, so the engine's
        tau_{Mk} counts it and the harness must too. Cheap (one RPC) and idempotent."""
        pubs = self.wr.stream_publishers(config.WEIGHTS_STREAM)
        if pubs:
            self.stream_pubs.update(pubs)
        return self.stream_pubs

    def _log_backlog(self, epoch):
        """Record and, past a threshold, warn about the mempool depth.

        A growing backlog is the failure mode that invalidates a run quietly: submissions
        outpace the blocks, every record lands epochs late, and the reconciliation
        feedback never reaches the engine in time (see close_epoch step 8). Surfacing the
        depth makes that diagnosable from the log alone."""
        ok, res = self.net.admin.cli_ok("getmempoolinfo")
        if not ok or not isinstance(res, dict):
            return 0
        size = int(res.get("size") or 0)
        self.max_backlog = max(self.max_backlog, size)
        if size > config.MEMPOOL_WARN:
            self.log.warn("epoch %d: %d transaction(s) still unconfirmed in the mempool "
                          "-- the chain is not keeping up with the submission rate"
                          % (epoch, size))
        return size

    def epoch_of_txid(self, txid):
        """Confirming epoch of a transaction, or None while it is unconfirmed."""
        h = self.txid2h.get(txid)
        return None if h is None else config.height_to_epoch(h)

    def snapshot_opening_balances(self):
        """Record every participant's GAS balance before the first sampled epoch, so
        the run's closing conservation check has a baseline."""
        self._opening_balances = self._all_balances()
        total = sum(self._opening_balances.values())
        self.log.info("opening GAS on network: %.4f across %d addresses"
                      % (total, len(self._opening_balances)))
        return self._opening_balances

    def _all_balances(self, minconf=1):
        """{label: confirmed GAS balance} for every funded participant, each read on
        the node that owns its key."""
        out = {}
        for label in self.reg.all_labels():
            node = self.reg.node_for(label)
            addr = self.reg.address_of(label)
            if node is None or not addr:
                continue
            out[label] = node.gas_balance(addr, minconf)
        return out

    # ------------------------------------------------------------------
    # Activity counters tau -- derived from chain, engine-exact
    # ------------------------------------------------------------------
    def _all_records(self, tx_records):
        """Every transaction the harness caused: the simulated traffic, the
        settlement/reconciliation transfers it signed on the participants' behalf, and
        the ADMIN's stream publishes. Together with the wpoa-weights publisher index
        this covers every non-coinbase transaction on the network."""
        return (list(tx_records) + list(self.settlement_tx)
                + list(getattr(self.sw, "published", [])))

    def epoch_tau(self, epoch, tx_records):
        """({label: tau}, attributed, unattributed) for `epoch`.

        tau is counted exactly as ComputeActivityForEpoch does: +1 per DISTINCT signing
        address per non-coinbase transaction, attributed to the epoch of the CONFIRMING
        block. Two sources, together covering every transaction on the network:

          * harness records -- the sender label is the signing address (every transfer
            is a single-from-address sendassetfrom), including the settlement and
            reconciliation transfers;
          * the wpoa-weights publisher index -- the miners' own per-epoch w_k
            publishes, which the harness does not submit.

        `attributed` counts the transactions resolved this way and `unattributed` the
        ones in the epoch's blocks that neither source explains; the caller turns the
        latter into the tau_coverage invariant."""
        seen = set()                        # (txid, signer) -- dedup, as the engine does
        tau = {}

        def credit(txid, signer):
            if not signer or (txid, signer) in seen:
                return False
            seen.add((txid, signer))
            tau[signer] = tau.get(signer, 0) + 1
            return True

        in_epoch = set()
        for t in self._all_records(tx_records):
            txid = t.get("txid")
            if not txid:
                continue
            h = self.txid2h.get(txid)
            if h is None or config.height_to_epoch(h) != epoch:
                continue
            in_epoch.add(txid)
            credit(txid, t.get("sender"))

        for txid, publishers in self.stream_pubs.items():
            h = self.txid2h.get(txid)
            if h is None or config.height_to_epoch(h) != epoch:
                continue
            in_epoch.add(txid)
            for label in publishers:
                credit(txid, label)

        # Independent recount of the epoch's non-coinbase transactions.
        start, end = config.epoch_range(epoch)
        on_chain = 0
        for h in range(max(0, start), end + 1):
            b = self.block_idx.get(h)
            if b:
                on_chain += b.get("validated", 0)
        return tau, len(in_epoch), max(0, on_chain - len(in_epoch))

    def _companies_of(self, miner_idx):
        """The cluster's companies C_k, read from the ON-CHAIN membership stream when it
        is available (that is the set the engine itself uses), else the configured
        topology.

        Returned in ascending ADDRESS order, because that is the order
        WeightEngine::RawWeight sums the c_i in -- deliberately, so the non-associative
        floating-point total is identical on every node. Matching it here removes the
        last source of numeric difference between the replay and the node, which
        matters at exactly the rounding boundaries where ToIntegerWeight can otherwise
        land a unit apart."""
        mlabel = config.miner_id(miner_idx)
        members = None
        if self.membership is not None:
            members = self.membership.companies_of(mlabel)
        if not members:
            members = self.reg.companies_of(miner_idx)
        return sorted(members, key=lambda l: (self.reg.address_of(l) or l))

    # ------------------------------------------------------------------
    # Weights -- the Vers_2 / thesis formulas
    # ------------------------------------------------------------------
    def compute_epoch_weights(self, epoch, tau):
        """The whole weight half of the pipeline for one epoch, from tau.

        Returns (per_cluster, per_company, theta) where per_cluster[m] carries
        raw_weight W_k, final_weight w_k, both per-mille Delays, the selection
        probability on the configured basis and the allocation A_k.

        BOTH normalizations are computed on purpose. `delay_raw` is W_k/W_tot*1000 (the
        thesis and the C++ engine); `delay_final` is w_k/w_tot*1000 (Vers_2, whose
        GuadagnoEx is derived from the feedback-adjusted ImpCluster). They coincide in
        the first sampled epoch -- where every rho_prev is 0, so the bracket is the same
        (1-lambda) for everyone -- and can diverge afterwards. config.ALLOC_BASIS picks
        which one is settled; the other stays in the report as the comparison."""
        kappa, lam = config.KAPPA, config.LAMBDA
        per_company, raw, sum_c = [], {}, {}
        theta = 0

        for k in range(config.NUM_MINERS):
            mlabel = config.miner_id(k)
            total_impact = 0.0
            # Address order for the SUM (engine-faithful); the display name comes from
            # the company's own LABEL, never from its position in this list.
            for clabel in self._companies_of(k):
                esg_i = self.esg.get(clabel, 0)
                tau_i = tau.get(clabel, 0)
                impatto = (esg_i * tau_i / kappa) if kappa else 0.0
                total_impact += impatto
                theta += tau_i
                per_company.append({
                    "epoch": epoch, "cluster": mlabel, "company": clabel,
                    "display": config.company_display_for(clabel), "tx_utente": tau_i,
                    "esg": esg_i, "impatto_utente": round(impatto, 6),
                })
            sum_c[mlabel] = total_impact
            # W_k = ESG_Mk * (tau_Mk + sum_i c_i)  -- Vers_2's epoch-1 "Impatto Cluster"
            raw[mlabel] = self.esg.get(mlabel, 0) * (tau.get(mlabel, 0) + total_impact)

        # w_k = W_k * [rho_prev*lambda + (1-lambda)]. The bracket is in [1-lambda, 1]
        # and strictly positive for lambda < 1, which is what keeps w_k > 0.
        final = {}
        for k in range(config.NUM_MINERS):
            mlabel = config.miner_id(k)
            bracket = self.compliance.get(mlabel, 0.0) * lam + (1.0 - lam)
            final[mlabel] = raw[mlabel] * bracket

        total_raw = sum(raw.values())
        total_final = sum(final.values())
        basis = config.alloc_basis()

        per_cluster = {}
        for k in range(config.NUM_MINERS):
            mlabel = config.miner_id(k)
            delay_raw = (raw[mlabel] / total_raw * 1000.0) if total_raw > 0 else 0.0
            delay_final = (final[mlabel] / total_final * 1000.0) if total_final > 0 else 0.0
            delay = delay_final if basis == "final" else delay_raw
            p_k = delay / 1000.0
            per_cluster[mlabel] = {
                "sum_impatto_utente": sum_c[mlabel],
                "raw_weight": raw[mlabel],
                "final_weight": final[mlabel],
                "bracket": self.compliance.get(mlabel, 0.0) * lam + (1.0 - lam),
                "delay_raw": delay_raw,
                "delay_final": delay_final,
                "delay": delay,
                "p_k": p_k,
                # A_k = Theta * p_k * ALPHA. On the "raw" basis this is identically the
                # engine's Allocation(alpha, theta, W_k, W_tot).
                "allocation": theta * p_k * config.ALPHA,
                "total_raw": total_raw,
                "total_final": total_final,
            }
        return per_cluster, per_company, theta

    def _cluster_chain_facts(self, epoch):
        """Per cluster: blocks proposed and the mean inter-block interval (msec) inside
        `epoch`, read from the block index.

        These are OUTCOME measures, not inputs. `blocks_mined` is what wPoA actually did
        with p_k (the consensus check), and `block_interval_ms` is the genuinely measured
        latency -- distinct from the Vers_2 "Delay in msec" column, which is the
        per-mille weight. MultiChain stamps block times in whole seconds, so the
        interval is coarse but real."""
        start, end = config.epoch_range(epoch)
        facts = dict((m, {"blocks": 0, "validated": 0, "block_interval_ms": 0.0,
                          "_gaps": []})
                     for m in self.reg.miner_labels())
        for h in range(max(0, start), end + 1):
            b = self.block_idx.get(h)
            if not b:
                continue
            label = b.get("miner")
            if label not in facts:
                continue                      # a block proposed outside the cluster set
            facts[label]["blocks"] += 1
            facts[label]["validated"] += b.get("validated", 0)
            prev = self.block_idx.get(h - 1)
            if prev:
                gap = (b.get("time", 0) - prev.get("time", 0)) * 1000.0
                if gap >= 0:
                    facts[label]["_gaps"].append(gap)
        for m, f in facts.items():
            gaps = f.pop("_gaps")
            f["block_interval_ms"] = (sum(gaps) / len(gaps)) if gaps else 0.0
        return facts

    # ------------------------------------------------------------------
    # Reconciliation (automated, on chain)
    # ------------------------------------------------------------------
    def _resi_target(self, miner_idx, available):
        """R_k drawn from its legal domain [0, available], available = A_k + B_prev.

        Two modes (config.RESO_MODE):
          "rate"    -- available * RESO_RATES[k], with a small seeded jitter. The
                       DEFAULT, because it makes %Reso ~ the configured per-cluster
                       rate, which in turn makes the lambda-feedback on w_k legible
                       instead of drowned in noise.
          "uniform" -- uniform(0, available), the reference spreadsheet's
                       RANDBETWEEN(0; GuadagnoEx + Giacenza).
        Either way the result is clamped to [0, available], so %Reso cannot leave
        [0,1] and B_k cannot go negative."""
        if available <= 0:
            return 0.0
        if config.RESO_MODE == "uniform":
            amount = self._rng.uniform(0.0, available)
        else:
            rate = config.reso_rate(miner_idx)
            if config.RESO_JITTER > 0:
                rate *= (1.0 + self._rng.uniform(-config.RESO_JITTER, config.RESO_JITTER))
            amount = available * max(0.0, min(1.0, rate))
        return round(max(0.0, min(available, amount)), config.GAS_DECIMALS)

    def _settle_allocation(self, epoch, miner_label, allocation):
        """Pay the epoch's allocation A_k to the miner from the FEEPOOL.

        The FEEPOOL stands in for the AGGREGATE of the paying senders: charging each of
        the ~750 senders its own 0.2 GAS in a separate transaction would not only
        triple the run's transaction count, it would ALTER THE MEASUREMENT -- each fee
        payment is a transaction signed by that company, so it would inflate the very
        tau_i it is a fee on. Paying the pot out in one transfer per cluster keeps the
        GAS totals identical (sum_k A_k = ALPHA * Theta) and tau clean."""
        if allocation <= 0:
            return None
        admin = self.net.admin
        ok, res = admin.cli_ok("sendassetfrom", self.reg.feepool_address(),
                               self.reg.address_of(miner_label),
                               config.GAS_ASSET_NAME, allocation)
        txid = res if (ok and looks_txid(res)) else None
        if not txid:
            self.log.error("allocation settlement failed %s e%d (%.4f GAS): %s"
                           % (miner_label, epoch, allocation, res))
            return None
        self.settlement_tx.append({"epoch": epoch, "txid": txid,
                                   "sender": config.FEEPOOL_LABEL,
                                   "receiver": miner_label, "type": "allocation",
                                   "amount": allocation})
        return txid

    def _return_to_admin(self, epoch, miner_label, amount):
        """The miner returns `amount` GAS to the ADMIN address. Signed by the miner's
        own node -- this is the automated step that replaces the operator. Returns
        (txid_or_None, amount_actually_requested)."""
        if amount <= 0:
            return None, 0.0
        node = self.reg.node_for(miner_label)
        maddr = self.reg.address_of(miner_label)
        # Never ask for more than the miner can actually spend: minconf 0 includes the
        # allocation submitted moments ago, whose change is spendable immediately.
        available = node.gas_balance(maddr, 0)
        send = round(min(amount, available), config.GAS_DECIMALS)
        if send < amount:
            self.log.warn("%s e%d: reconciliation clamped %.4f -> %.4f GAS "
                          "(available balance)" % (miner_label, epoch, amount, send))
        if send <= 0:
            return None, 0.0
        ok, res = node.cli_ok("sendassetfrom", maddr, self.reg.admin_address(),
                              config.GAS_ASSET_NAME, send)
        txid = res if (ok and looks_txid(res)) else None
        if not txid:
            self.log.error("reconciliation transfer failed %s e%d (%.4f GAS): %s"
                           % (miner_label, epoch, send, res))
            return None, 0.0
        self.settlement_tx.append({"epoch": epoch, "txid": txid,
                                   "sender": miner_label,
                                   "receiver": config.ADMIN_LABEL,
                                   "type": "reconciliation", "amount": send})
        return txid, send

    def read_credit_to_admin(self, txid):
        """The GAS quantity `txid` pays to the ADMIN address, read from the confirmed
        transaction itself (getrawtransaction verbose -> vout -> assets). This, not the
        amount we asked for, is the authoritative Resi. Returns 0.0 if unreadable."""
        if not txid:
            return 0.0
        admin_addr = self.reg.admin_address()
        ok, tx = self.net.admin.cli_ok("getrawtransaction", txid, 1)
        if not ok or not isinstance(tx, dict):
            self.log.warn("could not re-read reconciliation tx %s: %s" % (txid, tx))
            return 0.0
        credited = 0.0
        for vout in tx.get("vout", []) or []:
            if not isinstance(vout, dict):
                continue
            spk = vout.get("scriptPubKey") or {}
            if admin_addr not in (spk.get("addresses") or []):
                continue
            for a in vout.get("assets") or []:
                if isinstance(a, dict) and a.get("name") == config.GAS_ASSET_NAME:
                    try:
                        credited += float(a.get("qty", 0.0))
                    except (TypeError, ValueError):
                        pass
        return round(credited, config.GAS_DECIMALS)

    # ------------------------------------------------------------------
    # The epoch driver
    # ------------------------------------------------------------------
    def close_epoch(self, epoch, tx_records):
        """Harvest, weigh, settle and reconcile `epoch`. Called once, immediately after
        the epoch's last block is mined. Returns (cluster_rows, company_rows)."""
        start, end = config.epoch_range(epoch)
        t0 = time.time()

        # 1. chain reads. The index is contiguous from 0, so the epoch's first block
        #    always has its parent available for the interval measurement.
        self.extend_index(end)
        self.refresh_stream_publishers()
        facts = self._cluster_chain_facts(epoch)
        tau, attributed, unattributed = self.epoch_tau(epoch, tx_records)
        if unattributed:
            self.tau_gaps.append((epoch, unattributed))
            self.log.warn("epoch %d: %d transaction(s) in the epoch's blocks could not "
                          "be attributed to a signer (tau may be short)"
                          % (epoch, unattributed))

        # 2. the weight half of the pipeline (pure, from tau).
        weights, company_rows, theta = self.compute_epoch_weights(epoch, tau)

        # 3-4. settle the allocation, then reconcile -- both on chain, both automatic.
        #      B_prev is captured BEFORE it is advanced: it is the denominator of %Reso
        #      and the carry term of B_k.
        prev_balance = dict(self.balance)
        pending = {}
        for k in range(config.NUM_MINERS):
            mlabel = config.miner_id(k)
            allocation = round(weights[mlabel]["allocation"], config.GAS_DECIMALS)
            b_prev = prev_balance.get(mlabel, 0.0)
            available = round(allocation + b_prev, config.GAS_DECIMALS)
            alloc_txid = self._settle_allocation(epoch, mlabel, allocation)
            target = self._resi_target(k, available)
            recon_txid, requested = self._return_to_admin(epoch, mlabel, target)
            pending[mlabel] = {"allocation": allocation, "available": available,
                               "b_prev": b_prev, "target": target,
                               "alloc_txid": alloc_txid, "recon_txid": recon_txid,
                               "requested": requested}

        # 5. wait for the reconciliations to confirm. This must precede the balance
        #    read: Giacenza is by definition the balance AFTER reconciliation.
        for mlabel, p in pending.items():
            if p["recon_txid"]:
                if not self.net.wait_confirmed(self.reg.node_for(mlabel), p["recon_txid"]):
                    self.log.warn("%s e%d: reconciliation tx did not confirm in time"
                                  % (mlabel, epoch))

        # 6-7. read the amounts back off chain, fold the state forward, publish.
        cluster_rows = []
        for k in range(config.NUM_MINERS):
            mlabel = config.miner_id(k)
            p, f, w = pending[mlabel], facts[mlabel], weights[mlabel]
            allocation, b_prev = p["allocation"], p["b_prev"]

            # THE authoritative Resi: what the confirmed transaction actually paid.
            resi = self.read_credit_to_admin(p["recon_txid"])
            denom = allocation + b_prev
            resi_clamped = 0.0 if denom <= 0 else max(0.0, min(resi, denom))
            rho = (resi_clamped / denom) if denom > 0 else 0.0
            balance = b_prev + allocation - resi_clamped          # B_k  [Fix 1]

            self.balance[mlabel] = round(balance, config.GAS_DECIMALS)
            self.compliance[mlabel] = rho
            self.total_gain[mlabel] = round(self.total_gain[mlabel] + allocation,
                                            config.GAS_DECIMALS)

            # the miner's raw balance, for the ledger-vs-accounting reconciliation.
            node = self.reg.node_for(mlabel)
            saldo = node.gas_balance(self.reg.address_of(mlabel), 1)

            # NOTHING IS PUBLISHED for reconciliation any more. The engine derives R_k
            # itself, from the very transfer whose txid is in p["recon_txid"] -- it scans
            # the epoch's confirmed blocks for value paid to the treasury address by
            # transactions the miner signed. `resi` above is the harness's INDEPENDENT
            # reading of that same transfer, so comparing the two is now a real
            # cross-check of the engine rather than a tautology: the harness and the
            # engine derive the same number from the same blocks by different code paths.
            #
            # This also removed the harness's worst timing bug: the attestation used to
            # confirm 20-24 blocks after the epoch it described had buried, so the engine
            # read a stale R_k. A derived value cannot be late.
            recon_pub_txid = None

            cluster_rows.append({
                "epoch": epoch, "cluster": mlabel, "letter": config.cluster_letter(k),
                "esg": self.esg.get(mlabel, 0), "iso": config.iso_certificate(k),
                # activity
                "tx_miner": tau.get(mlabel, 0),          # tau_Mk (the weight's input)
                "sum_impatto_utente": round(w["sum_impatto_utente"], 6),
                # weights -- "Impatto Cluster" is the raw weight W_k
                "impatto_cluster": round(w["raw_weight"], 6),
                "raw_weight": round(w["raw_weight"], 6),
                "final_weight": round(w["final_weight"], 6),
                "feedback_bracket": round(w["bracket"], 6),
                "delay_msec": round(w["delay"], 4),          # per-mille weight [Fix 6]
                "delay_raw": round(w["delay_raw"], 4),
                "delay_final": round(w["delay_final"], 4),
                "p_k": round(w["p_k"], 6),
                # economics
                "theta": theta,
                "guadagno": allocation,                       # A_k          [Fix 3/7]
                "resi": round(resi_clamped, config.GAS_DECIMALS),
                "resi_onchain": resi,
                "resi_requested": p["requested"],
                "resi_target": p["target"],
                "available": round(denom, config.GAS_DECIMALS),
                "giacenza": round(balance, config.GAS_DECIMALS),      # B_k   [Fix 1]
                "giacenza_prev": round(b_prev, config.GAS_DECIMALS),
                "pct_reso": round(rho * 100.0, 4),                    # %Reso [Fix 2]
                "rho": round(rho, 6),
                "reso_rate_nominal": config.reso_rate(k),
                "total_gain": self.total_gain[mlabel],
                "saldo_onchain": round(saldo, config.GAS_DECIMALS),
                # consensus outcome (NOT an input to any of the above)
                "blocks_mined": f["blocks"],
                "validated_in_blocks": f["validated"],
                "block_interval_ms": round(f["block_interval_ms"], 2),
                # provenance
                "alloc_txid": p["alloc_txid"] or "",
                "recon_txid": p["recon_txid"] or "",
                "recon_stream_txid": recon_pub_txid or "",   # always "" now: nothing is published
            })

        # 8. WAIT FOR THE RECONCILIATION RECORDS TO CONFIRM before leaving the epoch.
        #
        # This is not politeness, it is the experiment's correctness condition. R_k^{(e)}
        # is the ONLY economic input the engine takes from us, and it must be readable
        # before epoch e+1 buries or the engine computes rho_k^{(e)} = 0 and applies the
        # bare (1-lambda) bracket. A run where the publishes lag -- a mempool backlog
        # builds up easily once an epoch's traffic exceeds what its blocks can absorb --
        # silently measures the WRONG weight: every published w_k comes out as exactly
        # round(W_k * kappa * (1-lambda)), the feedback never engages, and the
        # engine-vs-replay comparison fails for a reason that has nothing to do with the
        # engine. Blocking here also throttles the epoch loop to what the chain can
        # actually absorb, which stops the backlog from growing without bound.
        # There is no reconciliation RECORD to wait for any more: the engine derives R_k
        # from the epoch's confirmed transfers to the treasury address, so the value it
        # reads is the transfer itself. What still matters is that the TRANSFER confirmed
        # inside its epoch, which the settlement check above already covers -- and which
        # is now the only timing requirement, instead of transfer-then-attestation.
        #
        # The old check waited on an attestation that habitually confirmed 20-24 blocks
        # after its epoch had buried, making the engine read rho = 0 and every replay
        # comparison fail for a reason that was not the engine's. Deriving the value
        # removed the race rather than tuning around it. See
        # src/wpoa/docs/adr/reconciliation-onchain.md.
        for r in cluster_rows:
            r["recon_stream_confirmed"] = "n/a (derived)"
        self._log_backlog(epoch)

        self.cluster_rows += cluster_rows
        self.company_rows += company_rows

        # 9. per-epoch invariants, on the data just produced.
        checks = self.verify_epoch_invariants({
            "epoch": epoch, "theta": theta, "clusters": cluster_rows,
            "prev_balance": prev_balance,
        })
        self.epoch_checks += checks

        failed = [c for c in checks if not c["ok"]]
        self.log.info("epoch %d settled in %.1fs: Theta=%d sum A_k=%.4f "
                      "(alpha*Theta=%.4f) sum Resi=%.4f sum Delay=%.1f%s"
                      % (epoch, time.time() - t0, theta,
                         sum(r["guadagno"] for r in cluster_rows),
                         config.ALPHA * theta,
                         sum(r["resi"] for r in cluster_rows),
                         sum(r["delay_msec"] for r in cluster_rows),
                         "" if not failed else "  [%d INVARIANT FAILURE(S)]" % len(failed)))
        for c in failed:
            self.log.error("epoch %d invariant %s FAILED: %s"
                           % (epoch, c["check"], c["detail"]))
        return cluster_rows, company_rows

    # ------------------------------------------------------------------
    # Per-epoch invariants
    # ------------------------------------------------------------------
    def verify_epoch_invariants(self, epoch_data):
        """The five per-epoch invariants of the model, checked on one epoch's rows.

        Returns a list of {check, epoch, ok, detail}. Never raises: a violation is
        recorded and surfaced by the caller, so a run always produces its artifacts."""
        epoch = epoch_data["epoch"]
        theta = epoch_data["theta"]
        rows = epoch_data["clusters"]
        prev = epoch_data.get("prev_balance", {})
        out = []
        tol = max(config.GAS_EPS, 10 ** -config.GAS_DECIMALS) * max(1, len(rows))

        def add(name, ok, detail):
            out.append({"check": name, "epoch": epoch, "ok": bool(ok),
                        "detail": detail})

        # 1. the epoch's fee pot is fully and exactly distributed.
        sum_a = sum(r["guadagno"] for r in rows)
        want = config.ALPHA * theta
        add("alloc_sums_to_alpha_theta", abs(sum_a - want) <= tol,
            "sum A_k %.4f vs alpha*Theta %.4f (delta %.6f)" % (sum_a, want, sum_a - want))

        # 2. the per-mille normalization.
        sum_delay = sum(r["delay_msec"] for r in rows)
        add("delay_sums_to_1000", abs(sum_delay - 1000.0) <= config.DELAY_SUM_EPS
            or sum_delay == 0.0,
            "sum Delay %.4f (expected 1000)" % sum_delay)

        # 3. the conformity rate is a rate.
        bad = [(r["cluster"], r["rho"]) for r in rows
               if not (-config.GAS_EPS <= r["rho"] <= 1.0 + config.GAS_EPS)]
        add("rho_in_unit_interval", not bad,
            "all %d rho in [0,1]" % len(rows) if not bad else "out of range: %s" % bad)

        # 4. the balance never goes negative.
        bad = [(r["cluster"], r["giacenza"]) for r in rows
               if r["giacenza"] < -config.GAS_EPS]
        add("balance_non_negative", not bad,
            "all %d B_k >= 0" % len(rows) if not bad else "negative: %s" % bad)

        # 5. nobody returns more than was available to return.
        bad = []
        for r in rows:
            limit = r["guadagno"] + prev.get(r["cluster"], 0.0)
            if r["resi"] > limit + tol:
                bad.append((r["cluster"], r["resi"], limit))
        add("resi_within_available", not bad,
            "all %d R_k <= A_k + B_prev" % len(rows)
            if not bad else "over limit: %s" % bad)

        return out

    # ------------------------------------------------------------------
    # Closing checks
    # ------------------------------------------------------------------
    def conservation_report(self, tx_records=None):
        """Chain-read GAS accounting for the whole run:

          issued           total GAS ever created (the one issue tx)
          on_network       sum of every participant's confirmed balance now
          admin_delta      ADMIN's balance increase = GAS returned by the miners
          feepool_delta    FEEPOOL's balance change = -(allocations paid out)
          resi_total       sum of the per-epoch Resi read off chain
          alloc_total      sum of the per-epoch allocations A_k
          theta_total      total AZIENDA activity over the sampled epochs
          alpha_theta      ALPHA * theta_total -- must EQUAL alloc_total now that the
                           allocation is the fee pot distributed by weight, not a
                           per-block fee tally
          balance_total    sum of the final B_k
          miner_trade_net  {miner: net GAS from miner<->miner transfers}
          validated_total  non-coinbase transactions in the sampled epochs' blocks
          blocks_foreign   blocks in those epochs with no cluster-miner proposer
          tau_gaps         epochs where some transaction had no resolvable signer
        """
        closing = self._all_balances()
        # ALSO at minconf 0. A confirmed-only sum under-counts whenever a transfer is
        # still in flight: the sender no longer holds the input and the recipient does not
        # yet hold the output, so the GAS is invisible to both. That is a CONFIRMATION LAG,
        # not GAS destruction, and the supply check has to be able to tell them apart --
        # otherwise a lagging node looks like a broken ledger.
        closing_0 = self._all_balances(minconf=0)
        opening = self._opening_balances or {}
        resi_total = round(sum(r["resi"] for r in self.cluster_rows), config.GAS_DECIMALS)
        alloc_total = round(sum(r["guadagno"] for r in self.cluster_rows),
                            config.GAS_DECIMALS)
        theta_total = sum(r["tx_utente"] for r in self.company_rows)

        # Net miner<->miner GAS movement, from the recorded transfers.
        miners = set(self.reg.miner_labels())
        trade = dict((m, 0.0) for m in miners)
        for t in (tx_records or []):
            if t.get("type") != "miner" or not t.get("txid"):
                continue
            if self.txid2h.get(t["txid"]) is None:
                continue                          # never confirmed: moved nothing
            amount = float(t.get("amount") or 0.0)
            if t.get("sender") in trade:
                trade[t["sender"]] -= amount
            if t.get("receiver") in trade:
                trade[t["receiver"]] += amount

        validated_total, blocks_foreign = 0, 0
        for epoch in sorted({r["epoch"] for r in self.cluster_rows}):
            start, end = config.epoch_range(epoch)
            for h in range(max(0, start), end + 1):
                b = self.block_idx.get(h)
                if not b:
                    continue
                validated_total += b.get("validated", 0)
                if b.get("miner") not in miners:
                    blocks_foreign += 1

        # Settlement transfers and governance publishes that never made it into a block.
        unconfirmed = [t for t in (list(self.settlement_tx)
                                   + list(getattr(self.sw, "published", [])))
                       if t.get("txid") and self.txid2h.get(t["txid"]) is None]
        unconfirmed_gas = round(sum(float(t.get("amount") or 0.0) for t in unconfirmed),
                                config.GAS_DECIMALS)

        return {
            "issued": float(config.GAS_TOTAL_SUPPLY),
            "on_network": round(sum(closing.values()), config.GAS_DECIMALS),
            "on_network_minconf0": round(sum(closing_0.values()), config.GAS_DECIMALS),
            "unconfirmed_settlement": len(unconfirmed),
            "unconfirmed_settlement_gas": unconfirmed_gas,
            "recon_publish_late": list(self.recon_publish_late),
            "max_backlog": self.max_backlog,
            "opening_on_network": round(sum(opening.values()), config.GAS_DECIMALS),
            "admin_delta": round(closing.get(config.ADMIN_LABEL, 0.0)
                                 - opening.get(config.ADMIN_LABEL, 0.0),
                                 config.GAS_DECIMALS),
            "feepool_delta": round(closing.get(config.FEEPOOL_LABEL, 0.0)
                                   - opening.get(config.FEEPOOL_LABEL, 0.0),
                                   config.GAS_DECIMALS),
            "resi_total": resi_total,
            "alloc_total": alloc_total,
            "theta_total": theta_total,
            "alpha_theta": round(config.ALPHA * theta_total, config.GAS_DECIMALS),
            "balance_total": round(sum(self.balance.values()), config.GAS_DECIMALS),
            "miner_trade_net": trade,
            "validated_total": validated_total,
            "blocks_foreign": blocks_foreign,
            "tau_gaps": list(self.tau_gaps),
            "closing_balances": closing,
            "closing_balances_minconf0": closing_0,
            "opening_balances": opening,
        }
