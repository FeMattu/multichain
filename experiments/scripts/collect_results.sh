#!/usr/bin/env bash
# Re-run log archiving and metric extraction over a finished run.
#
#   experiments/scripts/collect_results.sh --run-id <id>
#
# Idempotent, and it reads raw/ rather than consuming it, so a bug in an
# extractor can be fixed and this re-run without having destroyed its input.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
trap 'on_error $LINENO' ERR

RUN_ID=""
while [ $# -gt 0 ]; do
    case "$1" in
        --run-id) RUN_ID="$2"; shift 2 ;;
        -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
        *) die "$EXIT_CONFIG_ERROR" "unknown argument: $1" ;;
    esac
done
[ -n "$RUN_ID" ] || die "$EXIT_CONFIG_ERROR" "--run-id is required"

# Barrier before reading: multichaind keeps its data directory and debug.log
# open, and an extractor that reads them mid-flush sees a truncated tail and
# reports it as "no data". This waits on the processes themselves.
CHAIN="$(chain_of_run "$RUN_ID")"
[ -n "$CHAIN" ] && wait_for_daemons_to_exit "$CHAIN" 120 || true

cli metrics collect --run-id "$RUN_ID"
