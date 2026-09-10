#!/usr/bin/env bash
# Seal params.dat and lay out the per-node data directories for an existing run.
#
#   experiments/scripts/initialize_multichain.sh --run-id <id>
#
# Normally run_experiment.sh does this. Use it directly when re-sealing a chain
# after editing config/chain-params.dat inside a run directory.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
trap 'on_error $LINENO' ERR

RUN_ID=""
while [ $# -gt 0 ]; do
    case "$1" in
        --run-id) RUN_ID="$2"; shift 2 ;;
        -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
        *) die "$EXIT_CONFIG_ERROR" "unknown argument: $1" ;;
    esac
done
[ -n "$RUN_ID" ] || die "$EXIT_CONFIG_ERROR" "--run-id is required"
cli multichain initialize --run-id "$RUN_ID"
