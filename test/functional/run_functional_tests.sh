#!/usr/bin/env bash
#
# Entrypoint for the project's functional (end-to-end) tests.
#
# A functional run drives a REAL MultiChain network and exercises wPoA, the weight
# engine, the malus registry and the streams together — which is why these tests live
# here rather than under a single module. See ../../docs/adr/test-restructure-2026.md.
#
# Suites:
#   wpoa                    the wPoA system run — ONE full-stack network (weights + VRF
#                           + RANDAO + sortition), warmed up once, then every feature
#                           check against that shared run
#   weight-engine           weight-engine publish side + closed streams (single node)
#   weight-engine-bootstrap weight-engine bootstrap ordering on a clean network
#   weight-engine-large     LARGE network: 10 miners + 20 companies + 2 CAs + admin,
#                           100-block epochs, >= 50 epochs. NOT in the default set —
#                           it mines thousands of blocks and takes a long time. Use
#                           --fast (or WE_LARGE_FAST=1) for a 5-epoch iteration.
#
# The DEFAULT set is the fast one: wpoa, weight-engine, weight-engine-bootstrap.
# weight-engine-large is opt-in, by name.
#
# Usage:
#   ./run_functional_tests.sh                                  # the default (fast) set
#   ./run_functional_tests.sh --list                           # show suites and exit
#   ./run_functional_tests.sh --suite wpoa                     # one suite
#   ./run_functional_tests.sh --suite weight-engine --suite wpoa
#   ./run_functional_tests.sh --suite weight-engine-large      # the heavy run
#   ./run_functional_tests.sh --suite weight-engine-large --fast
#   ./run_functional_tests.sh --all                            # default set + large
#   QUICK=1 ./run_functional_tests.sh                          # smaller samples/budgets
#   DRY_RUN=1 ./run_functional_tests.sh                        # print the plan only
#
# Environment:
#   QUICK=1                 reduced sample sizes / budgets for a fast pass
#   INCLUDE_PUBLIC_SELECTOR run the wPoA sortition-off scenario too (default off)
#   SKIP_DIVERSITY_SCENARIO=1  skip the 4-miner mining-diversity regression scenario
#   FUNCTIONAL_TIMEOUT      hard timeout PER SUITE in seconds (default 1800; 0 = none).
#                           weight-engine-large overrides this with its own budget
#                           unless you set it explicitly.
#   NO_WARN=1               suppress the warning banners (for CI)
#   DRY_RUN=1               print the plan without launching anything
#   BINDIR, NODES, WEIGHTS, SETUP_BLOCKS, KEEP_LOGS, WE_LARGE_*  pass through.
#
# Exit code: 0 iff every selected suite passed; non-zero if any failed or timed out.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # test/functional

QUICK="${QUICK:-0}"
DRY_RUN="${DRY_RUN:-0}"
FAST_LARGE=0

# A suite's script, keyed by name. Kept as a function rather than an associative array
# so the script still runs under bash 3 (macOS /bin/bash).
suite_script() {
    case "$1" in
        wpoa)                    echo "$SCRIPT_DIR/wpoa/functional_test_wpoa_system.sh" ;;
        weight-engine)           echo "$SCRIPT_DIR/weight_engine/functional_test_weight_engine.sh" ;;
        weight-engine-bootstrap) echo "$SCRIPT_DIR/weight_engine/functional_test_weight_engine_bootstrap.sh" ;;
        weight-engine-large)     echo "$SCRIPT_DIR/weight_engine/functional_test_weight_engine_large_network.sh" ;;
        *)                       echo "" ;;
    esac
}

suite_desc() {
    case "$1" in
        wpoa)                    echo "wPoA system run (one full-stack network, every feature check)" ;;
        weight-engine)           echo "weight-engine publish side + closed streams (single node)" ;;
        weight-engine-bootstrap) echo "weight-engine bootstrap ordering on a clean network" ;;
        weight-engine-large)     echo "LARGE network, 100-block epochs, >= 50 epochs (heavy)" ;;
        *)                       echo "" ;;
    esac
}

# Per-suite default hard timeout. The large run legitimately needs hours, so a shared
# 1800s default would kill it at the first epoch rollover and report a spurious TIMEOUT.
suite_timeout() {
    if [ -n "${FUNCTIONAL_TIMEOUT:-}" ]; then
        echo "$FUNCTIONAL_TIMEOUT"; return
    fi
    case "$1" in
        weight-engine-large) [ "$FAST_LARGE" = "1" ] && echo 3600 || echo 28800 ;;
        *)                   echo 1800 ;;
    esac
}

DEFAULT_SUITES="wpoa weight-engine weight-engine-bootstrap"
ALL_SUITES="wpoa weight-engine weight-engine-bootstrap weight-engine-large"

usage() { sed -n '2,45p' "${BASH_SOURCE[0]}" | sed 's/^#\{0,1\} \{0,1\}//'; }

list_suites() {
    echo "Available functional suites:"
    local s
    for s in $ALL_SUITES; do
        local mark="  "
        case " $DEFAULT_SUITES " in *" $s "*) mark="* " ;; esac
        printf "  %s%-26s %s\n" "$mark" "$s" "$(suite_desc "$s")"
    done
    echo
    echo "  '*' marks the suites in the DEFAULT set (run when --suite is not given)."
}

# ---- parse arguments --------------------------------------------------------
SELECTED=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        -h|--help)  usage; exit 0 ;;
        --list)     list_suites; exit 0 ;;
        --all)      SELECTED="$ALL_SUITES"; shift ;;
        --fast)     FAST_LARGE=1; shift ;;
        --suite)
            [ "$#" -ge 2 ] || { echo "--suite needs a name (try --list)" >&2; exit 2; }
            if [ -z "$(suite_script "$2")" ]; then
                echo "unknown suite: $2" >&2; list_suites >&2; exit 2
            fi
            SELECTED="$SELECTED $2"; shift 2 ;;
        --suite=*)
            name="${1#--suite=}"
            if [ -z "$(suite_script "$name")" ]; then
                echo "unknown suite: $name" >&2; list_suites >&2; exit 2
            fi
            SELECTED="$SELECTED $name"; shift ;;
        *) echo "unexpected argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done
[ -n "$SELECTED" ] || SELECTED="$DEFAULT_SUITES"

# --fast is the large suite's own knob; export it so the script sees it however it was
# selected (flag or environment).
[ "$FAST_LARGE" = "1" ] && export WE_LARGE_FAST=1

# ---- run --------------------------------------------------------------------
echo "══════════════════════════════════════════════════════════════════════"
echo "  functional tests"
echo "══════════════════════════════════════════════════════════════════════"
echo "  suites:$SELECTED"
echo "  QUICK=$QUICK  INCLUDE_PUBLIC_SELECTOR=${INCLUDE_PUBLIC_SELECTOR:-0}  WE_LARGE_FAST=${WE_LARGE_FAST:-0}"

declare -a NAMES=() STATES=()
overall=0

for s in $SELECTED; do
    script="$(suite_script "$s")"
    t="$(suite_timeout "$s")"

    if [ ! -x "$script" ]; then
        echo
        echo "── [$s] ERROR: not executable or missing: $script" >&2
        NAMES+=("$s"); STATES+=("MISSING"); overall=1
        continue
    fi

    declare -a cmd=("$script")
    if [ "$t" -gt 0 ] && command -v timeout >/dev/null 2>&1; then
        cmd=(timeout --kill-after=30s "${t}s" "$script")
    fi

    echo
    echo "──────────────────────────────────────────────────────────────────────"
    echo "── [$s] $(suite_desc "$s")"
    echo "──  script:       $script"
    echo "──  hard timeout: ${t}s"
    echo "──────────────────────────────────────────────────────────────────────"

    if [ "$DRY_RUN" = "1" ]; then
        echo "   [dry-run] ${cmd[*]}"
        NAMES+=("$s"); STATES+=("DRY-RUN")
        continue
    fi

    "${cmd[@]}"
    rc=$?
    if [ "$rc" -eq 0 ]; then
        NAMES+=("$s"); STATES+=("PASS")
    elif [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
        echo "  TIMEOUT: [$s] exceeded ${t}s — often a probabilistic stall; re-running usually succeeds." >&2
        NAMES+=("$s"); STATES+=("TIMEOUT"); overall=1
    else
        NAMES+=("$s"); STATES+=("FAIL"); overall=1
    fi
done

# ---- per-suite summary ------------------------------------------------------
echo
echo "══════════════════════════════════════════════════════════════════════"
echo "  FUNCTIONAL SUMMARY (per suite)"
echo "══════════════════════════════════════════════════════════════════════"
for ((i = 0; i < ${#NAMES[@]}; i++)); do
    printf "  %-28s %s\n" "${NAMES[i]}" "${STATES[i]}"
done
echo

if [ "$overall" -ne 0 ]; then
    echo "  RESULT: FAIL"
    exit 1
fi
echo "  RESULT: PASS"
exit 0
