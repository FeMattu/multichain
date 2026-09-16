# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# membership_reader.py -- reads the node -> cluster-miner association FROM THE CHAIN,
# applying the same fold the C++ engine applies.
#
# WHY THIS EXISTS. The association is not harness knowledge: it is public on-chain
# state, SELF-DECLARED by each node on "weight-engine-membership" (one item per
# declaration, item key = the DECLARING node's address, payload
# {"json": {"node_address": .., "miner_address": .., "timestamp": ..}}).
#
# THE FOLD. Because a node may change cluster at any time, the engine takes each
# declaring address's LATEST confirmed record and inverts the relation into C_k
# (WeightStreamReader::ReadMembership -> mc_AccumulateLatestMembership +
# mc_BuildClustersFromMembership). This reader reproduces that: it lists the stream in
# chain order and keeps the last declaration per key.
#
# WHY NOT getstreamkeysummary jsonobjectmerge ANY MORE. That was the right read while
# membership was keyed by miner and accumulated additively, and it is exactly why the
# scheme had to change: an additive merge cannot express a node LEAVING a cluster, so a
# node that moved from miner A to miner B stayed in both for ever. There is no
# summary-mode equivalent of last-confirmed-wins, so the fold is done here explicitly.
#
# SELF-ATTESTATION. The engine additionally DISCARDS any record whose transaction
# signer differs from its declared node_address. The harness applies the same test,
# using the item's "publishers" field, so a forged record is invisible to the harness
# exactly as it is to the engine.
#
# CACHING. Membership is static for a run (published once, before epoch 1), so the
# merged map is fetched ONCE and served from a local dict thereafter -- the same
# read-through cache shape as the block/txid indexes in economics.py. One call per
# cluster, five calls per run, instead of one per company per epoch.
#
# CONSISTENCY CHECKS. Because the map now comes from chain it can actually be wrong,
# so the reader validates what it gets: a company claimed by two clusters, a company
# with no cluster, or a cluster whose size differs from the configured topology are
# all reported. These are exactly the failure modes that would silently corrupt
# sum_{i in C_k} c_i and therefore every W_k.

import config


class MembershipReader(object):
    def __init__(self, network, registry, log):
        self.net = network
        self.reg = registry
        self.log = log
        self._company_of = {}      # miner_label -> [company_label, ...]  (from chain)
        self._miner_of = {}        # company_label -> miner_label        (from chain)
        self._discarded = 0        # records dropped for failing self-attestation
        self._loaded = False
        self._issues = []          # human-readable consistency findings

    # ------------------------------------------------------------------
    # Chain read (once) + cache
    # ------------------------------------------------------------------
    def load(self, force=False):
        """Fetch and cache the cluster sets from the membership stream. Idempotent:
        the second and later calls are free. Returns self."""
        if self._loaded and not force:
            return self
        self._company_of, self._miner_of, self._issues = {}, {}, []
        self._discarded = 0

        # node_address -> miner_address, latest confirmed declaration winning.
        node_to_miner = self._read_declarations()

        # Invert into C_k, applying the engine's two inversion rules: a miner's
        # self-declaration registers the cluster head, and a miner is never listed
        # among its own companies (its activity enters W_k through tau_Mk instead).
        for k in range(config.NUM_MINERS):
            self._company_of[config.miner_id(k)] = []

        for naddr in sorted(node_to_miner):
            maddr = node_to_miner[naddr]
            mlabel = self.reg.label_of(maddr)
            nlabel = self.reg.label_of(naddr)
            if mlabel not in self._company_of:
                self._issues.append("%s declares unknown cluster %s" % (nlabel, mlabel))
                continue
            if naddr == maddr:
                continue                     # cluster head registering itself
            if nlabel in self._miner_of:
                # A node in two clusters cannot happen under last-confirmed-wins, so if
                # it shows up the fold itself is wrong -- worth reporting loudly.
                self._issues.append("%s claimed by both %s and %s"
                                    % (nlabel, self._miner_of[nlabel], mlabel))
            self._miner_of[nlabel] = mlabel
            self._company_of[mlabel].append(nlabel)

        for k in range(config.NUM_MINERS):
            mlabel = config.miner_id(k)
            n = len(self._company_of[mlabel])
            if n != config.COMPANIES_PER_MINER:
                self._issues.append("%s has %d companies on chain (configured %d)"
                                    % (mlabel, n, config.COMPANIES_PER_MINER))

        missing = [c for c in self.reg.company_labels() if c not in self._miner_of]
        if missing:
            self._issues.append("%d company(ies) with no cluster on chain: %s"
                                % (len(missing), missing[:5]))

        self._loaded = True
        total = sum(len(v) for v in self._company_of.values())
        if self._issues:
            for msg in self._issues:
                self.log.warn("membership: %s" % msg)
        self.log.info("membership read from chain: %d clusters, %d companies, "
                      "%d record(s) discarded for failing self-attestation"
                      % (len(self._company_of), total, self._discarded))
        return self

    def _read_declarations(self):
        """{node_address: miner_address} from the membership stream, chain order, latest
        confirmed declaration winning -- the engine's own fold. Records whose signer is
        not the declared node_address are DISCARDED, as the engine discards them."""
        ok, items = self.net.admin.cli_ok(
            "liststreamitems", config.MEMBERSHIP_STREAM, "false", "100000")
        if not ok or not isinstance(items, list):
            self.log.warn("liststreamitems(%s) failed: %r"
                          % (config.MEMBERSHIP_STREAM, items))
            return {}

        latest = {}
        for it in items:
            if not isinstance(it, dict) or not it.get("confirmations", 0):
                continue                     # confirmed items only, as the engine reads
            rec = _unwrap_json(it.get("data"))
            if not isinstance(rec, dict):
                continue
            node = rec.get("node_address")
            miner = rec.get("miner_address")
            if not node or not miner:
                continue
            # Self-attestation: the tx signer must BE the declared node.
            if node not in (it.get("publishers") or []):
                self._discarded += 1
                continue
            latest[str(node)] = str(miner)   # chain order -> last one wins
        return latest

    # ------------------------------------------------------------------
    # Lookups (cache-only; call load() first)
    # ------------------------------------------------------------------
    def companies_of(self, miner_label):
        """The cluster's company labels as recorded ON CHAIN, in address order."""
        return list(self._company_of.get(miner_label, []))

    def miner_of(self, company_label):
        """The cluster miner a company belongs to on chain, or None."""
        return self._miner_of.get(company_label)

    def clusters(self):
        """{miner_label: [company_label, ...]} for every configured cluster."""
        return dict((m, list(c)) for m, c in self._company_of.items())

    def issues(self):
        """Consistency findings from the last load() ([] when the map is clean)."""
        return list(self._issues)

    def agrees_with_registry(self):
        """True when the on-chain map is exactly the configured topology. Reported as
        its own invariant, since every W_k depends on it."""
        if self._issues:
            return False
        for k in range(config.NUM_MINERS):
            mlabel = config.miner_id(k)
            if sorted(self._company_of.get(mlabel, [])) != sorted(self.reg.companies_of(k)):
                return False
        return True


def _unwrap_json(value):
    """An item's payload may arrive as the record object directly or still wrapped in
    {"json": ...} depending on how it was published -- the same ambiguity
    mc_WeightUnwrapItemJson absorbs on the C++ side. Accept both."""
    if isinstance(value, dict) and "json" in value and isinstance(value["json"], dict):
        return value["json"]
    return value
