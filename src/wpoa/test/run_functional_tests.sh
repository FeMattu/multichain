#!/usr/bin/env bash
#
# Entrypoint for the wPoA functional (end-to-end) tests.
#
# The functional suite is now a SINGLE orchestrated system-level run
# (functional_test_wpoa_system.sh): it starts ONE multi-node network, waits for
# weight convergence and a block warm-up ONCE, and then verifies every feature
# (weight, multi-node consistency, VRF, RANDAO, sortition, distribution) against
# that shared run. This script is the thin, robust wrapper around it — it adds a
# hard timeout safety-net and the QUICK profile, and normalises the exit code.
#
# It is NOT a sequencer of per-feature bootstraps: the old multinode/vrf/randao/
# sortition drivers (which each recreated a network) have been folded into the
# system test's check_* functions.
#
# Usage:
#   ./run_functional_tests.sh                       # the system run (full sample)
#   QUICK=1 ./run_functional_tests.sh               # smaller sample / shorter budgets
#   INCLUDE_PUBLIC_SELECTOR=1 ./run_functional_tests.sh   # + the sortition-off regime
#   FUNCTIONAL_TIMEOUT=2400 ./run_functional_tests.sh
#   DRY_RUN=1 ./run_functional_tests.sh             # print the plan, launch nothing
#
# Environment:
#   QUICK=1                 reduced sample sizes / budgets for a fast pass
#   INCLUDE_PUBLIC_SELECTOR run the extra sortition-off scenario (default off)
#   FUNCTIONAL_TIMEOUT      hard timeout in seconds for the whole run (default 1800; 0 = none)
#   NO_WARN=1               suppress the warning banner (for CI)
#   DRY_RUN=1               print the plan without launching anything
#   BINDIR, NODES, WEIGHTS, SETUP_BLOCKS, KEEP_LOGS, ... pass through to the run.
#
# Exit code: 0 iff the system run passed; non-zero if it failed or timed out.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEM_TEST="$SCRIPT_DIR/functional_test_wpoa_system.sh"

FUNCTIONAL_TIMEOUT="${FUNCTIONAL_TIMEOUT:-1800}"
QUICK="${QUICK:-0}"
DRY_RUN="${DRY_RUN:-0}"

usage() { sed -n '2,32p' "${BASH_SOURCE[0]}" | sed 's/^#\{0,1\} \{0,1\}//'; }

for arg in "$@"; do
    case "$arg" in
        -h|--help) usage; exit 0 ;;
        *)         echo "unexpected argument: $arg" >&2; usage; exit 2 ;;
    esac
done

[ -x "$SYSTEM_TEST" ] || { echo "ERROR: not executable: $SYSTEM_TEST" >&2; exit 2; }

# The system test owns the warning banner and the QUICK profile; we only add the
# outer hard timeout. QUICK/INCLUDE_PUBLIC_SELECTOR/NO_WARN/BINDIR/... are env
# and inherited automatically.
declare -a cmd=("$SYSTEM_TEST")
if [ "$FUNCTIONAL_TIMEOUT" -gt 0 ] && command -v timeout >/dev/null 2>&1; then
    cmd=(timeout --kill-after=30s "${FUNCTIONAL_TIMEOUT}s" "$SYSTEM_TEST")
fi

echo "== wPoA functional tests (single orchestrated system run) =="
echo "   test: $SYSTEM_TEST"
echo "   QUICK=$QUICK   INCLUDE_PUBLIC_SELECTOR=${INCLUDE_PUBLIC_SELECTOR:-0}   hard-timeout=${FUNCTIONAL_TIMEOUT}s"
if [ "$DRY_RUN" = "1" ]; then
    echo "   [dry-run] ${cmd[*]}"
    exit 0
fi

"${cmd[@]}"
rc=$?
if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
    echo "  TIMEOUT: the functional run exceeded ${FUNCTIONAL_TIMEOUT}s — likely a probabilistic stall; re-running usually succeeds." >&2
    exit 124
fi
exit "$rc"
