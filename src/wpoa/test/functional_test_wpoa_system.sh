#!/usr/bin/env bash
#
# wPoA SYSTEM-LEVEL functional test — one network, many checks.
#
# Replaces the former per-feature functional tests (multinode / vrf / randao /
# sortition), each of which bootstrapped its OWN multi-node network and waited
# for its OWN block warm-up. Because the private-sortition configuration already
# runs the FULL stack (weights + VRF + RANDAO + sortition) together, we start a
# SINGLE full-stack network, wait for weight convergence and a block warm-up
# ONCE, and then run every feature check against that one shared run.
#
# Phases:
#   1. setup       — create the chain and bootstrap N nodes with the full stack
#   2. warm-up     — wait for weight convergence, then mine past the sample window
#   3. checks      — run all check_* verifications on the SAME run:
#                      check_weight                 aggregate weight registry
#                      check_stream_permissions     weights closed / malus open
#                      check_malus                  Psi inert, false evidence refused
#                      check_multinode_consistency  no persistent fork
#                      check_vrf                    reveals carried & verified, 0 rejects
#                      check_randao                 beacon seed derived, 0 fallback folds
#                      check_sortition              private path engaged, 0 public argmin
#                      check_distribution           weight-proportional (chi-square)
#   4. teardown    — stop and wipe every node
#
# Optional, opt-in second scenario (INCLUDE_PUBLIC_SELECTOR=1): a SEPARATE short
# run with sortition OFF (VRF+RANDAO only), the one regime that cannot be
# observed on the full-stack run because block acceptance is regime-exclusive
# (sortition replaces the public argmin path). It reuses the same library, so no
# bootstrap code is duplicated. Off by default → the default cost is one network.
#
# Requires the node to be built first (./autogen.sh && ./configure && make).
#
# Usage:
#   ./functional_test_wpoa_system.sh
#   NODES=4 WEIGHTS="100 200 300 400" ./functional_test_wpoa_system.sh
#   QUICK=1 ./functional_test_wpoa_system.sh                  # smaller sample / budgets
#   INCLUDE_PUBLIC_SELECTOR=1 ./functional_test_wpoa_system.sh
#   NO_WARN=1 ./functional_test_wpoa_system.sh                # skip the warning banner
#
# Key env (see also functional_lib.sh): NODES, WEIGHTS, SETUP_BLOCKS,
#   SAMPLE_BLOCKS, CONFIRM_BUFFER, DRIVE_TIMEOUT, RANDAO_LOOKBACK,
#   SORTITION_DELAY, DIST_TOLERANCE, BINDIR, KEEP_LOGS.
#
# Exit code: 0 iff every CRITICAL check passed; non-zero otherwise.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"          # .../src
# shellcheck source=functional_lib.sh
. "$SCRIPT_DIR/functional_lib.sh"

# ---- tunables (QUICK shrinks the sample & budgets) --------------------------
QUICK="${QUICK:-0}"
NO_WARN="${NO_WARN:-0}"
BINDIR="${BINDIR:-$SRC_DIR}"
NODES="${NODES:-3}"
SETUP_BLOCKS="${SETUP_BLOCKS:-30}"
RANDAO_LOOKBACK="${RANDAO_LOOKBACK:-1}"     # k in seed[n+1]=H(R_tot[n-k]‖h[n]‖n+1)
SORTITION_DELAY="${SORTITION_DELAY:-1}"     # delay = s * score * total_effective_weight
DIST_TOLERANCE="${DIST_TOLERANCE:-0.05}"    # advisory ±share bound; chi-square is the gate
CONFIRM_BUFFER="${CONFIRM_BUFFER:-6}"       # blocks mined beyond the sample before the fork check
if [ "$QUICK" = "1" ]; then
    SAMPLE_BLOCKS="${SAMPLE_BLOCKS:-30}"
    DRIVE_TIMEOUT="${DRIVE_TIMEOUT:-300}"
else
    SAMPLE_BLOCKS="${SAMPLE_BLOCKS:-80}"
    DRIVE_TIMEOUT="${DRIVE_TIMEOUT:-500}"
fi
export BINDIR NODES SETUP_BLOCKS   # consumed by functional_lib.sh

# -enablewpoa is the master switch: it turns on the whole stack (weights + selection
# + VRF + RANDAO + sortition). The numeric knobs (lookback, delay) are still passed
# explicitly. Specific -enablewpoa* flags would override the master per phase.
FULL_STACK_ARGS="-enablewpoa=1 -wpoarandaolookback=$RANDAO_LOOKBACK -wpoasortitiondelay=$SORTITION_DELAY -debug=wpoa"

# Sample window, filled in after warm-up.
SAMPLE_START=0
SAMPLE_END=0

trap fl_teardown EXIT

# ---- warning banner ---------------------------------------------------------
print_warning() {
    [ "$NO_WARN" = "1" ] && return 0
    cat >&2 <<'EOF'

============================================================================
  ⚠  wPoA SYSTEM FUNCTIONAL TEST — please read
============================================================================
  * This drives a REAL multi-node MultiChain network and mines a window of
    blocks. It can take several minutes.
  * It is now OPTIMIZED to reuse a SINGLE network setup and a SINGLE block
    warm-up for every feature check (instead of re-bootstrapping per feature).
  * Even so, it exercises a live distributed/blockchain system, so a run may
    occasionally stall or wait longer than usual (slow weight convergence, a
    transient simultaneous-qualifier fork, a node failing to join). The
    probability is LOW but real — a property of the system under test, not a
    defect in this script.
  * Tip: QUICK=1 uses a smaller sample for a faster pass.
============================================================================

EOF
    if [ -t 1 ] && [ "${FUNCTIONAL_YES:-0}" != "1" ]; then
        echo "  Starting in 3s — press Ctrl-C to abort." >&2; sleep 3
    fi
}

################################################################################
# CHECKS — each reads the shared, already-warmed run. They never start a node.
################################################################################

# Aggregate weight registry converged to Σ w_i on every node.
check_weight() {
    local i ok=0 bad=0
    for ((i = 0; i < NODES; i++)); do
        if [ "$(fl_node_total "$i")" = "$FL_TOTAL_WEIGHT" ]; then ok=$((ok+1)); else bad=$((bad+1)); fi
    done
    fl_log "getallweights (node 0):"; fl_cli 0 getallweights | sed 's/^/    /'
    fl_assert_eq "$ok" "$NODES" "nodes reporting aggregate weight $FL_TOTAL_WEIGHT"
    fl_assert_zero "$bad" "nodes with a wrong aggregate"
}

# The two registries must carry OPPOSITE write policies (Def. 5.16 / Def. 5.17):
# wpoa-weights closed, so only authorized publishers can move a validator's
# weight; wpoa-weights-malus open, so anyone can accuse — safety there comes from
# every node re-deriving the evidence, not from restricting who may speak.
check_stream_permissions() {
    local w_write m_write unauth
    w_write="$(fl_stream_write_restricted 0 wpoa-weights)"
    m_write="$(fl_stream_write_restricted 0 wpoa-weights-malus)"
    fl_log "wpoa-weights       restrict.write = $w_write (expect true  = closed)"
    fl_log "wpoa-weights-malus restrict.write = $m_write (expect false = open)"
    fl_assert_eq "$w_write" "true"  "wpoa-weights is write-restricted"
    fl_assert_eq "$m_write" "false" "wpoa-weights-malus is open to any publisher"

    # And the restriction must actually bite: an address with no write permission
    # on wpoa-weights cannot publish a weight record, but can still report.
    unauth="$(fl_cli 0 getnewaddress 2>/dev/null | tr -d '"[:space:]')"
    if [ -z "$unauth" ]; then
        fl_bad "could not create an unpermitted address"
        return
    fi
    fl_cli 0 grant "$unauth" send,receive >/dev/null 2>&1
    if fl_cli 0 publishfrom "$unauth" wpoa-weights "$unauth" '{"json":{"node_address":"'"$unauth"'","weight":999999}}' >/dev/null 2>&1; then
        fl_bad "an address WITHOUT wpoa-weights.write managed to publish a weight"
    else
        fl_ok "an address without wpoa-weights.write cannot publish a weight"
    fi
    if fl_cli 0 publishfrom "$unauth" wpoa-weights-malus "$unauth" '{"json":{"kind":"delay","node_address":"'"$unauth"'","height":1,"blocks":["ff"]}}' >/dev/null 2>&1; then
        fl_ok "any address can publish to the open wpoa-weights-malus stream"
    else
        fl_bad "an ordinary address could NOT publish to the open malus stream"
    fi
}

# The malus mechanism is inert on honest behaviour, and the Valid() predicate
# refuses evidence that does not hold — the property that makes the open stream
# safe (a false report changes no weight anywhere).
check_malus() {
    local i addr h bh bad=0 psi eff w
    addr="$(fl_cli 0 getallweights 2>/dev/null | sed -nE 's/^[[:space:]]*"([A-Za-z0-9]{30,40})"[[:space:]]*:.*/\1/p' | head -n1)"
    [ -n "$addr" ] || { fl_bad "could not read a validator address"; return; }

    # Honest validator: no accumulated malus, Psi = 1, w_eff = w.
    psi="$(fl_cli 0 getnodemalus "$addr" 2>/dev/null | sed -nE 's/.*"psi"[[:space:]]*:[[:space:]]*([0-9.]+).*/\1/p' | head -n1)"
    w="$(fl_cli 0 getnodemalus "$addr" 2>/dev/null | sed -nE 's/.*"weight"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' | head -n1)"
    eff="$(fl_cli 0 getnodemalus "$addr" 2>/dev/null | sed -nE 's/.*"effective"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' | head -n1)"
    fl_log "getnodemalus $addr -> psi=$psi weight=$w effective=$eff"
    fl_assert_eq "$psi" "1"   "honest validator carries Psi = 1"
    fl_assert_eq "$eff" "$w"  "honest validator's effective weight equals its raw weight"

    # False / malformed evidence must be refused locally on EVERY node, so no
    # report reaches the chain and no weight moves.
    h="$SAMPLE_END"
    bh="$(fl_blockhash_at 0 "$h")"
    [ -n "$bh" ] || { fl_bad "could not read a block hash at $h"; return; }
    for ((i = 0; i < NODES; i++)); do
        # an honest block is not a delay violation
        fl_cli "$i" reportmalus delay "$addr" "$h" "$bh" >/dev/null 2>&1 && bad=$((bad+1))
        # the same block twice is not an equivocation
        fl_cli "$i" reportmalus equiv "$addr" "$h" "$bh" "$bh" >/dev/null 2>&1 && bad=$((bad+1))
        # a block nobody has ever seen proves nothing
        fl_cli "$i" reportmalus delay "$addr" "$h" \
            "00000000000000000000000000000000000000000000000000000000deadbeef" >/dev/null 2>&1 && bad=$((bad+1))
    done
    fl_assert_zero "$bad" "false or malformed malus reports accepted (must be 0)"
}

# All nodes agree on the block hash at SAMPLE_END (buried under CONFIRM_BUFFER).
check_multinode_consistency() {
    local ref i hi mism=0
    ref="$(fl_blockhash_at 0 "$SAMPLE_END")"
    [ -n "$ref" ] || { fl_bad "could not read node 0 block hash at $SAMPLE_END"; return; }
    fl_log "reference block $SAMPLE_END @ node 0 = $ref"
    for ((i = 1; i < NODES; i++)); do
        hi="$(fl_blockhash_at "$i" "$SAMPLE_END")"
        if [ -n "$hi" ] && [ "$hi" != "$ref" ]; then
            fl_bad "fork: node $i block $SAMPLE_END = $hi"; mism=$((mism+1))
        fi
    done
    fl_assert_zero "$mism" "nodes disagreeing on the chain at height $SAMPLE_END"
}

# VRF reveals were carried and verified network-wide; the prover never failed and
# nothing was rejected for a VRF reason. Under the full stack the verify is logged
# by the sortition path (see check_sortition); here we assert the VRF invariants.
check_vrf() {
    local prover_fail vrf_reject
    prover_fail=$(fl_logcount_all "wPoA-VRF: failed to produce VRF reveal")
    vrf_reject=$(fl_logcount_all "REJECT.*(missing|invalid) VRF reveal|missing VRF reveal \(sortition\)|invalid or missing VRF reveal over the sortition input")
    fl_log "per-node VRF rejections:"; fl_logcount_per_node "REJECT.*VRF|missing VRF reveal|invalid VRF reveal"
    fl_assert_zero "$prover_fail" "miner-side VRF prover failures"
    fl_assert_zero "$vrf_reject"  "VRF-reveal rejections under honest operation"
    # Liveness past setup already proves every accepted governed block carried a
    # reveal that verified (mandatory verification); recorded here for the report.
    fl_log "chain advanced past setup under mandatory VRF verification: height $(fl_tip_height 0)"
}

# RANDAO beacon seed was derived on the governed heights and no governed reveal
# was missing (0 fallback folds).
check_randao() {
    local seeds folds
    seeds=$(fl_logcount_all "\[wPoA-RANDAO\] seed for height=")
    folds=$(fl_logcount_all "reveal unavailable")
    fl_log "per-node RANDAO seed derivations:"; fl_logcount_per_node "\[wPoA-RANDAO\] seed for height="
    fl_assert_gt0  "$seeds" "RANDAO beacon-seed derivations logged"
    fl_assert_zero "$folds" "RANDAO fallback folds (a governed reveal could not be read)"
}

# Private sortition governed selection: private scorings + private acceptances
# occurred, and ZERO blocks were accepted via the public argmin path.
check_sortition() {
    local score verify public tooearly
    score=$(fl_logcount_all "wPoA-sortition height=.*score=")
    verify=$(fl_logcount_all "sortition OK block")
    public=$(fl_logcount_all "miner==proposer==")
    tooearly=$(fl_logcount_all "too early for its sortition score")
    fl_log "private scorings=$score  private acceptances=$verify  public-argmin=$public  too-early=$tooearly"
    fl_assert_gt0  "$score"  "private miner-side scorings"
    fl_assert_gt0  "$verify" "private validator-side acceptances (each verified a VRF reveal)"
    fl_assert_zero "$public" "public-argmin acceptances on sortition heights (selection must be private)"
    fl_log "(advisory) too-early-for-score rejects across nodes: $tooearly"
}

# Observed proposer distribution matches the weight ratios (chi-square) over the
# shared sample window.
check_distribution() {
    local wj="${FL_DATADIRS[0]}/weights.json" bj="${FL_DATADIRS[0]}/blocks.json"
    fl_cli 0 getallweights > "$wj" 2>/dev/null || { fl_bad "getallweights failed"; return; }
    fl_cli 0 listblocks "$SAMPLE_START-$SAMPLE_END" > "$bj" 2>/dev/null || { fl_bad "listblocks failed"; return; }
    if python3 "$SCRIPT_DIR/analyze_distribution.py" "$wj" "$bj" "$DIST_TOLERANCE"; then
        fl_ok "proposer distribution matches weight ratios (chi-square) over $SAMPLE_BLOCKS blocks"
    else
        fl_bad "proposer distribution did not match weight ratios within tolerance (see table above)"
    fi
}

# ---- optional independent regime: public argmin selection (sortition OFF) ----
# The one scenario the full-stack run cannot observe. Uses the same library.
scenario_public_selector() {
    fl_phase "OPTIONAL SCENARIO: public-selector regime (sortition OFF)"
    # Master on, but sortition explicitly OFF (specific flag overrides the master):
    # weights + selection + VRF + RANDAO with the public argmin selection path.
    local pub_args="-enablewpoa=1 -enablewpoasortition=0 -wpoarandaolookback=$RANDAO_LOOKBACK -debug=wpoa"
    fl_start_network "$pub_args"
    fl_wait_weight_convergence || fl_die "weights did not converge (public-selector scenario)"
    local cur; cur="$(fl_tip_height 0)"; cur="${cur:-0}"
    SAMPLE_START=$(( cur + 1 )); [ "$SAMPLE_START" -lt "$SETUP_BLOCKS" ] && SAMPLE_START=$SETUP_BLOCKS
    SAMPLE_END=$(( SAMPLE_START + SAMPLE_BLOCKS - 1 ))
    fl_drive_to_height $(( SAMPLE_END + CONFIRM_BUFFER )) "$DRIVE_TIMEOUT" "public-selection stall" \
        || fl_die "public-selector scenario did not reach height $SAMPLE_END"

    fl_check_begin "public_vrf_reveal_ok" 1
        local vrf_ok public
        vrf_ok=$(fl_logcount_all "VRF reveal OK")
        public=$(fl_logcount_all "miner==proposer==")
        fl_assert_gt0 "$vrf_ok" "standalone 'VRF reveal OK' verifications (non-sortition path)"
        fl_assert_gt0 "$public" "public argmin acceptances ('miner==proposer==')"
    fl_check_end || true

    fl_check_begin "public_distribution" 1
        check_distribution
    fl_check_end || true

    fl_teardown
}

################################################################################
# ORCHESTRATION
################################################################################
print_warning

fl_phase "PHASE 1/4 — setup (single full-stack network)"
fl_require_binaries
fl_start_network "$FULL_STACK_ARGS"

fl_phase "PHASE 2/4 — warm-up (once)"
fl_wait_weight_convergence || fl_die "aggregate weight not confirmed on all nodes within ${WEIGHT_TIMEOUT}s"
cur="$(fl_tip_height 0)"; cur="${cur:-0}"
SAMPLE_START=$(( cur + 1 )); [ "$SAMPLE_START" -lt "$SETUP_BLOCKS" ] && SAMPLE_START=$SETUP_BLOCKS
SAMPLE_END=$(( SAMPLE_START + SAMPLE_BLOCKS - 1 ))
DRIVE_TO=$(( SAMPLE_END + CONFIRM_BUFFER ))
fl_log "sample window: heights $SAMPLE_START..$SAMPLE_END ($SAMPLE_BLOCKS blocks); driving to $DRIVE_TO"
fl_drive_to_height "$DRIVE_TO" "$DRIVE_TIMEOUT" "full-stack stall (sortition/seed disagreement, or all qualifiers idle?)" \
    || fl_die "chain did not reach height $DRIVE_TO within ${DRIVE_TIMEOUT}s"

fl_phase "PHASE 3/4 — feature checks (shared run)"
fl_check_begin "weight"                1; check_weight;                fl_check_end || true
fl_check_begin "stream_permissions"    1; check_stream_permissions;    fl_check_end || true
fl_check_begin "malus"                 1; check_malus;                 fl_check_end || true
fl_check_begin "multinode_consistency" 1; check_multinode_consistency; fl_check_end || true
fl_check_begin "vrf"                   1; check_vrf;                   fl_check_end || true
fl_check_begin "randao"                1; check_randao;                fl_check_end || true
fl_check_begin "sortition"             1; check_sortition;             fl_check_end || true
fl_check_begin "distribution"          1; check_distribution;          fl_check_end || true

fl_phase "PHASE 4/4 — teardown"
fl_teardown

# ---- optional independent regime --------------------------------------------
if [ "${INCLUDE_PUBLIC_SELECTOR:-0}" = "1" ]; then
    scenario_public_selector
fi

# ---- verdict ----------------------------------------------------------------
if fl_check_summary; then
    echo
    echo "SYSTEM FUNCTIONAL TEST PASSED (single network; weight, stream permissions, malus, consistency, VRF, RANDAO, sortition, distribution)."
    exit 0
fi
echo
echo "SYSTEM FUNCTIONAL TEST FAILED." >&2
exit 1
