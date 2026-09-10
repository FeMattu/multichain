#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Container entrypoint.
#
# Three things must happen in every container, then it gets out of the way:
# raise the soft file-descriptor limit to the hard one granted by
# `docker run --ulimit`, make /proc/sys writable, and report whether this
# container can actually build an emulated network.
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

# docker mounts /proc/sys read-only. The netns fabric turns on IPv4 forwarding
# inside every router namespace, and `sysctl -q -w` exits 0 whether or not the
# write landed - so a read-only /proc/sys does not fail the run, it produces a
# backbone that silently does not route. Remounting needs CAP_SYS_ADMIN and an
# unconfined AppArmor profile, which is what mcsim and docker-compose grant;
# the preflight below is what reports it when they do not.
if [ ! -w /proc/sys/net/ipv4/ip_forward ]; then
    mount -o remount,rw /proc/sys 2>/dev/null || true
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
