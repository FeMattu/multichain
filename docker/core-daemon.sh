#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# core-up / core-down / core-status — core-daemon's life cycle in a container.
#
#   core-up [--wait SECONDS]   start core-daemon and wait until its gRPC API
#                              actually answers (default: 30s)
#   core-down                  stop it
#   core-status                report, exit 0 when the API answers
#
# One script, three names: the image symlinks core-down and core-status onto
# this file and it dispatches on $0.
#
# Why this exists at all: on a normal machine systemd starts core-daemon.
# There is no systemd in a container, and the harness's CORE fabric does not
# start the daemon either - it connects to one. So something has to, and it
# has to WAIT: core-daemon binds its gRPC port a second or two after the
# process appears, and a run that connects in that window fails its preflight
# with "no CORE daemon answering" and falls back to netns, which is the exact
# silent substitution the harness is built to refuse.
#
# The readiness check is a real gRPC call (list the sessions), not a port
# probe. The port is listening before the service behind it can answer, and
# that false ready is what makes the fallback fire.
#
#   CORE_GRPC_ADDRESS=127.0.0.1:50051   where the daemon is expected
# ---------------------------------------------------------------------------
set -uo pipefail

ADDRESS="${CORE_GRPC_ADDRESS:-127.0.0.1:50051}"
LOG_FILE="${CORE_LOG:-/var/log/core/core-daemon.log}"
PID_FILE=/var/run/core/core-daemon.pid
WAIT_SECONDS=30

say()  { printf '[core] %s\n' "$*" >&2; }
die()  { printf '[core] %s\n' "$*" >&2; exit 1; }

# Does CORE answer? A real request through the same client the harness uses,
# so a pass here means the fabric's own preflight will pass too.
api_answers() {
    python3 - "$ADDRESS" <<'PY' >/dev/null 2>&1
import sys
from core.api.grpc import client
handle = client.CoreGrpcClient(sys.argv[1])
handle.connect()
handle.get_sessions()
handle.close()
PY
}

daemon_pid() {
    if [ -r "$PID_FILE" ]; then
        local pid; pid="$(cat "$PID_FILE" 2>/dev/null || true)"
        if [ -n "$pid" ] && [ -d "/proc/$pid" ]; then printf '%s' "$pid"; return 0; fi
    fi
    pgrep -f '[c]ore-daemon' | head -1
}

cmd_up() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --wait) WAIT_SECONDS="$2"; shift 2 ;;
            *) die "core-up: unknown argument $1" ;;
        esac
    done

    command -v core-daemon >/dev/null 2>&1 || \
        die "core-daemon is not installed in this image"

    if api_answers; then
        say "already answering at $ADDRESS"
        return 0
    fi

    # core-daemon creates namespaces and bridges through vnoded, so it needs
    # the same capabilities the fabric does. Saying so here is far clearer
    # than the traceback it produces on its first node.
    if ! ip netns add __coreprobe$$ 2>/dev/null; then
        say "WARNING: this container cannot create a network namespace, so"
        say "         core-daemon will start and then fail on its first node."
        say "         It needs --cap-add NET_ADMIN --cap-add SYS_ADMIN and"
        say "         --security-opt apparmor=unconfined (mcsim passes all three)."
    else
        ip netns del __coreprobe$$ 2>/dev/null || true
    fi

    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$PID_FILE")" /tmp/pycore
    say "starting core-daemon (log: $LOG_FILE)"
    nohup core-daemon >>"$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    local waited=0
    while [ "$waited" -lt "$WAIT_SECONDS" ]; do
        if api_answers; then
            say "ready at $ADDRESS after ${waited}s"
            return 0
        fi
        # A daemon that died is not going to start answering; say why now
        # instead of burning the rest of the timeout.
        if [ -z "$(daemon_pid)" ]; then
            say "core-daemon exited during startup. Last lines of $LOG_FILE:"
            tail -n 15 "$LOG_FILE" >&2 2>/dev/null || true
            return 1
        fi
        sleep 1
        waited=$((waited + 1))
    done

    say "core-daemon did not answer at $ADDRESS within ${WAIT_SECONDS}s"
    tail -n 15 "$LOG_FILE" >&2 2>/dev/null || true
    return 1
}

cmd_down() {
    local pid; pid="$(daemon_pid)"
    if [ -z "$pid" ]; then say "not running"; return 0; fi
    say "stopping core-daemon (pid $pid)"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 10); do
        [ -d "/proc/$pid" ] || break
        sleep 1
    done
    [ -d "/proc/$pid" ] && kill -9 "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    return 0
}

cmd_status() {
    local pid; pid="$(daemon_pid)"
    if api_answers; then
        say "answering at $ADDRESS${pid:+ (pid $pid)}"
        return 0
    fi
    if [ -n "$pid" ]; then
        say "process is up (pid $pid) but nothing answers at $ADDRESS"
    else
        say "not running"
    fi
    return 1
}

case "$(basename "$0")" in
    core-down)   cmd_down "$@" ;;
    core-status) cmd_status "$@" ;;
    *)           cmd_up "$@" ;;
esac
