#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Container entrypoint.
#
# Does the two things that must happen inside every container, then gets out of
# the way: raises the soft file-descriptor limit to the hard one granted by
# `docker run --ulimit`, and reports whether the container is configured to run
# Shadow at native speed.
#
#   SIM_PREFLIGHT=auto|1|0   run the preflight report (default: auto = only on a TTY)
# ---------------------------------------------------------------------------
set -uo pipefail

# Shadow opens file descriptors from its own process space for every managed
# process, so the soft limit — not the hard one — is what bites.
HARD=$(ulimit -Hn 2>/dev/null || echo "")
if [ -n "$HARD" ]; then
    ulimit -n "$HARD" 2>/dev/null || true
fi

case "${SIM_PREFLIGHT:-auto}" in
    1)    /usr/local/bin/preflight.sh || true ;;
    auto) [ -t 1 ] && /usr/local/bin/preflight.sh || true ;;
    *)    : ;;
esac

if [ -t 1 ]; then
    cat <<'BANNER'

  MultiChain + Shadow — Ubuntu 22.04 userspace on the host kernel.

    mc-build                              compile MultiChain (src/multichaind)
    mc-preflight                          re-run the environment report
    ./run.sh --config=config/simulations/<name>.json    run a simulation
    python3 tools/pipeline/run_pipeline.py --help       analyse the output

BANNER
fi

exec "$@"
