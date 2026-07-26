# WeightEngine experimental simulation — what it does, how it works, what it returns

This is the design companion to the code in
[`src/weight_engine/test/experimental/`](../). It explains the experiment end to
end: the **MyLedger** network it drives, the two consensus regimes it can run, the
exact steps of a run, the artifacts it produces, and the non-obvious mechanisms (and
the consensus-timing pitfalls) that make it work.

It is an **experimental, offline-analysis harness**, *not* a pass/fail functional
test — though it now closes every run with an invariant pass (§5). The pass/fail
check for the publish side is
[`../functional_test_weight_engine.sh`](../functional_test_weight_engine.sh); the
system-level wPoA check is
[`../../../wpoa/test/functional_test_wpoa_system.sh`](../../../wpoa/test/functional_test_wpoa_system.sh).

**Cardinal rule:** it never re-implements the weight math *for consensus*. The
[`WeightEngine`](../../../weight_engine.h) computes `w_k` on the nodes; the harness
*publishes the public inputs* through the sanctioned admin RPCs and *reads back* the
results. A Python mirror of the pipeline exists in
[`economics.py`](../helpers/economics.py) for **display and cross-check only** and is
never fed back to the chain (§4.7).

---

## 0. What changed from the original (Apuana SB) suite

| | Before | Now |
|---|---|---|
| Topology | 4 miners × 5 companies (`M1..M4`, `COMPANY_Mx_Cy`) | **MyLedger**: 5 cluster miners `ClusterMinerA..E` × 10 aziende (`Azienda_A1..E10`), 50 total |
| ADMIN | governance writer only | governance writer **and** reconciliation counterparty (the Apuana SB stand-in) |
| ESG | 2 decimals over `[1, 100]` | **integers over `[10, 20]`** (the MyLedger configuration sheet) |
| Currency | anonymous "activity asset" | **GAS**, a divisible asset with `1 GAS = 1 EUR` |
| Fees / earnings | none | every transaction costs **α = 0.2 GAS**; `Guadagno_k = TxMiner_k · α` is settled on chain |
| Reconciliation | a random `R_k ∈ [0,5]` published to the stream, with **no on-chain counterpart** | the miner **actually transfers** `Resi_k` GAS to the ADMIN address; the amount is **read back off chain** and that is what gets published |
| `Giacenza` | recomputed `B_k` from the thesis formulas | the miner's **real on-chain GAS balance** after the reconciliation confirmed |
| `Tx Miner` | the miner's own signed transactions | transactions the miner **validated** (blocks it proposed, coinbase excluded) |
| `Delay` | modelled as `share × 1000` | **measured**: mean inter-block interval of the blocks the cluster proposed |
| Volume | a handful of transfers network-wide per epoch | **10–20 per azienda per epoch** → `Θ ≈ 750` |
| Transport | one `multichain-cli` process per RPC | **JSON-RPC over a persistent HTTP connection**, CLI as automatic fallback |
| Report | recomputed every figure from the formulas | formats **chain-read** figures; the recomputed `W_k`/`A_k` remain only as cross-check columns |
| Invariants | none | 8 checks written to `assertions.csv` (§5) |

---

## 1. The scenario

A single local MultiChain network of **1 ADMIN + 5 cluster-miner nodes**, run for a
configurable number of **epochs** (default 30).

| Actor | Count | On-chain identity | Role |
|---|---|---|---|
| **ADMIN** | 1 (node 0) | genesis / global administrator | the **Apuana SB stand-in**: publishes ESG + membership + reconciliation, issues and distributes GAS, and **receives** every reconciliation transfer. **Not a miner** (its `mine` permission is revoked once the miner set is live) |
| **cluster miner** `ClusterMinerA..E` | 5 | one mining node each | the wPoA validators; the engine computes and publishes each one's `w_k`; each earns `Guadagno` for the transactions it validates |
| **azienda** `Azienda_X1..X10` | 10 per cluster → 50 | a plain address **in the ADMIN wallet** | belongs to a cluster; sends 10–20 GAS transfers per epoch, generating activity `τ` |
| **FEEPOOL** | 1 | a plain address in the ADMIN wallet | the aggregate of all transaction senders when fees are settled (§6.6) |

The ADMIN owns the azienda keys so it can both *sign* their transactions and publish
their governance data; miners sign their own transactions on their own node.

The inputs the [`WeightEngine`](../../../weight_engine.h) consumes map onto the actors
exactly as the thesis defines them:

```
c_i   = ESG_i · τ_i / κ                          (company contribution = "Impatto utente")
W_k   = ESG_{Mk} · ( τ_{Mk} + Σ_{i∈C_k} c_i )    (raw cluster weight)
A_k   = α · Θ · W_k / W_tot                       (allocation)
ρ_k   = R_k / (A_k + B_{k-1})                     (compliance, from reconciliation R_k)
w_k^(1) = W_k ;  w_k^(e) = W_k · [ρ_{k,e-1}·λ + (1-λ)]   (final weight)
```

so the harness must supply **ESG for every miner AND every azienda** (an uncertified
miner has `W_k = 0`, floored to 1, which would flatten the experiment),
**membership**, **reconciliation** `R_k` per epoch, and enough on-chain **activity**
that `τ` is non-zero. Activity is *not* a stream — the engine derives `τ` directly
from the confirmed blocks of the epoch
([`weight_reader.cpp::ComputeActivityForEpoch`](../../../weight_reader.cpp)) — so the
harness produces it by making the aziende transact.

### 1.1 Where α sits, and why the weight does not depend on it directly

`α = 0.2` is **both** the engine's allocation constant and the MyLedger cost of one
transaction in GAS. One symbol, one value — which is what keeps the two views
reconcilable. But α is **not a term of the weight**:

* `W_k` is built purely from ESG and activity. No α.
* α reaches the weight only along `A_k → ρ_k → w_k^{(e+1)}`, i.e. through the
  allocation and the compliance feedback, one epoch later.

So the weight is a function of **{ESG, activity (NumTx), and the reconciliation
feedback}**. `Giacenza` enters it the same indirect way: the reconciled amount and the
carried residual `B_k` set the denominator of `ρ_k`.

### 1.2 Two definitions of "earnings", and how they relate

| | Definition | Distributed by |
|---|---|---|
| `Guadagno_k` (MyLedger) | `TxMiner_k · α` | actual validation work |
| `A_k` (thesis / engine) | `α · Θ · W_k / W_tot` | weight share |

Every transaction is validated by exactly one cluster, so the `TxMiner` tallies
partition the epoch's transactions — which is the invariant `tx_validated_once` checks
against an independent recount off the block index (§5). Summing:

```
Σ_k Guadagno_k  =  α · (validated transactions)
Σ_k A_k         =  α · Θ                          (since Σ_k W_k / W_tot = 1)
```

**These are close but not equal, and the difference is real.** `Θ` counts only *azienda
activity*, whereas a block carries more than that: the miner↔miner transfers, the fee
settlements, the reconciliation transfers, the reconciliation stream records and each
miner's own `wpoa-weights` publish are all validated too, and all earn α. So

```
Σ_k Guadagno_k  =  α · (Θ + settlement/governance overhead)   ≈  1.03 · α · Θ
```

at the default volumes (~22 overhead transactions per epoch against `Θ ≈ 750`). The
run reports both figures and the overhead percentage rather than asserting a false
equality — an earlier version of this harness *did* assert `Σ Guadagno = α·Θ` and it is
simply wrong. What is asserted is the definitional identity
`Σ Guadagno = α · validated` plus the partition check above.

Distribution is where the two differ interestingly: `Guadagno` follows blocks mined,
`A_k` follows weight share, and in `wpoa` mode the block distribution tracks the weight
share, so they converge per cluster. The report shows both.

---

## 2. The two modes (mandatory `--mode`)

The harness runs **exactly one** mode per invocation and never both. The mode only
changes the node launch flags ([`config.node_args`](../config.py)); everything else is
identical.

| `--mode` | Node flags | Proposer selection | `wpoa-weights` |
|---|---|---|---|
| `wpoa`   | `-enablewpoa=1 -enableweightengine=1 …` | **weighted** — the engine's `w_k` drives probabilistic wPoA selection | computed **and** governs selection |
| `native` | `-enablewpoaweights=1 -enableweightengine=1 …` | native **round-robin** (master switch off) | computed and published, but **not** used for selection |

`native` is the control: the engine still computes and publishes `w_k`, so you can
compare "who *would* have proposed under wPoA (the weight favourite)" against "who
actually proposed under round-robin". That comparison is written to `experiment.log`
per epoch. It also matters economically: because `Guadagno` follows blocks mined,
`native` spreads it evenly while `wpoa` concentrates it on the high-weight clusters —
visible in the `Riepilogo` sheet's per-cluster totals.

---

## 3. Anatomy of a run

Driver: [`experimental_test.py`](../experimental_test.py), class `Experiment`.

### 3.1 Setup — [`chain_setup.py`](../helpers/chain_setup.py)

Ports the permissioned-bootstrap protocol proven in
[`functional_lib.sh`](../../../wpoa/test/functional_lib.sh): create the chain, start
node 0 (seed/ADMIN), then for each miner *launch → grant `connect,send,receive,mine` +
`wpoa-weights.write` → relaunch to join*. `params.dat` is tuned (fast blocks; a long
setup phase — see §6.1; `mine-empty-rounds` high so it keeps mining).

Immediately after bootstrap, `ensure_miners_can_mine()` **re-grants and confirms**
`mine` on every miner (see §6.2 for why this is not redundant).

`Node` speaks **JSON-RPC over a persistent HTTP connection** (credentials read from
`<datadir>/<chain>/multichain.conf`), falling back to `multichain-cli` whenever the
socket or the credentials are unavailable — see §6.7. `cli` / `cli_ok` keep their old
signatures, so every caller is unchanged; the one new rule is that arguments are
passed as **native Python values** (`True`, `0.2`, `1`) because the CLI's
`RPCConvertValues` no longer runs.

### 3.2 Publish the static inputs — [`stream_writer.py`](../helpers/stream_writer.py)

All via the ADMIN, through the schema-validating RPCs (never raw `publishfrom`):

1. `ensure_write_permission()` — grant the ADMIN `.write` on the three closed input
   streams **and wait for confirmation** (an unconfirmed write permission makes
   `publishfrom` silently fail).
2. `weightsetesg` — a certified, static integer ESG score in `[10, 20]` for all 55
   cluster addresses (5 miners + 50 aziende), generated by
   [`esg_generator.py`](../helpers/esg_generator.py) from `WE_SEED`. ADMIN and FEEPOOL
   are deliberately **unscored**: they are not cluster members and must never enter a
   weight.
3. `weightsetmembership` — one call per azienda, mapping it to its cluster.
4. Fund participants — [`tx_simulator.py`](../helpers/tx_simulator.py) issues GAS to
   the ADMIN and sends each participant a starting balance; the FEEPOOL gets enough to
   settle every epoch's fees (`config.feepool_fund()`).
5. `ensure_wpoa_weights_stream()` — the ADMIN **creates** the open `wpoa-weights`
   output stream and subscribes to it (see §6.3).
6. `demote_admin_from_mining()` — revoke the ADMIN's `mine`, so it never proposes.

### 3.3 Warm-up

`wait_all_miners_weighted()` blocks until every miner appears in `getallweights`,
i.e. each has computed and published a first `w_k`. This guarantees wPoA selection
has a weight map before sampling begins.

### 3.4 Epoch loop

Sampled epochs are the `NUM_EPOCHS` epochs **after** the current tip (and, in `wpoa`
mode, after the setup phase — §6.1). For each epoch `e`:

1. `wait_height(start(e))` — wait until the tip enters epoch `e`'s block range.
2. `generate_epoch_txs(e)` — every azienda sends `WE_TX_MIN..WE_TX_MAX` (10–20) GAS
   transfers to other aziende, plus a couple of miner↔miner transfers so `τ_{Mk}` is
   not degenerate. Each `sendassetfrom` spends a UTXO owned by the sender, so the
   engine counts one `τ` for that sender in the confirming block's epoch.
3. `wait_height(end(e)+1)` — let the epoch's blocks mine. **Nothing economic can be
   computed before this point**: `TxMiner` is not defined until the epoch's blocks exist.
4. `close_epoch(e)` — [`economics.py`](../helpers/economics.py) runs the whole
   settlement automatically (§3.5).

Then it drives `STABILITY_MARGIN + 2` blocks past the last epoch's end so every
sampled epoch **buries** and its `w_k` gets published (§6.4).

### 3.5 The automated reconciliation engine — [`economics.py`](../helpers/economics.py)

`close_epoch(e)`, once per epoch, with **no manual step anywhere**:

1. **Read the blocks** (`listblocks`, one call per chunk) → per cluster:
   `blocks_mined`, `TxMiner` (Σ `txcount − 1`, dropping each coinbase) and
   `Delay in msec` (mean interval between the blocks it proposed and their parents).
2. **Read the transactions** (`getblock`) → per azienda `Tx utente` (= the engine's
   `τ_i`) and `Impatto utente = τ_i · ESG_i / κ`; per cluster
   `Impatto Cluster = Σ Impatto utente`.
3. **Settle the fees on chain**: `Guadagno_k = TxMiner_k · α` is transferred
   FEEPOOL → miner.
4. **Reconcile on chain**: the miner's own node signs a transfer of
   `Resi_k = Guadagno_k · reso_rate_k` to the ADMIN address. `reso_rate_k` is the
   per-cluster **Reso** column of the configuration sheet (`WE_RESO_RATES`, default
   `1.00 / 0.90 / 0.75 / 0.60 / 0.40`) with a small seeded jitter, clamped so
   `Resi ∈ [0, Guadagno]` — which is why `% Reso` can never leave `[0, 100]`.
5. **Read the amount back off chain**: the reconciliation transaction is re-read
   (`getrawtransaction … 1`) and the GAS quantity of the vout paying the ADMIN address
   is the authoritative `Resi` — never the amount we asked the node to send.
6. **Read `Giacenza`**: after the reconciliation *confirms*, the miner's on-chain GAS
   balance (`getaddressbalances`, minconf 1) read on the miner's own node.
7. **Publish** `weightsetreconciliation(miner, Resi_from_chain, e)`, so the engine's
   `ρ_k` is driven by GAS that actually moved.

`Total GAIN_k` is the running sum of `Guadagno_k`, so it is monotonic by construction
— which §5 asserts.

**Why publishing `R_k` after the epoch is safe.** `R_k^{(e)}` feeds `ρ_k^{(e)}`, which
the weight formula consumes one epoch later (`w_k^{(e+1)}`). And
`ComputeLocalWeightForEpoch` re-reads the whole reconciliation stream and **replays
from epoch 1** on every publish. So `R_k^{(e)}` only has to be confirmed before epoch
`e+1` buries — a full epoch plus margin of slack, not the few blocks it might appear
to need.

### 3.6 Harvest + report — [`weight_reader.py`](../helpers/weight_reader.py) + [`reporters/`](../reporters/)

- Per-epoch weights come from the miners' `debug.log` lines
  `[WeightEngine] epoch E (height H): w_k = W for ADDR` — the authoritative,
  epoch-tagged value each miner published.
- The block/txid index is built **incrementally**, one epoch at a time, by
  `economics.extend_index` — so the harvest reuses it instead of rescanning the chain.
- The artifacts (§4) are written, the invariants checked (§5), and the network is
  always torn down in `finally`.

---

## 4. What it returns (`output/`, recreated each run)

### 4.1 `config_sheet.csv` — one row per cluster (the static configuration)
```
cluster, letter, esg_cluster, iso_certificate, reso_rate_nominal,
companies, esg_companies
```
`companies` / `esg_companies` are `;`-joined lists. This is what
`make_report.py` turns into the **Foglio di configurazione**.

### 4.2 `cluster_economics.csv` — one row per (epoch × cluster) — **the MyLedger core**
```
epoch, cluster, letter, esg, iso,
blocks_mined, tx_miner, tau_miner_signed, impatto_cluster, delay_ms,
guadagno, resi, resi_target, resi_requested, giacenza, pct_reso,
reso_rate_nominal, total_gain,
engine_weight, engine_prob, selected_proposer,
raw_weight_recomputed, allocation_recomputed,
fee_txid, recon_txid, recon_stream_txid
```
Everything left of `engine_weight` is read or settled on chain. `resi_target` is what
the Reso rate asked for, `resi_requested` what the node was told to send (clamped to
the available balance) and `resi` what the chain says arrived — normally all three are
equal, and any divergence is a logged warning worth reading.

### 4.3 `company_activity.csv` — one row per (epoch × azienda)
```
epoch, cluster, company, display, tx_utente, esg, impatto_utente
```

### 4.4 `epochs_summary.csv` — one row per epoch
```
epoch, mode, block_height, proposer_miner, proposer_method,
weight_<cluster>… , prob_<cluster>… , tx_count, theta, reconciliation_done, timestamp
```
The per-cluster columns are **derived from `config.NUM_MINERS`**, so changing the
cluster count no longer leaves stale `M1..M4` headers. `proposer_miner` is the
**modal** proposer of the epoch; `theta` is the epoch's total azienda activity.

### 4.5 `esg_scores.csv`, `transactions.csv`, `weights_evolution.csv`, `wpoa_proposer_log.csv`
As before, with `type ∈ {funding, company, miner, fee_settlement, reconciliation}` in
`transactions.csv` and `amount_gas` in place of the old `amount`. A transaction's
`epoch` is the epoch of its **confirming block**.

### 4.6 `assertions.csv` + `experiment.log`
The invariant verdicts (§5), and the levelled trace with the run header, the
per-epoch settlement lines, and a final summary (Θ, Guadagno, Resi, Total GAIN per
cluster, blocks by miner, `http/cli` call counts, final `getallweights`).

### 4.7 The `report.xlsx` workbook — [`make_report.py`](../make_report.py)

| Sheet | Content |
|---|---|
| `Foglio di configurazione` | Score min/max ESG, Numero min/max Tx, α/κ/λ, and per ClusterMiner its **Score ESG, Certificato ISO, Peso %, Reso** — plus the 10 **AZIENDE** of each cluster with their ESG scores |
| `Epoch N` (one per epoch) | per azienda **Nome utente \| Tx Utente \| Impatto utente \| Score ESG**; after each group of 10, the cluster row **Tx Miner \| Impatto Cluster \| Delay in msec \| Guadagno Ex (€) \| € Resi in Ex \| Giacenza \| % Reso \| Total GAIN**, then the engine cross-check block (`w_k`, selection probability, recomputed `W_k` and `A_k`, proposer flag); epoch totals and an ESG/ISO recap close the sheet |
| `Riepilogo` | one row per epoch (Tot Tx, Tot Impatto, GAS distributed, GAS returned, mean % Reso) + per-cluster run totals |
| `Pesi & Probabilita` | epoch × cluster grid of published weights and selection probabilities |
| `Proposer log (wpoa)` | verbatim `wpoa_proposer_log.csv` (wpoa mode only) |
| `Verifiche` | the invariant checks, green/red |

The totals rows are real Excel `SUM()` formulas over the actual cell ranges, so the
sheet is auditable rather than a set of opaque numbers.

**The cross-check columns.** `W_k` and `A_k` never leave the node, so the report shows
a Python replay of the pipeline beside the engine's published `w_k`. One deliberate
imprecision: the replay's `τ_{Mk}` counts the transactions the harness *recorded* a
miner signing, while the engine additionally counts the miner's own `wpoa-weights`
publish — roughly one more per epoch, identically for every miner. So the two are
compared by **ranking**, not by value, and `τ_{Mk}` is in any case the small term of
`W_k` next to the cluster's `Impatto`.

---

## 5. The invariant pass (`assertions.csv`)

Run at the end of every run. A failure is logged as `ERROR` and recorded, but never
aborts — the artifacts are always complete.

| Check | What it asserts |
|---|---|
| `weight_ranking` | the engine's weight ordering agrees with the **ESG + activity composite** ordering, measured as mean pairwise concordance across epochs ≥ `WE_RANK_MIN` (default 0.80). Below 1.0 on purpose: the feedback factor `ρλ + (1−λ)` legitimately reorders clusters whose raw weights are close. The concordance against the full replay of `W_k` is reported alongside |
| `conformity_rate_range` | `% Reso ∈ [0, 100]` for every (epoch × cluster) |
| `total_gain_monotonic` | cumulative `Total GAIN` never decreases, per cluster |
| `tx_validated_once` | the per-cluster `TxMiner` tallies add up to an independent recount of every non-coinbase transaction in the sampled epochs' blocks, and no block lacks a cluster-miner proposer |
| `gas_fees_match_validation` | `Σ Guadagno = α · (validated transactions)`. The detail line also reports `α·Θ` and what percentage of the validated traffic is settlement/governance overhead — see §1.2 |
| `gas_returned_to_admin` | the ADMIN's **on-chain balance increase** equals `Σ Resi` read off chain |
| `gas_supply_conserved` | the sum of every participant's balance equals the issued GAS supply |
| `feepool_paid_out` | the FEEPOOL's balance decrease equals `Σ Guadagno` |

The last five are pure chain reads, so they check the ledger, not the bookkeeping.

---

## 6. Non-obvious mechanisms (and the pitfalls they solve)

### 6.1 The setup phase must outlast the warm-up (wpoa deadlock)
While the native setup phase (`setup-first-blocks`) lasts, mining is round-robin —
which is what lets the ADMIN publish inputs and the miners establish a first weight.
The instant it ends, weighted selection governs; if **no weight exists yet, no miner
qualifies and the chain deadlocks.** So `SETUP_FIRST_BLOCKS` (default 60 — raised from
40 because 55 addresses now need ESG + membership + funding) is sized to comfortably
outlast bootstrap + publish + first-weight, and in `wpoa` mode the harness waits until
the tip is past the setup phase before sampling. Native mode is indifferent.

### 6.2 Confirm `mine` before wPoA governs (mining-key race)
Bootstrap grants can still be **unconfirmed** when wPoA takes over. An elected miner
whose `mine` permission has not confirmed reports *"no local mining key"* and cannot
propose — and since wPoA elects exactly one proposer per height, the chain stalls
until (or unless) that grant confirms. `ensure_miners_can_mine()` re-grants and waits
for confirmation on the exact address the engine keys the weight by.

### 6.3 Someone must create `wpoa-weights`
The registry creates the (open) `wpoa-weights` stream lazily — but only a
create-permitted node can, and in a normal wPoA deployment that node is a validating
genesis. Here the ADMIN is deliberately **not** a cluster miner, so its engine never
reaches the create step, and the miners lack create permission. The ADMIN therefore
creates it explicitly (open, exactly as the registry would) and subscribes so
`getallweights` — queried on the ADMIN — can see the miners' published weights.

### 6.4 Weights lag the tip (buried epochs)
The engine publishes `w_k` only for the newest **buried** epoch
(`(tip − STABILITY_MARGIN + 1) / len`), folding forward from epoch 1, because `τ` is
derived from block/undo data and a shallow reorg near the tip must not change it. The
harness drives `STABILITY_MARGIN + 2` blocks past the last sampled epoch before
harvesting. That same replay-from-epoch-1 behaviour is what makes the post-epoch
reconciliation publish safe (§3.5).

### 6.5 No native currency → GAS is an issued asset
A default MultiChain has `initial-block-reward = 0`, so there is no spendable native
currency. GAS is therefore a purpose-issued **divisible** asset (`WE_ASSET_UNITS`,
default `0.0001`) with `1 unit = 1 EUR`, so `α = 0.2` and every Reso fraction are
exact. Each `sendassetfrom` is a transaction whose signed input the engine's undo-data
metric counts as one `τ` for the sender — exactly the thesis definition of activity.
Nothing in the model depends on the asset-versus-native choice; only the word "native"
does.

### 6.6 Why a FEEPOOL instead of charging each sender
Each network transaction costs α, paid to the validating miner. Deducting 0.2 GAS in a
separate transaction from every one of ~750 senders per epoch would roughly double the
run's transaction count for no modelling gain, so one FEEPOOL address stands in for
the aggregate and pays each miner its whole epoch fee income in a single transfer. The
GAS totals are identical; only the number of transactions differs. The FEEPOOL is not
a cluster member, so its `τ` never enters a weight, and paying *into* a miner adds no
`τ` to the miner either (`τ` counts signed inputs, not credits).

### 6.7 Why the transport changed
The MyLedger topology issues ~50 aziende × 10–20 transfers × 30 epochs ≈ 22 000
transactions, plus a `getblock` per block. At roughly 100 ms per `multichain-cli`
process spawn that alone would take the better part of an hour and dominate the whole
experiment; over a persistent HTTP connection the same call costs single-digit
milliseconds. The CLI remains the automatic fallback (and the summary line reports the
`http / cli` split, so a silent fallback to the slow path is visible).

### 6.8 Two `τ`, on purpose
`epoch_activity` (the MyLedger business view) counts only network traffic;
`engine_tau` (the replay input) additionally counts a miner's reconciliation transfer,
because the engine counts every transaction a member signs. Mixing them up would
either inflate `Tx utente` or understate `W_k`.

---

## 7. Determinism & error handling

Every random choice (ESG scores, transaction picks, Reso jitter) derives from
`WE_SEED` (default 42), so a run is reproducible: the same seed yields the same ESG
assignment and trade pattern regardless of node timing. A failed RPC is logged to
`experiment.log` and the run continues; `cli_ok` never raises, not even when the CLI
binary itself is unusable; the network is torn down on every exit path.

---

## 8. File map

```
experimental/
├── experimental_test.py      orchestrator (Experiment): run phases, CSVs, invariants
├── make_report.py            Vers_2 / POESIA .xlsx report from the CSVs (needs openpyxl)
├── config.py                 seed, MyLedger topology, GAS/α, epoch geometry, all WE_* knobs
├── run_experiment.sh         wrapper around experimental_test.py
├── helpers/
│   ├── chain_setup.py        Network/Node: JSON-RPC transport, bootstrap, grants, waits, teardown
│   ├── participants.py       label ⇄ address ⇄ owning-node registry (+ ADMIN, FEEPOOL)
│   ├── esg_generator.py      seeded static integer ESG + the configuration-sheet view
│   ├── stream_writer.py      ADMIN → esg / membership / reconciliation (validating RPCs)
│   ├── tx_simulator.py       GAS issue/fund + per-epoch transfers (activity τ)
│   ├── economics.py          the MyLedger economics + automated on-chain reconciliation
│   │                         (+ the display-only Python mirror of the weight pipeline)
│   └── weight_reader.py      getallweights + debug.log weight parse + block/proposer index
├── reporters/
│   ├── csv_reporter.py       the CSV writers (+ output reset)
│   └── log_reporter.py       levelled experiment.log
└── output/                   generated each run (git-ignored)
```

Module names use `_` (not the hyphens of the original spec sketch) so they are
importable Python modules; `participants.py` and `economics.py` are added helpers the
writers share.

---

## 9. Running it

```bash
# build the node first: ./autogen.sh && ./configure && make
./run_experiment.sh --mode=wpoa
./run_experiment.sh --mode=native

# then the workbook
pip install --user openpyxl
python3 make_report.py

# a fast smoke run (minutes, not tens of minutes)
WE_EPOCHS=4 WE_EPOCH_LENGTH=6 WE_TX_MIN=2 WE_TX_MAX=4 WE_SETUP_BLOCKS=30 \
  ./run_experiment.sh --mode=native
```

**Expected duration of a default run.** 30 epochs × 10 blocks × 2 s ≈ 10 minutes of
chain time, plus setup and burial — call it 12–18 minutes. The dominant costs are the
block cadence (not the RPC traffic, since §6.7) and the engine's own
replay-from-epoch-1 at each epoch boundary, which grows quadratically in the epoch
index. If you raise `WE_EPOCHS` or the transaction volume a lot, expect that replay to
become the limiting factor.
