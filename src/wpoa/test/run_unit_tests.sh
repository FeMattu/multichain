#!/usr/bin/env bash
#
# Build and run the wPoA weight-registry unit tests.
#
# These tests exercise the pure record parsing / aggregation logic
# (src/wpoa/weight_record.h) and depend only on json_spirit headers and
# Boost.Test (header-only). They do NOT require the node to be built.
#
# Usage:  ./src/wpoa/test/run_unit_tests.sh
#
set -euo pipefail

# Resolve the src/ directory (this script lives in src/wpoa/test/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"   # .../src
OUT="${TMPDIR:-/tmp}/wpoa_weight_tests"

CXX="${CXX:-g++}"

echo "Compiling wPoA unit tests..."
"$CXX" -std=c++11 -O0 -g \
    -I"$SRC_DIR" -I/usr/include \
    "$SCRIPT_DIR/wpoa_weight_tests.cpp" \
    -o "$OUT"

echo "Running..."
"$OUT" --log_level=test_suite
echo
echo "OK — all wPoA unit tests passed."
