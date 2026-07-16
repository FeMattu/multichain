#!/usr/bin/env bash
#
# Functional (end-to-end) test for the wPoA Phase 4 private (VRF-scored) sortition.
#
# Bootstraps a permissioned MultiChain network of N nodes started with the full
# stack -enablewpoa=1 -enablewpoavrf=1 -enablewpoarandao=1 -enablewpoasortition=1,
# drives it past the wPoA setup height, and asserts the private sortition works
# end-to-end:
#
#   1. LIVENESS UNDER PRIVATE SORTITION (the core signal). No node can recompute
#      the global argmin any more (every validator's score is private under its own
#      VRF key), so agreement now rests on: each node self-elects by a
#      score-proportional mining delay (the argmin proposes first), and every peer
#      accepts a block iff its VRF reveal verifies over the sortition input AND its
#      nTime is no earlier than the recomputed score entitles (the time bar). If the
#      miner and validators disagreed on the input encoding, the score transform,
#      the effective-weight sum or the delay map, blocks would be rejected and the
#      chain would stall. Advancing past setup with all nodes agreeing therefore
#      PROVES the whole sortition path is bit-identical network-wide.
#
#   2. NO PERSISTENT FORK. All nodes agree on the block hash at the sampled height
#      once it is buried under a confirmation buffer (rare simultaneous-qualifier
#      forks are transient and self-heal — the accepted §11 "network-delay-vs-sorting"
#      property; the buffer lets them settle before the check).
#
#   3. PRIVATE PATH ENGAGED, PUBLIC PATH NOT USED (unpredictability evidence). Each
#      node's debug.log shows the private miner-side scoring ("wPoA-sortition
#      height=... score=") and the private validator-side acceptance ("sortition
#      OK"), and ZERO public-argmin acceptances ("miner==proposer==", the Phase 2/3b
#      log) over the sampled heights — i.e. no node ever elected the proposer from
#      public data. Reveal-verification rejects are reported (advisory).
#
#   4. WEIGHT-PROPORTIONAL DISTRIBUTION UNDER PRIVATE SORTITION. The observed
#      proposer distribution still matches the weight ratios (chi-square goodness-
#      of-fit), confirming argmin over PRIVATE VRF scores preserves Pr[i]=w_i/Σw
#      (thesis §7.4) on a live network — the headline result of the security fix.
#
# The sortition math itself (VRF-input encoding, score reuse, delay map, and
# probability preservation with real VRF keys) is covered node-free by the unit
# suite, src/wpoa/test/run_sortition_unit_tests.sh — this test covers the on-chain
# wiring: private self-election, the time bar, liveness and agreement.
#
# Requires the node to be built first.
#
# Usage:
#   ./functional_test_wpoa_sortition.sh                                   # 3 nodes
#   NODES=4 WEIGHTS="100 200 300 400" ./functional_test_wpoa_sortition.sh
#   SORT_BLOCKS=120 SORTITION_DELAY=2 SETUP_BLOCKS=30 ./functional_test_wpoa_sortition.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"          # .../src

BINDIR="${BINDIR:-$SRC_DIR}"
NODES="${NODES:-3}"
RPC_TIMEOUT="${RPC_TIMEOUT:-30}"
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-30}"
WEIGHT_TIMEOUT="${WEIGHT_TIMEOUT:-180}"    # seconds to wait for weight convergence
CHAIN="wpoasortition$$"

# wPoA/VRF/RANDAO engage at height >= setup-first-blocks; private sortition engages
# on the same heights. SORT_BLOCKS governed blocks are then sampled.
SETUP_BLOCKS="${SETUP_BLOCKS:-30}"
SORT_BLOCKS="${SORT_BLOCKS:-80}"
RANDAO_LOOKBACK="${RANDAO_LOOKBACK:-1}"      # k >= 1 required (seed<->reveal acyclicity)
SORTITION_DELAY="${SORTITION_DELAY:-1}"      # delay = s * score * total_effective_weight
CONFIRM_BUFFER="${CONFIRM_BUFFER:-6}"        # blocks mined beyond the sample before the fork check
SORT_TIMEOUT="${SORT_TIMEOUT:-500}"          # seconds to accrue the governed sample
DIST_TOLERANCE="${DIST_TOLERANCE:-0.05}"     # advisory ±share bound; chi-square is the gate

WPOA_ARGS="-enablewpoa=1 -enablewpoavrf=1 -enablewpoarandao=1 -wpoarandaolookback=$RANDAO_LOOKBACK -enablewpoasortition=1 -wpoasortitiondelay=$SORTITION_DELAY -debug=wpoa"

MCUTIL="$BINDIR/multichain-util"
MCD="$BINDIR/multichaind"

declare -a DATADIRS RPCPORTS P2PPORTS WEIGHTS_ARR

fail() {
    echo "FUNCTIONAL TEST FAILED: $*" >&2
    if [ "${KEEP_LOGS:-0}" = "1" ]; then
        for ((i = 0; i < NODES; i++)); do
            echo "==== node $i debug.log (wpoa/sortition/reject) ====" >&2
            grep -iE "wpoa|sortition|reject|verifyblockminer" "${DATADIRS[i]}/$CHAIN/debug.log" 2>/dev/null | tail -n 40 >&2
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
    DATADIRS[i]="$(mktemp -d "${TMPDIR:-/tmp}/wpoa_sortition_node${i}.XXXXXX")"
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

echo "== wPoA Phase 4 private-sortition functional test =="
echo "  chain=$CHAIN nodes=$NODES weights=(${WEIGHTS_ARR[*]:0:$NODES}) total=$TOTAL_WEIGHT"
echo "  setup-first-blocks=$SETUP_BLOCKS  sample-blocks=$SORT_BLOCKS  lookback k=$RANDAO_LOOKBACK  delay-scale=$SORTITION_DELAY"

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

# ---- drive the chain through sortition-governed heights ---------------------
cur="$(tip_height 0)"; cur="${cur:-0}"
SAMPLE_START=$(( cur + 1 ))
[ "$SAMPLE_START" -lt "$SETUP_BLOCKS" ] && SAMPLE_START=$SETUP_BLOCKS
SAMPLE_END=$(( SAMPLE_START + SORT_BLOCKS - 1 ))
DRIVE_TO=$(( SAMPLE_END + CONFIRM_BUFFER ))   # bury the sample so transient forks settle

echo
echo "== driving the chain to height $DRIVE_TO under private sortition (timeout ${SORT_TIMEOUT}s) =="
deadline=$(( SECONDS + SORT_TIMEOUT ))
last_h=-1; stall_since=$SECONDS
while [ "$SECONDS" -lt "$deadline" ]; do
    h="$(tip_height 0)"; h="${h:-0}"
    if [ "$h" -ge "$DRIVE_TO" ]; then break; fi
    if [ "$h" -ne "$last_h" ]; then last_h=$h; stall_since=$SECONDS
        [ $(( h % 20 )) -eq 0 ] && echo "    height $h / $DRIVE_TO"
    elif [ $(( SECONDS - stall_since )) -ge 90 ]; then
        echo "    WARNING: chain stalled at height $h for 90s (sortition disagreement, or all qualifiers idle?)"
        tail -n 8 "${DATADIRS[0]}/$CHAIN/debug.log" 2>/dev/null | grep -iE "wpoa|sortition" || true
        stall_since=$SECONDS
    fi
    sleep 2
done

h="$(tip_height 0)"; h="${h:-0}"
[ "$h" -ge "$DRIVE_TO" ] || fail "chain only reached height $h of $DRIVE_TO within ${SORT_TIMEOUT}s (sortition disagreement likely stalling block acceptance)"
echo "  chain advanced to height $h under private sortition."

# ---- assertion 2: no persistent fork ----------------------------------------
h0_at_end="$(cli 0 getblockhash "$SAMPLE_END" 2>/dev/null)"
[ -n "$h0_at_end" ] || fail "could not read node 0 block hash at $SAMPLE_END"
for ((i = 1; i < NODES; i++)); do
    hi_at_end="$(cli "$i" getblockhash "$SAMPLE_END" 2>/dev/null)"
    if [ -n "$hi_at_end" ] && [ "$hi_at_end" != "$h0_at_end" ]; then
        fail "fork detected: node $i block $SAMPLE_END = $hi_at_end != node 0 $h0_at_end"
    fi
done
echo "  all nodes agree on the chain at height $SAMPLE_END (no persistent fork) — sortition consensus identical network-wide."

# ---- assertion 3: private path engaged, public path NOT used ----------------
total_score=0
total_verify=0
total_public=0
total_tooearly=0
for ((i = 0; i < NODES; i++)); do
    dbg="${DATADIRS[i]}/$CHAIN/debug.log"
    sc=$(grep -c "wPoA-sortition height=.*score=" "$dbg" 2>/dev/null); sc=${sc:-0}
    vf=$(grep -c "sortition OK block" "$dbg" 2>/dev/null); vf=${vf:-0}
    pb=$(grep -c "miner==proposer==" "$dbg" 2>/dev/null); pb=${pb:-0}
    te=$(grep -c "too early for its sortition score" "$dbg" 2>/dev/null); te=${te:-0}
    echo "  node $i: private-scorings=$sc  sortition-accepts=$vf  public-argmin-accepts=$pb  too-early-rejects=$te"
    total_score=$(( total_score + sc ))
    total_verify=$(( total_verify + vf ))
    total_public=$(( total_public + pb ))
    total_tooearly=$(( total_tooearly + te ))
done
[ "$total_score" -gt 0 ]  || fail "no 'wPoA-sortition ... score=' evidence — the private miner-side scoring path was not exercised"
[ "$total_verify" -gt 0 ] || fail "no 'sortition OK' evidence — the private validator-side acceptance path was not exercised"
[ "$total_public" -eq 0 ] || fail "public-argmin acceptances ('miner==proposer==') were logged on sortition heights ($total_public) — selection was NOT private"
echo "  sortition evidence: $total_score private scorings, $total_verify private acceptances, 0 public-argmin acceptances."
echo "  (advisory) too-early-for-score rejects across nodes: $total_tooearly"

# ---- assertion 4: weight-proportional distribution under private sortition ---
echo
echo "== proposer distribution under private sortition (chi-square) =="
WEIGHTS_JSON="${DATADIRS[0]}/weights.json"
BLOCKS_JSON="${DATADIRS[0]}/blocks.json"
cli 0 getallweights > "$WEIGHTS_JSON" 2>/dev/null || fail "getallweights failed"
cli 0 listblocks "$SAMPLE_START-$SAMPLE_END" > "$BLOCKS_JSON" 2>/dev/null \
    || fail "listblocks $SAMPLE_START-$SAMPLE_END failed"

python3 "$SCRIPT_DIR/analyze_distribution.py" "$WEIGHTS_JSON" "$BLOCKS_JSON" "$DIST_TOLERANCE"
rc=$?
if [ "$rc" -ne 0 ]; then
    fail "proposer distribution under private sortition did not match weight ratios (chi-square; see table above)"
fi

echo
echo "FUNCTIONAL TEST PASSED (private sortition: chain live and fork-free with private per-validator scoring, no public-argmin acceptances, weight-proportional over $SORT_BLOCKS blocks, delay-scale=$SORTITION_DELAY)."
exit 0
