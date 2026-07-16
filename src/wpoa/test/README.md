# wPoA test suite

All wPoA tests live in this directory. There are two kinds, and three
entrypoints that run them.

## Layout

```
src/wpoa/test/
├── run_all_tests.sh                     ← single entrypoint: unit + functional
├── run_unit_tests.sh                    ← all unit suites (or a named subset)
├── run_functional_tests.sh             ← all functional suites (or a named subset)
│
├── wpoa_weight_tests.cpp                ← unit: weight registry
├── wpoa_selector_tests.cpp             ← unit: proposer selector (argmin)
├── vrf_wrapper_tests.cpp               ← unit: VRF wrapper (ECVRF/DLEQ)
├── randao_accumulator_tests.cpp        ← unit: RANDAO accumulator/seed
├── private_sortition_tests.cpp         ← unit: private (VRF-scored) sortition
│
├── functional_test_wpoa_multinode.sh   ← functional: weight + distribution
├── functional_test_wpoa_vrf.sh         ← functional: VRF beacon
├── functional_test_wpoa_randao.sh      ← functional: RANDAO beacon seed
├── functional_test_wpoa_sortition.sh   ← functional: full stack (private sortition)
└── analyze_distribution.py             ← chi-square proposer-distribution analyzer
```

**Unit tests** are self-contained Boost.Test modules compiled straight from
source — fast, deterministic, and they do **not** require the node to be built.
**Functional tests** bootstrap **real** multi-node MultiChain networks and mine
blocks — they **do** require a built node (`./autogen.sh && ./configure && make`).

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
./src/wpoa/test/run_functional_tests.sh                 # every suite
./src/wpoa/test/run_functional_tests.sh vrf sortition   # just the named suite(s)
QUICK=1 ./src/wpoa/test/run_functional_tests.sh         # fast smoke (reduced samples)
```

Suites: `multinode  vrf  randao  sortition`, run in that order (each layers on
the previous; `sortition` exercises the full VRF+RANDAO+sortition stack). The
individual drivers remain directly runnable and accept the same env knobs as
before (`BINDIR`, `NODES`, `WEIGHTS`, `SETUP_BLOCKS`, `DIST_BLOCKS`, …).

### ⚠ Warning about the functional tests

Functional tests drive a live distributed system, so please note:

* **They can take a long time.** Each suite bootstraps a multi-node network and
  mines hundreds of blocks; a full run is on the order of many minutes.
* **They can occasionally stall or fail to terminate on their own.** Slow weight
  convergence, a transient simultaneous-qualifier fork, or a node that fails to
  join can leave a run hanging. This is a **property of the blockchain /
  distributed environment under test, not a defect in the scripts.** The
  probability is **low**, but it is real and is called out explicitly here.
* **Safety net.** `run_functional_tests.sh` wraps every suite in a hard timeout
  (`FUNCTIONAL_TIMEOUT`, default `1800`s; set `0` to disable). A suite that trips
  it is reported as `TIMEOUT`; re-running almost always succeeds. Use `QUICK=1`
  for a much faster (smaller-sample) pass.

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
| `QUICK=1` | functional / all | Reduced sample sizes and timeouts for a fast pass. |
| `FUNCTIONAL_TIMEOUT` | functional / all | Per-suite hard timeout in seconds (`0` disables). |
| `NO_WARN=1` | functional / all | Suppress the warning banner (for CI). |
| `DRY_RUN=1` | any | Print the plan without building or launching anything. |
| `CONTINUE_ON_UNIT_FAIL=1` | all | Run the functional phase even if unit tests fail. |
| `BINDIR`, `NODES`, `WEIGHTS`, `KEEP_LOGS`, … | functional | Passed straight through to the drivers. |
```
