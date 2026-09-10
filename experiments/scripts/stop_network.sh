#!/usr/bin/env bash
# Tear the emulated fabric down. Results are never touched.
#
#   sudo -E experiments/scripts/stop_network.sh --run-id <id>
#   sudo -E experiments/scripts/stop_network.sh --prefix poesia   # no run id needed
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
trap 'on_error $LINENO' ERR

RUN_ID=""; PREFIX="poesia"
while [ $# -gt 0 ]; do
    case "$1" in
        --run-id) RUN_ID="$2"; shift 2 ;;
        --prefix) PREFIX="$2"; shift 2 ;;
        -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
        *) die "$EXIT_CONFIG_ERROR" "unknown argument: $1" ;;
    esac
done

if [ -n "$RUN_ID" ]; then
    cli network stop --run-id "$RUN_ID"
else
    # Works from a fresh shell after a crash: the session is found on the
    # system by its namespace prefix, not from any remembered state.
    cli results clean --prefix "$PREFIX"
fi
say "the fabric is down; results were not touched"
