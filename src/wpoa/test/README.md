# wPoA test suite

All wPoA tests live in this directory. There are two kinds, and three
entrypoints that run them.

## Layout

```
src/wpoa/test/
├── run_all_tests.sh                     ← single entrypoint: unit + functional
├── run_unit_tests.sh                    ← all unit suites (or a named subset)
├── run_functional_tests.sh             ← wrapper: the system run + hard timeout
│
├── wpoa_weight_tests.cpp                ← unit: weight registry
├── wpoa_selector_tests.cpp             ← unit: proposer selector (argmin)
├── vrf_wrapper_tests.cpp               ← unit: VRF wrapper (ECVRF/DLEQ)
├── randao_accumulator_tests.cpp        ← unit: RANDAO accumulator/seed
├── private_sortition_tests.cpp         ← unit: private (VRF-scored) sortition
│
├── functional_test_wpoa_system.sh      ← THE functional test: one network, many checks
├── functional_lib.sh                    ← shared bash helpers (sourced, not executed)
└── analyze_distribution.py             ← chi-square proposer-distribution analyzer
```

**Unit tests** are self-contained Boost.Test modules compiled straight from
source — fast, deterministic, and they do **not** require the node to be built.
The **functional test** is a single, system-level run: it bootstraps **one**
real multi-node MultiChain network, warms it up once, and then verifies every
feature against that shared run — it **does** require a built node
(`./autogen.sh && ./configure && make`).

## Run only the unit tests

```bash
./src/wpoa/test/run_unit_tests.sh                 # every suite
./src/wpoa/test/run_unit_tests.sh selector vrf    # just the named suite(s)
./src/wpoa/test/run_unit_tests.sh --list          # list available suites
```

Suites: `weight  selector  vrf  randao  sortition`. The `vrf` and `sortition`
suites link `secp256k1`; a normal build produces
`src/secp256k1/.libs/libsecp256k1.a`, which they pick up automatically.

Exit code is `0` only if every selected suite **built and passed**; any compile
or test failure yields a non-zero exit.

## Run only the functional tests

```bash
./src/wpoa/test/run_functional_tests.sh                 # the single system run
QUICK=1 ./src/wpoa/test/run_functional_tests.sh         # fast smoke (smaller sample)
INCLUDE_PUBLIC_SELECTOR=1 ./src/wpoa/test/run_functional_tests.sh
```

There is now **one** functional test —
[`functional_test_wpoa_system.sh`](functional_test_wpoa_system.sh), also runnable
directly. It starts **one** full-stack network (weights + VRF + RANDAO +
sortition), waits for weight convergence and a block warm-up **once**, then runs
all feature checks on that shared run, organised as phases:

| Phase | What happens |
|---|---|
| **1 setup** | create the chain, bootstrap N nodes with the full stack |
| **2 warm-up** | wait for weight convergence, mine past the sample window (once) |
| **3 checks** | `check_weight`, `check_multinode_consistency`, `check_vrf`, `check_randao`, `check_sortition`, `check_distribution` — all on the same run |
| **4 teardown** | stop and wipe every node |

Each check prints ✔/✗ lines and a final results table; the run exits non-zero if
**any critical check fails**. `run_functional_tests.sh` is a thin wrapper that
adds a hard timeout around this run.

**Why one run?** The old design had a separate script per feature, each
re-bootstrapping a network and re-waiting for blocks. Since the sortition
configuration already enables the *whole* stack, a single full-stack network
produces VRF reveals, RANDAO seeds and sortition scorings together — so all of
those are verified on one setup, at a fraction of the cost.

**Optional independent regime.** Block acceptance is regime-exclusive: with
sortition on, the public *argmin* selection path (and its `VRF reveal OK` log)
never runs. `INCLUDE_PUBLIC_SELECTOR=1` adds a short second scenario with
sortition **off** (VRF+RANDAO only) to cover that path. It reuses the same
helpers (no duplicated bootstrap) and is **off by default**, so the default cost
stays one network.

### ⚠ Warning about the functional test

It drives a live distributed system, so please note:

* **It can take time.** It mines a window of blocks on a real multi-node network
  — several minutes. It is now optimised to reuse **one** setup and **one**
  warm-up for every check (instead of re-bootstrapping per feature).
* **It can occasionally stall or wait longer than usual.** Slow weight
  convergence, a transient simultaneous-qualifier fork, or a node that fails to
  join can hold up a run. This is a **property of the blockchain / distributed
  environment under test, not a defect in the script.** The probability is
  **low**, but it is real and is called out explicitly here.
* **Safety net.** `run_functional_tests.sh` wraps the run in a hard timeout
  (`FUNCTIONAL_TIMEOUT`, default `1800`s; set `0` to disable). A run that trips it
  is reported as `TIMEOUT`; re-running almost always succeeds. Use `QUICK=1` for
  a much faster (smaller-sample) pass.

## Run everything (full system validation)

```bash
./src/wpoa/test/run_all_tests.sh            # unit, then functional (full)
QUICK=1 ./src/wpoa/test/run_all_tests.sh    # unit, then functional (fast smoke)
```

`run_all_tests.sh` runs the **unit tests first** (fast, node-free) and then the
**functional tests**. If the unit phase fails it **skips** the functional phase
by default (there is no point spending minutes on multi-node drivers when the
core logic is broken); set `CONTINUE_ON_UNIT_FAIL=1` to run functional anyway.
The full run exits non-zero if **either** phase fails.

## Useful environment variables

| Variable | Applies to | Meaning |
|---|---|---|
| `CXX`, `CXXFLAGS` | unit | Compiler / flags (default `g++`, `-std=c++11 -O2 -g`). |
| `QUICK=1` | functional / all | Smaller sample and shorter budgets for a fast pass. |
| `INCLUDE_PUBLIC_SELECTOR=1` | functional / all | Also run the sortition-off (public argmin) scenario. |
| `FUNCTIONAL_TIMEOUT` | functional / all | Hard timeout in seconds for the whole run (`0` disables). |
| `NO_WARN=1` | functional / all | Suppress the warning banner (for CI). |
| `DRY_RUN=1` | any | Print the plan without building or launching anything. |
| `CONTINUE_ON_UNIT_FAIL=1` | all | Run the functional phase even if unit tests fail. |
| `NODES`, `WEIGHTS`, `SETUP_BLOCKS`, `SAMPLE_BLOCKS`, `CONFIRM_BUFFER` | functional | Network size / weights / warm-up + sample window. |
| `RANDAO_LOOKBACK`, `SORTITION_DELAY`, `DIST_TOLERANCE` | functional | Feature knobs passed to the node / analyzer. |
| `BINDIR`, `KEEP_LOGS` | functional | Binaries location; keep node datadirs on teardown. |
```
