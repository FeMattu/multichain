# shellcheck shell=bash
#
# functional_lib.sh — shared helpers for the project functional tests.
#
# This library is *sourced*, never executed. It factors out the network
# bootstrap, block-height waiting, metrics collection and assertion bookkeeping
# that used to be copy-pasted into every per-feature functional test, so a
# single orchestrated run can start ONE network and check many features on it.
#
# It serves the wPoA, weight-engine and large-network suites alike: a functional run
# exercises all of those layers together, which is why the library (and the suites)
# live at test/functional/ rather than under one module. See
# ../../docs/adr/test-restructure-2026.md.
#
# The bootstrap protocol (permissioned MultiChain: create → grant → rejoin) is
# preserved verbatim from the original per-feature functional tests it replaces,
# which it is known to work against.
#
# Public surface (all prefixed fl_ / FL_):
#   fl_require_binaries                     assert multichaind/-util/-cli exist
#   fl_start_network "<WPOA_ARGS>"          create chain + bootstrap all nodes
#   fl_start_single_node "<NODE_ARGS>"      create chain + ONE genesis node
#   fl_restart_node i "<NODE_ARGS>"         stop + relaunch node i with new args
#   fl_wait_weight_convergence              wait until every node sees TOTAL_WEIGHT
#   fl_drive_to_height H TIMEOUT [STALLMSG] mine until node 0 tip >= H
#   fl_teardown                             stop + wipe every node (idempotent)
#   fl_cli i <args...>                      run multichain-cli against node i
#   fl_node_total i / fl_tip_height i / fl_blockhash_at i H
#   fl_logcount_all "<grep -E pattern>"     sum matches across every node's debug.log
#   fl_cli_q i <args...>                    fl_cli with stderr merged + request echo stripped
#   fl_is_txid STR / fl_node_address i / fl_new_address i
#   fl_apply_param_overrides PARAMS_FILE    write FL_PARAM_OVERRIDES into params.dat
#   Epoch geometry: fl_buried_epoch_at H LEN / fl_height_for_buried_epoch E LEN
#                   fl_setup_first_blocks_floor LEN
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
declare -a FL_DATADIRS=() FL_RPCPORTS=() FL_P2PPORTS=() FL_WEIGHTS=() FL_NODE_ADDR=()

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

# Value of one chain parameter as reported by getblockchainparams, e.g.
#   fl_chain_param 0 mining-diversity  ->  0.3
fl_chain_param() {
    fl_cli "$1" getblockchainparams 2>/dev/null \
        | grep -oE "\"$2\"[[:space:]]*:[[:space:]]*[^,}]+" \
        | sed -E 's/.*:[[:space:]]*//; s/[[:space:]"]+$//' | head -n1
}

# One miner address per line for heights <from>..<to>, in ascending height order.
# listblocks returns the whole range in a single RPC (blockToJSONForListBlocks
# carries "miner"), so this stays one round-trip regardless of the window size.
fl_block_miners() {
    fl_cli "$1" listblocks "$2-$3" 2>/dev/null \
        | grep -oE '"miner"[[:space:]]*:[[:space:]]*"[^"]*"' \
        | sed -E 's/.*"([^"]*)"$/\1/'
}

# The spacing the NATIVE mining-diversity rule would impose, replicating
# mc_Permissions::IsBarredByDiversity: floor(miners*diversity - eps) + 1, clamped to
# [1, miners]. A block is barred when (height - last_mined_by_this_miner) <= spacing-1,
# so spacing 1 is inert and spacing >= 2 forbids consecutive blocks by the same miner.
# Used to assert a run is actually in the regime where the rule would bite.
fl_native_diversity_spacing() {
    awk -v n="$1" -v d="$2" 'BEGIN{
        s=int(n*d-0.000001)+1
        if(s<1)s=1
        if(s>n)s=n
        print s
    }'
}

# "true" / "false" — whether publishing to <stream> needs a write permission.
# Reads the "write" flag of the stream's "restrict" object (liststreams verbose).
fl_stream_write_restricted() {
    fl_cli "$1" liststreams "$2" true 2>/dev/null \
        | sed -nE 's/.*"write"[[:space:]]*:[[:space:]]*(true|false).*/\1/p' | head -n1
}

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

    # Optional extra params.dat overrides (see fl_apply_param_overrides for why anything
    # consensus-critical has to go in the FILE and not on the command line).
    fl_apply_param_overrides "$params"

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

    fl_grant_weights_write
}

# wpoa-weights is a CLOSED stream, so publishing a weight needs an explicit
# per-stream write permission. The grant issued during bootstrap can land before
# node 0 has created the stream (the create is a transaction and needs a block),
# in which case it is silently dropped; re-issue it here, once the stream exists,
# for every joined node. The registration thread retries for minutes, so a grant
# arriving now is still in time.
fl_grant_weights_write() {
    local t i addr
    for ((t = 0; t < 60; t++)); do
        fl_cli 0 liststreams wpoa-weights >/dev/null 2>&1 && break
        sleep 2
    done
    if ! fl_cli 0 liststreams wpoa-weights >/dev/null 2>&1; then
        fl_log "WARNING: wpoa-weights does not exist yet; write grants skipped"
        return 0
    fi
    for ((i = 1; i < NODES; i++)); do
        addr="$(fl_cli "$i" getaddresses 2>/dev/null | sed -nE 's/.*"([A-Za-z0-9]{30,40})".*/\1/p' | head -n1)"
        [ -n "$addr" ] || continue
        fl_cli 0 grant "$addr" wpoa-weights.write >/dev/null 2>&1 \
            && fl_log "granted wpoa-weights.write to node $i ($addr)"
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

# ---- single-node lifecycle ---------------------------------------------------
# Some functional tests need ONE genesis node on a fresh chain rather than the
# multi-node grant/rejoin bootstrap of fl_start_network: the properties they assert
# (stream auto-creation, write policy, schema validation) are visible on a single
# node, and a 3-node network would only make them slower and flakier.
#
# Factored verbatim out of functional_test_weight_engine.sh, whose contract it
# preserves exactly: multichain-util create, target-block-time forced down so
# confirmations are quick, then the daemon with the caller's args and an RPC probe.
# It populates the same FL_* state fl_cli and fl_teardown read, so a single-node test
# gets the shared teardown and logging for free.
#
# fl_start_single_node "<NODE_ARGS>" — fatal (fl_die) if the node does not serve RPC.
fl_start_single_node() {
    local node_args=$1
    FL_CHAIN="${FL_CHAIN_PREFIX:-wesingle}$$"
    NODES=1

    local base=$(( 20000 + (RANDOM % 20000) ))
    FL_RPCPORTS[0]=$base
    FL_P2PPORTS[0]=$(( base + 1 ))
    FL_DATADIRS[0]="$(mktemp -d "${TMPDIR:-/tmp}/wpoa_single.XXXXXX")"
    FL_WEIGHTS[0]=0
    FL_NET_UP=1   # datadir exists -> teardown must clean it even if a later step dies

    fl_log "chain=$FL_CHAIN (single node) datadir=${FL_DATADIRS[0]}"
    [ -n "$node_args" ] && fl_log "node args: $node_args"

    "$BINDIR/multichain-util" create "$FL_CHAIN" -datadir="${FL_DATADIRS[0]}" >/dev/null 2>&1 \
        || fl_die "multichain-util create failed"

    local params="${FL_DATADIRS[0]}/$FL_CHAIN/params.dat"
    [ -f "$params" ] || fl_die "params.dat not found at $params"
    # 2s is the parameter minimum; fast blocks keep grant/publish confirmations quick.
    sed -i -E "s/^(target-block-time[[:space:]]*=[[:space:]]*)[0-9]+/\1$TARGET_BLOCK_TIME/" "$params" || true
    fl_apply_param_overrides "$params"

    # shellcheck disable=SC2086
    "$BINDIR/multichaind" "$FL_CHAIN" -datadir="${FL_DATADIRS[0]}" -port="${FL_P2PPORTS[0]}" \
        -rpcport="${FL_RPCPORTS[0]}" $node_args -daemon >/dev/null 2>&1

    if ! fl_wait_rpc 0; then
        fl_log "daemon did not come up; tail of debug.log:"
        tail -20 "${FL_DATADIRS[0]}/$FL_CHAIN/debug.log" 2>/dev/null
        fl_die "RPC did not come up on the single node"
    fi
}

# Restart node i with a (possibly changed) argument string, and wait for RPC.
#
# Needed because -weighttreasuryaddress cannot be passed at first launch: the genesis
# address does not exist until the node has created its wallet. A node left without the
# flag is the one node computing R_k = 0, so it disagrees with the rest of the network —
# which is why the treasury must be set by a stop/relaunch, not by a later RPC. Mirrors
# helpers/chain_setup.py in the experimental harness.
# fl_restart_node i "<NODE_ARGS>" [CHAIN_SPEC]
#
# CHAIN_SPEC defaults to the bare chain name, which is right for the seed: its datadir
# already holds the chain. A JOINED node is relaunched against the seed address instead,
# so it re-dials a known peer rather than depending on peers.dat having survived.
fl_restart_node() {
    local i=$1 node_args=$2 spec=${3:-$FL_CHAIN}
    fl_cli "$i" stop >/dev/null 2>&1 || true
    sleep 3
    # shellcheck disable=SC2086
    "$BINDIR/multichaind" "$spec" -datadir="${FL_DATADIRS[i]}" -port="${FL_P2PPORTS[i]}" \
        -rpcport="${FL_RPCPORTS[i]}" $node_args -daemon >/dev/null 2>&1
    fl_wait_rpc "$i"
}

# ---- small shared predicates -------------------------------------------------
# multichain-cli echoes the request JSON ({"method":...}) ahead of the response, so a
# naive grep on the output can match the REQUEST instead of the answer. Every caller
# that greps a response needs this, hence one definition.
fl_strip_request_json() { grep -v '"method"'; }

# fl_cli with stderr merged and the request echo stripped: the contract an assertion
# that greps for an ERROR MESSAGE needs, since the error arrives on stderr.
fl_cli_q() { local i=$1; shift; fl_cli "$i" "$@" 2>&1 | fl_strip_request_json; }

# True when the string contains a 64-hex-digit txid, i.e. the call succeeded.
fl_is_txid() { echo "$1" | grep -qiE '[0-9a-f]{64}'; }

# First address of node i's wallet ("" when it has none yet).
fl_node_address() {
    fl_cli "$1" getaddresses 2>/dev/null \
        | sed -nE 's/.*"([A-Za-z0-9]{30,40})".*/\1/p' | head -n1
}

# A fresh address on node i.
fl_new_address() { fl_cli "$1" getnewaddress 2>/dev/null | tr -d '"[:space:]'; }

# ---- params.dat overrides (extracted so both lifecycles share one copy) -------
# Chain parameters are hash-enforced and inherited by joining nodes, so anything
# consensus-critical -- the weight-engine switches, weight-epoch-length, weight-lambda,
# the wPoA phase flags -- belongs in params.dat and NOT on the command line. Passed as a
# runtime flag instead, the value applies to that node only: it diverges from its own
# chain (AppInit2 warns about exactly that), and any parameter DERIVED at genesis is
# computed from the file rather than from the override.
#
# One "key = value" per line in FL_PARAM_OVERRIDES.
fl_apply_param_overrides() {
    local params=$1
    [ -n "${FL_PARAM_OVERRIDES:-}" ] || return 0
    local _k _v _line
    while IFS= read -r _line; do
        [ -z "${_line// /}" ] && continue
        _k="$(printf '%s' "${_line%%=*}" | xargs)"
        _v="$(printf '%s' "${_line#*=}"  | xargs)"
        if grep -qE "^${_k}[[:space:]]*=" "$params"; then
            sed -i -E "s|^(${_k}[[:space:]]*=[[:space:]]*)[^#]*|\1${_v} |" "$params"
            fl_log "params.dat: $_k = $_v"
        else
            fl_log "WARNING: params.dat has no key '$_k'; override skipped"
        fi
    done <<< "$FL_PARAM_OVERRIDES"
}

# ---- epoch geometry ----------------------------------------------------------
# The engine publishes for the newest BURIED epoch: with STABILITY_MARGIN = 6,
#   epoch(height) = (height - 6 + 1) / weight-epoch-length
# (weight_engine.cpp). Duplicated nowhere else — every caller that reasons about which
# epoch a height belongs to uses these, so the arithmetic cannot drift between tests.
FL_STABILITY_MARGIN="${FL_STABILITY_MARGIN:-6}"      # MC_WEIGHT_DEFAULT_STABILITY_MARGIN
FL_SETUP_PUBLISH_MARGIN="${FL_SETUP_PUBLISH_MARGIN:-3}"  # MC_WEIGHT_SETUP_PUBLISH_MARGIN

# The newest epoch buried at a given tip height (0 = nothing buried yet).
fl_buried_epoch_at() {
    local h=$1 len=$2 stable=$(( $1 - FL_STABILITY_MARGIN ))
    [ "$stable" -lt 0 ] && { echo 0; return; }
    echo $(( (stable + 1) / len ))
}

# The tip height at which epoch e first becomes buried.
fl_height_for_buried_epoch() {
    echo $(( $1 * $2 + FL_STABILITY_MARGIN - 1 ))
}

# The setup-first-blocks floor the node derives at genesis
# (mc_MultichainParams::AdjustSetupFirstBlocks):
#   first_computable = len + STABILITY_MARGIN - 1
#   floor            = first_computable + SETUP_PUBLISH_MARGIN + 1
# The trailing +1 is load-bearing: at exactly first_computable + margin the confirming
# block would land on the first wPoA height, which cannot be produced without the
# registry it would populate.
fl_setup_first_blocks_floor() {
    echo $(( $1 + FL_STABILITY_MARGIN - 1 + FL_SETUP_PUBLISH_MARGIN + 1 ))
}

# ---- published-weight verification (weightverifyweights) ---------------------
# The RPC answers with
#   { "epoch": n, "verified": bool, "records": n, "invalid": n, "entries": [ ... ] }
# where each entry carries address / published / published_epoch / recomputed / verdict,
# and verdict is one of: ok | mismatch | not-a-cluster | other-epoch | unverified.
#
# Parsed with python3 rather than sed because a verdict tally has to look INSIDE the
# entries array, and a regex over the flat text would happily count the word "mismatch"
# out of the RPC's own help string. python3 is already a dependency of this suite
# (analyze_distribution.py).

# One top-level field of the verification report ("" when absent / unparsable).
fl_verify_field() {
    fl_cli "$1" weightverifyweights 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
v = d.get(sys.argv[1])
if isinstance(v, bool):
    print("true" if v else "false")
elif v is not None:
    print(v)
' "$2" 2>/dev/null
}

# How many entries carry a given verdict. Prints 0 when the report is empty, so callers
# can compare numerically without guarding.
fl_verdict_count() {
    fl_cli "$1" weightverifyweights 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print(0); sys.exit(0)
want = sys.argv[1]
print(sum(1 for e in d.get("entries", []) if e.get("verdict") == want))
' "$2" 2>/dev/null || echo 0
}

# A one-line tally for the evidence log: "epoch=3 verified=true records=4 ok=3
# other-epoch=1 mismatch=0 not-a-cluster=0 unverified=0".
fl_verdict_tally() {
    fl_cli "$1" weightverifyweights 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print("(no verification report)"); sys.exit(0)
es = d.get("entries", [])
c = {}
for e in es:
    c[e.get("verdict", "?")] = c.get(e.get("verdict", "?"), 0) + 1
order = ["ok", "other-epoch", "mismatch", "not-a-cluster", "unverified"]
parts = ["epoch=%s" % d.get("epoch"), "verified=%s" % d.get("verified"),
         "records=%s" % d.get("records"), "invalid=%s" % d.get("invalid")]
parts += ["%s=%d" % (k, c.get(k, 0)) for k in order]
for k in sorted(c):
    if k not in order:
        parts.append("%s=%d" % (k, c[k]))
print("  ".join(parts))
' 2>/dev/null || echo "(no verification report)"
}

# ---- treasury address --------------------------------------------------------
# R_k is the native-currency value paid to the TREASURY address by transactions the
# miner signed, derived from the epoch's confirmed blocks. Every node must resolve the
# SAME address -- it is consensus-critical, and nodes disagreeing about it compute
# different R_k and therefore different w_k.
#
# The flag cannot be passed at first launch: the genesis address does not exist until
# the node has created its wallet. So the sequence is start -> read address -> derive a
# treasury -> RESTART EVERY NODE with the flag. A node left without it is the one node
# computing R_k = 0, which is a fork, not a degradation. Mirrors
# helpers/chain_setup.py in the experimental harness.
#
# Deliberately returns a DEDICATED address rather than reusing the admin's. With the
# admin as treasury, an admin -> node payment sends its CHANGE back to the treasury, so
# mc_ValuePaidToTreasury sees a positive value and the transaction is only spared by the
# `signer == treasury` guard in mc_AccumulateReconciliation. That guard is correct, but
# a refuel path whose safety rests on one `continue` is not worth the risk in a test
# whose job is to prove the direction rule. A separate address cannot touch it at all.
fl_make_treasury_address() {
    local i=$1 addr
    addr="$(fl_new_address "$i")"
    [ -n "$addr" ] || return 1
    fl_cli "$i" grant "$addr" receive >/dev/null 2>&1 || true
    echo "$addr"
}

# Restart every node with a new argument string. The SEED goes first so it is serving
# again before any joined node tries to re-dial it; the joined nodes then come back
# against the seed address.
fl_restart_all_nodes() {
    local node_args=$1 i pids=()
    fl_log "restarting all $NODES node(s) with: $node_args"

    # The seed first and alone: the others re-dial it, so it has to be serving before
    # they come back.
    fl_restart_node 0 "$node_args" || fl_die "the seed node did not come back up after the restart"
    fl_log "node 0 (seed) back up"

    # The rest concurrently. Sequentially this costs 3s + RPC wait per node, and with 33
    # nodes that is minutes of the network running degraded -- long enough, at
    # target-block-time 2, to matter to the setup-phase budget.
    if [ "${FL_BOOTSTRAP_PARALLEL:-1}" = "1" ] && [ "$NODES" -gt 2 ]; then
        for ((i = 1; i < NODES; i++)); do
            fl_restart_node "$i" "$node_args" "$FL_SEED_ADDR" >/dev/null 2>&1 &
            pids+=($!)
        done
        for p in "${pids[@]}"; do wait "$p" 2>/dev/null || true; done
        local up=0
        for ((i = 0; i < NODES; i++)); do fl_cli "$i" getinfo >/dev/null 2>&1 && up=$(( up + 1 )); done
        fl_log "  $up of $NODES node(s) back up"
        [ "$up" -eq "$NODES" ] || fl_die "only $up of $NODES nodes came back after the restart"
    else
        for ((i = 1; i < NODES; i++)); do
            fl_restart_node "$i" "$node_args" "$FL_SEED_ADDR" \
                || fl_die "node $i did not come back up after the restart"
        done
    fi
}

# ---- role-differentiated network --------------------------------------------
# fl_start_network bootstraps a HOMOGENEOUS set: every node gets `mine` and a static
# -weight. The large-network topology is not homogeneous -- miners mine, companies
# generate activity and must NOT mine, Certification Authorities sign ESG and must not
# mine either -- so it needs its own bootstrap. The grant/rejoin dance itself is
# identical and is not duplicated: only the permission set differs per role.
#
# Deliberately NO static -weight here. That is the other weight path (a fixed value the
# node publishes for itself); this network is about the weight the ENGINE computes, and
# a static value would sit alongside it as a second, epoch-less record.
#
# Caller sets FL_ROLE, one entry per node, index 0 = the genesis admin:
#   FL_ROLE=(admin miner miner ... company ... ca ca)
#
# Roles and what each is granted from node 0:
#   admin     genesis; holds everything by construction
#   miner     connect,send,receive,mine   + wpoa-weights.write, membership.write
#   company   connect,send,receive        + membership.write        (NO mine)
#   ca        connect,send,receive        + high1, esg.write        (NO mine)
#
# fl_start_role_network "<COMMON_ARGS>" — fatal on any setup failure.
fl_start_role_network() {
    local common_args=$1 i
    FL_CHAIN="${FL_CHAIN_PREFIX:-wpoarole}$$"
    _fl_alloc
    FL_NET_UP=1   # datadirs exist -> teardown must clean them even if a later step dies

    fl_log "chain=$FL_CHAIN nodes=$NODES roles=(${FL_ROLE[*]})"
    [ -n "$common_args" ] && fl_log "common node args: $common_args"

    "$BINDIR/multichain-util" create "$FL_CHAIN" -datadir="${FL_DATADIRS[0]}" >/dev/null 2>&1 \
        || fl_die "multichain-util create failed"

    local params="${FL_DATADIRS[0]}/$FL_CHAIN/params.dat"
    [ -f "$params" ] || fl_die "params.dat not found at $params"
    sed -i -E "s/^(target-block-time[[:space:]]*=[[:space:]]*)[0-9]+/\1$TARGET_BLOCK_TIME/" "$params" || true
    sed -i -E "s/^(mine-empty-rounds[[:space:]]*=[[:space:]]*)[-0-9.]+/\11000/"              "$params" || true
    # setup-first-blocks is NOT forced here, but a caller SHOULD pass one through
    # FL_PARAM_OVERRIDES on a network of any size -- see fl_setup_blocks_for_network.
    #
    # The genesis node derives a floor and writes it into params.dat before the parameter
    # hash is taken, which covers the EPOCH GEOMETRY (when the first weight can confirm)
    # and nothing else. It cannot know how long bringing N daemons up takes, and past a
    # handful of nodes that is the larger of the two: the chain reaches the floor before
    # the registry has anything in it, wPoA elects nobody, and the chain stops. Passing a
    # LARGER value is safe -- AdjustSetupFirstBlocks only ever raises to its floor and
    # leaves a bigger value untouched -- and lengthening the setup phase is the fix, not
    # a side effect.
    fl_apply_param_overrides "$params"

    fl_log "starting node 0 (genesis / admin)..."
    # shellcheck disable=SC2086
    "$BINDIR/multichaind" "$FL_CHAIN" -datadir="${FL_DATADIRS[0]}" -port="${FL_P2PPORTS[0]}" \
        -rpcport="${FL_RPCPORTS[0]}" $common_args -daemon >/dev/null 2>&1 \
        || fl_die "multichaind failed to launch node 0"
    fl_wait_rpc 0 || fl_die "RPC did not come up on node 0"

    # Same-host peers dial loopback (getinfo nodeaddress can be a NAT addr on WSL).
    FL_SEED_ADDR="$FL_CHAIN@127.0.0.1:${FL_P2PPORTS[0]}"
    fl_log "seed node address: $FL_SEED_ADDR"

    # PARALLEL, and this is a correctness fix rather than a speed-up.
    #
    # Bootstrapping sequentially costs 10-30s per node while the seed keeps mining. At 33
    # nodes and target-block-time 2 that is 150-500 BLOCKS consumed before the first
    # membership record is even published -- past setup-first-blocks, where wPoA takes
    # over and finds an empty weight registry, elects nobody, and the chain stops dead.
    # The join itself is independent per node (each one talks only to the seed), so the
    # only serialised part is the grant, which must come from node 0.
    #
    # Two phases: every node makes its first launch and prints its address concurrently,
    # then node 0 issues all the grants in one pass, then every node relaunches
    # concurrently. FL_BOOTSTRAP_PARALLEL=0 falls back to the sequential path.
    if [ "${FL_BOOTSTRAP_PARALLEL:-1}" = "1" ] && [ "$NODES" -gt 2 ]; then
        _fl_bootstrap_role_nodes_parallel "$common_args" || fl_die "parallel bootstrap failed"
    else
        for ((i = 1; i < NODES; i++)); do
            _fl_bootstrap_role_node "$i" "$common_args" || \
                fl_die "node $i (${FL_ROLE[i]}) refused to join (see ${FL_DATADIRS[i]}/node.log)"
        done
    fi
}

# Phase 1: first launch, concurrently. On a permissioned chain the node initialises,
# prints the grant hint and exits without serving RPC.
_fl_first_launch_one() {
    local i=$1 common_args=$2
    # shellcheck disable=SC2086
    "$BINDIR/multichaind" "$FL_SEED_ADDR" -datadir="${FL_DATADIRS[i]}" -port="${FL_P2PPORTS[i]}" \
        -rpcport="${FL_RPCPORTS[i]}" $common_args -daemon > "${FL_DATADIRS[i]}/node.log" 2>&1
}

_fl_bootstrap_role_nodes_parallel() {
    local common_args=$1 i pids=()

    fl_log "phase 1/3: first launch of $(( NODES - 1 )) nodes, concurrently"
    for ((i = 1; i < NODES; i++)); do
        _fl_first_launch_one "$i" "$common_args" &
        pids+=($!)
    done
    for p in "${pids[@]}"; do wait "$p" 2>/dev/null || true; done
    sleep 3   # let the hints land in the logs

    fl_log "phase 2/3: granting from node 0 (serialised -- only the admin can grant)"
    local granted=0 already=0
    declare -a NEEDS_GRANT=()
    for ((i = 1; i < NODES; i++)); do
        if fl_cli "$i" getinfo >/dev/null 2>&1; then
            already=$(( already + 1 ))           # joined directly, no grant needed
            continue
        fi
        local addr; addr="$(_fl_addr_from_log "${FL_DATADIRS[i]}/node.log")"
        if [ -z "$addr" ]; then
            fl_log "  WARNING: node $i printed no grant hint; see ${FL_DATADIRS[i]}/node.log"
            continue
        fi
        FL_NODE_ADDR[i]="$addr"
        if fl_cli 0 grant "$addr" "$(_fl_role_global_perms "${FL_ROLE[i]:-company}")" >/dev/null 2>&1; then
            granted=$(( granted + 1 )); NEEDS_GRANT+=("$i")
        else
            fl_log "  WARNING: grant failed for node $i ($addr)"
        fi
    done
    fl_log "  granted $granted node(s); $already had already joined"
    # One confirmation wait for ALL the grants, instead of one per node.
    sleep $(( TARGET_BLOCK_TIME * 4 ))

    fl_log "phase 3/3: relaunching $granted node(s), concurrently"
    pids=()
    for i in "${NEEDS_GRANT[@]}"; do
        ( for ((t = 0; t < CONNECT_TIMEOUT; t += 2)); do
              _fl_first_launch_one "$i" "$common_args"
              for ((u = 0; u < 10; u++)); do
                  fl_cli "$i" getinfo >/dev/null 2>&1 && exit 0
                  sleep 1
              done
              sleep 2
          done
          exit 1 ) &
        pids+=($!)
    done
    local failed=0 idx=0
    for p in "${pids[@]}"; do
        wait "$p" 2>/dev/null || { fl_log "  node ${NEEDS_GRANT[idx]} did not come up"; failed=$(( failed + 1 )); }
        idx=$(( idx + 1 ))
    done

    local up=0
    for ((i = 0; i < NODES; i++)); do
        fl_cli "$i" getinfo >/dev/null 2>&1 && up=$(( up + 1 ))
    done
    fl_log "  $up of $NODES node(s) serving RPC"
    [ "$up" -eq "$NODES" ] || return 1
    return 0
}

# The per-role permission set. Split out so the grant list is readable and so the
# post-join re-grant below can reuse it verbatim.
_fl_role_global_perms() {
    case "$1" in
        miner)   echo "connect,send,receive,mine" ;;
        company) echo "connect,send,receive" ;;
        ca)      echo "connect,send,receive" ;;
        *)       echo "connect,send,receive" ;;
    esac
}

_fl_bootstrap_role_node() {
    local i=$1 common_args=$2
    local role=${FL_ROLE[i]:-company}
    local log="${FL_DATADIRS[i]}/node.log"

    fl_log "bootstrapping node $i (role=$role)..."
    # First launch: on a permissioned chain the node initializes, prints the grant hint
    # and exits without serving RPC (with -daemon the launcher still returns 0, so a real
    # join is detected by probing RPC, not by the exit code).
    # shellcheck disable=SC2086
    "$BINDIR/multichaind" "$FL_SEED_ADDR" -datadir="${FL_DATADIRS[i]}" -port="${FL_P2PPORTS[i]}" \
        -rpcport="${FL_RPCPORTS[i]}" $common_args -daemon > "$log" 2>&1

    local t
    for ((t = 0; t < 5; t++)); do
        if fl_cli "$i" getinfo >/dev/null 2>&1; then
            fl_log "node $i joined directly (no grant needed)"; return 0
        fi
        sleep 1
    done

    local addr; addr="$(_fl_addr_from_log "$log")"
    [ -n "$addr" ] || { cat "$log" >&2; return 1; }
    fl_log "node $i ($role) address: $addr -> granting $(_fl_role_global_perms "$role")"
    fl_cli 0 grant "$addr" "$(_fl_role_global_perms "$role")" >/dev/null 2>&1 || return 1

    for ((t = 0; t < CONNECT_TIMEOUT; t += 2)); do
        # shellcheck disable=SC2086
        "$BINDIR/multichaind" "$FL_SEED_ADDR" -datadir="${FL_DATADIRS[i]}" -port="${FL_P2PPORTS[i]}" \
            -rpcport="${FL_RPCPORTS[i]}" $common_args -daemon > "$log" 2>&1
        fl_wait_rpc "$i" && return 0
        sleep 2
    done
    cat "$log" >&2
    return 1
}

# ---- native currency ---------------------------------------------------------
# MultiChain defaults initial-block-reward = 0, so on a stock chain there IS NO spendable
# native currency and every balance below reads 0 forever. That is not a cosmetic detail:
# ComputeEpochFacts derives the credits, the debits AND R_k from native output values, so
# without native currency R_k = 0, the saldo is 0, RestitutionRate hits its saldo <= 0
# guard and rho is pinned at 0 for every cluster -- w_k collapses to W_k * (1 - lambda),
# a uniform scaling, and the restitution feedback is inert no matter how many epochs run.
#
# A suite that needs the feedback to MOVE must therefore enable the native currency in
# its own params.dat (initial-block-reward, plus first-block-reward to premine the
# genesis admin). See docs/adr/test-restructure-2026.md §6.2.

# Wallet-wide native balance of node i, as a decimal string ("0" when unreadable).
fl_native_balance() {
    fl_cli "$1" getbalance 2>/dev/null | tr -d '"[:space:]' | grep -E '^-?[0-9]+(\.[0-9]+)?$' || echo 0
}

# Numeric compare for decimal balances, since [ -lt ] is integer-only.
# fl_lt A B -> true when A < B
fl_lt() { awk -v a="$1" -v b="$2" 'BEGIN{exit !(a+0 < b+0)}'; }

# Send `amount` of NATIVE currency from node 0 (the admin) to node i's first address,
# logging the balance either side, the amount and the txid.
#
# DIRECTION MATTERS, and this is the safe direction. R_k credits the SIGNERS of a
# transaction by what that transaction pays TO THE TREASURY
# (mc_AccumulateReconciliation + mc_ValuePaidToTreasury). A refuel is admin -> node:
# the signer is the admin and the outputs pay the node, so the value paid to the
# treasury is 0 and nothing accumulates. A reconciliation is the opposite,
# node -> treasury. Provided the treasury is NOT the admin's own address, a refuel
# cannot touch R_k at all -- which is why fl_make_treasury_address returns a dedicated
# one rather than reusing the admin's.
fl_refuel_node() {
    local i=$1 amount=$2 addr before after txid
    addr="$(fl_node_address "$i")"
    if [ -z "$addr" ]; then
        fl_log "  REFUEL node $i: no address to fund"
        return 1
    fi
    before="$(fl_native_balance "$i")"
    txid="$(fl_cli 0 sendtoaddress "$addr" "$amount" 2>/dev/null | tr -d '"[:space:]')"
    if ! fl_is_txid "$txid"; then
        fl_log "  REFUEL node $i ($addr): FAILED -- admin could not send $amount (out of funds?)"
        return 1
    fi
    after="$(fl_native_balance "$i")"
    fl_log "  REFUEL node $i ($addr): balance $before -> $after  (+$amount)  txid=$txid"
    echo "$txid"
}

# ---- proposer tally ----------------------------------------------------------
# "addr count" per line, descending, over the closed height range [from, to].
# listblocks carries the miner, so this is one RPC regardless of the window size.
fl_proposer_tally() {
    fl_block_miners "$1" "$2" "$3" | sort | uniq -c | sort -rn | awk '{print $2, $1}'
}

# ---- reconciliation direction -----------------------------------------------
# The native value a transaction pays TO a given address, summed over its outputs.
#
# This is the shell mirror of mc_ValuePaidToTreasury (weight_engine/weight_records.h):
# R_k is the value paid to the treasury by transactions the miner SIGNED, so "does this
# transaction pay the treasury" is exactly the predicate that decides whether it counts
# as a reconciliation. There is no RPC that exposes R_k, so this is how the direction
# rule is asserted -- on the transaction itself, against the same quantity the engine
# reads, rather than on a derived weight where the signal would be buried in epoch noise.
#
# Prints a decimal total; 0 when the transaction pays that address nothing.
fl_tx_value_to_address() {
    local i=$1 txid=$2 addr=$3
    fl_cli "$i" getrawtransaction "$txid" 1 2>/dev/null | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print(0); sys.exit(0)
want = sys.argv[1]
total = 0.0
for o in d.get("vout", []):
    spk = o.get("scriptPubKey", {}) or {}
    addrs = spk.get("addresses") or ([spk["address"]] if spk.get("address") else [])
    if want in addrs:
        try:
            total += float(o.get("value") or 0)
        except (TypeError, ValueError):
            pass
print(("%.8f" % total).rstrip("0").rstrip(".") or 0)
' "$addr" 2>/dev/null || echo 0
}

# True when the decimal string is numerically zero.
fl_is_zero() { awk -v a="$1" 'BEGIN{exit !(a+0 == 0)}'; }

# ---- setup-phase budgeting ---------------------------------------------------
# THE DEADLOCK THIS EXISTS TO PREVENT, because it is a race and not an arithmetic error.
#
# fl_setup_first_blocks_floor answers "how many blocks must pass before the first weight
# can be CONFIRMED", which is pure epoch geometry: epoch_len + 9. The node derives the
# same figure at genesis. But the floor knows nothing about WALL CLOCK, and wPoA engaging
# is a race between two things measured in different units:
#
#   * the chain reaching setup-first-blocks   -- blocks, at target-block-time each;
#   * this harness finishing the bootstrap    -- seconds: N nodes joining, then the
#     grants, then membership and ESG published and confirmed.
#
# With 3 nodes and a short epoch the first is slower, so the floor is enough and the
# bootstrap suite passes. With 33 nodes it inverts: even a brisk 8s per node is 256s,
# i.e. 128 blocks at target-block-time 2, and the chain is past a floor of 109 before a
# single membership record exists. wPoA then takes over an EMPTY registry, elects nobody,
# and the chain stops -- reporting "0 validators, total=0", which reads like a weight
# bug and is really a stopwatch.
#
# So the setup phase must also cover the bootstrap, in blocks:
#
#   setup >= (per-node bootstrap seconds * nodes + input publication) / target-block-time
#
# Safe to set: AdjustSetupFirstBlocks only ever RAISES setup-first-blocks to its floor and
# leaves a larger value untouched, so a generous value here cannot conflict with the
# derivation. It costs blocks, not correctness.
#
# fl_setup_blocks_for_network NODES EPOCH_LEN [SECONDS_PER_NODE]
fl_setup_blocks_for_network() {
    local nodes=$1 len=$2 per_node=${3:-${FL_BOOTSTRAP_SECONDS_PER_NODE:-6}}
    local tbt=${TARGET_BLOCK_TIME:-2}
    local floor; floor="$(fl_setup_first_blocks_floor "$len")"

    # Bootstrap: parallel, so the cost is dominated by the slowest node plus the grant
    # pass rather than by the sum -- but keep a per-node term, because 33 daemons
    # contend for one host's CPU and disk.
    local boot_s=$(( per_node * nodes / 2 + 60 ))
    local inputs_s=$(( tbt * 12 + nodes ))         # grants + membership + ESG, confirmed
    local need=$(( (boot_s + inputs_s) / tbt ))

    # Plus the epoch geometry itself, and 50% head-room: this is a deadline, and
    # overshooting wastes blocks while undershooting kills the run.
    need=$(( (need + floor) * 3 / 2 ))
    [ "$need" -lt "$floor" ] && need="$floor"
    echo "$need"
}

# Wait until the weight registry is genuinely usable: at least `want` validators carrying
# a NON-ZERO weight, as seen by node 0.
#
# Non-zero matters. Efraimidis-Spirakis cannot draw a zero-weight key (Cor. 5.4), so a
# registry listing validators at weight 0 elects nobody just as surely as an empty one.
#
# Returns 0 when ready. Returns 1 on timeout, having logged the diagnosis -- and the
# diagnosis is the point: without it a caller sees only a chain that stopped.
fl_wait_registry_ready() {
    local want=$1 timeout=$2 setup_blocks=${3:-0}
    local deadline=$(( SECONDS + timeout )) n h
    fl_log "waiting for >= $want validator(s) with a non-zero weight (timeout ${timeout}s)..."
    while [ "$SECONDS" -lt "$deadline" ]; do
        n="$(fl_cli 0 getallweights 2>/dev/null \
             | grep -oE '"[A-Za-z0-9]{30,40}"[[:space:]]*:[[:space:]]*[0-9]+' \
             | sed -E 's/.*:[[:space:]]*//' | awk '$1>0' | wc -l)"
        n="${n:-0}"
        h="$(fl_tip_height 0)"; h="${h:-0}"
        if [ "$n" -ge "$want" ]; then
            fl_log "registry ready: $n scoreable validator(s) at height $h"
            return 0
        fi
        if [ "$setup_blocks" -gt 0 ] && [ "$h" -ge "$setup_blocks" ]; then
            fl_log "  !! height $h has reached setup-first-blocks=$setup_blocks with only $n scoreable validator(s)."
            fl_log "     wPoA now governs and the registry cannot elect a proposer: the chain will stop here."
            fl_log "     This is the bootstrap race, not a weight-pipeline fault -- raise setup-first-blocks"
            fl_log "     (WE_LARGE_SETUP_BLOCKS) or lower the node count."
            return 1
        fi
        sleep 3
    done
    fl_log "  !! timed out with $n scoreable validator(s) at height $h (wanted $want)"
    return 1
}

# ---- run recording -----------------------------------------------------------
# A functional run is a one-shot experiment on a live network: once the nodes are torn
# down the evidence is gone. These helpers stream the observations to CSV AS THEY ARE
# TAKEN, under test/output/<experiment>/, so an analysis can be re-run, compared across
# runs, or checked by someone who was not there. we_stats.py consumes exactly this layout.
#
# Recording is append-only and cheap, and deliberately happens DURING the drive loop
# rather than at the end: a run that stalls at epoch 12 still leaves 12 epochs of data
# to diagnose it with, which is the case where the evidence matters most.

FL_RUN_DIR=""

# fl_record_begin <experiment-name> [output-root]
fl_record_begin() {
    local name=$1 root=${2:-${FL_OUTPUT_ROOT:-}}
    if [ -z "$root" ]; then
        fl_log "WARNING: no output root; recording disabled"
        return 1
    fi
    FL_RUN_DIR="$root/$name"
    mkdir -p "$FL_RUN_DIR" || { fl_log "WARNING: cannot create $FL_RUN_DIR"; FL_RUN_DIR=""; return 1; }

    echo "height,miner"                                                   > "$FL_RUN_DIR/proposers.csv"
    echo "epoch,address,weight"                                           > "$FL_RUN_DIR/weights.csv"
    echo "epoch,height,verified_epoch,mismatch,not_a_cluster,other_epoch,refuels" \
                                                                          > "$FL_RUN_DIR/epochs.csv"
    echo "epoch,node,role,balance"                                        > "$FL_RUN_DIR/gas.csv"
    echo "epoch,node,role,before,after,amount,txid"                       > "$FL_RUN_DIR/refuels.csv"
    fl_log "recording this run to $FL_RUN_DIR"
    return 0
}

# fl_record_meta <experiment> <json-object-of-parameters>
fl_record_meta() {
    [ -n "$FL_RUN_DIR" ] || return 0
    printf '{\n  "experiment": "%s",\n  "started": "%s",\n  "chain": "%s",\n  "nodes": %s,\n  "parameters": %s\n}\n' \
        "$1" "$(date -Is)" "$FL_CHAIN" "$NODES" "$2" > "$FL_RUN_DIR/meta.json"
}

fl_record_finish() {
    [ -n "$FL_RUN_DIR" ] || return 0
    [ -f "$FL_RUN_DIR/meta.json" ] || return 0
    python3 - "$FL_RUN_DIR/meta.json" <<'PYEOF' 2>/dev/null || true
import json, sys, datetime
p = sys.argv[1]
try:
    d = json.load(open(p))
except Exception:
    sys.exit(0)
d["finished"] = datetime.datetime.now().astimezone().isoformat()
json.dump(d, open(p, "w"), indent=2)
PYEOF
}

# Every miner in the closed height range, one row per block: "height,miner".
#
# The height comes from the block object, NOT from a counter seeded at $from. listblocks
# makes no ordering guarantee, and any mismatch between the blocks returned and the width
# of the range would silently shift every following row -- corrupting the proposer
# distribution instead of failing, which is the worst outcome for a statistical test.
#
# NOTE the two-step declaration. `local from=$1 to=$2 h=$from` does NOT work: local is a
# builtin, so all of its arguments are word-expanded BEFORE any assignment takes effect,
# making $from the (unset) outer variable -- fatal under `set -u`, and only at the first
# epoch rollover, hours into a large run.
fl_record_proposers() {
    [ -n "$FL_RUN_DIR" ] || return 0
    local from to
    from=$1
    to=$2
    fl_cli 0 listblocks "$from-$to" 2>/dev/null | python3 -c '
import sys, json
try:
    blocks = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if not isinstance(blocks, list):
    sys.exit(0)
for b in blocks:
    if not isinstance(b, dict):
        continue
    h, m = b.get("height"), b.get("miner")
    if h is None or not m:
        continue
    print("%s,%s" % (h, m))
' >> "$FL_RUN_DIR/proposers.csv"
}

# The whole weight map as node 0 sees it, stamped with the epoch.
fl_record_weights() {
    [ -n "$FL_RUN_DIR" ] || return 0
    local epoch=$1
    fl_cli 0 getallweights 2>/dev/null \
        | grep -oE '"[A-Za-z0-9]{30,40}"[[:space:]]*:[[:space:]]*[0-9]+' \
        | sed -E 's/"//g; s/[[:space:]]*:[[:space:]]*/,/' \
        | awk -v e="$epoch" -F, '{printf "%s,%s,%s\n", e, $1, $2}' \
        >> "$FL_RUN_DIR/weights.csv"
}

# fl_record_epoch <epoch> <height> <verified> <mismatch> <not_a_cluster> <other_epoch> <refuels>
fl_record_epoch() {
    [ -n "$FL_RUN_DIR" ] || return 0
    printf '%s,%s,%s,%s,%s,%s,%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$FL_RUN_DIR/epochs.csv"
}

# fl_record_gas <epoch> — one row per node, with its role.
fl_record_gas() {
    [ -n "$FL_RUN_DIR" ] || return 0
    local epoch=$1 i
    for ((i = 0; i < NODES; i++)); do
        printf '%s,%s,%s,%s\n' "$epoch" "$i" "${FL_ROLE[i]:-?}" "$(fl_native_balance "$i")" \
            >> "$FL_RUN_DIR/gas.csv"
    done
}

# fl_record_refuel <epoch> <node> <before> <after> <amount> <txid>
fl_record_refuel() {
    [ -n "$FL_RUN_DIR" ] || return 0
    printf '%s,%s,%s,%s,%s,%s,%s\n' "$1" "$2" "${FL_ROLE[$2]:-?}" "$3" "$4" "$5" "$6" \
        >> "$FL_RUN_DIR/refuels.csv"
}

# Hand the recorded run to the analyser. Returns its exit code, so a statistical
# failure can fail the suite.
fl_record_analyse() {
    [ -n "$FL_RUN_DIR" ] || { fl_log "no recorded run to analyse"; return 0; }
    local lib="${FL_LIB_DIR:-$(dirname "${BASH_SOURCE[0]}")}"
    fl_phase "STATISTICS — analysing the recorded run"
    python3 "$lib/we_stats.py" "$FL_RUN_DIR" "$@"
    local rc=$?
    fl_log "report:  $FL_RUN_DIR/report.md"
    fl_log "summary: $FL_RUN_DIR/summary.txt"
    return "$rc"
}
