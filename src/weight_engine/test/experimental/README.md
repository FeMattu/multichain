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

## What this experiment is for

**Does the deployed weight engine compute the weight the POESIA / Vers_2 model
specifies, and does wPoA then select proposers by it?**

Everything else here exists to make that one comparison trustworthy. The harness replays
the documented pipeline from the *same public inputs the node reads*, and checks its
prediction of `w_k` against the integer the node actually published — cell by cell, by
value.

**Result on the reference smoke runs: `20/20` cells exact in `wpoa` mode**, and 19–20 of
20 in `native`, where the residue is off by a single integer unit at an exact `.5`
rounding boundary (`46.725 × 100 = 4672.5`). The engine computes the documented formula.

## The pipeline

`κ = 100` is Vers_2's divide-by-100 and `λ = 0.5` is its `Peso %Reso = 50`, so the
spreadsheet and the thesis are the *same* formulas:

```
ImpUtente_i^(e)  = ESG_i · τ_i^(e) / κ                          the engine's c_i
ImpCluster_k^(e) = ESG_Mk · (τ_Mk^(e) + Σ_i ImpUtente_i^(e))     the raw weight W_k
w_k^(e)          = W_k^(e) · [ρ_k^(e-1)·λ + (1−λ)]               the final weight
Delay_k^(e)      = ImpCluster_k / Σ_j ImpCluster_j · 1000        per-mille weight
p_k^(e)          = Delay_k^(e) / 1000                            selection probability
A_k^(e)          = Θ^(e) · p_k^(e) · α                           Guadagno
R_k^(e)          ∈ [0, A_k + B_k^(e-1)]                          Resi — sent ON CHAIN
B_k^(e)          = B_k^(e-1) + A_k^(e) − R_k^(e)                 Giacenza, B^(0) = 0
% Reso_k^(e)     = R_k^(e) / (A_k^(e) + B_k^(e-1)) · 100         tasso di conformità
Total GAIN_k^(e) = Total GAIN_k^(e-1) + A_k^(e)
```

**1 GAS = 1 EUR**, `α = 0.2 GAS` per transaction. GAS is a purpose-issued **divisible
asset** (a default MultiChain has no spendable native currency), so 0.2 and every Reso
fraction are exact.

Each line above was checked against the printed Vers_2 epoch-1 figures — `ImpCluster`
756, `Delay` 228, `Guadagno` 34.54, `Giacenza` 9.66, `% Reso` 72.03 % — and the epoch-2
carry-forward (`Giacenza` 21.24, `% Reso` 56.30 %, `Total GAIN` 73.49). Every one
reproduces to the cent.

### Four things that are easy to get wrong

| | |
|---|---|
| **`Guadagno` is not "the fees of the blocks I mined"** | the epoch's whole pot is `α·Θ` and it is split by **weight share** `p_k`. Who proposed a block does not enter it. `Σ_k A_k = α·Θ` therefore holds as an **equality** the ledger must satisfy |
| **`Giacenza` is a running balance** | `B_k^(e-1) + A − R`, not `A − R`, and not the miner's raw on-chain GAS balance (which also carries its seed funding and its miner↔miner trading). The raw balance is reported separately as `saldo_onchain` |
| **`% Reso` divides by `A_k + B_k^(e-1)`** | the balance *available to reconcile*, not by `A_k` alone |
| **`Delay in msec` is not a latency** | in Vers_2 it is the **per-mille normalized weight**; its per-epoch total is exactly **1000**. The genuinely measured inter-block interval is the separate `block_interval_ms` column |

**α is not a weight input.** `W_k` is a function of ESG and activity only; α scales the
allocation, and so reaches the weight solely through
allocation → compliance → feedback, one epoch later. `Giacenza` enters the same indirect
way, via the denominator of `ρ_k`. See [`docs/experiment.md` §1.1](docs/experiment.md).

### The one place the spreadsheet and the C++ core disagree

Vers_2 derives its `GuadagnoEx` from the **feedback-adjusted** `ImpCluster`, while the
thesis and `weight_engine.h` define `A_k = α·Θ·W_k/W_tot` on the **raw** `W_k`. The two
coincide in epoch 1 and can diverge from epoch 2 on. `WE_ALLOC_BASIS` selects which one
is settled on chain (`raw`, the default, so the ledger mirrors what the node computes);
**both are always computed and reported** side by side as `delay_raw` / `delay_final`.
See [`docs/experiment.md` §1.2](docs/experiment.md).

## What it does

* Brings up **1 ADMIN node + 5 cluster-miner nodes**, reusing the
  permissioned-bootstrap protocol proven in
  [`../../../wpoa/test/functional_lib.sh`](../../../wpoa/test/functional_lib.sh).
* The **ADMIN** publishes the public inputs through the sanctioned admin RPCs:
  * `weightsetesg` — a certified, static **integer** ESG score in `[10, 20]` for every
    cluster miner and every azienda, seeded (`WE_SEED`, default 42);
  and the aziende / miners declare their OWN cluster membership, self-attested:
  * membership — each azienda signs its own `{node_address, miner_address, timestamp}`
    record (`publishfrom` from the azienda's own address), and each miner registers
    itself as a cluster head with the public `weightregistermembership`. There is no
    admin path: a record signed by anyone other than the node it names is discarded
    by every reader;
  and reconciliation is **not published at all**: the engine derives `R_k` from the
  epoch's confirmed transfers to the treasury address, so the harness only has to MAKE
  the transfers (it already did) and point the engine at the recipient with
  `-weighttreasuryaddress=<ADMIN>`.
* The cluster sets are then **read back off chain** by listing the membership stream and
  taking, per declaring address, its latest confirmed `miner_address` — the same
  last-confirmed-wins fold the engine applies internally
  (`mc_AccumulateLatestMembership` + `mc_BuildClustersFromMembership`). The old
  `getstreamkeysummary … jsonobjectmerge` read no longer applies: the merge was additive,
  which is exactly why it could not express a node leaving a cluster. From that point the
  harness works from published state, not from its own idea of the topology, so a
  membership bug is detectable rather than shared.
* Each epoch every azienda **and every cluster miner** sends 10–20 GAS transfers
  (`Θ ≈ 750`). Every transfer's signed input is what the engine counts as that address's
  `τ` for the epoch.
* **`τ` is reconstructed exactly, not estimated.** The engine counts +1 per distinct
  signing address per non-coinbase transaction. The harness knows the signer of every
  transaction it submitted and reads the signer of the ones it did not — each miner's own
  per-epoch `w_k` publish — off the `wpoa-weights` publisher index. Coverage is then
  asserted against an independent recount of the epoch's blocks (`tau_coverage`), which
  is what licenses comparing `w_k` **by value** instead of by ranking.
* At each epoch boundary the **reconciliation engine runs automatically**: derive `τ` →
  compute `W_k`, `w_k`, `Delay`, `p_k`, `A_k` → settle `A_k` FEEPOOL → miner → the miner
  returns `R_k` to the ADMIN → **re-read the amount off the confirmed transaction** →
  fold `B_k`, `ρ_k`, `Total GAIN` forward → publish the chain-verified `R_k`. No manual
  step anywhere.
* The nodes compute `w_k` and publish it to `wpoa-weights`; the harness reads the live
  registry (`getallweights`), the per-epoch `[WeightEngine] epoch E … w_k = W` lines
  from each miner's `debug.log`, and each block's proposer via `listblocks`.

## Modes (mandatory `--mode`)

The harness runs **exactly one** mode per invocation; it never runs both.

| Mode | Node flags | Proposer selection | wpoa-weights |
|---|---|---|---|
| `--mode=wpoa`   | `-enablewpoa=1 -enableweightengine=1` | **weighted** by `w_k` | computed, drives selection |
| `--mode=native` | `-enablewpoaweights=1 -enableweightengine=1` | native **round-robin** | computed, published, *not* used for selection |

`Guadagno` is identical in both modes — it follows weight share, not proposership. What
differs is **who actually proposes**: `native` round-robins regardless of `w_k`, `wpoa`
draws proportionally to it. Running both on the same seed therefore isolates the
consensus effect of the weight from its economic effect, and `native` doubles as the
control: the engine still computes and publishes `w_k`, so `engine_matches_replay` is
verifiable without weighted selection in the loop at all.

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

> **Keep the volume within what the chain absorbs.** If submissions outpace block
> (HISTORICAL — no longer reachable: `R_k` is derived, so no record can confirm late.)
> production a mempool backlog builds, `weightsetreconciliation` confirms *after* the
> epoch it belongs to has buried, and the engine then reads `ρ = 0` and applies the bare
> `(1−λ)` bracket — every published `w_k` comes out as exactly `round(W_k·κ·(1−λ))` and
> the weight comparison fails for a reason that has nothing to do with the engine. The
> harness now blocks on those records confirming and warns above `WE_MEMPOOL_WARN`
> (default 200) — **a run that trips that warning is not a valid measurement.** Lower
> `WE_TX_MIN`/`WE_TX_MAX` or raise `WE_EPOCH_LENGTH`.

RPC goes over a **persistent JSON-RPC HTTP connection** (a `multichain-cli` spawn per
call would dominate a 22 000-transaction run), with the CLI as automatic fallback; the
summary line reports the `http / cli` split so a silent fallback is visible.

## Output (`output/`, recreated each run)

| File | One row per | Highlights |
|---|---|---|
| `config_sheet.csv`     | cluster | ESG, Certificato ISO, nominal Reso rate, the 10 aziende and their ESG |
| `cluster_economics.csv`| epoch × cluster | the Vers_2 summary columns **Tx Miner, Impatto Cluster, Delay, Guadagno, Resi, Giacenza, % Reso, Total GAIN**, then the pipeline detail (`raw_weight`, `final_weight`, `feedback_bracket`, `delay_raw`/`delay_final`, `p_k`, `giacenza_prev`, `available`, `rho`, `saldo_onchain`), the consensus outcome (`blocks_mined`, `block_interval_ms`) and the engine cross-check (`engine_weight`, `w_k_expected_int`, `weight_match`) |
| `company_activity.csv` | epoch × azienda | Tx utente, Impatto utente, Score ESG |
| `epochs_summary.csv`   | epoch | modal proposer, method, per-cluster weight + probability, tx count, Θ, reconciliation flag |
| `esg_scores.csv`       | address | cluster/azienda, ESG score, cluster, publish txid |
| `transactions.csv`     | transaction | sender, receiver, type, GAS amount, confirming height + epoch |
| `weights_evolution.csv`| epoch × cluster | weight, normalized weight, selection probability, selected?, Δ vs prev epoch |
| `wpoa_proposer_log.csv`| epoch *(wpoa mode only)* | selected vs weight-expected proposer, cumulative per-cluster selections, cumulative deviation |
| `epoch_checks.csv`     | epoch × check | the five per-epoch model invariants, checked inside `close_epoch` while the run is live |
| `assertions.csv`       | invariant | the run-level checks below and their verdicts |
| `experiment.log`        | — | levelled `[INFO]/[DEBUG]/[WARN]/[ERROR]` trace + header + summary |

The per-cluster columns are derived from `config.NUM_MINERS`, so changing the cluster
count no longer leaves stale `M1..M4` headers behind.

## Invariants

Two levels. The **five model invariants** run inside `close_epoch`, epoch by epoch,
while the run is live (→ `epoch_checks.csv`):

| Check | Asserts |
|---|---|
| `alloc_sums_to_alpha_theta` | `Σ_k A_k = α·Θ` — the pot is fully and exactly distributed |
| `delay_sums_to_1000` | the per-mille normalization: `Σ_k Delay_k = 1000` |
| `rho_in_unit_interval` | `ρ_k ∈ [0, 1]` |
| `balance_non_negative` | `B_k ≥ 0` |
| `resi_within_available` | `R_k ≤ A_k + B_k^(e-1)` — nobody returns more than was available |

The **run-level checks** then close the run (→ `assertions.csv`):

| Check | Asserts |
|---|---|
| **`engine_matches_replay`** | **the primary result**: the integer weight each node published equals the harness's independent replay of `w_k`, for ≥ `WE_WEIGHT_MATCH_MIN` (0.95) of the cells. Cells are classed `exact` / `within-tol` (≤ `WE_WEIGHT_REL_EPS`, 1 %) / `off` |
| `weight_ranking` | the weight ordering agrees with the ESG + activity composite ordering (mean pairwise concordance ≥ `WE_RANK_MIN`, default 0.80 — the feedback factor legitimately reorders near-ties) |
| `reconciliation_visible_to_engine` | every `R_k` record confirmed before the next epoch buried. **If this fails the weight comparison is meaningless** — the engine reads `ρ = 0` and applies the bare `(1−λ)` bracket. See the caveat below |
| `settlement_confirmed` | every settlement transfer and governance publish made it into a block; GAS in flight is reported here rather than as a phantom supply gap |
| `tau_coverage` | every transaction in every sampled epoch was attributed to a signer. **This is the precondition for comparing `w_k` by value**; without it the comparison degrades to ranking |
| `membership_from_chain` | the cluster sets read back off the membership stream are the configured topology — no company double-claimed, none orphaned, no wrong-sized cluster |
| `conformity_rate_range` | `% Reso ∈ [0, 100]` everywhere |
| `total_gain_monotonic` | cumulative `Total GAIN` never decreases, per cluster |
| `alloc_equals_alpha_theta` | `Σ A_k = α·Θ` over the whole run — an **equality**, unlike the per-block fee tally it replaced |
| `gas_returned_to_admin` | the ADMIN's on-chain balance increase equals `Σ R_k` read off chain |
| `feepool_paid_out` | the FEEPOOL's balance decrease equals `Σ A_k` |
| `gas_supply_conserved` | every balance summed equals the issued GAS supply |
| `giacenza_matches_chain` | per miner, `(closing − opening balance) − net miner↔miner trading = B_k`. This is what ties the accounting table to the ledger |
| `proposer_share_tracks_p_k` | *(wpoa mode)* the L1 deviation between observed block share and mean `p_k`. **Reported, never thresholded**: the selector applies its own whale-compression at election time, so exact agreement is not expected |

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
| `Foglio di configurazione` | α/κ/λ (with λ also shown as **Peso % Reso** in the sheet's own units) and the allocation basis; the **Vers_2 range grid** verbatim — one row per ClusterMiner and per AZIENDE-of-a-cluster × Score min/max ESG and Numero min/max Tx; per ClusterMiner **Score ESG, Certificato ISO, Peso %, Reso**; the 10 **AZIENDE** of each cluster with their ESG scores |
| `Epoch N` (one per epoch) | per azienda **Nome utente / Tx Utente / Impatto utente / Score ESG**; after each group of 10 the cluster row **Tx Miner / Impatto Cluster / Delay in msec / Guadagno Ex (€) / € Resi in Ex / Giacenza / % Reso / Total GAIN**, then the engine cross-check block (**Peso engine `w_k` / Prob. selezione / `w_k` atteso / `w_k` atteso (int) / Match**); epoch totals and an ESG/ISO recap close the sheet |
| `Riepilogo` | per-epoch row with the two self-checking columns **Somma Delay (=1000)** and **α×Θ vs Σ Guadagno** (highlighted red if they disagree), plus per-cluster run totals including blocks proposed and the `w_k` match tally |
| `Pesi & Probabilita` | epoch × cluster grid of published weights and selection probabilities |
| `Proposer log (wpoa)` | verbatim `wpoa_proposer_log.csv` (wpoa mode only) |
| `Verifiche` | both invariant levels: every run-level check, then the per-epoch tally with only the **failures** listed in full |

Every economic figure in the workbook is **read from the chain** by the harness and
merely formatted here; totals rows are real `SUM()` formulas over the actual cell
ranges, so the sheet is auditable. The configuration sheet reads its parameters from
`experiment.log`, not from the reporter's environment, so a report generated in a
different shell cannot print defaults next to overridden data.

`W_k`, `w_k` and `A_k` never leave the node, so they appear as the harness's replay of
the pipeline beside the engine's published `w_k`, with a `Match` verdict per cell. Since
`τ` is reconstructed exactly and summed in **ascending address order** — the order
`WeightEngine::RawWeight` uses, deliberately, so the non-associative floating-point
total is node-independent — the comparison is **by value**, not by ranking.

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
