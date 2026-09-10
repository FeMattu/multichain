# ---------------------------------------------------------------------------
# Helpers shared by the role scripts, which run INSIDE a node's namespace.
# Source it, do not execute it.
#
# WHY curl AND NOT multichain-cli
# -------------------------------
# Every process that touches Bitcoin Core's RNG pays the Strengthen() loop of
# src/utils/random.cpp once: a busy wait that reshuffles SHA512 until 100 ms of
# clock have passed. It is paid per PROCESS, at the first use of the RNG.
#
# Under Shadow that cost was fatal, because clock_gettime goes through the vDSO
# and the simulator credited it 10 ns. Running natively it is no longer fatal -
# but it is not free either: 100 ms of real CPU per invocation. The admin polls
# twenty nodes every 30 s and samples every epoch; at that rate multichain-cli
# would burn seconds of CPU per cycle on twenty namespaces at once, on the same
# host that is running twenty daemons. curl pays none of it.
#
# So the reason changed and the conclusion did not. Use curl.
#
# Every function takes the peer's EMULATED address, so node-to-node RPC travels
# the impaired paths - it is part of what the experiment measures. The harness's
# own collectors run on the host and use the management plane instead.
# ---------------------------------------------------------------------------

: "${POESIA_RUN:?POESIA_RUN is not set}"
: "${POESIA_CHAIN:?POESIA_CHAIN is not set}"
: "${POESIA_RPCPORT:=27000}"
: "${POESIA_RPCUSER:=poesia}"
: "${POESIA_RPCPASS:=poesiarpc}"
: "${POESIA_HOST:=unknown}"

SHARED="$POESIA_RUN/runtime/shared"
METRICS="$POESIA_RUN/raw/metrics"
mkdir -p "$SHARED" "$METRICS"

log() { echo "[$POESIA_HOST $(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

# rpc <ip> <method> [params-json] -> the full JSON response
rpc() {
    local ip=$1 method=$2 params=${3:-[]}
    curl -s -m "${POESIA_RPC_TIMEOUT:-60}" --user "$POESIA_RPCUSER:$POESIA_RPCPASS" \
         --data-binary "{\"id\":\"$POESIA_HOST\",\"method\":\"$method\",\"params\":$params}" \
         "http://$ip:$POESIA_RPCPORT/" 2>/dev/null
}

# rpc_result <ip> <method> [params] -> the "result" field, raw.
# MultiChain always emits {"result":...,"error":...,"id":...} in that order.
rpc_result() {
    rpc "$@" | sed -E 's/^\{"result":(.*),"error":.*$/\1/'
}

rpc_err() {
    rpc "$@" | grep -oE '"message":"[^"]*"' | head -n1
}

# rpc_ok <ip> <method> [params]: true when the call produced no error
rpc_ok() {
    local out; out="$(rpc "$@")"
    [ -n "$out" ] && ! echo "$out" | grep -q '"error":{'
}

# wait_rpc <ip> <timeout_s>: wait for the daemon to answer
wait_rpc() {
    local ip=$1 timeout=${2:-300} t=0
    while [ "$t" -lt "$timeout" ]; do
        rpc_ok "$ip" getblockcount && return 0
        sleep 2; t=$((t + 2))
    done
    log "TIMEOUT: no RPC answer from $ip after ${timeout}s"
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

# wait_stream <ip> <name> <timeout_s>: wait for a stream to exist on chain
wait_stream() {
    local ip=$1 name=$2 timeout=${3:-600} t=0
    while [ "$t" -lt "$timeout" ]; do
        rpc_ok "$ip" liststreams "[\"$name\"]" && return 0
        sleep 5; t=$((t + 5))
    done
    log "TIMEOUT: stream $name not found on $ip"
    return 1
}

# csv <file> <row>: append. A row shorter than PIPE_BUF is written atomically,
# which is what lets several hosts share one file.
csv() { echo "$2" >> "$METRICS/$1"; }

# csvh <file> <header>: write the header only if the file does not exist.
# Several hosts write the same CSV (traffic, reconciliation); without this each
# would insert another copy of the header in the middle of the data.
csvh() { [ -f "$METRICS/$1" ] || echo "$2" > "$METRICS/$1"; }

# addr_of <host>: the node's address, deposited by first_launch.sh
addr_of() { cat "$SHARED/$1.addr" 2>/dev/null; }

# hex_of <string>: hex payload for publish
hex_of() { printf '%s' "$1" | od -An -tx1 | tr -d ' \n'; }
