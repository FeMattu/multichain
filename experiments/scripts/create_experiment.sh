#!/usr/bin/env bash
# Start a new experiment from an existing one, so the axes stay comparable.
#
#   experiments/scripts/create_experiment.sh --name my-run --from regional
#   experiments/scripts/create_experiment.sh --name slow --from regional \
#       --chain-params experiments/configs/chain-params/tbt30s-sqrt.dat
#
# Copies the descriptor and rewrites only the fields you name, so that a diff
# against the original shows exactly the axis you moved - which is the whole
# discipline this suite is built around.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
trap 'on_error $LINENO' ERR

NAME=""; FROM=""; TOPOLOGY=""; CHAIN_PARAMS=""; SEED=""
while [ $# -gt 0 ]; do
    case "$1" in
        --name) NAME="$2"; shift 2 ;;
        --from) FROM="$2"; shift 2 ;;
        --topology) TOPOLOGY="$2"; shift 2 ;;
        --chain-params) CHAIN_PARAMS="$2"; shift 2 ;;
        --seed) SEED="$2"; shift 2 ;;
        -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
        *) die "$EXIT_CONFIG_ERROR" "unknown argument: $1" ;;
    esac
done
[ -n "$NAME" ] || die "$EXIT_CONFIG_ERROR" "--name is required"
[ -n "$FROM" ] || die "$EXIT_CONFIG_ERROR" "--from is required (an existing descriptor name or path)"

SOURCE="$FROM"
[ -f "$SOURCE" ] || SOURCE="$EXPERIMENTS_DIR/configs/experiments/$FROM.yaml"
require_file "$SOURCE" "source descriptor"
TARGET="$EXPERIMENTS_DIR/configs/experiments/$NAME.yaml"
[ -e "$TARGET" ] && die "$EXIT_CONFIG_ERROR" "$TARGET already exists"

cd "$REPO_DIR"
"$PYTHON" - "$SOURCE" "$TARGET" "$NAME" "${TOPOLOGY:-}" "${CHAIN_PARAMS:-}" "${SEED:-}" <<'PY'
import sys, pathlib, re
source, target, name, topology, chain_params, seed = sys.argv[1:7]
text = pathlib.Path(source).read_text(encoding="utf-8")
text = re.sub(r"^name:.*$", "name: %s" % name, text, count=1, flags=re.M)
text = re.sub(r"^scenario:.*$", "scenario: %s" % name, text, count=1, flags=re.M)
if topology:
    text = re.sub(r"^topology:.*$", "topology: %s" % topology, text, count=1, flags=re.M)
if chain_params:
    text = re.sub(r"^chain_params:.*$", "chain_params: %s" % chain_params, text, count=1, flags=re.M)
if seed:
    text = re.sub(r"^seed:.*$", "seed: %s" % seed, text, count=1, flags=re.M)
pathlib.Path(target).write_text(text, encoding="utf-8")
PY

say "created $TARGET"
cli validate --experiment "$TARGET" >/dev/null \
    || die "$EXIT_CONFIG_ERROR" "the new descriptor does not validate"
say "it validates. What you changed:"
diff -u "$SOURCE" "$TARGET" | sed -n '4,$p' || true
