#!/usr/bin/env bash
#
# Functional (end-to-end) test for the wPoA Phase 3a VRF randomness beacon.
#
# Bootstraps a permissioned MultiChain network of N nodes started with
# -enablewpoa=1 -enablewpoavrf=1, drives it past the wPoA setup height, and
# asserts the beacon works end-to-end:
#
#   1. LIVENESS UNDER MANDATORY VERIFICATION. Every node REQUIRES a VRF reveal
#      that verifies against the proposer's key and the previous block hash on
#      each wPoA-governed block (VerifyBlockMinerWPoA); a missing or forged
#      reveal is rejected. So if the chain advances past the setup height with
#      all nodes agreeing on the tip, every accepted block necessarily carried a
#      reveal that verified on every peer. A broken prover or verifier would
#      stall the chain here — this is the core end-to-end signal.
#
#   2. NO FORK. All nodes agree on the block hash at the sampled height.
#
#   3. POSITIVE EVIDENCE. Each node's debug.log shows "VRF reveal OK" lines
#      (peers actually verified reveals) and NO "REJECT ... VRF" / "missing VRF
#      reveal" lines under normal operation.
#
# The cryptographic soundness of the VRF itself (tamper/forgery rejection,
# uniqueness) is covered node-free by the unit suite,
# src/wpoa/test/run_vrf_unit_tests.sh — this test covers the on-chain wiring.
#
# Requires the node to be built first.
#
# Usage:
#   ./functional_test_wpoa_vrf.sh                         # 3 nodes
#   NODES=4 WEIGHTS="100 200 300 400" ./functional_test_wpoa_vrf.sh
#   VRF_BLOCKS=60 SETUP_BLOCKS=30 ./functional_test_wpoa_vrf.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"          # .../src

BINDIR="${BINDIR:-$SRC_DIR}"
NODES="${NODES:-3}"
RPC_TIMEOUT="${RPC_TIMEOUT:-30}"
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-30}"
WEIGHT_TIMEOUT="${WEIGHT_TIMEOUT:-180}"    # seconds to wait for weight convergence
CHAIN="wpoavrf$$"

# wPoA engages at height >= setup-first-blocks; VRF_BLOCKS wPoA-VRF-governed
# blocks are then sampled for the beacon assertions.
SETUP_BLOCKS="${SETUP_BLOCKS:-30}"
VRF_BLOCKS="${VRF_BLOCKS:-40}"
VRF_TIMEOUT="${VRF_TIMEOUT:-300}"          # seconds to accrue the VRF-governed sample

WPOA_ARGS="-enablewpoa=1 -enablewpoavrf=1 -debug=wpoa"

MCUTIL="$BINDIR/multichain-util"
MCD="$BINDIR/multichaind"

declare -a DATADIRS RPCPORTS P2PPORTS WEIGHTS_ARR

fail() {
    echo "FUNCTIONAL TEST FAILED: $*" >&2
    if [ "${KEEP_LOGS:-0}" = "1" ]; then
        for ((i = 0; i < NODES; i++)); do
            echo "==== node $i debug.log (wpoa/vrf/reject) ====" >&2
            grep -iE "wpoa|vrf|reject|verifyblockminer" "${DATADIRS[i]}/$CHAIN/debug.log" 2>/dev/null | tail -n 40 >&2
        done
    fi
    exit 1
}

# ---- parse/derive weights ---------------------------------------------------
if [ -n "${WEIGHTS:-}" ]; then
    read -r -a WEIGHTS_ARR <<< "$WEIGHTS"
fi
for ((i = 0; i < NODES; i++)); do
    if [ -z "${WEIGHTS_ARR[i]:-}" ]; then
        WEIGHTS_ARR[i]=$((100 + i * 100))
    fi
done
TOTAL_WEIGHT=0
for w in "${WEIGHTS_ARR[@]:0:$NODES}"; do TOTAL_WEIGHT=$((TOTAL_WEIGHT + w)); done

# ---- allocate ports & datadirs ----------------------------------------------
BASE_RPC_PORT=$(( 20000 + (RANDOM % 20000) ))
for ((i = 0; i < NODES; i++)); do
    RPCPORTS[i]=$(( BASE_RPC_PORT + i * 10 ))
    P2PPORTS[i]=$(( RPCPORTS[i] + 1 ))
    DATADIRS[i]="$(mktemp -d "${TMPDIR:-/tmp}/wpoa_vrf_node${i}.XXXXXX")"
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

echo "== wPoA Phase 3a VRF beacon functional test =="
echo "  chain=$CHAIN nodes=$NODES weights=(${WEIGHTS_ARR[*]:0:$NODES}) total=$TOTAL_WEIGHT"
echo "  setup-first-blocks=$SETUP_BLOCKS  vrf-sample-blocks=$VRF_BLOCKS"

# ---- helpers -----------------------------------------------------------------
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
    local log=$1
    grep -oE 'grant[[:space:]]+[A-Za-z0-9]{30,40}[[:space:]]+connect' "$log" \
        | head -n1 | awk '{print $2}'
}

node_total() {
    cli "$1" getallweights 2>/dev/null \
        | sed -nE 's/.*"total"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' | head -n1
}
tip_height() { cli "$1" getblockcount 2>/dev/null; }

# ---- node 0: create chain and bootstrap the network -------------------------
"$MCUTIL" create "$CHAIN" -datadir="${DATADIRS[0]}" >/dev/null 2>&1 \
    || fail "multichain-util create failed"

PARAMS="${DATADIRS[0]}/$CHAIN/params.dat"
[ -f "$PARAMS" ] || fail "params.dat not found at $PARAMS"
sed -i -E "s/^(target-block-time[[:space:]]*=[[:space:]]*)[0-9]+/\12/"      "$PARAMS" || true
sed -i -E "s/^(mine-empty-rounds[[:space:]]*=[[:space:]]*)[-0-9.]+/\11000/" "$PARAMS" || true
sed -i -E "s/^(setup-first-blocks[[:space:]]*=[[:space:]]*)[0-9]+/\1$SETUP_BLOCKS/" "$PARAMS" || true

echo "Starting node 0 (seed, weight=${WEIGHTS_ARR[0]})..."
"$MCD" "$CHAIN" -datadir="${DATADIRS[0]}" -port="${P2PPORTS[0]}" -rpcport="${RPCPORTS[0]}" \
       -weight="${WEIGHTS_ARR[0]}" $WPOA_ARGS -daemon >/dev/null 2>&1 \
    || fail "multichaind failed to launch node 0"

wait_for_rpc 0 || fail "RPC did not come up on node 0"

SEED_ADDR="$CHAIN@127.0.0.1:${P2PPORTS[0]}"
echo "  seed node address: $SEED_ADDR"

bootstrap_node() {
    local i=$1
    local weight=${WEIGHTS_ARR[i]}
    local log="${DATADIRS[i]}/node.log"

    echo "Bootstrapping node $i (weight=$weight)..."
    "$MCD" "$SEED_ADDR" -datadir="${DATADIRS[i]}" -port="${P2PPORTS[i]}" -rpcport="${RPCPORTS[i]}" \
           -weight="$weight" $WPOA_ARGS -daemon > "$log" 2>&1

    for ((t = 0; t < 5; t++)); do
        if cli "$i" getinfo >/dev/null 2>&1; then
            echo "  node $i joined directly (no grant needed)"
            return 0
        fi
        sleep 1
    done

    local addr
    addr="$(get_node_address_from_log "$log")"
    if [ -z "$addr" ]; then
        cat "$log" >&2
        fail "could not determine wallet address for node $i (no grant hint in log)"
    fi
    echo "  node $i address: $addr -> granting permissions from node 0"

    if ! cli 0 grant "$addr" connect,send,receive,mine >/dev/null 2>&1; then
        fail "grant connect,send,receive,mine failed for node $i ($addr)"
    fi
    cli 0 grant "$addr" wpoa-weights.write >/dev/null 2>&1 || true

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
    bootstrap_node "$i" || fail "node $i refused to join (see ${DATADIRS[i]}/node.log)"
    wait_for_rpc "$i" || fail "RPC did not come up on node $i"
done

# ---- wait for weight convergence on all nodes -------------------------------
echo "Waiting for aggregate weight $TOTAL_WEIGHT on ALL $NODES node(s) (timeout ${WEIGHT_TIMEOUT}s)..."
deadline=$(( SECONDS + WEIGHT_TIMEOUT ))
converged=0
while [ "$SECONDS" -lt "$deadline" ]; do
    all_ok=1
    for ((i = 0; i < NODES; i++)); do
        [ "$(node_total "$i")" = "$TOTAL_WEIGHT" ] || { all_ok=0; break; }
    done
    if [ "$all_ok" = "1" ]; then converged=1; break; fi
    sleep 3
done
[ "$converged" = "1" ] || fail "aggregate weight $TOTAL_WEIGHT not confirmed on all nodes within ${WEIGHT_TIMEOUT}s"
echo "Aggregate weight $TOTAL_WEIGHT confirmed across all $NODES node(s)."

# ---- drive the chain through VRF-governed heights ---------------------------
cur="$(tip_height 0)"; cur="${cur:-0}"
SAMPLE_START=$(( cur + 1 ))
[ "$SAMPLE_START" -lt "$SETUP_BLOCKS" ] && SAMPLE_START=$SETUP_BLOCKS
SAMPLE_END=$(( SAMPLE_START + VRF_BLOCKS - 1 ))

echo
echo "== driving the chain to height $SAMPLE_END under the VRF beacon (timeout ${VRF_TIMEOUT}s) =="
deadline=$(( SECONDS + VRF_TIMEOUT ))
last_h=-1; stall_since=$SECONDS
while [ "$SECONDS" -lt "$deadline" ]; do
    h="$(tip_height 0)"; h="${h:-0}"
    if [ "$h" -ge "$SAMPLE_END" ]; then break; fi
    if [ "$h" -ne "$last_h" ]; then last_h=$h; stall_since=$SECONDS
        [ $(( h % 20 )) -eq 0 ] && echo "    height $h / $SAMPLE_END"
    elif [ $(( SECONDS - stall_since )) -ge 60 ]; then
        echo "    WARNING: chain stalled at height $h for 60s (VRF verification failing?)"
        tail -n 8 "${DATADIRS[0]}/$CHAIN/debug.log" 2>/dev/null | grep -iE "wpoa|vrf" || true
        stall_since=$SECONDS
    fi
    sleep 2
done

h="$(tip_height 0)"; h="${h:-0}"
[ "$h" -ge "$SAMPLE_END" ] || fail "chain only reached height $h of $SAMPLE_END within ${VRF_TIMEOUT}s (beacon likely stalling block acceptance)"
echo "  chain advanced to height $h under mandatory VRF verification."

# ---- assertion 2: no fork ----------------------------------------------------
h0_at_end="$(cli 0 getblockhash "$SAMPLE_END" 2>/dev/null)"
[ -n "$h0_at_end" ] || fail "could not read node 0 block hash at $SAMPLE_END"
for ((i = 1; i < NODES; i++)); do
    hi_at_end="$(cli "$i" getblockhash "$SAMPLE_END" 2>/dev/null)"
    if [ -n "$hi_at_end" ] && [ "$hi_at_end" != "$h0_at_end" ]; then
        fail "fork detected: node $i block $SAMPLE_END = $hi_at_end != node 0 $h0_at_end"
    fi
done
echo "  all nodes agree on the chain at height $SAMPLE_END (no fork) — reveals verified network-wide."

# ---- assertion 3: positive/negative evidence in the logs --------------------
total_ok=0
total_reject=0
for ((i = 0; i < NODES; i++)); do
    dbg="${DATADIRS[i]}/$CHAIN/debug.log"
    # grep -c already prints 0 when there are no matches; capture and default to 0
    # only if the file is missing (avoids a double-printed count breaking arithmetic).
    ok=$(grep -c "VRF reveal OK" "$dbg" 2>/dev/null); ok=${ok:-0}
    rej=$(grep -Ec "REJECT.*VRF|missing VRF reveal|invalid VRF reveal" "$dbg" 2>/dev/null); rej=${rej:-0}
    echo "  node $i: VRF-reveal-OK=$ok  VRF-rejections=$rej"
    total_ok=$(( total_ok + ok ))
    total_reject=$(( total_reject + rej ))
done

[ "$total_reject" -eq 0 ] || fail "nodes logged $total_reject VRF rejection(s) under honest operation"
[ "$total_ok" -gt 0 ] || fail "no 'VRF reveal OK' evidence found in any node's debug.log — verification path may not be exercised"

echo
echo "  VRF beacon evidence: $total_ok verified reveals logged across nodes, 0 rejections."
echo "FUNCTIONAL TEST PASSED (VRF beacon: reveals produced, verified network-wide, chain live and fork-free over $VRF_BLOCKS blocks)."
exit 0
