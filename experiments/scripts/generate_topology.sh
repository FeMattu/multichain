#!/usr/bin/env bash
# Export a topology, and print its RTT matrix.
#
#   experiments/scripts/generate_topology.sh --topology <file> [--format gml|json|csv] [--output <file>]
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
trap 'on_error $LINENO' ERR

TOPOLOGY=""; FORMAT="gml"; OUTPUT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --topology) TOPOLOGY="$2"; shift 2 ;;
        --format)   FORMAT="$2"; shift 2 ;;
        --output)   OUTPUT="$2"; shift 2 ;;
        -h|--help)  sed -n '2,5p' "$0"; exit 0 ;;
        *) die "$EXIT_CONFIG_ERROR" "unknown argument: $1" ;;
    esac
done
[ -n "$TOPOLOGY" ] || die "$EXIT_CONFIG_ERROR" "--topology is required"
require_file "$TOPOLOGY" "topology"

cli topology validate --topology "$TOPOLOGY" --matrix
if [ -n "$OUTPUT" ]; then
    cli topology generate --topology "$TOPOLOGY" --format "$FORMAT" --output "$OUTPUT"
else
    cli topology generate --topology "$TOPOLOGY" --format "$FORMAT"
fi
