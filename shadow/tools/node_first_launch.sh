#!/usr/bin/env bash
# FASE 1 DEL JOIN (nodi diversi dall'admin).
#
# Su una catena permissioned il primo avvio di un nodo non entra in rete: crea
# il datadir e il wallet, stampa il proprio indirizzo e termina, in attesa che
# l'amministratore gli conceda i permessi. Qui catturiamo quell'indirizzo e lo
# depositiamo in shared/<host>.addr, da dove role_admin.sh lo legge per
# emettere i grant. La FASE 2 (join vero) e' un secondo processo multichaind
# schedulato piu' avanti nella timeline di shadow.yaml.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/sim_common.sh"

DATADIR="$POESIA_RUN/data/$POESIA_HOST"
OUT="$SHARED/$POESIA_HOST.addr"
mkdir -p "$DATADIR"

log "primo avvio (raccolta indirizzo) verso $POESIA_SEED"
"$POESIA_BINDIR/multichaind" "$POESIA_SEED" -datadir="$DATADIR" \
    -port="$POESIA_P2PPORT" -rpcport="$POESIA_RPCPORT" \
    -externalip="$POESIA_IP" -dnsseed=0 -discover=0 -shortoutput \
    > "$SHARED/$POESIA_HOST.firstlaunch.log" 2>&1

# -shortoutput stampa il solo indirizzo del wallet quando servono i permessi.
grep -oE '[A-Za-z0-9]{30,40}' "$SHARED/$POESIA_HOST.firstlaunch.log" | tail -n1 > "$OUT"

if [ -s "$OUT" ]; then
    log "indirizzo pubblicato: $(cat "$OUT")"
else
    log "ERRORE: nessun indirizzo estratto; log:"
    cat "$SHARED/$POESIA_HOST.firstlaunch.log"
    exit 1
fi
