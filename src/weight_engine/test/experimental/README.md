# WeightEngine experimental simulation — MyLedger scenario

An **experimental, offline-analysis** harness that runs a real local MultiChain
network modelled on **MyLedger** end-to-end and records how the `WeightEngine`
behaves across many epochs — in either the weighted-wPoA regime or native
round-robin. It is *not* a pass/fail functional test (that is
[`../functional_test_weight_engine.sh`](../functional_test_weight_engine.sh)); its
product is a set of CSVs, an `.xlsx` report and a log for plotting and statistics —
plus an invariant pass that closes every run.

It **invokes** the shipped engine and **reads** its results — it never
reimplements the weight math for consensus (that lives in `src/weight_engine/`).

The design companion is [`docs/experiment.md`](docs/experiment.md).

## The network

| Actor | Count | Role |
|---|---|---|
| **ADMIN** (node 0) | 1 | the **Apuana SB stand-in**: genesis / global admin, publishes ESG + membership + reconciliation, issues and distributes GAS, and **receives** every reconciliation transfer. Not a miner — its `mine` permission is revoked once the miner set is live |
| **ClusterMinerA..E** | 5 | the wPoA validators; the engine computes and publishes each one's `w_k` |
| **Azienda_X1..X10** | 10 per cluster → **50** | addresses in the ADMIN wallet that send 10–20 GAS transfers per epoch, generating the activity `τ` |
| **FEEPOOL** | 1 | stands in for the aggregate of all senders when transaction fees are settled |

## The economics

**1 GAS = 1 EUR.** Every network transaction costs **α = 0.2 GAS**, paid to the miner
that validated it:

```
Guadagno_k^(e) = TxMiner_k^(e) · α        earnings, from the blocks the cluster proposed
Resi_k^(e)     = Guadagno_k^(e) · Reso_k  returned to the ADMIN, on chain
% Reso_k^(e)   = Resi_k / Guadagno_k · 100
Giacenza_k^(e) = the miner's on-chain GAS balance AFTER the reconciliation confirmed
Total GAIN_k   = Σ Guadagno_k over the epochs so far
```

GAS is a purpose-issued **divisible asset** (a default MultiChain has no spendable
native currency), so 0.2 and every Reso fraction are exact.

**α is not a weight input.** The engine's weight is built from ESG and activity only —
`W_k = ESG_Mk · (τ_Mk + Σ_i ESG_i·τ_i/κ)` — and α reaches it solely through
allocation → compliance → feedback, one epoch later. `Giacenza` enters the same
indirect way, via the denominator of `ρ_k`. See
[`docs/experiment.md` §1.1](docs/experiment.md).

`Σ_k Guadagno_k = α·(validated transactions)` while `Σ_k A_k = α·Θ`: the MyLedger
"earned by validating" and the thesis "entitled by weight" differ in **distribution**
(blocks mined vs weight share) and, by about 3% at the default volumes, in **total** —
because settlement, reconciliation and governance transactions are validated and earn α
too, while `Θ` counts only azienda activity. Both figures and the overhead share are
reported every run; see [`docs/experiment.md` §1.2](docs/experiment.md).

## What it does

* Brings up **1 ADMIN node + 5 cluster-miner nodes**, reusing the
  permissioned-bootstrap protocol proven in
  [`../../../wpoa/test/functional_lib.sh`](../../../wpoa/test/functional_lib.sh).
* The **ADMIN** publishes the public inputs through the sanctioned admin RPCs:
  * `weightsetesg` — a certified, static **integer** ESG score in `[10, 20]` for every
    cluster miner and every azienda, seeded (`WE_SEED`, default 42);
  * `weightsetmembership` — the azienda → cluster mapping;
  * `weightsetreconciliation` — per miner per epoch, **the GAS actually returned**.
* Each epoch every azienda sends 10–20 GAS transfers (`Θ ≈ 750`). Every transfer's
  signed input is what the engine counts as that address's `τ` for the epoch.
* At each epoch boundary the **reconciliation engine runs automatically**: read
  `TxMiner`/`Delay` from the blocks → settle `Guadagno` FEEPOOL → miner → the miner
  returns `Resi` to the ADMIN → **re-read the amount off chain** → read `Giacenza` →
  publish the chain-verified `R_k`. No manual step anywhere.
* The nodes compute `w_k` and publish it to `wpoa-weights`; the harness reads the live
  registry (`getallweights`), the per-epoch `[WeightEngine] epoch E … w_k = W` lines
  from each miner's `debug.log`, and each block's proposer via `listblocks`.

## Modes (mandatory `--mode`)

The harness runs **exactly one** mode per invocation; it never runs both.

| Mode | Node flags | Proposer selection | wpoa-weights |
|---|---|---|---|
| `--mode=wpoa`   | `-enablewpoa=1 -enableweightengine=1` | **weighted** by `w_k` | computed, drives selection |
| `--mode=native` | `-enablewpoaweights=1 -enableweightengine=1` | native **round-robin** | computed, published, *not* used for selection |

Because `Guadagno` follows blocks mined, `native` spreads earnings evenly while `wpoa`
concentrates them on the high-weight clusters — a directly comparable economic result.

## Run

```bash
# build the node first: ./autogen.sh && ./configure && make
./run_experiment.sh --mode=wpoa
./run_experiment.sh --mode=native

# a fast smoke run (minutes instead of tens of minutes)
WE_EPOCHS=4 WE_EPOCH_LENGTH=6 WE_TX_MIN=2 WE_TX_MAX=4 WE_SETUP_BLOCKS=30 \
  ./run_experiment.sh --mode=native
```

A default run is 30 epochs × 10 blocks × 2 s ≈ **12–18 minutes** of live chain. All
knobs are `WE_*` environment variables — see [`config.py`](config.py):
`WE_SEED`, `WE_MINERS`, `WE_COMPANIES`, `WE_EPOCHS`, `WE_EPOCH_LENGTH`, `WE_TX_MIN`,
`WE_TX_MAX`, `WE_ALPHA`, `WE_KAPPA`, `WE_LAMBDA`, `WE_ESG_MIN`, `WE_ESG_MAX`,
`WE_RESO_RATES`, `WE_RESO_JITTER`, `WE_ISO_CERTS`, `WE_RANK_MIN`, `WE_SETUP_BLOCKS`,
`WE_BLOCK_TIME`, …

RPC goes over a **persistent JSON-RPC HTTP connection** (a `multichain-cli` spawn per
call would dominate a 22 000-transaction run), with the CLI as automatic fallback; the
summary line reports the `http / cli` split so a silent fallback is visible.

## Output (`output/`, recreated each run)

| File | One row per | Highlights |
|---|---|---|
| `config_sheet.csv`     | cluster | ESG, Certificato ISO, nominal Reso rate, the 10 aziende and their ESG |
| `cluster_economics.csv`| epoch × cluster | **TxMiner, Impatto Cluster, Delay, Guadagno, Resi, Giacenza, % Reso, Total GAIN** + the engine's weight/probability and the recomputed `W_k`/`A_k` |
| `company_activity.csv` | epoch × azienda | Tx utente, Impatto utente, Score ESG |
| `epochs_summary.csv`   | epoch | modal proposer, method, per-cluster weight + probability, tx count, Θ, reconciliation flag |
| `esg_scores.csv`       | address | cluster/azienda, ESG score, cluster, publish txid |
| `transactions.csv`     | transaction | sender, receiver, type, GAS amount, confirming height + epoch |
| `weights_evolution.csv`| epoch × cluster | weight, normalized weight, selection probability, selected?, Δ vs prev epoch |
| `wpoa_proposer_log.csv`| epoch *(wpoa mode only)* | selected vs weight-expected proposer, cumulative per-cluster selections, cumulative deviation |
| `assertions.csv`       | invariant | the checks below and their verdicts |
| `experiment.log`        | — | levelled `[INFO]/[DEBUG]/[WARN]/[ERROR]` trace + header + summary |

The per-cluster columns are derived from `config.NUM_MINERS`, so changing the cluster
count no longer leaves stale `M1..M4` headers behind.

## Invariants checked at the end of every run

| Check | Asserts |
|---|---|
| `weight_ranking` | the engine's weight ordering agrees with the ESG + activity composite ordering (mean pairwise concordance ≥ `WE_RANK_MIN`, default 0.80 — the feedback factor legitimately reorders near-ties) |
| `conformity_rate_range` | `% Reso ∈ [0, 100]` everywhere |
| `total_gain_monotonic` | cumulative `Total GAIN` never decreases, per cluster |
| `tx_validated_once` | the per-cluster `TxMiner` tallies match an independent recount of every non-coinbase transaction in the sampled epochs' blocks |
| `gas_fees_match_validation` | `Σ Guadagno = α · (validated transactions)`; the detail line also reports `α·Θ` and the settlement/governance overhead share |
| `gas_returned_to_admin` | the ADMIN's on-chain balance increase equals `Σ Resi` read off chain |
| `gas_supply_conserved` | every balance summed equals the issued GAS supply |
| `feepool_paid_out` | the FEEPOOL's balance decrease equals `Σ Guadagno` |

The last five are pure chain reads, so they check the ledger rather than the
bookkeeping. A failure is logged and recorded but never aborts the run, so the
artifacts are always complete.

## Excel report (Vers_2 / POESIA layout)

```bash
pip install --user openpyxl          # one-time dependency
python3 make_report.py               # reads ./output, writes output/report.xlsx
python3 make_report.py --dir output --out /tmp/report.xlsx
```

| Sheet | Content |
|---|---|
| `Foglio di configurazione` | Score min/max ESG, Numero min/max Tx, α/κ/λ; per ClusterMiner **Score ESG, Certificato ISO, Peso %, Reso**; the 10 **AZIENDE** of each cluster with their ESG scores |
| `Epoch N` (one per epoch) | per azienda **Nome utente / Tx Utente / Impatto utente / Score ESG**; after each group of 10 the cluster row **Tx Miner / Impatto Cluster / Delay in msec / Guadagno Ex (€) / € Resi in Ex / Giacenza / % Reso / Total GAIN**, then the engine cross-check block; epoch totals and an ESG/ISO recap close the sheet |
| `Riepilogo` | per-epoch totals (Tx, Impatto, GAS distributed, GAS returned, mean % Reso) + per-cluster run totals |
| `Pesi & Probabilita` | epoch × cluster grid of published weights and selection probabilities |
| `Proposer log (wpoa)` | verbatim `wpoa_proposer_log.csv` (wpoa mode only) |
| `Verifiche` | the invariant checks, green/red |

Every economic figure in the workbook is **read from the chain** by the harness and
merely formatted here; totals rows are real `SUM()` formulas over the actual cell
ranges, so the sheet is auditable.

`W_k` and `A_k` never leave the node, so they are shown as a Python replay of the
pipeline beside the engine's published `w_k`. The replay's `τ_{Mk}` omits the miner's
own `wpoa-weights` publish (≈ +1 per epoch, identically for every miner), so the two
are compared by **ranking**, not by value.

## Notes / conventions

* **A transaction's `epoch` is the epoch of its confirming block**, resolved from the
  block index — a transfer near an epoch boundary is attributed where it actually
  landed, not where it was submitted.
* **"Proposer of an epoch"** is the miner that mined the most blocks in that epoch
  (an epoch spans many blocks); the full per-miner tally is in
  `wpoa_proposer_log.csv`.
* **`selection_probability`** is the theoretical `w_k / Σ w_k`. The consensus selector
  additionally applies whale-compression at election time, so observed shares track
  these probabilities without being identical (see
  `src/weight_engine/weight_engine.h`).
* **Two `τ` on purpose**: `epoch_activity` (the business view) counts only network
  traffic; `engine_tau` (the replay input) also counts a miner's reconciliation
  transfer, because the engine counts every transaction a cluster member signs.
* **Reconciliation timing**: `R_k^{(e)}` is published just after epoch `e` closes. That
  is in time because it feeds `ρ_k^{(e)}`, which the weight formula consumes one epoch
  later, and the engine replays the whole pipeline from epoch 1 on every publish.
* **Files use `_` not `-`** in module names (`chain_setup.py`, not `chain-setup.py`)
  so they are importable Python modules; `participants.py` and `economics.py` are
  added helpers the writers share.
* **Reproducibility**: every random choice (ESG, transaction picks, Reso jitter)
  derives from `WE_SEED`.
* **Error handling**: a failed RPC is logged to `experiment.log` and the run continues;
  `cli_ok` never raises; the network is always torn down on exit.
