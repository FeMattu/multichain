#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Can this container actually run an experiment?
#
#   mc-preflight              report, always exit 0
#   mc-preflight --strict     exit non-zero when something mandatory is missing
#
# The harness has its own, more detailed check
# (experiments/scripts/check_environment.sh). This one covers what is specific
# to being inside a container: the capabilities, the namespace, the limits.
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

# --- capabilities ----------------------------------------------------------
# Building namespaces and applying tc both need CAP_NET_ADMIN. Without it the
# harness fails at the first `ip netns add`, several steps in.
if capsh --print 2>/dev/null | grep -q 'cap_net_admin'; then
    ok "CAP_NET_ADMIN is granted"
elif ip link add __probe type dummy 2>/dev/null; then
    ip link del __probe 2>/dev/null || true
    ok "network administration works (CAP_NET_ADMIN by effect)"
else
    bad "CAP_NET_ADMIN is missing — run with --cap-add NET_ADMIN (mcsim does)"
fi

# --- the container's own network namespace ---------------------------------
# The fabric builds inside it. Sharing the host's would put twenty emulated
# nodes on the host's real network, which is not what anyone wants.
if [ "$(readlink /proc/self/ns/net)" = "$(readlink /proc/1/ns/net 2>/dev/null)" ]; then
    note "sharing PID 1's network namespace (normal inside a container)"
fi
if ip netns list >/dev/null 2>&1; then
    ok "ip netns is usable"
else
    bad "ip netns does not work — /var/run/netns may not be writable"
fi

# --- tc and the qdiscs the fabric installs ---------------------------------
for tool in ip tc; do
    if command -v "$tool" >/dev/null 2>&1; then
        ok "$tool: $(command -v "$tool")"
    else
        bad "$tool is missing (install iproute2)"
    fi
done

if tc qdisc add dev lo root netem delay 1ms 2>/dev/null; then
    tc qdisc del dev lo root 2>/dev/null || true
    ok "netem works"
else
    bad "netem is not usable — the host kernel needs sch_netem (modprobe sch_netem)"
fi

# --- limits ----------------------------------------------------------------
SOFT=$(ulimit -Sn 2>/dev/null || echo 0)
if [ "$SOFT" -ge 8192 ]; then
    ok "open files: $SOFT"
else
    bad "open files is only $SOFT; twenty daemons and their peers need more (--ulimit nofile=1048576)"
fi

CPUS=$(nproc 2>/dev/null || echo 1)
MEM_KB=$(awk '/MemAvailable/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
note "CPUs visible: $CPUS"
note "memory available: $((MEM_KB / 1024)) MiB"
if [ "$CPUS" -lt 5 ]; then
    note "with $CPUS CPUs, a twenty-node run will report host contention as much"
    note "as protocol behaviour — the harness warns about this too"
fi

# --- MultiChain ------------------------------------------------------------
ROOT="${MULTICHAIN_HOME:-$(pwd)}"
if [ -x "$ROOT/src/multichaind" ]; then
    ok "multichaind: $ROOT/src/multichaind"
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
