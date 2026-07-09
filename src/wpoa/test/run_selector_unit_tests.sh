#!/usr/bin/env bash
#
# Build and run the wPoA Phase 2 proposer-selector unit tests.
#
# These tests exercise the pure Efraimidis–Spirakis scoring/argmin core
# (src/wpoa/wpoa_selector.h, class WPoASelector). They depend only on the
# HMAC-SHA256 / SHA256 crypto primitives and Boost.Test (header-only); they do
# NOT require the node to be built.
#
# Usage:  ./src/wpoa/test/run_selector_unit_tests.sh
set -euo pipefail

# Resolve the src/ directory (this script lives in src/wpoa/test/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"   # .../src
OUT="${TMPDIR:-/tmp}/wpoa_selector_tests"

CXX="${CXX:-g++}"

echo "Compiling wPoA selector unit tests..."
"$CXX" -std=c++11 -O2 -g \
    -I"$SRC_DIR" -I/usr/include \
    "$SCRIPT_DIR/wpoa_selector_tests.cpp" \
    "$SRC_DIR/crypto/hmac_sha256.cpp" \
    "$SRC_DIR/crypto/sha256.cpp" \
    -o "$OUT"

echo "Running..."
"$OUT" --log_level=test_suite
echo
echo "OK — all wPoA selector unit tests passed."
