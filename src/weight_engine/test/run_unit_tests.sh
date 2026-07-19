#!/usr/bin/env bash
#
# Build and run ALL WeightEngine unit-test suites (Boost.Test), or a named subset.
#
# Each suite is a self-contained Boost.Test module compiled straight from source
# — no node build required — because the weight-calculation layer's pure helpers
# and math core depend only on json_spirit and the C++ standard library.
#
# The WeightEngine lives in its own folder (src/weight_engine), separate from the
# wPoA consensus (src/wpoa), so it ships its own runner mirroring
# src/wpoa/test/run_unit_tests.sh. Keeping it dedicated preserves the layer
# separation (this runner never links secp256k1, which the vrf/sortition wpoa
# suites need but these json_spirit-only suites do not).
#
# Usage:
#   ./run_unit_tests.sh                   # build + run every suite
#   ./run_unit_tests.sh records           # only the named suite(s)
#   ./run_unit_tests.sh --list            # list the available suites and exit
#   DRY_RUN=1 ./run_unit_tests.sh         # print what would run, build nothing
#
# Suites:  records  engine
#   records  — input-stream record parsers/aggregators (weight_records.h)     [W1]
#   engine   — weight-pipeline math core (weight_engine.h)                    [W2]
#              (skipped gracefully until the W2 source exists)
#
# Environment:
#   CXX        C++ compiler            (default: g++)
#   CXXFLAGS   compile flags           (default: -std=c++11 -O2 -g)
#   TMPDIR     where test binaries go  (default: /tmp)
#
# Exit code: 0 iff every selected suite built AND passed; non-zero otherwise.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"          # .../src
CXX="${CXX:-g++}"
CXXFLAGS="${CXXFLAGS:--std=c++11 -O2 -g}"
OUTDIR="${TMPDIR:-/tmp}"
DRY_RUN="${DRY_RUN:-0}"

ALL_SUITES="records engine"

usage() { sed -n '2,29p' "${BASH_SOURCE[0]}" | sed 's/^#\{0,1\} \{0,1\}//'; }

# Build and run a single suite. Echoes progress; returns 0 on pass.
build_and_run() {
    local key="$1"
    local src desc out
    local -a includes=(-I"$SRC_DIR" -I/usr/include)

    case "$key" in
        records)
            desc="input-stream record parsers (membership/esg/activity/reconciliation)"
            src="$SCRIPT_DIR/weight_records_tests.cpp" ;;
        engine)
            desc="weight-pipeline math core (contribution -> raw weight -> feedback -> w_k)"
            src="$SCRIPT_DIR/weight_engine_tests.cpp" ;;
        *)
            echo "  ERROR: unknown suite '$key' (valid: $ALL_SUITES)" >&2
            return 2 ;;
    esac

    if [ ! -f "$src" ]; then
        echo "  SKIP [$key]: $src not present yet" >&2
        return 0
    fi

    out="$OUTDIR/weight_${key}_tests"

    local -a flags
    read -r -a flags <<< "$CXXFLAGS"

    if [ "$DRY_RUN" = "1" ]; then
        echo "── [$key] $desc"
        echo "     would compile: $CXX ${flags[*]} ${includes[*]} $src -o $out"
        return 0
    fi

    echo "──────────────────────────────────────────────────────────────────"
    echo "── [$key] compiling: $desc"
    if ! "$CXX" "${flags[@]}" "${includes[@]}" "$src" -o "$out"; then
        echo "  COMPILE FAILED: $key" >&2
        return 1
    fi
    echo "── [$key] running"
    if ! "$out" --log_level=test_suite; then
        echo "  TESTS FAILED: $key" >&2
        return 1
    fi
    echo "── [$key] OK"
    return 0
}

# ---- parse arguments --------------------------------------------------------
SELECTED=""
for arg in "$@"; do
    case "$arg" in
        -h|--help)  usage; exit 0 ;;
        --list)     echo "Available unit-test suites: $ALL_SUITES"; exit 0 ;;
        -*)         echo "unknown option: $arg" >&2; usage; exit 2 ;;
        *)
            if [[ " $ALL_SUITES " != *" $arg "* ]]; then
                echo "unknown suite: $arg (valid: $ALL_SUITES)" >&2
                exit 2
            fi
            SELECTED="$SELECTED $arg" ;;
    esac
done
[ -n "$SELECTED" ] || SELECTED="$ALL_SUITES"

# ---- run --------------------------------------------------------------------
echo "== WeightEngine unit tests =="
echo "  suites:$SELECTED"
echo "  CXX=$CXX  CXXFLAGS=$CXXFLAGS"

declare -a PASSED=() FAILED=()
for s in $SELECTED; do
    if build_and_run "$s"; then PASSED+=("$s"); else FAILED+=("$s"); fi
done

echo "──────────────────────────────────────────────────────────────────"
echo "== unit-test summary =="
[ "${#PASSED[@]}" -gt 0 ] && echo "  PASSED: ${PASSED[*]}"
if [ "${#FAILED[@]}" -gt 0 ]; then
    echo "  FAILED: ${FAILED[*]}"
    echo "UNIT TESTS FAILED."
    exit 1
fi
echo "OK — all selected WeightEngine unit tests passed."
exit 0
