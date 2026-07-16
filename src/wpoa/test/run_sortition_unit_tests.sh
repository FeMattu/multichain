#!/usr/bin/env bash
#
# Build and run the wPoA Phase 4 private-sortition unit tests.
#
# These tests exercise the pure private-sortition core (src/wpoa/private_sortition.h,
# class PrivateSortition) together with the real VRF (src/wpoa/vrf_wrapper.h) for the
# end-to-end probability-preservation check. They depend only on SHA256 / HMAC-SHA256,
# the VRF wrapper (secp256k1) and Boost.Test (header-only); they do NOT require the
# node to be built. The one prerequisite is that secp256k1 has already been built once
# (it is part of a normal `./autogen.sh && ./configure && make`, which produces
# src/secp256k1/.libs/libsecp256k1.a).
#
# Usage:  ./src/wpoa/test/run_sortition_unit_tests.sh
set -euo pipefail

# Resolve the src/ directory (this script lives in src/wpoa/test/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"   # .../src
OUT="${TMPDIR:-/tmp}/wpoa_sortition_tests"

SECP_LIB="$SRC_DIR/secp256k1/.libs/libsecp256k1.a"
if [ ! -f "$SECP_LIB" ]; then
    echo "error: $SECP_LIB not found — build secp256k1 first"       >&2
    echo "       (run ./autogen.sh && ./configure && make once)"    >&2
    exit 1
fi

CXX="${CXX:-g++}"

echo "Compiling wPoA private-sortition unit tests..."
"$CXX" -std=c++11 -O2 -g \
    -I"$SRC_DIR" -I"$SRC_DIR/secp256k1/include" -I/usr/include \
    "$SCRIPT_DIR/private_sortition_tests.cpp" \
    "$SRC_DIR/wpoa/vrf_wrapper.cpp" \
    "$SRC_DIR/crypto/hmac_sha256.cpp" \
    "$SRC_DIR/crypto/sha256.cpp" \
    "$SECP_LIB" \
    -o "$OUT"

echo "Running..."
"$OUT" --log_level=test_suite
echo
echo "OK — all wPoA private-sortition unit tests passed."
