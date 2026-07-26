# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# membership_reader.py -- reads the company -> cluster-miner association FROM THE
# CHAIN, through the same native protocol facility the C++ engine uses.
#
# WHY THIS EXISTS. The association is not harness knowledge: it is public on-chain
# state, published by the ADMIN to "weight-engine-membership" (one item per company,
# item key = miner address, payload {"json": {"<company_addr>": <timestamp>}}). The
# engine rebuilds each cluster set C_k by MERGING every item under a miner key --
# WeightStreamReader::ReadMembership -> mc_ParseMembershipClusterJson, which is
# MultiChain's own mc_MergeValues. The RPC surface of that exact merge is
#
#     getstreamkeysummary "weight-engine-membership" <miner_address> "jsonobjectmerge"
#
# so this reader asks the node to do the merge rather than re-implementing it in
# Python. What the harness reads is therefore byte-for-byte what the engine reads, and
# a divergence between the two becomes impossible by construction instead of being
# something we hope holds.
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

        for k in range(config.NUM_MINERS):
            mlabel = config.miner_id(k)
            maddr = self.reg.address_of(mlabel)
            if not maddr:
                self._issues.append("%s has no address" % mlabel)
                self._company_of[mlabel] = []
                continue
            members = self._read_cluster(maddr)
            labels = []
            for caddr in sorted(members):
                clabel = self.reg.label_of(caddr)
                labels.append(clabel)
                if clabel in self._miner_of:
                    # A company in two clusters would be double-counted in W: the
                    # engine's std::set-per-miner cannot detect this either, so the
                    # harness has to.
                    self._issues.append("%s claimed by both %s and %s"
                                        % (clabel, self._miner_of[clabel], mlabel))
                self._miner_of[clabel] = mlabel
            self._company_of[mlabel] = labels
            if len(labels) != config.COMPANIES_PER_MINER:
                self._issues.append("%s has %d companies on chain (configured %d)"
                                    % (mlabel, len(labels), config.COMPANIES_PER_MINER))

        missing = [c for c in self.reg.company_labels() if c not in self._miner_of]
        if missing:
            self._issues.append("%d company(ies) with no cluster on chain: %s"
                                % (len(missing), missing[:5]))

        self._loaded = True
        total = sum(len(v) for v in self._company_of.values())
        if self._issues:
            for msg in self._issues:
                self.log.warn("membership: %s" % msg)
        self.log.info("membership read from chain: %d clusters, %d companies "
                      "(via getstreamkeysummary jsonobjectmerge)"
                      % (len(self._company_of), total))
        return self

    def _read_cluster(self, miner_addr):
        """The set of company ADDRESSES associated with `miner_addr`, as the node's own
        jsonobjectmerge folds them. Returns a set (possibly empty)."""
        ok, res = self.net.admin.cli_ok(
            "getstreamkeysummary", config.MEMBERSHIP_STREAM, miner_addr,
            "jsonobjectmerge")
        if not ok:
            self.log.warn("getstreamkeysummary(%s) failed: %s" % (miner_addr, res))
            return set()
        merged = _unwrap_json(res)
        if not isinstance(merged, dict):
            self.log.warn("membership summary for %s is not an object: %r"
                          % (miner_addr, res))
            return set()
        # Field NAMES are the company addresses (the values are publish timestamps).
        return set(str(k) for k in merged.keys() if k)

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
    """getstreamkeysummary may hand back the merged object directly or still wrapped
    in {"json": ...} depending on how the items were published -- the same ambiguity
    mc_WeightUnwrapItemJson absorbs on the C++ side. Accept both."""
    if isinstance(value, dict) and "json" in value and isinstance(value["json"], dict):
        return value["json"]
    return value
