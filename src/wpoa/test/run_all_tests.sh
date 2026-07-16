#!/usr/bin/env bash
#
# Run the ENTIRE wPoA test suite: unit tests first, then functional tests.
#
# This is the single entrypoint that validates the whole system end to end:
#   Phase 1  ── unit tests      (fast, node-free) via run_unit_tests.sh
#   Phase 2  ── functional tests (slow, real multi-node) via run_functional_tests.sh
#
# Unit tests run first because they are fast and node-free: if the pure logic is
# broken there is no point spending many minutes on the multi-node drivers. By
# default a unit-test failure therefore SKIPS the functional phase (set
# CONTINUE_ON_UNIT_FAIL=1 to run functional tests anyway).
#
#   ⚠  The functional phase can take a LONG time and, being a live distributed
#      system, may occasionally stall — see run_functional_tests.sh for details.
#      Use QUICK=1 for a faster (reduced-sample) end-to-end validation.
#
# Usage:
#   ./run_all_tests.sh                 # unit + functional (full)
#   QUICK=1 ./run_all_tests.sh         # unit + functional (fast smoke)
#   DRY_RUN=1 ./run_all_tests.sh       # print the plan, run nothing
#
# Environment (all passed through to the sub-runners):
#   QUICK, FUNCTIONAL_TIMEOUT, NO_WARN, DRY_RUN, BINDIR, NODES, WEIGHTS, ...
#   CONTINUE_ON_UNIT_FAIL=1   run the functional phase even if unit tests fail.
#
# Exit code: 0 iff BOTH phases pass; non-zero if any sub-phase fails.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTINUE_ON_UNIT_FAIL="${CONTINUE_ON_UNIT_FAIL:-0}"

unit_rc=0
func_rc=0

echo "##################################################################"
echo "#  wPoA — FULL TEST RUN (unit + functional)                      #"
echo "##################################################################"

# ---- Phase 1: unit tests ----------------------------------------------------
echo
echo ">>> PHASE 1/2 — unit tests"
"$SCRIPT_DIR/run_unit_tests.sh"
unit_rc=$?
if [ "$unit_rc" -ne 0 ]; then
    echo ">>> unit tests FAILED (exit $unit_rc)"
    if [ "$CONTINUE_ON_UNIT_FAIL" != "1" ]; then
        echo ">>> skipping the functional phase (set CONTINUE_ON_UNIT_FAIL=1 to run it anyway)."
        echo
        echo "########################  RESULT: FAIL  ##########################"
        exit "$unit_rc"
    fi
    echo ">>> CONTINUE_ON_UNIT_FAIL=1 — proceeding to the functional phase anyway."
fi

# ---- Phase 2: functional tests ----------------------------------------------
echo
echo ">>> PHASE 2/2 — functional tests"
"$SCRIPT_DIR/run_functional_tests.sh"
func_rc=$?
[ "$func_rc" -ne 0 ] && echo ">>> functional tests FAILED (exit $func_rc)"

# ---- verdict ----------------------------------------------------------------
echo
echo "##################################################################"
echo "#  FULL TEST RUN SUMMARY                                         #"
echo "#    unit tests:       $([ "$unit_rc" -eq 0 ] && echo PASS || echo FAIL)"
echo "#    functional tests: $([ "$func_rc" -eq 0 ] && echo PASS || echo FAIL)"
echo "##################################################################"

if [ "$unit_rc" -ne 0 ] || [ "$func_rc" -ne 0 ]; then
    exit 1
fi
echo "OK — full wPoA test run passed (unit + functional)."
exit 0
