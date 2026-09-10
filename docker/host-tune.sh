#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# host-tune.sh — kernel and CPU settings on the HOST (run it on the physical
# Ubuntu machine, not inside the container).
#
# Container namespaces do not virtualise these: vm.*, fs.* and kernel.* are
# global, and Docker refuses to set non-namespaced sysctls, so a simulation
# inherits whatever the host has. The values come from
# shadow/docs/system_configuration.md.
#
#   sudo ./docker/host-tune.sh              report only (default, changes nothing)
#   sudo ./docker/host-tune.sh --apply      apply for this boot
#   sudo ./docker/host-tune.sh --apply --persist
#                                           also write /etc/sysctl.d/99-shadow-sim.conf
#   sudo ./docker/host-tune.sh --apply --revert-governor
#                                           put the cpufreq governor back to schedutil
# ---------------------------------------------------------------------------
set -uo pipefail

APPLY=0; PERSIST=0; GOV_TARGET=performance
while [ "$#" -gt 0 ]; do
    case "$1" in
        --apply)   APPLY=1 ;;
        --persist) PERSIST=1 ;;
        --revert-governor) GOV_TARGET=schedutil ;;
        -h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
row()  { printf '  %-24s current=%-14s target=%-14s %s\n' "$1" "$2" "$3" "$4"; }
warn() { printf '\033[33m  ! %s\033[0m\n' "$*"; }

if [ "$APPLY" = 1 ] && [ "$(id -u)" -ne 0 ]; then
    echo "--apply needs root: sudo $0 --apply" >&2; exit 1
fi

# --- sysctls ---------------------------------------------------------------
# name=value pairs, in the order shadow's documentation introduces them
SYSCTLS=(
    "fs.nr_open=10485760"          # per-process open-file ceiling; caps --ulimit nofile
    "fs.file-max=10485760"         # system-wide open files
    "vm.max_map_count=1073741824"  # mmap regions per process
    "kernel.pid_max=4194304"       # kernel-wide maximum (threads.h)
    "kernel.threads-max=4194304"
    "vm.swappiness=1"              # a swapping simulation is a ruined measurement
)

say "sysctl"
for kv in "${SYSCTLS[@]}"; do
    key="${kv%%=*}"; want="${kv#*=}"
    have="$(sysctl -n "$key" 2>/dev/null || echo '?')"
    note=""
    if [ "$have" = "?" ]; then
        note="not available on this kernel"
    elif [ "$have" -lt "$want" ] 2>/dev/null; then
        note="raise"
    elif [ "$key" = vm.swappiness ] && [ "$have" -gt "$want" ] 2>/dev/null; then
        note="lower"
    else
        note="ok"
    fi
    row "$key" "$have" "$want" "$note"
    if [ "$APPLY" = 1 ] && [ "$have" != "?" ] && [ "$note" != "ok" ]; then
        sysctl -q -w "$kv" && printf '    applied %s (now %s)\n' "$key" "$(sysctl -n "$key")"
    fi
done

if [ "$APPLY" = 1 ] && [ "$PERSIST" = 1 ]; then
    CONF=/etc/sysctl.d/99-shadow-sim.conf
    {
        echo "# POESIA / wPoA Shadow simulations — see docker/host-tune.sh"
        for kv in "${SYSCTLS[@]}"; do echo "${kv%%=*} = ${kv#*=}"; done
    } > "$CONF"
    say "persisted to $CONF"
fi

# --- cpufreq ---------------------------------------------------------------
# Wall-clock comparability between runs is the point here: with a
# frequency-scaling governor the same simulation can differ by double digits.
say "cpufreq"
GOVS=$(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | sort -u | paste -sd,)
if [ -z "$GOVS" ]; then
    warn "no cpufreq interface (virtualised host, or intel_pstate in passive/HWP-only mode)"
else
    row "scaling_governor" "${GOVS}" "${GOV_TARGET}" "$([ "$GOVS" = "$GOV_TARGET" ] && echo ok || echo change)"
    if [ "$APPLY" = 1 ] && [ "$GOVS" != "$GOV_TARGET" ]; then
        n=0
        for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
            if grep -qw "$GOV_TARGET" "$(dirname "$g")/scaling_available_governors" 2>/dev/null; then
                echo "$GOV_TARGET" > "$g" && n=$((n+1))
            fi
        done
        printf '    set on %d CPUs (resets at reboot — use tuned/cpupower for persistence)\n' "$n"
    fi
fi
for f in /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference; do
    [ -r "$f" ] || continue
    row "energy_perf_preference" "$(cat "$f")" "performance" ""
    if [ "$APPLY" = 1 ]; then
        for e in /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference; do
            echo performance > "$e" 2>/dev/null || true
        done
    fi
done

# --- topology & memory (report only) ---------------------------------------
say "topology"
printf '  CPUs=%s  ' "$(nproc)"
if [ -r /sys/devices/system/cpu/smt/active ] && [ "$(cat /sys/devices/system/cpu/smt/active)" = 1 ]; then
    printf 'SMT=on\n'
    PHYS=$(lscpu --parse=cpu,core,socket,node 2>/dev/null | grep -v '^#' \
           | awk -F, '!s[$3","$2]++{print $1}' | sort -n | paste -sd,)
    warn "SMT siblings share execution resources; for a single large run prefer"
    warn "  ./docker/mcsim shell --cpuset=${PHYS}"
    warn "and for two parallel runs split the physical cores between them"
    warn "(shadow/docs/parallel_sims.md)."
else
    printf 'SMT=off/unknown\n'
fi
NODES=$(lscpu 2>/dev/null | awk -F: '/NUMA node\(s\)/{gsub(/ /,"",$2);print $2}')
[ -n "${NODES:-}" ] && printf '  NUMA nodes=%s%s\n' "$NODES" \
    "$([ "${NODES:-1}" -gt 1 ] && echo '  (keep one simulation inside one node: shared cache)' || echo '')"

say "memory"
awk '/MemTotal|SwapTotal/{printf "  %-12s %.1f GiB\n", $1, $2/1048576}' /proc/meminfo
if [ "$(awk '/SwapTotal/{print $2}' /proc/meminfo)" -gt 0 ]; then
    warn "swap is enabled: swapoff -a before a long campaign, or keep vm.swappiness=1"
fi
if [ -r /sys/kernel/mm/transparent_hugepage/enabled ]; then
    printf '  %-12s %s\n' "THP" "$(cat /sys/kernel/mm/transparent_hugepage/enabled)"
fi

# --- docker daemon ---------------------------------------------------------
say "docker"
if command -v docker >/dev/null; then
    OS=$(docker info --format '{{.OperatingSystem}}' 2>/dev/null || echo '?')
    DRV=$(docker info --format '{{.Driver}}' 2>/dev/null || echo '?')
    CG=$(docker info --format '{{.CgroupVersion}}' 2>/dev/null || echo '?')
    printf '  engine=%s  storage=%s  cgroup=v%s\n' "$OS" "$DRV" "$CG"
    case "$OS" in *"Docker Desktop"*)
        warn "Docker Desktop = containers inside a VM. Install the native engine"
        warn "(apt install docker.io, or docker-ce) for bare-metal parity." ;;
    esac
else
    warn "docker not installed"
fi

[ "$APPLY" = 0 ] && say "report only — nothing changed. Re-run with --apply (and --persist)."
exit 0
