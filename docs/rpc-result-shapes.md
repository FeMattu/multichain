# wPoA / WeightEngine RPCs — what each one actually returns

> **Register: technical-direct.** A reference for anyone writing a consumer of the audit
> RPCs. It exists because the shapes are **not uniform**, and the only other way to learn
> that is to write a parser, run it, and find out which calls it silently mishandled.

The read-only audit families were added together and look interchangeable. They are not:
three different container shapes are in use, and two of them appear within the same
`weightlist*` family. Nothing here is a defect to be fixed — changing a published result
shape would break every existing consumer — but it has to be *written down*.

## The three shapes

| Shape | Looks like | Which RPCs |
|---|---|---|
| **A — address → object** | `{"scores": {"1Abc...": {"score": …, "weight": …}}}` | `wpoalistscores`, `wpoalistdelays`, `wpoalisteffectiveweights`, `wpoalistfinalweights`, `weightlistcontributions`, `weightlistclusterweights`, `weightlistearnings` |
| **B — address → bare number** | `{"weights": {"1Abc...": 4200}}` | `getallweights`, `weightlistreturns`, `weightlistbalances` |
| **C — array of objects** | `{"entries": [{"address": …, "verdict": …}]}` | `weightverifyweights`, `wpoalistblocksortition` (a bare array, no wrapper key) |

A consumer that assumes shape A will read shape B as `4200["score"]` and raise; one that
assumes B will read A as a dict where a number was expected. Both failures happen at parse
time on a subset of the calls, which is the worst place to discover them.

`getallmalus` is shape A but nests one level deeper: `{"validators": {"1Abc...": {...}}}`.

## Per-RPC detail

### wPoA round audit — shape A

Each takes an optional `height` (default: tip + 1) and returns the per-address map under a
family-specific key, plus a shared round context.

| RPC | Map key | Per-entry fields |
|---|---|---|
| `wpoalistscores` | `scores` | `score` (double **or JSON `null`** when ineligible), `weight`, `effective_weight`, `eligible` |
| `wpoalistdelays` | `delays` | `delay`, `score`, `score_norm`, `effective_weight`, `eligible` |
| `wpoalisteffectiveweights` | `effective_weights` | `raw_weight`, `dumping_function`, `effective_weight` (a **double** here, and *not* malus-corrected) |
| `wpoalistfinalweights` | `final_weights` | `raw_weight`, `malus`, `malus_factor`, `weight_after_malus`, `dumping_function`, `effective_weight_after_malus_and_dumping`, `eligible` |

Round context on every score/delay answer: `height`, `seed`, `seed_source`
(`randao` \| `prevblockhash`), `dumping_function`, `total_effective_weight`. Delay answers
add `target_block_time`, `delta`, `lambda`, `feedback` (Φ).

> **Which weight the election consumes.** `wpoalisteffectiveweights` reports `g(w)` — the
> dumping function alone. `wpoalistfinalweights` reports `g(w·Ψ)`, after the malus factor
> too, and *that* is what the selector draws on. Comparing observed block shares against
> the effective weight rather than the final one tests a null the selector never used.

> ⛔ **Which *score* these four report — the trap that outlives the shape traps.** All of
> them score with the **public** Efraimidis form `HMAC-SHA256(seed, address)`, the only one
> computable for a validator whose secret key the answering node does not hold. Under private
> sortition (Phase 4) the election draws from a VRF under each proposer's own key, so these
> scores are an audit of the model and its inputs and are *statistically independent* of the
> draw that armed the timers. They cannot name the round's argmin, and a metric that treats
> them as if they could returns its own null value whatever the protocol does. The block
> audit below is the surface that reports the real thing.

### Block sortition audit — shape C

`wpoagetblocksortition <height>` returns one object; `wpoalistblocksortition
<block-set-identifier>` returns a **bare JSON array** of the same objects — no wrapper key,
unlike every shape-A answer above. The block-set grammar is `listblocks`'s, and one call is
capped at 1000 heights because each one is read from disk.

These report the **winner's real private score**, recomputed from the VRF reveal its block
carries — the same recompute `WPoASortitionVerifyProposer` performs to enforce the time bar.
It is the only score surface that describes the election that actually happened, and it
exists only for the winner: no node can produce the others.

| Field group | Fields |
|---|---|
| identity | `height`, `hash`, `miner`, `epoch` |
| the real draw | `score`, `score_norm`, `delay`, `earliest_time`, `effective_weight` |
| timing | `block_time`, `parent_time`, `dt_prev`, `time_received` (**local** sub-second arrival, per-node, not consensus data) |
| round context | `total_effective_weight`, `target_block_time`, `delta`, `lambda`, `feedback`, `seed`, `seed_source`, `dumping_function` |
| provenance | `sample_height`, `sample_epoch`, `weight_epoch_stale`, `verdict` |

`verdict` is always present and names why a row carries no score rather than leaving a hole:
`ok`, `not-sortition`, `no-reveal`, `no-signer`, `no-weight`, `no-block`, `no-block-data`,
`unevaluable`.

> **Weights are read as of the answering tip, not as of `height`.** The registry has no
> height-bound read, and weights only move on an epoch boundary, so an answer is exact
> whenever `sample_epoch == epoch`; `weight_epoch_stale` flags the rows where it is not
> (roughly one per epoch when sampled per block).

### WeightEngine epoch audit

Each takes an optional `epoch` (default: newest fully buried) and refuses an epoch that is
not yet buried.

| RPC | Map key | Shape | Per-entry |
|---|---|---|---|
| `weightlistcontributions` | `contributions` | **A** | `address`, `cluster`, `esg_score`, `activity`, `kappa`, `contribution` |
| `weightlistclusterweights` | `cluster_weights` | **A** | 12 fields incl. `raw_cluster_weight`, `previous_epoch_return_rate` (**`null` at epoch 1** — no previous rate, which is not the same as a rate of zero), `final_cluster_weight`, `published_weight` |
| `weightlistearnings` | `earnings` | **A** | `income`, `expenses_gross`, `expenses_excl_return`, `earnings`, `return_amount`, `balance`, `return_rate` |
| `weightlistreturns` | `returns` | **B** | the bare `R_k`; the treasury address is a sibling field, not per-entry |
| `weightlistbalances` | `balances` | **B** | the bare `saldo_k` |
| `weightverifyweights` | `entries` | **C** | `address`, `published`, `published_epoch`, `recomputed`, `verdict` (`ok` \| `mismatch` \| `not-a-cluster` \| `other-epoch` \| `unverified`) |

### Registry and malus

| RPC | Shape | Note |
|---|---|---|
| `getallweights` | **B** | `{validators, total, weights: {addr: int}}` |
| `getallmalus` | **A** | `{epoch, enabled, validators: {addr: {malus, psi, weight, effective, excluded, epochs_to_clear}}}` |
| `getnodemalus` | flat | one object, not a map |

## Two traps that are not about shape

**`liststreamitems` defaults to `count = 10`.** Reading a whole stream requires passing
`count` explicitly. The default silently truncates to the last ten items, and a consumer
that does not pass it will under-count every stream it reads without any error.

**A float very close to 1 may render as `0`.** The JSON writer emits doubles by formatting
to 14 decimals and stripping trailing zeros; `0.99999999999999889` formats as
`1.00000000000000`, every decimal strips, and the emitted value is `0`. Observed on
`score_norm` in 2 of 415 rounds of a real run, where the `delay` in the *same answer* was
computed from the true value and therefore disagreed with it.

The node's arithmetic is correct — `PrivateSortition::NormalizedScore` returns the right
value and the delay matches it. It is the rendering that loses information, and it affects
any double whose 14-decimal rendering is all zeros after the point.

*Not fixed here*: the writer (`src/json/json_spirit_writer_template.h`,
`output_double_precision`) serialises every numeric RPC in MultiChain, and changing its
precision would alter output far beyond this subsystem and could break existing consumers.

**What to do instead:** derive such quantities from fields that survive. `score_norm` is
`1 - exp(-total_effective_weight · score)`, and both `score` and `total_effective_weight`
render faithfully. The functional harness recomputes it for exactly this reason
(`test/analysis/pipeline/phase2_aggregate.py`).

## There is no `getround` or `getepoch`

The commit that "exposed the round and the epoch to read-only audit" added 27 RPCs as
*families*, not two scalar getters:

- the **round** is the `height` argument, and the `height` / `seed` / `seed_source` fields
  of every wPoA audit answer;
- the **epoch** is the `epoch` argument, and the `epoch` field of every WeightEngine one.

The closest things to "what round/epoch is it now": `wpoalistscores` with no argument
(returns `height` = tip + 1), and any `weightlist*` with no argument (returns the newest
buried epoch).

---

## Related

- [protocol-parameters.md](protocol-parameters.md) — the parameters these RPCs report on.
- [weight-engine.md](weight-engine.md) — the pipeline whose stages these families expose.
- [`../test/docs/RPCLIST.md`](../test/docs/RPCLIST.md) — the node's full command reference.

_Verified against `src/rpc/rpcwpoa.cpp` and `src/rpc/rpcweightengine.cpp` on 2026-09-17
UTC (commit `7f3eb829`, branch `fix/wpoa-cpp-bugs-and-harness-simplification`)._
