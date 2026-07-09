#!/usr/bin/env bash
#
# Functional (end-to-end) smoke test for the wPoA weight registry.
#
# Drives a REAL single multichaind node: creates a throwaway chain with fast
# blocks, starts the node with -weight=<N>, waits until the weight is confirmed
# on-chain, asserts it via `getallweights`, then stops the node and cleans up.
#
# Requires the node to be built first (see src/wpoa/TESTING.md §1).
#
# Usage:
#   ./src/wpoa/test/functional_test_wpoa.sh
#   BINDIR=./src WEIGHT=200 TIMEOUT=180 ./src/wpoa/test/functional_test_wpoa.sh
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"          # .../src

BINDIR="${BINDIR:-$SRC_DIR}"
WEIGHT="${WEIGHT:-137}"
TIMEOUT="${TIMEOUT:-150}"                            # seconds to wait for confirmation
CHAIN="wpoaft$$"                                     # unique-ish chain name
DATADIR="$(mktemp -d "${TMPDIR:-/tmp}/wpoa_ft.XXXXXX")"
RPCPORT=$(( 20000 + (RANDOM % 20000) ))
P2PPORT=$(( RPCPORT + 1 ))

MCUTIL="$BINDIR/multichain-util"
MCD="$BINDIR/multichaind"
CLI="$BINDIR/multichain-cli -datadir=$DATADIR -rpcport=$RPCPORT $CHAIN"

fail() { echo "FUNCTIONAL TEST FAILED: $*" >&2; exit 1; }

cleanup() {
    echo "Cleaning up..."
    $BINDIR/multichain-cli -datadir="$DATADIR" -rpcport=$RPCPORT "$CHAIN" stop >/dev/null 2>&1 || true
    sleep 2
    # Best-effort: kill any leftover daemon on this datadir.
    pkill -f "multichaind $CHAIN -datadir=$DATADIR" >/dev/null 2>&1 || true
    rm -rf "$DATADIR"
}
trap cleanup EXIT

for b in "$MCUTIL" "$MCD"; do
    [ -x "$b" ] || fail "binary not found or not executable: $b (build the node first)"
done

echo "== wPoA functional test =="
echo "  chain=$CHAIN weight=$WEIGHT datadir=$DATADIR rpcport=$RPCPORT"

# 1. Create the chain.
"$MCUTIL" create "$CHAIN" -datadir="$DATADIR" >/dev/null 2>&1 \
    || fail "multichain-util create failed"

# 2. Speed up mining for the test (params are fixed at creation time).
PARAMS="$DATADIR/$CHAIN/params.dat"
[ -f "$PARAMS" ] || fail "params.dat not found at $PARAMS"
sed -i -E "s/^(target-block-time[[:space:]]*=[[:space:]]*)[0-9]+/\12/"        "$PARAMS" || true
sed -i -E "s/^(mine-empty-rounds[[:space:]]*=[[:space:]]*)[-0-9.]+/\11000/"   "$PARAMS" || true

# 3. Start the node (single permitted miner => mines its own transactions).
echo "Starting node..."
"$MCD" "$CHAIN" -datadir="$DATADIR" -port=$P2PPORT -rpcport=$RPCPORT \
       -weight="$WEIGHT" -daemon >/dev/null 2>&1 \
    || fail "multichaind failed to launch"

# 4. Wait for the RPC interface to come up.
echo -n "Waiting for RPC"
for i in $(seq 1 30); do
    if $CLI getinfo >/dev/null 2>&1; then echo " up."; break; fi
    echo -n "."; sleep 1
    [ "$i" -eq 30 ] && { echo; fail "RPC did not come up"; }
done

# 5. Poll getallweights until the weight is confirmed (single node => total == WEIGHT).
echo "Waiting for weight $WEIGHT to be confirmed (timeout ${TIMEOUT}s)..."
deadline=$(( SECONDS + TIMEOUT ))
last=""
while [ "$SECONDS" -lt "$deadline" ]; do
    out="$($CLI getallweights 2>/dev/null)"
    last="$out"
    # total equals the single node's weight once its publish tx is mined.
    if echo "$out" | grep -qE "\"total\"[[:space:]]*:[[:space:]]*$WEIGHT([^0-9]|$)"; then
        echo "----------------------------------------"
        echo "$out"
        echo "----------------------------------------"
        echo "FUNCTIONAL TEST PASSED (weight $WEIGHT confirmed on-chain)."
        exit 0
    fi
    sleep 3
done

echo "---- last getallweights ----"
echo "$last"
echo "---- debug.log (tail) ----"
tail -n 40 "$DATADIR/$CHAIN/debug.log" 2>/dev/null | grep -i "StreamWeightRegistry" || tail -n 20 "$DATADIR/$CHAIN/debug.log" 2>/dev/null
fail "weight $WEIGHT was not confirmed within ${TIMEOUT}s"
