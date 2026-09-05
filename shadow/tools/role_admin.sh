#!/usr/bin/env bash
# NODO ADMIN — Apuana SB.
#
#   fase 'grant'  : concede i permessi a tutti i nodi, crea lo stream di filiera,
#                   abilita il ruolo di Certification Authority, importa il
#                   treasury come watch-only e distribuisce il GAS iniziale.
#   fase 'refill' : ciclo di rifornimento. Interroga il saldo di ogni azienda e,
#                   quando scende sotto soglia, le invia nuovo GAS. Serve a
#                   garantire che nessuna simulazione si fermi perche' un nodo
#                   ha finito le unita' (cap. 4.2.1 della tesi: Apuana SB vende
#                   GAS alle aziende clienti e fa da camera di compensazione).
#   fase 'epoch_watch' : sorvegliante di epoca. A ogni epoca chiusa e sepolta
#                   campiona cio' che a fine run NON sarebbe piu' ricostruibile,
#                   e lo appende sotto metrics/epoche/. Tre cose, e solo quelle:
#                     * weightverifyweights, che riporta la SOLA ultima epoca
#                       verificata: lo snapshot finale ne conserverebbe una;
#                     * altezza e best-hash di ogni nodo, per vedere un fork
#                       riassorbito a metà run, che node_state.csv (istantanea
#                       di fine run) non mostrerebbe;
#                     * saldo del treasury, che a fine run e' un solo numero.
#                   Il riepilogo per epoca (metrics/summary_epoche.txt) NON viene
#                   costruito qui: lo fa tools/summary_per_epoca.py a fine
#                   simulazione, fuori da Shadow. Il motivo e' lo stesso per cui
#                   sim_common.sh usa curl e non multichain-cli — vedi il commento
#                   in testa a quel file: ogni processo lanciato dentro Shadow
#                   paga il vDSO, e un interprete Python avviato a ogni epoca
#                   sposterebbe l'orologio simulato del nodo che deve intanto
#                   rifornire il GAS. Qui dentro solo bash e curl.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/sim_common.sh"

PHASE="${1:-grant}"
IP="$POESIA_IP"
MINERS="${POESIA_MINERS:-m1 m2 m3}"
COMPANIES="${POESIA_COMPANIES:-c1 c2 c3 c4 c5}"
GAS_COMPANY="${POESIA_GAS_COMPANY:-100}"     # dotazione iniziale azienda
GAS_MINER="${POESIA_GAS_MINER:-50}"          # fondo cassa miner (per riconciliare)
GAS_THRESHOLD="${POESIA_GAS_THRESHOLD:-20}"  # soglia sotto cui si rifornisce
GAS_TOPUP="${POESIA_GAS_TOPUP:-100}"         # taglio del rifornimento
REFILL_EVERY="${POESIA_REFILL_EVERY:-30}"    # secondi simulati fra due controlli
STREAM="${POESIA_STREAM:-poesia-supplychain}"
EPOCHLEN="${POESIA_EPOCHLEN:-12}"           # lunghezza epoca in blocchi

grant_one() {   # grant_one <addr> <permessi>
    local addr=$1 perms=$2
    if rpc_ok "$IP" grant "[\"$addr\",\"$perms\"]"; then
        log "grant $perms -> $addr"
    else
        log "ATTENZIONE: grant $perms -> $addr fallito: $(rpc_err "$IP" grant "[\"$addr\",\"$perms\"]")"
    fi
}

do_grant() {
    wait_rpc "$IP" 600 || exit 1
    local own; own="$(rpc_result "$IP" getaddresses | grep -oE '[A-Za-z0-9]{30,40}' | head -n1)"
    echo "$own" > "$SHARED/admin.addr"
    log "indirizzo admin (Apuana SB): $own"

    # Attende che tutti i nodi abbiano depositato il proprio indirizzo.
    local t=0 missing
    while [ "$t" -lt 300 ]; do
        missing=""
        for h in $MINERS $COMPANIES ca; do
            [ -s "$SHARED/$h.addr" ] || missing="$missing $h"
        done
        [ -z "$missing" ] && break
        sleep 5; t=$((t + 5))
    done
    [ -n "$missing" ] && log "ATTENZIONE: indirizzi mancanti:$missing"

    # --- permessi di base ---------------------------------------------------
    for h in $MINERS; do
        grant_one "$(addr_of "$h")" "connect,send,receive,mine"
    done
    for h in $COMPANIES ca; do
        grant_one "$(addr_of "$h")" "connect,send,receive"
    done

    # --- permessi di scrittura sugli stream ---------------------------------
    # Vanno concessi UNO STREAM PER CHIAMATA: 'grant addr "a.write,b.write"'
    # viene rifiutato da MultiChain con "Could not parse entity key".
    # wpoa-weights NON viene piu' creato da qui. Il nodo lo crea da solo all'avvio:
    # ThreadWeightEngine chiama EnsureStreamReady() prima del gate d'epoca, quindi lo
    # stream (e i grant .write che lo puntano) esistono molto prima che la wPoA ingaggi.
    #
    # Prima non era cosi': la create era raggiungibile solo da RegisterLocalWeight, cioe'
    # solo quando un nodo aveva GIA' un peso da pubblicare -- e un peso non c'era finche'
    # un'epoca non era sepolta. La rete si fermava a setup-first-blocks con
    # "cannot score (unsynced or unweighted)", e questo script creava lo stream a mano per
    # aggirare il problema.
    #
    # Aggirarlo qui pero' nascondeva il comportamento del prodotto all'esperimento. Ora
    # l'harness lo MISURA: aspetta che lo stream compaia da solo e registra a che altezza,
    # cosi' il summary puo' confrontarla con setup-first-blocks. Se non comparisse, la
    # riga sotto lo direbbe invece di mascherarlo.
    if wait_stream "$IP" wpoa-weights 900; then
        local wpoa_h_after; wpoa_h_after="$(rpc_result "$IP" getblockcount)"
        log "stream wpoa-weights creato dal nodo, visibile entro height ${wpoa_h_after:-?}"
        echo "${wpoa_h_after:-}" > "$METRICS/wpoa_weights_stream_height.txt"
    else
        log "ATTENZIONE: wpoa-weights non e' comparso (bootstrap del registro fallito)"
        echo "" > "$METRICS/wpoa_weights_stream_height.txt"
    fi
    wait_stream "$IP" weight-engine-membership 900 || true
    wait_stream "$IP" weight-engine-esg 900 || true
    for h in $MINERS $COMPANIES; do
        grant_one "$(addr_of "$h")" "wpoa-weights.write"
        grant_one "$(addr_of "$h")" "weight-engine-membership.write"
    done

    # L'admin non e' capo cluster, quindi non pubblica pesi e il registro non lo
    # iscrive a wpoa-weights: senza subscribe esplicito lo snapshot finale e
    # weightverifyweights fallirebbero con "Not subscribed to this stream".
    # subscribe esegue un rescan, quindi indicizza anche gli item gia' confermati.
    for st in wpoa-weights weight-engine-esg weight-engine-membership wpoa-weights-malus; do
        rpc_ok "$IP" subscribe "[\"$st\"]" && log "sottoscritto lo stream $st"
    done

    # --- ruolo di Certification Authority ------------------------------------
    # high1 e' il permesso custom che porta il ruolo di CA (weight_authorization.h).
    # NON e' implicito nell'essere amministratore: va delegato esplicitamente.
    grant_one "$(addr_of ca)" "high1"
    grant_one "$(addr_of ca)" "weight-engine-esg.write"

    # --- treasury della riconciliazione ---------------------------------------
    if [ -n "${POESIA_TREASURY:-}" ]; then
        grant_one "$POESIA_TREASURY" "receive"
        rpc_ok "$IP" importaddress "[\"$POESIA_TREASURY\",\"treasury\",false]" \
            && log "treasury importato watch-only: $POESIA_TREASURY"
    fi

    # --- stream applicativo di filiera ----------------------------------------
    if rpc_ok "$IP" create '["stream","'"$STREAM"'",true]'; then
        log "stream applicativo creato: $STREAM (open)"
    else
        log "stream $STREAM gia' presente o non creabile"
    fi

    # --- distribuzione iniziale del GAS ---------------------------------------
    # Il premine (first-block-reward) e' tutto qui: Apuana SB vende GAS alle
    # aziende e finanzia il fondo cassa dei miner perche' possano riconciliare.
    for h in $COMPANIES; do
        if rpc_ok "$IP" send "[\"$(addr_of "$h")\",$GAS_COMPANY]"; then
            log "inviati $GAS_COMPANY GAS a $h"
            csv gas_transfers.csv "$(rpc_result "$IP" getblockcount),init,$h,$GAS_COMPANY"
        fi
    done
    for h in $MINERS ca; do
        if rpc_ok "$IP" send "[\"$(addr_of "$h")\",$GAS_MINER]"; then
            log "inviati $GAS_MINER GAS a $h"
            csv gas_transfers.csv "$(rpc_result "$IP" getblockcount),init,$h,$GAS_MINER"
        fi
    done
    log "fase grant completata"
}

do_refill() {
    wait_rpc "$IP" 600 || exit 1
    csvh gas_balances.csv "height,host,balance"
    log "ciclo di rifornimento GAS attivo (soglia ${GAS_THRESHOLD}, taglio ${GAS_TOPUP})"
    while true; do
        local h bal height
        height="$(rpc_result "$IP" getblockcount)"
        for h in $COMPANIES $MINERS ca; do
            local ip_var="POESIA_IP_${h}"
            local nip="${!ip_var:-}"
            [ -z "$nip" ] && continue
            bal="$(rpc_result "$nip" getbalance)"
            case "$bal" in ''|*[!0-9.]*) continue ;; esac
            csv gas_balances.csv "$height,$h,$bal"
            # confronto in virgola mobile senza bc
            if awk -v b="$bal" -v t="$GAS_THRESHOLD" 'BEGIN{exit !(b < t)}'; then
                if rpc_ok "$IP" send "[\"$(addr_of "$h")\",$GAS_TOPUP]"; then
                    log "RIFORNIMENTO: $h aveva $bal GAS -> +$GAS_TOPUP"
                    csv gas_transfers.csv "$height,refill,$h,$GAS_TOPUP"
                else
                    log "ATTENZIONE: rifornimento di $h fallito"
                fi
            fi
        done
        sleep "$REFILL_EVERY"
    done
}

# ---------------------------------------------------------------------------
# Sorvegliante di epoca
# ---------------------------------------------------------------------------
#
# STABILITA'. Un'epoca viene campionata solo quando e' chiusa E sepolta di
# EPOCH_MARGIN blocchi: e' lo stesso margine che il weight engine si prende
# prima di pubblicare il peso di un'epoca (Sez. 6.4). Campionare prima
# fotograferebbe un verdetto che il motore non ha ancora emesso, e la riga
# direbbe "non verificato" per un motivo di tempismo, non di protocollo.
EPOCH_MARGIN="${POESIA_EPOCH_MARGIN:-8}"
EPOCH_POLL="${POESIA_EPOCH_POLL:-10}"          # secondi simulati fra due controlli
SETUPBLOCKS="${POESIA_SETUPBLOCKS:-60}"        # fine della fase PoA nativa

do_epoch_watch() {
    wait_rpc "$IP" 900 || exit 1
    local dir="$METRICS/epoche"
    mkdir -p "$dir"
    : > "$dir/verify_epoche.jsonl"
    echo "epoca,height_admin,host,height,besthash,peers" > "$dir/node_state_epoche.csv"
    echo "epoca,height,saldo_treasury_gas"                > "$dir/treasury_epoche.csv"
    log "sorvegliante di epoca attivo (epochlen=$EPOCHLEN, margine=$EPOCH_MARGIN blocchi)"

    # Prima epoca che valga la pena campionare: quella in cui cade il primo
    # blocco governato dalla wPoA. Le epoche interamente dentro la fase di setup
    # non hanno blocchi da analizzare, e campionarle sarebbe solo un burst di
    # RPC all'avvio.
    local last=$(( SETUPBLOCKS / EPOCHLEN ))
    log "sorvegliante: prima epoca campionata la $(( last + 1 )) "\
        "(setup = $SETUPBLOCKS blocchi)"

    while true; do
        local h target
        h="$(rpc_result "$IP" getblockcount)"
        case "$h" in ''|*[!0-9]*) sleep "$EPOCH_POLL"; continue ;; esac

        # L'epoca t e' pronta quando la catena e' arrivata EPOCH_MARGIN blocchi
        # oltre il suo ultimo blocco, cioe' quando h >= t*EPOCHLEN + margine.
        # Invertita: t <= (h - margine)/EPOCHLEN. Si campionano TUTTE le epoche
        # pronte e non ancora fatte, non solo l'ultima: la finestra di sepoltura
        # e' larga poche altezze e con target-block-time basso un solo controllo
        # per ciclo salterebbe epoche intere.
        if [ "$h" -gt "$EPOCH_MARGIN" ]; then
            target=$(( (h - EPOCH_MARGIN) / EPOCHLEN ))
            while [ "$last" -lt "$target" ]; do
                last=$(( last + 1 ))
                campiona_epoca "$last" "$h" "$dir"
            done
        fi
        sleep "$EPOCH_POLL"
    done
}

# campiona_epoca <epoca> <height_corrente> <dir>
campiona_epoca() {
    local target=$1 h=$2 dir=$3
    log "epoca $target chiusa e sepolta (height $h): campionamento"

    # 1. verifica indipendente: e' l'unico istante in cui la RPC parla di QUESTA
    #    epoca, perche' riporta solo l'ultima che il nodo ha verificato.
    local v; v="$(rpc "$IP" weightverifyweights)"
    printf '{"epoca_richiesta":%s,"height":%s,"verify":%s}\n' \
           "$target" "$h" "${v:-null}" >> "$dir/verify_epoche.jsonl"

    # 2. stato per nodo: un fork riassorbito prima della fine run non
    #    lascerebbe altra traccia in node_state.csv, che e' un'istantanea finale.
    local hh
    for hh in admin $MINERS $COMPANIES ca; do
        local ip_var="POESIA_IP_${hh}" nip
        nip="${!ip_var:-}"
        [ -z "$nip" ] && continue
        local nh bh pc
        nh="$(rpc_result "$nip" getblockcount)"
        bh="$(rpc_result "$nip" getbestblockhash | tr -d '\"')"
        pc="$(rpc "$nip" getpeerinfo | grep -o '"addr"' | wc -l)"
        echo "$target,$h,$hh,${nh:-n/d},${bh:-n/d},${pc:-0}" \
             >> "$dir/node_state_epoche.csv"
    done

    # 3. saldo del treasury: a fine run e' un numero solo, qui e' una serie.
    if [ -n "${POESIA_TREASURY:-}" ]; then
        local tb
        tb="$(rpc "$IP" getaddressbalances "[\"$POESIA_TREASURY\"]" \
              | grep -oE '"qty":[0-9.]+' | head -n1 | cut -d: -f2)"
        echo "$target,$h,${tb:-n/d}" >> "$dir/treasury_epoche.csv"
    fi
}

# Dump finale dello stato della catena: e' la fonte primaria delle metriche.
# Molto piu' affidabile del parsing dei debug.log, perche' listblocks riporta
# direttamente il proposer di ogni altezza.
do_snapshot() {
    wait_rpc "$IP" 300 || exit 1
    local h; h="$(rpc_result "$IP" getblockcount)"
    log "snapshot finale a height=$h"
    echo "$h" > "$METRICS/final_height.txt"

    rpc "$IP" listblocks "[\"1-$h\"]"                       > "$METRICS/blocks.json"
    rpc "$IP" liststreamitems '["wpoa-weights",false,100000]' > "$METRICS/weights.json"
    rpc "$IP" liststreamitems '["weight-engine-esg",false,10000]'        > "$METRICS/esg.json"
    rpc "$IP" liststreamitems '["weight-engine-membership",false,10000]' > "$METRICS/membership.json"
    rpc "$IP" liststreamitems '["wpoa-weights-malus",false,10000]'       > "$METRICS/malus.json"
    rpc "$IP" weightverifyweights                            > "$METRICS/verify.json"
    rpc "$IP" getinfo                                        > "$METRICS/admin_getinfo.json"
    rpc "$IP" listpermissions '["mine"]'                     > "$METRICS/permissions_mine.json"
    # I parametri COME LI HA LA CATENA. Gli argomenti passati a collect_metrics dicono
    # cosa si credeva di aver configurato; questo dice su cosa la rete ha davvero girato
    # -- e i due possono divergere (un valore alzato alla genesi, un flag di runtime mai
    # finito in params.dat). Ogni soglia del summary si calcola da qui.
    rpc "$IP" getblockchainparams                            > "$METRICS/chainparams.json"

    # stato per-nodo: altezza e conteggio peer (rilevamento di fork persistenti)
    # altezza di riferimento comune, scelta abbastanza sotto il tip da essere
    # gia' propagata ovunque anche se un nodo e' un blocco indietro
    local DEEP_HEIGHT=$(( h - 6 )); [ "$DEEP_HEIGHT" -lt 1 ] && DEEP_HEIGHT=1
    log "hash di riferimento confrontato all'altezza $DEEP_HEIGHT"
    csvh node_state.csv "host,height,besthash,hash_a_${DEEP_HEIGHT},peers,balance"
    local hh
    for hh in admin $MINERS $COMPANIES ca; do
        local ip_var="POESIA_IP_${hh}" nip
        nip="${!ip_var:-}"
        [ -z "$nip" ] && continue
        local nh nb bh pc
        nh="$(rpc_result "$nip" getblockcount)"
        bh="$(rpc_result "$nip" getbestblockhash | tr -d '\"')"
        # Hash sepolto a un'altezza ASSOLUTA comune a tutti i nodi: se si usasse
        # "altezza propria - 6" i nodi a altezze diverse confronterebbero blocchi
        # diversi per costruzione, e una normale differenza di propagazione
        # verrebbe scambiata per un fork.
        local dh; dh="$(rpc_result "$nip" getblockhash "[$DEEP_HEIGHT]" | tr -d '\"')"
        [ -z "$dh" ] && dh="n/d"
        pc="$(rpc "$nip" getpeerinfo | grep -o '"addr"' | wc -l)"
        nb="$(rpc_result "$nip" getbalance)"
        csv node_state.csv "$hh,$nh,$bh,$dh,$pc,$nb"
    done

    if [ -n "${POESIA_TREASURY:-}" ]; then
        rpc "$IP" getaddressbalances "[\"$POESIA_TREASURY\"]" > "$METRICS/treasury_balance.json"
    fi
    log "snapshot completato"
}

case "$PHASE" in
    grant)       do_grant ;;
    refill)      do_refill ;;
    epoch_watch) do_epoch_watch ;;
    snapshot)    do_snapshot ;;
    *)      log "fase sconosciuta: $PHASE"; exit 2 ;;
esac
