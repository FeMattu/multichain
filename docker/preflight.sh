#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# In-container preflight: does this container actually behave like bare metal?
#
# Every check below maps to something that either breaks a Shadow simulation or
# silently slows it down. Run it once after `mcsim build`, and whenever the
# host's docker configuration changes.
#
#   mc-preflight            report, always exits 0
#   mc-preflight --strict   exit 1 if any check warns (for scripts / CI)
# ---------------------------------------------------------------------------
set -uo pipefail

STRICT=0
[ "${1:-}" = "--strict" ] && STRICT=1

WARN=0
ok()   { printf '  \033[32m[ ok ]\033[0m %-26s %s\n' "$1" "$2"; }
warn() { printf '  \033[33m[warn]\033[0m %-26s %s\n' "$1" "$2"; WARN=$((WARN+1)); }
info() { printf '  \033[36m[info]\033[0m %-26s %s\n' "$1" "$2"; }
head2(){ printf '\n\033[1m%s\033[0m\n' "$1"; }

read_first() { [ -r "$1" ] && head -1 "$1" 2>/dev/null; }

printf '\033[1m═══ POESIA / wPoA — container preflight ═══\033[0m\n'

# ---------------------------------------------------------------------------
head2 "Toolchain"
if command -v shadow >/dev/null; then
    ok "shadow" "$(shadow --version | head -1)"
else
    warn "shadow" "not on PATH"
fi
if [ -x "${BINDIR:-/nonexistent}/multichaind" ]; then
    # the first line of `multichaind --version` is blank
    ok "multichaind" "$("${BINDIR}/multichaind" --version 2>/dev/null | grep -m1 .)"
else
    warn "multichaind" "not built yet — run: mc-build"
fi
info "gcc / python3" "$(gcc -dumpversion) / $(python3 --version 2>&1 | cut -d' ' -f2)"
info "awk" "$(awk -W version 2>&1 | head -1 | cut -c1-46)"
PYVERS=$(python3 - <<'PY' 2>/dev/null
mods = (("networkx", "nx"), ("numpy", "np"), ("pandas", "pd"),
        ("scipy", "sp"), ("openpyxl", "xl"), ("jsonschema", "js"))
out = []
for mod, short in mods:
    try:
        out.append("%s %s" % (short, __import__(mod).__version__))
    except Exception:
        out.append("%s MISSING" % mod)
print("  ".join(out))
PY
)
case "$PYVERS" in
    *MISSING*) warn "python stack"  "$PYVERS" ;;
    *)         ok   "python stack"  "$PYVERS" ;;
esac

# ---------------------------------------------------------------------------
head2 "Shadow hard requirements"
# /dev/shm — Shadow keeps its shared-memory blocks here (one per managed
# thread). Docker's 64 MB default makes any non-trivial simulation die.
SHM_KB=$(df -k /dev/shm 2>/dev/null | awk 'NR==2{print $2}')
SHM_GB=$(( ${SHM_KB:-0} / 1024 / 1024 ))
if   [ "${SHM_KB:-0}" -ge 4194304 ]; then ok   "/dev/shm" "${SHM_GB} GiB"
elif [ "${SHM_KB:-0}" -ge 1048576 ]; then warn "/dev/shm" "${SHM_GB} GiB — small; docker run --shm-size=1024g"
else                                      warn "/dev/shm" "$(( ${SHM_KB:-0} / 1024 )) MiB — too small; docker run --shm-size=1024g"
fi

# seccomp — Docker's default profile blocks personality(), which Shadow uses to
# disable ASLR: determinism is lost and each blocked call stalls ~3 s.
# (shadow/ci/run.sh, moby/moby#43011)
SECCOMP=$(awk '/^Seccomp:/{print $2}' /proc/self/status 2>/dev/null)
case "${SECCOMP:-?}" in
    0) ok   "seccomp" "disabled (correct)" ;;
    *) warn "seccomp" "mode ${SECCOMP} active — add --security-opt seccomp=unconfined" ;;
esac

# open files
SOFT=$(ulimit -Sn); HARD=$(ulimit -Hn)
if [ "$SOFT" = "unlimited" ] || [ "$SOFT" -ge 65536 ] 2>/dev/null; then
    ok "open files (ulimit -n)" "soft=${SOFT} hard=${HARD}"
else
    warn "open files (ulimit -n)" "soft=${SOFT} — add --ulimit nofile=1048576:1048576"
fi

# ---------------------------------------------------------------------------
head2 "No hidden throttling (performance parity)"
CG2=0; [ -r /sys/fs/cgroup/cgroup.controllers ] && CG2=1

if [ "$CG2" = 1 ]; then
    CPUMAX=$(read_first /sys/fs/cgroup/cpu.max)
    case "${CPUMAX:-max}" in
        max*) ok   "cpu quota" "none (${CPUMAX:-unset})" ;;
        *)    warn "cpu quota" "${CPUMAX} — remove --cpus/--cpu-quota, Shadow needs full cores" ;;
    esac
    MEMMAX=$(read_first /sys/fs/cgroup/memory.max)
    case "${MEMMAX:-max}" in
        max) ok   "memory limit" "none" ;;
        *)   warn "memory limit" "$(( MEMMAX / 1024 / 1024 )) MiB — remove --memory unless deliberate" ;;
    esac
    # A simulation of this size is a few hundred tasks plus one Shadow worker
    # per CPU, so anything in the thousands is comfortable. Some engines apply a
    # default limit that --pids-limit=-1 does not lift.
    PIDMAX=$(read_first /sys/fs/cgroup/pids.max)
    case "${PIDMAX:-max}" in
        max) ok   "pids limit" "none" ;;
        *)   if [ "${PIDMAX}" -ge 8192 ]; then ok "pids limit" "${PIDMAX} tasks"
             else warn "pids limit" "${PIDMAX} — add --pids-limit=-1"; fi ;;
    esac
    CPUSET=$(read_first /sys/fs/cgroup/cpuset.cpus.effective)
else
    QUOTA=$(read_first /sys/fs/cgroup/cpu/cpu.cfs_quota_us)
    [ "${QUOTA:--1}" = "-1" ] && ok "cpu quota" "none (cgroup v1)" \
                              || warn "cpu quota" "${QUOTA} us — remove --cpus"
    CPUSET=$(read_first /sys/fs/cgroup/cpuset/cpuset.cpus)
fi

NPROC=$(nproc)
# Shadow pins its worker threads and only uses CPUs inside its cgroup cpuset
# (shadow/docs/parallel_sims.md). All CPUs visible == same layout as bare metal.
info "usable CPUs" "nproc=${NPROC}  cpuset=${CPUSET:-<all>}"
info "memory" "$(awk '/MemTotal/{printf "%.1f GiB total", $2/1048576}' /proc/meminfo)"

SWAP=$(awk '/SwapTotal/{print $2}' /proc/meminfo)
if [ "${SWAP:-0}" -gt 0 ]; then
    info "swap" "$(( SWAP / 1024 / 1024 )) GiB present — a swapping simulation is a ruined measurement"
else
    ok "swap" "none"
fi

# ---------------------------------------------------------------------------
head2 "Host kernel settings (change them on the HOST: docker/host-tune.sh)"
MMC=$(read_first /proc/sys/vm/max_map_count)
if [ "${MMC:-0}" -ge 262144 ]; then ok   "vm.max_map_count" "${MMC}"
else                                warn "vm.max_map_count" "${MMC:-?} — raise it for large simulations"
fi
NROPEN=$(read_first /proc/sys/fs/nr_open)
if [ "${NROPEN:-0}" -ge 1048576 ]; then ok   "fs.nr_open" "${NROPEN}"
else                                    warn "fs.nr_open" "${NROPEN:-?} — caps --ulimit nofile"
fi
info "kernel.pid_max" "$(read_first /proc/sys/kernel/pid_max)"
info "kernel.threads-max" "$(read_first /proc/sys/kernel/threads-max)"

GOV=$(read_first /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)
if [ -n "${GOV:-}" ]; then
    [ "$GOV" = performance ] && ok "cpufreq governor" "performance" \
                             || warn "cpufreq governor" "${GOV} — 'performance' removes wall-clock variance between runs"
else
    info "cpufreq governor" "not exposed to the container"
fi
SMT=$(read_first /sys/devices/system/cpu/smt/active)
[ "${SMT:-0}" = "1" ] && info "SMT / hyperthreading" "on — pin to physical cores only (mcsim shell --cpuset=...)" \
                      || info "SMT / hyperthreading" "off or not reported"

if grep -qi microsoft /proc/version 2>/dev/null; then
    warn "virtualisation" "WSL2 kernel — a VM, not bare metal: fine for development, not for the final campaign"
elif [ -r /sys/class/dmi/id/product_name ] && grep -qiE 'virtual|vmware|kvm|qemu' /sys/class/dmi/id/product_name; then
    warn "virtualisation" "$(cat /sys/class/dmi/id/product_name) — virtualised host"
else
    info "virtualisation" "no VM signature (container namespaces only: native speed)"
fi

# ---------------------------------------------------------------------------
head2 "Filesystem"
PROJ="${MULTICHAIN_HOME:-/home/mattu/multichain}"
if [ -d "$PROJ/.git" ]; then
    FSTYPE=$(df -T "$PROJ" 2>/dev/null | awk 'NR==2{print $2}')
    case "$FSTYPE" in
        overlay) warn "project mount" "on overlayfs — bind-mount the repo instead (I/O bound phases get slower)" ;;
        *)       ok   "project mount" "${PROJ} (${FSTYPE})" ;;
    esac
    [ -w "$PROJ/shadow" ] && ok "write access" "shadow/ writable as $(id -un) ($(id -u):$(id -g))" \
                          || warn "write access" "shadow/ not writable by $(id -u):$(id -g) — rebuild with USER_UID/USER_GID"
else
    warn "project mount" "${PROJ} does not look like the repository — check the bind mount"
fi
[ -d "$PROJ/v8build/v8" ] && ok "v8 prebuilt tree" "present" \
                          || warn "v8 prebuilt tree" "missing — mc-build downloads it"

printf '\n'
if [ "$WARN" -eq 0 ]; then
    printf '\033[32m═══ all checks passed ═══\033[0m\n'
else
    printf '\033[33m═══ %d warning(s) ═══\033[0m see docker/README.md\n' "$WARN"
    [ "$STRICT" = 1 ] && exit 1
fi
exit 0
