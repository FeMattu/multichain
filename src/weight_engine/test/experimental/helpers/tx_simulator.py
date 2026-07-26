# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# tx_simulator.py -- generates the on-chain ACTIVITY that drives the WeightEngine's
# tau_i counters and, through it, the MyLedger economics.
#
# GAS. There is no spendable native currency on a default MultiChain
# (initial-block-reward = 0), so GAS -- the network currency, 1 GAS = 1 EUR -- is a
# purpose-issued DIVISIBLE asset: the admin issues it once, funds every participant,
# and thereafter each participant SENDS GAS. Every `sendassetfrom <addr> ...` spends
# a UTXO owned by <addr>, so the engine's undo-data activity metric counts one tau
# for <addr> in the confirming block's epoch (weight_reader.cpp
# ComputeActivityForEpoch) -- which is exactly the thesis-defined tau: transactions
# with an input signed by the address. The asset is issued with
# config.GAS_ASSET_UNITS divisibility so amounts like ALPHA = 0.2 GAS are exact.
#
# A transfer is signed by the node that owns the sender's key: companies live in
# the admin wallet (admin signs), miners sign on their own node.
#
# CHANGED FROM THE ORIGINAL (Apuana SB) SETUP. Volume is now driven PER COMPANY --
# every azienda sends TX_PER_COMPANY_MIN..MAX transfers each epoch, matching the
# MyLedger configuration sheet's "Numero minimo/massimo Tx" (10..20) -- instead of a
# handful of transfers picked network-wide. With 50 aziende that makes Theta ~ 750
# per epoch, which is what makes the per-cluster impact figures meaningful. The
# separate "symbolic asset transfer" category is gone: every transfer now moves GAS,
# so there is only one kind of value on the network.
#
# Determinism: transaction picks come from a per-epoch RNG seeded from config.SEED,
# so a given seed reproduces the same trade pattern regardless of timing.

import random
import time

import config
from helpers.chain_setup import looks_txid


class TxSimulator(object):
    def __init__(self, network, registry, log):
        self.net = network
        self.reg = registry
        self.log = log

    # -- one-time GAS issue + funding --------------------------------------
    def setup(self):
        """Issue GAS to the admin and fund every participant. The FEEPOOL gets a
        larger float because it settles every epoch's fee income for all clusters
        (config.feepool_fund()). Waits for issue + funding to confirm so senders have
        a spendable balance before the first sampled epoch. Returns the funding tx
        records."""
        admin = self.net.admin
        # issue <address> <asset-name> <qty> <units>: units is the divisibility, so
        # 0.0001 lets the fee/reconciliation amounts be exact multiples of 0.2 GAS.
        ok, res = admin.cli_ok("issue", admin.address, config.GAS_ASSET_NAME,
                               config.GAS_TOTAL_SUPPLY, config.GAS_ASSET_UNITS)
        if not (ok and looks_txid(res)):
            raise RuntimeError("GAS issue failed: %s" % (res,))
        self.net.wait_confirmed(admin, res)
        self.log.info("issued '%s' (%d units, divisibility %g) to ADMIN -- 1 GAS = 1 EUR"
                      % (config.GAS_ASSET_NAME, config.GAS_TOTAL_SUPPLY,
                         config.GAS_ASSET_UNITS))

        feepool_fund = config.feepool_fund()
        funding = []
        last_txid = None
        for label in self.reg.all_labels():
            if label == config.ADMIN_LABEL:
                continue                      # the issuer already holds the supply
            amount = feepool_fund if label == config.FEEPOOL_LABEL else config.FUND_PER_ADDR
            addr = self.reg.address_of(label)
            ok, res = admin.cli_ok("sendassetfrom", admin.address, addr,
                                   config.GAS_ASSET_NAME, _q(amount))
            txid = res if (ok and looks_txid(res)) else None
            if txid:
                last_txid = txid
            else:
                self.log.error("funding %s failed: %s" % (label, res))
            funding.append({"epoch": 0, "txid": txid, "sender": config.ADMIN_LABEL,
                            "receiver": label, "type": "funding", "amount": amount})
        if last_txid:
            self.net.wait_confirmed(admin, last_txid)
        self.log.info("funded %d participants (%g GAS each) + FEEPOOL (%g GAS)"
                      % (len(funding) - 1, config.FUND_PER_ADDR, feepool_fund))
        return funding

    # -- per-epoch transactions --------------------------------------------
    def generate_epoch_txs(self, epoch):
        """Submit this epoch's simulated transfers and return their records.

        Categories:
          * company : every azienda sends TX_PER_COMPANY_MIN..MAX GAS transfers to
                      other aziende -- the network traffic MyLedger charges ALPHA for.
          * miner   : a few miner<->miner transfers, so tau_{Mk} (the miner's own
                      activity term of W_k) is not degenerate.

        The `epoch` field is the INTENDED epoch; the confirming block's actual epoch
        is resolved later by the reporter (a tx near an epoch boundary may confirm in
        e or e+1).

        Submissions are SPREAD over config.tx_waves() waves, one block apart. Bursting
        them all at once (which takes a fraction of a second over JSON-RPC) would land
        the entire epoch in the single next block, making TxMiner -- and therefore
        Guadagno, Resi and Giacenza -- a lottery on who mined that one block rather than
        a measure of validation work. See config.TX_WAVES."""
        rng = random.Random(config.SEED ^ (0xA1CE * epoch + 7))
        companies = self.reg.company_labels()
        miners = self.reg.miner_labels()
        t0 = time.time()

        # Build the whole epoch's plan first, in a fixed label order, so the traffic a
        # seed produces is identical however it ends up being paced.
        plan = []
        for sender in companies:
            n = rng.randint(config.TX_PER_COMPANY_MIN, config.TX_PER_COMPANY_MAX)
            for _ in range(n):
                receiver = _pick_other(rng, companies, sender)
                amount = _q(rng.uniform(config.TX_AMOUNT_MIN, config.TX_AMOUNT_MAX))
                plan.append((sender, receiver, amount, "company"))
        for _ in range(rng.randint(config.TX_MINER_MIN, config.TX_MINER_MAX)):
            s, r = _pick_pair(rng, miners)
            amount = _q(rng.uniform(config.TX_AMOUNT_MIN, config.TX_AMOUNT_MAX))
            plan.append((s, r, amount, "miner"))

        _, end = config.epoch_range(epoch)
        waves = max(1, min(config.tx_waves(), len(plan)))
        records, paced = [], 0
        for w in range(waves):
            # interleaved slices, so every wave carries a mix of senders and clusters
            for (s, r, amount, ttype) in plan[w::waves]:
                records.append(self._send(s, r, amount, ttype, epoch))
            if w < waves - 1:
                # Never wait past the epoch's last block: if the chain has fallen
                # behind, submit the remainder back-to-back rather than stall.
                if self.net.wait_next_block(not_past=end):
                    paced += 1

        ok = sum(1 for x in records if x["txid"])
        self.log.info("epoch %d: submitted %d/%d transactions in %.1fs "
                      "(%d waves, %d block-paced)"
                      % (epoch, ok, len(records), time.time() - t0, waves, paced))
        return records

    def _send(self, sender_label, receiver_label, amount, ttype, epoch):
        node = self.reg.node_for(sender_label)
        saddr = self.reg.address_of(sender_label)
        raddr = self.reg.address_of(receiver_label)
        rec = {"epoch": epoch, "txid": None, "sender": sender_label,
               "receiver": receiver_label, "type": ttype, "amount": amount}
        if node is None or not saddr or not raddr:
            self.log.error("cannot send %s->%s (missing node/address)" %
                           (sender_label, receiver_label))
            return rec
        ok, res = node.cli_ok("sendassetfrom", saddr, raddr,
                              config.GAS_ASSET_NAME, amount)
        if ok and looks_txid(res):
            rec["txid"] = res
        else:
            # Insufficient GAS balance / transient lock: logged, run continues.
            self.log.warn("tx %s->%s (%s) failed: %s" %
                          (sender_label, receiver_label, ttype, res))
        return rec


def _q(amount):
    """Quantize a GAS amount to the asset's display precision, so what we ask the
    node to send is exactly what the balance/conservation checks later compare."""
    return round(float(amount), config.GAS_DECIMALS)


def _pick_other(rng, pool, exclude):
    """Pick a member of pool that is not `exclude` (pool of 1 -> itself)."""
    if len(pool) < 2:
        return pool[0]
    r = rng.choice(pool)
    while r == exclude:
        r = rng.choice(pool)
    return r


def _pick_pair(rng, pool):
    """Pick an ordered (sender, receiver) pair of distinct members of pool."""
    if len(pool) < 2:
        return pool[0], pool[0]
    s = rng.choice(pool)
    return s, _pick_other(rng, pool, s)
