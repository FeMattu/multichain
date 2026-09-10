#!/usr/bin/env bash
# MINER NODE (validator, cluster head).
#
#   phase 'register'  : registers as the head of its own cluster on
#                       weight-engine-membership (a miner calls
#                       weightregistermembership with its OWN address).
#   phase 'reconcile' : each epoch, returns a fraction of the GAS collected in
#                       fees to the treasury. It is this transfer, derived from
#                       confirmed blocks and never declared, that constitutes
#                       R_k (Def. 6.7) and therefore the compliance rate rho_k
#                       that feeds back into the next epoch's weight
#                       (Def. 6.8-6.9).
#                       The rate differs per miner (POESIA_RECONCILE_RATE) so
#                       the rho_k diverge and the feedback is observable.
set -Euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

PHASE="${1:-register}"
IP="$POESIA_IP"
RATE="${POESIA_RECONCILE_RATE:-0.6}"
RESERVE="${POESIA_RECONCILE_RESERVE:-2}"   # GAS kept back to pay fees
EPOCHLEN="${POESIA_EPOCHLEN:-12}"

do_register() {
    wait_rpc "$IP" 900 || exit 1
    wait_stream "$IP" weight-engine-membership 900 || exit 1
    local own; own="$(addr_of "$POESIA_HOST")"
    for attempt in 1 2 3 4 5; do
        if rpc_ok "$IP" weightregistermembership "[\"$own\"]"; then
            log "registered as cluster head: $own"
            csv membership.csv "$POESIA_HOST,$own,$own"
            return 0
        fi
        log "membership attempt $attempt failed: $(rpc_err "$IP" weightregistermembership "[\"$own\"]")"
        sleep 10
    done
    log "ERROR: membership not registered"
    return 1
}

do_reconcile() {
    [ -z "${POESIA_TREASURY:-}" ] && { log "no treasury configured: reconciliation disabled"; exit 0; }
    wait_rpc "$IP" 900 || exit 1
    csvh reconciliation.csv "height,epoch,miner,balance,sent"
    local last_epoch=-1
    while true; do
        local h e bal amount
        h="$(rpc_result "$IP" getblockcount)"
        case "$h" in ''|*[!0-9]*) sleep 10; continue ;; esac
        e=$(( h / EPOCHLEN + 1 ))
        if [ "$e" -ne "$last_epoch" ]; then
            last_epoch=$e
            bal="$(rpc_result "$IP" getbalance)"
            case "$bal" in ''|*[!0-9.]*) sleep 10; continue ;; esac
            amount="$(awk -v b="$bal" -v r="$RATE" -v res="$RESERVE" \
                      'BEGIN{a=(b-res)*r; if(a<0.1) a=0; printf "%.4f", a}')"
            if awk -v a="$amount" 'BEGIN{exit !(a > 0)}'; then
                if rpc_ok "$IP" send "[\"$POESIA_TREASURY\",$amount]"; then
                    log "epoch $e: reconciled $amount GAS out of $bal (rate $RATE)"
                    csv reconciliation.csv "$h,$e,$POESIA_HOST,$bal,$amount"
                else
                    log "WARNING: reconciliation failed: $(rpc_err "$IP" send "[\"$POESIA_TREASURY\",$amount]")"
                    csv reconciliation.csv "$h,$e,$POESIA_HOST,$bal,0"
                fi
            else
                csv reconciliation.csv "$h,$e,$POESIA_HOST,$bal,0"
            fi
        fi
        sleep 10
    done
}

case "$PHASE" in
    register)  do_register ;;
    reconcile) do_reconcile ;;
    *) log "unknown phase: $PHASE"; exit 2 ;;
esac
