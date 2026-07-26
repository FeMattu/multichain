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
results. A Python replay of the pipeline lives in
[`economics.py`](../helpers/economics.py) for **cross-check and reporting only** and is
never fed back to the chain — it is what the engine's published `w_k` is measured
against (§4.7).

---

## 0. What changed from the original (Apuana SB) suite

| | Before | Now |
|---|---|---|
| Topology | 4 miners × 5 companies (`M1..M4`, `COMPANY_Mx_Cy`) | **MyLedger**: 5 cluster miners `ClusterMinerA..E` × 10 aziende (`Azienda_A1..E10`), 50 total |
| ADMIN | governance writer only | governance writer **and** reconciliation counterparty (the Apuana SB stand-in) |
| ESG | 2 decimals over `[1, 100]` | **integers over `[10, 20]`** (the MyLedger configuration sheet) |
| Currency | anonymous "activity asset" | **GAS**, a divisible asset with `1 GAS = 1 EUR` |
| Fees / earnings | none | every transaction costs **α = 0.2 GAS**; the epoch's pot `α·Θ` is split by **weight share** `p_k` and settled on chain |
| Reconciliation | a random `R_k ∈ [0,5]` published to the stream, with **no on-chain counterpart** | the miner **actually transfers** `R_k` GAS to the ADMIN address; the amount is **read back off chain** and that is what gets published |
| `Giacenza` | recomputed `B_k` from the thesis formulas | the accounting balance `B_k^(e-1) + A_k − R_k`, **reconciled against** the miner's on-chain balance net of its trading (`giacenza_matches_chain`) |
| `Tx Miner` | the miner's own signed transactions | `τ_Mk`, the miner's own signed transactions — **10–20 per epoch**, the same band as the aziende |
| `Delay` | modelled as `share × 1000` | the **per-mille normalized weight** (Vers_2's own meaning), total exactly 1000. The measured inter-block interval is a separate `block_interval_ms` column |
| Volume | a handful of transfers network-wide per epoch | **10–20 per azienda AND per miner per epoch** → `Θ ≈ 750` |
| Membership | assumed from the local topology | **read back off the membership stream** with the engine's own `jsonobjectmerge` |
| `τ` | approximated from harness records | **reconstructed exactly**, harness records + the `wpoa-weights` publisher index, with coverage asserted |
| Engine check | ranking only (`τ_Mk` was known to be short) | **by value**: the replayed `w_k` vs the published integer, per cell |
| Transport | one `multichain-cli` process per RPC | **JSON-RPC over a persistent HTTP connection**, CLI as automatic fallback |
| Report | recomputed every figure from the formulas | formats **chain-read** figures; the replayed `w_k` remains as the engine cross-check |
| Invariants | none | **5 per epoch** (`epoch_checks.csv`) + **12 run-level** (`assertions.csv`), §5 |

### 0.1 Corrections applied in this revision

The first MyLedger revision of this harness derived the economics from **block
proposership**. That is not the model, and four columns were wrong as a result:

| Column | Was | Is |
|---|---|---|
| `Guadagno` | `TxMiner_k · α` — the fees of the blocks *k* mined | `A_k = Θ · p_k · α` — the epoch pot split by weight share. Proposership does not enter it |
| `Giacenza` | the raw on-chain balance (so it also carried the 1000 GAS seed funding and the miner↔miner trading) | `B_k = B_k^(e-1) + A_k − R_k`, `B^(0) = 0` |
| `% Reso` | `R_k / A_k` | `R_k / (A_k + B_k^(e-1))` |
| `Impatto Cluster` | `Σ_i c_i` only — `ESG_Mk` and `τ_Mk` were missing | `ESG_Mk · (τ_Mk + Σ_i c_i)` = `W_k` |
| `Delay` | the measured mean inter-block interval | `W_k / W_tot · 1000` |

One consequence is worth stating plainly: `Σ_k Guadagno_k = α·Θ` is now an **equality the
ledger satisfies**. Under the old per-block form it could not be, because settlement,
reconciliation and governance transactions are validated and would have earned α too
while `Θ` counts only azienda activity — an earlier version of this document asserted
that equality anyway, and it was simply wrong.

---

## 1. The scenario

A single local MultiChain network of **1 ADMIN + 5 cluster-miner nodes**, run for a
configurable number of **epochs** (default 30).

| Actor | Count | On-chain identity | Role |
|---|---|---|---|
| **ADMIN** | 1 (node 0) | genesis / global administrator | the **Apuana SB stand-in**: publishes ESG + membership + reconciliation, issues and distributes GAS, and **receives** every reconciliation transfer. **Not a miner** (its `mine` permission is revoked once the miner set is live) |
| **cluster miner** `ClusterMinerA..E` | 5 | one mining node each | the wPoA validators; the engine computes and publishes each one's `w_k`; each earns `Guadagno = A_k` in proportion to its **weight share**, and sends 10–20 transfers of its own per epoch (`τ_Mk`) |
| **azienda** `Azienda_X1..X10` | 10 per cluster → 50 | a plain address **in the ADMIN wallet** | belongs to a cluster **as recorded on the membership stream**; sends 10–20 GAS transfers per epoch, generating activity `τ_i` and hence `Θ` |
| **FEEPOOL** | 1 | a plain address in the ADMIN wallet | the aggregate of all transaction senders; pays out each epoch's `α·Θ` pot (§3.5 step 4, §6.6) |

The ADMIN owns the azienda keys so it can both *sign* their transactions and publish
their governance data; miners sign their own transactions on their own node.

The inputs the [`WeightEngine`](../../../weight_engine.h) consumes map onto the actors
exactly as the thesis defines them:

```
c_i   = ESG_i · τ_i / κ                          (company contribution = "Impatto utente")
W_k   = ESG_{Mk} · ( τ_{Mk} + Σ_{i∈C_k} c_i )    (raw cluster weight)
A_k   = α · Θ · W_k / W_tot                       (allocation — see §1.2 on the basis)
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

### 1.2 The one place the spreadsheet and the C++ core provably disagree

`Guadagno` is the allocation `A_k`, and there is exactly one open question about it:
**proportional to which weight?**

| | Definition | Basis |
|---|---|---|
| thesis / `weight_engine.h` | `A_k = α · Θ · W_k / W_tot` | the **raw** weight `W_k` |
| Vers_2 spreadsheet | `A_k = α · Θ · w_k / w_tot` | the **feedback-adjusted** `w_k` (its `ImpCluster`/`Delay`) |

Both give `Σ_k A_k = α·Θ` (the shares sum to 1 either way), and they coincide in epoch 1
— where every `ρ^(0)` is 0, so the bracket `[ρ·λ + (1−λ)]` is the same `1−λ` for
everyone and cancels in the normalization. From epoch 2 on they can diverge: the
spreadsheet feeds the compliance feedback into the allocation as well as into the
weight, the thesis deliberately does not (`weight_engine.h` lines 28–35 documents this
choice: allocation tracks certified+current merit, avoiding a feedback-of-feedback loop).

The harness **always computes both** and reports them as `delay_raw` / `delay_final`.
`WE_ALLOC_BASIS` decides only which one is actually settled on chain, and defaults to
`raw` — because settling what the node computes is what makes the engine's own `B_k` and
`ρ_k` verifiable against the ledger at all. `WE_ALLOC_BASIS=final` reproduces the
spreadsheet instead, which is the natural sensitivity run for the thesis.

### 1.3 A discrepancy in the reference PDF worth flagging

Every documented formula reproduces the printed Vers_2 **epoch-1** figures to the cent,
and the epoch-2 carry-forward columns (`Giacenza` 21.24, `% Reso` 56.30 %, `Total GAIN`
73.49) follow exactly from `B_prev + A − R` and `R/(A + B_prev)`.

The epoch-2 **`ImpCluster`** does not. For cluster A the sheet prints 918, while
`ESG_Mk · (τ_Mk + Σ_i ImpUtente_i) = 19 · (18 + 20.20) = 725.8` and the documented
bracket `[0.7203·0.5 + 0.5] = 0.860` gives 624 — the sheet's implied factor is 1.265,
outside the `[1−λ, 1]` range the bracket can produce at all. Solving the factor for all
five clusters shows it is not a function of `%Reso_(e-1)` alone (A and E have
`%Reso` 0.7203 and 0.7214 but factors 1.265 and 1.137).

This is either an extraction artifact of the printed PDF or an approximation in the
formula as documented. It does not affect this harness, which implements the bracket as
`weight_engine.h` and the analysis report both state it — and, more to the point,
**measures** whether the deployed engine agrees (`engine_matches_replay`). If the
`.ods` is available, comparing its epoch-2 `ImpCluster` cell formula directly would
settle it.

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
per epoch.

The **economics are identical in both modes** — `Guadagno` follows weight share, not
proposership, so the mode changes nothing about it. What the mode isolates is the
consensus half: in `wpoa` the observed block distribution should track `p_k`
(`proposer_share_tracks_p_k`, reported not thresholded — the selector applies its own
whale-compression at election time), in `native` it is round-robin by construction.
`native` is therefore also the cleaner setting in which to verify
`engine_matches_replay`, since weighted selection is out of the loop entirely.

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
   transfers to other aziende, and **every cluster miner sends
   `WE_TX_MINER_MIN..WE_TX_MINER_MAX` (10–20) of its own**, which is `τ_{Mk}`. Each
   `sendassetfrom` spends a UTXO owned by the sender, so the engine counts one `τ` for
   that sender in the confirming block's epoch.
3. `wait_height(end(e)+1)` — let the epoch's blocks mine. **Nothing can be computed
   before this point**: `τ` is defined over the epoch's confirmed blocks.
4. `close_epoch(e)` — [`economics.py`](../helpers/economics.py) runs the whole
   settlement automatically (§3.5).

Then it drives `STABILITY_MARGIN + 2` blocks past the last epoch's end so every
sampled epoch **buries** and its `w_k` gets published (§6.4).

### 3.5 The automated reconciliation engine — [`economics.py`](../helpers/economics.py)

`close_epoch(e)`, once per epoch, with **no manual step anywhere**:

1. **Index the epoch's blocks** (`listblocks` + `getblock`, chunked and cached) and
   refresh the `wpoa-weights` publisher index (`liststreamitems`).
2. **Derive `τ`** — `epoch_tau` counts **+1 per distinct signing address per non-coinbase
   transaction**, attributed to the epoch of the *confirming* block: exactly
   `ComputeActivityForEpoch`'s rule. Signers come from the harness's own records (every
   transfer is a single-from-address `sendassetfrom`, so the sender label *is* the signing
   address) plus the stream publisher index for the publishes the harness did not submit.
   The function also returns how many transactions in the epoch's blocks it could **not**
   attribute — `tau_coverage` (§5) asserts that is zero, which is the precondition for
   comparing `w_k` by value.
3. **Compute the weights** (`compute_epoch_weights`, pure) — `ImpUtente_i`, `W_k`, `w_k`,
   both per-mille `Delay`s, `p_k`, `A_k`. The `Σ_i c_i` sum runs in **ascending address
   order**, matching `WeightEngine::RawWeight`, so the non-associative floating-point
   total is identical to the node's.
4. **Settle the allocation on chain**: `A_k` is transferred FEEPOOL → miner. The FEEPOOL
   stands in for the aggregate of the paying senders — charging each of ~750 senders its
   own 0.2 GAS separately would not only triple the transaction count, it would *alter
   the measurement*, since each fee payment is a transaction signed by that company and
   would inflate the very `τ_i` it is a fee on. The GAS totals are identical.
5. **Reconcile on chain**: the miner's own node signs a transfer of `R_k` to the ADMIN
   address, drawn from its legal domain `[0, A_k + B_k^(e-1)]`. `WE_RESO_MODE=rate` (the
   default) takes `(A_k + B_prev) · reso_rate_k` with a small seeded jitter, where
   `reso_rate_k` is the configuration sheet's per-cluster **Reso** column (`WE_RESO_RATES`,
   default `1.00 / 0.90 / 0.75 / 0.60 / 0.40`) — so `% Reso` tracks the nominal rate and
   the λ-feedback on `w_k` is legible instead of buried in noise. `WE_RESO_MODE=uniform`
   reproduces the spreadsheet's `RANDBETWEEN(0; GuadagnoEx + Giacenza)` instead. Either
   way the clamp to `[0, A_k + B_prev]` is what keeps `% Reso ∈ [0,1]` and `B_k ≥ 0`.
6. **Read the amount back off chain**: the reconciliation transaction is re-read
   (`getrawtransaction … 1`) and the GAS quantity of the vout paying the ADMIN address
   is the authoritative `R_k` — never the amount we asked the node to send. The read
   happens **after the transaction confirms**, because `Giacenza` is by definition the
   post-reconciliation state.
7. **Fold the state forward**: `ρ_k = R_k/(A_k + B_prev)`, `B_k = B_prev + A_k − R_k`,
   `Total GAIN_k += A_k`. The miner's raw on-chain balance is also recorded, as
   `saldo_onchain`, so the accounting balance can be reconciled against the ledger.
8. **Publish** `weightsetreconciliation(miner, R_k_from_chain, e)`, so the engine's
   `ρ_k` is driven by GAS that actually moved.
9. **Check the five model invariants** on what was just produced
   (`verify_epoch_invariants`, §5) — a violation is recorded and surfaced immediately,
   not at the end of the run.

`Total GAIN_k` is the running sum of `A_k`, so it is monotonic by construction — which
§5 asserts.

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
  # --- the Vers_2 cluster-summary row, in sheet order ---
tx_miner, impatto_cluster, delay_msec, guadagno, resi, giacenza, pct_reso, total_gain,
  # --- pipeline detail ---
theta, sum_impatto_utente, raw_weight, final_weight, feedback_bracket,
delay_raw, delay_final, p_k, giacenza_prev, available, rho,
resi_target, resi_requested, resi_onchain, reso_rate_nominal, saldo_onchain,
  # --- consensus outcome (NOT an input to anything above) ---
blocks_mined, validated_in_blocks, block_interval_ms,
  # --- engine cross-check ---
engine_weight, engine_prob, w_k_expected, w_k_expected_int, weight_match,
selected_proposer,
  # --- provenance ---
alloc_txid, recon_txid, recon_stream_txid
```
Reading the columns that are easy to confuse:

| Column | Meaning |
|---|---|
| `tx_miner` | `τ_Mk`, the miner's **own** activity — an input to `W_k` |
| `validated_in_blocks` | how many transactions landed in the blocks it proposed — an **audit** figure, used by nothing |
| `impatto_cluster` / `raw_weight` | the same value, `W_k`; the first is the sheet's name |
| `final_weight` | `w_k = W_k · feedback_bracket` |
| `delay_msec` | the per-mille normalized weight actually in use (`delay_raw` or `delay_final` per `WE_ALLOC_BASIS`) |
| `block_interval_ms` | the **measured** mean inter-block interval — the thing "Delay" sounds like but is not |
| `giacenza` / `giacenza_prev` | `B_k` and `B_k^(e-1)` |
| `available` | `A_k + B_k^(e-1)`, the denominator of `% Reso` and the domain of `R_k` |
| `saldo_onchain` | the miner's raw GAS balance — seed funding and trading included, so **not** `B_k` |
| `weight_match` | `exact` / `within-tol` / `off` / `unpublished` |

`resi_target` is what the Reso rate asked for, `resi_requested` what the node was told
to send (clamped to the spendable balance), `resi_onchain` what the confirmed transaction
actually paid the ADMIN and `resi` that value clamped to `available`. Normally all four
agree; any divergence is a logged warning worth reading.

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
As before, with
`type ∈ {funding, company, miner, allocation, reconciliation, publish_esg,
publish_membership, publish_reconciliation, grant_write}` in `transactions.csv` and
`amount_gas` in place of the old `amount`. A transaction's `epoch` is the epoch of its
**confirming block**. The `publish_*` / `grant_write` rows are what make the ledger
record complete enough for `tau_coverage` to be assertable.

### 4.6 `epoch_checks.csv`, `assertions.csv` + `experiment.log`
`epoch_checks.csv` carries the five per-epoch model invariants (one row per epoch ×
check, §5); `assertions.csv` the run-level verdicts. `experiment.log` is the levelled
trace: the run header (now including the allocation basis and Reso mode), one settlement
line per epoch reporting `Θ`, `Σ A_k` against `α·Θ` and `Σ Delay`, and a final summary
(Θ, `Σ A_k / α·Θ`, Resi, `Σ B_k`, Total GAIN per cluster, blocks by miner, `http/cli`
call counts, final `getallweights`).

### 4.7 The `report.xlsx` workbook — [`make_report.py`](../make_report.py)

| Sheet | Content |
|---|---|
| `Foglio di configurazione` | α/κ/λ (λ shown **also as `Peso % Reso`**, the sheet's own units) and the allocation basis; the **Vers_2 range grid** verbatim — a row per ClusterMiner and per AZIENDE-of-a-cluster × Score min/max ESG and Numero min/max Tx; per ClusterMiner its **Score ESG, Certificato ISO, Peso %, Reso**; the 10 **AZIENDE** of each cluster with their ESG scores |
| `Epoch N` (one per epoch) | per azienda **Nome utente \| Tx Utente \| Impatto utente \| Score ESG**; after each group of 10, the cluster row **Tx Miner \| Impatto Cluster \| Delay in msec \| Guadagno Ex (€) \| € Resi in Ex \| Giacenza \| % Reso \| Total GAIN**, then the engine cross-check block (**Peso engine `w_k` \| Prob. selezione \| `w_k` atteso \| `w_k` atteso (int) \| Match \| Proposer**); epoch totals and an ESG/ISO recap close the sheet |
| `Riepilogo` | one row per epoch with the two **self-checking** columns `Somma Delay (=1000)` and `α×Θ` vs `Σ Guadagno`, highlighted red if they disagree; plus per-cluster run totals including blocks proposed and the `w_k` match tally |
| `Pesi & Probabilita` | epoch × cluster grid of published weights and selection probabilities |
| `Proposer log (wpoa)` | verbatim `wpoa_proposer_log.csv` (wpoa mode only) |
| `Verifiche` | **both** invariant levels: every run-level check, then the per-epoch tally with only the failures listed in full |

The totals rows are real Excel `SUM()` formulas over the actual cell ranges, so the
sheet is auditable rather than a set of opaque numbers. The configuration sheet reads
its parameters from `experiment.log` rather than from the reporter's own environment —
otherwise a report generated in a different shell would print the *defaults* next to
data produced with `WE_*` overrides.

**The cross-check columns — the experiment's primary result.** `W_k`, `w_k` and `A_k`
never leave the node, so the report shows the harness's replay of the pipeline beside
the engine's published `w_k`, with a per-cell `Match` verdict. The comparison is **by
value**, which rests on two things:

* `τ` is reconstructed exactly (§3.5 step 2) and the coverage is asserted, so the
  replay's `τ_Mk` is not short by the miner's own weight publish as it used to be;
* `Σ_i c_i` is summed in **ascending address order**, the order
  `WeightEngine::RawWeight` uses deliberately so that the non-associative
  floating-point total is identical on every node.

The node publishes `ToIntegerWeight(w_k, κ) = round(w_k · κ)`, so the two are compared
as integers. Reference smoke runs give **19–20 of 20 cells `exact`**; the residue is
`within-tol`, off by a single integer unit where `w_k · κ` lands on an exact `.5`
boundary and the two summation orders round it opposite ways (e.g. `46.725 · 100 =
4672.5` → 4673 here, 4672 on the node). That is a rounding artifact at a tie, not a
formula difference — which is exactly what the three-way `exact` / `within-tol` / `off`
classification exists to distinguish.

---

## 5. The invariant pass (`assertions.csv`)

Invariants run at **two levels**. A failure is logged as `ERROR` and recorded, but never
aborts — the artifacts are always complete.

### 5.1 Per epoch, inside `close_epoch` (`epoch_checks.csv`)

Checked on the data the moment it is produced, so a violation is visible at the epoch
that caused it rather than aggregated away at the end.

| Check | What it asserts |
|---|---|
| `alloc_sums_to_alpha_theta` | `Σ_k A_k = α·Θ` — the epoch's pot is fully and exactly distributed |
| `delay_sums_to_1000` | the per-mille normalization holds: `Σ_k Delay_k = 1000` (± `WE_DELAY_EPS`) |
| `rho_in_unit_interval` | `ρ_k ∈ [0, 1]` — it is a rate |
| `balance_non_negative` | `B_k ≥ 0` |
| `resi_within_available` | `R_k ≤ A_k + B_k^(e-1)` — nobody returns more than was available |

### 5.2 Run level (`assertions.csv`)

| Check | What it asserts |
|---|---|
| **`engine_matches_replay`** | **the primary result.** The integer weight each node published equals the harness's independent replay of `w_k`, for at least `WE_WEIGHT_MATCH_MIN` (0.95) of the comparable cells. Each cell is classed `exact`, `within-tol` (≤ `WE_WEIGHT_REL_EPS`, default 1 %), `off`, or `unpublished` |
| `weight_ranking` | the weight ordering agrees with the **ESG + activity composite** `ESG_Mk·(τ_Mk + Σ_i c_i)` ordering, as mean pairwise concordance ≥ `WE_RANK_MIN` (default 0.80). Below 1.0 on purpose: the feedback factor `ρλ + (1−λ)` legitimately reorders clusters whose raw weights are close |
| `reconciliation_visible_to_engine` | every `R_k` record confirmed before the next epoch buried. **If this fails, `engine_matches_replay` is meaningless** — see §6.9 |
| `settlement_confirmed` | every allocation/reconciliation transfer and governance publish made it into a block. GAS still in flight is reported here rather than surfacing as a phantom supply gap |
| `tau_coverage` | every transaction in every sampled epoch was attributed to a signer. **This is the precondition for `engine_matches_replay` being a value comparison at all**; if it fails, treat the weight check as a ranking result |
| `membership_from_chain` | the cluster sets read back off `weight-engine-membership` are exactly the configured topology — no company claimed by two clusters, none orphaned, no wrong-sized cluster. Every `W_k` depends on this set, so it is checked rather than assumed |
| `conformity_rate_range` | `% Reso ∈ [0, 100]` for every (epoch × cluster) |
| `total_gain_monotonic` | cumulative `Total GAIN` never decreases, per cluster |
| `alloc_sums_to_alpha_theta`, `delay_sums_to_1000`, `rho_in_unit_interval`, `balance_non_negative`, `resi_within_available` | the §5.1 tally, rolled up: "*n*/*N* epochs pass" |
| `alloc_equals_alpha_theta` | `Σ A_k = α·Θ` over the whole run — an **equality**, unlike the per-block fee tally it replaced (§0.1) |
| `gas_returned_to_admin` | the ADMIN's **on-chain balance increase** equals `Σ R_k` read off chain |
| `feepool_paid_out` | the FEEPOOL's balance decrease equals `Σ A_k` |
| `gas_supply_conserved` | the sum of every participant's balance equals the issued GAS supply |
| `giacenza_matches_chain` | per miner, `(closing − opening balance) − net miner↔miner trading = B_k`. This is what ties the accounting table to the ledger: `B_k` is not the raw balance, so it is verified as a **delta net of trading** rather than compared directly |
| `proposer_share_tracks_p_k` | *(wpoa mode only)* the L1 deviation between observed block share and mean `p_k`. **Reported, never thresholded** — the selector applies its own whale-compression at election time (`weight_engine.h`), so exact agreement is not expected and asserting it would be wrong |

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
Each network transaction costs α; the epoch's pot is `α·Θ`, split by weight share.
Deducting 0.2 GAS in a separate transaction from every one of ~750 senders per epoch
would roughly double the run's transaction count — but the decisive objection is not
cost, it is that **it would alter the measurement**: each fee payment is a transaction
*signed by that company*, so it would add +1 to the very `τ_i` it is a fee on, and the
weights would then be a function of the fee mechanism. One FEEPOOL address therefore
stands in for the aggregate and pays out each cluster's `A_k` in a single transfer. The
GAS totals are identical (`Σ_k A_k = α·Θ`, asserted); only the transaction count differs.
The FEEPOOL is not a cluster member, so its own `τ` never enters a weight, and paying
*into* a miner adds no `τ` to the miner either (`τ` counts signed inputs, not credits).

### 6.7 Why the transport changed
The MyLedger topology issues ~50 aziende × 10–20 transfers × 30 epochs ≈ 22 000
transactions, plus a `getblock` per block. At roughly 100 ms per `multichain-cli`
process spawn that alone would take the better part of an hour and dominate the whole
experiment; over a persistent HTTP connection the same call costs single-digit
milliseconds. The CLI remains the automatic fallback (and the summary line reports the
`http / cli` split, so a silent fallback to the slow path is visible).

### 6.9 The mempool backlog that silently invalidates a run
This one was found by the invariants, in a `wpoa` run that failed
`engine_matches_replay` with 12 of 16 cells `off`.

The published integers turned out to be **exactly** `round(W_k · κ · 0.5)` for every
cluster in every affected epoch — that is, the engine had applied the bare `(1−λ)`
bracket, meaning it read `ρ_k^(e-1) = 0`. It had not seen the reconciliation records at
all: submissions were outpacing block production, a mempool backlog had built up, and
`weightsetreconciliation` was confirming **20–24 blocks late**, well after the epoch it
belonged to had buried. Two unrelated checks (`gas_supply_conserved`,
`giacenza_matches_chain`) failed at the same time for the same underlying reason — a
lagging miner whose transfers were in flight and therefore held by neither party.

Three changes came out of it:

1. **`close_epoch` now blocks until the reconciliation records confirm** before leaving
   the epoch. That is a correctness condition, not politeness: `R_k^(e)` is the only
   economic input the engine takes from the harness, and it must be readable before epoch
   `e+1` buries. Blocking there also throttles the epoch loop to what the chain can
   absorb, so the backlog cannot grow without bound.
2. **The failure gets its own name.** `reconciliation_visible_to_engine` and
   `settlement_confirmed` report the actual condition, and `engine_matches_replay`'s
   detail line now *names this cause* when it sees the two together, instead of leaving
   it to be rediscovered.
3. **Supply is checked at minconf 0 as well.** A transfer in flight is held by neither
   sender nor recipient, so a confirmed-only sum under-counts by exactly that amount.
   Passing on either reading separates a confirmation lag from GAS that actually went
   missing.

The practical rule: a run that logs the mempool warning (`WE_MEMPOOL_WARN`, default 200)
is **not a valid measurement**. Lower `WE_TX_MIN`/`WE_TX_MAX` or raise
`WE_EPOCH_LENGTH` until the peak backlog is near zero. For reference, 50 aziende × 2–3
transfers over 12-block epochs runs at a peak backlog of 0 and gives 20/20 `exact`.

### 6.8 One `τ`, counted the engine's way
An earlier revision maintained *two* activity counters — a "business" one that ignored
settlement traffic and an "engine" one that did not — and reconciled them by hand. That
was a modelling error dressed up as a distinction: the engine has exactly one rule
(`+1 per distinct signing address per non-coinbase transaction`), and any second
definition can only disagree with the thing being verified.

There is now one `τ`, computed by that rule, from two complete sources: the harness's own
records and the `wpoa-weights` publisher index for the publishes it did not submit. What
used to be papered over — a miner's own weight publish, ~+1 per epoch — is now counted,
and the leftover is measured rather than assumed: `epoch_tau` returns how many
transactions in the epoch's blocks it could not attribute, and `tau_coverage` asserts
that count is zero. Getting this right is what upgraded the engine comparison from a
ranking test to a value test.

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
│   ├── membership_reader.py  cluster sets read BACK off chain (getstreamkeysummary
│   │                         jsonobjectmerge — the engine's own merge), cached
│   ├── tx_simulator.py       GAS issue/fund + per-epoch transfers (activity τ)
│   ├── economics.py          the whole Vers_2 pipeline: exact τ, W_k/w_k/Delay/p_k/A_k,
│   │                         automated on-chain settlement + reconciliation, and the
│   │                         five per-epoch invariants
│   └── weight_reader.py      getallweights + debug.log weight parse + block/proposer
│                             index + stream publisher index
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
