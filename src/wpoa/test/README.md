# wPoA unit tests

This directory holds the wPoA **unit** tests: self-contained Boost.Test modules
compiled straight from source, fast, deterministic, and requiring **no** node
build.

The **functional** tests used to live here too. They now live at
[`test/functional/`](../../../test/functional/) — a functional run exercises wPoA,
the weight engine, the malus registry and the streams as one system, so it is not
a wPoA-module artifact. Rationale:
[`docs/adr/test-restructure-2026.md`](../../../docs/adr/test-restructure-2026.md).

## Layout

```
src/wpoa/test/
├── run_all_tests.sh                    ← single entrypoint: unit + functional
├── run_unit_tests.sh                   ← all unit suites (or a named subset)
│
├── wpoa_weight_tests.cpp               ← unit: weight registry
├── wpoa_malus_tests.cpp                ← unit: behavioural + data-integrity malus
├── wpoa_selector_tests.cpp             ← unit: proposer selector (argmin)
├── vrf_wrapper_tests.cpp               ← unit: VRF wrapper (ECVRF/DLEQ)
├── randao_accumulator_tests.cpp        ← unit: RANDAO accumulator / seed core
└── private_sortition_tests.cpp         ← unit: private (VRF-scored) sortition
```

`run_all_tests.sh` stays here because it is the only entrypoint that runs
*everything*; it delegates its functional phase to
[`test/functional/run_functional_tests.sh`](../../../test/functional/run_functional_tests.sh).

## Run the unit tests

```bash
./src/wpoa/test/run_unit_tests.sh                 # every suite
./src/wpoa/test/run_unit_tests.sh selector vrf    # just the named suite(s)
./src/wpoa/test/run_unit_tests.sh --list          # list available suites
```

Suites: `weight  malus  selector  vrf  randao  sortition`. The `vrf` and
`sortition` suites link `secp256k1`; a normal build produces
`src/secp256k1/.libs/libsecp256k1.a`, which they pick up automatically.

These runners do **not** use autotools — they invoke `g++` directly with
`-I$SRC_DIR` and resolve sources relative to themselves. Exit code is `0` only if
every selected suite **built and passed**.

## Run the functional tests

See [`test/functional/README.md`](../../../test/functional/README.md). In short:

```bash
./test/functional/run_functional_tests.sh                    # the fast default suites
QUICK=1 ./test/functional/run_functional_tests.sh            # smaller sample
./test/functional/run_functional_tests.sh --suite wpoa       # just the wPoA system run
./test/functional/run_functional_tests.sh --list             # what is available
```

## Run everything

```bash
./src/wpoa/test/run_all_tests.sh            # unit, then functional (full)
QUICK=1 ./src/wpoa/test/run_all_tests.sh    # unit, then functional (fast smoke)
```

Unit tests run **first** (fast, node-free); a unit failure **skips** the
functional phase by default, since there is no point spending minutes on
multi-node drivers when the core logic is broken. Set `CONTINUE_ON_UNIT_FAIL=1`
to run functional anyway. The full run exits non-zero if **either** phase fails.

## Environment variables

| Variable | Applies to | Meaning |
|---|---|---|
| `CXX`, `CXXFLAGS` | unit | Compiler / flags (default `g++`, `-std=c++11 -O2 -g`). |
| `TMPDIR` | unit | Where the compiled test binaries go (default `/tmp`). |
| `DRY_RUN=1` | any | Print the plan without building or launching anything. |
| `CONTINUE_ON_UNIT_FAIL=1` | all | Run the functional phase even if unit tests fail. |

The functional knobs (`NODES`, `WEIGHTS`, `QUICK`, `FUNCTIONAL_TIMEOUT`,
`BINDIR`, `KEEP_LOGS`, …) are documented in
[`test/functional/README.md`](../../../test/functional/README.md).
