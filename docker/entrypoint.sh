#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Container entrypoint.
#
# Four things must happen in every container, then it gets out of the way:
# raise the soft file-descriptor limit to the hard one granted by
# `docker run --ulimit`, make /proc/sys writable, start core-daemon, and
# report whether this container can actually build an emulated network.
#
#   MC_CORE=auto|1|0        start core-daemon (default: auto = when installed)
#   MC_CORE_WAIT=30         seconds to wait for its gRPC API
#   MC_PREFLIGHT=auto|1|0   run the environment report (default: auto = on a TTY)
# ---------------------------------------------------------------------------
set -uo pipefail

# Twenty multichaind processes, each with its peers, exhaust a default soft
# limit long before the hard one.
HARD=$(ulimit -Hn 2>/dev/null || echo "")
if [ -n "$HARD" ]; then
    ulimit -n "$HARD" 2>/dev/null || true
fi

# docker mounts /proc/sys read-only. Both fabrics turn on IPv4 forwarding
# inside node namespaces with `sysctl -q -w`, which exits 0 whether or not the
# write landed - so a read-only /proc/sys does not fail the run, it produces a
# backbone that silently does not route. Remounting needs CAP_SYS_ADMIN and an
# unconfined AppArmor profile, which is what mcsim and docker-compose grant;
# the preflight below is what reports it when they do not.
if [ ! -w /proc/sys/net/ipv4/ip_forward ]; then
    mount -o remount,rw /proc/sys 2>/dev/null || true
fi

# CORE is the harness's primary fabric and nothing else starts its daemon:
# the fabric connects to one, and with `backend: auto` a daemon that is not
# answering means the run stops for consent to use netns instead. Starting it
# here is what makes `backend: auto` resolve to CORE inside this image.
#
# A failure is reported and not fatal. Plenty of useful commands - mc-build,
# the analysis pipeline, validate, dry-run - need no fabric at all, and
# refusing to give someone a shell because the emulator did not come up would
# take away the very tools they need to find out why.
case "${MC_CORE:-auto}" in
    0)  : ;;
    1)  /usr/local/bin/core-up --wait "${MC_CORE_WAIT:-30}" || \
            echo "[entrypoint] core-daemon did not come up; 'core-status' has the detail" >&2 ;;
    *)  if command -v core-daemon >/dev/null 2>&1; then
            /usr/local/bin/core-up --wait "${MC_CORE_WAIT:-30}" >/dev/null 2>&1 || \
                echo "[entrypoint] core-daemon did not come up; run 'core-up' to see why" >&2
        fi ;;
esac

case "${MC_PREFLIGHT:-auto}" in
    1)    /usr/local/bin/preflight.sh || true ;;
    auto) [ -t 1 ] && /usr/local/bin/preflight.sh || true ;;
    *)    : ;;
esac

if [ -t 1 ]; then
    cat <<'BANNER'

  MultiChain + CORE — one Ubuntu 22.04 userspace, the host's own kernel.

    mc-build                                   compile MultiChain into src/
    core-status / core-up / core-down          the CORE daemon
    mc-preflight                               re-run the environment report

    experiments/scripts/check_environment.sh   can this container do it?
    experiments/scripts/run_experiment.sh \
        --experiment experiments/configs/experiments/smoke-3n.yaml

    python3 -m experiments.cli --help          every command

BANNER
fi

exec "$@"
