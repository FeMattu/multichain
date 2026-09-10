#!/usr/bin/env bash
# COMPANY NODE (client, without the mine permission).
#
#   phase 'register' : declares that it joins a miner's cluster on
#                      weight-engine-membership. The choice is autonomous and
#                      the record is self-attested: the reader accepts it only
#                      because the signer matches node_address, so nobody can
#                      declare somebody else's membership.
#   phase 'traffic'  : publishes supply-chain items on the application stream.
#                      Each publication (a) pays 0.2 GAS of fee to the miner
#                      that includes it and (b) increments tau_i, the epoch's
#                      activity counter that the contribution
#                      c_i = ESG_i * tau_i / kappa - and therefore the cluster
#                      weight - depends on.
#                      The interval differs per company so the tau_i, and with
#                      them the W_k, diverge.
set -Euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

PHASE="${1:-register}"
IP="$POESIA_IP"
STREAM="${POESIA_STREAM:-poesia-supplychain}"
INTERVAL="${POESIA_TX_INTERVAL:-12}"

do_register() {
    wait_rpc "$IP" 900 || exit 1
    wait_stream "$IP" weight-engine-membership 900 || exit 1
    local miner_addr; miner_addr="$(addr_of "$POESIA_CLUSTER")"
    if [ -z "$miner_addr" ]; then
        log "ERROR: no address for miner $POESIA_CLUSTER"
        return 1
    fi
    for attempt in 1 2 3 4 5; do
        if rpc_ok "$IP" weightregistermembership "[\"$miner_addr\"]"; then
            log "joined cluster $POESIA_CLUSTER ($miner_addr)"
            csv membership.csv "$POESIA_HOST,$(addr_of "$POESIA_HOST"),$miner_addr"
            return 0
        fi
        log "attempt $attempt failed: $(rpc_err "$IP" weightregistermembership "[\"$miner_addr\"]")"
        sleep 10
    done
    log "ERROR: membership not registered"
    return 1
}

do_traffic() {
    wait_rpc "$IP" 900 || exit 1
    wait_stream "$IP" "$STREAM" 900 || exit 1
    local own; own="$(addr_of "$POESIA_HOST")"
    csvh traffic.csv "height,host,seq,txid_or_error"
    log "traffic generator active (one item every ${INTERVAL}s)"
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
            log "publish failed (seq $seq): $(rpc_err "$IP" publishfrom "[\"$own\",\"$STREAM\",\"$key\",\"$payload\"]")"
        fi
        sleep "$INTERVAL"
    done
}

case "$PHASE" in
    register) do_register ;;
    traffic)  do_traffic ;;
    *) log "unknown phase: $PHASE"; exit 2 ;;
esac
