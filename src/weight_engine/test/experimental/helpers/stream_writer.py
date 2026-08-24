# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# stream_writer.py -- the write path onto the three WeightEngine input streams,
# driven the way an operator would drive it rather than by writing raw items.
#
#   esg            : one certified score per address (miners + companies), static.
#                    ADMIN-attested, via weightsetesg.
#   membership     : each node declares its OWN cluster, SELF-ATTESTED. There is no
#                    admin path: a record signed by anyone other than the node it
#                    names is discarded by every reader, so the harness signs each
#                    declaration with the declaring address itself (publishfrom for
#                    the wallet-held aziende, weightregistermembership on each miner
#                    node). See publish_membership.
#   reconciliation : one R_k per miner per epoch. ADMIN-attested, via
#                    weightsetreconciliation.
#
# The two ADMIN-attested streams are schema-validated by the node before the record
# lands (weight_publisher.cpp) and run on the ADMIN (genesis / global-admin) node,
# the Apuana SB stand-in.
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
import time

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

    def _record(self, txid, kind, subject, epoch=0, sender=None):
        """Note a publish in the ledger record (see self.published).

        `sender` is the label that actually SIGNED the transaction, which is what the
        engine counts towards that address's tau. It defaults to the ADMIN for the
        admin-attested streams, but a self-attested membership declaration is signed by
        the declaring node itself and must be recorded as such — attributing it to the
        ADMIN would silently break the harness's tau_coverage invariant."""
        if txid:
            self.published.append({"epoch": epoch, "txid": txid,
                                   "sender": sender or config.ADMIN_LABEL,
                                   "receiver": subject,
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

    def ensure_certification_authority(self):
        """Grant the ADMIN address the Certification Authority role and WAIT for the
        grant to confirm -- weightsetesg refuses an address without it, and an
        unconfirmed grant does not count.

        The role is carried by MultiChain's `high1` custom permission slot: it must be
        a HIGH slot because only those require `admin` (not merely `activate`) to
        grant, which is what keeps CA status conferrable by the administrator alone.
        Idempotent."""
        admin = self.net.admin
        ok, res = admin.cli_ok("grant", admin.address, "high1")
        if ok and _looks_txid(res):
            self._record(res, "grant_certauth", config.ADMIN_LABEL)
            self.net.wait_confirmed(admin, res)
        self.log.info("ADMIN holds the Certification Authority role (high1)")

    # -- ESG (static, published once) --------------------------------------
    def publish_esg(self, scores):
        """Publish every address's certified ESG score. Returns
        {label: (address, score, txid_or_None)} for esg_scores.csv.

        weightsetesg is CERTIFICATION-AUTHORITY-only, and being a global admin is not
        sufficient: the admin confers the role, it does not hold it automatically. The
        harness's ADMIN stands in for Apuana SB, which in the project both administers
        the network and runs the certification process, so it grants ITSELF the role
        once before publishing -- exactly the on-chain step a real deployment performs
        for whichever address signs certifications."""
        self.ensure_certification_authority()
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

    # -- membership (SELF-ATTESTED, published once) -------------------------
    def publish_membership(self):
        """Every azienda declares ITS OWN cluster, and every miner registers itself as
        a cluster head. Returns a list of (miner_label, declaring_label, txid_or_None).

        Membership is no longer an admin attestation: the reader accepts a record only
        if the address that SIGNED the publishing transaction equals the node_address
        the payload declares (weight_reader.cpp ReadMembership). An admin publishing on
        a company's behalf would therefore be discarded, so there is no admin path left
        to drive here.

        Two write paths, both genuinely self-attested — what matters is the SIGNER, not
        which RPC produced the transaction:
          * the aziende are addresses in the ADMIN's own wallet, so the harness signs
            each declaration with `publishfrom <company> ...`, i.e. from the company's
            own address;
          * the cluster miners are separate nodes, so each one calls the public
            `weightregistermembership` with its own address, exactly as an operator
            would.
        """
        out = []

        # Every declaring address needs .write on the (still CLOSED) stream. Under the
        # new model this permission is meant to be network-wide: it lets an address
        # speak about itself and nothing more.
        stream = "weight-engine-membership"
        for label in self.reg.cluster_labels():
            addr = self.reg.address_of(label)
            if addr:
                self.net.admin.cli_ok("grant", addr, "%s.write" % stream)  # best-effort

        for m in range(config.NUM_MINERS):
            mlabel = config.miner_id(m)
            miner_addr = self.reg.address_of(mlabel)
            if not miner_addr:
                out.append((mlabel, mlabel, None))
                continue

            # The miner registers ITSELF as a cluster head, from its own node.
            mnode = self.reg.node_for(mlabel)
            if mnode is not None:
                ok, res = mnode.cli_ok("weightregistermembership", miner_addr)
                txid = res if (ok and _looks_txid(res)) else None
                if not txid:
                    self.log.error("miner self-registration failed %s: %s" % (mlabel, res))
                out.append((mlabel, mlabel,
                            self._record(txid, "publish_membership", mlabel,
                                         sender=mlabel)))

            # Each azienda declares its own membership, signed by its own address.
            for c in range(config.COMPANIES_PER_MINER):
                clabel = config.company_id(m, c)
                caddr = self.reg.address_of(clabel)
                if not caddr:
                    out.append((mlabel, clabel, None))
                    continue
                record = ('{"json":{"node_address":"%s","miner_address":"%s",'
                          '"timestamp":%d}}' % (caddr, miner_addr, int(time.time())))
                ok, res = self.net.admin.cli_ok("publishfrom", caddr, stream, caddr, record)
                txid = res if (ok and _looks_txid(res)) else None
                if not txid:
                    self.log.error("membership self-declaration failed %s->%s: %s" %
                                   (clabel, mlabel, res))
                out.append((mlabel, clabel,
                            self._record(txid, "publish_membership", clabel,
                                         sender=clabel)))

        self.log.info("published membership: %d self-attested declarations" % len(out))
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
