#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Can this container actually run an experiment?
#
#   mc-preflight              report, always exit 0
#   mc-preflight --strict     exit non-zero when something mandatory is missing
#
# The harness has its own, more detailed check
# (experiments/scripts/check_environment.sh). This one covers what is specific
# to being inside a container: the userspace version, the capabilities, the
# namespace, the limits, the resources.
#
# Every check here does the real operation rather than probing for the tool
# that performs it. `ip netns list` succeeds in a container that cannot create
# a namespace, and that false pass is exactly how a run gets to fail four
# steps in.
# ---------------------------------------------------------------------------
set -uo pipefail

STRICT=0
[ "${1:-}" = "--strict" ] && STRICT=1
PROBLEMS=0

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$*"; PROBLEMS=$((PROBLEMS + 1)); }
note() { printf '  \033[33m·\033[0m %s\n' "$*"; }

echo
echo "container preflight"
echo "-------------------"

# --- the userspace ---------------------------------------------------------
# The whole point of the container. MultiChain links against Boost 1.74 and
# builds with GCC 11, which is 22.04; on a newer archive the build either fails
# or produces binaries whose libraries the daemons cannot load at run time.
VERSION_ID=""
[ -r /etc/os-release ] && . /etc/os-release
case "$VERSION_ID" in
    22.04) ok "userspace: Ubuntu 22.04" ;;
    "")    bad "cannot read /etc/os-release: this is not the expected image" ;;
    *)     bad "userspace is Ubuntu $VERSION_ID, not 22.04 — MultiChain needs the
      22.04 GCC 11 / Boost 1.74 archive. Rebuild: ./docker/mcsim build" ;;
esac

# --- capabilities and the namespace ----------------------------------------
# One check, because `ip netns add` is what the fabric actually calls and it
# needs all of it: CAP_NET_ADMIN, CAP_SYS_ADMIN (it mounts), an AppArmor
# profile that permits mount(), and a writable /run.
PROBE="mcpre$$"
if NETNS_ERR="$(ip netns add "$PROBE" 2>&1)"; then
    ok "ip netns add works"
    ip netns del "$PROBE" 2>/dev/null || true
else
    case "$NETNS_ERR" in
        *"make-shared"*|*"mount"*)
            bad "ip netns add cannot mount /run/netns — the container needs
      --cap-add SYS_ADMIN and --security-opt apparmor=unconfined (mcsim passes
      both). The error was: ${NETNS_ERR%%$'\n'*}" ;;
        *"not permitted"*|*"denied"*)
            bad "ip netns add was refused: ${NETNS_ERR%%$'\n'*}
      Add --cap-add NET_ADMIN --cap-add SYS_ADMIN." ;;
        *)  bad "ip netns add failed: ${NETNS_ERR%%$'\n'*}" ;;
    esac
fi

if ip link add __probe type dummy 2>/dev/null; then
    ip link del __probe 2>/dev/null || true
    ok "link administration works (veth, bridges, addresses)"
else
    bad "cannot create a link — run with --cap-add NET_ADMIN (mcsim does)"
fi

for tool in ip tc; do
    command -v "$tool" >/dev/null 2>&1 || bad "$tool is missing (install iproute2)"
done

# --- netem, the impairment itself ------------------------------------------
if tc qdisc add dev lo root netem delay 1ms 2>/dev/null; then
    tc qdisc del dev lo root 2>/dev/null || true
    ok "netem works"
else
    bad "netem is not usable — the host kernel needs sch_netem (modprobe sch_netem)"
fi

# --- forwarding ------------------------------------------------------------
# The netns fabric enables it in every router namespace with `sysctl -q -w`,
# which exits 0 even when /proc/sys is read-only. A container that fails this
# check does not fail its run: it produces a backbone that does not route.
if [ -w /proc/sys/net/ipv4/ip_forward ]; then
    ok "/proc/sys is writable (routers can enable IPv4 forwarding)"
else
    bad "/proc/sys is read-only, so the routers cannot enable forwarding and the
      backbone will not route. The entrypoint remounts it when the container has
      --cap-add SYS_ADMIN and --security-opt apparmor=unconfined."
fi

# --- limits ----------------------------------------------------------------
SOFT=$(ulimit -Sn 2>/dev/null || echo 0)
if [ "$SOFT" -ge 8192 ]; then
    ok "open files: $SOFT"
else
    bad "open files is only $SOFT; twenty daemons and their peers need more (--ulimit nofile=1048576)"
fi

# --- resources -------------------------------------------------------------
# Read from the container's own cgroup, not from the host: an experiment
# started without resource flags is meant to get everything the machine has,
# and a quota nobody meant to set looks exactly like a slow protocol.
CPUS=$(nproc 2>/dev/null || echo 1)
MEM_KB=$(awk '/MemAvailable/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
CPU_MAX=$(cat /sys/fs/cgroup/cpu.max 2>/dev/null || echo "max")
MEM_MAX=$(cat /sys/fs/cgroup/memory.max 2>/dev/null || echo "max")
CPUSET=$(cat /sys/fs/cgroup/cpuset.cpus.effective 2>/dev/null || echo "")

case "$CPU_MAX" in
    max*) ok "CPU: no quota — all $CPUS visible CPUs${CPUSET:+ ($CPUSET)}" ;;
    *)    QUOTA=${CPU_MAX%% *}; PERIOD=${CPU_MAX##* }
          note "CPU quota in force: $CPU_MAX (~$((QUOTA / PERIOD)) CPUs of $CPUS) — \
started with --cpus" ;;
esac
if [ "$MEM_MAX" = "max" ]; then
    ok "memory: no ceiling — $((MEM_KB / 1024)) MiB available"
else
    note "memory ceiling in force: $((MEM_MAX / 1048576)) MiB — started with --memory"
fi
if [ "$CPUS" -lt 5 ]; then
    note "with $CPUS CPUs, a twenty-node run will report host contention as much"
    note "as protocol behaviour — the harness warns about this too"
fi

# --- MultiChain ------------------------------------------------------------
ROOT="${MULTICHAIN_HOME:-$(pwd)}"
if [ -x "$ROOT/src/multichaind" ]; then
    # Built against another archive's Boost, it runs here and nowhere else -
    # or, more often, does not run here at all.
    if "$ROOT/src/multichaind" --version >/dev/null 2>&1; then
        ok "multichaind: $ROOT/src/multichaind"
    else
        bad "$ROOT/src/multichaind will not execute in this userspace — it was
      probably built on the host. Rebuild it here: mc-build --clean"
    fi
else
    note "multichaind not built yet — run 'mc-build'"
fi

if [ -d "$ROOT/experiments" ]; then
    ok "the harness is mounted at $ROOT/experiments"
else
    bad "no experiments/ under $ROOT — is the repository bind-mounted?"
fi

echo
if [ "$PROBLEMS" -gt 0 ]; then
    echo "  $PROBLEMS problem(s). See docker/README.md."
    [ "$STRICT" -eq 1 ] && exit 1
else
    echo "  ready."
fi
echo
exit 0
