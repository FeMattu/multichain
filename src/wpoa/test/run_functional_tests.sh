#!/usr/bin/env bash
#
# Orchestrate the wPoA functional (end-to-end) test suite.
#
# Runs the multi-node functional drivers in dependency order, each wrapped in a
# hard timeout, and reports a single aggregate pass/fail. Every driver bootstraps
# a REAL permissioned MultiChain network of several nodes, so the node must be
# built first (a normal ./autogen.sh && ./configure && make).
#
# ┌──────────────────────────────────────────────────────────────────────────┐
# │  ⚠  WARNING — READ BEFORE RUNNING  ⚠                                       │
# │                                                                            │
# │  • Functional tests can take a LONG time. They spin up multi-node networks │
# │    and mine hundreds of blocks; a full run is on the order of many minutes.│
# │  • Because they exercise a live distributed/blockchain system, a run may   │
# │    occasionally STALL or fail to terminate on its own (e.g. slow weight    │
# │    convergence, a transient simultaneous-qualifier fork, a node that does  │
# │    not join). The probability is LOW, but it is real and inherent to the   │
# │    system under test — not a bug in these scripts.                         │
# │  • As a safety net every driver is wrapped in a hard timeout               │
# │    (FUNCTIONAL_TIMEOUT, default 1800s). A driver that trips it is reported  │
# │    as a TIMEOUT; re-running usually succeeds.                               │
# └──────────────────────────────────────────────────────────────────────────┘
#
# Suites (run in this order; each layers on the previous):
#   multinode   weight aggregation + weighted proposer distribution (chi-square)
#   vrf         VRF randomness-beacon liveness, network-wide verification, no fork
#   randao      RANDAO beacon-seed liveness, no fork, weight-proportional dist.
#   sortition   FULL STACK: private (VRF-scored) sortition, no public argmin,
#               liveness, no persistent fork, weight-proportional distribution
#
# Usage:
#   ./run_functional_tests.sh                     # run every suite (full defaults)
#   ./run_functional_tests.sh vrf sortition       # only the named suite(s)
#   QUICK=1 ./run_functional_tests.sh             # smaller samples / shorter budgets
#   FUNCTIONAL_TIMEOUT=2400 ./run_functional_tests.sh
#   DRY_RUN=1 ./run_functional_tests.sh           # print what would run, launch nothing
#   ./run_functional_tests.sh --list              # list suites and exit
#
# Environment:
#   QUICK=1              use reduced sample sizes / timeouts for a fast smoke pass
#   FUNCTIONAL_TIMEOUT   per-suite hard timeout in seconds (default 1800; 0 = none)
#   NO_WARN=1            suppress the warning banner (for CI)
#   DRY_RUN=1            do not launch anything, just print the plan
#   BINDIR, NODES, WEIGHTS, KEEP_LOGS, ... are passed through to each driver.
#   Per-suite knobs (DIST_BLOCKS, VRF_BLOCKS, RANDAO_BLOCKS, SORT_BLOCKS, ...)
#   set in the environment are respected; QUICK only fills in ones left unset.
#
# Exit code: 0 iff every selected suite passed; non-zero if any failed/timed out.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FUNCTIONAL_TIMEOUT="${FUNCTIONAL_TIMEOUT:-1800}"
QUICK="${QUICK:-0}"
DRY_RUN="${DRY_RUN:-0}"
NO_WARN="${NO_WARN:-0}"

ALL_SUITES="multinode vrf randao sortition"

# suite -> driver script
script_for() {
    case "$1" in
        multinode) echo "$SCRIPT_DIR/functional_test_wpoa_multinode.sh" ;;
        vrf)       echo "$SCRIPT_DIR/functional_test_wpoa_vrf.sh" ;;
        randao)    echo "$SCRIPT_DIR/functional_test_wpoa_randao.sh" ;;
        sortition) echo "$SCRIPT_DIR/functional_test_wpoa_sortition.sh" ;;
        *)         return 1 ;;
    esac
}

# In QUICK mode, fill in smaller sample sizes / timeouts for a suite — but only
# for variables the caller did NOT already set (so explicit overrides win).
apply_quick_env() {
    [ "$QUICK" = "1" ] || return 0
    case "$1" in
        multinode) export DIST_BLOCKS="${DIST_BLOCKS:-120}"  DIST_TIMEOUT="${DIST_TIMEOUT:-300}" ;;
        vrf)       export VRF_BLOCKS="${VRF_BLOCKS:-25}"     VRF_TIMEOUT="${VRF_TIMEOUT:-180}" ;;
        randao)    export RANDAO_BLOCKS="${RANDAO_BLOCKS:-30}" RANDAO_TIMEOUT="${RANDAO_TIMEOUT:-200}" ;;
        sortition) export SORT_BLOCKS="${SORT_BLOCKS:-30}"   SORT_TIMEOUT="${SORT_TIMEOUT:-250}" ;;
    esac
}

usage() { sed -n '2,50p' "${BASH_SOURCE[0]}" | sed 's/^#\{0,1\} \{0,1\}//'; }

print_warning() {
    [ "$NO_WARN" = "1" ] && return 0
    cat >&2 <<EOF

============================================================================
  ⚠  wPoA FUNCTIONAL TESTS — please read
============================================================================
  * These tests drive REAL multi-node MultiChain networks and mine many
    blocks. A full run can take a LONG time (many minutes).
  * They exercise a live distributed/blockchain system, so a run may
    occasionally STALL or not terminate on its own (slow convergence, a
    transient simultaneous-qualifier fork, a node failing to join). The
    probability is LOW but real — it is a property of the system under
    test, not a defect in these scripts.
  * Safety net: each suite is wrapped in a hard timeout of
    ${FUNCTIONAL_TIMEOUT}s (FUNCTIONAL_TIMEOUT; 0 disables). A suite that
    trips it is reported as TIMEOUT — re-running usually succeeds.
  * For a faster smoke pass use QUICK=1 (smaller samples, shorter budgets).
============================================================================

EOF
    if [ -t 1 ] && [ "${FUNCTIONAL_YES:-0}" != "1" ] && [ "$DRY_RUN" != "1" ]; then
        echo "  Starting in 3s — press Ctrl-C to abort." >&2
        sleep 3
    fi
}

# Run one suite; returns its exit status (124 => timed out).
run_suite() {
    local key="$1" script
    script="$(script_for "$key")" || { echo "  ERROR: unknown suite '$key'" >&2; return 2; }
    [ -x "$script" ] || { echo "  ERROR: driver not executable: $script" >&2; return 2; }

    apply_quick_env "$key"

    local -a cmd=("$script")
    if [ "$FUNCTIONAL_TIMEOUT" -gt 0 ] && command -v timeout >/dev/null 2>&1; then
        cmd=(timeout --kill-after=30s "${FUNCTIONAL_TIMEOUT}s" "$script")
    fi

    echo "──────────────────────────────────────────────────────────────────"
    echo "== functional suite: $key =="
    echo "   driver: $script"
    [ "$QUICK" = "1" ] && echo "   profile: QUICK"
    if [ "$DRY_RUN" = "1" ]; then
        echo "   [dry-run] ${cmd[*]}"
        return 0
    fi

    "${cmd[@]}"
    local rc=$?
    if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
        echo "  TIMEOUT [$key]: exceeded ${FUNCTIONAL_TIMEOUT}s — likely a probabilistic stall; re-running usually succeeds." >&2
        return 124
    fi
    return "$rc"
}

# ---- parse arguments --------------------------------------------------------
SELECTED=""
for arg in "$@"; do
    case "$arg" in
        -h|--help) usage; exit 0 ;;
        --list)    echo "Available functional suites: $ALL_SUITES"; exit 0 ;;
        -*)        echo "unknown option: $arg" >&2; usage; exit 2 ;;
        *)
            if [[ " $ALL_SUITES " != *" $arg "* ]]; then
                echo "unknown suite: $arg (valid: $ALL_SUITES)" >&2
                exit 2
            fi
            SELECTED="$SELECTED $arg" ;;
    esac
done
[ -n "$SELECTED" ] || SELECTED="$ALL_SUITES"

print_warning

echo "== wPoA functional tests =="
echo "  suites:$SELECTED"
echo "  per-suite hard timeout: ${FUNCTIONAL_TIMEOUT}s   QUICK=$QUICK   DRY_RUN=$DRY_RUN"

declare -a PASSED=() FAILED=()
for s in $SELECTED; do
    if run_suite "$s"; then PASSED+=("$s"); else FAILED+=("$s"); fi
done

echo "──────────────────────────────────────────────────────────────────"
echo "== functional-test summary =="
[ "${#PASSED[@]}" -gt 0 ] && echo "  PASSED: ${PASSED[*]}"
if [ "${#FAILED[@]}" -gt 0 ]; then
    echo "  FAILED: ${FAILED[*]}"
    echo "FUNCTIONAL TESTS FAILED."
    exit 1
fi
echo "OK — all selected wPoA functional tests passed."
exit 0
