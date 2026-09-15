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
#                                                    (both malus families)
#                      check_multinode_consistency  no persistent fork
#                      check_diversity_spacing      mining-diversity inert under wPoA
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
# A THIRD scenario (scenario_diversity_spacing) runs automatically when — and only
# when — NODES < 4: the native mining-diversity spacing is arithmetically inert below
# 4 miners, so the shared run cannot express a validator winning two consecutive wPoA
# rounds. It is a 4-miner network with skewed weights, and it is the targeted
# regression for that bug. Suppress with SKIP_DIVERSITY_SCENARIO=1; at NODES>=4 it is
# skipped because check_diversity_spacing already covered the case in the shared run.
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
#   SORTITION_DELTA, SORTITION_LAMBDA, DIST_TOLERANCE, BINDIR, KEEP_LOGS,
#   SKIP_DIVERSITY_SCENARIO.
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
# Band half-width as a fraction of target-block-time. The protocol default is 0.5,
# which on a normal chain (target-block-time 15s) gives Delta_max = 7.5s and a ~3.8s
# median spread between the first and second candidate. This test compresses
# target-block-time to TARGET_BLOCK_TIME (2s) so a run finishes quickly, and the band
# scales WITH the target: at delta=0.5 that leaves only Delta_max = 1s and a ~500ms
# spread, comparable to the jitter of a busy loopback network — so the timer race
# starts turning on jitter instead of on score (Prop. 5.17) and the observed
# distribution drifts. delta is raised here to restore the absolute spread the
# compressed target would otherwise lose; it is a property of the test's tight
# target-block-time, not of the protocol default.
SORTITION_DELTA="${SORTITION_DELTA:-0.9}"
SORTITION_LAMBDA="${SORTITION_LAMBDA:-0}"   # global delay-feedback gain (0 = off)
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
FULL_STACK_ARGS="-enablewpoa=1 -wpoarandaolookback=$RANDAO_LOOKBACK -wpoasortitiondelta=$SORTITION_DELTA -wpoasortitionlambda=$SORTITION_LAMBDA -debug=wpoa"

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

    # ---- published-data integrity kinds ----------------------------------
    # The second family of violations: what a node WROTE to a stream the weight
    # pipeline reads, rather than how it behaved producing a block. Evidence is the
    # publishing TRANSACTION. Under honest operation there is nothing to find, so what
    # is asserted here is the same property as above — no false positive — against the
    # records the run legitimately produced.
    local wtx bad2=0
    wtx="$(fl_cli 0 liststreamitems wpoa-weights 2>/dev/null \
           | sed -nE 's/.*"txid"[[:space:]]*:[[:space:]]*"([0-9a-f]{64})".*/\1/p' | tail -n1)"
    if [ -n "$wtx" ]; then
        for ((i = 0; i < NODES; i++)); do
            # An honestly self-published weight is not a selfwrite: the declared address
            # DID sign it. Swept over a range of heights so the refusal cannot be an
            # accident of naming the wrong one.
            for h in $((SAMPLE_END - 2)) $((SAMPLE_END - 1)) "$SAMPLE_END"; do
                fl_cli "$i" reportmalus selfwrite "$addr" "$h" "$wtx" >/dev/null 2>&1 \
                    && bad2=$((bad2+1))
                # And a correctly computed weight is not a badweight: every node's
                # recomputation agrees with it.
                fl_cli "$i" reportmalus badweight "$addr" "$h" "$wtx" >/dev/null 2>&1 \
                    && bad2=$((bad2+1))
            done
            # A transaction nobody has ever seen proves nothing, for either kind.
            fl_cli "$i" reportmalus selfwrite "$addr" "$SAMPLE_END" \
                "00000000000000000000000000000000000000000000000000000000deadbeef" \
                >/dev/null 2>&1 && bad2=$((bad2+1))
            fl_cli "$i" reportmalus badweight "$addr" "$SAMPLE_END" \
                "00000000000000000000000000000000000000000000000000000000deadbeef" \
                >/dev/null 2>&1 && bad2=$((bad2+1))
        done
        fl_assert_zero "$bad2" \
            "false data-integrity reports accepted against honest records (must be 0)"
    else
        fl_log "no wpoa-weights item to test the data-integrity kinds against; skipped"
    fi

    # The kinds must at least be RECOGNISED, so a typo in the wire spelling cannot make
    # the whole family silently unreportable.
    if fl_cli 0 help reportmalus 2>/dev/null | grep -q "selfwrite"; then
        fl_ok "reportmalus advertises the data-integrity kinds"
    else
        fl_bad "reportmalus does not advertise selfwrite/badweight"
    fi
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

# The three symptom counters, asserted by check_diversity_spacing in both regimes.
_check_diversity_symptoms() {
    local denied cannot nokey
    denied=$(fl_logcount_all "Permission denied for miner")
    cannot=$(fl_logcount_all "cannot mine now, waiting")
    nokey=$(fl_logcount_all "no local mining key, waiting")
    fl_log "per-node 'Permission denied for miner':"; fl_logcount_per_node "Permission denied for miner"
    fl_assert_zero "$denied" "'Permission denied for miner' block rejections"
    fl_assert_zero "$cannot" "miner-side 'cannot mine now' back-offs"
    fl_assert_zero "$nokey"  "elected proposers that found no local mining key"
}

# REGRESSION — mining-diversity spacing must be inert on wPoA-governed heights.
#
# The native rule (mc_Permissions::IsBarredByDiversity) is round-robin: it forbids a
# miner from producing a block within `spacing` heights of its previous one. Under
# weighted selection every permissioned address takes part in every round, so a heavier
# validator legitimately wins two CONSECUTIVE rounds — which the native rule rejects.
#
# The defect was masked by the default 3-node set-up, where the computed spacing
# degenerates to 1 and the rule is arithmetically inert; from 4 miners upward (with the
# default mining-diversity 0.3) it becomes 2 and bites. So this check FIRST asserts the
# run is in the biting regime, then asserts the consecutive win was accepted.
#
# The three symptom counters are the three faces of the same bug:
#   "Permission denied for miner"  — validator side, block admission (CheckBlockPermissions)
#   "cannot mine now, waiting"     — miner side, CreateNewBlock's canMine self-test probe
#   "no local mining key, waiting" — miner side, GetKeyFromAddressBook via GetAllPermissions:
#                                    the elected proposer concludes it holds no mining key
#                                    and sleeps through its own round (the stalling face)
check_diversity_spacing() {
    local d spacing
    d="$(fl_chain_param 0 mining-diversity)"
    [ -n "$d" ] || { fl_bad "could not read mining-diversity from getblockchainparams"; return; }
    spacing="$(fl_native_diversity_spacing "$NODES" "$d")"
    fl_log "miners=$NODES  mining-diversity=$d  ->  native spacing=$spacing"

    if [ "${spacing:-1}" -lt 2 ]; then
        # Not a failure: at this miner count the native rule is arithmetically inert, so
        # there is nothing for it to break. The consecutive-win case is covered by
        # scenario_diversity_spacing, which the orchestration runs precisely when this
        # shared run cannot express it. Assert the symptom counters anyway — they are
        # meaningful at any miner count — and skip the pair requirement.
        fl_log "native spacing is $spacing: the native rule is inert at $NODES miners, so this"
        fl_log "shared run cannot express the consecutive-win case (covered by the dedicated scenario)."
        _check_diversity_symptoms
        return
    fi
    fl_ok "native spacing is $spacing (>=2): the consecutive-win regime is under test"

    # Count consecutive same-miner pairs over the sample window.
    local miners=() pairs=0 i
    while IFS= read -r line; do [ -n "$line" ] && miners+=("$line"); done \
        < <(fl_block_miners 0 "$SAMPLE_START" "$SAMPLE_END")
    if [ "${#miners[@]}" -lt 2 ]; then
        fl_bad "could not read block miners for heights $SAMPLE_START..$SAMPLE_END"
        return
    fi
    for ((i = 1; i < ${#miners[@]}; i++)); do
        [ "${miners[i]}" = "${miners[i-1]}" ] && pairs=$((pairs + 1))
    done
    fl_log "blocks sampled: ${#miners[@]} (heights $SAMPLE_START..$SAMPLE_END); consecutive same-miner pairs: $pairs"

    _check_diversity_symptoms

    # A run with zero consecutive pairs proves nothing either way: report it as a
    # failure of the TEST to exercise the case, not as a pass.
    if [ "$pairs" -gt 0 ]; then
        fl_ok "a validator won two consecutive wPoA rounds and the block was accepted ($pairs occurrence(s))"
    else
        fl_bad "no consecutive same-miner pair occurred: INCONCLUSIVE (raise SAMPLE_BLOCKS, or skew WEIGHTS so one validator wins more often)"
    fi
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

# Dedicated 4-miner scenario for the mining-diversity regression.
#
# Needed only because the native spacing is arithmetically inert below 4 miners (see
# check_diversity_spacing): at the default NODES=3 the shared run simply cannot express a
# consecutive win. Weights are deliberately skewed so the heaviest validator wins often
# and consecutive pairs appear within a short sample: with 100/200/400/800 the chance that
# any given pair of adjacent heights has the same proposer is sum(p_i^2) ~= 0.38, so a
# 30-block window yields ~11 of them.
#
# The orchestration runs this ONLY when the shared run could not cover the case, so the
# default cost is one extra short network and NODES>=4 runs pay nothing.
scenario_diversity_spacing() {
    fl_phase "SCENARIO: mining-diversity regression (4 miners, skewed weights)"
    local NODES=4
    local WEIGHTS="100 200 400 800"
    local SAMPLE_BLOCKS=30
    fl_log "miners=$NODES weights=($WEIGHTS) — native spacing becomes 2 and would bar consecutive wins"

    fl_start_network "$FULL_STACK_ARGS"
    fl_wait_weight_convergence || fl_die "weights did not converge (diversity scenario)"
    local cur; cur="$(fl_tip_height 0)"; cur="${cur:-0}"
    SAMPLE_START=$(( cur + 1 )); [ "$SAMPLE_START" -lt "$SETUP_BLOCKS" ] && SAMPLE_START=$SETUP_BLOCKS
    SAMPLE_END=$(( SAMPLE_START + SAMPLE_BLOCKS - 1 ))
    fl_drive_to_height $(( SAMPLE_END + CONFIRM_BUFFER )) "$DRIVE_TIMEOUT" \
        "4-miner stall — a proposer barred by mining-diversity would look exactly like this" \
        || fl_die "diversity scenario did not reach height $SAMPLE_END (chain stalled)"

    fl_check_begin "diversity_spacing_4n" 1
        check_diversity_spacing
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
fl_check_begin "diversity_spacing"     1; check_diversity_spacing;     fl_check_end || true
fl_check_begin "vrf"                   1; check_vrf;                   fl_check_end || true
fl_check_begin "randao"                1; check_randao;                fl_check_end || true
fl_check_begin "sortition"             1; check_sortition;             fl_check_end || true
fl_check_begin "distribution"          1; check_distribution;          fl_check_end || true

fl_phase "PHASE 4/4 — teardown"
fl_teardown

# ---- mining-diversity regression --------------------------------------------
# Runs only when the shared run above could not exercise it, i.e. when the native
# spacing is inert at this miner count. At NODES>=4 check_diversity_spacing already
# covered it on the shared network and this costs nothing.
if [ "${SKIP_DIVERSITY_SCENARIO:-0}" != "1" ] && [ "$NODES" -lt 4 ]; then
    scenario_diversity_spacing
fi

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
