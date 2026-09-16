#!/usr/bin/env bash
#
# run_experiment.sh -- convenience wrapper around experimental_test.py.
#
# Requires a built node (./autogen.sh && ./configure && make). Runs EXACTLY the
# mode you pass; it never runs both. Output lands in experimental/output/.
#
# Usage:
#   ./run_experiment.sh --mode=wpoa
#   ./run_experiment.sh --mode=native
#   WE_EPOCHS=6 WE_EPOCH_LENGTH=4 ./run_experiment.sh --mode=wpoa   # smaller/faster
#
# All tunables are WE_* environment variables (see config.py).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/experimental_test.py" "$@"
