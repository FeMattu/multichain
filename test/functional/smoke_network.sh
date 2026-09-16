#!/usr/bin/env bash
#
# Functional/smoke test — the thesis' economic model on a real wPoA network.
# =============================================================================
# Every node here is a real `multichaind` process on THIS machine, talking real RPC and
# real P2P. There is deliberately NO network emulation: no netem, no jitter, no link
# delay, no CORE. That is the point of this suite rather than a limitation of it — it
# isolates the PROTOCOL (weight computation, weighted selection, RANDAO/VRF reveal,
# inter-epoch feedback, malus) from every network variable, so that a change in an
# observed quantity has exactly one candidate explanation. Network behaviour is
# /experiments' subject; this suite must never grow a dependency on it.
#
# -----------------------------------------------------------------------------
# THE ECONOMIC MODEL, and why it is shaped exactly like this
# -----------------------------------------------------------------------------
# Implemented to thesis §4.2.1 / §4.3.1 and Def. 6.6-6.10, verified against the code
# (docs/adr/functional-smoke-refactor-2026.md). Four rules, each load-bearing:
#
#   1. GAS IS PREMINED. The admin (Apuana SB) holds the entire supply at genesis:
#      `first-block-reward` > 0 and `initial-block-reward` = 0. The thesis is explicit —
#      "moneta a emissione preminata [...] senza alcun meccanismo di conio incrementale
#      legato alla produzione dei blocchi" — so a per-block subsidy is NOT the model, and
#      is not needed: a premine alone yields a fully spendable native currency (ADR §7.1,
#      verified on a live chain).
#
#   2. COMPANIES SPEND ONLY ON FEES. Company transactions are INFORMATIVE — stream
#      publications carrying a data payload — never GAS transfers. Thesis §4.2.1: "lo
#      scopo delle transazioni non è il trasferimento di valore monetario tra i
#      partecipanti, ma esclusivamente la trasmissione autenticata e immutabile di
#      informazioni". The GAS a company holds exists only to pay the fee.
#
#   3. MINERS RESTITUTE. Miners earn the fees of the transactions they include (Def. 6.7)
#      and periodically return GAS to the treasury (Def. 6.6). THIS IS THE ONLY FLOW THAT
#      PRODUCES R_k, and the actor matters absolutely: `weight_engine.cpp:183` reads
#      `r_e[miner_address]` and nothing else, so a company paying the treasury credits a
#      key no cluster ever reads and leaves R_k = 0 for everybody. An earlier revision of
#      the large-network suite had companies pay the treasury and therefore measured a
#      pinned rho for its whole run (ADR §3.2).
#
#   4. NO HORIZONTAL GAS. Only admin -> node (seed, refuel) and miner -> treasury
#      (restitution) are legitimate. Company -> company GAS transfer is a bug, and this
#      suite ASSERTS its absence over the recorded data rather than merely refraining
#      from generating it.
#
# -----------------------------------------------------------------------------
# THE FEE
# -----------------------------------------------------------------------------
# The thesis states a flat 0.2 GAS per transaction. MultiChain has no such parameter:
# `minimum-relay-fee` is charged PER 1000 BYTES. This suite sets 0.2 GAS/KB and RECORDS
# THE MEASURED FEE, so the per-transaction cost is reported from the size distribution
# the run actually produced instead of being assumed. See ADR §7.2 for the divergence and
# the proposed thesis wording.
#
# -----------------------------------------------------------------------------
# Usage
# -----------------------------------------------------------------------------
#   ./smoke_network.sh                 # full run
#   ./smoke_network.sh --fast          # fewer epochs, same epoch length and roles
#
# Environment (defaults in brackets):
#   SMOKE_FAST          [0]      1 = the reduced epoch count
#   SMOKE_MINERS        [4]      miner nodes (wPoA validators / cluster heads)
#   SMOKE_COMPANIES     [6]      non-miner company nodes
#   SMOKE_CAS           [2]      non-miner Certification Authorities
#   SMOKE_EPOCH_LEN     [100]    blocks per epoch
#   SMOKE_EPOCHS        [12]     epochs to cover (3 under --fast)
#   SMOKE_LOOKBACK      [len+1]  RANDAO k
#   SMOKE_LAMBDA        [0.5]    feedback damping (system default)
#   SMOKE_ESG           [15]     ESG score the CAs certify with
#   SMOKE_TX_MIN/MAX    [20/60]  informative transactions per company per epoch
#   SMOKE_RESTIT_MIN/MAX[0/5]    restitution transfers per miner per epoch
#   SMOKE_FEE_RAW       [20000000]  minimum-relay-fee, raw units per 1000 bytes
#   SMOKE_PREMINE_RAW   [100000000000000]  first-block-reward; <= maximum-per-output
#   SMOKE_OUTPUT        [test/output]
#   BINDIR, KEEP_LOGS, TARGET_BLOCK_TIME   as elsewhere in the suite
#
# Exit code: 0 iff every CRITICAL check passed.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # test/functional
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export FL_LIB_DIR="$SCRIPT_DIR/lib"
export FL_OUTPUT_ROOT="${SMOKE_OUTPUT:-$REPO_ROOT/test/output}"
# shellcheck source=lib/functional_lib.sh
. "$SCRIPT_DIR/lib/functional_lib.sh"

FAST="${SMOKE_FAST:-0}"
for arg in "$@"; do
    case "$arg" in
        --fast)    FAST=1 ;;
        -h|--help) sed -n '2,90p' "${BASH_SOURCE[0]}" | sed 's/^#\{0,1\} \{0,1\}//'; exit 0 ;;
        *)         echo "unexpected argument: $arg" >&2; exit 2 ;;
    esac
done

# ---- topology ---------------------------------------------------------------
BINDIR="${BINDIR:-$REPO_ROOT/src}"
MINERS="${SMOKE_MINERS:-4}"
COMPANIES="${SMOKE_COMPANIES:-6}"
CAS="${SMOKE_CAS:-2}"
EPOCH_LEN="${SMOKE_EPOCH_LEN:-100}"
if [ "$FAST" = "1" ]; then EPOCHS="${SMOKE_EPOCHS:-3}"; else EPOCHS="${SMOKE_EPOCHS:-12}"; fi
LOOKBACK="${SMOKE_LOOKBACK:-$(( EPOCH_LEN + 1 ))}"
LAMBDA="${SMOKE_LAMBDA:-0.5}"
ESG_SCORE="${SMOKE_ESG:-15}"
TX_MIN="${SMOKE_TX_MIN:-20}"
TX_MAX="${SMOKE_TX_MAX:-60}"
RESTIT_MIN="${SMOKE_RESTIT_MIN:-0}"
RESTIT_MAX="${SMOKE_RESTIT_MAX:-5}"
FEE_RAW="${SMOKE_FEE_RAW:-20000000}"
PREMINE_RAW="${SMOKE_PREMINE_RAW:-100000000000000}"
TARGET_BLOCK_TIME="${TARGET_BLOCK_TIME:-2}"
KEEP_LOGS="${KEEP_LOGS:-0}"
EVENT_STREAM="${SMOKE_EVENT_STREAM:-supply-chain-events}"

NODES=$(( 1 + MINERS + COMPANIES + CAS ))
export FL_CHAIN_PREFIX="smoke"

[ "$MINERS"    -ge 1 ] || fl_die "SMOKE_MINERS must be >= 1"
[ "$CAS"       -ge 1 ] || fl_die "SMOKE_CAS must be >= 1 (nobody could certify ESG)"
[ "$COMPANIES" -ge 1 ] || fl_die "SMOKE_COMPANIES must be >= 1 (nothing would generate tau)"
[ "$TX_MAX" -ge "$TX_MIN" ] || fl_die "SMOKE_TX_MAX must be >= SMOKE_TX_MIN"
[ "$RESTIT_MAX" -ge "$RESTIT_MIN" ] || fl_die "SMOKE_RESTIT_MAX must be >= SMOKE_RESTIT_MIN"

# ---- GAS budgeting, derived rather than guessed ------------------------------
# A company must never run dry MID-EPOCH: it would stop generating tau and the epoch's
# weight would silently understate it. So the seed covers the worst case (TX_MAX
# transactions every epoch for the whole run) with a margin, and the refuel floor covers
# one further worst-case epoch so a top-up always arrives before the money runs out.
FEE_PER_KB="$(awk -v r="$FEE_RAW" 'BEGIN{printf "%.8f", r/100000000}')"
# A stream publish with this payload measures ~0.4-0.6 KB; 1 KB per transaction is a
# deliberate over-estimate, because over-funding costs nothing and under-funding voids
# the run.
GAS_PER_TX="$FEE_PER_KB"
GAS_FLOOR="$(awk -v t="$TX_MAX" -v g="$GAS_PER_TX" 'BEGIN{printf "%.4f", t*g*2}')"
GAS_SEED="$(awk -v t="$TX_MAX" -v g="$GAS_PER_TX" -v e="$EPOCHS" \
            'BEGIN{printf "%.4f", t*g*e*1.5 + 50}')"
GAS_TOPUP="$(awk -v s="$GAS_SEED" 'BEGIN{printf "%.4f", s/2}')"
# Miners restitute, so they need a float too: they earn fees, but not before they have
# mined, and epoch 1 would otherwise find them with nothing to return.
MINER_SEED="$(awk -v m="$RESTIT_MAX" -v e="$EPOCHS" 'BEGIN{printf "%.4f", m*e*40 + 200}')"

# THE WALLET FEE CEILING HAS TO BE RAISED, or nothing can be published.
#
# Found by running this suite: every node failed `weightregistermembership` with
#
#     error code: -6   Transaction too large for fee policy
#
# while holding 2592 GAS and the right write permission. The cause is a collision between
# the CHAIN's relay fee and the WALLET's own ceiling:
#
#   wallet.cpp:36    maxTxFee = 0.1 * COIN                     -- 0.1 GAS, a local default
#   wallet.cpp:3266  nFeeNeeded capped at maxTxFee
#   walletcoins.cpp:2463  if (nFeeNeeded < minRelayTxFee.GetFee(nBytes)) -> FAIL
#
# So once `minimum-relay-fee * nBytes/1000` exceeds maxTxFee, the cap guarantees the very
# comparison that then rejects the transaction. At 0.2 GAS per 1000 bytes that is every
# transaction above 500 bytes -- which is most stream publishes, and precisely why a plain
# 474-byte transfer still worked while a membership record did not.
#
# -maxtxfee is WALLET POLICY, not consensus: it belongs on the command line, it may differ
# per node without forking anything, and raising it changes no chain parameter. Derived
# from the configured fee rather than hardcoded, so the two cannot drift apart.
MAXTXFEE="$(awk -v r="$FEE_RAW" 'BEGIN{printf "%.8f", (r/100000000)*10}')"

SETUP_FLOOR="$(fl_setup_first_blocks_floor "$EPOCH_LEN")"
SETUP_BLOCKS="${SMOKE_SETUP_BLOCKS:-$(fl_setup_blocks_for_network "$NODES" "$EPOCH_LEN")}"
[ "$SETUP_BLOCKS" -ge "$SETUP_FLOOR" ] || SETUP_BLOCKS="$SETUP_FLOOR"
VERIFY_HEIGHT="$(fl_height_for_buried_epoch $(( EPOCHS + 1 )) "$EPOCH_LEN")"
TARGET_HEIGHT=$(( VERIFY_HEIGHT + FL_STABILITY_MARGIN + 9 ))
[ "$TARGET_HEIGHT" -gt "$SETUP_BLOCKS" ] || TARGET_HEIGHT=$(( SETUP_BLOCKS + EPOCH_LEN ))
EPOCH_DRIVE_TIMEOUT="${SMOKE_EPOCH_TIMEOUT:-$(( EPOCH_LEN * TARGET_BLOCK_TIME * 6 + 300 ))}"

trap fl_teardown EXIT

fl_phase "PLAN — $NODES nodes, $EPOCHS epochs of $EPOCH_LEN blocks, no network emulation"
cat <<PLAN
  topology
    admin / genesis (treasury funder)   1
    miners      (validators, restitute) $MINERS
    companies   (informative tx only)   $COMPANIES
    certification authorities           $CAS
    ----------------------------------- ----
    total nodes                         $NODES

  chain parameters (params.dat — hash-enforced, inherited by joining nodes)
    weight-epoch-length                 $EPOCH_LEN
    weight-lambda                       $LAMBDA
    wpoa-randao-lookback (k)            $LOOKBACK
    first-block-reward                  $PREMINE_RAW raw ($(awk -v p="$PREMINE_RAW" 'BEGIN{printf "%.0f", p/100000000}') GAS premined to the admin)
    initial-block-reward                0            (premined currency: thesis 4.2.1)
    minimum-relay-fee                   $FEE_RAW raw ($FEE_PER_KB GAS per 1000 bytes)
    -maxtxfee (wallet policy, per node) $MAXTXFEE      (must exceed the relay fee of the
                                        largest transaction, or nothing publishes)
    setup-first-blocks                  $SETUP_BLOCKS (floor $SETUP_FLOOR)
    target-block-time                   $TARGET_BLOCK_TIME

  economic model (thesis 4.2.1 / 4.3.1, Def. 6.6-6.10)
    company informative tx / epoch      random $TX_MIN..$TX_MAX, drawn per company per epoch
    miner restitutions / epoch          random $RESTIT_MIN..$RESTIT_MAX, distinct amounts
    company GAS seed / floor / top-up   $GAS_SEED / $GAS_FLOOR / $GAS_TOPUP
    miner GAS seed                      $MINER_SEED
    horizontal GAS transfers            FORBIDDEN, and asserted absent

  block arithmetic
    epoch $EPOCHS verified at                 $VERIFY_HEIGHT
    TOTAL BLOCKS TO MINE                $TARGET_HEIGHT
    output directory                    $FL_OUTPUT_ROOT

  mode                                  $( [ "$FAST" = "1" ] && echo "--fast ($EPOCHS epochs)" || echo "full ($EPOCHS epochs)" )
PLAN

# ---- roles ------------------------------------------------------------------
declare -a FL_ROLE=(admin)
declare -a MINER_IDX=() COMPANY_IDX=() CA_IDX=()
for ((i = 0; i < MINERS; i++));    do FL_ROLE+=(miner);   MINER_IDX+=($(( ${#FL_ROLE[@]} - 1 ))); done
for ((i = 0; i < COMPANIES; i++)); do FL_ROLE+=(company); COMPANY_IDX+=($(( ${#FL_ROLE[@]} - 1 ))); done
for ((i = 0; i < CAS; i++));       do FL_ROLE+=(ca);      CA_IDX+=($(( ${#FL_ROLE[@]} - 1 ))); done

export FL_PARAM_OVERRIDES="setup-first-blocks = $SETUP_BLOCKS
weight-epoch-length = $EPOCH_LEN
weight-lambda = $LAMBDA
wpoa-randao-lookback = $LOOKBACK
first-block-reward = $PREMINE_RAW
initial-block-reward = 0
minimum-relay-fee = $FEE_RAW
${FL_PARAM_OVERRIDES:-}"

ENGINE_ARGS="-enablewpoa=1 -enableweightengine=1 -debug=wpoa -maxtxfee=$MAXTXFEE"

fl_phase "SETUP — bootstrapping $NODES nodes"
fl_require_binaries
fl_start_role_network "$ENGINE_ARGS"

EFFECTIVE_SETUP="$(fl_chain_param 0 setup-first-blocks)"
[ -n "$EFFECTIVE_SETUP" ] || fl_die "could not read setup-first-blocks from getblockchainparams"
fl_log "effective setup-first-blocks on chain: $EFFECTIVE_SETUP (derived floor $SETUP_FLOOR)"

fl_check_begin "chain_parameters_in_force" 1
    fl_assert_eq "$(fl_chain_param 0 weight-epoch-length)" "$EPOCH_LEN" "weight-epoch-length on chain"
    fl_assert_eq "$(fl_chain_param 0 wpoa-randao-lookback)" "$LOOKBACK" "wpoa-randao-lookback on chain"
    if [ "$EFFECTIVE_SETUP" -ge "$SETUP_FLOOR" ]; then
        fl_ok "setup-first-blocks=$EFFECTIVE_SETUP is at or above the floor $SETUP_FLOOR"
    else
        fl_bad "setup-first-blocks=$EFFECTIVE_SETUP is BELOW the floor $SETUP_FLOOR"
    fi
    ibr="$(fl_chain_param 0 initial-block-reward)"
    if [ "${ibr:-0}" = "0" ]; then
        fl_ok "initial-block-reward is 0: the currency is premined, per thesis 4.2.1"
    else
        fl_bad "initial-block-reward is '$ibr', not 0: that is incremental minting, which 4.2.1 excludes"
    fi
fl_check_end || true

# ---- addresses --------------------------------------------------------------
fl_phase "ADDRESSES"
declare -a ADDR=()
for ((i = 0; i < NODES; i++)); do
    a="$(fl_node_address "$i")"
    [ -n "$a" ] || fl_die "node $i (${FL_ROLE[i]}) has no address"
    ADDR+=("$a")
done
ADMIN="${ADDR[0]}"
fl_log "admin: $ADMIN"

# ---- treasury ---------------------------------------------------------------
# A DEDICATED address, never the admin's. With the admin as treasury, a refuel's own
# change output pays the treasury and is spared only by the `signer == treasury` guard in
# mc_AccumulateReconciliation. That guard is correct, but a suite whose job is to prove
# the direction rule must not depend on it.
fl_phase "TREASURY — a dedicated address, set on every node by restart"
TREASURY="$(fl_make_treasury_address 0)"
[ -n "$TREASURY" ] || fl_die "could not create a treasury address"
fl_log "treasury: $TREASURY (distinct from the admin $ADMIN)"
ENGINE_ARGS="$ENGINE_ARGS -weighttreasuryaddress=$TREASURY"
fl_restart_all_nodes "$ENGINE_ARGS"

fl_check_begin "network_up_with_treasury" 1
    down=0
    for ((i = 0; i < NODES; i++)); do
        fl_cli "$i" getinfo >/dev/null 2>&1 || { fl_bad "node $i (${FL_ROLE[i]}) is not serving RPC"; down=$(( down + 1 )); }
    done
    fl_assert_zero "$down" "nodes not serving RPC after the treasury restart"
    fl_assert_eq "$([ "$TREASURY" != "$ADMIN" ] && echo distinct || echo same)" "distinct" \
        "treasury is a dedicated address, so a refuel cannot reach R_k"
fl_check_end || true

# ---- recording --------------------------------------------------------------
EXPERIMENT="${SMOKE_NAME:-smoke-$( [ "$FAST" = "1" ] && echo fast || echo full )-e${EPOCHS}-l${LAMBDA}-$(date +%Y%m%d-%H%M%S)}"
fl_record_begin "$EXPERIMENT" || fl_log "continuing without recording"
fl_smoke_record_begin
fl_record_meta "$EXPERIMENT" "$(printf '{"miners": %s, "companies": %s, "cas": %s, "epoch_len": %s, "epochs": %s, "lookback": %s, "lambda": "%s", "setup_first_blocks": %s, "target_block_time": %s, "premine_raw": %s, "initial_block_reward": 0, "min_relay_fee_raw": %s, "tx_per_epoch": "%s-%s", "restitutions_per_epoch": "%s-%s", "treasury": "%s", "fast": %s}' \
    "$MINERS" "$COMPANIES" "$CAS" "$EPOCH_LEN" "$EPOCHS" "$LOOKBACK" "$LAMBDA" \
    "$EFFECTIVE_SETUP" "$TARGET_BLOCK_TIME" "$PREMINE_RAW" "$FEE_RAW" \
    "$TX_MIN" "$TX_MAX" "$RESTIT_MIN" "$RESTIT_MAX" "$TREASURY" "$FAST")"

# ---- permissions, streams, engine inputs ------------------------------------
fl_phase "INPUTS — permissions, the event stream, membership and ESG"
for ((i = 0; i < NODES; i++)); do
    fl_cli 0 grant "${ADDR[i]}" weight-engine-membership.write >/dev/null 2>&1 || true
done
for idx in "${CA_IDX[@]}"; do
    fl_cli 0 grant "${ADDR[idx]}" high1 >/dev/null 2>&1 && fl_log "node $idx: granted high1 (CA role)"
    fl_cli 0 grant "${ADDR[idx]}" weight-engine-esg.write >/dev/null 2>&1
done
for idx in "${MINER_IDX[@]}"; do
    fl_cli 0 grant "${ADDR[idx]}" wpoa-weights.write >/dev/null 2>&1 || true
done

# The informative transactions need a stream of their own. Deliberately NOT one of the
# weight-engine streams: publishing test payloads onto weight-engine-membership would
# feed the engine's own input with noise and make tau indistinguishable from a
# malformed-record test.
# CLOSED (`false`), so writing needs an explicit per-stream grant. An open stream would
# let any node with `send` publish, which would make the informative traffic
# indistinguishable from anything else on the chain and would quietly permit a role that
# is supposed to generate no activity to generate some.
fl_cli 0 create stream "$EVENT_STREAM" false >/dev/null 2>&1 \
    && fl_log "created the informative stream '$EVENT_STREAM' (closed; companies granted .write below)" \
    || fl_log "note: '$EVENT_STREAM' may already exist"
sleep $(( TARGET_BLOCK_TIME * 3 ))
for idx in "${COMPANY_IDX[@]}"; do
    fl_cli 0 grant "${ADDR[idx]}" "$EVENT_STREAM.write" >/dev/null 2>&1 || true
done
fl_log "waiting for the grants to confirm..."
sleep $(( TARGET_BLOCK_TIME * 6 ))

# ---- seed GAS ---------------------------------------------------------------
fl_phase "GAS — seeding from the premine (admin -> node only)"
admin_bal="$(fl_native_balance 0)"
fl_log "admin native balance: $admin_bal"
if fl_is_zero "$admin_bal"; then
    fl_die "the admin holds NO native currency: first-block-reward did not take effect. Without it R_k is 0 and every economic assertion below is vacuous."
fi
seeded=0
for idx in "${COMPANY_IDX[@]}" "${CA_IDX[@]}"; do
    txid="$(fl_cli 0 sendtoaddress "${ADDR[idx]}" "$GAS_SEED" 2>/dev/null | tr -d '"[:space:]')"
    fl_is_txid "$txid" && seeded=$(( seeded + 1 ))
done
for idx in "${MINER_IDX[@]}"; do
    txid="$(fl_cli 0 sendtoaddress "${ADDR[idx]}" "$MINER_SEED" 2>/dev/null | tr -d '"[:space:]')"
    fl_is_txid "$txid" && seeded=$(( seeded + 1 ))
done
sleep $(( TARGET_BLOCK_TIME * 4 ))
fl_check_begin "gas_seeded" 1
    fl_assert_eq "$seeded" "$(( NODES - 1 ))" "non-admin nodes funded from the premine"
fl_check_end || true

# ---- membership + ESG -------------------------------------------------------
for ((i = 0; i < NODES; i++)); do
    fl_cli "$i" weightregistermembership "${ADDR[i]}" >/dev/null 2>&1 \
        || fl_log "WARNING: node $i could not self-register membership"
done
ca_n=${#CA_IDX[@]}; ci=0
for idx in "${MINER_IDX[@]}" "${COMPANY_IDX[@]}"; do
    ca=${CA_IDX[$(( ci % ca_n ))]}
    fl_cli "$ca" weightsetesg "${ADDR[idx]}" "$ESG_SCORE" >/dev/null 2>&1 \
        || fl_log "WARNING: CA node $ca could not certify node $idx"
    ci=$(( ci + 1 ))
done
sleep $(( TARGET_BLOCK_TIME * 6 ))

# ---- the direction rule, both ways, before the long run ---------------------
fl_phase "DIRECTION — a refuel is not a reconciliation; a miner transfer is"
fl_check_begin "reconciliation_direction" 1
    probe_c="${COMPANY_IDX[0]}"
    refuel_tx="$(fl_refuel_node "$probe_c" "$GAS_TOPUP")"
    if [ -n "$refuel_tx" ]; then
        paid="$(fl_tx_value_to_address 0 "$refuel_tx" "$TREASURY")"
        if fl_is_zero "$paid"; then
            fl_ok "admin -> node pays the treasury 0, so a refuel is NOT a reconciliation"
        else
            fl_bad "an admin -> node refuel paid $paid to the treasury: it WOULD count as one"
        fi
    else
        fl_bad "could not issue a refuel to probe the direction rule"
    fi
    # POSITIVE CONTROL from a MINER, because that is the actor whose R_k is read.
    probe_m="${MINER_IDX[0]}"
    recon_tx="$(fl_cli "$probe_m" sendtoaddress "$TREASURY" 7 2>/dev/null | tr -d '"[:space:]')"
    if fl_is_txid "$recon_tx"; then
        sleep $(( TARGET_BLOCK_TIME * 3 ))
        paid2="$(fl_tx_value_to_address "$probe_m" "$recon_tx" "$TREASURY")"
        if fl_is_zero "$paid2"; then
            fl_bad "a miner -> treasury transfer registered 0: the probe cannot see reconciliations at all"
        else
            fl_ok "miner -> treasury pays the treasury $paid2, so reconciliations ARE detectable"
        fi
    else
        fl_bad "miner node $probe_m could not pay the treasury (out of gas?)"
    fi
fl_check_end || true

# ---- readiness --------------------------------------------------------------
fl_phase "READINESS — the registry must be usable before wPoA engages at $EFFECTIVE_SETUP"
fl_check_begin "registry_ready_before_wpoa" 1
    want_ready=$(( MINERS / 2 )); [ "$want_ready" -lt 1 ] && want_ready=1
    if fl_wait_registry_ready "$want_ready" $(( EFFECTIVE_SETUP * TARGET_BLOCK_TIME )) "$EFFECTIVE_SETUP"; then
        fl_ok "the registry carries scoreable weights at height $(fl_tip_height 0) < $EFFECTIVE_SETUP"
    else
        fl_bad "the registry was NOT usable before wPoA engaged -- the run cannot proceed"
        fl_check_end || true
        fl_record_finish; fl_teardown; trap - EXIT
        fl_check_summary || true
        echo "SMOKE TEST FAILED: the weight registry was not ready before wPoA engaged." >&2
        exit 1
    fi
fl_check_end || true

# ---- the run ----------------------------------------------------------------
fl_phase "RUN — $TARGET_HEIGHT blocks, economics driven and recorded each epoch"

REFUELS=0; REFUEL_FAILURES=0; STALLED=0
CURRENT_EPOCH=0; EPOCH_REFUELS=0
LAST_RECORDED_HEIGHT=$EFFECTIVE_SETUP
VERIFY_SAMPLES=0; VERIFY_MISMATCH=0; VERIFY_NOTCLUSTER=0; VERIFY_OTHER_EPOCH=0
VERIFY_INVALID_DISAGREE=0; MAX_VERIFIED_EPOCH=0
TOTAL_INFORMATIVE=0; TOTAL_RESTITUTIONS=0
RESTITUTION_TOTAL=0

monitor_gas() {
    local i bal txid
    for ((i = 1; i < NODES; i++)); do
        bal="$(fl_native_balance "$i")"
        if fl_lt "$bal" "$GAS_FLOOR"; then
            txid="$(fl_refuel_node "$i" "$GAS_TOPUP")"
            if [ -n "$txid" ]; then
                REFUELS=$(( REFUELS + 1 )); EPOCH_REFUELS=$(( EPOCH_REFUELS + 1 ))
                fl_record_refuel "$CURRENT_EPOCH" "$i" "$bal" "$(fl_native_balance "$i")" "$GAS_TOPUP" "$txid"
            else
                REFUEL_FAILURES=$(( REFUEL_FAILURES + 1 ))
            fi
        fi
    done
}

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
        VERIFY_MISMATCH=$(( VERIFY_MISMATCH + mm ))
        VERIFY_NOTCLUSTER=$(( VERIFY_NOTCLUSTER + nc ))
        VERIFY_OTHER_EPOCH=$(( VERIFY_OTHER_EPOCH + oe ))
        EPOCH_MISMATCH=$(( EPOCH_MISMATCH + mm ))
        EPOCH_NOTCLUSTER=$(( EPOCH_NOTCLUSTER + nc ))
        EPOCH_OTHER=$(( EPOCH_OTHER + oe ))
        [ "$ve" -gt "$EPOCH_VERIFIED" ] && EPOCH_VERIFIED="$ve"
        # other-epoch and unverified are NOT findings (mc_WeightVerdictIsInvalid), so the
        # invalid counter must equal exactly mismatch + not-a-cluster.
        [ "$inv" -eq $(( mm + nc )) ] || VERIFY_INVALID_DISAGREE=$(( VERIFY_INVALID_DISAGREE + 1 ))
    done
}

# Companies generate INFORMATIVE transactions: stream publications, never GAS transfers.
# The count is drawn independently per company per epoch, as the model requires -- a fixed
# count gives tau no variance and nothing in the weight pipeline moves.
generate_informative_activity() {
    # TWO counters, and they must not be conflated. `sent` is this COMPANY's published
    # count and resets per company; `epoch_sent` is the epoch total. A single accumulator
    # writes a running total into every company's row, so informative.csv reads as though
    # each company published more than the last -- a silently corrupted per-company tau
    # rather than a visible failure. Observed on the first real run.
    local epoch=$1 idx n j txid key payload sent=0 epoch_sent=0
    for idx in "${COMPANY_IDX[@]}"; do
        n=$(fl_rand_between "$TX_MIN" "$TX_MAX")
        sent=0
        for ((j = 0; j < n; j++)); do
            key="lot-$epoch-$idx-$j"
            # A hex payload standing in for the lavorazione / passaggio di proprietà
            # record: an information carrier with no monetary value, exactly as 4.2.1
            # describes. It pays a fee and creates NO transfer between companies.
            payload="$(printf 'epoch=%s node=%s seq=%s ts=%s' "$epoch" "$idx" "$j" "$(date +%s)" | od -An -tx1 | tr -d ' \n')"
            txid="$(fl_cli "$idx" publish "$EVENT_STREAM" "$key" "$payload" 2>/dev/null | tr -d '"[:space:]')"
            if fl_is_txid "$txid"; then
                sent=$(( sent + 1 ))
                epoch_sent=$(( epoch_sent + 1 ))
                TOTAL_INFORMATIVE=$(( TOTAL_INFORMATIVE + 1 ))
            fi
        done
        fl_record_informative "$epoch" "$idx" "${ADDR[idx]}" "$n" "$sent"
    done
    fl_log "  informative transactions published this epoch: $epoch_sent"
}

# Miners restitute to the treasury: the ONLY flow that produces R_k, because
# weight_engine.cpp reads r_e[miner_address] and nothing else. The count is random per
# miner per epoch (0 is allowed: a miner may return nothing), and every amount within one
# miner-epoch is DISTINCT, so a constant never masquerades as a measurement.
generate_restitution() {
    local epoch=$1 idx n j amount txid bal
    for idx in "${MINER_IDX[@]}"; do
        n=$(fl_rand_between "$RESTIT_MIN" "$RESTIT_MAX")
        [ "$n" -gt 0 ] || { fl_record_restitution_none "$epoch" "$idx" "${ADDR[idx]}"; continue; }
        local used=""
        for ((j = 0; j < n; j++)); do
            bal="$(fl_native_balance "$idx")"
            amount="$(fl_distinct_amount "$used")"
            # Never return more than is held: the ledger would refuse it, and Oss. 6.1
            # makes the balance the natural cap on R_k anyway.
            if fl_lt "$bal" "$amount"; then continue; fi
            txid="$(fl_cli "$idx" sendtoaddress "$TREASURY" "$amount" 2>/dev/null | tr -d '"[:space:]')"
            if fl_is_txid "$txid"; then
                used="$used $amount"
                TOTAL_RESTITUTIONS=$(( TOTAL_RESTITUTIONS + 1 ))
                RESTITUTION_TOTAL="$(awk -v a="$RESTITUTION_TOTAL" -v b="$amount" 'BEGIN{printf "%.8f", a+b}')"
                fl_record_restitution "$epoch" "$idx" "${ADDR[idx]}" "$amount" "$txid"
            fi
        done
    done
}

for ((e = 1; e <= EPOCHS; e++)); do
    want=$(fl_height_for_buried_epoch "$e" "$EPOCH_LEN")
    [ "$want" -lt "$EFFECTIVE_SETUP" ] && want=$(( EFFECTIVE_SETUP + FL_STABILITY_MARGIN ))

    CURRENT_EPOCH=$e
    generate_informative_activity "$e"
    generate_restitution "$e"

    if ! fl_drive_to_height "$want" "$EPOCH_DRIVE_TIMEOUT" "stall while covering epoch $e of $EPOCHS"; then
        fl_log "  STALL: did not reach height $want for epoch $e within ${EPOCH_DRIVE_TIMEOUT}s"
        STALLED=1
        break
    fi
    EPOCH_REFUELS=0
    monitor_gas
    monitor_verification

    h_now="$(fl_tip_height 0)"; h_now="${h_now:-0}"
    fl_record_weights "$e"
    fl_record_gas "$e"
    fl_record_malus_snapshot "$e" "${MINER_IDX[*]}" "${ADDR[*]}"
    fl_record_epoch "$e" "$h_now" "${EPOCH_VERIFIED:-0}" "${EPOCH_MISMATCH:-0}" \
                    "${EPOCH_NOTCLUSTER:-0}" "${EPOCH_OTHER:-0}" "$EPOCH_REFUELS"
    if [ "$h_now" -gt "$LAST_RECORDED_HEIGHT" ]; then
        fl_record_proposers $(( LAST_RECORDED_HEIGHT + 1 )) "$h_now"
        LAST_RECORDED_HEIGHT="$h_now"
    fi
    fl_log "epoch $e/$EPOCHS at height $h_now | informative=$TOTAL_INFORMATIVE restitutions=$TOTAL_RESTITUTIONS refuels=$REFUELS verified<=$MAX_VERIFIED_EPOCH"
done

if [ "$STALLED" = "0" ]; then
    fl_log "driving past the final epoch so epoch $EPOCHS can be verified (needs $VERIFY_HEIGHT)"
    fl_drive_to_height "$TARGET_HEIGHT" $(( EPOCH_DRIVE_TIMEOUT * 3 )) "stall while burying the final epoch" || STALLED=1
    CURRENT_EPOCH=$(( EPOCHS + 1 )); EPOCH_REFUELS=0
    monitor_gas; monitor_verification
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
    if [ "$FINAL_EPOCH" -ge "$EPOCHS" ]; then
        fl_ok "covered $FINAL_EPOCH buried epochs, at or beyond the required $EPOCHS"
    else
        fl_bad "only $FINAL_EPOCH epochs buried of $EPOCHS (height $FINAL_HEIGHT of $TARGET_HEIGHT)"
    fi
    fl_assert_zero "$STALLED" "stalls while driving the chain"
fl_check_end || true

fl_check_begin "economic_activity_generated" 1
    fl_log "informative transactions: $TOTAL_INFORMATIVE   restitutions: $TOTAL_RESTITUTIONS (total $RESTITUTION_TOTAL GAS)"
    fl_assert_gt0 "$TOTAL_INFORMATIVE" "informative transactions published by companies"
    # A run where no miner ever restituted cannot say anything about the feedback, so this
    # is a hard failure rather than a note: R_k would be 0 for every cluster and rho would
    # be pinned exactly as it was in the revision this suite replaces.
    fl_assert_gt0 "$TOTAL_RESTITUTIONS" "restitution transfers issued by miners (R_k would be 0 without them)"
fl_check_end || true

fl_check_begin "no_horizontal_gas_transfers" 1
    # The mandate's explicit assertion, made over the RECORDED DATA rather than by
    # trusting that the generator only issued legitimate flows. Legitimate directions are
    # admin -> node and node -> treasury; anything else between two non-admin,
    # non-treasury addresses is the bug this forbids.
    fl_smoke_assert_no_horizontal_gas "$ADMIN" "$TREASURY" "${ADDR[*]}"
fl_check_end || true

fl_check_begin "restitution_reached_the_engine" 1
    # R_k is exposed by no RPC, so the observable proxy is the treasury's own balance: it
    # can only have been paid by the miners, since the admin never pays it and the
    # companies never transfer GAS at all.
    t_recv="$(fl_cli 0 getaddressbalances "$TREASURY" 2>/dev/null | sed -nE 's/.*"qty"[[:space:]]*:[[:space:]]*([0-9.]+).*/\1/p' | head -n1)"
    fl_log "treasury balance: ${t_recv:-unknown}   restitution issued: $RESTITUTION_TOTAL GAS"
    if [ -n "$t_recv" ] && ! fl_is_zero "$t_recv"; then
        fl_ok "the treasury holds $t_recv GAS, so reconciliation transfers did confirm on chain"
    else
        fl_bad "the treasury holds nothing: no reconciliation reached the chain, so R_k is 0 everywhere"
    fi
fl_check_end || true

fl_check_begin "verification_clean_across_epochs" 1
    fl_log "verification sampled $VERIFY_SAMPLES time(s); highest verified epoch $MAX_VERIFIED_EPOCH"
    fl_log "  mismatch=$VERIFY_MISMATCH  not-a-cluster=$VERIFY_NOTCLUSTER  other-epoch=$VERIFY_OTHER_EPOCH"
    fl_assert_gt0  "$VERIFY_SAMPLES"    "verification reports sampled during the run"
    fl_assert_zero "$VERIFY_MISMATCH"   "mismatch verdicts (every node here is honest)"
    fl_assert_zero "$VERIFY_NOTCLUSTER" "not-a-cluster verdicts (every miner is a registered cluster)"
    fl_assert_zero "$VERIFY_INVALID_DISAGREE" \
        "samples where invalid != mismatch + not-a-cluster (other-epoch counted as a finding)"
    fl_log "note: other-epoch is EXPECTED -- verification targets e-1 while the tip is in e."
fl_check_end || true

fl_check_begin "no_malus_false_positives" 1
    bad_psi=0
    for idx in "${MINER_IDX[@]}"; do
        m="$(fl_cli 0 getnodemalus "${ADDR[idx]}" 2>/dev/null)"
        psi="$(printf '%s' "$m" | sed -nE 's/.*"psi"[[:space:]]*:[[:space:]]*([0-9.]+).*/\1/p' | head -n1)"
        w="$(  printf '%s' "$m" | sed -nE 's/.*"weight"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' | head -n1)"
        eff="$(printf '%s' "$m" | sed -nE 's/.*"effective"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' | head -n1)"
        if [ "${psi:-0}" != "1" ] || [ "${eff:-x}" != "${w:-y}" ]; then
            fl_bad "miner node $idx carries a malus after an honest run: psi=$psi weight=$w effective=$eff"
            bad_psi=$(( bad_psi + 1 ))
        fi
    done
    fl_assert_zero "$bad_psi" "honest miners carrying an accumulated malus"
fl_check_end || true

fl_check_begin "weights_agree_across_nodes" 1
    ref="$(fl_node_total 0)"; mism=0
    for idx in "${MINER_IDX[@]}"; do
        ti="$(fl_node_total "$idx")"
        [ -n "$ti" ] && [ "$ti" != "$ref" ] && { fl_bad "node $idx total=$ti != node 0 total=$ref"; mism=$(( mism + 1 )); }
    done
    fl_assert_zero "$mism" "miners disagreeing on the aggregate weight (node 0 = $ref)"
fl_check_end || true

fl_check_begin "no_persistent_fork" 1
    # Collected from EVERY node, never derived from the admin: a fork is two nodes holding
    # different hashes at one height, and one node sees one hash and calls it the chain
    # (experiments/docs/metrics.md).
    probe=$(( FINAL_HEIGHT - FL_STABILITY_MARGIN )); [ "$probe" -lt 1 ] && probe=1
    ref="$(fl_blockhash_at 0 "$probe")"; mism=0
    for ((i = 1; i < NODES; i++)); do
        hi="$(fl_blockhash_at "$i" "$probe")"
        [ -n "$hi" ] && [ "$hi" != "$ref" ] && { fl_bad "fork: node $i block $probe differs"; mism=$(( mism + 1 )); }
    done
    fl_assert_zero "$mism" "nodes disagreeing on the chain at buried height $probe"
fl_check_end || true

fl_check_begin "gas_never_ran_out" 1
    fl_log "refuels issued: $REFUELS   failures: $REFUEL_FAILURES"
    dry=0
    for ((i = 1; i < NODES; i++)); do
        bal="$(fl_native_balance "$i")"
        if fl_is_zero "$bal"; then
            fl_bad "node $i (${FL_ROLE[i]}) ended with a ZERO balance: it could no longer transact"
            dry=$(( dry + 1 ))
        fi
    done
    fl_assert_zero "$dry"             "nodes that ran out of native currency"
    fl_assert_zero "$REFUEL_FAILURES" "refuel transactions the admin could not issue"
fl_check_end || true

# =============================================================================
# STATISTICS AND FIGURES
# =============================================================================
fl_record_finish
STATS_RC=0
if [ -n "$FL_RUN_DIR" ]; then
    fl_record_analyse --draws "${SMOKE_MC_DRAWS:-50000}" --alpha "${SMOKE_ALPHA:-0.01}" || STATS_RC=$?
    [ -f "$FL_RUN_DIR/summary.txt" ] && { echo; sed 's/^/  /' "$FL_RUN_DIR/summary.txt"; }
    fl_phase "FIGURES"
    python3 "$FL_LIB_DIR/stats/plots.py" "$FL_RUN_DIR" 2>&1 | sed 's/^/  /'
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
    echo "Recorded run, analysis and figures: $FL_RUN_DIR"
    echo "  report.md / summary.txt        the verdicts"
    echo "  plots/                         the figures, with plots/README.md naming each source"
    echo "  informative.csv restitution.csv malus.csv   the economic observations"
fi

if fl_check_summary; then
    echo
    echo "SMOKE TEST PASSED ($NODES nodes, $FINAL_EPOCH epochs of $EPOCH_LEN blocks,"
    echo "$TOTAL_INFORMATIVE informative tx, $TOTAL_RESTITUTIONS restitutions, $REFUELS refuels)."
    exit 0
fi
echo
echo "SMOKE TEST FAILED." >&2
exit 1
