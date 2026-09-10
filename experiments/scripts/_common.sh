# ---------------------------------------------------------------------------
# Shared by every script in this directory. Source it; do not execute it.
#
# Exit codes are the interface: the CLI returns these and so do the scripts,
# so a caller can branch on them. The table is duplicated in
# experiments/exit_codes.py and tests/unit/test_exit_codes.py parses this file
# to prove the two agree.
# ---------------------------------------------------------------------------
set -Eeuo pipefail

EXIT_SUCCESS=0
EXIT_CONFIG_ERROR=1
EXIT_ENVIRONMENT_UNAVAILABLE=2
EXIT_RUNTIME_ERROR=3
EXIT_INCOMPLETE_DATA=4
EXIT_ANALYSIS_FAILED=5

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENTS_DIR="$(cd "$SCRIPTS_DIR/.." && pwd)"
REPO_DIR="$(cd "$EXPERIMENTS_DIR/.." && pwd)"
PYTHON="${PYTHON:-python3}"

# Run the CLI from the repository root, so `python -m experiments.cli` resolves
# without the caller having to be there or to set PYTHONPATH.
cli() { (cd "$REPO_DIR" && "$PYTHON" -m experiments.cli "$@"); }

# Progress goes to stderr, always: several of these scripts pass the CLI's JSON
# through on stdout, and a progress line in the middle of it would break every
# caller that parses it.
say()  { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
warn() { printf '[%s] WARNING: %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
die()  { local code=$1; shift; printf '[%s] ERROR: %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; exit "$code"; }

# on_error <line>: the ERR trap. Reports where it happened instead of leaving
# the caller to guess from a bare non-zero exit.
on_error() {
    local code=$? line=${1:-?}
    warn "failed at line $line (exit $code)"
    exit "$code"
}

# require <tool> [hint]
require() {
    command -v "$1" >/dev/null 2>&1 || \
        die "$EXIT_ENVIRONMENT_UNAVAILABLE" "$1 is not installed.${2:+ $2}"
}

# require_file <path> <what>
require_file() {
    [ -f "$1" ] || die "$EXIT_CONFIG_ERROR" "$2 not found: $1"
}

# confirm <question>: yes unless a tty says otherwise. Non-interactive callers
# must pass --yes rather than being asked a question nobody will answer.
confirm() {
    if [ "${ASSUME_YES:-0}" = "1" ]; then return 0; fi
    if [ ! -t 0 ]; then
        die "$EXIT_CONFIG_ERROR" "$1 (refusing to assume; pass --yes)"
    fi
    printf '%s [y/N] ' "$1"
    local answer; read -r answer
    case "$answer" in [yY]*) return 0 ;; *) return 1 ;; esac
}
