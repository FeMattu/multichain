# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# stream_writer.py -- the ADMIN's write path onto the three WeightEngine input
# streams. It NEVER writes raw items: it drives the sanctioned admin RPCs
# (weightsetesg / weightsetmembership / weightsetreconciliation) exactly as an
# operator would, so every record is schema-validated by the node before it lands
# (weight_publisher.cpp). All calls run on the ADMIN (genesis / global-admin) node,
# the Apuana SB stand-in.
#
#   esg            : one certified score per address (miners + companies), static.
#   membership     : company -> miner cluster mapping (one call per company).
#   reconciliation : one R_k per miner per epoch.
#
# CHANGED FROM THE ORIGINAL (Apuana SB) SETUP. R_k used to be a random draw over
# [0, 5] with no on-chain counterpart -- the stream asserted a reconciliation that
# never happened. It is now the GAS that a miner ACTUALLY returned to the ADMIN
# address in the epoch, read back off chain by economics.py and handed to
# publish_reconciliation_amount. publish_reconciliation (the seeded-random form) is
# kept only so the pre-MyLedger flow still runs; the MyLedger path never calls it.
#
# Every call returns the publish txid (or None + a logged error), so failures are
# recorded and the run continues, per the experiment's error-handling rule.

import random

import config
from helpers.chain_setup import looks_txid as _looks_txid


class StreamWriter(object):
    def __init__(self, network, registry, log):
        self.net = network
        self.reg = registry          # ParticipantRegistry (labels <-> addresses)
        self.log = log
        self._rng = random.Random(config.SEED ^ 0x5EC0)  # legacy path only
        # Every publish is a TRANSACTION SIGNED BY THE ADMIN, so it is part of the
        # ledger and of the epoch's transaction count. Recording them here lets the
        # harness account for 100% of the transactions in an epoch's blocks -- the
        # tau_coverage invariant -- instead of writing the difference off as noise.
        self.published = []          # tx records, same shape as tx_simulator's

    def _record(self, txid, kind, subject, epoch=0):
        """Note an ADMIN-signed publish in the ledger record (see self.published)."""
        if txid:
            self.published.append({"epoch": epoch, "txid": txid,
                                   "sender": config.ADMIN_LABEL, "receiver": subject,
                                   "type": kind, "amount": 0.0})
        return txid

    def ensure_write_permission(self):
        """Grant the ADMIN address write on the three (closed) input streams and
        WAIT for the grants to confirm -- publishfrom rejects an unconfirmed write
        permission, so publishing before confirmation silently fails. The engine
        created the streams; publishing needs an explicit per-stream write grant
        (mirrors functional_test_weight_engine.sh). Idempotent."""
        admin = self.net.admin
        txids = []
        for s in config.INPUT_STREAMS:
            ok, res = admin.cli_ok("grant", admin.address, "%s.write" % s)
            if ok and _looks_txid(res):
                txids.append(res)
                self._record(res, "grant_write", s)
        for txid in txids:
            self.net.wait_confirmed(admin, txid)
        self.log.info("granted ADMIN write on the %d input streams (confirmed)"
                      % len(config.INPUT_STREAMS))

    # -- ESG (static, published once) --------------------------------------
    def publish_esg(self, scores):
        """Publish every address's certified ESG score. Returns
        {label: (address, score, txid_or_None)} for esg_scores.csv."""
        out = {}
        for label, score in sorted(scores.items()):
            addr = self.reg.address_of(label)
            if not addr:
                self.log.warn("no address for %s; skipping ESG publish" % label)
                out[label] = (None, score, None)
                continue
            ok, res = self.net.admin.cli_ok("weightsetesg", addr, float(score))
            if ok and _looks_txid(res):
                self.log.debug("ESG %s=%s -> %s (%s)" % (label, score, addr, res))
                out[label] = (addr, score, self._record(res, "publish_esg", label))
            else:
                self.log.error("ESG publish failed for %s: %s" % (label, res))
                out[label] = (addr, score, None)
        return out

    # -- membership (static, published once) -------------------------------
    def publish_membership(self):
        """Associate every azienda with its cluster miner. Returns a list of
        (miner_label, company_label, txid_or_None)."""
        out = []
        for m in range(config.NUM_MINERS):
            miner_addr = self.reg.address_of(config.miner_id(m))
            for c in range(config.COMPANIES_PER_MINER):
                clabel = config.company_id(m, c)
                caddr = self.reg.address_of(clabel)
                if not (miner_addr and caddr):
                    out.append((config.miner_id(m), clabel, None))
                    continue
                ok, res = self.net.admin.cli_ok("weightsetmembership", miner_addr, caddr)
                txid = res if (ok and _looks_txid(res)) else None
                if not txid:
                    self.log.error("membership publish failed %s<-%s: %s" %
                                   (config.miner_id(m), clabel, res))
                out.append((config.miner_id(m), clabel,
                            self._record(txid, "publish_membership", clabel)))
        self.log.info("published membership: %d azienda->cluster links" % len(out))
        return out

    # -- reconciliation (per epoch) ----------------------------------------
    def publish_reconciliation_amount(self, miner_label, reconciled, epoch):
        """Attest ONE miner's reconciled amount for `epoch`. `reconciled` is the GAS
        that economics.py read off chain as credited to the ADMIN address, so the
        stream and the ledger agree by construction. The engine clamps R_k to
        [0, A_k + B_k^{(e-1)}] anyway, so any non-negative value is legal.
        Returns the publish txid or None."""
        addr = self.reg.address_of(miner_label)
        if not addr:
            self.log.error("no address for %s; cannot publish reconciliation" % miner_label)
            return None
        ok, res = self.net.admin.cli_ok("weightsetreconciliation", addr,
                                        float(reconciled), int(epoch))
        txid = res if (ok and _looks_txid(res)) else None
        if not txid:
            self.log.error("reconciliation publish failed %s e%d (%.4f): %s"
                           % (miner_label, epoch, reconciled, res))
        return self._record(txid, "publish_reconciliation", miner_label, epoch)

    def publish_reconciliation(self, epoch):
        """LEGACY (pre-MyLedger): publish a seeded-random R_k for every miner, with no
        on-chain transfer behind it. Superseded by the automated on-chain path in
        economics.py; retained so the original flow remains runnable. Returns
        {miner_label: (reconciled, txid_or_None)}."""
        out = {}
        for m in range(config.NUM_MINERS):
            mlabel = config.miner_id(m)
            reconciled = round(self._rng.uniform(0.0, 5.0), 4)
            txid = self.publish_reconciliation_amount(mlabel, reconciled, epoch)
            out[mlabel] = (reconciled, txid)
        self.log.info("published reconciliation for epoch %d (%d miners)" %
                      (epoch, len(out)))
        return out
