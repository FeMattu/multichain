# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# stream_writer.py -- the write path onto the TWO published WeightEngine input streams,
# driven the way an operator would drive it rather than by writing raw items.
#
#   esg        : one certified score per address (miners + companies), static. Written
#                by a CERTIFICATION AUTHORITY via weightsetesg -- being a global admin
#                is not sufficient, so the harness grants the ADMIN the role first
#                (ensure_certification_authority).
#   membership : each node declares its OWN cluster, SELF-ATTESTED. There is no admin
#                path: a record signed by anyone other than the node it names is
#                discarded by every reader, so the harness signs each declaration with
#                the declaring address itself (publishfrom for the wallet-held aziende,
#                weightregistermembership on each miner node). See publish_membership.
#
# NO RECONCILIATION WRITER. tau and R_k are both DERIVED by the engine from the epoch's
# confirmed blocks, so neither has a stream or a publisher. The harness's job for R is
# only to MAKE the transfers -- economics.py already sends real GAS from each miner to
# the ADMIN -- and to point the engine at the recipient by setting
# -weighttreasuryaddress to the ADMIN address at chain creation.
#
# THE HISTORY IS WORTH KEEPING. R_k was originally a seeded random draw over [0, 5] with
# NO on-chain counterpart: the stream asserted a reconciliation that never happened. It
# was then made honest -- the real GAS returned, read back off chain and re-published as
# an attestation -- which exposed the next problem: the record confirmed 20-24 blocks
# AFTER the epoch it described had buried, so the engine read a stale R_k. Deriving the
# value removes both failures at once: a derived value cannot be fictional and cannot be
# late, because it is not published at all -- it is read off the very blocks that
# recorded the transfers. See src/wpoa/docs/adr/reconciliation-onchain.md.
#
# Every call returns the publish txid (or None + a logged error), so failures are
# recorded and the run continues, per the experiment's error-handling rule.

import time

import config
from helpers.chain_setup import looks_txid as _looks_txid


class StreamWriter(object):
    def __init__(self, network, registry, log):
        self.net = network
        self.reg = registry          # ParticipantRegistry (labels <-> addresses)
        self.log = log
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
        """Grant the ADMIN address write on the two (closed) published input streams and
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

    # -- reconciliation: NO publisher any more ----------------------------
    #
    # R_k is DERIVED by the engine from the epoch's confirmed transfers to the treasury
    # address, so there is nothing to publish and no publish_reconciliation* method here.
    # The harness's job is now only to MAKE the transfers (economics.py already does, as
    # real GAS sends from each miner to the ADMIN) and to point the engine at the right
    # recipient by setting -weighttreasuryaddress to the ADMIN address at chain creation.
    #
    # This removed the harness's own worst failure mode: the reconciliation record used
    # to confirm 20-24 blocks AFTER the epoch it described had already buried, so the
    # engine read a stale R_k. A derived value cannot be late, because it is not
    # published -- it is read off the very blocks that recorded the transfers.
    # See src/wpoa/docs/adr/reconciliation-onchain.md.
