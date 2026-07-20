# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# tx_simulator.py -- generates the on-chain ACTIVITY that drives the WeightEngine's
# tau_i counters. There is no native currency on a default MultiChain (initial-
# block-reward = 0), so "value" is a purpose-issued asset: the admin issues it once,
# funds every participant, and thereafter each participant SENDS the asset. Every
# `sendassetfrom <addr> ...` spends a UTXO owned by <addr>, so the engine's
# undo-data activity metric counts one tau for <addr> in the confirming block's
# epoch (weight_reader.cpp ComputeActivityForEpoch) -- which is exactly the
# thesis-defined tau: transactions with an input signed by the address.
#
# A transfer is signed by the node that owns the sender's key: companies live in
# the admin wallet (admin signs), miners sign on their own node.
#
# Determinism: transaction picks come from a per-epoch RNG seeded from config.SEED,
# so a given seed reproduces the same trade pattern regardless of timing.

import random

import config
from helpers.chain_setup import looks_txid


class TxSimulator(object):
    def __init__(self, network, registry, log):
        self.net = network
        self.reg = registry
        self.log = log

    # -- one-time asset issue + funding ------------------------------------
    def setup(self):
        """Issue the simulation asset to the admin and fund every participant with
        FUND_PER_ADDR units. Waits for issue + funding to confirm so senders have a
        spendable balance before epoch 1. Returns the list of funding tx records."""
        admin = self.net.admin
        ok, res = admin.cli_ok("issue", admin.address, config.ASSET_NAME,
                               config.ASSET_TOTAL, 1)
        if not (ok and looks_txid(res)):
            raise RuntimeError("asset issue failed: %s" % (res,))
        self.net.wait_confirmed(admin, res)
        self.log.info("issued asset '%s' (%d units) to admin" %
                      (config.ASSET_NAME, config.ASSET_TOTAL))

        funding = []
        last_txid = None
        for label in self.reg.all_labels():
            addr = self.reg.address_of(label)
            ok, res = admin.cli_ok("sendassetfrom", admin.address, addr,
                                   config.ASSET_NAME, config.FUND_PER_ADDR)
            txid = res if (ok and looks_txid(res)) else None
            if txid:
                last_txid = txid
            else:
                self.log.error("funding %s failed: %s" % (label, res))
            funding.append({"epoch": 0, "txid": txid, "sender": "admin",
                            "receiver": label, "type": "funding",
                            "amount": config.FUND_PER_ADDR})
        if last_txid:
            self.net.wait_confirmed(admin, last_txid)
        self.log.info("funded %d participants with %d units each" %
                      (len(self.reg.all_labels()), config.FUND_PER_ADDR))
        return funding

    # -- per-epoch transactions --------------------------------------------
    def generate_epoch_txs(self, epoch):
        """Submit this epoch's simulated transfers and return their records. The
        `epoch` field is the INTENDED epoch; the confirming block's actual epoch is
        resolved later by the reporter (a tx near an epoch boundary may confirm in
        e or e+1). Categories per the spec: company<->company, miner<->miner, and
        a couple of symbolic asset transfers between random participants."""
        rng = random.Random(config.SEED ^ (0xA1CE * epoch + 7))
        companies = self.reg.company_labels()
        miners = self.reg.miner_labels()
        everyone = companies + miners
        records = []

        def emit(sender, receiver, ttype):
            amount = rng.randint(config.TX_AMOUNT_MIN, config.TX_AMOUNT_MAX)
            records.append(self._send(sender, receiver, amount, ttype, epoch))

        for _ in range(rng.randint(config.TX_COMPANY_MIN, config.TX_COMPANY_MAX)):
            s, r = _pick_pair(rng, companies)
            emit(s, r, "company")
        for _ in range(rng.randint(config.TX_MINER_MIN, config.TX_MINER_MAX)):
            s, r = _pick_pair(rng, miners)
            emit(s, r, "miner")
        for _ in range(rng.randint(config.TX_ASSET_MIN, config.TX_ASSET_MAX)):
            s, r = _pick_pair(rng, everyone)
            emit(s, r, "asset")

        ok = sum(1 for x in records if x["txid"])
        self.log.info("epoch %d: submitted %d/%d transactions" %
                      (epoch, ok, len(records)))
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
                              config.ASSET_NAME, amount)
        if ok and looks_txid(res):
            rec["txid"] = res
        else:
            # Insufficient asset balance / transient lock: logged, run continues.
            self.log.warn("tx %s->%s (%s) failed: %s" %
                          (sender_label, receiver_label, ttype, res))
        return rec


def _pick_pair(rng, pool):
    """Pick an ordered (sender, receiver) pair of distinct members of pool."""
    if len(pool) < 2:
        return pool[0], pool[0]
    s = rng.choice(pool)
    r = rng.choice(pool)
    while r == s:
        r = rng.choice(pool)
    return s, r
