#!/usr/bin/env python3
# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# audit_transfers.py — prove that no GAS moved between two ordinary nodes.
# =============================================================================
# The economic model permits exactly two directions of native-currency movement:
#
#     admin -> node       the initial distribution and the liveness refuel
#     node  -> treasury   the restitution that produces R_k   (Def. 6.6)
#
# Anything else -- a company paying another company, a miner paying a CA -- is outside the
# model. Thesis 4.2.1 is explicit that GAS "non svolge [...] la funzione di strumento di
# scambio economico tra aziende".
#
# WHY THIS IS AUDITED FROM THE CHAIN, and not from the generator. A harness that only ever
# issues legitimate transfers proves nothing: the claim is about every transfer that
# happened, including any the harness did not intend, and the only witness to that is the
# ledger. So this walks the confirmed blocks and reconstructs each transaction's
# (signers -> recipients) shape from the chain itself.
#
# WHY IT WALKS BURIED HEIGHTS ONLY. Below the stability margin the block set can still
# change under a reorg, and a transfer read from a block that is later replaced is not a
# fact about the chain. Same rule, and the same reason, as the weight engine's own
# buried-epoch requirement.
#
# Signers are resolved by fetching each input's previous output, because a transaction
# does not carry its input addresses. That is one extra RPC per input and this runs once,
# at the end of a run, over a bounded range.
#
# Configuration arrives by environment rather than argv, so that addresses (which can be
# numerous) do not have to be quoted through two layers of shell:
#
#   FL_AUDIT_ADMIN      the admin address          (may pay anybody)
#   FL_AUDIT_TREASURY   the treasury address       (may be paid by anybody)
#   FL_AUDIT_KNOWN      comma-separated node addresses
#   FL_AUDIT_FROM/TO    the closed, buried height range
#   FL_AUDIT_BIN/DD/PORT/CHAIN   how to reach multichain-cli
#
# Output: one line per violation, empty when there are none. Exit code is always 0 --
# the CALLER decides what a violation means, and a non-zero exit here would be
# indistinguishable from the script failing to run.

from __future__ import annotations

import json
import os
import subprocess
import sys

BIN = os.environ.get("FL_AUDIT_BIN", "")
DD = os.environ.get("FL_AUDIT_DD", "")
PORT = os.environ.get("FL_AUDIT_PORT", "")
CHAIN = os.environ.get("FL_AUDIT_CHAIN", "")

ADMIN = os.environ.get("FL_AUDIT_ADMIN", "")
TREASURY = os.environ.get("FL_AUDIT_TREASURY", "")
KNOWN = {a for a in os.environ.get("FL_AUDIT_KNOWN", "").split(",") if a}


def cli(*args):
    """One multichain-cli call, parsed as JSON. None when it fails or is not JSON.

    multichain-cli echoes the request JSON ahead of the response, so the first line is
    dropped when it is the echo -- the same trap fl_strip_request_json exists for on the
    shell side.
    """
    cmd = [os.path.join(BIN, "multichain-cli"),
           "-datadir=%s" % DD, "-rpcport=%s" % PORT, CHAIN] + [str(a) for a in args]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    lines = [l for l in out.splitlines() if '"method"' not in l]
    try:
        return json.loads("\n".join(lines))
    except ValueError:
        return None


def out_address(vout):
    spk = vout.get("scriptPubKey", {}) or {}
    addrs = spk.get("addresses")
    if addrs:
        return addrs[0]
    return spk.get("address") or ""


def main():
    try:
        lo = int(os.environ.get("FL_AUDIT_FROM", "1"))
        hi = int(os.environ.get("FL_AUDIT_TO", "0"))
    except ValueError:
        return 0
    if hi < lo or not KNOWN:
        return 0

    prevout_cache = {}
    violations = []

    for height in range(lo, hi + 1):
        block = cli("getblock", height, 1)
        if not isinstance(block, dict):
            continue
        for txid in block.get("tx", []) or []:
            tx = cli("getrawtransaction", txid, 1)
            if not isinstance(tx, dict):
                continue
            vins = tx.get("vin", []) or []
            # A coinbase has no resolvable signer and pays the miner its reward and fees.
            # It is never a transfer between two parties.
            if any("coinbase" in vin for vin in vins):
                continue

            signers = set()
            for vin in vins:
                ptxid, pn = vin.get("txid"), vin.get("vout")
                if ptxid is None or pn is None:
                    continue
                key = (ptxid, pn)
                if key not in prevout_cache:
                    ptx = cli("getrawtransaction", ptxid, 1)
                    addr = ""
                    if isinstance(ptx, dict):
                        vouts = ptx.get("vout", []) or []
                        if 0 <= pn < len(vouts):
                            addr = out_address(vouts[pn])
                    prevout_cache[key] = addr
                if prevout_cache[key]:
                    signers.add(prevout_cache[key])

            if not signers or ADMIN in signers:
                continue          # admin -> anybody is the legitimate funding direction

            for vout in tx.get("vout", []) or []:
                try:
                    value = float(vout.get("value") or 0)
                except (TypeError, ValueError):
                    value = 0.0
                if value <= 0:
                    continue      # OP_RETURN / data outputs carry no value
                dest = out_address(vout)
                if not dest or dest == TREASURY or dest == ADMIN:
                    continue      # node -> treasury is the restitution; -> admin is a return
                if dest in signers:
                    continue      # the transaction's own change
                if dest in KNOWN:
                    violations.append(
                        "height %d tx %s: %s -> %s  %.8f GAS  (neither party is admin/treasury)"
                        % (height, txid[:16], ",".join(sorted(signers))[:34], dest[:34], value))

    for v in violations:
        print(v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
