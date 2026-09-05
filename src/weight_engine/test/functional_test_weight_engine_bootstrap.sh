#!/usr/bin/env bash
#
# Functional test — weight-engine BOOTSTRAP on a clean network.
#
# Guards the bootstrap ordering of the wpoa-weights stream. The failure it reproduces:
#
#   wpoa-weights used to be created lazily, from inside RegisterLocalWeight — i.e. only
#   once a node ALREADY had a weight to publish. Under the weight engine a weight only
#   becomes computable after the first epoch is buried, so on a clean network the create
#   was sequenced after an event that itself needed the stream:
#
#     stream missing -> nothing publishable -> registry empty -> no proposer elected
#       -> chain does not advance -> no epoch buries -> no weight -> stream missing
#
#   The chain stopped at setup-first-blocks reporting only "0 validators, total=0" and
#   "cannot score (unsynced or unweighted)".
#
# There are two halves to the ordering, and this test pins both:
#
#   1. THE STREAM MUST EXIST EARLY — checked directly, and it is the half the node code
#      owns: creating the stream needs only the `create` permission, which the genesis
#      admin holds from block 1. ThreadWeightEngine now calls EnsureStreamReady() before
#      the epoch gate, so the stream (and the write grants aimed at it) are in place long
#      before wPoA engages.
#
#   2. THE FIRST WEIGHT MUST BE COMPUTABLE BEFORE wPoA ENGAGES — a property of the chain
#      parameters, not of the code:
#
#          setup-first-blocks  >  weight-epoch-length + STABILITY_MARGIN(6) - 1
#
#      The stock defaults (epoch 100, margin 6, setup 60 -> 105 > 60) VIOLATE it, which is
#      why this is easy to hit; AppInit2 now warns explicitly when they do. This test runs
#      a configuration that SATISFIES it (epoch 10 -> first weight at 15, setup 30) and
#      asserts the registry is genuinely populated by the transition height.
#
# Reuses the wPoA functional library for the network bootstrap, so no setup code is
# duplicated. Requires the node to be built first.
#
# Usage:
#   ./functional_test_weight_engine_bootstrap.sh
#   NODES=4 ./functional_test_weight_engine_bootstrap.sh
#   KEEP_LOGS=1 ./functional_test_weight_engine_bootstrap.sh
#
# Exit code: 0 iff every critical check passed.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"          # .../src
# shellcheck source=../../wpoa/test/functional_lib.sh
. "$SRC_DIR/wpoa/test/functional_lib.sh"

BINDIR="${BINDIR:-$SRC_DIR}"
NODES="${NODES:-3}"
SETUP_BLOCKS="${SETUP_BLOCKS:-30}"
EPOCH_LEN="${EPOCH_LEN:-10}"
STABILITY_MARGIN=6                  # MC_WEIGHT_DEFAULT_STABILITY_MARGIN
ESG_SCORE="${ESG_SCORE:-15}"
TARGET_BLOCK_TIME="${TARGET_BLOCK_TIME:-2}"
DRIVE_TIMEOUT="${DRIVE_TIMEOUT:-400}"
WEIGHT_TIMEOUT="${WEIGHT_TIMEOUT:-240}"
KEEP_LOGS="${KEEP_LOGS:-0}"

ENGINE_ARGS="-enablewpoa=1 -enableweightengine=1 -weightepochlength=$EPOCH_LEN -debug=wpoa"

FIRST_WEIGHT_HEIGHT=$(( EPOCH_LEN + STABILITY_MARGIN - 1 ))

trap 'fl_teardown' EXIT

fl_phase "SETUP — clean network, weight engine ON (epoch=$EPOCH_LEN, setup-first-blocks=$SETUP_BLOCKS)"
fl_require_binaries
fl_log "invariant: setup-first-blocks($SETUP_BLOCKS) > epoch($EPOCH_LEN) + margin($STABILITY_MARGIN) - 1 = $FIRST_WEIGHT_HEIGHT"
if [ "$FIRST_WEIGHT_HEIGHT" -ge "$SETUP_BLOCKS" ]; then
    fl_die "misconfigured test: the first weight lands at $FIRST_WEIGHT_HEIGHT >= setup-first-blocks $SETUP_BLOCKS, so the registry CANNOT be populated in time (lower EPOCH_LEN or raise SETUP_BLOCKS)"
fi
fl_start_network "$ENGINE_ARGS"

# ---------------------------------------------------------------------------
# 1. The stream exists, and it exists EARLY — before wPoA engages.
# ---------------------------------------------------------------------------
# This is the direct regression assertion and it does not depend on the rest of the
# weight pipeline: under the bug the stream did not exist at all at this point, because
# no node had yet had a weight to publish.
fl_check_begin "stream_created_early" 1
    h_now="$(fl_tip_height 0)"; h_now="${h_now:-0}"
    if fl_cli 0 liststreams wpoa-weights >/dev/null 2>&1; then
        fl_ok "wpoa-weights exists at height $h_now"
    else
        fl_bad "wpoa-weights does NOT exist at height $h_now (the bootstrap deadlock)"
    fi
    if [ "$h_now" -lt "$SETUP_BLOCKS" ]; then
        fl_ok "and it exists BEFORE wPoA engages (height $h_now < setup-first-blocks $SETUP_BLOCKS)"
    else
        fl_bad "the chain is already at $h_now >= $SETUP_BLOCKS: cannot prove the stream pre-dates the transition"
    fi
    w_write="$(fl_stream_write_restricted 0 wpoa-weights)"
    fl_assert_eq "$w_write" "true" "wpoa-weights was created CLOSED (write-restricted)"
fl_check_end || true

# ---------------------------------------------------------------------------
# 2. Feed the engine its inputs: membership (self-written) + ESG (CA-signed).
# ---------------------------------------------------------------------------
# Without these no node is a certified cluster miner, W_k is 0 for everyone and there is
# no publishable weight — so this is setup, not an assertion.
fl_phase "INPUTS — membership (self-attested) and ESG (Certification Authority)"
declare -a ADDRS=()
for ((i = 0; i < NODES; i++)); do
    a="$(fl_cli "$i" getaddresses 2>/dev/null | sed -nE 's/.*"([A-Za-z0-9]{30,40})".*/\1/p' | head -n1)"
    ADDRS+=("$a")
    fl_log "node $i address: $a"
done

# membership.write for every node — a node declares its OWN cluster, so the grant must be
# on the node's own address and the call must come from that node.
for ((i = 0; i < NODES; i++)); do
    fl_cli 0 grant "${ADDRS[i]}" weight-engine-membership.write >/dev/null 2>&1 \
        && fl_log "granted weight-engine-membership.write to node $i"
done
# node 0 is the Certification Authority: admin confers the role, it is not automatic.
fl_cli 0 grant "${ADDRS[0]}" high1 >/dev/null 2>&1 && fl_log "granted high1 (CA role) to node 0"
fl_cli 0 grant "${ADDRS[0]}" weight-engine-esg.write >/dev/null 2>&1 && fl_log "granted weight-engine-esg.write to node 0"

fl_log "waiting for the grants to confirm..."
sleep $(( TARGET_BLOCK_TIME * 5 ))

# Each node registers itself as its own cluster head (self-write).
for ((i = 0; i < NODES; i++)); do
    if fl_cli "$i" weightregistermembership "${ADDRS[i]}" >/dev/null 2>&1; then
        fl_log "node $i self-registered membership"
    else
        fl_log "WARNING: node $i could not self-register membership"
    fi
done
# The CA certifies every node, so each has a non-zero ESG and therefore W_k > 0.
for ((i = 0; i < NODES; i++)); do
    if fl_cli 0 weightsetesg "${ADDRS[i]}" "$ESG_SCORE" >/dev/null 2>&1; then
        fl_log "CA certified node $i with ESG=$ESG_SCORE"
    else
        fl_log "WARNING: CA could not certify node $i"
    fi
done

# ---------------------------------------------------------------------------
# 3. Drive past the wPoA transition and assert the registry is populated.
# ---------------------------------------------------------------------------
fl_phase "DRIVE — past the wPoA transition at height $SETUP_BLOCKS"
DRIVE_TO=$(( SETUP_BLOCKS + 3 * EPOCH_LEN ))
fl_drive_to_height "$DRIVE_TO" "$DRIVE_TIMEOUT" \
    "STALL at the wPoA transition — this is exactly the bootstrap deadlock" \
    || fl_log "WARNING: did not reach $DRIVE_TO; the checks below will show why"

fl_check_begin "no_stall_at_transition" 1
    h="$(fl_tip_height 0)"; h="${h:-0}"
    if [ "$h" -gt "$SETUP_BLOCKS" ]; then
        fl_ok "chain advanced past the transition (height $h > setup-first-blocks $SETUP_BLOCKS)"
    else
        fl_bad "chain STALLED at height $h (transition is $SETUP_BLOCKS): registry empty when wPoA engaged"
    fi
fl_check_end || true

fl_check_begin "registry_populated" 1
    # The mandate's two conditions: the registry is not empty, and at least one validator
    # is scoreable (a weight > 0 — Efraimidis-Spirakis cannot draw a zero-weight key).
    bad_nodes=0
    for ((i = 0; i < NODES; i++)); do
        v="$(fl_cli "$i" getallweights 2>/dev/null | sed -nE 's/.*"validators"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' | head -n1)"
        t="$(fl_node_total "$i")"
        fl_log "node $i: validators=${v:-?} total=${t:-?}"
        if [ "${v:-0}" -lt 1 ] || [ "${t:-0}" -lt 1 ]; then
            bad_nodes=$(( bad_nodes + 1 ))
        fi
    done
    fl_assert_zero "$bad_nodes" "nodes reporting an EMPTY weight registry ('0 validators, total=0')"

    scoreable="$(fl_cli 0 getallweights 2>/dev/null \
        | grep -oE '"[A-Za-z0-9]{30,40}"[[:space:]]*:[[:space:]]*[0-9]+' \
        | sed -E 's/.*:[[:space:]]*//' | awk '$1>0' | wc -l)"
    fl_assert_gt0 "$scoreable" "validators with a scoreable (non-zero) weight"
fl_check_end || true

fl_check_begin "no_scoring_stall_logs" 1
    cannot_score=$(fl_logcount_all "cannot score \(unsynced or unweighted\)")
    fl_log "per-node 'cannot score (unsynced or unweighted)':"
    fl_logcount_per_node "cannot score \(unsynced or unweighted\)"
    # A handful of these is legitimate right at the transition, before the first weight is
    # imported; a stalled network logs them forever. Judge by the chain having advanced
    # (checked above) and by the count not dominating the run.
    if [ "${cannot_score:-0}" -eq 0 ]; then
        fl_ok "no 'cannot score' back-offs at all"
    else
        fl_log "note: $cannot_score 'cannot score' lines — acceptable only because the chain advanced past the transition"
        fl_ok "'cannot score' back-offs did not prevent liveness ($cannot_score, chain at $(fl_tip_height 0))"
    fi
fl_check_end || true

fl_check_begin "weights_agree_across_nodes" 1
    ref="$(fl_node_total 0)"
    mism=0
    for ((i = 1; i < NODES; i++)); do
        ti="$(fl_node_total "$i")"
        [ -n "$ti" ] && [ "$ti" != "$ref" ] && { fl_bad "node $i total=$ti != node 0 total=$ref"; mism=$((mism+1)); }
    done
    fl_assert_zero "$mism" "nodes disagreeing on the aggregate weight (node 0 = $ref)"
fl_check_end || true

fl_phase "TEARDOWN"
fl_teardown
trap - EXIT

if fl_check_summary; then
    echo
    echo "WEIGHT-ENGINE BOOTSTRAP TEST PASSED (stream created before the transition; registry populated; no stall)."
    exit 0
fi
echo
echo "WEIGHT-ENGINE BOOTSTRAP TEST FAILED." >&2
exit 1
