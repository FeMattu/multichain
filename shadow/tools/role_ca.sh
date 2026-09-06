#!/usr/bin/env bash
# NODO CERTIFICATION AUTHORITY.
#
# Pubblica su weight-engine-esg il punteggio ESG certificato di ogni miner e di
# ogni azienda. I punteggi sono estratti a caso uniformemente in (0, 100) da un
# generatore seminato con POESIA_RNG_SEED: la stessa run rieseguita con lo
# stesso seed produce gli stessi ESG.
#
# Il ruolo di CA e' portato dal permesso custom high1, delegato dall'admin e
# revocabile: essere amministratore NON basta a certificare (cfr.
# weight-engine.md 6.4). Un ESG e' un'attestazione di fiducia, non verificabile
# crittograficamente da terzi: l'unica difesa e' restringere chi puo' asserirla.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/sim_common.sh"

IP="$POESIA_IP"
TARGETS="${POESIA_MINERS:-m1 m2 m3} ${POESIA_COMPANIES:-c1 c2 c3 c4 c5}"
RNG_SEED="${POESIA_RNG_SEED:-1}"

# RIPARTIZIONE FRA PIU' CA. Un descrittore di simulazione puo' dichiararne fino
# a 3: senza ripartizione ognuna certificherebbe l'intero elenco, scrivendo N
# volte lo stesso ESG sullo stream. Ogni CA prende una fetta dei target a
# rotazione (indice del target modulo il numero di CA).
#
# Il contatore i resta GLOBALE e scorre tutti i target, anche quelli che questa
# CA salta: e' il seme dello score (srand(s+k)), quindi tenerlo globale fa si'
# che l'ESG di un dato host non dipenda da quante CA ci sono. La stessa run con
# 1, 2 o 3 CA produce gli stessi punteggi.
CA_INDEX="${POESIA_CA_INDEX:-1}"
CA_COUNT="${POESIA_CA_COUNT:-1}"

wait_rpc "$IP" 900 || exit 1
wait_stream "$IP" weight-engine-esg 900 || exit 1

csvh esg_scores.csv "host,address,esg"

i=0
for h in $TARGETS; do
    i=$((i + 1))
    # fetta di questa CA: i target sono distribuiti a rotazione
    [ $(( (i - 1) % CA_COUNT )) -eq $(( CA_INDEX - 1 )) ] || continue
    addr="$(addr_of "$h")"
    if [ -z "$addr" ]; then
        log "ATTENZIONE: indirizzo di $h non disponibile, ESG saltato"
        continue
    fi
    # uniforme in (0,100), esclusi gli estremi: ESG_i > 0 e' richiesto dalla
    # Def. 6.1 (e la positivita' del peso dipende da questo).
    score="$(awk -v s="$RNG_SEED" -v k="$i" 'BEGIN{srand(s+k); v=rand(); if(v<0.001)v=0.001; if(v>0.999)v=0.999; printf "%.2f", v*100}')"
    for attempt in 1 2 3 4 5; do
        if rpc_ok "$IP" weightsetesg "[\"$addr\",$score]"; then
            log "ESG certificato: $h ($addr) = $score"
            csv esg_scores.csv "$h,$addr,$score"
            break
        fi
        log "tentativo $attempt fallito per $h: $(rpc_err "$IP" weightsetesg "[\"$addr\",$score]")"
        sleep 10
    done
done
log "certificazione ESG completata (CA $CA_INDEX di $CA_COUNT)"
