#!/usr/bin/env bash
#
# Functional test — WeightEngine publish side (admin attestations) + closed streams.
# -----------------------------------------------------------------------------
# Brings up a single genesis node with the weight engine enabled, then asserts:
#   1. the three admin input streams are auto-created (CLOSED);
#   2. an admin publishes a valid ESG / membership / reconciliation record;
#   3. an invalid ESG (score <= 0) is rejected by schema round-trip validation;
#   4. a future-epoch reconciliation is rejected;
#   5. a raw publish from an address without write permission is rejected (the
#      CLOSED-stream guard against schema-bypassing writes);
#   6. the published records are readable back;
#   7. wpoa-weights (getallweights) still works — the output contract is intact.
#
# Self-contained: no external deps beyond python3 (JSON parsing). Fast blocks
# (target-block-time=1) keep confirmations quick.
#
# Usage:  ./functional_test_weight_engine.sh
# Exit:   0 iff every assertion passed.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"     # repo root
MCD="$ROOT/src/multichaind"
UTIL="$ROOT/src/multichain-util"
CLIBIN="$ROOT/src/multichain-cli"

CHAIN="wetestpub"
DD="${TMPDIR:-/tmp}/mcw_pub_$$"
PORT=31811
RPC=31812

PASS=0; FAIL=0
say(){ echo "-- $*"; }
ok(){ echo "  PASS: $*"; PASS=$((PASS+1)); }
bad(){ echo "  FAIL: $*"; FAIL=$((FAIL+1)); }

# multichain-cli echoes the request JSON ({"method":...}) ahead of the response;
# strip it so JSON parsing / assertions see only the response.
mcli(){ "$CLIBIN" "$CHAIN" -datadir="$DD" -rpcport=$RPC "$@" 2>&1 | grep -v '"method"'; }
first_addr(){ mcli getaddresses | python3 -c 'import sys,json; a=json.load(sys.stdin); print(a[0] if a else "")' 2>/dev/null; }
is_txid(){ echo "$1" | grep -qiE '[0-9a-f]{64}'; }

cleanup(){ mcli stop >/dev/null 2>&1; sleep 2; pkill -x multichaind 2>/dev/null; rm -rf "$DD"; }
trap cleanup EXIT

pkill -x multichaind 2>/dev/null; sleep 1
rm -rf "$DD"; mkdir -p "$DD"

say "creating chain $CHAIN"
"$UTIL" create "$CHAIN" -datadir="$DD" >/dev/null 2>&1
# fast blocks so grant/publish confirmations are quick (2s is the param minimum)
sed -i 's/^target-block-time.*/target-block-time = 2  # (test override)/' "$DD/$CHAIN/params.dat" 2>/dev/null

say "starting daemon (weight engine ON, epoch length 4)"
"$MCD" "$CHAIN" -datadir="$DD" -enablewpoaweights -enableweightengine \
       -weightepochlength=4 -port=$PORT -rpcport=$RPC -daemon >/dev/null 2>&1

# wait for RPC
up=0
for i in $(seq 1 30); do sleep 2; if mcli getinfo >/dev/null 2>&1; then up=1; break; fi; done
if [ "$up" != 1 ]; then
  echo "daemon did not come up; tail of debug.log:"
  tail -20 "$DD/$CHAIN/debug.log" 2>/dev/null
  exit 1
fi

ADMIN="$(first_addr)"
say "admin/node address: $ADMIN"
[ -n "$ADMIN" ] || { echo "could not resolve node address"; exit 1; }

# 1. streams auto-created (closed)
say "waiting for the 3 admin input streams to be auto-created"
n=0
for i in $(seq 1 30); do
  sleep 2
  n=$(mcli liststreams '*' 2>/dev/null | grep -oE 'weight-engine-[a-z]+' | sort -u | wc -l)
  [ "${n:-0}" -ge 3 ] && break
done
[ "${n:-0}" -ge 3 ] && ok "3 input streams auto-created" || bad "input streams not created (got ${n:-0})"

# confirm they are CLOSED (open=false)
closed=$(mcli liststreams '*' 2>/dev/null | python3 -c '
import sys,json
try: d=json.load(sys.stdin)
except Exception: d=[]
c=sum(1 for s in d if s.get("name","").startswith("weight-engine-") and s.get("restrict",{}).get("write") is True)
print(c)' 2>/dev/null)
[ "${closed:-0}" -ge 3 ] && ok "input streams are CLOSED (write-restricted)" || bad "streams not closed (closed=${closed:-0})"

# grant write on the 3 streams to the admin address, then let confirm
for s in weight-engine-esg weight-engine-membership weight-engine-reconciliation; do
  mcli grant "$ADMIN" "$s.write" >/dev/null 2>&1
done
sleep 4

# 2a. valid ESG
r=$(mcli weightsetesg "$ADMIN" 15)
is_txid "$r" && ok "admin publishes valid ESG" || bad "valid ESG failed: $r"

# 3. invalid ESG (score 0) rejected
r=$(mcli weightsetesg "$ADMIN" 0)
echo "$r" | grep -qiE 'reject|error|> 0|schema' && ok "invalid ESG (0) rejected" || bad "invalid ESG NOT rejected: $r"

# 2b. membership
r=$(mcli weightsetmembership "$ADMIN" "$ADMIN")
is_txid "$r" && ok "admin publishes membership" || bad "membership failed: $r"

# 2c. reconciliation valid (epoch 1)
r=$(mcli weightsetreconciliation "$ADMIN" 10 1)
is_txid "$r" && ok "admin publishes reconciliation (epoch 1)" || bad "reconciliation failed: $r"

# 4. future-epoch reconciliation rejected
r=$(mcli weightsetreconciliation "$ADMIN" 10 999999)
echo "$r" | grep -qiE 'future|reject|error|invalid' && ok "future-epoch reconciliation rejected" || bad "future epoch NOT rejected: $r"

# 5. raw publish from a fresh (no-write) address is rejected (closed-stream guard)
NW=$(mcli getnewaddress 2>/dev/null | tr -d '"')
r=$(mcli publishfrom "$NW" weight-engine-esg "$ADMIN" "{\"json\":{\"node_address\":\"$ADMIN\",\"esg\":5}}")
echo "$r" | grep -qiE 'error|permission|not|invalid' && ok "raw write from non-write address rejected (closed stream)" || bad "closed stream bypassable: $r"

mcli subscribe weight-engine-esg >/dev/null 2>&1   # ensure we can read items back
sleep 3  # let the valid publishes confirm + subscription import

# 6. published records readable back
r=$(mcli liststreamitems weight-engine-esg 2>/dev/null)
echo "$r" | grep -q '"esg"' && ok "ESG record readable on stream" || bad "ESG record not found: $r"

# 7. wpoa-weights output contract intact
r=$(mcli getallweights 2>/dev/null)
echo "$r" | grep -q 'validators' && ok "getallweights (wpoa-weights) intact" || bad "getallweights broken: $r"

echo ""
echo "== SUMMARY: PASS=$PASS  FAIL=$FAIL =="
[ "$FAIL" -eq 0 ] && { echo "OK"; exit 0; } || { echo "FUNCTIONAL TEST FAILED"; exit 1; }
