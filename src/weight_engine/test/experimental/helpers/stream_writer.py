# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# stream_writer.py -- the admin's write path onto the three WeightEngine input
# streams. It NEVER writes raw items: it drives the sanctioned admin RPCs
# (weightsetesg / weightsetmembership / weightsetreconciliation) exactly as an
# operator would, so every record is schema-validated by the node before it lands
# (weight_publisher.cpp). All calls run on the admin (genesis / global-admin) node.
#
#   esg            : one certified score per address (miners + companies), static.
#   membership     : company -> miner cluster mapping (one call per company).
#   reconciliation : one R_k per miner per epoch (simulated attestations).
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
        self._rng = random.Random(config.SEED ^ 0x5EC0)  # separate stream for R_k

    def ensure_write_permission(self):
        """Grant the admin address write on the three (closed) input streams and
        WAIT for the grants to confirm -- publishfrom rejects an unconfirmed write
        permission, so publishing before confirmation silently fails. The engine
        created the streams; publishing needs an explicit per-stream write grant
        (mirrors functional_test_weight_engine.sh). Idempotent."""
        admin = self.net.admin
        txids = []
        for s in ("weight-engine-esg", "weight-engine-membership",
                  "weight-engine-reconciliation"):
            ok, res = admin.cli_ok("grant", admin.address, "%s.write" % s)
            if ok and _looks_txid(res):
                txids.append(res)
        for txid in txids:
            self.net.wait_confirmed(admin, txid)
        self.log.info("granted admin write on the 3 input streams (confirmed)")

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
            ok, res = self.net.admin.cli_ok("weightsetesg", addr, "%g" % score)
            if ok and _looks_txid(res):
                self.log.debug("ESG %s=%.2f -> %s (%s)" % (label, score, addr, res))
                out[label] = (addr, score, res)
            else:
                self.log.error("ESG publish failed for %s: %s" % (label, res))
                out[label] = (addr, score, None)
        return out

    # -- membership (static, published once) -------------------------------
    def publish_membership(self):
        """Associate every company with its miner cluster. Returns a list of
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
                out.append((config.miner_id(m), clabel, txid))
        self.log.info("published membership: %d company->miner links" % len(out))
        return out

    # -- reconciliation (per epoch) ----------------------------------------
    def publish_reconciliation(self, epoch):
        """Publish a simulated reconciled amount R_k for every miner for `epoch`.
        Amounts are seeded (reproducible); the engine clamps R_k to its legal
        domain, so any non-negative value is a valid attestation. Returns
        {miner_label: (reconciled, txid_or_None)}."""
        out = {}
        for m in range(config.NUM_MINERS):
            miner_addr = self.reg.address_of(config.miner_id(m))
            reconciled = round(self._rng.uniform(0.0, 5.0), 4)
            ok, res = self.net.admin.cli_ok(
                "weightsetreconciliation", miner_addr, "%g" % reconciled, str(epoch))
            txid = res if (ok and _looks_txid(res)) else None
            if not txid:
                self.log.error("reconciliation publish failed %s e%d: %s" %
                               (config.miner_id(m), epoch, res))
            out[config.miner_id(m)] = (reconciled, txid)
        self.log.info("published reconciliation for epoch %d (%d miners)" %
                      (epoch, len(out)))
        return out
