# Functional tests

End-to-end tests that drive a **real** MultiChain network: they launch
`multichaind` / `multichain-cli` processes, mine blocks and assert network
behaviour.

They live here, at project level, rather than under `src/wpoa/test/` or
`src/weight_engine/test/`, because a functional run exercises wPoA, the weight
engine, the malus registry and the streams **as one system** — none of them is a
single module's artifact. The unit tests stay with their modules. Rationale:
[`docs/adr/test-restructure-2026.md`](../../docs/adr/test-restructure-2026.md).

> This is the only `test/` tree in the repository. Upstream Bitcoin Core keeps a
> `src/test/` and a `qa/`; this fork has neither, and the unit tests live beside
> their modules instead (`src/wpoa/test/`, `src/weight_engine/test/`).

## Layout

```
test/functional/
├── run_functional_tests.sh      ← the runner: suite selection, per-suite timeout
├── lib/
│   ├── functional_lib.sh        ← shared helpers (sourced, never executed)
│   ├── lint_lib.sh              ← checks the harness itself, stubbed RPCs, no node
│   └── we_stats.py              ← the statistical layer + its own self-check
├── wpoa/
│   ├── functional_test_wpoa_system.sh   ← ONE full-stack network, every feature check
│   └── analyze_distribution.py          ← chi-square proposer-distribution analyzer
└── weight_engine/
    ├── functional_test_weight_engine.sh                ← publish side, closed streams
    ├── functional_test_weight_engine_bootstrap.sh      ← bootstrap ordering
    └── functional_test_weight_engine_large_network.sh  ← 33 nodes, >= 50 epochs (heavy)
```

## Suites

| Suite | Default? | What it does |
|---|---|---|
| `lib-lint` | **yes** | Checks the **harness**, not the chain: every script parses, the epoch-geometry and setup-budget helpers return their known values, and every per-epoch recorder is driven against **stubbed RPCs**. **Needs no node** and takes about a second. It runs first for a reason — the recorders fire for the first time at the first epoch rollover, so a typo there used to surface hours into the large run. |
| `stats-selfcheck` | **yes** | Validates the statistical machinery itself — chi-square p-values against textbook critical values, Gini and entropy against closed forms, Cor. 5.4, and a negative control confirming an unweighted draw is rejected. **Needs no node**, so it is the one suite that runs where `multichaind` does not build. |
| `wpoa` | **yes** | One full-stack network (weights + VRF + RANDAO + sortition), warmed up once, then every feature check against that shared run: weight registry, stream permissions, malus, multi-node consistency, mining-diversity, VRF, RANDAO, sortition, distribution. |
| `weight-engine` | **yes** | Single genesis node: the two published input streams auto-create CLOSED, ESG is Certification-Authority-only, membership is self-written, reconciliation has no write path, the closed-stream guard bites, verification is reachable. |
| `weight-engine-bootstrap` | **yes** | Clean multi-node network: `wpoa-weights` exists *before* wPoA engages, the `setup-first-blocks` floor is enforced on chain, the registry is populated at the transition, no stall. |
| `weight-engine-large` | **no** | 10 miners + 20 companies + 2 CAs + admin, 100-block epochs, ≥ 50 epochs (~5120 blocks). Exercises the restitution-rate feedback, epoch-scoped verification, proposer coverage and GAS refuelling over a long run, then **records itself to `test/output/` and runs the statistical analysis**. **Hours** by default; `--fast` cuts it to 5 epochs. |

## Run

```bash
./test/functional/run_functional_tests.sh --suite lib-lint # check the harness (~1s, no node)
./test/functional/run_functional_tests.sh                  # the default (fast) set
./test/functional/run_functional_tests.sh --list           # show suites, mark the defaults
./test/functional/run_functional_tests.sh --suite wpoa     # one suite
./test/functional/run_functional_tests.sh --suite weight-engine --suite wpoa
./test/functional/run_functional_tests.sh --all            # default set + the large run
QUICK=1 ./test/functional/run_functional_tests.sh          # smaller samples / budgets
DRY_RUN=1 ./test/functional/run_functional_tests.sh        # print the plan only
```

The heavy suite, explicitly:

```bash
./test/functional/run_functional_tests.sh --suite weight-engine-large          # 50 epochs
./test/functional/run_functional_tests.sh --suite weight-engine-large --fast   # 5 epochs
WE_LARGE_LAMBDA=0.3 ./test/functional/run_functional_tests.sh --suite weight-engine-large
```

Every script is also runnable directly. The runner adds suite selection, a
per-suite hard timeout and a **per-suite** summary table.

Requires a built node (`./autogen.sh && ./configure && make`) — except `lib-lint`
and `stats-selfcheck`, which need none and are therefore worth running before any
long suite is paid for. The unit suites do not either — see [`src/wpoa/test/`](../../src/wpoa/test/) and
[`src/weight_engine/test/`](../../src/weight_engine/test/).

## ⚠ These drive a live distributed system

* **They take time.** Minutes for the default set; hours for
  `weight-engine-large` at 50 epochs.
* **They can occasionally stall.** Slow weight convergence, a transient
  simultaneous-qualifier fork, or a node that fails to join can hold up a run.
  That is a **property of the system under test, not a defect in the script.**
  The probability is low but real.
* **Safety net.** The runner wraps each suite in a hard timeout
  (`FUNCTIONAL_TIMEOUT`, default 1800 s; the large suite defaults to 28800 s, or
  3600 s under `--fast`; `0` disables). A tripped run is reported as `TIMEOUT`;
  re-running almost always succeeds. `QUICK=1` gives a much faster pass.

## Environment variables

| Variable | Applies to | Meaning |
|---|---|---|
| `BINDIR` | all | Where `multichaind`/`-cli`/`-util` live (default `src/`). |
| `QUICK=1` | wpoa | Smaller sample and shorter budgets. |
| `NODES`, `WEIGHTS` | wpoa, bootstrap | Network size; per-node static weights. |
| `SETUP_BLOCKS` | wpoa, bootstrap | `setup-first-blocks` requested in `params.dat`. |
| `SAMPLE_BLOCKS`, `CONFIRM_BUFFER` | wpoa | Sample window and the burial buffer before the fork check. |
| `RANDAO_LOOKBACK`, `SORTITION_DELTA`, `SORTITION_LAMBDA`, `DIST_TOLERANCE` | wpoa | Feature knobs passed to the node / analyzer. |
| `INCLUDE_PUBLIC_SELECTOR=1` | wpoa | Also run the sortition-off (public argmin) scenario. |
| `SKIP_DIVERSITY_SCENARIO=1` | wpoa | Skip the 4-miner mining-diversity regression scenario. |
| `EPOCH_LEN` | weight-engine | Epoch length for the single-node run (default 4). |
| `WE_LARGE_SETUP_BLOCKS` | weight-engine-large | `setup-first-blocks`. Derived from the node count by default — raise it if the bootstrap outruns it (the suite says so explicitly if it does). |
| `WE_LARGE_MC_DRAWS`, `WE_LARGE_ALPHA` | weight-engine-large | Monte Carlo draws per scenario (50000) and significance level (0.01). |
| `WE_LARGE_OUTPUT`, `WE_LARGE_NAME` | weight-engine-large | Where the recorded run is written, and under what name. |
| `WE_LARGE_*` (others) | weight-engine-large | See the header of that script; all documented there. |
| `FUNCTIONAL_TIMEOUT` | all | Hard timeout **per suite**, in seconds (`0` disables). |
| `NO_WARN=1` | all | Suppress the warning banners (for CI). |
| `DRY_RUN=1` | all | Print the plan without launching anything. |
| `KEEP_LOGS=1` | all | Keep node datadirs on teardown, for post-mortem. |
| `FL_PARAM_OVERRIDES` | all | Extra `params.dat` lines (`key = value`, one per line). Consensus-critical parameters belong **here**, not on the command line. |

## Writing a new functional test

Source the library and let it own the lifecycle:

```bash
FUNC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$FUNC_DIR/lib/functional_lib.sh"

trap fl_teardown EXIT
fl_require_binaries
fl_start_network "-enablewpoa=1"          # or fl_start_single_node "..."

fl_check_begin "my_property" 1
    fl_assert_gt0 "$(fl_node_total 0)" "aggregate weight"
fl_check_end || true

fl_teardown
fl_check_summary || exit 1
```

`fl_check_summary` returns non-zero iff a **critical** check failed, which is what
the runner reads. The library's public surface is documented in its header
comment; the epoch-geometry helpers (`fl_buried_epoch_at`,
`fl_height_for_buried_epoch`, `fl_setup_first_blocks_floor`) exist so no test
re-derives the stability/publish margins by hand.
