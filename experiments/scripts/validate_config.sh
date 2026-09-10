#!/usr/bin/env bash
# Validate one descriptor, or every descriptor, without touching the system.
#
#   experiments/scripts/validate_config.sh
#   experiments/scripts/validate_config.sh --experiment <descriptor>
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
trap 'on_error $LINENO' ERR

EXPERIMENT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --experiment) EXPERIMENT="$2"; shift 2 ;;
        -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
        *) die "$EXIT_CONFIG_ERROR" "unknown argument: $1" ;;
    esac
done

FAILED=0
if [ -n "$EXPERIMENT" ]; then
    require_file "$EXPERIMENT" "experiment descriptor"
    cli validate --experiment "$EXPERIMENT" || FAILED=1
else
    for descriptor in "$EXPERIMENTS_DIR"/configs/experiments/*.yaml; do
        say "validating $(basename "$descriptor")"
        cli validate --experiment "$descriptor" >/dev/null || { warn "$descriptor is invalid"; FAILED=1; }
    done
    for topology in "$EXPERIMENTS_DIR"/configs/topologies/*.yaml; do
        cli topology validate --topology "$topology" >/dev/null \
            || { warn "$topology is invalid"; FAILED=1; }
    done
    say "checked $(ls "$EXPERIMENTS_DIR"/configs/experiments/*.yaml | wc -l) experiments and \
$(ls "$EXPERIMENTS_DIR"/configs/topologies/*.yaml | wc -l) topologies"
fi
[ "$FAILED" -eq 0 ] || die "$EXIT_CONFIG_ERROR" "at least one configuration is invalid"
say "configuration OK"
