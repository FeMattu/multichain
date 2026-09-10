#!/usr/bin/env bash
# Report whether this machine can run an experiment, and what is only optional.
#
#   experiments/scripts/check_environment.sh
#   experiments/scripts/check_environment.sh --experiment <descriptor>
#
# Exit 0 when a run is possible, 2 when a mandatory piece is missing.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
trap 'on_error $LINENO' ERR

EXPERIMENT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --experiment) EXPERIMENT="$2"; shift 2 ;;
        -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
        *) die "$EXIT_CONFIG_ERROR" "unknown argument: $1" ;;
    esac
done

echo "=== operating system ==========================================="
if [ -r /etc/os-release ]; then . /etc/os-release; echo "  distribution : ${PRETTY_NAME:-unknown}"; fi
echo "  kernel       : $(uname -r)"
echo "  architecture : $(uname -m)"
case "$(uname -r)" in
    *microsoft*|*WSL*)
        echo "  note         : WSL2. Namespaces and tc work, but the kernel is Microsoft's;"
        echo "                 sch_netem may need 'modprobe sch_netem' and cpuid is not"
        echo "                 virtualised, so rdrand stays native." ;;
esac

echo
echo "=== mandatory =================================================="
MISSING=0
for tool in ip tc python3; do
    if command -v "$tool" >/dev/null 2>&1; then
        printf '  %-14s %s\n' "$tool" "$(command -v "$tool")"
    elif [ -x "/usr/sbin/$tool" ]; then
        # iproute2 lives in sbin, which is not on a non-root PATH: the single
        # most common reason a present tool looks missing.
        printf '  %-14s /usr/sbin/%s (not on your PATH; add /usr/sbin)\n' "$tool" "$tool"
    else
        printf '  %-14s MISSING\n' "$tool"; MISSING=$((MISSING + 1))
    fi
done

echo
echo "=== kernel modules ============================================="
BUILTIN="/lib/modules/$(uname -r)/modules.builtin"
for module in sch_netem sch_tbf veth; do
    if [ -d "/sys/module/$module" ]; then
        printf '  %-14s loaded\n' "$module"
    elif [ -r "$BUILTIN" ] && grep -q "/$module\.ko" "$BUILTIN" 2>/dev/null; then
        # Compiled into the kernel rather than loadable. /sys/module is empty
        # for a built-in driver and modinfo fails on it, so checking only those
        # two reports a working kernel as broken.
        printf '  %-14s built into the kernel\n' "$module"
    elif modinfo "$module" >/dev/null 2>&1; then
        printf '  %-14s available, not loaded (modprobe %s)\n' "$module" "$module"
    else
        # Undecidable without root: a built-in driver on a kernel that ships no
        # modules.builtin looks exactly like a missing one. Say so, and let the
        # run fail with a precise message rather than blocking it here.
        printf '  %-14s cannot be confirmed from userspace\n' "$module"
        case "$module" in
            sch_netem) warn "sch_netem could not be confirmed; if 'tc qdisc add ... netem' fails, run 'sudo modprobe sch_netem'" ;;
            veth)      warn "veth could not be confirmed; if 'ip link add type veth' fails, the kernel lacks CONFIG_VETH" ;;
        esac
    fi
done

echo
echo "=== privileges ================================================="
if [ "$(id -u)" -eq 0 ]; then
    echo "  running as root"
elif sudo -n true 2>/dev/null; then
    echo "  passwordless sudo available"
else
    echo "  NOT root and sudo needs a password."
    echo "  A real run needs CAP_NET_ADMIN. Without it you can still use"
    echo "  'experiment dry-run', 'validate' and the whole analysis path."
fi

echo
echo "=== optional ==================================================="
for tool in nsenter curl core-daemon docker git; do
    if command -v "$tool" >/dev/null 2>&1; then
        printf '  %-14s %s\n' "$tool" "$(command -v "$tool")"
    else
        printf '  %-14s absent\n' "$tool"
    fi
done
echo "  (curl is used by the role scripts inside the nodes; without it a run"
echo "   starts but no permission, ESG or membership record is ever written.)"

echo
echo "=== python modules ============================================="
cd "$REPO_DIR"
"$PYTHON" - <<'PY'
mandatory = ["yaml", "jsonschema"]
analysis = ["numpy", "scipy", "pandas", "matplotlib", "networkx", "openpyxl"]
optional = ["core"]
missing = 0
for group, names, need in (("mandatory", mandatory, True),
                           ("analysis", analysis, False),
                           ("optional", optional, False)):
    for name in names:
        try:
            module = __import__(name)
            version = getattr(module, "__version__", "present")
            print("  %-14s %-10s (%s)" % (name, version, group))
        except ImportError:
            print("  %-14s %-10s (%s)" % (name, "MISSING", group))
            if need:
                missing += 1
raise SystemExit(1 if missing else 0)
PY
[ $? -ne 0 ] && MISSING=$((MISSING + 1))

if [ -n "$EXPERIMENT" ]; then
    echo
    echo "=== this experiment ============================================"
    require_file "$EXPERIMENT" "experiment descriptor"
    if ! cli env check --experiment "$EXPERIMENT"; then
        die "$EXIT_ENVIRONMENT_UNAVAILABLE" "the experiment cannot run here; see the report above"
    fi
fi

echo
if [ "$MISSING" -gt 0 ]; then
    die "$EXIT_ENVIRONMENT_UNAVAILABLE" "$MISSING mandatory item(s) missing"
fi
say "environment OK"
