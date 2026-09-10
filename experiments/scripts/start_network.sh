#!/usr/bin/env bash
# Build the emulated fabric and leave it up, without starting MultiChain.
#
#   sudo -E experiments/scripts/start_network.sh --experiment <descriptor> [--run-id <id>]
#
# Useful to inspect the network before committing to a run: ping between
# namespaces, check the delays with `ip netns exec <ns> ping`, look at the
# routes. Tear it down with stop_network.sh, which never touches results.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

EXPERIMENT=""; RUN_ID=""; BACKEND=""
while [ $# -gt 0 ]; do
    case "$1" in
        --experiment) EXPERIMENT="$2"; shift 2 ;;
        --run-id) RUN_ID="$2"; shift 2 ;;
        --backend) BACKEND="$2"; shift 2 ;;
        -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
        *) die "$EXIT_CONFIG_ERROR" "unknown argument: $1" ;;
    esac
done
[ -n "$EXPERIMENT" ] || die "$EXIT_CONFIG_ERROR" "--experiment is required"
require_file "$EXPERIMENT" "experiment descriptor"

# A fabric half-built by a failure would leak namespaces. Clean up, then fail.
cleanup_partial() {
    local code=$?
    [ "$code" -eq 0 ] && return 0
    warn "the fabric did not come up; removing whatever was created"
    cli results clean --prefix poesia >/dev/null 2>&1 || true
    exit "$code"
}
trap cleanup_partial EXIT
trap 'on_error $LINENO' ERR

ARGS=(network start --experiment "$EXPERIMENT")
[ -n "$RUN_ID" ] && ARGS+=(--run-id "$RUN_ID")
[ -n "$BACKEND" ] && ARGS+=(--backend "$BACKEND")
cli "${ARGS[@]}"
trap - EXIT
say "the network is up. Tear it down with: experiments/scripts/stop_network.sh --run-id <id>"
