# Behavioural malus registry (`malus_record.h` + `malus_registry.{h,cpp}`)

> The second of the two registries wPoA maintains, and the deliberate mirror image of
> the first. Where [`stream-weight-registry.md`](stream-weight-registry.md) documents the
> **closed** stream that says how much a validator is worth, this one documents the
> **open** stream that records how it has behaved — and how the two are combined into the
> effective weight the proposer election actually consumes.

---

## 1. Why a second registry

The weight `w_i` on `wpoa-weights` is produced entirely outside the consensus: an ESG
score and a participation measure, computed by the weight-management layer
([`../../weight_engine/`](../../weight_engine/)) and published as an opaque number. That
layer has no view of how validator `i` behaves *on the wPoA protocol itself*. A validator
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
| Write policy | **CLOSED** — needs `wpoa-weights.write` | **OPEN** — anyone may publish |
| What it carries | a validator's weight | an accusation against a validator |
| Trust model | trust the *publisher* (authorized) | trust the *evidence* (re-verified) |
| Created in | `stream_weight_registry.cpp` | `malus_registry.cpp` |

The asymmetry is the whole design. A weight is a *claim* nobody can check — the value
comes from outside the chain, so the only defence is to restrict who may assert it. An
accusation, by contrast, is a *proof*: every node re-derives it from public chain data and
reaches its own verdict. Restricting who may accuse would buy nothing and would centralize
the one function that most benefits from being open — anyone who spots misbehaviour can
report it, and no privileged accuser is needed.

Opening the stream is therefore free in safety terms. A false, malformed or duplicated
report is discarded **identically on every honest node** (§4), so it never reaches the
accumulator and never moves anyone's weight. Spamming the stream costs the spammer
transaction fees and achieves nothing.

---

## 3. What can be reported, and why only these two

Two kinds, and no others, because these are exactly the misbehaviours a node can already
prove while validating a block. A report whose proof needed another validator's private
state or secret key could not be decided locally, which would break the property the open
stream rests on.

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

**What the mechanism does not cover.** Both proofs are self-referential to the accused's
own cryptographic evidence. Neither establishes that a given validator really did hold the
globally minimum score — that question is outside the reach of *any* local check, by
construction of the private sortition.

---

## 4. `Valid(e)` — the local decidability predicate

`MalusRegistry::ValidReport` is the gate that makes an open stream safe. It uses only the
primitives block validation already uses, and only public chain data:

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

Because every input is public and already agreed, two honest nodes always compute the same
verdict. The reporting RPC runs the same check *before* broadcasting, so a node never
spends a transaction on evidence its own peers would throw away.

---

## 5. Accumulation, and why exclusion is always temporary

A single proved violation must not exclude a validator for ever — an isolated event (a
transient bug, a mishandled restart) is not the same thing as a pattern. So the registry
accumulates an **exponential moving average**, not a counter:

```
M^(e) = mu * M^(e-1) + sum of p(kind) over the epoch's valid reports      (Def. 5.21)
Psi   = max(0, 1 - M / M_max)                                            (Def. 5.22)
```

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
> [protocol-parameters.md §3](protocol-parameters.md#3-catalogo--registro-del-malus-comportamentale).**

Two constraints are **hard failures** at startup, and both are structural rather than
stylistic:

1. **The registry requires private sortition.** Both evidence kinds are proved against
   the block's VRF reveal over the beacon seed, which only exists once sortition runs.
2. **`p(Equiv) > p(Delay)`.** An equivocation is a *safety* fault, a delay violation
   only a *scheduling* one; inverting the order would let the lighter fault dominate
   the accumulator.

---

## 9. RPC surface

| Command | What it does |
|---|---|
| `getallmalus` | `M`, `Psi`, raw weight, `w_eff`, exclusion flag and epochs-to-clear for every validator. |
| `getnodemalus "address"` | The same, for one validator. |
| `reportmalus "kind" "address" height "blockhash" ["blockhash2"]` | Publishes a report, after re-verifying it locally. |

---

## 10. Tests

- **Unit** ([`../test/wpoa_malus_tests.cpp`](../test/wpoa_malus_tests.cpp), node-free, run
  with `run_unit_tests.sh malus`): record parsing including both `OpReturnFormatEntry`
  wrappings and rejection of every malformed shape; the fold and its decay; `Psi` over its
  whole range; `w_eff`; the map-level transform; and reversibility — that an excluded
  validator becomes eligible again after exactly `EpochsToClear` clean epochs, for every
  `mu` in `(0,1)`.
- **Functional** ([`../test/functional_test_wpoa_system.sh`](../test/functional_test_wpoa_system.sh)):
  `check_stream_permissions` asserts the closed/open asymmetry and that it bites (an
  address without `wpoa-weights.write` cannot publish a weight, yet can publish a report);
  `check_malus` asserts the mechanism is inert on honest behaviour and that every node
  refuses false evidence — an honest block is not a delay violation, one block named twice
  is not an equivocation, and a block nobody has seen proves nothing.

---

## 11. Files

| File | Role |
|---|---|
| [`../malus_record.h`](../malus_record.h) | Pure core: record parsing, `Fold`, `CorrectionFactor`, `EffectiveWeight`, `EpochsToClear`, `ApplyToWeights`. Node-free and unit-tested in isolation. |
| [`../malus_registry.h`](../malus_registry.h) | The `MalusRegistry` facade, the runtime parameters and `WPoAApplyMalus`. |
| [`../malus_registry.cpp`](../malus_registry.cpp) | Stream provisioning (open), confirmed-only reads, `ValidReport`, the per-epoch fold, publication, the provisioning thread and the RPCs. |
