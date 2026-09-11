#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Host settings a twenty-node emulated run wants. Needs sudo to apply.
#
#   ./docker/host-tune.sh            report what is set and what it should be
#   sudo ./docker/host-tune.sh --apply
#
# Short, because emulation needs little from the host. CORE and the netns
# fabric both drive kernel primitives and run on the host's own scheduler at
# native speed, so what is left is the handful of limits that twenty real
# daemons on one machine genuinely exhaust.
#
# Nothing here is persistent: everything resets at reboot. That is deliberate
# - a benchmark harness should not silently reconfigure someone's machine.
# ---------------------------------------------------------------------------
set -Eeuo pipefail
trap 'echo "[host-tune] failed at line $LINENO" >&2' ERR

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

report() { printf '  %-34s %-16s %s\n' "$1" "$2" "$3"; }

echo
echo "host settings for a twenty-node emulated run"
echo "--------------------------------------------"

check() {   # check <sysctl> <wanted> <why>
    local key=$1 wanted=$2 why=$3
    local current
    current="$(sysctl -n "$key" 2>/dev/null || echo "?")"
    if [ "$current" = "$wanted" ]; then
        report "$key" "$current" "ok"
    else
        report "$key" "$current" "-> $wanted   ($why)"
        if [ "$APPLY" -eq 1 ]; then
            sysctl -w "$key=$wanted" >/dev/null && report "" "" "applied"
        fi
    fi
}

# Twenty namespaces, forty veth ends, plus the qdiscs on each.
check net.core.somaxconn 4096 "peer connection backlog"
check fs.inotify.max_user_instances 512 "one per namespace-watching process"

# Each multichaind opens a file per peer plus its databases.
CURRENT_NOFILE="$(ulimit -Hn)"
if [ "$CURRENT_NOFILE" -ge 1048576 ]; then
    report "ulimit -Hn" "$CURRENT_NOFILE" "ok"
else
    report "ulimit -Hn" "$CURRENT_NOFILE" "-> 1048576   (raise in /etc/security/limits.conf)"
fi

# The two modules the fabric needs. Built-in on many kernels; on WSL2 they
# usually exist as modules and are not autoloaded.
for module in sch_netem sch_tbf veth; do
    if [ -d "/sys/module/$module" ]; then
        report "module $module" "loaded" "ok"
    elif grep -qs "/$module\.ko" "/lib/modules/$(uname -r)/modules.builtin"; then
        report "module $module" "built-in" "ok"
    elif modinfo "$module" >/dev/null 2>&1; then
        report "module $module" "available" "-> modprobe $module"
        [ "$APPLY" -eq 1 ] && modprobe "$module" && report "" "" "loaded"
    else
        report "module $module" "unknown" "cannot be confirmed from userspace"
    fi
done

CPUS="$(nproc)"
echo
echo "  CPUs: $CPUS"
if [ "$CPUS" -lt 5 ]; then
    echo "  With $CPUS CPUs a twenty-node run will report host contention as much as"
    echo "  protocol behaviour. Prefer a smaller node count or a longer"
    echo "  target-block-time; the harness warns about this too."
fi

echo
[ "$APPLY" -eq 0 ] && echo "  Report only. Re-run with sudo --apply to change anything."
echo
