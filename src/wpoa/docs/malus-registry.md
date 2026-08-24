# Behavioural malus registry (`malus_record.h` + `malus_registry.{h,cpp}`)

> **Register: technical-direct.** A developer reference: APIs, function signatures,
> data structures and control flow, with code terminology left verbatim. For the
> theoretical consensus model see
> [thesis-project-overview.md](thesis-project-overview.md); for parameter values see
> [protocol-parameters.md](protocol-parameters.md); for implementation status see
> [implementation-status.md](implementation-status.md).

> The second of the two registries wPoA maintains, and the deliberate mirror image of
> the first. Where [`stream-weight-registry.md`](stream-weight-registry.md) documents the
> **closed** stream that says how much a validator is worth, this one documents the
> **open** stream that records how it has behaved — and how the two are combined into the
> effective weight the proposer election actually consumes.

---

## Table of contents
- [1. Why a second registry](#1-why-a-second-registry)
- [2. The two streams are opposites, on purpose](#2-the-two-streams-are-opposites-on-purpose)
- [3. What can be reported, and why only these](#3-what-can-be-reported-and-why-only-these)
  - [The consensus-behavioural family](#the-consensus-behavioural-family)
  - [The published-data-integrity family](#the-published-data-integrity-family)
- [4. Valid(e) — the local decidability predicate](#4-valide-—-the-local-decidability-predicate)
- [5. Accumulation, and why exclusion is always temporary](#5-accumulation-and-why-exclusion-is-always-temporary)
- [6. Epoch alignment, and the acyclicity it buys](#6-epoch-alignment-and-the-acyclicity-it-buys)
- [7. Where it enters consensus](#7-where-it-enters-consensus)
- [8. Configuration](#8-configuration)
- [9. RPC surface](#9-rpc-surface)
- [10. Tests](#10-tests)
- [11. Files](#11-files)

---
## 1. Why a second registry

The weight `w_i` on `wpoa-weights` is produced entirely outside the consensus: an ESG
score and a participation measure, computed by the weight-management layer
([`../../weight_engine/`](../../weight_engine/)) and published as a number the consensus
consumes without knowing how it was derived. That layer has no view of how validator `i`
behaves *on the wPoA protocol itself*. A validator
that equivocates, or that tries to jump its scheduling delay, keeps exactly the same
`w_i` as an honest one — the misbehaviour is invisible to the mechanism that sets the
weight.

The malus registry closes that gap **without touching the weight layer at all**. It
accumulates proved misbehaviour into a decaying severity `M_i`, turns it into a correction
factor `Psi_i`, and applies it *downstream* of the raw weight:

```
w_eff_i = w_i * Psi_i
```

The raw weight, the `wpoa-weights` stream and the Efraimidis–Spirakis election math are
all unchanged. Only the number handed to the sortition changes.

---

## 2. The two streams are opposites, on purpose

| | `wpoa-weights` | `wpoa-weights-malus` |
|---|---|---|
| Write policy | **CLOSED** — needs `wpoa-weights.write`, now granted network-wide | **OPEN** — anyone may publish |
| What it carries | a validator's own weight | an accusation against a validator |
| Trust model | trust the *evidence*: the record is self-published and its value is independently recomputable | trust the *evidence* (re-verified) |
| Created in | `stream_weight_registry.cpp` | `malus_registry.cpp` |

The asymmetry is still the design, but it has **narrowed**, and the reason is worth being
precise about.

**Originally** a weight was a *claim nobody could check*: it came from outside the chain, so
the only defence was to restrict who may assert it — hence the closed stream and one
authorized publisher per cluster. An accusation, by contrast, has always been a *proof*:
every node re-derives it from public chain data and reaches its own verdict. Restricting
who may accuse would buy nothing and would centralize the one function that most benefits
from being open.

**A weight is now checkable too**, on both counts, so `wpoa-weights.write` is granted to
every node while the stream stays closed:

- *who wrote it* — the record is **self-published**: the reader discards it unless the
  transaction's signer is the cluster the record is about;
- *whether the value is right* — every pipeline input is public and deterministic, so any
  node **re-runs the identical computation** and a differing value is provably wrong.

The two registries have therefore converged on the **same epistemic principle**: trust the
evidence, not the publisher. What still separates them is only the *shape* of the evidence
— a signature plus a recomputation for a weight, a referenced block plus a re-derivation
for an accusation — and consequently the write policy: closed-but-universal for weights
(a node may write only about itself), fully open for accusations (anyone may report about
anyone, because the report proves itself).

**One datum resisted this and still does: the ESG score.** It is an attestation with
nothing inside it to check, so it is defended the only way such a claim can be — by
restricting who may assert it, through the Certification Authority role. Everything else
in the weight pipeline is now either chain-derived (the activity counters and the
reconciled amounts, both read off the blocks) or self-verifiable. Detail:
[weight-engine.md §5.1](weight-engine.md#51-every-node-publishes-its-own-weight-and-every-node-checks-the-others)
and [§6.4](weight-engine.md#64-esg--the-certification-authority-role).

Opening the stream is therefore free in safety terms. A false, malformed or duplicated
report is discarded **identically on every honest node** (§4), so it never reaches the
accumulator and never moves anyone's weight. Spamming the stream costs the spammer
transaction fees and achieves nothing.

---

## 3. What can be reported, and why only these

Four kinds, in **two families**. Both satisfy the same requirement — the proof must be
re-derivable from public chain data — and differ in what the evidence is and what the
offence damages. A report whose proof needed another validator's private state or secret
key could not be decided locally, which would break the property the open stream rests on.

| Family | Kinds | Evidence | What it attacks |
|---|---|---|---|
| **Consensus-behavioural** | `equiv`, `delay` | the **block**, and the VRF reveal it carries | how the election is *executed* |
| **Published-data integrity** | `selfwrite`, `badweight` | the publishing **transaction**, its signature and payload | the *inputs* the election consumes |

The second family exists because the weight inputs became self-verifiable. A forged
membership record or a false weight is now **provably** wrong, and anything provable can
carry a malus on exactly the same terms as an equivocation — trust the evidence, not the
publisher. Before that, a wrong weight was simply an unverifiable claim, so there was
nothing to accuse.

### The consensus-behavioural family

### `equiv` — equivocation

The accused signed **two distinct blocks at one height** over the same beacon seed.

The proof needs no extra context. For a fixed key and input the VRF output is unique, so an
honest validator physically cannot produce two distinct validly-revealed blocks for one
round — the coexistence of the two blocks *is* the proof of a deliberate double proposal.
This is the fault that threatens the chain's **safety** (competing blocks at one height),
which is why it carries by far the larger score.

### `delay` — scheduling-delay violation

The accused published a block whose VRF proof is valid but whose timestamp precedes the
delay its own sortition score entitled it to:

```
t(B) < parent.nTime + MiningDelay(score_i, ...)
```

The **attempt** is the offence, whether or not it was accepted anywhere. Block validation
already rejects such a block, but without a registry a node could retry the attempt
indefinitely at zero cost; recording it gives the attempt a price. This fault threatens
only the correctness of the temporal scheduling, not safety — hence the much smaller
score, and the protocol constraint `p(Equiv) >> p(Delay)` enforced at startup.

**What the behavioural proofs do not cover.** Both are self-referential to the accused's
own cryptographic evidence. Neither establishes that a given validator really did hold the
globally minimum score — that question is outside the reach of *any* local check, by
construction of the private sortition.

### The published-data-integrity family

Both kinds concern a **stream the weight pipeline reads**, and both are proved from the
publishing transaction rather than from a block. Neither needs the private sortition, so
neither is restricted to sortition-governed heights.

#### `selfwrite` — a record published on another address's behalf

The accused signed a transaction publishing, on a **self-attested** stream
(`wpoa-weights` or `weight-engine-membership`), a record whose `node_address` is somebody
else's.

The proof is the exact **negation** of the rule the readers apply: a report is valid
precisely when the readers discarded the record. Both use the same shared predicate
(`mc_StreamItemIsSelfAttested`, [`../weight_record.h`](../weight_record.h)), so a node can
never accuse a record it would have accepted, or accept one it would accuse.

Readers discard such a record already, so the attempt gains nothing — and that is exactly
why it needs a price. Without one a node could forge records indefinitely for the cost of
fees alone, and every peer would keep decoding and discarding them. **The attempt is the
offence**, the same reasoning as `delay`.

#### `badweight` — a weight that fails independent recomputation

The accused published on `wpoa-weights` a value that does not survive re-running the
pipeline over the epoch's public inputs
([weight-engine.md §5.1](weight-engine.md#51-every-node-publishes-its-own-weight-and-every-node-checks-the-others)).

Unlike `selfwrite`, this one **can succeed**: a record from the right signer is accepted
on the self-publication rule, so a false value would flow into the election unless
somebody recomputes it. It is the offence with the most direct effect on proposer
probability — a single inflated weight distorts every round of the epoch — which is why
it carries the heavier of the two data-integrity scores.

The two are kept **disjoint**: a record the accused did not sign was already discarded on
the self-publication rule, so it is a `selfwrite` and not a `badweight`. One act is never
scored twice.

#### What the data-integrity proofs require, and what they do not

Both need the **weight engine** to be decidable — `badweight` to recompute, a membership
`selfwrite` because the engine is what subscribes to that stream. `enable-weight-engine`
is itself a hash-enforced chain parameter, so every node agrees on whether these kinds are
decidable *at all*, which is what keeps the verdict, and therefore `Psi`, uniform. On a
chain without the engine, such reports are refused network-wide and the node says so at
startup.

A node that cannot recompute a given epoch — pruned, or not yet synced — reports the
accusation as **undecided, not proved**. That is the safe direction: an unprovable
accusation must not count. It is the same principle as the verifier's fail-open seen from
the accused's side — in both cases *"cannot tell"* means *"no penalty"*.

---

## 4. `Valid(e)` — the local decidability predicate

`MalusRegistry::ValidReport` is the gate that makes an open stream safe. It uses only the
primitives block validation already uses, and only public chain data:

**For the consensus-behavioural kinds:**

1. the height must be governed by private sortition (both proofs rest on the block-carried
   VRF reveal over the beacon seed, which exists nowhere else);
2. the referenced block(s) must resolve in the local block index, and carry a signer and a
   VRF reveal;
3. the signer's address must match the accused;
4. the reveal must verify against the beacon seed derived over the block's parent — the
   same check the validator ran;
5. and then, per kind:
   - `equiv`: the two blocks must be **distinct**, at the reported height, and share a
     parent (same round ⇒ same seed, which is what makes VRF uniqueness bite);
   - `delay`: the score is recomputed from the revealed output and the accused's effective
     weight, and the block's `nTime` must be **strictly earlier** than
     `parent.nTime + delay`.

**For the data-integrity kinds** (`MalusRegistry::ValidDataIntegrityReport`), the evidence
is a transaction rather than a block, so the sequence differs while the discipline does
not — every step is a comparison between two pieces of public data, never a judgement:

1. the report must name exactly **one** transaction;
2. that transaction must be **confirmed**, at the reported height, and carry a decodable
   item on the named stream — decoded with the *same* parsers the readers use, so verifier
   and reader cannot disagree about what a record says;
3. the report's own claims (`stream`, `declared_address`, `epoch`, `declared`) are
   re-checked against that transaction. They exist to make the accusation **auditable**,
   not to be believed: a mismatch invalidates the report;
4. then, per kind:
   - `selfwrite`: the accused must be a **signer** of the transaction, and the declared
     address must **not** be. Both halves matter — the first establishes who wrote it, the
     second that what it wrote was a forgery;
   - `badweight`: the accused must be the signer *and* the subject (otherwise it is a
     `selfwrite`), the record must state an epoch, and re-running the pipeline over that
     epoch's public inputs must **disagree** with the published value. If the value turns
     out correct, the report is refused with exactly that reason.

Because every input is public and already agreed, two honest nodes always compute the same
verdict. The reporting RPC runs the same check *before* broadcasting, so a node never
spends a transaction on evidence its own peers would throw away — and for the
data-integrity kinds it also *derives* what it alleges from the referenced transaction, so
a caller cannot mis-state the accusation in the first place.

---

## 5. Accumulation, and why exclusion is always temporary

A single proved violation must not exclude a validator for ever — an isolated event (a
transient bug, a mishandled restart) is not the same thing as a pattern. So the registry
accumulates an **exponential moving average**, not a counter:

```
M^(e) = mu * M^(e-1) + sum of p(kind) over the epoch's valid reports      (Def. 5.21)
Psi   = max(0, 1 - M / M_max)                                            (Def. 5.22)
```

**One accumulator carries both families.** Adding the two data-integrity kinds touched
exactly one function — `MalusAccumulator::Points`, the per-kind score dispatch. Everything
downstream was already generic, because it operates on the accumulated severity `M` rather
than on what produced it: `Fold`, `Psi`, `w_eff`, `EpochsToClear` and `ApplyToWeights` all
needed **no change at all**, and neither did the consensus path. Two consequences worth
stating:

- a node cannot spread misbehaviour across kinds to stay under the threshold — a
  `selfwrite` and a `badweight` in one epoch add up in the same `M`;
- **exclusion stays temporary for data-integrity violations too**. The decay argument
  below is a property of `M`, not of the offence that raised it, so a node that stops
  misbehaving recovers after the same finite, computable number of clean epochs.

`Psi = 1` for a validator with no accumulated violations, so **the mechanism is completely
inert on honest behaviour**; it then falls linearly and reaches 0 at `M >= M_max`.

With `mu < 1` the memory decays, so an exclusion always clears after a finite, computable
number of clean epochs:

```
k* = ceil( ln(M / M_max) / ln(1 / mu) )                                  (Prop. 5.16)
```

`MalusAccumulator::EpochsToClear` returns exactly that, settled on the *strict* inequality
`mu^k * M < M_max` (the closed form alone solves the non-strict one and lands a validator
exactly *on* the threshold when `M / M_max` is an exact power of `1/mu`). The `mu < 1`
constraint is enforced at startup — it is what makes "no permanent ban" (Cor. 5.17) a
property of the code and not just of the tuning.

A zero effective weight needs no special handling anywhere downstream: the score transform
already returns `+inf` for a zero weight
([`wpoa_selector.h`](../wpoa_selector.h) `ScoreFromEntropy64`), which makes the validator
structurally ineligible without an explicit exclusion branch.

---

## 6. Epoch alignment, and the acyclicity it buys

`M` and `Psi` are per-epoch quantities on the **same** height→epoch map the weight layer
uses (`HeightToEpoch`, [`../../weight_engine/weight_engine.h`](../../weight_engine/weight_engine.h)) —
single-sourced deliberately, since two copies of a consensus-critical mapping could drift.

Heights in epoch `e` are governed by `Psi^(e-1)`: a malus proved in an epoch takes effect
from the epoch **after**. That mirrors the weight layer's own inter-epoch feedback, where
`rho^(e-1)` drives `w^(e)` (Def. 6.9) — and it is also what keeps the definition acyclic.
Validating a `delay` report from epoch `e` requires the delay the block validator actually
enforced, which is derived from the effective weight in force at that height; resolving it
against `Psi^(e)` would make the epoch's own reports depend on themselves.

---

## 7. Where it enters consensus

Exactly one place: `WPoAApplyMalus(weights, height)`.

```
StreamWeightRegistry::GetAllNodesWeights()      raw w from the closed stream
        │
        ▼
WPoAApplyMalus(weights, height)                 w_eff = w * Psi^(e-1)
        │
        ├──► WPoASelectProposer            (public argmin path)
        └──► BuildSortitionContext         (private sortition: miner AND validator)
```

Both the miner and the validator call it on the map they read from `wpoa-weights`, so both
sides score the same numbers — a divergence here would be a fork. It returns the map
unchanged when the registry is disabled, the stream is unavailable, or nobody carries a
proved violation, so enabling the mechanism on a clean chain is a no-op.

---

## 8. Configuration

The registry is governed by five inheritable chain parameters, resolved like every
other wPoA switch (`params.dat` baseline, CLI override, loud warning on a local
divergence). All are consensus-critical.

> **Names, types, defaults and valid ranges:
> [protocol-parameters.md §3](protocol-parameters.md#3-catalogue--behavioural-malus-registry).**

The registry is governed by seven inheritable chain parameters — the two data-integrity
scores joined the five original ones.

Three constraints are **hard failures** at startup, and all three are structural rather
than stylistic:

1. **The registry requires private sortition.** The *behavioural* evidence kinds are
   proved against the block's VRF reveal over the beacon seed, which only exists once
   sortition runs.
2. **`p(Equiv) > p(Delay)`.** An equivocation is a *safety* fault, a delay violation
   only a *scheduling* one; inverting the order would let the lighter fault dominate
   the accumulator.
3. **`p(BadWeight) > p(SelfWrite)`.** The same argument inside the data-integrity pair: a
   forged record is *always discarded*, so its score prices the attempt, while a false
   weight *succeeds* unless somebody recomputes it and then distorts every round of the
   epoch.

The intended ordering overall is therefore
`p(Equiv) > p(BadWeight) > p(SelfWrite) > p(Delay)`: safety first, then a fault that takes
effect, then two attempts that are rejected anyway.

The data-integrity kinds additionally need the **weight engine** to be decidable at all
(`badweight` to recompute; a membership `selfwrite` because the engine is what subscribes
to that stream). That is *not* a startup failure — the behavioural kinds still work — but
the node logs a note, because on such a chain those reports are refused network-wide.

---

## 9. RPC surface

| Command | What it does |
|---|---|
| `getallmalus` | `M`, `Psi`, raw weight, `w_eff`, exclusion flag and epochs-to-clear for every validator. |
| `getnodemalus "address"` | The same, for one validator. |
| `reportmalus "kind" "address" height "evidence" ["blockhash2"]` | Publishes a report, after re-verifying it locally. `kind` is `equiv`, `delay`, `selfwrite` or `badweight`; `evidence` is a block hash for the first two and the offending **transaction id** for the last two. The data-integrity kinds take no further arguments — what they allege is derived from the referenced transaction, so a caller cannot mis-state it. |

---

## 10. Tests

- **Unit** ([`../test/wpoa_malus_tests.cpp`](../test/wpoa_malus_tests.cpp), node-free, run
  with `run_unit_tests.sh malus`): record parsing including both `OpReturnFormatEntry`
  wrappings and rejection of every malformed shape; the fold and its decay; `Psi` over its
  whole range; `w_eff`; the map-level transform; and reversibility — that an excluded
  validator becomes eligible again after exactly `EpochsToClear` clean epochs, for every
  `mu` in `(0,1)`. For the data-integrity kinds: their record shapes and every rejection
  (missing fields, a report accusing an *honest* record, a `badweight` whose two values
  agree, two evidence references where one is required); the four-score dispatch and the
  severity ordering; that the two-score form stays backward-compatible by scoring the new
  kinds `0`; and end to end through the correction — one proved `badweight` halving
  `w_eff`, a second reaching the threshold, then decaying back.
- **Functional** ([`../test/functional_test_wpoa_system.sh`](../test/functional_test_wpoa_system.sh)):
  `check_stream_permissions` asserts the closed/open asymmetry and that it bites (an
  address without `wpoa-weights.write` cannot publish a weight, yet can publish a report);
  `check_malus` asserts the mechanism is inert on honest behaviour and that every node
  refuses false evidence, for **both families** — an honest block is not a delay violation,
  one block named twice is not an equivocation, a block nobody has seen proves nothing;
  and an honestly self-published weight is neither a `selfwrite` (the declared address did
  sign it) nor a `badweight` (every node's recomputation agrees with it), swept over
  several heights so the refusal cannot be an accident of naming the wrong one.

---

## 11. Files

| File | Role |
|---|---|
| [`../malus_record.h`](../malus_record.h) | Pure core: the four kinds and their families, record parsing (including the data-integrity payloads), the `MalusScores` dispatch, `Fold`, `CorrectionFactor`, `EffectiveWeight`, `EpochsToClear`, `ApplyToWeights`. Node-free and unit-tested in isolation. |
| [`../malus_registry.h`](../malus_registry.h) | The `MalusRegistry` facade, the runtime parameters and `WPoAApplyMalus`. |
| [`../malus_registry.cpp`](../malus_registry.cpp) | Stream provisioning (open), confirmed-only reads, `ValidReport` and `ValidDataIntegrityReport`, the per-epoch fold, publication, the provisioning thread and the RPCs. |
