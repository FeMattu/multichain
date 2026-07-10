#!/usr/bin/env bash
#
# Functional (end-to-end) smoke test for the wPoA weight registry.
#
# Generalizes the single-node test to N >= 1 nodes:
#   - N == 1: identical behavior to the original single-node test.
#   - N  > 1: bootstraps a permissioned MultiChain network of N nodes, each
#             started with its own -weight=<Wi>, and verifies that node 0
#             observes the correct AGGREGATE weight via `getallweights`.
#
# Bootstrap protocol per additional node (MultiChain permission-gated P2P),
# following the reference methodology (see Create-a-Blockchain.md §5):
#   1. Launch `multichaind CHAIN@127.0.0.1:P2P0 -datadir=... -weight=Wi`. On a
#      permissioned chain (the default) the node initializes its local chain
#      copy and wallet, prints the address the admin must grant, and EXITS
#      without serving RPC. (If the chain is anyone-can-connect it instead
#      stays up and joins directly — detected by probing RPC.)
#   2. Read the node's own wallet address from the grant hint it printed. RPC
#      is not reachable at this stage, so `getaddresses` cannot be used.
#   3. Node 0 (the chain admin) grants `connect,send,receive,mine` (and,
#      best-effort, write access to the wpoa-weights stream) to that address.
#   4. Relaunch the node with -daemon; it now joins because the address is
#      permitted, and serves RPC.
#
# Requires the node to be built first (see src/wpoa/TESTING.md §1).
#
# Usage:
#   ./functional_test_wpoa_multinode.sh                       # 3 nodes, default weights
#   NODES=1 ./functional_test_wpoa_multinode.sh                # single-node mode (legacy behavior)
#   NODES=5 WEIGHTS="10 20 30 40 50" ./functional_test_wpoa_multinode.sh
#   BINDIR=./src NODES=4 TIMEOUT=240 ./functional_test_wpoa_multinode.sh
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"          # .../src

BINDIR="${BINDIR:-$SRC_DIR}"
NODES="${NODES:-3}"
TIMEOUT="${TIMEOUT:-180}"          # seconds to wait for aggregate weight confirmation
RPC_TIMEOUT="${RPC_TIMEOUT:-30}"   # seconds to wait for each node's RPC to come up
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-30}"  # seconds to wait for a bootstrap node to be granted+reconnect
CHAIN="wpoamn$$"                    # unique-ish chain name

# ---- wPoA Phase 2 (weighted proposer selection) knobs -----------------------
# ENABLEWPOA=1 starts every node with -enablewpoa so the weighted election
# governs mining after the setup period. DIST_BLOCKS>0 additionally runs the
# proposer-distribution / chi-square assertion (the Phase 2 thesis artifact);
# DIST_BLOCKS=0 keeps the legacy behavior (assert aggregate weight, then stop).
ENABLEWPOA="${ENABLEWPOA:-1}"
DIST_BLOCKS="${DIST_BLOCKS:-1000}"      # wPoA-governed blocks to sample
DIST_TOLERANCE="${DIST_TOLERANCE:-0.05}" # per-validator ±relative tolerance (±5%)
DIST_TIMEOUT="${DIST_TIMEOUT:-600}"     # seconds to wait for the sample to accrue
# wPoA engages at height >= setup-first-blocks. Kept comfortably above the time
# it takes every node to join and get its weight confirmed, so the whole sample
# is elected from a converged, identical weight map on every node.
SETUP_BLOCKS="${SETUP_BLOCKS:-40}"

WPOA_ARGS=""
if [ "$ENABLEWPOA" = "1" ]; then
    WPOA_ARGS="-enablewpoa=1 -debug=wpoa"
fi

MCUTIL="$BINDIR/multichain-util"
MCD="$BINDIR/multichaind"

declare -a DATADIRS RPCPORTS P2PPORTS WEIGHTS_ARR

fail() { echo "FUNCTIONAL TEST FAILED: $*" >&2; exit 1; }

# ---- parse/derive weights ---------------------------------------------------
if [ -n "${WEIGHTS:-}" ]; then
    read -r -a WEIGHTS_ARR <<< "$WEIGHTS"
fi
for ((i = 0; i < NODES; i++)); do
    if [ -z "${WEIGHTS_ARR[i]:-}" ]; then
        WEIGHTS_ARR[i]=$((137 + i * 50))   # distinct default weights per node
    fi
done
TOTAL_WEIGHT=0
for w in "${WEIGHTS_ARR[@]:0:$NODES}"; do TOTAL_WEIGHT=$((TOTAL_WEIGHT + w)); done

# ---- allocate ports & datadirs ----------------------------------------------
BASE_RPC_PORT=$(( 20000 + (RANDOM % 20000) ))
for ((i = 0; i < NODES; i++)); do
    RPCPORTS[i]=$(( BASE_RPC_PORT + i * 10 ))
    P2PPORTS[i]=$(( RPCPORTS[i] + 1 ))
    DATADIRS[i]="$(mktemp -d "${TMPDIR:-/tmp}/wpoa_ft_node${i}.XXXXXX")"
done

cli() {
    local i=$1; shift
    "$BINDIR/multichain-cli" -datadir="${DATADIRS[i]}" -rpcport="${RPCPORTS[i]}" "$CHAIN" "$@"
}

cleanup() {
    echo "Cleaning up..."
    for ((i = NODES - 1; i >= 0; i--)); do
        cli "$i" stop >/dev/null 2>&1 || true
    done
    sleep 2
    for ((i = 0; i < NODES; i++)); do
        pkill -f "multichaind .*-datadir=${DATADIRS[i]}" >/dev/null 2>&1 || true
        rm -rf "${DATADIRS[i]}"
    done
}
trap cleanup EXIT

for b in "$MCUTIL" "$MCD"; do
    [ -x "$b" ] || fail "binary not found or not executable: $b (build the node first)"
done

echo "== wPoA multi-node functional test =="
echo "  chain=$CHAIN nodes=$NODES weights=(${WEIGHTS_ARR[*]:0:$NODES}) total=$TOTAL_WEIGHT"

# ---- wait helpers ------------------------------------------------------------
wait_for_rpc() {
    local i=$1
    echo -n "  waiting for RPC on node $i"
    for ((t = 0; t < RPC_TIMEOUT; t++)); do
        if cli "$i" getinfo >/dev/null 2>&1; then echo " up."; return 0; fi
        echo -n "."; sleep 1
    done
    echo
    return 1
}

get_node_address_from_log() {
    # A node joining a permissioned chain for the first time cannot serve RPC:
    # it initializes its datadir, prints the address the admin must grant, and
    # exits (verified against MultiChain 2.3). `getaddresses` is therefore not
    # reachable at this point, so we parse the address out of the grant hint the
    # node itself prints, e.g.:
    #   multichain-cli CHAIN grant 1FBSdDQ6XLKSma4Su6pidsyYX13YAA81jBrn6d connect
    local log=$1
    grep -oE 'grant[[:space:]]+[A-Za-z0-9]{30,40}[[:space:]]+connect' "$log" \
        | head -n1 | awk '{print $2}'
}

# ---- node 0: create chain and bootstrap the network -------------------------
"$MCUTIL" create "$CHAIN" -datadir="${DATADIRS[0]}" >/dev/null 2>&1 \
    || fail "multichain-util create failed"

PARAMS="${DATADIRS[0]}/$CHAIN/params.dat"
[ -f "$PARAMS" ] || fail "params.dat not found at $PARAMS"
sed -i -E "s/^(target-block-time[[:space:]]*=[[:space:]]*)[0-9]+/\12/"      "$PARAMS" || true
sed -i -E "s/^(mine-empty-rounds[[:space:]]*=[[:space:]]*)[-0-9.]+/\11000/" "$PARAMS" || true
# wPoA engages at height >= setup-first-blocks; give weights time to converge.
sed -i -E "s/^(setup-first-blocks[[:space:]]*=[[:space:]]*)[0-9]+/\1$SETUP_BLOCKS/" "$PARAMS" || true

echo "Starting node 0 (seed, weight=${WEIGHTS_ARR[0]})..."
"$MCD" "$CHAIN" -datadir="${DATADIRS[0]}" -port="${P2PPORTS[0]}" -rpcport="${RPCPORTS[0]}" \
       -weight="${WEIGHTS_ARR[0]}" $WPOA_ARGS -daemon >/dev/null 2>&1 \
    || fail "multichaind failed to launch node 0"

wait_for_rpc 0 || fail "RPC did not come up on node 0"

# All nodes run on this host, so connect over loopback. We deliberately do NOT
# use getinfo's "nodeaddress" here: on some hosts (e.g. WSL) it reports a NAT
# address such as 10.255.255.254 that peers on the same machine cannot dial,
# whereas 127.0.0.1 is always reachable for a same-host test.
SEED_ADDR="$CHAIN@127.0.0.1:${P2PPORTS[0]}"
echo "  seed node address: $SEED_ADDR"

# ---- bootstrap additional nodes ----------------------------------------------
bootstrap_node() {
    local i=$1
    local weight=${WEIGHTS_ARR[i]}
    local log="${DATADIRS[i]}/node.log"

    echo "Bootstrapping node $i (weight=$weight)..."

    # Step 1: first launch. This initializes the node's datadir/wallet and
    # fetches chain params from the seed. On a permissioned chain (the default
    # from `multichain-util create`) the node is not yet allowed in, so it
    # prints the grant hint and exits WITHOUT serving RPC. If the chain is
    # anyone-can-connect, it instead stays up and its RPC becomes reachable.
    #
    # NOTE: with -daemon the launcher returns 0 even in the not-permitted case
    # (it forks before discovering the rejection), so the exit code is NOT a
    # reliable join signal. We detect a real join by probing RPC instead.
    "$MCD" "$SEED_ADDR" -datadir="${DATADIRS[i]}" -port="${P2PPORTS[i]}" -rpcport="${RPCPORTS[i]}" \
           -weight="$weight" $WPOA_ARGS -daemon > "$log" 2>&1

    # Fast path: node came up on its own (anyone-can-connect) -> nothing to grant.
    for ((t = 0; t < 5; t++)); do
        if cli "$i" getinfo >/dev/null 2>&1; then
            echo "  node $i joined directly (no grant needed)"
            return 0
        fi
        sleep 1
    done

    # Step 2: read the node's own address from the grant hint it just printed.
    local addr
    addr="$(get_node_address_from_log "$log")"
    if [ -z "$addr" ]; then
        cat "$log" >&2
        fail "could not determine wallet address for node $i (no grant hint in log)"
    fi
    echo "  node $i address: $addr -> granting permissions from node 0"

    # Step 3: grant permissions from node 0 (the chain admin).
    if ! cli 0 grant "$addr" connect,send,receive,mine >/dev/null 2>&1; then
        fail "grant connect,send,receive,mine failed for node $i ($addr)"
    fi
    # Best-effort: only needed if the wpoa-weights stream was created as
    # restricted-write. The registry creates it open, so this is normally a
    # no-op, but it keeps the test correct if that ever changes.
    cli 0 grant "$addr" wpoa-weights.write >/dev/null 2>&1 || true

    # Step 4: relaunch as a daemon. Now that the address is permitted the node
    # joins and serves RPC. Retry to absorb any grant-propagation delay; each
    # failed attempt exits on its own, so re-launching on the same port is safe.
    for ((t = 0; t < CONNECT_TIMEOUT; t += 2)); do
        "$MCD" "$SEED_ADDR" -datadir="${DATADIRS[i]}" -port="${P2PPORTS[i]}" -rpcport="${RPCPORTS[i]}" \
               -weight="$weight" $WPOA_ARGS -daemon > "$log" 2>&1
        if wait_for_rpc "$i"; then
            return 0
        fi
        sleep 2
    done
    cat "$log" >&2
    return 1
}

for ((i = 1; i < NODES; i++)); do
    bootstrap_node "$i" || fail "node $i refused to join after granting permissions (see ${DATADIRS[i]}/node.log)"
    wait_for_rpc "$i" || fail "RPC did not come up on node $i"
done

# ---- wait until EVERY node has the full weight map confirmed -----------------
# The whole distribution sample must be elected from a converged, identical
# weight map on every node, so we require the aggregate on all nodes (not just
# node 0) before proceeding.
node_total() {
    cli "$1" getallweights 2>/dev/null \
        | sed -nE 's/.*"total"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' | head -n1
}
tip_height() { cli "$1" getblockcount 2>/dev/null; }
tip_hash()   { cli "$1" getbestblockhash 2>/dev/null; }

echo "Waiting for aggregate weight $TOTAL_WEIGHT to be confirmed on ALL $NODES node(s) (timeout ${TIMEOUT}s)..."
deadline=$(( SECONDS + TIMEOUT ))
converged=0
while [ "$SECONDS" -lt "$deadline" ]; do
    all_ok=1
    for ((i = 0; i < NODES; i++)); do
        [ "$(node_total "$i")" = "$TOTAL_WEIGHT" ] || { all_ok=0; break; }
    done
    if [ "$all_ok" = "1" ]; then converged=1; break; fi
    sleep 3
done

if [ "$converged" != "1" ]; then
    echo "---- last getallweights per node ----"
    for ((i = 0; i < NODES; i++)); do echo "node $i: total=$(node_total "$i")"; done
    echo "---- debug.log tail (node 0) ----"
    tail -n 30 "${DATADIRS[0]}/$CHAIN/debug.log" 2>/dev/null | grep -iE "StreamWeightRegistry|wpoa" \
        || tail -n 20 "${DATADIRS[0]}/$CHAIN/debug.log" 2>/dev/null
    fail "aggregate weight $TOTAL_WEIGHT was not confirmed on all nodes within ${TIMEOUT}s"
fi

echo "----------------------------------------"
cli 0 getallweights
echo "----------------------------------------"
echo "Aggregate weight $TOTAL_WEIGHT confirmed across all $NODES node(s)."

# Legacy mode: no distribution phase requested (or wPoA disabled) -> done.
if [ "$ENABLEWPOA" != "1" ] || [ "$DIST_BLOCKS" -le 0 ]; then
    echo "FUNCTIONAL TEST PASSED (aggregate weight confirmed; distribution phase skipped)."
    exit 0
fi

# ---- Phase 2: proposer-distribution / chi-square goodness-of-fit ------------
# Weights are globally confirmed, so from here every height is elected from the
# same weight map on every node. Sample only heights that are (a) wPoA-governed
# (>= setup-first-blocks) and (b) strictly after this convergence point.
cur="$(tip_height 0)"; cur="${cur:-0}"
SAMPLE_START=$(( cur + 1 ))
[ "$SAMPLE_START" -lt "$SETUP_BLOCKS" ] && SAMPLE_START=$SETUP_BLOCKS
SAMPLE_END=$(( SAMPLE_START + DIST_BLOCKS - 1 ))

echo
echo "== wPoA Phase 2 proposer-distribution test =="
echo "  sampling heights $SAMPLE_START..$SAMPLE_END ($DIST_BLOCKS blocks), tolerance ±$(awk "BEGIN{printf \"%.1f\",$DIST_TOLERANCE*100}")%"
echo "  waiting for the chain to reach height $SAMPLE_END (timeout ${DIST_TIMEOUT}s)..."

deadline=$(( SECONDS + DIST_TIMEOUT ))
last_h=-1; stall_since=$SECONDS
while [ "$SECONDS" -lt "$deadline" ]; do
    h="$(tip_height 0)"; h="${h:-0}"
    if [ "$h" -ge "$SAMPLE_END" ]; then break; fi
    if [ "$h" -ne "$last_h" ]; then last_h=$h; stall_since=$SECONDS
        # progress ping roughly every ~50 blocks
        [ $(( h % 50 )) -eq 0 ] && echo "    height $h / $SAMPLE_END"
    elif [ $(( SECONDS - stall_since )) -ge 120 ]; then
        echo "    WARNING: chain appears stalled at height $h for 120s"
        stall_since=$SECONDS
    fi
    sleep 2
done

h="$(tip_height 0)"; h="${h:-0}"
[ "$h" -ge "$SAMPLE_END" ] || fail "chain only reached height $h of $SAMPLE_END within ${DIST_TIMEOUT}s"

# Consistency: all nodes must agree on the tip hash at the sample end (no fork).
ref_hash="$(tip_hash 0)"
for ((i = 1; i < NODES; i++)); do
    hi="$(tip_hash "$i")"
    # A node may be a block or two ahead; compare the block hash at SAMPLE_END.
    hi_at_end="$(cli "$i" getblockhash "$SAMPLE_END" 2>/dev/null)"
    h0_at_end="$(cli 0 getblockhash "$SAMPLE_END" 2>/dev/null)"
    if [ -n "$hi_at_end" ] && [ "$hi_at_end" != "$h0_at_end" ]; then
        fail "fork detected: node $i block $SAMPLE_END = $hi_at_end != node 0 $h0_at_end"
    fi
done
echo "  all nodes agree on the chain at height $SAMPLE_END (no fork)."

# Collect the data and analyze.
WEIGHTS_JSON="${DATADIRS[0]}/weights.json"
BLOCKS_JSON="${DATADIRS[0]}/blocks.json"
cli 0 getallweights > "$WEIGHTS_JSON" 2>/dev/null || fail "getallweights failed"
cli 0 listblocks "$SAMPLE_START-$SAMPLE_END" > "$BLOCKS_JSON" 2>/dev/null \
    || fail "listblocks $SAMPLE_START-$SAMPLE_END failed"

python3 "$SCRIPT_DIR/analyze_distribution.py" "$WEIGHTS_JSON" "$BLOCKS_JSON" "$DIST_TOLERANCE"
rc=$?
if [ "$rc" -ne 0 ]; then
    fail "proposer distribution did not match weight ratios within tolerance (see table above)"
fi

echo "FUNCTIONAL TEST PASSED (weighted proposer distribution matches weight ratios within tolerance over $DIST_BLOCKS blocks)."
exit 0