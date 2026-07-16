#!/usr/bin/env bash
#
# Build and run ALL wPoA unit-test suites (Boost.Test), or a named subset.
#
# Each suite is a self-contained Boost.Test module compiled straight from source
# — no node build required. The VRF and private-sortition suites additionally
# link secp256k1, which a normal `./autogen.sh && ./configure && make` builds
# once as src/secp256k1/.libs/libsecp256k1.a.
#
# This single runner replaces the former per-suite launchers
# (run_selector_unit_tests.sh, run_vrf_unit_tests.sh, run_randao_unit_tests.sh,
# run_sortition_unit_tests.sh): pass a suite name to run just one.
#
# Usage:
#   ./run_unit_tests.sh                   # build + run every suite
#   ./run_unit_tests.sh selector vrf      # only the named suite(s)
#   ./run_unit_tests.sh --list            # list the available suites and exit
#   DRY_RUN=1 ./run_unit_tests.sh         # print what would run, build nothing
#
# Suites:  weight  selector  vrf  randao  sortition
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
SECP_LIB="$SRC_DIR/secp256k1/.libs/libsecp256k1.a"
OUTDIR="${TMPDIR:-/tmp}"
DRY_RUN="${DRY_RUN:-0}"

ALL_SUITES="weight selector vrf randao sortition"

usage() { sed -n '2,31p' "${BASH_SOURCE[0]}" | sed 's/^#\{0,1\} \{0,1\}//'; }

# Build and run a single suite. Echoes progress; returns 0 on pass.
build_and_run() {
    local key="$1"
    local src desc out needs_secp=0
    local -a extra=() includes=(-I"$SRC_DIR" -I/usr/include) link=()

    case "$key" in
        weight)
            desc="weight registry (weight_record.h parsing + newest-wins aggregation)"
            src="$SCRIPT_DIR/wpoa_weight_tests.cpp" ;;
        selector)
            desc="proposer selector (Efraimidis-Spirakis weighted argmin)"
            src="$SCRIPT_DIR/wpoa_selector_tests.cpp"
            extra=("$SRC_DIR/crypto/hmac_sha256.cpp" "$SRC_DIR/crypto/sha256.cpp") ;;
        vrf)
            desc="VRF wrapper (ECVRF / DLEQ prove+verify)"
            src="$SCRIPT_DIR/vrf_wrapper_tests.cpp"
            extra=("$SRC_DIR/wpoa/vrf_wrapper.cpp" "$SRC_DIR/crypto/sha256.cpp")
            needs_secp=1 ;;
        randao)
            desc="RANDAO accumulator / beacon-seed derivation"
            src="$SCRIPT_DIR/randao_accumulator_tests.cpp"
            extra=("$SRC_DIR/crypto/sha256.cpp") ;;
        sortition)
            desc="private sortition (VRF-scored selection + probability preservation)"
            src="$SCRIPT_DIR/private_sortition_tests.cpp"
            extra=("$SRC_DIR/wpoa/vrf_wrapper.cpp" "$SRC_DIR/crypto/hmac_sha256.cpp" "$SRC_DIR/crypto/sha256.cpp")
            needs_secp=1 ;;
        *)
            echo "  ERROR: unknown suite '$key' (valid: $ALL_SUITES)" >&2
            return 2 ;;
    esac

    out="$OUTDIR/wpoa_${key}_tests"
    if [ "$needs_secp" = "1" ]; then
        includes+=(-I"$SRC_DIR/secp256k1/include")
        if [ ! -f "$SECP_LIB" ]; then
            echo "  ERROR [$key]: $SECP_LIB not found — build secp256k1 first" >&2
            echo "               (run ./autogen.sh && ./configure && make once)"  >&2
            return 1
        fi
        link=("$SECP_LIB")
    fi

    local -a flags
    read -r -a flags <<< "$CXXFLAGS"

    if [ "$DRY_RUN" = "1" ]; then
        echo "── [$key] $desc"
        echo "     would compile: $CXX ${flags[*]} ${includes[*]} $src ${extra[*]:-} ${link[*]:-} -o $out"
        return 0
    fi

    echo "──────────────────────────────────────────────────────────────────"
    echo "── [$key] compiling: $desc"
    if ! "$CXX" "${flags[@]}" "${includes[@]}" "$src" "${extra[@]}" "${link[@]}" -o "$out"; then
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
echo "== wPoA unit tests =="
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
echo "OK — all selected wPoA unit tests passed."
exit 0
