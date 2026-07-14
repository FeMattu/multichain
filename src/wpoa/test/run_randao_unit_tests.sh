#!/usr/bin/env bash
#
# Build and run the wPoA Phase 3b RANDAO accumulator unit tests.
#
# These tests exercise the pure accumulator/seed core (src/wpoa/randao_accumulator.h,
# class RandaoAccumulator). They depend only on SHA256 and Boost.Test
# (header-only); they do NOT require the node to be built.
#
# Usage:  ./src/wpoa/test/run_randao_unit_tests.sh
set -euo pipefail

# Resolve the src/ directory (this script lives in src/wpoa/test/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"   # .../src
OUT="${TMPDIR:-/tmp}/wpoa_randao_tests"

CXX="${CXX:-g++}"

echo "Compiling wPoA RANDAO accumulator unit tests..."
"$CXX" -std=c++11 -O2 -g \
    -I"$SRC_DIR" -I/usr/include \
    "$SCRIPT_DIR/randao_accumulator_tests.cpp" \
    "$SRC_DIR/crypto/sha256.cpp" \
    -o "$OUT"

echo "Running..."
"$OUT" --log_level=test_suite
echo
echo "OK — all wPoA RANDAO accumulator unit tests passed."
