# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# weight_reader.py -- READS the engine's output and the chain; it never computes
# weights (that logic lives in the node, per the experiment spec). Sources:
#
#   1. getallweights            -- the live confirmed wpoa-weights registry
#                                  ({validators, total, weights:{addr:int}}); the
#                                  aggregate snapshot used for probabilities.
#   2. debug.log "[WeightEngine] epoch E (height H): w_k = W for ADDR" lines --
#      the AUTHORITATIVE per-epoch integer weight each miner published, tagged with
#      its epoch. Parsed across every miner's debug.log (same debug.log-grep
#      approach as src/wpoa/test). This is how per-epoch weight columns are filled.
#   3. listblocks "<range>"     -- per block: proposer (miner), height, time and
#      txcount, in ONE call. This is the chain source of the MyLedger economics:
#        * TxMiner_k^{(e)} = validated transactions in the blocks k proposed in e
#                            (= sum of txcount-1, dropping each coinbase), which
#                            drives Guadagno_k = TxMiner_k * ALPHA;
#        * Delay_k^{(e)}   = mean inter-block interval of those blocks, in msec.
#   4. getblock <h> 1           -- the txid list of a block, so any transaction's
#      confirming height (hence epoch) is resolved from the block index rather than
#      assumed from when it was submitted.
#   5. liststreamitems <stream> -- the publisher of every stream item, so the stream
#      publishes that the harness did not submit itself (above all each miner's own
#      per-epoch w_k publish to wpoa-weights) are still attributed to their signer.
#      This is what lets the replayed tau match the engine's exactly.
#
# NOTE ON "Delay in msec". listblocks' timestamps give the real mean inter-block
# interval, reported as `block_interval_ms`. It is NOT the Vers_2 "Delay in msec"
# column, which is the per-mille normalized weight (economics.py); the two are
# unrelated despite the name.

import os
import re

import config

# [WeightEngine] epoch 3 (height 18): w_k = 42 for 1ABC...
_WK_RE = re.compile(
    r"\[WeightEngine\]\s+epoch\s+(\d+)\s+\(height\s+(\d+)\):\s+w_k\s*=\s*(\d+)\s+for\s+([A-Za-z0-9]+)")

# listblocks is asked for at most this many heights per call, so one very long
# sampling run never builds a single multi-megabyte JSON response.
_BLOCK_CHUNK = 500


class WeightReader(object):
    def __init__(self, network, registry, log):
        self.net = network
        self.reg = registry
        self.log = log

    # -- live aggregate -----------------------------------------------------
    def get_all_weights(self):
        """Return {address: int_weight} from the admin node's getallweights, or {}."""
        ok, res = self.net.admin.cli_ok("getallweights")
        if ok and isinstance(res, dict):
            w = res.get("weights", {})
            return {a: int(v) for a, v in w.items()}
        return {}

    def wait_all_miners_weighted(self, timeout=None):
        """Wait until every miner appears in getallweights. Returns the weight map
        (possibly incomplete on timeout)."""
        import time
        deadline = time.time() + (timeout if timeout else config.WEIGHT_TIMEOUT)
        want = self.reg.miner_address_set()
        while time.time() < deadline:
            w = self.get_all_weights()
            if want.issubset(set(w.keys())):
                return w
            time.sleep(3)
        return self.get_all_weights()

    # -- per-epoch weights from the miners' debug.logs ----------------------
    def epoch_weights_from_logs(self):
        """Scan every miner's debug.log for the published-weight lines and return
        {epoch: {miner_label: int_weight}} (last value wins for a given
        epoch+miner, i.e. the confirmed republish)."""
        by_epoch = {}
        for node in self.net.nodes:
            path = os.path.join(node.datadir, self.net.chain, "debug.log")
            try:
                with open(path, "r", errors="replace") as f:
                    text = f.read()
            except IOError:
                continue
            for m in _WK_RE.finditer(text):
                epoch = int(m.group(1))
                addr = m.group(4)
                weight = int(m.group(3))
                label = self.reg.label_of(addr)
                by_epoch.setdefault(epoch, {})[label] = weight
        return by_epoch

    # -- blocks -------------------------------------------------------------
    def block_index(self, lo, hi):
        """Per-block facts for heights [lo, hi], read from listblocks in chunks.

        Returns {height: {"miner": label_or_None, "time": int, "txcount": int,
        "validated": txcount-1}}. `validated` drops the coinbase, so it is the count
        of real transactions in that block.

        `validated` is an AUDIT quantity (it cross-checks that every transaction was
        accounted for exactly once), NOT an earnings one: Guadagno is the epoch's fee
        pot distributed by weight share, and does not depend on who proposed a block.
        See config.py "ECONOMICS"."""
        out = {}
        if hi < lo:
            return out
        start = max(0, lo)
        while start <= hi:
            end = min(hi, start + _BLOCK_CHUNK - 1)
            ok, res = self.net.admin.cli_ok("listblocks", "%d-%d" % (start, end))
            if ok and isinstance(res, list):
                for b in res:
                    if not isinstance(b, dict):
                        continue
                    h = b.get("height")
                    if h is None:
                        continue
                    miner = b.get("miner")
                    txcount = int(b.get("txcount") or 0)
                    out[int(h)] = {
                        "miner": self.reg.label_of(miner) if miner else None,
                        "time": int(b.get("time") or 0),
                        "txcount": txcount,
                        # a block always carries exactly one coinbase, which has no
                        # resolvable signer and is not a network transaction.
                        "validated": max(0, txcount - 1),
                    }
            else:
                self.log.warn("listblocks %d-%d failed: %s" % (start, end, res))
            start = end + 1
        return out

    # -- stream publishers --------------------------------------------------
    def stream_publishers(self, stream, count=200000):
        """{txid: [publisher_label, ...]} for every item of `stream`.

        WHY. The engine's tau counts +1 per distinct signing address per non-coinbase
        transaction (weight_reader.cpp ComputeActivityForEpoch) -- and a STREAM PUBLISH
        is such a transaction. Each miner publishes its own w_k to wpoa-weights once
        per epoch, which the harness never submits and so cannot see in its own
        records; ignoring it leaves the replayed tau_{Mk} short by one per epoch and
        forces the engine comparison down to a ranking test.

        Reading the publishers straight off the stream's own index closes that gap
        exactly, so tau can be reconstructed to the transaction and w_k compared to the
        node BY VALUE. Returns {} (with a warning) if the node has no items index for
        the stream, in which case the caller degrades to the ranking comparison."""
        ok, res = self.net.admin.cli_ok("liststreamitems", stream, True, count, 0)
        if not ok or not isinstance(res, list):
            self.log.warn("liststreamitems %s failed (no items index?): %s"
                          % (stream, res))
            return {}
        out = {}
        for item in res:
            if not isinstance(item, dict):
                continue
            txid = item.get("txid")
            if not txid:
                continue
            pubs = item.get("publishers") or []
            out[txid] = [self.reg.label_of(p) for p in pubs if p]
        self.log.debug("stream %s: %d items indexed by publisher" % (stream, len(out)))
        return out

    def proposers_in_range(self, start, end):
        """Return a list of (height, miner_label) for blocks [start, end], reading
        the miner field of listblocks (as analyze_distribution.py does)."""
        idx = self.block_index(start, end)
        return [(h, idx[h]["miner"]) for h in sorted(idx)]

    def block_tx_index(self, lo, hi):
        """Scan blocks [lo, hi] and return (txid -> height, height -> proposer_label).
        Uses getblock (tx list per block) + listblocks (miner per block), so a tx's
        confirming block/epoch can be resolved for any signer, not just wallet txs."""
        idx = self.block_index(lo, hi)
        h2prop = dict((h, idx[h]["miner"]) for h in idx)
        txid2h = {}
        for h in range(max(0, lo), hi + 1):
            ok, res = self.net.admin.cli_ok("getblock", str(h), 1)
            if ok and isinstance(res, dict):
                for txid in res.get("tx", []):
                    txid2h[txid] = h
        return txid2h, h2prop

    @staticmethod
    def normalized(weights):
        """Map {label/addr: weight} -> {same key: probability}. Empty if total 0."""
        total = sum(weights.values())
        if total <= 0:
            return {k: 0.0 for k in weights}
        return {k: v / float(total) for k, v in weights.items()}
