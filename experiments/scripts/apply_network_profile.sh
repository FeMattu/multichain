#!/usr/bin/env bash
# Change network conditions on a live fabric, mid-run.
#
#   sudo -E experiments/scripts/apply_network_profile.sh --run-id <id> \
#       --profile experiments/configs/network-profiles/degraded.yaml
#   sudo -E experiments/scripts/apply_network_profile.sh --run-id <id> \
#       --profile .../partitioned.yaml --link milano-c--frankfurt
#   sudo -E experiments/scripts/apply_network_profile.sh --run-id <id> --restore
#
# Every change is timestamped into <run>/runtime/netem-events.jsonl with both
# clocks, so the analysis can align a change in behaviour with the change in
# conditions that caused it.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
trap 'on_error $LINENO' ERR

RUN_ID=""; PROFILE=""; RESTORE=0; LINKS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --run-id) RUN_ID="$2"; shift 2 ;;
        --profile) PROFILE="$2"; shift 2 ;;
        --link) LINKS+=(--link "$2"); shift 2 ;;
        --restore) RESTORE=1; shift ;;
        -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
        *) die "$EXIT_CONFIG_ERROR" "unknown argument: $1" ;;
    esac
done
[ -n "$RUN_ID" ] || die "$EXIT_CONFIG_ERROR" "--run-id is required"

if [ "$RESTORE" -eq 1 ]; then
    cli network apply-profile --run-id "$RUN_ID" --restore "${LINKS[@]+"${LINKS[@]}"}"
else
    [ -n "$PROFILE" ] || die "$EXIT_CONFIG_ERROR" "--profile or --restore is required"
    require_file "$PROFILE" "network profile"
    cli network apply-profile --run-id "$RUN_ID" --profile "$PROFILE" "${LINKS[@]+"${LINKS[@]}"}"
fi
