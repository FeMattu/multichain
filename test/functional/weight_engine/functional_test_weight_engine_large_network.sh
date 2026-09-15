#!/usr/bin/env bash
#
# Functional test — LARGE weighted-wPoA network over many epochs.
# =============================================================================
# The other functional suites are short: they prove a mechanism engages. This one runs
# the system long enough for the ECONOMICS to close a loop. The restitution-rate
# feedback is defined across epochs,
#
#     w_k^(e) = W_k^(e) * [ rho_k^(e-1) * lambda + (1 - lambda) ]      (Def. peso-finale)
#
# so it cannot be observed at all in a handful of epochs: rho is computed from an epoch's
# confirmed transfers and only reaches the weight one epoch later.
#
# Topology (the counts are the point, and all are overridable):
#   1  admin / genesis   — Certification Authority conferrer, treasury funder, refueller
#   10 miners            — the wPoA validators the engine computes w_k for
#   20 companies         — non-miner; they generate the activity tau and pay the treasury
#   2  Certification Authorities — non-miner; they sign the ESG scores
#   = 33 nodes.
#
# ⚠ 33 real multichaind processes on one host. Budget a few GB of RAM and expect hours
#   at the default 50 epochs. Use --fast for a 5-epoch pass during development: it keeps
#   100 blocks per epoch and every other structural constraint, so it exercises the same
#   geometry, just fewer times round.
#
# -----------------------------------------------------------------------------
# WHY THIS ENABLES THE NATIVE CURRENCY, which no other suite does
# -----------------------------------------------------------------------------
# MultiChain defaults `initial-block-reward = 0`, so on a stock chain there is no
# spendable native currency. That is not cosmetic here. ComputeEpochFacts derives the
# credits, the debits AND R_k from native output values (weight_reader.cpp), so with no
# native currency:
#
#     credits = debits = R_k = 0  ->  saldo = 0  ->  RestitutionRate's saldo <= 0 guard
#     ->  rho = 0 for every cluster, in every epoch  ->  w_k = W_k * (1 - lambda)
#
# a UNIFORM scaling. The election would be unchanged, lambda = 0.2 and 0.3 would be
# indistinguishable, and 50 epochs would measure a constant. So this suite premines the
# genesis admin and pays a block reward, in its OWN params.dat. No production code and
# no other suite is affected. Rationale: ../../../docs/adr/test-restructure-2026.md §6.2.
#
# -----------------------------------------------------------------------------
# WHY THE GAS REFUEL LOOP EXISTS
# -----------------------------------------------------------------------------
# A node with no native currency cannot publish a transaction — not membership, not ESG,
# not a transfer to the treasury. Over 50 epochs the companies spend continuously and
# the non-miners earn nothing, so without replenishment they run dry and the run stalls
# long before epoch 50, reporting a weight-engine failure that is really an empty wallet.
# The admin therefore tops up any node below a floor, and every refuel is logged with the
# node, the balance either side, the amount and the txid.
#
# The refuel must not be mistaken for a reconciliation. R_k credits the SIGNERS of a
# transaction by what it pays TO THE TREASURY, so:
#
#     node  -> treasury   signer = node, pays treasury   => IS a reconciliation
#     admin -> node       signer = admin, pays the node  => pays treasury 0, is NOT one
#
# The direction is asserted on the transactions themselves, against the same quantity
# mc_ValuePaidToTreasury reads, with a positive control (a real company -> treasury
# transfer) so the negative assertion means something. The treasury is a DEDICATED
# address, never the admin's: with the admin as treasury its own change outputs pay the
# treasury, and only the `signer == treasury` guard in mc_AccumulateReconciliation keeps
# that from counting.
#
# -----------------------------------------------------------------------------
# BLOCK ARITHMETIC — computed and logged, never hardcoded
# -----------------------------------------------------------------------------
# With EPOCH_LEN = L and STABILITY_MARGIN = 6:
#   epoch e is buried at tip height      L*e + 5
#   the engine publishes for e at        L*e + 5
#   the engine VERIFIES e (needs e+1) at L*(e+1) + 5
#   setup-first-blocks floor             L + 9   (derived at genesis, read back on chain)
#
# So covering N epochs *and verifying them* needs L*(N+1) + 5, not L*N. At L=100, N=50
# that is 5105 — the mandate's "~5000" is a little short of verifying epoch 50. The exact
# figure is computed below and printed before the run starts.
#
# -----------------------------------------------------------------------------
# Usage
# -----------------------------------------------------------------------------
#   ./functional_test_weight_engine_large_network.sh              # 50 epochs
#   ./functional_test_weight_engine_large_network.sh --fast       # 5 epochs
#   WE_LARGE_LAMBDA=0.3 ./functional_test_weight_engine_large_network.sh
#   WE_LARGE_MINERS=4 WE_LARGE_COMPANIES=6 ... --fast             # a smaller shape
#
# Environment (all with the documented defaults):
#   WE_LARGE_FAST           1 = 5 epochs instead of 50 (same as --fast)
#   WE_LARGE_MINERS         10    miner nodes
#   WE_LARGE_COMPANIES      20    non-miner company nodes
#   WE_LARGE_CAS            2     non-miner Certification Authority nodes
#   WE_LARGE_EPOCH_LEN      100   blocks per epoch (the mandate's floor; >= 100)
#   WE_LARGE_EPOCHS         50    epochs to cover (5 under --fast)
#   WE_LARGE_LOOKBACK       101   RANDAO k; deliberately > EPOCH_LEN (see below)
#   WE_LARGE_LAMBDA         0.2   feedback damping (system default is 0.5)
#   WE_LARGE_ESG            15    ESG score the CAs certify every cluster with
#   WE_LARGE_GAS_FLOOR      50    refuel below this native balance
#   WE_LARGE_GAS_TOPUP      500   native currency per refuel
#   WE_LARGE_GAS_SEED       1000  native currency seeded to each node at setup
#   WE_LARGE_BLOCK_REWARD   10    initial-block-reward
#   WE_LARGE_PREMINE        100000000  first-block-reward (the admin's float)
#   WE_LARGE_SETUP_BLOCKS   derived  setup-first-blocks; raise if the bootstrap outruns it
#   WE_LARGE_MC_DRAWS       50000 Monte Carlo draws per scenario
#   WE_LARGE_ALPHA          0.01  significance level for every statistical verdict
#   WE_LARGE_OUTPUT         test/output   where the recorded run and its report are written
#   WE_LARGE_NAME           derived  the run's directory name under the output root
#   TARGET_BLOCK_TIME       2     seconds (the parameter minimum)
#   BINDIR, KEEP_LOGS, FL_PARAM_OVERRIDES   as elsewhere in the suite
#
# ON k > EPOCH_LEN. WE_LARGE_LOOKBACK defaults to 101 with EPOCH_LEN 100, as mandated.
# It is legal (the range is 0..1000000 and no init check couples the two) but it is an
# unusual regime worth naming: the seed reads R_tot[n-101], so it moves far more slowly
# than one epoch, and below height 101 the lookback clamps to 0
# (randao_accumulator.cpp:211-214). Lower it to exercise a tighter beacon.
#
# Exit code: 0 iff every CRITICAL check passed.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # test/functional/weight_engine
FUNC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"                     # test/functional
REPO_ROOT="$(cd "$FUNC_DIR/../.." && pwd)"                   # repo root
export FL_LIB_DIR="$FUNC_DIR/lib"
export FL_OUTPUT_ROOT="${WE_LARGE_OUTPUT:-$REPO_ROOT/test/output}"
# shellcheck source=../lib/functional_lib.sh
. "$FUNC_DIR/lib/functional_lib.sh"

# ---- argument parsing -------------------------------------------------------
FAST="${WE_LARGE_FAST:-0}"
for arg in "$@"; do
    case "$arg" in
        --fast)    FAST=1 ;;
        -h|--help) sed -n '2,120p' "${BASH_SOURCE[0]}" | sed 's/^#\{0,1\} \{0,1\}//'; exit 0 ;;
        *)         echo "unexpected argument: $arg" >&2; exit 2 ;;
    esac
done

# ---- topology & parameters --------------------------------------------------
BINDIR="${BINDIR:-$REPO_ROOT/src}"
MINERS="${WE_LARGE_MINERS:-10}"
COMPANIES="${WE_LARGE_COMPANIES:-20}"
CAS="${WE_LARGE_CAS:-2}"
EPOCH_LEN="${WE_LARGE_EPOCH_LEN:-100}"
if [ "$FAST" = "1" ]; then
    EPOCHS="${WE_LARGE_EPOCHS:-5}"
else
    EPOCHS="${WE_LARGE_EPOCHS:-50}"
fi
LOOKBACK="${WE_LARGE_LOOKBACK:-$(( EPOCH_LEN + 1 ))}"
LAMBDA="${WE_LARGE_LAMBDA:-0.2}"
ESG_SCORE="${WE_LARGE_ESG:-15}"
GAS_FLOOR="${WE_LARGE_GAS_FLOOR:-50}"
GAS_TOPUP="${WE_LARGE_GAS_TOPUP:-500}"
GAS_SEED="${WE_LARGE_GAS_SEED:-1000}"
BLOCK_REWARD="${WE_LARGE_BLOCK_REWARD:-10}"
PREMINE="${WE_LARGE_PREMINE:-100000000}"
TARGET_BLOCK_TIME="${TARGET_BLOCK_TIME:-2}"
KEEP_LOGS="${KEEP_LOGS:-0}"

NODES=$(( 1 + MINERS + COMPANIES + CAS ))
export FL_CHAIN_PREFIX="welarge"

[ "$EPOCH_LEN" -ge 100 ] || fl_die "WE_LARGE_EPOCH_LEN must be >= 100 (got $EPOCH_LEN)"
[ "$MINERS"    -ge 1   ] || fl_die "WE_LARGE_MINERS must be >= 1"
[ "$CAS"       -ge 1   ] || fl_die "WE_LARGE_CAS must be >= 1 (nobody could sign ESG)"

# ---- the block budget, computed --------------------------------------------
SETUP_FLOOR="$(fl_setup_first_blocks_floor "$EPOCH_LEN")"
# THE FLOOR IS NOT ENOUGH ON A BIG NETWORK, and this is what stalled earlier revisions.
#
# The floor answers a question about epoch geometry: how many blocks before the first
# weight can be CONFIRMED. It knows nothing about how long it takes to bring 33 daemons
# up. Those are a race in different units, and at this size the bootstrap wins: even a
# brisk 8s per node is 256s, i.e. 128 blocks at target-block-time 2, so the chain sails
# past a floor of 109 before a single membership record exists. wPoA then takes over an
# EMPTY registry, elects nobody, and the chain stops -- looking like a weight bug when it
# is a stopwatch. See fl_setup_blocks_for_network.
#
# Raising it is safe: AdjustSetupFirstBlocks only ever raises setup-first-blocks TO the
# floor and leaves a larger value untouched, so this cannot conflict with the derivation
# the mandate warns about. It costs blocks, not correctness.
SETUP_BLOCKS="${WE_LARGE_SETUP_BLOCKS:-$(fl_setup_blocks_for_network "$NODES" "$EPOCH_LEN")}"
[ "$SETUP_BLOCKS" -ge "$SETUP_FLOOR" ] || SETUP_BLOCKS="$SETUP_FLOOR"
PUBLISH_HEIGHT="$(fl_height_for_buried_epoch "$EPOCHS" "$EPOCH_LEN")"
VERIFY_HEIGHT="$(fl_height_for_buried_epoch $(( EPOCHS + 1 )) "$EPOCH_LEN")"
TARGET_HEIGHT=$(( VERIFY_HEIGHT + FL_STABILITY_MARGIN + 9 ))   # slack past the last check
[ "$TARGET_HEIGHT" -gt "$SETUP_BLOCKS" ] || TARGET_HEIGHT=$(( SETUP_BLOCKS + EPOCH_LEN ))

# One RPC-poll budget per epoch chunk, generous: a 100-block epoch at 2s/block is ~200s
# of mining, and 33 nodes on one host will not hit that ideal.
EPOCH_DRIVE_TIMEOUT="${WE_LARGE_EPOCH_TIMEOUT:-$(( EPOCH_LEN * TARGET_BLOCK_TIME * 6 + 300 ))}"

trap fl_teardown EXIT

fl_phase "PLAN — $NODES nodes, $EPOCHS epochs of $EPOCH_LEN blocks"
cat <<PLAN
  topology
    admin / genesis                 1
    miners (wPoA validators)        $MINERS
    companies (non-miner)           $COMPANIES
    certification authorities       $CAS
    ------------------------------- ----
    total nodes                     $NODES

  chain parameters (params.dat, hash-enforced and inherited)
    weight-epoch-length             $EPOCH_LEN
    weight-lambda                   $LAMBDA        (system default 0.5)
    wpoa-randao-lookback (k)        $LOOKBACK      ($( [ "$LOOKBACK" -gt "$EPOCH_LEN" ] && echo "> epoch length, as mandated" || echo "<= epoch length" ))
    initial-block-reward            $BLOCK_REWARD  (native currency MUST exist -- see header)
    first-block-reward              $PREMINE       (the admin's float)
    target-block-time               $TARGET_BLOCK_TIME
    setup-first-blocks              $SETUP_BLOCKS  (floor $SETUP_FLOOR; raised to cover the
                                    bootstrap of $NODES nodes -- see the header)

  block arithmetic (computed from the epoch geometry, not hardcoded)
    stability margin                $FL_STABILITY_MARGIN
    setup-publish margin            $FL_SETUP_PUBLISH_MARGIN
    setup-first-blocks floor        $EPOCH_LEN + $FL_STABILITY_MARGIN - 1 + $FL_SETUP_PUBLISH_MARGIN + 1 = $SETUP_FLOOR
    epoch $EPOCHS published at            $EPOCH_LEN * $EPOCHS + $(( FL_STABILITY_MARGIN - 1 )) = $PUBLISH_HEIGHT
    epoch $EPOCHS VERIFIED at             $EPOCH_LEN * $(( EPOCHS + 1 )) + $(( FL_STABILITY_MARGIN - 1 )) = $VERIFY_HEIGHT
    TOTAL BLOCKS TO MINE            $TARGET_HEIGHT
    output directory                $FL_OUTPUT_ROOT

  gas
    seeded per node                 $GAS_SEED
    refuel floor / top-up           $GAS_FLOOR / $GAS_TOPUP

  mode                              $( [ "$FAST" = "1" ] && echo "--fast ($EPOCHS epochs)" || echo "full ($EPOCHS epochs)" )
PLAN

# ---- roles ------------------------------------------------------------------
declare -a FL_ROLE=(admin)
declare -a MINER_IDX=() COMPANY_IDX=() CA_IDX=()
for ((i = 0; i < MINERS; i++));    do FL_ROLE+=(miner);   MINER_IDX+=($(( ${#FL_ROLE[@]} - 1 ))); done
for ((i = 0; i < COMPANIES; i++)); do FL_ROLE+=(company); COMPANY_IDX+=($(( ${#FL_ROLE[@]} - 1 ))); done
for ((i = 0; i < CAS; i++));       do FL_ROLE+=(ca);      CA_IDX+=($(( ${#FL_ROLE[@]} - 1 ))); done

# ---- chain parameters -------------------------------------------------------
# Consensus-critical values go in params.dat, NOT on the command line: they are
# hash-enforced and inherited by joining nodes, and a runtime flag would apply to one
# node only (AppInit2 warns about exactly that). setup-first-blocks is deliberately
# absent so the genesis derivation owns it.
export FL_PARAM_OVERRIDES="setup-first-blocks = $SETUP_BLOCKS
weight-epoch-length = $EPOCH_LEN
weight-lambda = $LAMBDA
wpoa-randao-lookback = $LOOKBACK
initial-block-reward = $BLOCK_REWARD
first-block-reward = $PREMINE
${FL_PARAM_OVERRIDES:-}"

# The ENABLE switches stay on the command line: AppInit2's flag resolution does not
# consult params.dat's own enable-wpoa master (only the per-phase keys), so setting it in
# the file would leave wPoA off and the weight engine would refuse to start.
ENGINE_ARGS="-enablewpoa=1 -enableweightengine=1 -debug=wpoa"

fl_phase "SETUP — bootstrapping $NODES nodes"
fl_require_binaries
fl_start_role_network "$ENGINE_ARGS"

# ---- the effective setup-first-blocks, read off the chain -------------------
EFFECTIVE_SETUP="$(fl_chain_param 0 setup-first-blocks)"
[ -n "$EFFECTIVE_SETUP" ] || fl_die "could not read setup-first-blocks from getblockchainparams"
fl_log "effective setup-first-blocks on chain: $EFFECTIVE_SETUP (derived floor: $SETUP_FLOOR)"

fl_check_begin "setup_first_blocks_derived" 1
    # The mandate's constraint: whatever setup-first-blocks ends up being, it must not
    # reproduce the deadlock -- wPoA must not start electing before the first weight can
    # be CONFIRMED. Asserted against the value the CHAIN reports, not the one we asked
    # for, because the genesis node rewrites it before the parameter hash is taken.
    if [ "$EFFECTIVE_SETUP" -ge "$SETUP_FLOOR" ]; then
        fl_ok "setup-first-blocks=$EFFECTIVE_SETUP is at or above the derived floor $SETUP_FLOOR"
    else
        fl_bad "setup-first-blocks=$EFFECTIVE_SETUP is BELOW the floor $SETUP_FLOOR: the chain will stall there"
    fi
    if [ "$EFFECTIVE_SETUP" -ge "$SETUP_BLOCKS" ]; then
        fl_ok "and at or above the bootstrap budget we asked for ($SETUP_BLOCKS)"
    else
        fl_bad "setup-first-blocks=$EFFECTIVE_SETUP is below the bootstrap budget $SETUP_BLOCKS: wPoA may engage before the registry is populated"
    fi
    first_confirmable=$(( EPOCH_LEN + FL_STABILITY_MARGIN - 1 + FL_SETUP_PUBLISH_MARGIN ))
    if [ "$EFFECTIVE_SETUP" -gt "$first_confirmable" ]; then
        fl_ok "wPoA engages ($EFFECTIVE_SETUP) strictly after the first weight can confirm ($first_confirmable)"
    else
        fl_bad "wPoA engages at $EFFECTIVE_SETUP, at or before the first weight can confirm ($first_confirmable)"
    fi
fl_check_end || true

fl_check_begin "chain_parameters_in_force" 1
    fl_assert_eq "$(fl_chain_param 0 weight-epoch-length)" "$EPOCH_LEN" "weight-epoch-length on chain"
    fl_assert_eq "$(fl_chain_param 0 wpoa-randao-lookback)" "$LOOKBACK"  "wpoa-randao-lookback (k) on chain"
    # lambda is a string parameter, so compare as a number rather than as text.
    lam_onchain="$(fl_chain_param 0 weight-lambda)"
    if awk -v a="$lam_onchain" -v b="$LAMBDA" 'BEGIN{exit !(a+0 == b+0)}'; then
        fl_ok "weight-lambda on chain is $lam_onchain (requested $LAMBDA, system default 0.5)"
    else
        fl_bad "weight-lambda on chain is '$lam_onchain', expected $LAMBDA"
    fi
    if [ "$LOOKBACK" -gt "$EPOCH_LEN" ]; then
        fl_ok "k ($LOOKBACK) > weight-epoch-length ($EPOCH_LEN), the mandated regime"
    else
        fl_log "note: k ($LOOKBACK) <= weight-epoch-length ($EPOCH_LEN) -- overridden from the default"
        fl_ok "lookback configured as requested"
    fi
fl_check_end || true

# ---- addresses --------------------------------------------------------------
fl_phase "ADDRESSES — resolving one per node"
declare -a ADDR=()
for ((i = 0; i < NODES; i++)); do
    a="$(fl_node_address "$i")"
    [ -n "$a" ] || fl_die "node $i (${FL_ROLE[i]}) has no address"
    ADDR+=("$a")
done
ADMIN="${ADDR[0]}"
fl_log "admin: $ADMIN"

# ---- treasury, by restart ---------------------------------------------------
# Cannot be passed at first launch: the genesis address does not exist until the wallet
# does. Every node is restarted with it, because a node left without it computes R_k = 0
# while its peers do not -- a fork, not a degradation.
fl_phase "TREASURY — a dedicated address, set on every node by restart"
TREASURY="$(fl_make_treasury_address 0)"
[ -n "$TREASURY" ] || fl_die "could not create a treasury address"
fl_log "treasury: $TREASURY (deliberately NOT the admin's $ADMIN -- see the header)"
ENGINE_ARGS="$ENGINE_ARGS -weighttreasuryaddress=$TREASURY"
fl_restart_all_nodes "$ENGINE_ARGS"

fl_check_begin "network_up_with_treasury" 1
    down=0
    for ((i = 0; i < NODES; i++)); do
        fl_cli "$i" getinfo >/dev/null 2>&1 || { fl_bad "node $i (${FL_ROLE[i]}) is not serving RPC"; down=$(( down + 1 )); }
    done
    fl_assert_zero "$down" "nodes not serving RPC after the treasury restart"
fl_check_end || true

fl_check_begin "treasury_is_not_the_admin" 1
    if [ "$TREASURY" != "$ADMIN" ]; then
        fl_ok "treasury ($TREASURY) is distinct from the admin ($ADMIN), so a refuel cannot touch R_k"
    else
        fl_bad "treasury == admin: a refuel's change output would pay the treasury"
    fi
fl_check_end || true

# ---- permissions and engine inputs -----------------------------------------
EXPERIMENT="${WE_LARGE_NAME:-large-network-$( [ "$FAST" = "1" ] && echo fast || echo full )-e${EPOCHS}-l${LAMBDA}-$(date +%Y%m%d-%H%M%S)}"
fl_record_begin "$EXPERIMENT" || fl_log "continuing without recording"
fl_record_meta "$EXPERIMENT" "$(printf '{"miners": %s, "companies": %s, "cas": %s, "epoch_len": %s, "epochs": %s, "lookback": %s, "lambda": "%s", "setup_first_blocks": %s, "target_block_time": %s, "block_reward": %s, "premine": %s, "gas_floor": %s, "gas_topup": %s, "treasury": "%s", "fast": %s}' \
    "$MINERS" "$COMPANIES" "$CAS" "$EPOCH_LEN" "$EPOCHS" "$LOOKBACK" "$LAMBDA" "$EFFECTIVE_SETUP" "$TARGET_BLOCK_TIME" "$BLOCK_REWARD" "$PREMINE" "$GAS_FLOOR" "$GAS_TOPUP" "$TREASURY" "$FAST")"

fl_phase "INPUTS — membership (self-attested), ESG (Certification Authority)"

# Every node speaks about itself on the membership stream. The grant is on the node's own
# address and the call comes from that node: the records are self-attested, so a write
# permission grants a node nothing beyond the ability to describe itself.
for ((i = 0; i < NODES; i++)); do
    fl_cli 0 grant "${ADDR[i]}" weight-engine-membership.write >/dev/null 2>&1 || true
done
# The CA role is CONFERRED by the admin -- being an admin does not carry it. Only admin
# can grant a high1..high3 slot, which is what makes certification conferrable.
for idx in "${CA_IDX[@]}"; do
    fl_cli 0 grant "${ADDR[idx]}" high1 >/dev/null 2>&1 && fl_log "node $idx: granted high1 (CA role)"
    fl_cli 0 grant "${ADDR[idx]}" weight-engine-esg.write >/dev/null 2>&1
done
# Miners publish their own weight on the closed wpoa-weights stream.
for idx in "${MINER_IDX[@]}"; do
    fl_cli 0 grant "${ADDR[idx]}" wpoa-weights.write >/dev/null 2>&1 || true
done
fl_log "waiting for the grants to confirm..."
sleep $(( TARGET_BLOCK_TIME * 6 ))

# ---- seed gas ---------------------------------------------------------------
# Before anything else can transact. The non-miners never earn, so this float plus the
# refuel loop is their whole income.
fl_phase "GAS — seeding $GAS_SEED to each of $(( NODES - 1 )) non-admin nodes"
admin_bal="$(fl_native_balance 0)"
fl_log "admin native balance: $admin_bal (premine $PREMINE)"
if fl_is_zero "$admin_bal"; then
    fl_die "the admin has NO native currency: initial-block-reward/first-block-reward did not take effect in params.dat -- without it R_k is 0 and this whole suite is vacuous (see the header)"
fi
seeded=0
for ((i = 1; i < NODES; i++)); do
    txid="$(fl_cli 0 sendtoaddress "${ADDR[i]}" "$GAS_SEED" 2>/dev/null | tr -d '"[:space:]')"
    fl_is_txid "$txid" && seeded=$(( seeded + 1 ))
done
fl_log "seeded $seeded of $(( NODES - 1 )) nodes"
sleep $(( TARGET_BLOCK_TIME * 4 ))

fl_check_begin "gas_seeded" 1
    fl_assert_eq "$seeded" "$(( NODES - 1 ))" "non-admin nodes funded with native currency"
fl_check_end || true

# ---- membership + ESG -------------------------------------------------------
for ((i = 0; i < NODES; i++)); do
    fl_cli "$i" weightregistermembership "${ADDR[i]}" >/dev/null 2>&1 \
        || fl_log "WARNING: node $i could not self-register membership"
done
# The CAs certify every MINER, so each cluster has a non-zero ESG and therefore W_k > 0.
# Round-robin across the CAs so more than one of them is actually exercised.
ca_n=${#CA_IDX[@]}; ci=0
for idx in "${MINER_IDX[@]}"; do
    ca=${CA_IDX[$(( ci % ca_n ))]}
    fl_cli "$ca" weightsetesg "${ADDR[idx]}" "$ESG_SCORE" >/dev/null 2>&1 \
        && fl_log "CA node $ca certified miner node $idx with ESG=$ESG_SCORE" \
        || fl_log "WARNING: CA node $ca could not certify miner node $idx"
    ci=$(( ci + 1 ))
done
sleep $(( TARGET_BLOCK_TIME * 6 ))

# ---- the reconciliation direction rule, both ways --------------------------
# Asserted BEFORE the long run, so a direction bug fails in seconds rather than hours.
fl_phase "DIRECTION — a refuel is not a reconciliation; a treasury transfer is"
fl_check_begin "reconciliation_direction" 1
    # NEGATIVE: admin -> node. Signer is the admin, outputs pay the node, so the value
    # paid to the treasury is 0 and mc_AccumulateReconciliation credits nobody.
    probe_idx="${COMPANY_IDX[0]}"
    refuel_tx="$(fl_refuel_node "$probe_idx" "$GAS_TOPUP")"
    if [ -n "$refuel_tx" ]; then
        paid="$(fl_tx_value_to_address 0 "$refuel_tx" "$TREASURY")"
        if fl_is_zero "$paid"; then
            fl_ok "an admin -> node refuel pays the treasury 0, so it is NOT a reconciliation"
        else
            fl_bad "an admin -> node refuel paid $paid to the treasury: it WOULD be counted as a reconciliation"
        fi
    else
        fl_bad "could not issue a refuel transaction to probe the direction rule"
    fi

    # POSITIVE CONTROL: node -> treasury. Without this the assertion above could pass
    # simply because the parser never finds anything.
    recon_tx="$(fl_cli "$probe_idx" sendtoaddress "$TREASURY" 10 2>/dev/null | tr -d '"[:space:]')"
    if fl_is_txid "$recon_tx"; then
        sleep $(( TARGET_BLOCK_TIME * 3 ))
        paid2="$(fl_tx_value_to_address "$probe_idx" "$recon_tx" "$TREASURY")"
        if fl_is_zero "$paid2"; then
            fl_bad "a node -> treasury transfer registered 0 to the treasury: the probe cannot see reconciliations at all"
        else
            fl_ok "a node -> treasury transfer pays the treasury $paid2, so the probe does detect reconciliations"
        fi
    else
        fl_bad "node $probe_idx could not pay the treasury (out of gas?)"
    fi
fl_check_end || true

# ---- the registry must be usable BEFORE wPoA engages ------------------------
# The gate that turns the old silent stall into a diagnosis. Efraimidis-Spirakis cannot
# draw a zero-weight key (Cor. 5.4), so "populated" means validators with a NON-ZERO
# weight: a registry listing ten validators at 0 elects nobody just as surely as an empty
# one, and the chain stops at setup-first-blocks either way.
fl_phase "READINESS — the weight registry must be populated before wPoA takes over at $EFFECTIVE_SETUP"
fl_check_begin "registry_ready_before_wpoa" 1
    want_ready=$(( MINERS / 2 )); [ "$want_ready" -lt 1 ] && want_ready=1
    ready_budget=$(( EFFECTIVE_SETUP * TARGET_BLOCK_TIME ))
    if fl_wait_registry_ready "$want_ready" "$ready_budget" "$EFFECTIVE_SETUP"; then
        fl_ok "the registry carries scoreable weights with the chain still at $(fl_tip_height 0) < $EFFECTIVE_SETUP"
    else
        fl_bad "the registry was NOT usable before wPoA engaged -- the run cannot proceed (see the diagnosis above)"
        fl_log ""
        fl_log "  Most likely: bootstrapping $NODES nodes outran setup-first-blocks=$EFFECTIVE_SETUP."
        fl_log "  Retry with a larger budget, e.g. WE_LARGE_SETUP_BLOCKS=$(( EFFECTIVE_SETUP * 2 )),"
        fl_log "  or a smaller network (WE_LARGE_MINERS / WE_LARGE_COMPANIES)."
        fl_check_end || true
        fl_phase "TEARDOWN (aborted at readiness)"
        fl_record_finish
        [ -n "$FL_RUN_DIR" ] && fl_log "partial recording kept at $FL_RUN_DIR"
        fl_teardown
        trap - EXIT
        fl_check_summary || true
        echo
        echo "LARGE-NETWORK TEST FAILED: the weight registry was not ready before wPoA engaged." >&2
        exit 1
    fi
fl_check_end || true

# ---- the long run -----------------------------------------------------------
# Driven one epoch at a time so the monitoring happens DURING the run, not after it: a
# node that runs dry at epoch 12 must be refuelled at epoch 12, and a mismatch verdict
# is worth catching when it appears rather than 40 epochs later.
fl_phase "RUN — driving $TARGET_HEIGHT blocks, monitoring each epoch"

REFUELS=0
EPOCH_REFUELS=0
CURRENT_EPOCH=0
LAST_RECORDED_HEIGHT=$EFFECTIVE_SETUP
REFUEL_FAILURES=0
VERIFY_SAMPLES=0
VERIFY_MISMATCH=0
VERIFY_NOTCLUSTER=0
VERIFY_OTHER_EPOCH=0
VERIFY_INVALID_DISAGREE=0
MAX_VERIFIED_EPOCH=0
STALLED=0

# Refuel any node whose native balance has fallen below the floor. Runs every epoch, so
# the window between falling below and being topped up is at most one epoch -- and the
# floor is set well above one epoch's spend, so a node never actually reaches zero.
monitor_gas() {
    local i bal
    for ((i = 1; i < NODES; i++)); do
        bal="$(fl_native_balance "$i")"
        if fl_lt "$bal" "$GAS_FLOOR"; then
            local txid
            txid="$(fl_refuel_node "$i" "$GAS_TOPUP")"
            if [ -n "$txid" ]; then
                REFUELS=$(( REFUELS + 1 ))
                EPOCH_REFUELS=$(( EPOCH_REFUELS + 1 ))
                fl_record_refuel "$CURRENT_EPOCH" "$i" "$bal" "$(fl_native_balance "$i")" "$GAS_TOPUP" "$txid"
            else
                REFUEL_FAILURES=$(( REFUEL_FAILURES + 1 ))
            fi
        fi
    done
}

# Sample the verification report on the admin plus a couple of miners: the verdicts are
# per-node (each recomputes independently), so a disagreement is only visible across
# nodes, but polling all 33 every epoch would dominate the run.
monitor_verification() {
    local -a probe=(0 "${MINER_IDX[0]}" "${MINER_IDX[$(( ${#MINER_IDX[@]} - 1 ))]}")
    local i ve mm nc oe inv
    EPOCH_MISMATCH=0; EPOCH_NOTCLUSTER=0; EPOCH_OTHER=0; EPOCH_VERIFIED=0
    for i in "${probe[@]}"; do
        ve="$(fl_verify_field "$i" epoch)"; ve="${ve:-0}"
        [ "$ve" -ge 1 ] || continue
        VERIFY_SAMPLES=$(( VERIFY_SAMPLES + 1 ))
        [ "$ve" -gt "$MAX_VERIFIED_EPOCH" ] && MAX_VERIFIED_EPOCH="$ve"

        mm="$(fl_verdict_count "$i" mismatch)";      mm="${mm:-0}"
        nc="$(fl_verdict_count "$i" not-a-cluster)"; nc="${nc:-0}"
        oe="$(fl_verdict_count "$i" other-epoch)";   oe="${oe:-0}"
        inv="$(fl_verify_field "$i" invalid)";       inv="${inv:-0}"

        VERIFY_MISMATCH=$((   VERIFY_MISMATCH + mm ))
        VERIFY_NOTCLUSTER=$(( VERIFY_NOTCLUSTER + nc ))
        VERIFY_OTHER_EPOCH=$(( VERIFY_OTHER_EPOCH + oe ))
        EPOCH_MISMATCH=$((   EPOCH_MISMATCH + mm ))
        EPOCH_NOTCLUSTER=$(( EPOCH_NOTCLUSTER + nc ))
        EPOCH_OTHER=$((      EPOCH_OTHER + oe ))
        [ "$ve" -gt "$EPOCH_VERIFIED" ] && EPOCH_VERIFIED="$ve"
        # other-epoch and unverified are explicitly NOT findings
        # (mc_WeightVerdictIsInvalid), so the invalid counter must equal exactly
        # mismatch + not-a-cluster. This is the assertion that catches other-epoch
        # being folded into the findings.
        [ "$inv" -eq $(( mm + nc )) ] || VERIFY_INVALID_DISAGREE=$(( VERIFY_INVALID_DISAGREE + 1 ))

        if [ "$mm" -ne 0 ] || [ "$nc" -ne 0 ]; then
            fl_log "  !! node $i epoch $ve: mismatch=$mm not-a-cluster=$nc -- $(fl_verdict_tally "$i")"
        fi
    done
}

# Companies transact every epoch: this is what generates tau, the activity the weight
# pipeline counts, and what pays the treasury so R_k is non-zero and rho can move. tau
# counts SIGNED INPUTS, so the transaction has to come FROM the company.
generate_activity() {
    local idx sent=0
    for idx in "${COMPANY_IDX[@]}"; do
        # Half to the treasury (a reconciliation), half to the admin (ordinary spend), so
        # the two flows are distinguishable in the epoch facts.
        if [ $(( sent % 2 )) -eq 0 ]; then
            fl_cli "$idx" sendtoaddress "$TREASURY" 5 >/dev/null 2>&1 || true
        else
            fl_cli "$idx" sendtoaddress "$ADMIN" 2 >/dev/null 2>&1 || true
        fi
        sent=$(( sent + 1 ))
    done
}

for ((e = 1; e <= EPOCHS; e++)); do
    want=$(fl_height_for_buried_epoch "$e" "$EPOCH_LEN")
    [ "$want" -lt "$EFFECTIVE_SETUP" ] && want=$(( EFFECTIVE_SETUP + FL_STABILITY_MARGIN ))

    generate_activity
    if ! fl_drive_to_height "$want" "$EPOCH_DRIVE_TIMEOUT" \
            "stall while covering epoch $e of $EPOCHS"; then
        fl_log "  STALL: did not reach height $want for epoch $e within ${EPOCH_DRIVE_TIMEOUT}s"
        STALLED=1
        break
    fi
    CURRENT_EPOCH=$e
    EPOCH_REFUELS=0
    monitor_gas
    monitor_verification

    # Stream this epoch's observations out NOW. A run that stalls at epoch 12 still
    # leaves 12 epochs of evidence, which is exactly when the evidence matters.
    h_now="$(fl_tip_height 0)"; h_now="${h_now:-0}"
    fl_record_weights "$e"
    fl_record_gas "$e"
    fl_record_epoch "$e" "$h_now" "${EPOCH_VERIFIED:-0}" "${EPOCH_MISMATCH:-0}" \
                    "${EPOCH_NOTCLUSTER:-0}" "${EPOCH_OTHER:-0}" "$EPOCH_REFUELS"
    if [ "$h_now" -gt "$LAST_RECORDED_HEIGHT" ]; then
        fl_record_proposers $(( LAST_RECORDED_HEIGHT + 1 )) "$h_now"
        LAST_RECORDED_HEIGHT="$h_now"
    fi

    fl_log "epoch $e/$EPOCHS covered at height $h_now  |  refuels=$REFUELS  max verified epoch=$MAX_VERIFIED_EPOCH"
done

# Past the last epoch, so epoch $EPOCHS itself gets buried AND verified.
if [ "$STALLED" = "0" ]; then
    fl_log "driving past the final epoch so epoch $EPOCHS can be verified (needs height $VERIFY_HEIGHT)"
    fl_drive_to_height "$TARGET_HEIGHT" $(( EPOCH_DRIVE_TIMEOUT * 3 )) \
        "stall while burying the final epoch" || STALLED=1
    CURRENT_EPOCH=$(( EPOCHS + 1 ))
    EPOCH_REFUELS=0
    monitor_gas
    monitor_verification
    h_now="$(fl_tip_height 0)"; h_now="${h_now:-0}"
    fl_record_weights "$CURRENT_EPOCH"
    fl_record_gas "$CURRENT_EPOCH"
    fl_record_epoch "$CURRENT_EPOCH" "$h_now" "${EPOCH_VERIFIED:-0}" "${EPOCH_MISMATCH:-0}" \
                    "${EPOCH_NOTCLUSTER:-0}" "${EPOCH_OTHER:-0}" "$EPOCH_REFUELS"
    [ "$h_now" -gt "$LAST_RECORDED_HEIGHT" ] && fl_record_proposers $(( LAST_RECORDED_HEIGHT + 1 )) "$h_now"
fi

FINAL_HEIGHT="$(fl_tip_height 0)"; FINAL_HEIGHT="${FINAL_HEIGHT:-0}"
FINAL_EPOCH="$(fl_buried_epoch_at "$FINAL_HEIGHT" "$EPOCH_LEN")"

# =============================================================================
# CHECKS
# =============================================================================
fl_phase "CHECKS — height $FINAL_HEIGHT, newest buried epoch $FINAL_EPOCH"

fl_check_begin "covered_the_required_epochs" 1
    fl_log "target $TARGET_HEIGHT blocks for $EPOCHS epochs; reached $FINAL_HEIGHT (buried epoch $FINAL_EPOCH)"
    if [ "$FINAL_EPOCH" -ge "$EPOCHS" ]; then
        fl_ok "covered $FINAL_EPOCH buried epochs, at or beyond the required $EPOCHS"
    else
        fl_bad "only $FINAL_EPOCH epochs buried of the required $EPOCHS (height $FINAL_HEIGHT of $TARGET_HEIGHT)"
    fi
    fl_assert_zero "$STALLED" "stalls while driving the chain"
fl_check_end || true

fl_check_begin "every_miner_proposed" 0
    # NON-CRITICAL, deliberately. Selection is weighted and random, so a light miner
    # legitimately may not win in a finite sample -- the mandate asks for this to be
    # explained rather than failed on. What IS reported is each miner's weight share and
    # the count its share predicts, so a zero can be judged rather than guessed at.
    from=$(( EFFECTIVE_SETUP + 1 )); to=$FINAL_HEIGHT
    [ "$to" -le "$from" ] && to=$(( from + 1 ))
    fl_log "proposer tally over the wPoA-governed range $from..$to:"
    tally="$(fl_proposer_tally 0 "$from" "$to")"
    printf '%s\n' "$tally" | sed 's/^/    /'

    total_blocks=$(( to - from + 1 ))
    weights_json="$(fl_cli 0 getallweights 2>/dev/null)"
    w_total="$(printf '%s' "$weights_json" | sed -nE 's/.*"total"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' | head -n1)"
    w_total="${w_total:-0}"

    never=0
    for idx in "${MINER_IDX[@]}"; do
        a="${ADDR[idx]}"
        n="$(printf '%s\n' "$tally" | awk -v a="$a" '$1==a{print $2}')"; n="${n:-0}"
        w="$(printf '%s' "$weights_json" \
             | grep -oE "\"$a\"[[:space:]]*:[[:space:]]*[0-9]+" \
             | sed -E 's/.*:[[:space:]]*//' | head -n1)"; w="${w:-0}"
        if [ "$n" -gt 0 ]; then
            fl_log "    miner node $idx: $n block(s), weight $w"
        else
            never=$(( never + 1 ))
            if [ "$w_total" -gt 0 ] && [ "$w" -gt 0 ]; then
                exp="$(awk -v w="$w" -v t="$w_total" -v b="$total_blocks" 'BEGIN{printf "%.1f", b*w/t}')"
                pnever="$(awk -v w="$w" -v t="$w_total" -v b="$total_blocks" 'BEGIN{printf "%.3g", exp(b*log(1-w/t))}')"
                fl_log "    miner node $idx: NEVER proposed. weight $w of $w_total -> expected ~$exp of $total_blocks blocks; P(never) ~ $pnever"
            else
                fl_log "    miner node $idx: NEVER proposed, and its weight is $w (of total $w_total) -- it could not be drawn at all"
            fi
        fi
    done
    if [ "$never" -eq 0 ]; then
        fl_ok "every one of the $MINERS miners proposed at least one block"
    else
        fl_log "note: $never miner(s) never proposed; see the per-miner expectation above. Not failed: with weighted random selection this can be statistically ordinary, and a zero-weight miner is a weight-pipeline finding that the verification checks below would catch on its own."
        fl_ok "proposer coverage reported for all $MINERS miners ($never never elected)"
    fi
fl_check_end || true

fl_check_begin "verification_clean_across_epochs" 1
    fl_log "verification sampled $VERIFY_SAMPLES time(s) across the run; highest verified epoch $MAX_VERIFIED_EPOCH"
    fl_log "  mismatch=$VERIFY_MISMATCH  not-a-cluster=$VERIFY_NOTCLUSTER  other-epoch=$VERIFY_OTHER_EPOCH"
    fl_assert_gt0  "$VERIFY_SAMPLES"      "verification reports sampled during the run"
    fl_assert_zero "$VERIFY_MISMATCH"     "mismatch verdicts (every node here is honest)"
    fl_assert_zero "$VERIFY_NOTCLUSTER"   "not-a-cluster verdicts (every miner is a registered cluster)"
    fl_assert_zero "$VERIFY_INVALID_DISAGREE" \
        "samples where invalid != mismatch + not-a-cluster (other-epoch counted as a finding)"
    # other-epoch is EXPECTED: publication lags the epoch it describes, so at any instant
    # some records are about an epoch other than the one being recomputed. Reported, never
    # failed on -- treating it as a finding is precisely how an honest node gets accused.
    fl_log "note: $VERIFY_OTHER_EPOCH other-epoch verdict(s) observed. Expected and NOT a finding: verification targets e-1 while the tip is in e."
    fl_ok "other-epoch verdicts were reported without being treated as invalid"
fl_check_end || true

fl_check_begin "verification_reached_the_final_epoch" 1
    if [ "$MAX_VERIFIED_EPOCH" -ge $(( EPOCHS - 1 )) ]; then
        fl_ok "verification reached epoch $MAX_VERIFIED_EPOCH, covering the $EPOCHS-epoch run (it targets e-1)"
    else
        fl_bad "verification only reached epoch $MAX_VERIFIED_EPOCH of the expected $(( EPOCHS - 1 ))"
    fi
fl_check_end || true

fl_check_begin "no_malus_false_positives" 1
    # ALL FOUR KINDS, in both families: equiv/delay (evidence is a block) and
    # selfwrite/badweight (evidence is a publishing transaction). Every node here is
    # honest, so the property is that nothing sticks -- Psi = 1, w_eff = w, and false
    # evidence is refused locally on every node so no report ever reaches the chain.
    bad_psi=0
    for idx in "${MINER_IDX[@]}"; do
        a="${ADDR[idx]}"
        m="$(fl_cli 0 getnodemalus "$a" 2>/dev/null)"
        psi="$(printf '%s' "$m" | sed -nE 's/.*"psi"[[:space:]]*:[[:space:]]*([0-9.]+).*/\1/p' | head -n1)"
        w="$(  printf '%s' "$m" | sed -nE 's/.*"weight"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' | head -n1)"
        eff="$(printf '%s' "$m" | sed -nE 's/.*"effective"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' | head -n1)"
        if [ "${psi:-0}" != "1" ] || [ "${eff:-x}" != "${w:-y}" ]; then
            fl_bad "miner node $idx carries a malus after an honest run: psi=$psi weight=$w effective=$eff"
            bad_psi=$(( bad_psi + 1 ))
        fi
    done
    fl_assert_zero "$bad_psi" "honest miners carrying an accumulated malus"

    # And the Valid() predicate refuses false evidence of each kind. A successful report
    # here would be a false positive reaching the chain.
    accepted=0
    victim="${ADDR[${MINER_IDX[0]}]}"
    h=$(( FINAL_HEIGHT - FL_STABILITY_MARGIN ))
    bh="$(fl_blockhash_at 0 "$h" | tr -d '"[:space:]')"
    wtx="$(fl_cli 0 liststreamitems wpoa-weights 2>/dev/null \
           | sed -nE 's/.*"txid"[[:space:]]*:[[:space:]]*"([0-9a-f]{64})".*/\1/p' | tail -n1)"
    if [ -n "$bh" ]; then
        # behavioural family: an honest block is neither a delay nor an equivocation
        fl_cli 0 reportmalus delay "$victim" "$h" "$bh"      >/dev/null 2>&1 && accepted=$(( accepted + 1 ))
        fl_cli 0 reportmalus equiv "$victim" "$h" "$bh" "$bh" >/dev/null 2>&1 && accepted=$(( accepted + 1 ))
    else
        fl_log "note: could not read a block hash at $h; the behavioural kinds were not probed"
    fi
    if [ -n "$wtx" ]; then
        # data-integrity family: an honestly self-published, correctly computed weight is
        # neither a selfwrite nor a badweight
        fl_cli 0 reportmalus selfwrite  "$victim" "$h" "$wtx" >/dev/null 2>&1 && accepted=$(( accepted + 1 ))
        fl_cli 0 reportmalus badweight  "$victim" "$h" "$wtx" >/dev/null 2>&1 && accepted=$(( accepted + 1 ))
    else
        fl_log "note: no wpoa-weights item found; the data-integrity kinds were not probed"
    fi
    fl_assert_zero "$accepted" "false malus reports accepted against honest nodes (all four kinds)"

    # The four wire spellings must at least be RECOGNISED, or a whole family would be
    # silently unreportable and this check would pass vacuously.
    unknown=0
    for kind in equiv delay selfwrite badweight; do
        fl_cli 0 help reportmalus 2>/dev/null | grep -q "$kind" || { fl_bad "reportmalus does not advertise '$kind'"; unknown=$(( unknown + 1 )); }
    done
    fl_assert_zero "$unknown" "malus kinds missing from the reportmalus help (of 4)"
fl_check_end || true

fl_check_begin "gas_never_ran_out" 1
    fl_log "refuels issued: $REFUELS   failures: $REFUEL_FAILURES"
    dry=0
    for ((i = 1; i < NODES; i++)); do
        bal="$(fl_native_balance "$i")"
        if fl_is_zero "$bal"; then
            fl_bad "node $i (${FL_ROLE[i]}) ended with a ZERO native balance: it could no longer transact"
            dry=$(( dry + 1 ))
        fi
    done
    fl_assert_zero "$dry"              "nodes that ran completely out of native currency"
    fl_assert_zero "$REFUEL_FAILURES"  "refuel transactions the admin could not issue"
fl_check_end || true

fl_check_begin "weights_agree_across_nodes" 1
    # The weight map is derived from public inputs by every node independently, so a
    # disagreement is a determinism failure, not a timing artefact.
    ref="$(fl_node_total 0)"
    mism=0
    for idx in "${MINER_IDX[@]}"; do
        ti="$(fl_node_total "$idx")"
        [ -n "$ti" ] && [ "$ti" != "$ref" ] && { fl_bad "node $idx total=$ti != node 0 total=$ref"; mism=$(( mism + 1 )); }
    done
    fl_assert_zero "$mism" "miners disagreeing on the aggregate weight (node 0 = $ref)"
fl_check_end || true

fl_check_begin "no_persistent_fork" 1
    probe=$(( FINAL_HEIGHT - FL_STABILITY_MARGIN ))
    [ "$probe" -lt 1 ] && probe=1
    ref="$(fl_blockhash_at 0 "$probe")"
    mism=0
    for ((i = 1; i < NODES; i++)); do
        hi="$(fl_blockhash_at "$i" "$probe")"
        [ -n "$hi" ] && [ "$hi" != "$ref" ] && { fl_bad "fork: node $i block $probe differs"; mism=$(( mism + 1 )); }
    done
    fl_assert_zero "$mism" "nodes disagreeing on the chain at buried height $probe"
fl_check_end || true

# =============================================================================
# STATISTICS
# =============================================================================
# The suite's own checks are structural: did it stall, did a verdict come back invalid,
# did a node run dry. They say nothing about whether the ELECTION was correct, which is
# a question about a distribution and needs a test with a stated null hypothesis.
#
# Two tests, because neither is sufficient alone. The empirical chi-square runs against
# THIS binary on THIS run, so it tests the compiled selector, the VRF, the beacon and the
# weight pipeline together -- but its sample is however many blocks were mined, which
# gives it no power at all in the tail of a skewed weight vector. The Monte Carlo
# re-implements the Efraimidis-Spirakis transformation and draws it as many times as
# asked, so it can test that tail -- but it is not running the C++. Together they
# localise a fault: agree and the pipeline is sound, disagree and it is the
# implementation rather than the design.
fl_record_finish
STATS_RC=0
if [ -n "$FL_RUN_DIR" ]; then
    fl_record_analyse --draws "${WE_LARGE_MC_DRAWS:-50000}" \
                      --alpha "${WE_LARGE_ALPHA:-0.01}" || STATS_RC=$?
    if [ -f "$FL_RUN_DIR/summary.txt" ]; then
        echo
        sed 's/^/  /' "$FL_RUN_DIR/summary.txt"
    fi
fi

fl_check_begin "statistical_tests" 1
    if [ -z "$FL_RUN_DIR" ]; then
        fl_bad "the run was not recorded, so no statistical test could be made"
    elif [ "$STATS_RC" -eq 0 ]; then
        fl_ok "every statistical verdict passed (Monte Carlo + empirical chi-square)"
    elif [ "$STATS_RC" -eq 2 ]; then
        fl_bad "the recorded run held no analysable data -- an empty run must not read as a passing one"
    else
        fl_bad "a statistical verdict FAILED -- see $FL_RUN_DIR/report.md"
    fi
fl_check_end || true

fl_phase "TEARDOWN"
fl_teardown
trap - EXIT

if [ -n "$FL_RUN_DIR" ]; then
    echo
    echo "Recorded run and analysis: $FL_RUN_DIR"
    echo "  report.md         the readable report (Monte Carlo, chi-square, concentration, epochs, gas)"
    echo "  summary.txt       the same verdicts as plain text"
    echo "  montecarlo.csv    one row per scenario per candidate"
    echo "  distribution.csv  per-validator expected vs observed, with 95% CIs"
    echo "  concentration.csv Gini / entropy / top-share, weights and proposals"
    echo "  epoch_stats.csv   per-epoch weights, dispersion, verdicts, refuels"
    echo "  gas_stats.csv     per-node balance trajectory"
    echo "  proposers.csv weights.csv epochs.csv gas.csv refuels.csv   (raw observations)"
fi

if fl_check_summary; then
    echo
    echo "LARGE-NETWORK TEST PASSED ($NODES nodes, $FINAL_EPOCH epochs of $EPOCH_LEN blocks,"
    echo "lambda=$LAMBDA, k=$LOOKBACK, $FINAL_HEIGHT blocks, $REFUELS refuels, verification clean)."
    exit 0
fi
echo
echo "LARGE-NETWORK TEST FAILED." >&2
exit 1
