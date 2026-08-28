#!/usr/bin/env bash
# NODO MINER (validatore, capo cluster).
#
#   fase 'register'  : si registra come capo del proprio cluster su
#                      weight-engine-membership (un miner chiama
#                      weightregistermembership col PROPRIO indirizzo).
#   fase 'reconcile' : a ogni epoca rimanda al treasury una frazione del GAS
#                      incassato in fee. E' questo trasferimento, derivato dai
#                      blocchi confermati, a costituire R_k (Def. 6.7) e quindi
#                      il tasso di conformita' rho_k che retroaziona il peso
#                      dell'epoca successiva (Def. 6.8-6.9).
#                      Il tasso e' DIVERSO per miner (POESIA_RECONCILE_RATE)
#                      cosi' che i rho_k divergano e la retroazione sia
#                      osservabile.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/sim_common.sh"

PHASE="${1:-register}"
IP="$POESIA_IP"
RATE="${POESIA_RECONCILE_RATE:-0.6}"
RESERVE="${POESIA_RECONCILE_RESERVE:-2}"   # GAS lasciati per pagare le fee
EPOCHLEN="${POESIA_EPOCHLEN:-12}"

do_register() {
    wait_rpc "$IP" 900 || exit 1
    wait_stream "$IP" weight-engine-membership 900 || exit 1
    local own; own="$(addr_of "$POESIA_HOST")"
    for attempt in 1 2 3 4 5; do
        if rpc_ok "$IP" weightregistermembership "[\"$own\"]"; then
            log "registrato come capo cluster: $own"
            csv membership.csv "$POESIA_HOST,$own,$own"
            return 0
        fi
        log "tentativo $attempt di membership fallito: $(rpc_err "$IP" weightregistermembership "[\"$own\"]")"
        sleep 10
    done
    log "ERRORE: membership non registrata"
    return 1
}

do_reconcile() {
    [ -z "${POESIA_TREASURY:-}" ] && { log "treasury non configurato: riconciliazione disattivata"; exit 0; }
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
                    log "epoca $e: riconciliati $amount GAS su $bal (rate $RATE)"
                    csv reconciliation.csv "$h,$e,$POESIA_HOST,$bal,$amount"
                else
                    log "ATTENZIONE: riconciliazione fallita: $(rpc_err "$IP" send "[\"$POESIA_TREASURY\",$amount]")"
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
    *) log "fase sconosciuta: $PHASE"; exit 2 ;;
esac
