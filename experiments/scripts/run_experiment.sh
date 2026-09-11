#!/usr/bin/env bash
# Run one experiment end to end: build, bootstrap, measure, collect, analyse.
#
#   sudo -E experiments/scripts/run_experiment.sh \
#       --experiment experiments/configs/experiments/regional.yaml
#
#   sudo -E experiments/scripts/run_experiment.sh \
#       --experiment .../intercontinental.yaml --seed 12345 --duration 3600
#
#   experiments/scripts/run_experiment.sh --experiment ... --dry-run
#
# With `fabric.backend: auto` and no CORE on the machine, the run stops at
# exit code 2 rather than choosing the netns fabric for you. Authorise it:
#
#   sudo -E experiments/scripts/run_experiment.sh \
#       --experiment ... --allow-fallback-without-core
#
# Needs root or passwordless sudo, and the MultiChain binaries. Without them it
# stops at exit code 2 before creating anything. `-E` on sudo matters: it keeps
# MULTICHAIN_BIN, EXPERIMENT_ROOT and PYTHON.
#
# Ctrl+C is safe at any point: the harness stops the roles, stops the daemons
# over RPC so their databases flush, clears the impairment, destroys the fabric
# and writes a manifest saying it was interrupted. It never deletes results.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
trap 'on_error $LINENO' ERR

EXPERIMENT=""; RUN_ID=""; SEED=""; DURATION=""; BACKEND=""
DRY_RUN=0; SKIP_ANALYSIS=0; FORCE=0; SAMPLE_INTERVAL=""
ALLOW_FALLBACK=0; ASSUME_YES=0
while [ $# -gt 0 ]; do
    case "$1" in
        --experiment) EXPERIMENT="$2"; shift 2 ;;
        --run-id) RUN_ID="$2"; shift 2 ;;
        --seed) SEED="$2"; shift 2 ;;
        --duration) DURATION="$2"; shift 2 ;;
        --backend) BACKEND="$2"; shift 2 ;;
        --sample-interval) SAMPLE_INTERVAL="$2"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --no-analysis) SKIP_ANALYSIS=1; shift ;;
        --force) FORCE=1; shift ;;
        --allow-fallback-without-core) ALLOW_FALLBACK=1; shift ;;
        --yes) ASSUME_YES=1; shift ;;
        -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
        *) die "$EXIT_CONFIG_ERROR" "unknown argument: $1" ;;
    esac
done
[ -n "$EXPERIMENT" ] || die "$EXIT_CONFIG_ERROR" "--experiment is required"
require_file "$EXPERIMENT" "experiment descriptor"

# These two are options of the CLI itself, not of its subcommands, so they go
# before `experiment run`. Forwarding them is the whole point of accepting
# them here: the gate lives in Python and cannot see this script's variables.
GLOBAL_ARGS=()
[ "$ALLOW_FALLBACK" -eq 1 ] && GLOBAL_ARGS+=(--allow-fallback-without-core)
[ "$ASSUME_YES" -eq 1 ] && GLOBAL_ARGS+=(--yes)

say "validating the descriptor"
cli validate --experiment "$EXPERIMENT" >/dev/null \
    || die "$EXIT_CONFIG_ERROR" "$EXPERIMENT does not validate"

if [ "$DRY_RUN" -eq 1 ]; then
    ARGS=("${GLOBAL_ARGS[@]}" experiment dry-run --experiment "$EXPERIMENT")
    [ -n "$SEED" ] && ARGS+=(--seed "$SEED")
    [ -n "$DURATION" ] && ARGS+=(--duration "$DURATION")
    [ -n "$BACKEND" ] && ARGS+=(--backend "$BACKEND")
    cli "${ARGS[@]}"
    exit $EXIT_SUCCESS
fi

say "checking the environment"
cli env check --experiment "$EXPERIMENT" >/dev/null \
    || die "$EXIT_ENVIRONMENT_UNAVAILABLE" "the environment cannot run this experiment; \
run experiments/scripts/check_environment.sh --experiment $EXPERIMENT for the detail"

# Leftovers from a previous crash would silently impair this run.
say "clearing any leftover fabric"
cli results clean --prefix poesia >/dev/null 2>&1 || true

ARGS=("${GLOBAL_ARGS[@]}" experiment run --experiment "$EXPERIMENT")
[ -n "$RUN_ID" ] && ARGS+=(--run-id "$RUN_ID")
[ -n "$SEED" ] && ARGS+=(--seed "$SEED")
[ -n "$DURATION" ] && ARGS+=(--duration "$DURATION")
[ -n "$BACKEND" ] && ARGS+=(--backend "$BACKEND")
[ -n "$SAMPLE_INTERVAL" ] && ARGS+=(--sample-interval "$SAMPLE_INTERVAL")
[ "$FORCE" -eq 1 ] && ARGS+=(--force)

say "starting the run"
# `set +e` alone is not enough: with `set -E` the ERR trap still fires on a
# failing command substitution, and this trap exits. That would skip the
# qdisc cleanup below and the "partial results are kept" warning, which is
# precisely what a failed run needs. Handle the failure here instead.
set +e
trap - ERR
OUTPUT="$(cli "${ARGS[@]}" 2>&1 | tee /dev/stderr)"
RUN_RC=${PIPESTATUS[0]}
trap 'on_error $LINENO' ERR
set -e

RESOLVED_RUN_ID="$(printf '%s\n' "$OUTPUT" | sed -n 's/^run id: //p' | tail -1)"
[ -n "$RESOLVED_RUN_ID" ] || RESOLVED_RUN_ID="$RUN_ID"

# Exit code 2 means the environment refused before anything was created: the
# run directory holds a manifest and nothing else, so there is nothing to
# analyse and saying "partial results" would be a lie. Any other failure can
# still have collected most of a run, and that one is worth analysing.
if [ "$RUN_RC" -eq "$EXIT_ENVIRONMENT_UNAVAILABLE" ]; then
    SKIP_ANALYSIS=1
    warn "the run did not start (exit $RUN_RC); nothing was created beyond its manifest"
elif [ "$RUN_RC" -ne 0 ]; then
    warn "the run exited with $RUN_RC; its logs and partial results are kept"
fi

# The fabric is gone by now, but a hard kill can leave qdiscs on veth ends in
# the root namespace, which would impair the next run for no visible reason.
cli results clean --prefix poesia >/dev/null 2>&1 || true

if [ "$SKIP_ANALYSIS" -eq 0 ] && [ -n "$RESOLVED_RUN_ID" ]; then
    say "analysing $RESOLVED_RUN_ID"
    cli analysis run --run-id "$RESOLVED_RUN_ID" >/dev/null || \
        warn "the analysis did not complete; the raw artefacts are intact"
    cli report generate --run-id "$RESOLVED_RUN_ID" >/dev/null || \
        warn "report generation did not complete"
fi

say "run id: ${RESOLVED_RUN_ID:-<unknown>}"
exit "$RUN_RC"
