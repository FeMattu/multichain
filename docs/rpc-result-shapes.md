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
| **C — array of objects** | `{"entries": [{"address": …, "verdict": …}]}` | `weightverifyweights` |

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
