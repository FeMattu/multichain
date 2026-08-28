#!/usr/bin/env bash
# NODO AZIENDA (client, senza permesso mine).
#
#   fase 'register' : dichiara la propria adesione al cluster di un miner su
#                     weight-engine-membership. La scelta e' autonoma e il
#                     record e' auto-attestato: il lettore lo accetta solo
#                     perche' il firmatario coincide con node_address, quindi
#                     nessuno puo' dichiarare l'appartenenza altrui.
#   fase 'traffic'  : pubblica item di filiera sullo stream applicativo. Ogni
#                     pubblicazione (a) paga 0.2 GAS di fee al miner che la
#                     include, (b) incrementa tau_i, il contatore di attivita'
#                     dell'epoca da cui dipende il contributo c_i = ESG_i*tau_i/kappa
#                     e quindi il peso del cluster.
#                     L'intervallo e' diverso per azienda, cosi' che i tau_i e i
#                     W_k divergano.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/sim_common.sh"

PHASE="${1:-register}"
IP="$POESIA_IP"
STREAM="${POESIA_STREAM:-poesia-supplychain}"
INTERVAL="${POESIA_TX_INTERVAL:-12}"

do_register() {
    wait_rpc "$IP" 900 || exit 1
    wait_stream "$IP" weight-engine-membership 900 || exit 1
    local miner_addr; miner_addr="$(addr_of "$POESIA_CLUSTER")"
    if [ -z "$miner_addr" ]; then
        log "ERRORE: indirizzo del miner $POESIA_CLUSTER non disponibile"
        return 1
    fi
    for attempt in 1 2 3 4 5; do
        if rpc_ok "$IP" weightregistermembership "[\"$miner_addr\"]"; then
            log "adesione al cluster $POESIA_CLUSTER ($miner_addr)"
            csv membership.csv "$POESIA_HOST,$(addr_of "$POESIA_HOST"),$miner_addr"
            return 0
        fi
        log "tentativo $attempt fallito: $(rpc_err "$IP" weightregistermembership "[\"$miner_addr\"]")"
        sleep 10
    done
    log "ERRORE: adesione non registrata"
    return 1
}

do_traffic() {
    wait_rpc "$IP" 900 || exit 1
    wait_stream "$IP" "$STREAM" 900 || exit 1
    local own; own="$(addr_of "$POESIA_HOST")"
    csvh traffic.csv "height,host,seq,txid_or_error"
    log "generatore di traffico attivo (1 item ogni ${INTERVAL}s simulati)"
    local seq=0
    while true; do
        seq=$((seq + 1))
        local h key payload out
        h="$(rpc_result "$IP" getblockcount)"
        key="LOTTO-${POESIA_HOST}-$(printf '%05d' "$seq")"
        payload="$(hex_of "{\"host\":\"$POESIA_HOST\",\"seq\":$seq,\"height\":$h}")"
        out="$(rpc_result "$IP" publishfrom "[\"$own\",\"$STREAM\",\"$key\",\"$payload\"]")"
        if echo "$out" | grep -qE '^"[0-9a-f]{64}"$'; then
            csv traffic.csv "$h,$POESIA_HOST,$seq,$(echo "$out" | tr -d '\"')"
        else
            csv traffic.csv "$h,$POESIA_HOST,$seq,ERRORE"
            log "publish fallito (seq $seq): $(rpc_err "$IP" publishfrom "[\"$own\",\"$STREAM\",\"$key\",\"$payload\"]")"
        fi
        sleep "$INTERVAL"
    done
}

case "$PHASE" in
    register) do_register ;;
    traffic)  do_traffic ;;
    *) log "fase sconosciuta: $PHASE"; exit 2 ;;
esac
