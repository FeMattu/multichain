# shellcheck shell=bash
#
# functional_lib.sh — shared helpers for the wPoA functional tests.
#
# This library is *sourced*, never executed. It factors out the network
# bootstrap, block-height waiting, metrics collection and assertion bookkeeping
# that used to be copy-pasted into every per-feature functional test, so a
# single orchestrated run can start ONE network and check many features on it.
#
# The bootstrap protocol (permissioned MultiChain: create → grant → rejoin) is
# preserved verbatim from the original per-feature functional tests it replaces,
# which it is known to work against.
#
# Public surface (all prefixed fl_ / FL_):
#   fl_require_binaries                     assert multichaind/-util/-cli exist
#   fl_start_network "<WPOA_ARGS>"          create chain + bootstrap all nodes
#   fl_wait_weight_convergence              wait until every node sees TOTAL_WEIGHT
#   fl_drive_to_height H TIMEOUT [STALLMSG] mine until node 0 tip >= H
#   fl_teardown                             stop + wipe every node (idempotent)
#   fl_cli i <args...>                      run multichain-cli against node i
#   fl_node_total i / fl_tip_height i / fl_blockhash_at i H
#   fl_logcount_all "<grep -E pattern>"     sum matches across every node's debug.log
#   fl_phase "msg" / fl_log "msg" / fl_die "msg"
#   Assertion bookkeeping: fl_check_begin NAME CRITICAL / fl_ok MSG / fl_bad MSG
#                          fl_assert_gt0 VAL MSG / fl_assert_zero VAL MSG / fl_assert_eq A B MSG
#   fl_check_summary                        print table; returns non-zero if a critical check failed
#
# Inputs (env, with defaults):
#   BINDIR NODES WEIGHTS SETUP_BLOCKS
#   RPC_TIMEOUT CONNECT_TIMEOUT WEIGHT_TIMEOUT TARGET_BLOCK_TIME KEEP_LOGS
#
# The caller owns `set -uo pipefail` and any traps; fl_teardown is safe to call
# from an EXIT trap.

# ---- configuration & state --------------------------------------------------
BINDIR="${BINDIR:-}"
NODES="${NODES:-3}"
SETUP_BLOCKS="${SETUP_BLOCKS:-30}"
RPC_TIMEOUT="${RPC_TIMEOUT:-30}"
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-30}"
WEIGHT_TIMEOUT="${WEIGHT_TIMEOUT:-180}"
TARGET_BLOCK_TIME="${TARGET_BLOCK_TIME:-2}"
KEEP_LOGS="${KEEP_LOGS:-0}"

FL_CHAIN=""
FL_SEED_ADDR=""
FL_TOTAL_WEIGHT=0
FL_NET_UP=0
declare -a FL_DATADIRS=() FL_RPCPORTS=() FL_P2PPORTS=() FL_WEIGHTS=()

# assertion bookkeeping
declare -a FL_CHECK_NAMES=() FL_CHECK_STATE=()   # STATE: PASS | FAIL | WARN
FL_CUR_CHECK=""
FL_CUR_CRITICAL=1
FL_CUR_FAILED=0

# ---- logging ----------------------------------------------------------------
fl_phase() { echo; echo "════════════════════════════════════════════════════════════════════"; echo "▶ $*"; echo "════════════════════════════════════════════════════════════════════"; }
fl_log()   { echo "  $*"; }
fl_die()   { echo "FATAL: $*" >&2; exit 1; }

# ---- multichain-cli against a node ------------------------------------------
fl_cli() {
    local i=$1; shift
    "$BINDIR/multichain-cli" -datadir="${FL_DATADIRS[i]}" -rpcport="${FL_RPCPORTS[i]}" "$FL_CHAIN" "$@"
}

fl_require_binaries() {
    [ -n "$BINDIR" ] || fl_die "BINDIR is not set"
    local b
    for b in multichain-util multichaind multichain-cli; do
        [ -x "$BINDIR/$b" ] || fl_die "binary not found or not executable: $BINDIR/$b (build the node first)"
    done
}

# ---- small RPC helpers -------------------------------------------------------
fl_node_total() {
    fl_cli "$1" getallweights 2>/dev/null \
        | sed -nE 's/.*"total"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' | head -n1
}
fl_tip_height()  { fl_cli "$1" getblockcount 2>/dev/null; }
fl_blockhash_at(){ fl_cli "$1" getblockhash "$2" 2>/dev/null; }

# Sum grep -E matches for a pattern across every node's debug.log.
fl_logcount_all() {
    local pat=$1 i c total=0
    for ((i = 0; i < NODES; i++)); do
        c=$(grep -Ec "$pat" "${FL_DATADIRS[i]}/$FL_CHAIN/debug.log" 2>/dev/null); c=${c:-0}
        total=$(( total + c ))
    done
    echo "$total"
}

# Per-node line for evidence tables: "node i: <count>".
fl_logcount_per_node() {
    local pat=$1 i c
    for ((i = 0; i < NODES; i++)); do
        c=$(grep -Ec "$pat" "${FL_DATADIRS[i]}/$FL_CHAIN/debug.log" 2>/dev/null); c=${c:-0}
        echo "    node $i: $c"
    done
}

fl_wait_rpc() {
    local i=$1 t
    echo -n "  waiting for RPC on node $i"
    for ((t = 0; t < RPC_TIMEOUT; t++)); do
        if fl_cli "$i" getinfo >/dev/null 2>&1; then echo " up."; return 0; fi
        echo -n "."; sleep 1
    done
    echo
    return 1
}

_fl_addr_from_log() {
    grep -oE 'grant[[:space:]]+[A-Za-z0-9]{30,40}[[:space:]]+connect' "$1" \
        | head -n1 | awk '{print $2}'
}

# ---- network lifecycle -------------------------------------------------------
_fl_alloc() {
    local base=$(( 20000 + (RANDOM % 20000) )) i
    for ((i = 0; i < NODES; i++)); do
        FL_RPCPORTS[i]=$(( base + i * 10 ))
        FL_P2PPORTS[i]=$(( FL_RPCPORTS[i] + 1 ))
        FL_DATADIRS[i]="$(mktemp -d "${TMPDIR:-/tmp}/wpoa_sys_node${i}.XXXXXX")"
    done
}

# Derive per-node weights from $WEIGHTS (space-separated) or a default ramp.
_fl_weights() {
    local i; local -a given=()
    [ -n "${WEIGHTS:-}" ] && read -r -a given <<< "$WEIGHTS"
    FL_TOTAL_WEIGHT=0
    for ((i = 0; i < NODES; i++)); do
        if [ -n "${given[i]:-}" ]; then FL_WEIGHTS[i]=${given[i]}
        else FL_WEIGHTS[i]=$(( 100 + i * 100 )); fi
        FL_TOTAL_WEIGHT=$(( FL_TOTAL_WEIGHT + FL_WEIGHTS[i] ))
    done
}

_fl_bootstrap_node() {
    local i=$1 wpoa_args=$2
    local weight=${FL_WEIGHTS[i]}
    local log="${FL_DATADIRS[i]}/node.log"

    fl_log "bootstrapping node $i (weight=$weight)..."
    # First launch: on a permissioned chain the node initializes, prints the
    # grant hint and exits without serving RPC (with -daemon the launcher still
    # returns 0, so we detect a real join by probing RPC, not the exit code).
    # shellcheck disable=SC2086
    "$BINDIR/multichaind" "$FL_SEED_ADDR" -datadir="${FL_DATADIRS[i]}" -port="${FL_P2PPORTS[i]}" \
        -rpcport="${FL_RPCPORTS[i]}" -weight="$weight" $wpoa_args -daemon > "$log" 2>&1

    local t
    for ((t = 0; t < 5; t++)); do
        if fl_cli "$i" getinfo >/dev/null 2>&1; then
            fl_log "node $i joined directly (no grant needed)"; return 0
        fi
        sleep 1
    done

    local addr; addr="$(_fl_addr_from_log "$log")"
    [ -n "$addr" ] || { cat "$log" >&2; return 1; }
    fl_log "node $i address: $addr -> granting from node 0"
    fl_cli 0 grant "$addr" connect,send,receive,mine >/dev/null 2>&1 || return 1
    fl_cli 0 grant "$addr" wpoa-weights.write >/dev/null 2>&1 || true

    for ((t = 0; t < CONNECT_TIMEOUT; t += 2)); do
        # shellcheck disable=SC2086
        "$BINDIR/multichaind" "$FL_SEED_ADDR" -datadir="${FL_DATADIRS[i]}" -port="${FL_P2PPORTS[i]}" \
            -rpcport="${FL_RPCPORTS[i]}" -weight="$weight" $wpoa_args -daemon > "$log" 2>&1
        fl_wait_rpc "$i" && return 0
        sleep 2
    done
    cat "$log" >&2
    return 1
}

# fl_start_network "<WPOA_ARGS>" — create the chain and bring up all NODES nodes.
# Fatal (fl_die) on any setup failure: the run cannot proceed without a network.
fl_start_network() {
    local wpoa_args=$1
    FL_CHAIN="wpoasys$$"
    _fl_alloc
    _fl_weights
    FL_NET_UP=1   # datadirs exist -> teardown must clean them even if a later step dies

    fl_log "chain=$FL_CHAIN nodes=$NODES weights=(${FL_WEIGHTS[*]:0:$NODES}) total=$FL_TOTAL_WEIGHT"
    [ -n "$wpoa_args" ] && fl_log "node args: $wpoa_args"

    "$BINDIR/multichain-util" create "$FL_CHAIN" -datadir="${FL_DATADIRS[0]}" >/dev/null 2>&1 \
        || fl_die "multichain-util create failed"

    local params="${FL_DATADIRS[0]}/$FL_CHAIN/params.dat"
    [ -f "$params" ] || fl_die "params.dat not found at $params"
    sed -i -E "s/^(target-block-time[[:space:]]*=[[:space:]]*)[0-9]+/\1$TARGET_BLOCK_TIME/" "$params" || true
    sed -i -E "s/^(mine-empty-rounds[[:space:]]*=[[:space:]]*)[-0-9.]+/\11000/"              "$params" || true
    sed -i -E "s/^(setup-first-blocks[[:space:]]*=[[:space:]]*)[0-9]+/\1$SETUP_BLOCKS/"       "$params" || true

    fl_log "starting node 0 (seed, weight=${FL_WEIGHTS[0]})..."
    # shellcheck disable=SC2086
    "$BINDIR/multichaind" "$FL_CHAIN" -datadir="${FL_DATADIRS[0]}" -port="${FL_P2PPORTS[0]}" \
        -rpcport="${FL_RPCPORTS[0]}" -weight="${FL_WEIGHTS[0]}" $wpoa_args -daemon >/dev/null 2>&1 \
        || fl_die "multichaind failed to launch node 0"
    fl_wait_rpc 0 || fl_die "RPC did not come up on node 0"

    # Same-host peers dial loopback (getinfo nodeaddress can be a NAT addr on WSL).
    FL_SEED_ADDR="$FL_CHAIN@127.0.0.1:${FL_P2PPORTS[0]}"
    fl_log "seed node address: $FL_SEED_ADDR"

    local i
    for ((i = 1; i < NODES; i++)); do
        _fl_bootstrap_node "$i" "$wpoa_args" || fl_die "node $i refused to join (see ${FL_DATADIRS[i]}/node.log)"
        fl_wait_rpc "$i" || fl_die "RPC did not come up on node $i"
    done
}

# Wait until EVERY node has the full aggregate weight confirmed on-chain.
fl_wait_weight_convergence() {
    fl_log "waiting for aggregate weight $FL_TOTAL_WEIGHT on ALL $NODES node(s) (timeout ${WEIGHT_TIMEOUT}s)..."
    local deadline=$(( SECONDS + WEIGHT_TIMEOUT )) i all_ok
    while [ "$SECONDS" -lt "$deadline" ]; do
        all_ok=1
        for ((i = 0; i < NODES; i++)); do
            [ "$(fl_node_total "$i")" = "$FL_TOTAL_WEIGHT" ] || { all_ok=0; break; }
        done
        [ "$all_ok" = "1" ] && { fl_log "aggregate weight $FL_TOTAL_WEIGHT confirmed across all $NODES node(s)."; return 0; }
        sleep 3
    done
    for ((i = 0; i < NODES; i++)); do fl_log "node $i: total=$(fl_node_total "$i")"; done
    return 1
}

# Mine until node 0's tip reaches height H (single shared warm-up). Prints a
# progress ping and a stall warning; returns non-zero on timeout.
fl_drive_to_height() {
    local target=$1 timeout=$2 stallmsg=${3:-"chain stalled"}
    fl_log "driving the chain to height $target (timeout ${timeout}s)..."
    local deadline=$(( SECONDS + timeout )) last_h=-1 stall_since=$SECONDS h
    while [ "$SECONDS" -lt "$deadline" ]; do
        h="$(fl_tip_height 0)"; h="${h:-0}"
        [ "$h" -ge "$target" ] && { fl_log "reached height $h."; return 0; }
        if [ "$h" -ne "$last_h" ]; then
            last_h=$h; stall_since=$SECONDS
            [ $(( h % 20 )) -eq 0 ] && fl_log "  height $h / $target"
        elif [ $(( SECONDS - stall_since )) -ge 90 ]; then
            fl_log "  WARNING: $stallmsg — stuck at height $h for 90s"
            stall_since=$SECONDS
        fi
        sleep 2
    done
    h="$(fl_tip_height 0)"; h="${h:-0}"
    fl_log "only reached height $h of $target within ${timeout}s"
    return 1
}

fl_teardown() {
    [ "$FL_NET_UP" = "1" ] || return 0
    echo "  tearing down network..."
    local i
    for ((i = NODES - 1; i >= 0; i--)); do fl_cli "$i" stop >/dev/null 2>&1 || true; done
    sleep 2
    for ((i = 0; i < NODES; i++)); do
        pkill -f "multichaind .*-datadir=${FL_DATADIRS[i]}" >/dev/null 2>&1 || true
        [ "$KEEP_LOGS" = "1" ] || rm -rf "${FL_DATADIRS[i]}"
    done
    FL_NET_UP=0
    FL_DATADIRS=(); FL_RPCPORTS=(); FL_P2PPORTS=(); FL_WEIGHTS=()
}

# ---- assertion bookkeeping ---------------------------------------------------
# A check is a shell function that calls fl_ok / fl_bad / fl_assert_* helpers.
# Wrap it with fl_check_begin NAME CRITICAL ... then read the recorded verdict.

fl_check_begin() {
    FL_CUR_CHECK="$1"
    FL_CUR_CRITICAL="${2:-1}"
    FL_CUR_FAILED=0
    fl_phase "CHECK: $FL_CUR_CHECK$([ "$FL_CUR_CRITICAL" = "0" ] && echo '  (non-critical)')"
}

fl_ok()  { echo "  ✔ $*"; }
fl_bad() { echo "  ✗ $*" >&2; FL_CUR_FAILED=1; }

fl_assert_gt0()  { if [ "${1:-0}" -gt 0 ]; then fl_ok "$2 ($1)"; else fl_bad "$2 (got $1, expected > 0)"; fi; }
fl_assert_zero() { if [ "${1:-0}" -eq 0 ]; then fl_ok "$2 ($1)"; else fl_bad "$2 (got $1, expected 0)"; fi; }
fl_assert_eq()   { if [ "${1:-}" = "${2:-}" ]; then fl_ok "$3 ($1)"; else fl_bad "$3 (got '$1', expected '$2')"; fi; }

# Record the verdict of the check just run. Returns non-zero if it failed and
# was critical (so the caller can react), but always records for the summary.
fl_check_end() {
    local state
    if [ "$FL_CUR_FAILED" = "0" ]; then state="PASS"
    elif [ "$FL_CUR_CRITICAL" = "0" ]; then state="WARN"
    else state="FAIL"; fi
    FL_CHECK_NAMES+=("$FL_CUR_CHECK")
    FL_CHECK_STATE+=("$state")
    echo "  → $FL_CUR_CHECK: $state"
    [ "$state" = "FAIL" ] && return 1 || return 0
}

# Print the results table; return non-zero iff any critical check FAILED.
fl_check_summary() {
    local i any_fail=0
    fl_phase "RESULTS"
    for ((i = 0; i < ${#FL_CHECK_NAMES[@]}; i++)); do
        printf "  %-28s %s\n" "${FL_CHECK_NAMES[i]}" "${FL_CHECK_STATE[i]}"
        [ "${FL_CHECK_STATE[i]}" = "FAIL" ] && any_fail=1
    done
    echo
    if [ "$any_fail" = "1" ]; then echo "  RESULT: FAIL (a critical check failed)"; return 1; fi
    echo "  RESULT: PASS (all critical checks passed)"; return 0
}
