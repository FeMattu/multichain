#!/usr/bin/env bash
#
# lint_lib.sh — validates the functional harness itself. NEEDS NO NODE.
#
# WHY THIS EXISTS
#
# The functional suites are expensive: the large-network run mines thousands of blocks
# over hours. Several library functions execute only deep inside that run -- the
# per-epoch recorders fire for the first time at the FIRST EPOCH ROLLOVER. A typo there
# is not caught by `bash -n` (it is valid syntax), is not caught by any other suite
# (they do not record), and surfaces as a crash after the network is already up and
# hundreds of blocks deep. That is the single most expensive way to learn about a typo.
#
# This suite exercises those functions with STUBBED RPCs, in under a second, so the
# harness is checked before a real network is paid for.
#
# The bug that motivated it, kept as an explicit regression check below:
#
#     local from=$1 to=$2 h=$from        # in fl_record_proposers
#
# `local` is a builtin, so ALL of its arguments are word-expanded BEFORE any assignment
# takes effect. $from therefore resolved to the (unset) OUTER variable -- fatal under
# `set -u`, and only at the first epoch rollover.
#
# Usage:
#   ./test/functional/lib/lint_lib.sh
#   ./test/functional/run_functional_tests.sh --suite lib-lint
#
# Exit code: 0 iff every critical check passed.
set -uo pipefail

LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FUNC_DIR="$(cd "$LIB_DIR/.." && pwd)"
REPO_DIR="$(cd "$FUNC_DIR/../.." && pwd)"

# shellcheck source=/dev/null
. "$LIB_DIR/functional_lib.sh"

WORK="$(mktemp -d)"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

echo "══════════════════════════════════════════════════════════════════════"
echo "  functional harness lint — no node required"
echo "══════════════════════════════════════════════════════════════════════"
echo "  library: $LIB_DIR/functional_lib.sh"
echo "  scratch: $WORK"

# =============================================================================
# A — STATIC
# =============================================================================
fl_phase "STATIC — syntax, and the traps that syntax checking cannot see"

fl_check_begin "every_script_parses" 1
    n=0
    while IFS= read -r f; do
        n=$(( n + 1 ))
        if out="$(bash -n "$f" 2>&1)"; then :; else
            fl_bad "bash -n failed: $f"
            printf '%s\n' "$out" | sed 's/^/      /'
        fi
    done < <(find "$FUNC_DIR" -name '*.sh' -type f | sort)
    fl_assert_gt0 "$n" "shell scripts parsed"
fl_check_end || true

fl_check_begin "no_self_reference_in_a_single_local" 1
    # `local a=$1 b=$a` reads the OUTER $a. Valid syntax, wrong semantics, and under
    # `set -u` a hard crash. Nothing but a targeted scan finds this: shellcheck is not
    # installed in this environment, and `bash -n` accepts it.
    #
    # Only tokens that reference a name assigned EARLIER IN THE SAME `local`/`declare`
    # statement are reported, so the safe `local a; a=$(...); a="${a:-0}"` idiom (three
    # separate commands) does not trip it.
    hits=0
    while IFS= read -r f; do
        found="$(awk -v F="$f" '
          /^[[:space:]]*(local|declare|typeset)[[:space:]]/ {
            line=$0; s=line
            sub(/^[[:space:]]*(local|declare|typeset)[[:space:]]+/, "", s)
            # Scan only the `local` COMMAND, not the whole physical line. `local a; a=$1;
            # a="${a:-0}"` is three commands and is perfectly safe, so anything after the
            # first command separator must not be treated as part of the declaration.
            if (match(s, /;|&&|\|\|/)) s = substr(s, 1, RSTART - 1)
            n=0
            cnt=split(s, w, /[[:space:]]+/)
            for (i = 1; i <= cnt; i++) {
              tok=w[i]
              for (j = 1; j <= n; j++) {
                if (tok ~ ("\\$" names[j] "([^A-Za-z0-9_]|$)") ||
                    tok ~ ("\\$\\{" names[j] "[^A-Za-z0-9_]")  ||
                    tok ~ ("\\$\\{" names[j] "\\}")) {
                  printf "%s:%d: %s   <-- \"%s\" reads $%s assigned in the SAME statement\n", \
                         F, NR, line, tok, names[j]
                }
              }
              if (tok ~ /^[A-Za-z_][A-Za-z0-9_]*=/) {
                eq=index(tok, "="); names[++n]=substr(tok, 1, eq - 1)
              }
            }
          }' "$f")"
        if [ -n "$found" ]; then
            hits=$(( hits + 1 ))
            printf '%s\n' "$found" | sed 's/^/      /'
        fi
    done < <(find "$FUNC_DIR" -name '*.sh' -type f | sort)
    fl_assert_zero "$hits" "files with a same-statement self-reference"
fl_check_end || true

# =============================================================================
# B — PURE HELPERS  (epoch geometry and the setup budget: no RPC, exact answers)
# =============================================================================
fl_phase "PURE HELPERS — epoch geometry and the setup budget"

fl_check_begin "epoch_geometry" 1
    # floor = len + STABILITY_MARGIN - 1 + SETUP_PUBLISH_MARGIN + 1 = len + 9
    fl_assert_eq "$(fl_setup_first_blocks_floor 100)" "109" "floor at epoch length 100"
    fl_assert_eq "$(fl_setup_first_blocks_floor 10)"  "19"  "floor at epoch length 10"
    fl_assert_eq "$(fl_setup_first_blocks_floor 4)"   "13"  "floor at epoch length 4"

    # epoch e is first buried at tip len*e + 5
    fl_assert_eq "$(fl_height_for_buried_epoch 1 100)" "105" "height burying epoch 1, len 100"
    fl_assert_eq "$(fl_height_for_buried_epoch 50 100)" "5005" "height burying epoch 50, len 100"
    fl_assert_eq "$(fl_buried_epoch_at 105 100)" "1" "buried epoch at tip 105, len 100"
    fl_assert_eq "$(fl_buried_epoch_at 104 100)" "0" "buried epoch at tip 104, len 100 (not yet)"
    fl_assert_eq "$(fl_buried_epoch_at 0 100)"   "0" "buried epoch at genesis"

    # The two are inverses. Checked rather than asserted once, because a sign slip in
    # either margin still satisfies a single hand-picked pair.
    bad=0
    for len in 4 10 100; do
        for e in 1 2 3 5 17; do
            h="$(fl_height_for_buried_epoch "$e" "$len")"
            back="$(fl_buried_epoch_at "$h" "$len")"
            [ "$back" = "$e" ] || { fl_bad "round trip broke: len=$len e=$e -> h=$h -> $back"; bad=1; }
        done
    done
    [ "$bad" = "0" ] && fl_ok "geometry round-trips for every (len, epoch) pair tried (15)"
fl_check_end || true

fl_check_begin "setup_budget_covers_the_bootstrap" 1
    # The stall fix. The budget must exceed the floor whenever the bootstrap plausibly
    # outruns it, and must never fall BELOW the floor (the node would raise it anyway,
    # silently invalidating the plan the test printed).
    b33="$(fl_setup_blocks_for_network 33 100)"
    b3="$(fl_setup_blocks_for_network 3 10)"
    fl_assert_eq "$b33" "325" "budget for 33 nodes at epoch length 100"
    fl_assert_eq "$b3"  "100" "budget for 3 nodes at epoch length 10"

    bad=0
    for nodes in 1 3 10 33 64; do
        for len in 4 10 100; do
            got="$(fl_setup_blocks_for_network "$nodes" "$len")"
            floor="$(fl_setup_first_blocks_floor "$len")"
            [ "$got" -ge "$floor" ] || { fl_bad "budget $got < floor $floor (nodes=$nodes len=$len)"; bad=1; }
        done
    done
    [ "$bad" = "0" ] && fl_ok "budget is at or above the floor for every size tried (15)"

    # Monotonic in the node count: more nodes take longer to bootstrap, so the budget
    # cannot shrink. A non-monotonic budget is how the large run stalls again.
    prev=0; mono=1
    for nodes in 1 3 10 33 64; do
        got="$(fl_setup_blocks_for_network "$nodes" 100)"
        [ "$got" -ge "$prev" ] || { fl_bad "budget not monotonic: $nodes nodes -> $got, after $prev"; mono=0; }
        prev="$got"
    done
    [ "$mono" = "1" ] && fl_ok "budget is non-decreasing in the node count (1 -> 64)"
fl_check_end || true

fl_check_begin "numeric_and_predicate_helpers" 1
    # [ -lt ] is integer-only; balances are decimal. These wrap awk for that reason.
    fl_lt 1 2            && fl_ok "fl_lt 1 2"            || fl_bad "fl_lt 1 2 should be true"
    fl_lt 0.5 1.5        && fl_ok "fl_lt 0.5 1.5"        || fl_bad "fl_lt 0.5 1.5 should be true"
    fl_lt 2 1            && fl_bad "fl_lt 2 1 should be false" || fl_ok "fl_lt 2 1 is false"
    fl_lt 1.0 1          && fl_bad "fl_lt 1.0 1 should be false" || fl_ok "fl_lt 1.0 1 is false"
    fl_is_zero 0         && fl_ok "fl_is_zero 0"         || fl_bad "fl_is_zero 0 should be true"
    fl_is_zero 0.00000000 && fl_ok "fl_is_zero 0.00000000" || fl_bad "fl_is_zero 0.00000000 should be true"
    fl_is_zero 0.1       && fl_bad "fl_is_zero 0.1 should be false" || fl_ok "fl_is_zero 0.1 is false"

    fl_is_txid "0000000000000000000000000000000000000000000000000000000000000001" \
        && fl_ok "fl_is_txid accepts 64 hex" || fl_bad "fl_is_txid rejected a valid txid"
    fl_is_txid "error: insufficient funds" \
        && fl_bad "fl_is_txid accepted an error message" || fl_ok "fl_is_txid rejects an error message"

    # mc_Permissions::IsBarredByDiversity: floor(miners*diversity - eps) + 1
    fl_assert_eq "$(fl_native_diversity_spacing 4 0.3)" "2" "diversity spacing, 4 miners at 0.3"
    fl_assert_eq "$(fl_native_diversity_spacing 4 0)"   "1" "diversity spacing, diversity 0 (inert)"
    fl_assert_eq "$(fl_native_diversity_spacing 4 1)"   "4" "diversity spacing, diversity 1 (clamped)"
fl_check_end || true

# =============================================================================
# C — RECORDERS, against stubbed RPCs
# =============================================================================
fl_phase "RECORDERS — exercised with stubbed RPCs, no network"

# The stub. Only the calls the recorders make are answered; anything else fails loudly
# so a recorder that grows a new RPC dependency is noticed here rather than in a run.
STUB_LISTBLOCKS='[]'
STUB_WEIGHTS='{}'
STUB_BALANCE='0'
STUB_TIP='0'

fl_cli() {
    local node=$1; shift
    case "${1:-}" in
        listblocks)     printf '%s\n' "$STUB_LISTBLOCKS" ;;
        getallweights)  printf '%s\n' "$STUB_WEIGHTS" ;;
        getbalance)     printf '%s\n' "$STUB_BALANCE" ;;
        getblockcount)  printf '%s\n' "$STUB_TIP" ;;
        *) echo "STUB: unexpected RPC on node $node: $*" >&2; return 1 ;;
    esac
}

NODES=3
declare -a FL_ROLE=(admin miner company)
FL_CHAIN="lintchain"

fl_check_begin "recorders_are_inert_without_an_output_root" 1
    # A suite run without WE_LARGE_OUTPUT must not die in the recorders. Every one of
    # them guards on FL_RUN_DIR, and that guard is load-bearing.
    FL_RUN_DIR=""
    rc=0
    fl_record_proposers 1 5      || rc=1
    fl_record_weights 1          || rc=1
    fl_record_epoch 1 5 1 0 0 0 0 || rc=1
    fl_record_gas 1              || rc=1
    fl_record_refuel 1 1 0 5 5 deadbeef || rc=1
    fl_record_meta lint '{}'     || rc=1
    fl_record_finish             || rc=1
    fl_assert_zero "$rc" "every recorder returns 0 with recording disabled"
fl_check_end || true

fl_check_begin "record_begin_writes_every_header" 1
    if fl_record_begin "lint-run" "$WORK/output" >/dev/null; then
        fl_ok "fl_record_begin created $FL_RUN_DIR"
    else
        fl_bad "fl_record_begin failed"
    fi
    for f in proposers.csv weights.csv epochs.csv gas.csv refuels.csv; do
        if [ -s "$FL_RUN_DIR/$f" ]; then fl_ok "header written: $f"
        else fl_bad "missing or empty: $f"; fi
    done
    fl_assert_eq "$(head -n1 "$FL_RUN_DIR/proposers.csv")" "height,miner" "proposers.csv header"
fl_check_end || true

fl_check_begin "record_proposers_does_not_crash_under_set_u" 1
    # THE REGRESSION CHECK for `local from=$1 to=$2 h=$from`. Run in a subshell with
    # `set -u` so an unbound read is fatal there and observable here, rather than
    # killing this script.
    STUB_LISTBLOCKS='[{"height":101,"miner":"addrA"},{"height":102,"miner":"addrB"}]'
    err="$( ( set -u; fl_record_proposers 101 102 ) 2>&1 )"; rc=$?
    fl_assert_zero "$rc" "fl_record_proposers exit status under set -u"
    if printf '%s' "$err" | grep -qi 'unbound variable'; then
        fl_bad "fl_record_proposers read an unbound variable: $err"
    else
        fl_ok "no unbound-variable read"
    fi
fl_check_end || true

fl_check_begin "record_proposers_takes_the_height_from_the_block" 1
    # Deliberately OUT OF ORDER. A counter seeded at $from would label these
    # 101,addrC / 102,addrA / 103,addrB -- every row wrong, and wrong in a way that
    # corrupts the proposer distribution silently instead of failing.
    : > "$FL_RUN_DIR/proposers.csv"
    echo "height,miner" > "$FL_RUN_DIR/proposers.csv"
    STUB_LISTBLOCKS='[{"height":103,"miner":"addrC"},{"height":101,"miner":"addrA"},{"height":102,"miner":"addrB"}]'
    fl_record_proposers 101 103
    rows="$(tail -n +2 "$FL_RUN_DIR/proposers.csv" | wc -l | tr -d ' ')"
    fl_assert_eq "$rows" "3" "rows written for a 3-block range"
    for pair in 101,addrA 102,addrB 103,addrC; do
        if grep -qx "$pair" "$FL_RUN_DIR/proposers.csv"; then fl_ok "row present: $pair"
        else fl_bad "row missing (height taken from a counter, not the block?): $pair"; fi
    done

    # Malformed and empty answers must be survivable: a recorder that dies on a
    # transient RPC hiccup throws away the whole run's evidence.
    for bad_json in '' 'not json' '{}' '[{"height":null,"miner":"x"}]' '[{"miner":"x"}]'; do
        STUB_LISTBLOCKS="$bad_json"
        if ( set -u; fl_record_proposers 1 2 ) >/dev/null 2>&1; then :; else
            fl_bad "fl_record_proposers failed on input: '$bad_json'"
        fi
    done
    fl_ok "survives empty, malformed and field-less answers"
fl_check_end || true

fl_check_begin "record_weights_stamps_the_epoch" 1
    : > "$FL_RUN_DIR/weights.csv"
    echo "epoch,address,weight" > "$FL_RUN_DIR/weights.csv"
    STUB_WEIGHTS='{"1AbCdEfGhIjKlMnOpQrStUvWxYz1234567":1500,"1ZyXwVuTsRqPoNmLkJiHgFeDcBa7654321":2500,"total":4000}'
    fl_record_weights 7
    got="$(tail -n +2 "$FL_RUN_DIR/weights.csv" | wc -l | tr -d ' ')"
    fl_assert_eq "$got" "2" "weight rows written (the 'total' key is not an address)"
    if grep -q '^7,1AbCdEfGhIjKlMnOpQrStUvWxYz1234567,1500$' "$FL_RUN_DIR/weights.csv"; then
        fl_ok "epoch-stamped row present with its weight"
    else
        fl_bad "expected '7,<addr>,1500'; got: $(tail -n +2 "$FL_RUN_DIR/weights.csv" | tr '\n' ' ')"
    fi
fl_check_end || true

fl_check_begin "record_gas_and_refuel_carry_the_role" 1
    : > "$FL_RUN_DIR/gas.csv"; echo "epoch,node,role,balance" > "$FL_RUN_DIR/gas.csv"
    STUB_BALANCE='1234.50000000'
    fl_record_gas 4
    got="$(tail -n +2 "$FL_RUN_DIR/gas.csv" | wc -l | tr -d ' ')"
    fl_assert_eq "$got" "3" "one gas row per node"
    if grep -q '^4,1,miner,1234.50000000$' "$FL_RUN_DIR/gas.csv"; then
        fl_ok "role resolved from FL_ROLE, decimal balance preserved"
    else
        fl_bad "expected '4,1,miner,1234.50000000'; got: $(tail -n +2 "$FL_RUN_DIR/gas.csv" | tr '\n' ' ')"
    fi

    fl_record_refuel 4 1 10 60 50 "abc123"
    if grep -q '^4,1,miner,10,60,50,abc123$' "$FL_RUN_DIR/refuels.csv"; then
        fl_ok "refuel row carries node, role, before, after, amount, txid"
    else
        fl_bad "refuel row wrong: $(tail -n1 "$FL_RUN_DIR/refuels.csv")"
    fi
fl_check_end || true

fl_check_begin "record_meta_and_finish_produce_valid_json" 1
    fl_record_meta "lint-run" '{"weight-epoch-length":100,"weight-lambda":0.2}'
    fl_record_finish
    if python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
missing = [k for k in ("experiment", "started", "finished", "chain", "nodes", "parameters") if k not in d]
if missing:
    print("missing keys: %s" % ", ".join(missing)); sys.exit(1)
if d["parameters"].get("weight-epoch-length") != 100:
    print("parameters not embedded as an object: %r" % (d["parameters"],)); sys.exit(1)
' "$FL_RUN_DIR/meta.json"; then
        fl_ok "meta.json parses and carries started, finished and the parameters object"
    else
        fl_bad "meta.json is not valid or is incomplete"
    fi
fl_check_end || true

fl_check_begin "the_analyser_reads_what_the_recorders_wrote" 1
    # End to end on the CSVs the stubs just produced: the point is that the two sides
    # agree on the format, not that a 3-block run is statistically meaningful. we_stats
    # exits 2 on insufficient data, which is a legitimate verdict here -- what must NOT
    # happen is a traceback, i.e. a column the analyser expects and nobody writes.
    out="$(python3 "$LIB_DIR/we_stats.py" "$FL_RUN_DIR" --draws 2000 2>&1)"; rc=$?
    if printf '%s' "$out" | grep -q 'Traceback'; then
        fl_bad "we_stats.py raised on the recorded layout:"
        printf '%s\n' "$out" | tail -n 20 | sed 's/^/      /'
    else
        fl_ok "we_stats.py consumed the recorded CSVs without raising (exit $rc)"
    fi
    case "$rc" in
        0|1|2) fl_ok "exit code is one of the documented 0/1/2 (got $rc)" ;;
        *)     fl_bad "undocumented exit code $rc" ;;
    esac
fl_check_end || true

fl_check_begin "documented_output_files_are_all_produced" 0
    # NON-CRITICAL: the derived tables need real data, and this run has three blocks.
    # What is worth surfacing is a file test/output/README.md promises and nothing writes.
    for f in report.md summary.txt meta.json proposers.csv weights.csv epochs.csv gas.csv refuels.csv; do
        [ -f "$FL_RUN_DIR/$f" ] && fl_ok "present: $f" || fl_bad "absent: $f"
    done
fl_check_end || true

fl_check_begin "output_readme_matches_the_files" 0
    # The README under test/output/ documents a file list. Drift there is how somebody
    # goes looking for a CSV that no longer exists.
    readme="$REPO_DIR/test/output/README.md"
    if [ ! -f "$readme" ]; then
        fl_bad "not found: $readme"
    else
        undocumented=0
        for f in proposers.csv weights.csv epochs.csv gas.csv refuels.csv report.md summary.txt meta.json; do
            grep -q "$f" "$readme" || { fl_bad "written by the harness but not in README.md: $f"; undocumented=1; }
        done
        [ "$undocumented" = "0" ] && fl_ok "every raw file the harness writes is documented"
    fi
fl_check_end || true

fl_check_summary || exit 1
