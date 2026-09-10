#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Container entrypoint.
#
# Two things must happen in every container, then it gets out of the way:
# raise the soft file-descriptor limit to the hard one granted by
# `docker run --ulimit`, and report whether this container can actually build
# an emulated network.
#
#   MC_PREFLIGHT=auto|1|0   run the environment report (default: auto = on a TTY)
# ---------------------------------------------------------------------------
set -uo pipefail

# Twenty multichaind processes, each with its peers, exhaust a default soft
# limit long before the hard one.
HARD=$(ulimit -Hn 2>/dev/null || echo "")
if [ -n "$HARD" ]; then
    ulimit -n "$HARD" 2>/dev/null || true
fi

case "${MC_PREFLIGHT:-auto}" in
    1)    /usr/local/bin/preflight.sh || true ;;
    auto) [ -t 1 ] && /usr/local/bin/preflight.sh || true ;;
    *)    : ;;
esac

if [ -t 1 ]; then
    cat <<'BANNER'

  MultiChain + real network emulation — Ubuntu 22.04 userspace, host kernel.

    mc-build                                   compile MultiChain into src/
    mc-preflight                               re-run the environment report

    experiments/scripts/check_environment.sh   can this container do it?
    experiments/scripts/run_experiment.sh \
        --experiment experiments/configs/experiments/smoke-3n.yaml

    python3 -m experiments.cli --help          every command

BANNER
fi

exec "$@"
