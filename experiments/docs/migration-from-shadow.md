# Migration from Shadow

What moved, what was archived, what changed, and how to get any of it back.

## Summary

| | |
|---|---|
| removed | `shadow/` — 3.1 GB, 6160 tracked files |
| migrated | topologies, network model, chain parameters, role scripts, the whole analysis pipeline, the campaign's analytical products (2.2 MB) |
| archived in git history | the raw campaign data at commit `6278274` |
| verified | the migrated pipeline reproduces `shadow/risultati` **byte for byte**; the migrated topologies regenerate every historical `.gml` **byte for byte** |

Nothing was lost. `git checkout 6278274 -- shadow/` restores the whole tree.

## Why Shadow was removed

Three properties of the simulator determined the architecture of the old
suite, and none of them was about the protocol under test:

1. **`--unblocked-vdso-latency` was mandatory.** `Strengthen()` in
   `src/utils/random.cpp` busy-waits on `clock_gettime`, which Shadow credited
   10 ns; without the flag a node took tens of minutes of wall clock to boot.
   With it, the simulator charged latency to every clock call — and that
   latency is inside the archived block-time figures.
2. **The simulated clock started on 2000-01-01 and was not configurable.** A
   natively prepared data directory was rejected with *"block timestamp too
   far in the future"*, so the entire bootstrap had to run inside the
   simulation, and no step could use an interpreter.
3. **Jitter was never implemented** ([shadow#3601](https://github.com/shadow/shadow/issues/3601)).
   Every archived edge carries `jitter "0 us"`.

Running the binaries on a real emulated network removes all three. See
[architecture.md](architecture.md) for what replaces them.

## What was migrated, and how it was verified

### Topologies — verified byte for byte

`shadow/config/levels/*.json` and `intercontinental-global.json` became
`configs/topologies/legacy-*.yaml`, keeping every coordinate, label,
backbone/access split and **GML node id** (archived edge tables key on those
ids). The check is not a description but a comparison:
`tests/golden/test_legacy_topologies.py` exports each migrated YAML and
asserts it reproduces the historical `.gml` exactly.

Reaching that exposed two bugs in the converter, both fixed:

* `re.findall` returns `""`, not `None`, for a group that did not participate,
  so the GML attribute parser silently read every numeric value as empty;
* the derived delay was rounded twice — once in the model, once at emission —
  which moved one edge by a microsecond. It is now rounded once, at emission.

Four **new 20-node topologies** extend each geography: the ten historical
locations stay exactly where they were and ten more are added, reaching seven
backbone hubs. Worst end-to-end RTT runs 10.3 / 23.7 / 55.7 / 363.0 ms against
the historical 10.0 / 22.0 / 44.7 / 112.0 ms.

### The latency model — unchanged on purpose

```
one_way_ms = 0.005 · D_km · 1.4 + overhead     (0.5 ms backbone, 1.0 ms access)
```

Identical to `tools/gen_topology.py`. Changing it would silently invalidate
every comparison with the archive, so it is pinned and unit-tested against its
published check points (Milan–New York 6464 km → 91.5 ms RTT).

### Chain parameters — values asserted unchanged

Migrated key by key with an assertion, and the assertion caught a real
discrepancy: **`params-tbt10s-log.dat` was never a one-axis variant.** It
moved four knobs at once — `dump-function` to `log`, `weight-epoch-length` to
100, `measure-epochs` to 100 and `wpoa-sortition-lambda` to 0.3. It is
preserved verbatim as `tbt10s-log-epoch100.dat` (the descriptor behind the
historical `run6`), and a genuine one-axis `tbt10s-log.dat` is added
alongside. `tests/unit/test_chain_params.py` asserts both facts.

### Role scripts — migrated with their protocol knowledge

`role_admin.sh`, `role_miner.sh`, `role_company.sh`, `role_ca.sh` and
`node_first_launch.sh` became `runtime/roles/*.sh`. Comments were translated
to English; the on-chain logic is unchanged, including the parts that are
easy to lose:

* creating `wpoa-weights` explicitly and CLOSED;
* granting stream write permissions one stream per call (MultiChain rejects
  `grant addr "a.write,b.write"` with *"Could not parse entity key"*);
* the admin's explicit `subscribe`;
* the epoch sampler's burial margin, and its recovery of *all* ready epochs
  rather than only the latest;
* raising `maxtxfee` with the relay fee, without which stream publications
  silently fail while the network looks healthy.

They still speak JSON-RPC over `curl` rather than `multichain-cli`, and the
reason changed while the conclusion did not: under Shadow the CLI's
`Strengthen()` loop was fatal through the vDSO; natively it is 100 ms of real
CPU per invocation, which at twenty nodes polled every thirty seconds on the
host already running twenty daemons is not affordable either.

### The analysis pipeline — migrated with `git mv`, verified against the archive

`tools/pipeline/` → `analysis/pipeline/`, `tools/analizza_esperimenti.py` and
friends → `analysis/legacy/`. History follows the files.

Verified by re-running everything over the archived campaign:

* all three phases over `run1-tbt-15s/regionale` reproduce
  `shadow/risultati/run1-tbt-15s/regionale` **byte for byte** (the `.xlsx`
  excluded: it embeds a creation timestamp);
* the legacy analyser reproduces **every row** of all seventeen campaign
  sheets.

`tests/golden/test_legacy_pipeline.py` is that check, and it skips with
recovery instructions when the archive is not checked out.

Discovery now handles both layouts, chosen by inspection rather than by a
flag, so a campaign mixing archived and new runs analyses in one pass. A new
run is presented to the pipeline by `compatibility/run_adapter.py`, which
writes the level JSON and GML it expects into the run's own
`analysis-compat/`. The pipeline itself was not rewritten — rewriting it would
mean re-deriving every metric definition, and the point of migrating is that
they must not change.

## The three changes that are not byte-identical

Every one is deliberate, and none changes a value.

1. **`config.csv` provenance strings, for a native run only.** Four rows say
   where a value came from. A legacy run still reads `shadow.yaml general.seed`
   — the archive reproduces exactly — while a native run reads
   `manifest.json seed`. Parameter names and values are untouched.
2. **`fit_prop518.csv` changes if the input set changes.** It is a regression
   over the whole campaign, and the archived sheets predate `run6`. Restricted
   to their twenty runs it is byte-identical.
3. **`epoch_shares.csv` row order.** The current code sorts by address; the
   version that wrote the archive did not. Row *contents* are identical, and
   sorting makes the output reproducible, which it previously was not.

## What was archived rather than migrated

| what | size | where |
|---|---|---|
| `shadow/esperimenti/` — raw run data, 24 runs | ~1.1 GB, 4663 files | git `6278274` |
| `shadow/risultati/` — pipeline phase outputs | ~38 MB, 1185 files | git `6278274` |
| `shadow/analisi/.cache/` | 25 MB | regenerable; not kept |
| `shadow/runs/`, `shadow/<level>/run/` | ~2 GB | never tracked (gitignored) |

Recovering any of it:

```bash
git checkout 6278274 -- shadow/esperimenti shadow/config shadow/risultati
```

`tests/golden/test_legacy_pipeline.py::test_archive_recovery_instructions_are_accurate`
asserts that this commit really does carry the tree, so the instruction cannot
rot.

## What was kept, and where it went

| was | is now |
|---|---|
| `shadow/config/levels/*.json` | `configs/topologies/legacy-*.yaml` |
| `shadow/config/topologies/*.gml` | regenerated; kept as golden fixtures in `tests/golden/legacy-gml/` |
| `shadow/config/blockchain/*.dat`, `params.overrides` | `configs/chain-params/*.dat` |
| `shadow/config/simulation.schema.json` | `configs/schema/experiment.schema.json` and its three companions |
| `shadow/config/treasury.json` | `configs/treasury.json` — **address only** (see below) |
| `shadow/tools/role_*.sh`, `sim_common.sh` | `runtime/roles/` |
| `shadow/tools/gen_topology.py` | `topology/models.py` + `generator.py` + `exporters.py` |
| `shadow/tools/check_topology.py` | `analysis/legacy/check_topology.py`, plus `cli topology validate` |
| `shadow/tools/pipeline/**` | `analysis/pipeline/**` |
| `shadow/tools/analizza_esperimenti.py` and friends | `analysis/legacy/` |
| `shadow/analisi/*.md`, `fogli-di-analisi/`, `plots/` | `analysis/historical/shadow-campaign/` |
| `shadow/risultati/campaign/` | `analysis/historical/shadow-campaign/campaign/` |
| `shadow/docs/pipeline/` | `docs/pipeline/` |
| `shadow/run.sh` | `scripts/run_experiment.sh` + `cli experiment run` |

### The treasury private key was deliberately not carried over

`shadow/config/treasury.json` shipped a private key. Nothing in the harness
ever spends from the treasury — the admin imports it **watch-only** with
`importaddress`, so only the address has a runtime purpose. The migrated
`configs/treasury.json` therefore carries the address alone, keeping the
historical value `18Qrmht…` so that new runs match the
`weight_treasury_address` every archived `run_index.csv` records. A full pair
can be regenerated with `cli multichain treasury --force --with-key`, into a
file `.gitignore` excludes.

## Deliberate Shadow references that remain

`grep -ri shadow experiments/` finds matches, and each is intentional:

* `docs/migration-from-shadow.md` (this file) and the historical sections of
  the other documents;
* `analysis/historical/` — the archived campaign, labelled as Shadow results
  throughout, in its README and in every report banner;
* `analysis/pipeline/` and `analysis/legacy/` — comments describing what the
  archived data looks like and why (the two `debug.log` locations, the
  headerless CSVs, the `shadow.yaml` fallback in `parse_run_metadata`);
* the manifest section key `shadow` and the `config.csv` row
  `shadow_general_seed` — **artefact column names**, frozen because every
  archived report and comparison keys on them. Renaming them would break the
  compatibility this migration exists to provide. Both are annotated in place.
* `analysis/legacy/check_topology.py` — it validates the GML constraints
  Shadow's parser imposed. The exporter still satisfies them, so old and new
  edge tables carry the same numbers.

## Comparing a new run with the archive

You can, and you must say what you are doing. See
[metrics.md](metrics.md), "Three clocks". The short version:

* **Never compare timestamps.** Simulated time and wall-clock time are
  different quantities.
* **Block-time means carry different biases.** The archived figure includes
  the vDSO latency the simulator charged; a new one includes host contention.
  Neither is the protocol's `λΦ` feedback on its own.
* **Distributions, shares and test statistics are comparable.** Proposer
  shares, chi-square, Gini, epoch trajectories and the timer-race margin are
  dimensionless or in blocks, and mean the same thing in both.
* **Jitter is new.** The archive has none anywhere.
