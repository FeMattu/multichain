#!/usr/bin/env bash
# ADMIN NODE - Apuana SB.
#
#   phase 'grant'       : grants every node its permissions, creates the
#                         application stream, delegates the Certification
#                         Authority role, imports the treasury watch-only and
#                         distributes the initial GAS.
#   phase 'refill'      : GAS refill loop. Polls each node's balance and tops
#                         it up when it falls below the threshold, so that no
#                         run ever stops because a node ran out of units
#                         (thesis 4.2.1: Apuana SB sells GAS to its client
#                         companies and acts as the clearing house).
#   phase 'epoch_watch' : epoch sampler. Once an epoch is closed AND buried it
#                         records what would no longer be reconstructible at
#                         the end of the run, under raw/metrics/epochs/. Three
#                         things, and only those:
#                           * weightverifyweights, which reports only the LAST
#                             epoch the node verified: the final snapshot would
#                             keep exactly one;
#                           * every node's height and best hash, which is what
#                             makes a fork that healed mid-run visible - the
#                             end-of-run node_state.csv would not show it;
#                           * the treasury balance as a series rather than as
#                             one final number.
#   phase 'snapshot'    : final dump of the chain state. It is the primary
#                         source of every metric: listblocks reports the
#                         proposer of each height directly, which is far more
#                         reliable than parsing debug.log.
#
# No 'set -e' on purpose. These are supervisors that must survive a transient
# RPC failure: a refill loop that exits because one getbalance timed out would
# take the whole run with it. Failures are handled where they happen and
# logged; -E and the trap below make sure an unexpected one is still visible.
set -Euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

trap 'log "unexpected failure at line $LINENO (phase ${PHASE:-?})"' ERR

PHASE="${1:-grant}"
IP="$POESIA_IP"
MINERS="${POESIA_MINERS:-}"
COMPANIES="${POESIA_COMPANIES:-}"
CAS="${POESIA_CAS:-}"
ADMIN_HOST="${POESIA_ADMIN:-admin}"
GAS_COMPANY="${POESIA_GAS_COMPANY:-100}"     # initial endowment of a company
GAS_MINER="${POESIA_GAS_MINER:-50}"          # miner float, to be able to reconcile
GAS_THRESHOLD="${POESIA_GAS_THRESHOLD:-20}"  # below this, top up
GAS_TOPUP="${POESIA_GAS_TOPUP:-100}"         # size of a top-up
REFILL_EVERY="${POESIA_REFILL_EVERY:-30}"    # seconds between two checks
STREAM="${POESIA_STREAM:-poesia-supplychain}"
EPOCHLEN="${POESIA_EPOCHLEN:-12}"

grant_one() {   # grant_one <addr> <permissions>
    local addr=$1 perms=$2
    if rpc_ok "$IP" grant "[\"$addr\",\"$perms\"]"; then
        log "grant $perms -> $addr"
    else
        log "WARNING: grant $perms -> $addr failed: $(rpc_err "$IP" grant "[\"$addr\",\"$perms\"]")"
    fi
}

do_grant() {
    wait_rpc "$IP" 600 || exit 1
    local own; own="$(rpc_result "$IP" getaddresses | grep -oE '[A-Za-z0-9]{30,40}' | head -n1)"
    echo "$own" > "$SHARED/$ADMIN_HOST.addr"
    log "admin address (Apuana SB): $own"

    # Wait for every node to have deposited its address.
    local t=0 missing
    while [ "$t" -lt 300 ]; do
        missing=""
        for h in $MINERS $COMPANIES $CAS; do
            [ -s "$SHARED/$h.addr" ] || missing="$missing $h"
        done
        [ -z "$missing" ] && break
        sleep 5; t=$((t + 5))
    done
    [ -n "$missing" ] && log "WARNING: addresses still missing:$missing"

    # --- base permissions ---------------------------------------------------
    for h in $MINERS; do
        grant_one "$(addr_of "$h")" "connect,send,receive,mine"
    done
    for h in $COMPANIES $CAS; do
        grant_one "$(addr_of "$h")" "connect,send,receive"
    done

    # --- stream write permissions -------------------------------------------
    # One stream per call: grant addr "a.write,b.write" is rejected by
    # MultiChain with "Could not parse entity key".
    #
    # wpoa-weights MUST be created explicitly by the admin. With the weight
    # engine on, the registry does not create it until it has a weight to
    # publish, and it has no weight until membership and ESG records exist ->
    # without this create the network stalls at setup-first-blocks with
    # "cannot score (unsynced or unweighted)". It is created CLOSED, exactly as
    # StreamWeightRegistry::EnsureStreamExists() would.
    if rpc_ok "$IP" create '["stream","wpoa-weights",false]'; then
        log "stream wpoa-weights created (closed)"
    else
        log "stream wpoa-weights already present"
    fi
    wait_stream "$IP" wpoa-weights 900 || log "WARNING: wpoa-weights not confirmed"
    wait_stream "$IP" weight-engine-membership 900 || true
    wait_stream "$IP" weight-engine-esg 900 || true
    for h in $MINERS $COMPANIES; do
        grant_one "$(addr_of "$h")" "wpoa-weights.write"
        grant_one "$(addr_of "$h")" "weight-engine-membership.write"
    done

    # The admin is not a cluster head, so it publishes no weight and the
    # registry does not subscribe it to wpoa-weights: without an explicit
    # subscribe the final snapshot and weightverifyweights would fail with
    # "Not subscribed to this stream". subscribe performs a rescan, so it also
    # indexes items already confirmed.
    for st in wpoa-weights weight-engine-esg weight-engine-membership wpoa-weights-malus; do
        rpc_ok "$IP" subscribe "[\"$st\"]" && log "subscribed to stream $st"
    done

    # --- Certification Authority role ---------------------------------------
    # high1 is the custom permission that carries the CA role
    # (weight_authorization.h). It is NOT implied by being an administrator: it
    # has to be delegated explicitly.
    for h in $CAS; do
        grant_one "$(addr_of "$h")" "high1"
        grant_one "$(addr_of "$h")" "weight-engine-esg.write"
    done

    # --- reconciliation treasury --------------------------------------------
    if [ -n "${POESIA_TREASURY:-}" ]; then
        grant_one "$POESIA_TREASURY" "receive"
        rpc_ok "$IP" importaddress "[\"$POESIA_TREASURY\",\"treasury\",false]" \
            && log "treasury imported watch-only: $POESIA_TREASURY"
    fi

    # --- application stream --------------------------------------------------
    if rpc_ok "$IP" create '["stream","'"$STREAM"'",true]'; then
        log "application stream created: $STREAM (open)"
    else
        log "stream $STREAM already present or not creatable"
    fi

    # --- initial GAS distribution --------------------------------------------
    # The premine (first-block-reward) is all here: Apuana SB sells GAS to the
    # companies and funds the miners' float so they can reconcile.
    for h in $COMPANIES; do
        if rpc_ok "$IP" send "[\"$(addr_of "$h")\",$GAS_COMPANY]"; then
            log "sent $GAS_COMPANY GAS to $h"
            csv gas_transfers.csv "$(rpc_result "$IP" getblockcount),init,$h,$GAS_COMPANY"
        fi
    done
    for h in $MINERS $CAS; do
        if rpc_ok "$IP" send "[\"$(addr_of "$h")\",$GAS_MINER]"; then
            log "sent $GAS_MINER GAS to $h"
            csv gas_transfers.csv "$(rpc_result "$IP" getblockcount),init,$h,$GAS_MINER"
        fi
    done
    log "grant phase complete"
}

do_refill() {
    wait_rpc "$IP" 600 || exit 1
    csvh gas_balances.csv "height,host,balance"
    log "GAS refill loop active (threshold ${GAS_THRESHOLD}, top-up ${GAS_TOPUP})"
    while true; do
        local h bal height
        height="$(rpc_result "$IP" getblockcount)"
        for h in $COMPANIES $MINERS $CAS; do
            local ip_var="POESIA_IP_${h}"
            local nip="${!ip_var:-}"
            [ -z "$nip" ] && continue
            bal="$(rpc_result "$nip" getbalance)"
            case "$bal" in ''|*[!0-9.]*) continue ;; esac
            csv gas_balances.csv "$height,$h,$bal"
            # floating-point comparison without bc
            if awk -v b="$bal" -v t="$GAS_THRESHOLD" 'BEGIN{exit !(b < t)}'; then
                if rpc_ok "$IP" send "[\"$(addr_of "$h")\",$GAS_TOPUP]"; then
                    log "REFILL: $h had $bal GAS -> +$GAS_TOPUP"
                    csv gas_transfers.csv "$height,refill,$h,$GAS_TOPUP"
                else
                    log "WARNING: refill of $h failed"
                fi
            fi
        done
        sleep "$REFILL_EVERY"
    done
}

# ---------------------------------------------------------------------------
# Epoch sampler
# ---------------------------------------------------------------------------
#
# STABILITY. An epoch is sampled only once it is closed AND buried under
# EPOCH_MARGIN blocks: the same margin the weight engine takes before it
# publishes an epoch's weight (Sec. 6.4). Sampling earlier would photograph a
# verdict the engine has not issued yet, and the row would read "not verified"
# for a reason of timing rather than of protocol.
EPOCH_MARGIN="${POESIA_EPOCH_MARGIN:-8}"
EPOCH_POLL="${POESIA_EPOCH_POLL:-10}"
SETUPBLOCKS="${POESIA_SETUPBLOCKS:-60}"

do_epoch_watch() {
    wait_rpc "$IP" 900 || exit 1
    local dir="$METRICS/epochs"
    mkdir -p "$dir"
    : > "$dir/verify_epochs.jsonl"
    echo "epoch,height_admin,host,height,besthash,peers" > "$dir/node_state_epochs.csv"
    echo "epoch,height,treasury_balance_gas"              > "$dir/treasury_epochs.csv"
    log "epoch sampler active (epochlen=$EPOCHLEN, margin=$EPOCH_MARGIN blocks)"

    # First epoch worth sampling: the one holding the first wPoA-governed
    # block. Epochs entirely inside setup have nothing to analyse, and sampling
    # them would only be a burst of RPC at start-up.
    local last=$(( SETUPBLOCKS / EPOCHLEN ))
    log "sampler: first epoch sampled is $(( last + 1 )) (setup = $SETUPBLOCKS blocks)"

    while true; do
        local h target
        h="$(rpc_result "$IP" getblockcount)"
        case "$h" in ''|*[!0-9]*) sleep "$EPOCH_POLL"; continue ;; esac

        # Epoch t is ready once the chain is EPOCH_MARGIN blocks past its last
        # block, i.e. h >= t*EPOCHLEN + margin. Inverted: t <= (h-margin)/EPOCHLEN.
        # ALL ready-and-unsampled epochs are taken, not just the latest: the
        # burial window is a few heights wide and with a low target-block-time
        # one sample per cycle would skip whole epochs.
        if [ "$h" -gt "$EPOCH_MARGIN" ]; then
            target=$(( (h - EPOCH_MARGIN) / EPOCHLEN ))
            while [ "$last" -lt "$target" ]; do
                last=$(( last + 1 ))
                sample_epoch "$last" "$h" "$dir"
            done
        fi
        sleep "$EPOCH_POLL"
    done
}

# sample_epoch <epoch> <current height> <dir>
sample_epoch() {
    local target=$1 h=$2 dir=$3
    log "epoch $target closed and buried (height $h): sampling"

    # 1. independent verification: this is the only moment the RPC speaks about
    #    THIS epoch, because it reports only the last one the node verified.
    local v; v="$(rpc "$IP" weightverifyweights)"
    printf '{"epoch_requested":%s,"height":%s,"verify":%s}\n' \
           "$target" "$h" "${v:-null}" >> "$dir/verify_epochs.jsonl"

    # 2. per-node state: a fork that heals before the end of the run leaves no
    #    other trace in node_state.csv, which is a final snapshot.
    local hh
    for hh in $ADMIN_HOST $MINERS $COMPANIES $CAS; do
        local ip_var="POESIA_IP_${hh}" nip
        nip="${!ip_var:-}"
        [ -z "$nip" ] && continue
        local nh bh pc
        nh="$(rpc_result "$nip" getblockcount)"
        bh="$(rpc_result "$nip" getbestblockhash | tr -d '\"')"
        pc="$(rpc "$nip" getpeerinfo | grep -o '"addr"' | wc -l)"
        echo "$target,$h,$hh,${nh:-n/d},${bh:-n/d},${pc:-0}" \
             >> "$dir/node_state_epochs.csv"
    done

    # 3. treasury balance: one number at the end of the run, a series here.
    if [ -n "${POESIA_TREASURY:-}" ]; then
        local tb
        tb="$(rpc "$IP" getaddressbalances "[\"$POESIA_TREASURY\"]" \
              | grep -oE '"qty":[0-9.]+' | head -n1 | cut -d: -f2)"
        echo "$target,$h,${tb:-n/d}" >> "$dir/treasury_epochs.csv"
    fi
}

# Final dump of the chain state: the primary source of every metric. Far more
# reliable than parsing debug.log, because listblocks reports the proposer of
# each height directly.
do_snapshot() {
    wait_rpc "$IP" 300 || exit 1
    local h; h="$(rpc_result "$IP" getblockcount)"
    log "final snapshot at height=$h"
    echo "$h" > "$METRICS/final_height.txt"

    rpc "$IP" listblocks "[\"1-$h\"]"                                    > "$METRICS/blocks.json"
    rpc "$IP" liststreamitems '["wpoa-weights",false,100000]'            > "$METRICS/weights.json"
    rpc "$IP" liststreamitems '["weight-engine-esg",false,10000]'        > "$METRICS/esg.json"
    rpc "$IP" liststreamitems '["weight-engine-membership",false,10000]' > "$METRICS/membership.json"
    rpc "$IP" liststreamitems '["wpoa-weights-malus",false,10000]'       > "$METRICS/malus.json"
    rpc "$IP" weightverifyweights                                        > "$METRICS/verify.json"
    rpc "$IP" getinfo                                                    > "$METRICS/admin_getinfo.json"
    rpc "$IP" listpermissions '["mine"]'                                 > "$METRICS/permissions_mine.json"

    # Per-node state: height and peer count, for persistent-fork detection.
    # The reference height is deliberately below the tip, so it has already
    # propagated everywhere even if a node is one block behind.
    local DEEP_HEIGHT=$(( h - 6 )); [ "$DEEP_HEIGHT" -lt 1 ] && DEEP_HEIGHT=1
    log "reference hash compared at height $DEEP_HEIGHT"
    csvh node_state.csv "host,height,besthash,hash_a_${DEEP_HEIGHT},peers,balance"
    local hh
    for hh in $ADMIN_HOST $MINERS $COMPANIES $CAS; do
        local ip_var="POESIA_IP_${hh}" nip
        nip="${!ip_var:-}"
        [ -z "$nip" ] && continue
        local nh nb bh pc dh
        nh="$(rpc_result "$nip" getblockcount)"
        bh="$(rpc_result "$nip" getbestblockhash | tr -d '\"')"
        # Buried hash at an ABSOLUTE height common to every node: using
        # "own height - 6" would make nodes at different heights compare
        # different blocks by construction, and an ordinary propagation delay
        # would be mistaken for a fork.
        dh="$(rpc_result "$nip" getblockhash "[$DEEP_HEIGHT]" | tr -d '\"')"
        [ -z "$dh" ] && dh="n/d"
        pc="$(rpc "$nip" getpeerinfo | grep -o '"addr"' | wc -l)"
        nb="$(rpc_result "$nip" getbalance)"
        csv node_state.csv "$hh,$nh,$bh,$dh,$pc,$nb"
    done

    if [ -n "${POESIA_TREASURY:-}" ]; then
        rpc "$IP" getaddressbalances "[\"$POESIA_TREASURY\"]" > "$METRICS/treasury_balance.json"
    fi
    log "snapshot complete"
}

case "$PHASE" in
    grant)       do_grant ;;
    refill)      do_refill ;;
    epoch_watch) do_epoch_watch ;;
    snapshot)    do_snapshot ;;
    *)           log "unknown phase: $PHASE"; exit 2 ;;
esac
