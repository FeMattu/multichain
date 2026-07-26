# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# economics.py -- the MyLedger economic layer and the AUTOMATED reconciliation
# engine. New in this revision; it did not exist in the original (Apuana SB) suite,
# where the only per-epoch input was a random R_k published straight to the stream
# with no on-chain counterpart.
#
# WHAT IT DOES, once per epoch, at the epoch boundary and without any manual step:
#
#   1. READ the epoch's blocks (listblocks) and resolve, per cluster miner:
#        blocks_mined    -- blocks it proposed in the epoch
#        TxMiner         -- transactions it VALIDATED (sum of txcount-1: the coinbase
#                           is not a network transaction)
#        Delay           -- mean inter-block interval of those blocks, in msec
#   2. READ the epoch's confirmed transactions (getblock) and resolve, per company,
#        Tx utente       -- transfers the company signed in the epoch (= the engine's
#                           tau_i, since tau counts transactions with an input signed
#                           by the address -- weight_reader.cpp)
#        Impatto utente  -- tau_i * ESG_i / kappa  (the engine's c_i)
#      and per cluster, Impatto Cluster = sum of its companies' Impatto utente.
#   3. SETTLE fees on chain: Guadagno_k = TxMiner_k * ALPHA GAS (1 GAS = 1 EUR) is
#      transferred from the FEEPOOL address to the miner. One transfer per cluster
#      stands in for the ALPHA charged to each individual sender (see participants.py).
#   4. RECONCILE on chain: the miner returns Resi_k = Guadagno_k * reso_rate_k to the
#      ADMIN (Apuana SB) address. Programmatic: the miner node signs it itself, so no
#      operator action is involved anywhere in the loop.
#   5. READ THE RECONCILED AMOUNT BACK FROM CHAIN: the transfer's own transaction is
#      re-read (getrawtransaction verbose) and the GAS quantity of the vout paying the
#      ADMIN address is what gets reported and published -- never the amount we asked
#      the node to send. `listaddresstransactions` would give the same answer more
#      directly but needs the optional address-transactions wallet index, so the
#      transaction itself is used instead; the ADMIN balance delta cross-checks the
#      aggregate at the end of the run (conservation_report).
#   6. READ Giacenza_k -- the miner's on-chain GAS balance AFTER the reconciliation
#      has confirmed (minconf 1), which is the balance the spec feeds forward.
#   7. PUBLISH weightsetreconciliation(miner, Resi_from_chain, epoch) so the engine's
#      compliance rate rho_k is driven by the GAS that actually moved.
#
# WHERE ALPHA SITS. ALPHA is the per-transaction cost, so it fixes Guadagno and
# nothing else here; it is NOT a term of the weight. The engine's own allocation is
# A_k = ALPHA * Theta * W_k / W_tot -- the same total (sum_k Guadagno_k = ALPHA*Theta
# = sum_k A_k, because every transaction is validated exactly once) distributed by
# weight share instead of by validation work. Both are reported so the divergence
# between "earned by validating" and "entitled by weight" is measurable.
#
# ORDER OF OPERATIONS AND THE ENGINE'S DEADLINE. R_k^{(e)} is published just after
# epoch e's last block. The engine computes epoch e's weight when the tip reaches
# e_end + STABILITY_MARGIN, and R_k^{(e)} feeds rho_k^{(e)}, which the weight formula
# consumes one epoch later (w_k^{(e+1)} = W_k^{(e+1)} * [rho_k^{(e)}*lambda + 1-lambda]).
# Because ComputeLocalWeightForEpoch re-reads the whole reconciliation stream and
# replays from epoch 1 on every publish, R_k^{(e)} only has to be confirmed before
# epoch e+1 buries -- a full epoch plus margin of slack.

import random
import time

import config
from helpers.chain_setup import looks_txid


class EconomicsEngine(object):
    def __init__(self, network, registry, stream_writer, weight_reader, log, esg):
        self.net = network
        self.reg = registry
        self.sw = stream_writer
        self.wr = weight_reader
        self.log = log
        self.esg = esg or {}                # label -> certified ESG score

        # cumulative chain indexes, extended one epoch at a time. They are kept
        # CONTIGUOUS from height 0: a gap would silently drop a transaction's
        # confirming height (reading as "unconfirmed") and a block's proposer.
        self.txid2h = {}                    # txid -> confirming height
        self.block_idx = {}                 # height -> {miner, time, txcount, validated}
        self._indexed_to = -1               # highest contiguously indexed height

        # rolling accumulators
        self.total_gain = dict((m, 0.0) for m in registry.miner_labels())
        self.cluster_rows = []              # one dict per (epoch, cluster)
        self.company_rows = []              # one dict per (epoch, company)
        self.settlement_tx = []             # fee + reconciliation tx records

        # deterministic jitter on the nominal Reso rate
        self._rng = random.Random(config.SEED ^ 0x5EC0)
        self._opening_balances = {}         # label -> GAS balance before epoch 1

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
    # Per-epoch activity (tau) and impact
    # ------------------------------------------------------------------
    def epoch_activity(self, epoch, tx_records):
        """{label: tau} for `epoch`, counted from CONFIRMED transactions attributed to
        their confirming block's epoch -- the same rule the engine's undo-data metric
        applies. Only activity transfers count: fee settlement and reconciliation are
        settlement flows, and funding predates epoch 1."""
        tau = {}
        for t in tx_records:
            if t.get("type") not in ("company", "miner"):
                continue
            txid = t.get("txid")
            if not txid:
                continue
            h = self.txid2h.get(txid)
            if h is None or config.height_to_epoch(h) != epoch:
                continue
            tau[t["sender"]] = tau.get(t["sender"], 0) + 1
        return tau

    def _cluster_chain_facts(self, epoch):
        """Per cluster: blocks proposed, transactions validated and mean block delay
        (msec) inside `epoch`, read from the block index."""
        start, end = config.epoch_range(epoch)
        facts = dict((m, {"blocks": 0, "tx_miner": 0, "delay_ms": 0.0, "_gaps": []})
                     for m in self.reg.miner_labels())
        for h in range(max(0, start), end + 1):
            b = self.block_idx.get(h)
            if not b:
                continue
            label = b.get("miner")
            if label not in facts:
                continue                      # a block proposed outside the cluster set
            facts[label]["blocks"] += 1
            facts[label]["tx_miner"] += b.get("validated", 0)
            prev = self.block_idx.get(h - 1)
            if prev:
                # Block finalisation latency: the interval between this block and its
                # parent. MultiChain stamps block times in whole seconds, so this is a
                # coarse but genuine on-chain measure, not a modelled constant.
                gap = (b.get("time", 0) - prev.get("time", 0)) * 1000.0
                if gap >= 0:
                    facts[label]["_gaps"].append(gap)
        for m, f in facts.items():
            gaps = f.pop("_gaps")
            f["delay_ms"] = (sum(gaps) / len(gaps)) if gaps else 0.0
        return facts

    # ------------------------------------------------------------------
    # Reconciliation (automated, on chain)
    # ------------------------------------------------------------------
    def _resi_target(self, miner_idx, guadagno):
        """Resi_k = Guadagno_k * nominal rate, with a small seeded jitter so %Reso is
        not a flat line. Clamped to [0, Guadagno] so %Reso can never leave [0,100]."""
        rate = config.reso_rate(miner_idx)
        if config.RESO_JITTER > 0:
            rate *= (1.0 + self._rng.uniform(-config.RESO_JITTER, config.RESO_JITTER))
        rate = max(0.0, min(1.0, rate))
        return round(max(0.0, min(guadagno, guadagno * rate)), config.GAS_DECIMALS)

    def _settle_fees(self, epoch, miner_label, guadagno):
        """Pay the epoch's fee income to the miner from the FEEPOOL. Returns the txid
        or None. Amounts of 0 (a miner that proposed no block) send nothing."""
        if guadagno <= 0:
            return None
        admin = self.net.admin
        ok, res = admin.cli_ok("sendassetfrom", self.reg.feepool_address(),
                               self.reg.address_of(miner_label),
                               config.GAS_ASSET_NAME, guadagno)
        txid = res if (ok and looks_txid(res)) else None
        if not txid:
            self.log.error("fee settlement failed %s e%d (%.4f GAS): %s"
                           % (miner_label, epoch, guadagno, res))
            return None
        self.settlement_tx.append({"epoch": epoch, "txid": txid,
                                   "sender": config.FEEPOOL_LABEL,
                                   "receiver": miner_label, "type": "fee_settlement",
                                   "amount": guadagno})
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
        # fee settlement submitted moments ago, whose change is spendable immediately.
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
        """Harvest, settle and reconcile `epoch`. Called once, immediately after the
        epoch's last block is mined. Returns (cluster_rows, company_rows) for this
        epoch; both are also appended to the engine's cumulative lists."""
        start, end = config.epoch_range(epoch)
        t0 = time.time()

        # 1-2. chain reads. The index is contiguous from 0, so the epoch's first block
        # always has its parent available for the delay measurement.
        self.extend_index(end)
        facts = self._cluster_chain_facts(epoch)
        tau = self.epoch_activity(epoch, tx_records)

        # per-company impact (the engine's c_i) and the cluster totals.
        company_rows = []
        impatto_cluster = {}
        for k in range(config.NUM_MINERS):
            mlabel = config.miner_id(k)
            total_impact = 0.0
            for c in range(config.COMPANIES_PER_MINER):
                clabel = config.company_id(k, c)
                esg_i = self.esg.get(clabel, 0)
                tau_i = tau.get(clabel, 0)
                impatto = (tau_i * esg_i / config.KAPPA) if config.KAPPA else 0.0
                total_impact += impatto
                company_rows.append({
                    "epoch": epoch, "cluster": mlabel, "company": clabel,
                    "display": config.company_display(c), "tx_utente": tau_i,
                    "esg": esg_i, "impatto_utente": round(impatto, 6),
                })
            impatto_cluster[mlabel] = total_impact

        # 3-4. settle fees, then reconcile -- both on chain, both automatic.
        pending = {}
        for k in range(config.NUM_MINERS):
            mlabel = config.miner_id(k)
            tx_miner = facts[mlabel]["tx_miner"]
            guadagno = round(tx_miner * config.ALPHA, config.GAS_DECIMALS)
            fee_txid = self._settle_fees(epoch, mlabel, guadagno)
            target = self._resi_target(k, guadagno)
            recon_txid, requested = self._return_to_admin(epoch, mlabel, target)
            pending[mlabel] = {"guadagno": guadagno, "target": target,
                               "fee_txid": fee_txid, "recon_txid": recon_txid,
                               "requested": requested}

        # 5-6. wait for the reconciliations to confirm, then read the amounts back off
        # chain and the resulting Giacenza. Confirmation must precede the balance read:
        # Giacenza is defined as the balance AFTER reconciliation.
        for mlabel, p in pending.items():
            if p["recon_txid"]:
                if not self.net.wait_confirmed(self.reg.node_for(mlabel), p["recon_txid"]):
                    self.log.warn("%s e%d: reconciliation tx did not confirm in time"
                                  % (mlabel, epoch))

        cluster_rows = []
        for k in range(config.NUM_MINERS):
            mlabel = config.miner_id(k)
            p = pending[mlabel]
            f = facts[mlabel]
            guadagno = p["guadagno"]
            resi = self.read_credit_to_admin(p["recon_txid"])
            node = self.reg.node_for(mlabel)
            giacenza = node.gas_balance(self.reg.address_of(mlabel), 1)
            pct_reso = (resi / guadagno * 100.0) if guadagno > 0 else 0.0
            self.total_gain[mlabel] = round(self.total_gain[mlabel] + guadagno,
                                            config.GAS_DECIMALS)

            # 7. publish the CHAIN-VERIFIED amount, so rho_k reflects GAS that moved.
            recon_pub_txid = self.sw.publish_reconciliation_amount(mlabel, resi, epoch)

            cluster_rows.append({
                "epoch": epoch, "cluster": mlabel, "letter": config.cluster_letter(k),
                "esg": self.esg.get(mlabel, 0), "iso": config.iso_certificate(k),
                "blocks_mined": f["blocks"],
                "tx_miner": f["tx_miner"],
                "tau_miner_signed": tau.get(mlabel, 0),
                "impatto_cluster": round(impatto_cluster[mlabel], 6),
                "delay_ms": round(f["delay_ms"], 2),
                "guadagno": guadagno,
                "resi": resi,
                "resi_requested": p["requested"],
                "resi_target": p["target"],
                "giacenza": round(giacenza, config.GAS_DECIMALS),
                "pct_reso": round(pct_reso, 4),
                "reso_rate_nominal": config.reso_rate(k),
                "total_gain": self.total_gain[mlabel],
                "fee_txid": p["fee_txid"] or "",
                "recon_txid": p["recon_txid"] or "",
                "recon_stream_txid": recon_pub_txid or "",
            })

        theta = sum(r["tx_utente"] for r in company_rows)
        self.cluster_rows += cluster_rows
        self.company_rows += company_rows
        self.log.info("epoch %d settled in %.1fs: Theta=%d TxMiner=%d "
                      "Guadagno=%.2f Resi=%.2f GAS"
                      % (epoch, time.time() - t0, theta,
                         sum(r["tx_miner"] for r in cluster_rows),
                         sum(r["guadagno"] for r in cluster_rows),
                         sum(r["resi"] for r in cluster_rows)))
        return cluster_rows, company_rows

    # ------------------------------------------------------------------
    # Python mirror of weight_engine.h -- CROSS-CHECK AND DISPLAY ONLY
    #
    # The node publishes only the final integer w_k; the intermediate quantities
    # (W_k, A_k, rho_k, B_k) never leave it. To show them in the report -- and to
    # check that the published weight really is the documented function of ESG,
    # activity and the reconciliation feedback -- the pipeline is replayed here from
    # the same public inputs. It is NEVER fed back to the chain: consensus uses the
    # node's own computation, always.
    #
    # FIDELITY CAVEAT. tau_{Mk} here counts the transactions the harness recorded a
    # miner signing (its activity transfers plus its reconciliation transfer). The
    # engine additionally counts the miner's own wpoa-weights publish -- roughly one
    # more per epoch, identically for every miner -- so the replayed W_k is slightly
    # below the engine's and the two are compared by RANKING, not by value. tau_{Mk}
    # is in any case the small term of W_k next to the cluster's Impatto.
    # ------------------------------------------------------------------
    def engine_tau(self, epoch, tx_records):
        """{label: tau} as the ENGINE counts it for `epoch`: every recorded
        transaction a cluster member signed, settlement included. Differs from
        epoch_activity, which is the MyLedger business view and excludes settlement."""
        members = set(self.reg.cluster_labels())
        tau = {}
        for t in tx_records:
            sender = t.get("sender")
            if sender not in members:
                continue                      # ADMIN / FEEPOOL are not cluster members
            txid = t.get("txid")
            if not txid:
                continue
            h = self.txid2h.get(txid)
            if h is None or config.height_to_epoch(h) != epoch:
                continue
            tau[sender] = tau.get(sender, 0) + 1
        return tau

    def replay_epoch(self, epoch, tau_engine, prior_state, epoch_index):
        """One epoch of WeightEngine::ComputeEpoch, in Python.

        `prior_state` is {miner: (balance_prev, compliance_prev)}. `epoch_index` selects
        FinalWeight's branch: <= 1 means "first epoch, no feedback" (w_k = W_k). Callers
        replaying sampled epochs pass the ABSOLUTE epoch number, because the engine
        always replays from epoch 1 and therefore applies the feedback bracket to every
        epoch >= 2 -- with rho_prev = 0 before the first reconciliation, which is exactly
        what an empty `prior_state` gives. Returns ({miner: dict}, new_state)."""
        kappa, alpha, lam = config.KAPPA, config.ALPHA, config.LAMBDA
        raw, theta = {}, 0.0
        for k in range(config.NUM_MINERS):
            mlabel = config.miner_id(k)
            sum_c = 0.0
            for c in range(config.COMPANIES_PER_MINER):
                clabel = config.company_id(k, c)
                tau_i = tau_engine.get(clabel, 0)
                sum_c += self.esg.get(clabel, 0) * tau_i / kappa if kappa else 0.0
                theta += tau_i
            raw[mlabel] = self.esg.get(mlabel, 0) * (tau_engine.get(mlabel, 0) + sum_c)
        total_raw = sum(raw.values())

        out, new_state = {}, {}
        for k in range(config.NUM_MINERS):
            mlabel = config.miner_id(k)
            Wk = raw[mlabel]
            b_prev, rho_prev = prior_state.get(mlabel, (0.0, 0.0))
            Ak = (alpha * theta * Wk / total_raw) if total_raw > 0 else 0.0
            denom = Ak + b_prev
            Rk = 0.0
            for r in self.cluster_rows:        # the chain-verified Resi for this epoch
                if r["epoch"] == epoch and r["cluster"] == mlabel:
                    Rk = r["resi"]
                    break
            r_clamped = 0.0 if denom <= 0 else max(0.0, min(Rk, denom))
            rho = (r_clamped / denom) if denom > 0 else 0.0
            Bk = Ak - r_clamped + b_prev
            wk = Wk if epoch_index <= 1 else Wk * (rho_prev * lam + (1.0 - lam))
            out[mlabel] = {"raw_weight": Wk, "allocation": Ak, "compliance": rho,
                           "balance": Bk, "weight": wk, "theta": theta,
                           "total_raw": total_raw}
            new_state[mlabel] = (Bk, rho)
        return out, new_state

    # ------------------------------------------------------------------
    # Closing checks
    # ------------------------------------------------------------------
    def conservation_report(self):
        """Chain-read GAS accounting for the whole run. Returns a dict the assertion
        pass turns into pass/fail rows:

          issued          total GAS ever created (the one issue tx)
          on_network      sum of every participant's confirmed balance now
          admin_delta     ADMIN's balance increase = GAS returned by the miners
          feepool_delta   FEEPOOL's balance change = -(fees paid out)
          resi_total      sum of the per-epoch Resi read off chain
          guadagno_total  sum of the per-epoch Guadagno
          validated_total sum of the per-epoch TxMiner (transactions the clusters validated)
          blocks_validated total non-coinbase transactions in the sampled epochs' blocks
                          that a CLUSTER MINER proposed -- must equal validated_total
          blocks_foreign  blocks in those epochs with no cluster-miner proposer (expected 0)
          theta_total     total AZIENDA activity over the sampled epochs
          alpha_theta     ALPHA * theta_total

        NOTE ON alpha_theta. Guadagno is charged on every transaction a cluster
        VALIDATES, and the epochs' blocks carry more than azienda traffic: the
        miner<->miner transfers, the fee settlements, the reconciliation transfers, the
        reconciliation stream records and each miner's own wpoa-weights publish all get
        validated too. So sum Guadagno = ALPHA * validated_total, which EXCEEDS
        ALPHA * theta_total by that governance/settlement overhead. alpha_theta is
        reported for comparison against the thesis allocation sum (which is defined on
        Theta), not as an equality the ledger must satisfy.
        """
        closing = self._all_balances()
        opening = self._opening_balances or {}
        resi_total = round(sum(r["resi"] for r in self.cluster_rows), config.GAS_DECIMALS)
        guadagno_total = round(sum(r["guadagno"] for r in self.cluster_rows),
                               config.GAS_DECIMALS)
        validated_total = sum(r["tx_miner"] for r in self.cluster_rows)
        theta_total = sum(r["tx_utente"] for r in self.company_rows)

        # Independent recount straight off the block index: every non-coinbase
        # transaction in the sampled epochs, split by whether a cluster miner proposed
        # the block it landed in.
        miners = set(self.reg.miner_labels())
        blocks_validated, blocks_foreign = 0, 0
        for epoch in sorted({r["epoch"] for r in self.cluster_rows}):
            start, end = config.epoch_range(epoch)
            for h in range(max(0, start), end + 1):
                b = self.block_idx.get(h)
                if not b:
                    continue
                if b.get("miner") in miners:
                    blocks_validated += b.get("validated", 0)
                else:
                    blocks_foreign += 1

        return {
            "issued": float(config.GAS_TOTAL_SUPPLY),
            "on_network": round(sum(closing.values()), config.GAS_DECIMALS),
            "opening_on_network": round(sum(opening.values()), config.GAS_DECIMALS),
            "admin_delta": round(closing.get(config.ADMIN_LABEL, 0.0)
                                 - opening.get(config.ADMIN_LABEL, 0.0),
                                 config.GAS_DECIMALS),
            "feepool_delta": round(closing.get(config.FEEPOOL_LABEL, 0.0)
                                   - opening.get(config.FEEPOOL_LABEL, 0.0),
                                   config.GAS_DECIMALS),
            "resi_total": resi_total,
            "guadagno_total": guadagno_total,
            "validated_total": validated_total,
            "blocks_validated": blocks_validated,
            "blocks_foreign": blocks_foreign,
            "theta_total": theta_total,
            "alpha_theta": round(config.ALPHA * theta_total, config.GAS_DECIMALS),
            "closing_balances": closing,
            "opening_balances": opening,
        }
