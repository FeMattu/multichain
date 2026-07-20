# WeightEngine experimental simulation — what it does, how it works, what it returns

This is the design companion to the code in
[`src/weight_engine/test/experimental/`](../). It explains the experiment end to
end: the network it drives, the two consensus regimes it can run, the exact steps of
a run, the six analysis artifacts it produces, and the non-obvious mechanisms (and
two consensus-timing pitfalls) that make it work.

It is an **experimental, offline-analysis harness**, *not* a pass/fail functional
test. The pass/fail check for the publish side is
[`../functional_test_weight_engine.sh`](../functional_test_weight_engine.sh); the
system-level wPoA check is
[`../../../wpoa/test/functional_test_wpoa_system.sh`](../../../wpoa/test/functional_test_wpoa_system.sh).
This harness instead runs a realistic scenario and writes CSVs + a log you import
into Excel/pandas to study how weights, transactions and proposers evolve.

**Cardinal rule:** it never re-implements the weight math. The
[`WeightEngine`](../../../weight_engine.h) computes `w_k` on the nodes; the harness only
*publishes the public inputs* through the sanctioned admin RPCs and *reads back* the
results.

---

## 1. The scenario

A single local MultiChain network of **1 admin + N miner nodes** (default `N = 4`),
run for a configurable number of **epochs** (default 12).

| Actor | Count | On-chain identity | Role |
|---|---|---|---|
| **admin** | 1 (node 0) | genesis / global administrator | publishes ESG + membership + reconciliation; issues + distributes the activity asset; **not a miner** (its `mine` permission is revoked once the miner set is live) |
| **miner** `M1..MN` | 4 | one mining node each | the wPoA validators; the engine computes and publishes each one's `w_k` |
| **company** `COMPANY_Mx_Cy` | 5 per miner → 20 | a plain address **in the admin wallet** | belongs to a miner's cluster; transacts to generate activity `τ` |

The admin owns the company keys so it can both *sign* company transactions and
publish their governance data; miners sign their own transactions on their own node.

The four inputs the [`WeightEngine`](../../../weight_engine.h) consumes map onto the actors
exactly as the thesis defines them:

```
c_i   = ESG_i · τ_i / κ                          (company contribution)
W_k   = ESG_{Mk} · ( τ_{Mk} + Σ_{i∈C_k} c_i )    (raw cluster weight)
A_k   = α · Θ · W_k / W_tot                       (allocation)
ρ_k   = R_k / (A_k + B_{k-1})                     (compliance, from reconciliation R_k)
w_k^(1) = W_k ;  w_k^(e) = W_k · [ρ_{k,e-1}·λ + (1-λ)]   (final weight)
```

so the harness must supply **ESG for every miner AND every company** (an uncertified
miner has `W_k = 0`, floored to 1, which would flatten the experiment), **membership**
(which companies belong to which cluster), **reconciliation** `R_k` per epoch, and
enough on-chain **activity** that `τ` is non-zero. Activity is *not* a stream — the
engine derives `τ` directly from the confirmed blocks of the epoch
([`weight_reader.cpp::ComputeActivityForEpoch`](../../../weight_reader.cpp)) — so the harness
produces it by making the participants transact.

---

## 2. The two modes (mandatory `--mode`)

The harness runs **exactly one** mode per invocation and never both. The mode only
changes the node launch flags ([`config.node_args`](../config.py)); everything else is
identical.

| `--mode` | Node flags | Proposer selection | `wpoa-weights` |
|---|---|---|---|
| `wpoa`   | `-enablewpoa=1 -enableweightengine=1 …` | **weighted** — the engine's `w_k` drives probabilistic wPoA selection (VRF/RANDAO/sortition) | computed **and** governs selection |
| `native` | `-enablewpoaweights=1 -enableweightengine=1 …` | native **round-robin** (master switch off) | computed and published, but **not** used for selection |

`native` is the control: the engine still computes and publishes `w_k`, so you can
compare "who *would* have proposed under wPoA (the weight favourite)" against "who
actually proposed under round-robin". That comparison is written to
`experiment.log` per epoch (the fixed `epochs_summary.csv` schema has no column for
it).

---

## 3. Anatomy of a run

Driver: [`experimental_test.py`](../experimental_test.py), class `Experiment`.

### 3.1 Setup — [`chain_setup.py`](../helpers/chain_setup.py)

Ports the permissioned-bootstrap protocol proven in
[`functional_lib.sh`](../../../wpoa/test/functional_lib.sh): create the chain, start
node 0 (seed), then for each miner *launch → grant `connect,send,receive,mine` +
`wpoa-weights.write` → relaunch to join*. `params.dat` is tuned (fast blocks; a long
setup phase — see §6.1; `mine-empty-rounds` high so it keeps mining).

Immediately after bootstrap, `ensure_miners_can_mine()` **re-grants and confirms**
`mine` on every miner (see §6.2 for why this is not redundant).

### 3.2 Publish the static inputs — [`stream_writer.py`](../helpers/stream_writer.py)

All via the admin, through the schema-validating RPCs (never raw `publishfrom`):

1. `ensure_write_permission()` — grant the admin `.write` on the three closed input
   streams **and wait for confirmation** (an unconfirmed write permission makes
   `publishfrom` silently fail).
2. `weightsetesg` — a certified, static ESG score for all 24 addresses (miners +
   companies), generated by [`esg_generator.py`](../helpers/esg_generator.py) from
   `WE_SEED`.
3. `weightsetmembership` — one call per company, mapping it to its miner cluster.
4. Fund participants — [`tx_simulator.py`](../helpers/tx_simulator.py) issues the
   activity asset to the admin and sends each participant a starting balance.
5. `ensure_wpoa_weights_stream()` — the admin **creates** the open `wpoa-weights`
   output stream and subscribes to it (see §6.3).
6. `demote_admin_from_mining()` — revoke the admin's `mine`, so it never proposes.

### 3.3 Warm-up

`wait_all_miners_weighted()` blocks until every miner appears in `getallweights`,
i.e. each has computed and published a first `w_k`. This guarantees wPoA selection
has a weight map before sampling begins.

### 3.4 Epoch loop

Sampled epochs are the `NUM_EPOCHS` epochs **after** the current tip (and, in `wpoa`
mode, after the setup phase — §6.1). For each epoch `e`:

1. `wait_height(start(e))` — wait until the tip enters epoch `e`'s block range.
2. `generate_epoch_txs(e)` — submit the epoch's transfers: 3–7 company↔company, 3–7
   miner↔miner, 1–2 symbolic asset transfers. Each `sendassetfrom` spends a UTXO
   owned by the sender, so the engine counts one `τ` for that sender in the
   confirming block's epoch.
3. `publish_reconciliation(e)` — a simulated `R_k` per miner (seeded; the engine
   clamps it to its legal domain).
4. `wait_height(end(e)+1)` — let the epoch's blocks mine.

Then it drives `STABILITY_MARGIN + 2` blocks past the last epoch's end so every
sampled epoch **buries** and its `w_k` gets published (§6.4).

### 3.5 Harvest + report — [`weight_reader.py`](../helpers/weight_reader.py) + [`reporters/`](../reporters/)

- Per-epoch weights come from the miners' `debug.log` lines
  `[WeightEngine] epoch E (height H): w_k = W for ADDR` — the authoritative,
  epoch-tagged value each miner published.
- `block_tx_index(1, hi)` scans blocks with `getblock` (tx list) + `listblocks`
  (`miner` field) to map every txid → confirming height and every height → proposer.
- The six artifacts (§4) are written; the network is always torn down in `finally`.

---

## 4. What it returns (`output/`, recreated each run)

### 4.1 `epochs_summary.csv` — one row per epoch
```
epoch, mode, block_height, proposer_miner, proposer_method,
weight_M1..M4, prob_M1..M4, tx_count, reconciliation_done, timestamp
```
`proposer_miner` is the **modal** proposer of the epoch (an epoch spans many blocks);
`weight_Mk` are the integer `w_k` that epoch; `prob_Mk = w_k / Σ w`; `tx_count`
excludes funding/reconciliation.

### 4.2 `esg_scores.csv` — one row per address (epoch 0 = static)
```
epoch, company_id, miner_id, esg_score, cluster_id, stream_txid
```
24 rows (20 companies + the 4 miners' own scores). `stream_txid` is the
`weightsetesg` publish txid.

### 4.3 `transactions.csv` — one row per transaction
```
epoch, block_height, txid, sender, receiver, type, amount, confirmed
```
`type ∈ {funding, company, miner, asset, reconciliation}`. `epoch` is the epoch of the
**confirming block** (resolved from the block index), so a transfer near a boundary
is attributed where it actually landed.

### 4.4 `weights_evolution.csv` — one row per (epoch × miner)
```
epoch, miner_id, raw_weight, normalized_weight,
selection_probability, was_selected_proposer, delta_weight_from_prev_epoch
```

### 4.5 `wpoa_proposer_log.csv` — one row per epoch, **`wpoa` mode only**
```
epoch, selected_proposer, selection_probability_at_time,
theoretical_expected_proposer, match_expected,
total_selections_M1..M4, cumulative_deviation_from_expected
```
`theoretical_expected_proposer` is the weight-argmax; `match_expected` is whether the
modal proposer equalled it (they diverge on a finite sample — selection is
*probabilistic*, not argmax); `cumulative_deviation_from_expected` is the running L1
distance between observed and expected shares.

### 4.6 `experiment.log`
Levelled `[INFO]/[DEBUG]/[WARN]/[ERROR]` trace with a header (mode, seed, params), an
entry per relevant event, the per-epoch native-vs-wPoA comparison, and a final
summary (blocks-by-miner, final `getallweights`).

---

## 5. Reading the results

Weights track ESG and activity: a low-ESG miner stays near the floor while a
high-ESG, active one dominates. In `wpoa` mode the observed proposer distribution
skews toward the higher-weight miners — the whole point of weighted selection —
without matching `w_k/Σw` exactly, because (a) the sample is finite and (b) the
consensus selector applies whale-compression `f(w_k)` at election time (see
[`weight_engine.h`](../../../weight_engine.h) "RELATION TO THE SELECTOR"). Treat
`selection_probability` as the theoretical pre-dumping probability.

---

## 6. Non-obvious mechanisms (and the pitfalls they solve)

### 6.1 The setup phase must outlast the warm-up (wpoa deadlock)
While the native setup phase (`setup-first-blocks`) lasts, mining is round-robin —
which is what lets the admin publish inputs and the miners establish a first weight.
The instant it ends, weighted selection governs; if **no weight exists yet, no miner
qualifies and the chain deadlocks.** So `SETUP_FIRST_BLOCKS` (default 40) is sized to
comfortably outlast bootstrap + publish + first-weight, and in `wpoa` mode the
harness waits until the tip is past the setup phase before sampling — so the sampled
epochs are genuinely wPoA-governed. Native mode is indifferent.

### 6.2 Confirm `mine` before wPoA governs (mining-key race)
Bootstrap grants can still be **unconfirmed** when wPoA takes over. An elected miner
whose `mine` permission has not confirmed reports *"no local mining key"* and cannot
propose — and since wPoA elects exactly one proposer per height, the chain stalls
until (or unless) that grant confirms. `ensure_miners_can_mine()` re-grants and waits
for confirmation on the exact address the engine keys the weight by, removing the
race.

### 6.3 Someone must create `wpoa-weights`
The registry creates the (open) `wpoa-weights` stream lazily — but only a
create-permitted node can, and in a normal wPoA deployment that node is a validating
genesis. Here the admin is deliberately **not** a cluster miner, so its engine never
reaches the create step, and the miners lack create permission. The admin therefore
creates it explicitly (open, exactly as the registry would) and subscribes so
`getallweights` — queried on the admin — can see the miners' published weights.

### 6.4 Weights lag the tip (buried epochs)
The engine publishes `w_k` only for the newest **buried** epoch
(`(tip − STABILITY_MARGIN + 1) / len`), folding forward from epoch 1, because `τ` is
derived from block/undo data and a shallow reorg near the tip must not change it. The
harness accounts for this by driving `STABILITY_MARGIN + 2` blocks past the last
sampled epoch before harvesting.

### 6.5 No native currency → asset-based activity
A default MultiChain has `initial-block-reward = 0`, so there is no spendable native
currency. The harness issues a purpose asset, funds every participant, and moves it
around; each `sendassetfrom` is a transaction whose signed input the engine's
undo-data metric counts as one `τ` for the sender — exactly the thesis definition of
activity.

---

## 7. Determinism & error handling

Every random choice (ESG scores, transaction picks, reconciliation amounts) derives
from `WE_SEED` (default 42), so a run is reproducible: the same seed yields the same
ESG assignment and trade pattern regardless of node timing. A failed RPC is logged to
`experiment.log` and the run continues; the network is torn down on every exit path.

---

## 8. File map

```
experimental/
├── experimental_test.py      orchestrator (Experiment): run phases + build CSVs
├── config.py                 seed, topology, epoch geometry, all WE_* knobs
├── run_experiment.sh         wrapper around experimental_test.py
├── helpers/
│   ├── chain_setup.py        Network/Node: bootstrap, grants, confirm/height waits, teardown
│   ├── participants.py       label ⇄ address ⇄ owning-node registry
│   ├── esg_generator.py      seeded, static ESG for miners + companies
│   ├── stream_writer.py      admin → esg / membership / reconciliation (validating RPCs)
│   ├── tx_simulator.py       asset issue/fund + per-epoch transfers (activity τ)
│   └── weight_reader.py      getallweights + debug.log weight parse + block/proposer index
├── reporters/
│   ├── csv_reporter.py       the six CSV writers (+ output reset)
│   └── log_reporter.py       levelled experiment.log
└── output/                   generated each run (git-ignored)
```

Module names use `_` (not the hyphens of the original spec sketch) so they are
importable Python modules; `participants.py` is an added helper the writers share.

---

## 9. Running it

```bash
# build the node first: ./autogen.sh && ./configure && make
./run_experiment.sh --mode=wpoa
./run_experiment.sh --mode=native

# smaller / faster (all knobs are WE_* env vars; see config.py)
WE_EPOCHS=6 WE_EPOCH_LENGTH=4 ./run_experiment.sh --mode=native
```

A run drives a live multi-node chain for many blocks, so it takes several minutes;
the `WE_*` knobs trade fidelity for speed. For a fixed CSV schema the report columns
assume 4 miners (`M1..M4`); changing `WE_MINERS` still runs but the summary columns
stay at four.
