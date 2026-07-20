# WeightEngine experimental simulation

An **experimental, offline-analysis** harness that runs a real local MultiChain
network end-to-end and records how the `WeightEngine` behaves across many epochs —
in either the weighted-wPoA regime or native round-robin. It is *not* a pass/fail
functional test (that is
[`../functional_test_weight_engine.sh`](../functional_test_weight_engine.sh)); its
product is a set of CSVs + a log for plotting and statistics.

It **invokes** the shipped engine and **reads** its results — it never
reimplements the weight math (that lives in `src/weight_engine/`).

## What it does

* Brings up **1 admin node + N miner nodes** (default `N=4`), reusing the
  permissioned-bootstrap protocol proven in
  [`../../../wpoa/test/functional_lib.sh`](../../../wpoa/test/functional_lib.sh).
* The **admin** (genesis / global admin, *not* a miner — its mine permission is
  revoked) publishes the public inputs through the sanctioned admin RPCs:
  * `weightsetesg` — a certified, static ESG score for every miner and every
    company (5 companies per miner → 20 companies), seeded (`WE_SEED`, default 42);
  * `weightsetmembership` — the company → miner cluster mapping;
  * `weightsetreconciliation` — a simulated `R_k` per miner, once per epoch.
* Each epoch it generates on-chain **activity** — company↔company, miner↔miner and
  symbolic asset transfers — by moving a purpose-issued asset (a default MultiChain
  has no native currency). Every transfer's signed input is what the engine counts
  as the address's `tau` for that epoch.
* The nodes compute `w_k` and publish it to `wpoa-weights`; the harness reads the
  live registry (`getallweights`) and the per-epoch, epoch-tagged
  `[WeightEngine] epoch E … w_k = W` lines from each miner's `debug.log`, and reads
  each block's proposer via `listblocks` (as `analyze_distribution.py` does).

## Modes (mandatory `--mode`)

The harness runs **exactly one** mode per invocation; it never runs both.

| Mode | Node flags | Proposer selection | wpoa-weights |
|---|---|---|---|
| `--mode=wpoa`   | `-enablewpoa=1 -enableweightengine=1` | **weighted** by `w_k` | computed, drives selection |
| `--mode=native` | `-enablewpoaweights=1 -enableweightengine=1` | native **round-robin** | computed, published, *not* used for selection |

## Run

```bash
# build the node first: ./autogen.sh && ./configure && make
./run_experiment.sh --mode=wpoa
./run_experiment.sh --mode=native

# smaller/faster (all knobs are WE_* env vars; see config.py)
WE_EPOCHS=6 WE_EPOCH_LENGTH=4 WE_SETUP_BLOCKS=12 ./run_experiment.sh --mode=native
```

A run drives a live multi-node chain for many blocks, so it takes several minutes;
`WE_*` knobs let you trade fidelity for speed.

## Output (`output/`, recreated each run)

| File | One row per | Highlights |
|---|---|---|
| `epochs_summary.csv`   | epoch | modal proposer, method, per-miner weight + probability, tx count, reconciliation flag |
| `esg_scores.csv`       | address | company/miner, ESG score, cluster, publish txid |
| `transactions.csv`     | transaction | sender, receiver, type, amount, confirming height + epoch |
| `weights_evolution.csv`| epoch × miner | weight, normalized weight, selection probability, selected?, Δ vs prev epoch |
| `wpoa_proposer_log.csv`| epoch *(wpoa mode only)* | selected vs weight-expected proposer, cumulative per-miner selections, cumulative deviation |
| `experiment.log`       | — | levelled `[INFO]/[DEBUG]/[WARN]/[ERROR]` trace + header + summary |

## Notes / conventions

* **A transaction's `epoch` is the epoch of its confirming block**, resolved from
  the block index — a transfer near an epoch boundary is attributed where it
  actually landed, not where it was submitted.
* **"Proposer of an epoch"** is the miner that mined the most blocks in that epoch
  (an epoch spans many blocks); the full per-miner tally is in
  `wpoa_proposer_log.csv`.
* **`selection_probability`** is the theoretical `w_k / Σ w_k`. The consensus
  selector additionally applies whale-compression at election time, so observed
  shares track these probabilities without being identical (see
  `src/weight_engine/weight_engine.h`).
* **Files use `_` not `-`** in module names (`chain_setup.py`, not `chain-setup.py`)
  so they are importable Python modules; `participants.py` is an added helper the
  writers share.
* **Reproducibility**: every random choice (ESG, transaction picks, reconciliation
  amounts) derives from `WE_SEED`.
* **Error handling**: a failed RPC is logged to `experiment.log` and the run
  continues; the network is always torn down on exit.
