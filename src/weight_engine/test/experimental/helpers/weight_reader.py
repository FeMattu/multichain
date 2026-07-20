# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# weight_reader.py -- READS the engine's output; it never computes weights (that
# logic lives in the node, per the experiment spec). Three sources:
#
#   1. getallweights            -- the live confirmed wpoa-weights registry
#                                  ({validators, total, weights:{addr:int}}); the
#                                  aggregate snapshot used for probabilities.
#   2. debug.log "[WeightEngine] epoch E (height H): w_k = W for ADDR" lines --
#      the AUTHORITATIVE per-epoch integer weight each miner published, tagged with
#      its epoch. Parsed across every miner's debug.log (same debug.log-grep
#      approach as src/wpoa/test). This is how per-epoch weight columns are filled.
#   3. listblocks "<range>"     -- the proposer (miner field) of each block, exactly
#      as analyze_distribution.py reads it.

import os
import re

import config

# [WeightEngine] epoch 3 (height 18): w_k = 42 for 1ABC...
_WK_RE = re.compile(
    r"\[WeightEngine\]\s+epoch\s+(\d+)\s+\(height\s+(\d+)\):\s+w_k\s*=\s*(\d+)\s+for\s+([A-Za-z0-9]+)")


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

    # -- proposers ----------------------------------------------------------
    def proposers_in_range(self, start, end):
        """Return a list of (height, miner_label) for blocks [start, end], reading
        the miner field of listblocks (as analyze_distribution.py does)."""
        if end < start:
            return []
        ok, res = self.net.admin.cli_ok("listblocks", "%d-%d" % (start, end))
        out = []
        if ok and isinstance(res, list):
            for b in res:
                h = b.get("height")
                miner = b.get("miner")
                out.append((h, self.reg.label_of(miner) if miner else None))
        return out

    def block_tx_index(self, lo, hi):
        """Scan blocks [lo, hi] and return (txid -> height, height -> proposer_label).
        Uses getblock (tx list per block) + listblocks (miner per block), so a tx's
        confirming block/epoch can be resolved for any signer, not just wallet txs."""
        txid2h = {}
        h2prop = dict((h, lbl) for (h, lbl) in self.proposers_in_range(lo, hi))
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
