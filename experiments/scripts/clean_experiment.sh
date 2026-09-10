#!/usr/bin/env bash
# Remove what a crashed run left behind. Results are never removed by default.
#
#   sudo -E experiments/scripts/clean_experiment.sh
#   sudo -E experiments/scripts/clean_experiment.sh --prefix poesia
#   sudo -E experiments/scripts/clean_experiment.sh --run-id <id> --purge-results --yes
#
# The default target is the emulated fabric: namespaces, the management bridge,
# stray veth ends in the root namespace and the qdiscs still attached to them.
# That last one matters - a leftover netem qdisc silently impairs the next run.
#
# --purge-results deletes a run's directory. It asks first, and refuses to
# assume when there is no terminal to ask.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
trap 'on_error $LINENO' ERR

PREFIX="poesia"; RUN_ID=""; PURGE=0
while [ $# -gt 0 ]; do
    case "$1" in
        --prefix) PREFIX="$2"; shift 2 ;;
        --run-id) RUN_ID="$2"; shift 2 ;;
        --purge-results) PURGE=1; shift ;;
        --yes) ASSUME_YES=1; shift ;;
        -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
        *) die "$EXIT_CONFIG_ERROR" "unknown argument: $1" ;;
    esac
done

say "removing the fabric of session prefix '$PREFIX'"
if [ -n "$RUN_ID" ]; then
    cli results clean --prefix "$PREFIX" --run-id "$RUN_ID"
else
    cli results clean --prefix "$PREFIX"
fi

# Any multichaind left over from a run that died before its cleanup path.
if pgrep -f "multichaind .*poesia" >/dev/null 2>&1; then
    warn "multichaind processes are still running:"
    pgrep -af "multichaind .*poesia" || true
    if confirm "terminate them?"; then
        pkill -TERM -f "multichaind .*poesia" || true
        sleep 5
        pkill -KILL -f "multichaind .*poesia" 2>/dev/null || true
        say "terminated"
    else
        warn "left running; the next run may fail with a locked data directory"
    fi
fi

if [ "$PURGE" -eq 1 ]; then
    [ -n "$RUN_ID" ] || die "$EXIT_CONFIG_ERROR" "--purge-results needs --run-id"
    ROOT="$(cd "$REPO_DIR" && "$PYTHON" -c \
        "from experiments.paths import run_dir; print(run_dir('$RUN_ID'))")"
    [ -d "$ROOT" ] || die "$EXIT_CONFIG_ERROR" "no such run: $ROOT"
    du -sh "$ROOT"
    if confirm "DELETE the results at $ROOT?"; then
        rm -rf "$ROOT"
        say "deleted $ROOT"
    else
        say "kept $ROOT"
    fi
fi
say "cleanup complete"
