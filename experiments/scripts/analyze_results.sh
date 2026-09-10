#!/usr/bin/env bash
# Analyse a run and write its reports and plots.
#
#   experiments/scripts/analyze_results.sh --run-id <id>
#   experiments/scripts/analyze_results.sh --run-id a --run-id b --campaign
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
trap 'on_error $LINENO' ERR

RUN_IDS=(); CAMPAIGN=0; NO_PLOTS=0
while [ $# -gt 0 ]; do
    case "$1" in
        --run-id) RUN_IDS+=("$2"); shift 2 ;;
        --campaign) CAMPAIGN=1; shift ;;
        --no-plots) NO_PLOTS=1; shift ;;
        -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
        *) die "$EXIT_CONFIG_ERROR" "unknown argument: $1" ;;
    esac
done
[ "${#RUN_IDS[@]}" -gt 0 ] || die "$EXIT_CONFIG_ERROR" "at least one --run-id is required"

for run_id in "${RUN_IDS[@]}"; do
    say "analysing $run_id"
    cli analysis run --run-id "$run_id" >/dev/null \
        || die "$EXIT_ANALYSIS_FAILED" "the analysis of $run_id failed"
    if [ "$NO_PLOTS" -eq 1 ]; then
        cli report generate --run-id "$run_id" --no-plots >/dev/null
    else
        cli report generate --run-id "$run_id" >/dev/null
    fi
    say "  reports in \$(results root)/$run_id/reports/"
done

if [ "$CAMPAIGN" -eq 1 ]; then
    say "building the campaign view"
    ARGS=(analysis campaign)
    for run_id in "${RUN_IDS[@]}"; do ARGS+=(--run-id "$run_id"); done
    cli "${ARGS[@]}" || die "$EXIT_ANALYSIS_FAILED" "the campaign view failed"
fi
say "done"
