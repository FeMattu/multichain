# ---------------------------------------------------------------------------
# Funzioni condivise dagli script che girano DENTRO Shadow.
# Da sourcerare, non da eseguire.
#
# Nota sul perche' si usa curl e NON multichain-cli: ogni processo che tocca
# l'RNG di Bitcoin Core paga una volta il loop Strengthen() di random.cpp
# (100 ms di clock busy-wait). Sotto Shadow quel loop e' costosissimo perche'
# clock_gettime/gettimeofday passano dal vDSO. curl non lo paga; multichain-cli
# lo pagherebbe a ogni invocazione.  Vedi README.md sezione "Vincoli di Shadow".
# ---------------------------------------------------------------------------

: "${POESIA_RUN:?POESIA_RUN non impostato}"
: "${POESIA_CHAIN:?POESIA_CHAIN non impostato}"
: "${POESIA_RPCPORT:=27000}"
: "${POESIA_RPCUSER:=poesia}"
: "${POESIA_RPCPASS:=poesiarpc}"
: "${POESIA_HOST:=unknown}"

SHARED="$POESIA_RUN/shared"
METRICS="$POESIA_RUN/metrics"
mkdir -p "$SHARED" "$METRICS"

log() { echo "[$POESIA_HOST $(date -u +%H:%M:%S)] $*"; }

# rpc <ip> <method> [params-json] -> risposta JSON completa
rpc() {
    local ip=$1 method=$2 params=${3:-[]}
    curl -s -m 60 --user "$POESIA_RPCUSER:$POESIA_RPCPASS" \
         --data-binary "{\"id\":\"$POESIA_HOST\",\"method\":\"$method\",\"params\":$params}" \
         "http://$ip:$POESIA_RPCPORT/" 2>/dev/null
}

# rpc_result <ip> <method> [params] -> solo il campo "result" (grezzo)
# MultiChain emette sempre {"result":...,"error":...,"id":...} in quest'ordine.
rpc_result() {
    rpc "$@" | sed -E 's/^\{"result":(.*),"error":.*$/\1/'
}

rpc_err() {
    rpc "$@" | grep -oE '"message":"[^"]*"' | head -n1
}

# rpc_ok <ip> <method> [params]: vero se la chiamata non ha prodotto errore
rpc_ok() {
    local out; out="$(rpc "$@")"
    [ -n "$out" ] && ! echo "$out" | grep -q '"error":{'
}

# wait_rpc <ip> <timeout_s>: attende che il demone risponda
wait_rpc() {
    local ip=$1 timeout=${2:-300} t=0
    while [ "$t" -lt "$timeout" ]; do
        rpc_ok "$ip" getblockcount && return 0
        sleep 2; t=$((t + 2))
    done
    log "TIMEOUT: nessuna risposta RPC da $ip dopo ${timeout}s"
    return 1
}

# wait_height <ip> <h> <timeout_s>
wait_height() {
    local ip=$1 target=$2 timeout=${3:-3600} t=0 h
    while [ "$t" -lt "$timeout" ]; do
        h="$(rpc_result "$ip" getblockcount)"
        case "$h" in ''|*[!0-9]*) : ;; *) [ "$h" -ge "$target" ] && return 0 ;; esac
        sleep 5; t=$((t + 5))
    done
    return 1
}

# wait_stream <ip> <nome> <timeout_s>: attende che uno stream esista on-chain
wait_stream() {
    local ip=$1 name=$2 timeout=${3:-600} t=0
    while [ "$t" -lt "$timeout" ]; do
        rpc_ok "$ip" liststreams "[\"$name\"]" && return 0
        sleep 5; t=$((t + 5))
    done
    log "TIMEOUT: stream $name non trovato su $ip"
    return 1
}

# csv <file> <riga>: append (riga < PIPE_BUF, quindi atomico)
csv() { echo "$2" >> "$METRICS/$1"; }

# csvh <file> <intestazione>: scrive l'intestazione solo se il file non esiste.
# Serve perche' piu' host scrivono lo stesso CSV (traffico, riconciliazione):
# senza questo, ogni processo ne aggiungerebbe una copia in mezzo ai dati.
csvh() { [ -f "$METRICS/$1" ] || echo "$2" > "$METRICS/$1"; }

# addr_of <host>: indirizzo del nodo, scritto da node_first_launch.sh
addr_of() { cat "$SHARED/$1.addr" 2>/dev/null; }

# hex_of <stringa>: payload esadecimale per publish
hex_of() { printf '%s' "$1" | od -An -tx1 | tr -d ' \n'; }
