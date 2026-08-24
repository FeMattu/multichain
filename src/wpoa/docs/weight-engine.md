# Weight engine — on-chain derivation of validator weights

> **Register: technical-direct.** A reference for APIs, data structures, RPC flows and
> stream lifecycle. For the theoretical justification of the weight model see the thesis
> chapter *"Gestione del peso"*, summarised in
> [thesis-project-overview.md](thesis-project-overview.md).

The weight engine (`src/weight_engine/`) sits **above** the wPoA consensus
(`src/wpoa/`). Each epoch it reads a set of public on-chain input streams, computes the
per-cluster weight `w_k^{(e)}`, and publishes it to the **same** `wpoa-weights` stream
the consensus already consumes.

The two layers are coupled **only** through that stream: the consensus never learns *how*
`w_k` was produced. This separates weight-assignment policy from election mechanics, and
makes the `wpoa-weights` contract — `{address, integer weight > 0}` — the only interface
to preserve.

Configuration parameters: [protocol-parameters.md §4](protocol-parameters.md#4-catalogue--weight-engine).

---

## Table of contents

- [1. Why it exists](#1-why-it-exists)
- [2. The input streams](#2-the-input-streams)
- [3. The computation pipeline](#3-the-computation-pipeline)
- [4. The engine thread](#4-the-engine-thread)
- [5. Precedence: which publisher writes](#5-precedence-which-publisher-writes)
  - [5.1 Every node publishes its own weight, and every node checks the others](#51-every-node-publishes-its-own-weight-and-every-node-checks-the-others)
- [6. Security model — two independent gates](#6-security-model--two-independent-gates)
  - [6.1 On-chain gate](#61-on-chain-gate--consensus-enforced)
  - [6.2 Application gate — per stream, not uniform](#62-application-gate--per-stream-not-uniform)
  - [6.3 Why opening membership is safe](#63-why-opening-membership-is-safe--and-where-the-known-limit-still-bites)
  - [6.4 ESG — the Certification Authority role](#64-esg--the-certification-authority-role)
- [7. The complete flow](#7-the-complete-flow)
- [8. Threading](#8-threading)
- [9. Module files](#9-module-files)
- [10. References](#10-references)

---

## 1. Why it exists

wPoA elects proposers in proportion to weight. The question *where the weight comes from*
has no answer internal to consensus: it is a governance decision.

Two answers are implemented, mutually exclusive:

| | Weight source | When |
|---|---|---|
| **Static** | The per-node flag `-weight=<n>`, published verbatim | `-enableweightengine=0` (default) |
| **Dynamic** | `w_k` computed from the on-chain inputs, once per epoch | `-enableweightengine=1` |

The dynamic path is the one intended for real operation. The static path remains as a
fallback and for tests.

> **`-weight` is not the primary path.** With the engine on, the value of `-weight` is
> parsed, validated, written into `g_node_weight` and logged — and then **never
> published**. See [§5](#5-precedence-which-publisher-writes).

---

## 2. The input streams

The pipeline has **four inputs, but only two streams.** Two are *published* — and named
`weight-engine-*`, **not** `wpoa-*`, because they belong to the weight layer and its
actors (the certifier, the joining nodes themselves) rather than to consensus. The other
two are *derived*: read off the confirmed blocks, with no stream, no publisher and no
write permission at all. Only the **output** stream `wpoa-weights` belongs to wPoA. The
naming split mirrors the directory split.

> **Thesis alignment.** Figure 7.1 of the thesis describes a target permission model
> captioned as **not yet reflected by the implementation**: writes reserved to
> Certification Authorities on `weight-engine-esg`, own-record-only writes on
> `weight-engine-membership`, admin-reserved writes on `weight-engine-reconciliation`.
>
> The figure's caveat can now be **dropped entirely**, though the third row needs
> rewriting rather than ticking off:
>
> - **membership** is implemented as illustrated, strengthened with a cryptographic
>   self-attestation check ([§2.2](#22-membership-is-self-attested-and-the-key-is-the-declaring-node));
> - **ESG** is implemented as illustrated, through an explicitly delegated and revocable
>   CA role ([§6.4](#64-esg--the-certification-authority-role));
> - **reconciliation** has no writer to reserve: the stream is **gone** and `R_k` is
>   derived from the blocks ([§2.1](#21-activity-and-reconciliation-are-published-by-nobody)),
>   so its box becomes a chain-derived arrow like activity's. Likewise the figure's
>   `weight-engine-activity` box: that stream never existed as a mechanism.
>
> See [implementation-status.md §0.1](implementation-status.md#01-how-a-nodes-weight-is-assigned--the-authoritative-flow)
> and [adr/reconciliation-onchain.md §7](adr/reconciliation-onchain.md#7-divergence-from-the-thesis-text).

Definitions in [`weight_streams.h`](../../weight_engine/weight_streams.h).

**Published — two streams:**

| Stream | Item key | Payload | Origin | Who may write |
|---|---|---|---|---|
| `weight-engine-membership` | **node address** (declaring node) | `{"node_address":…, "miner_address":…, "timestamp":…}` | **The node itself**, via RPC | **Every node** (self-attested) |
| `weight-engine-esg` | node address | `{"node_address":…, "esg":…}` | **Certification Authority**, via RPC | Delegated certifiers only |

**Derived — no stream at all:**

| Quantity | Thesis | Source | Who may write |
|---|---|---|---|
| `tau_i^{(e)}` — activity counter | Def. 6.3 | the epoch's confirmed blocks | **nobody** |
| `R_k^{(e)}` — reconciled amount | Def. 6.7 | the epoch's confirmed blocks | **nobody** |

### 2.1 Activity and reconciliation are published by nobody

`tau_i^{(e)}` and `R_k^{(e)}` are both derived **directly from the confirmed blocks** of
the epoch, by `ComputeActivityAndReconciliationForEpoch()`
([`weight_reader.h`](../../weight_engine/weight_reader.h)). Both are deterministic
functions of those blocks, so every honest node recomputes the identical value: no
publisher, no duplicate-write risk, nothing to trust and nothing to misstate.

They are computed in **one shared pass**, not two. Both need the same traversal and the
same per-transaction fact — the set of addresses that signed the inputs, resolved from
undo data — so the marginal cost of reconciliation is a few comparisons per output inside
a scan that was happening anyway.

> **This changed.** `R_k^{(e)}` used to be an **administrator attestation** on a dedicated
> `weight-engine-reconciliation` stream: an admin stated how much a cluster had
> reconciled, and the pipeline took the number verbatim. That was an asymmetry with no
> justification — activity and reconciliation are *both* facts about confirmed
> transactions, and treating one as derived and the other as declared meant the feedback
> term depended on trusting one actor to state honestly a number the chain already
> recorded. The stream is **removed**.
>
> `weight-engine-activity` is removed too, for a different reason: it was a **name, not a
> mechanism** — defined in `weight_streams.h` but never created, never written and never
> read. Documentation describing "four input streams" and a stream "nobody writes" was
> describing that name.
>
> Full analysis, the option that was rejected and why:
> **[adr/reconciliation-onchain.md](adr/reconciliation-onchain.md)**.

#### What counts as a reconciliation transfer

`R_k^{(e)}` is the native-currency value paid to the **treasury address** by transactions
that miner `k` **signed**, among the confirmed transactions of epoch `e`.

- **Crediting the signer** — not any address appearing in the transaction — is what makes
  the direction unambiguous: a transfer *to* a miner is never mistaken for one *from* it,
  and the treasury paying somebody creates no reconciliation for the recipient.
- **Only outputs paying the treasury count.** A miner's own change output does not; nor
  does a transfer to a third party.
- **Non-monetary outputs never count.** An `OP_RETURN` carries no value and has no single
  destination, so a stream item or a notarisation can never register as a reconciliation.
- **The treasury paying itself is excluded**, so a refund or rebalancing cannot inflate
  any cluster's compliance.
- **Fees are excluded**: they go to the block's miner, not to the treasury.
- **Integer accumulation.** Values are summed in base units as `int64` and converted once
  at the end of the epoch, so the total carries no floating-point rounding of its own.

The rules live in the pure layer (`mc_ValuePaidToTreasury`,
`mc_AccumulateReconciliation` in [`weight_records.h`](../../weight_engine/weight_records.h))
and are unit-tested there; only the traversal needs the block layer.

#### The treasury address is a chain parameter

`weight-treasury-address` (`-weighttreasuryaddress`), hash-enforced like every other
weight-engine parameter — necessarily so, because the value of `R_k` depends on it and two
nodes disagreeing about it would compute different weights and fork.

Deriving it implicitly from *"who holds `admin`"* was rejected: the admin set is
**mutable**, so a node re-syncing after a grant or revocation would attribute a historical
epoch differently than the network did at the time. That is the same
retroactive-mutability hazard that keeps the Certification Authority check out of the ESG
reader ([§6.4](#64-esg--the-certification-authority-role)).

**Unset is legal** and means `R_k = 0` for every cluster, on every node — exactly the old
behaviour on a chain where nobody published reconciliation records. By Def. 6.8 a
uniformly zero `R` gives `rho_k = 0`, and by Def. 6.9 `w_k = W_k * (1 - lambda)`: a
uniform scaling that leaves the *relative* weights, and therefore the election, unchanged.

#### The same stability margin, for the same reason

Reconciliation obeys the identical buried-epoch guard as activity: the epoch's last block
must sit at least `MC_WEIGHT_DEFAULT_STABILITY_MARGIN` below the tip
([§3.2](#32-epochs-and-the-stability-margin)). Both are read from the same snapshotted
block range in the same pass, so a shallow reorg near the tip cannot make two nodes read
different blocks for either quantity.

### 2.2 Membership is self-attested, and the key is the declaring node

Joining a miner's cluster is a **voluntary and autonomous** decision of the joining node —
it is not something governance assigns. The stream reflects that directly.

**The validity rule (consensus-critical).** A membership record is valid **if and only if
the address that signed the publishing transaction equals the `node_address` declared in
the payload.** The publisher is the transaction's *signature*, not a payload field, so the
claim is self-verifiable: nobody can declare membership on another node's behalf. A record
that fails the test is **discarded** by the reader — it does not enter `C_k` and produces
no side effect of any kind. Not flagged, not down-weighted: discarded.

The rule lives in one place, `mc_MembershipRecordIsSelfAttested`
([`weight_records.h`](../../weight_engine/weight_records.h)), so the reader that discards
and any verifier that accuses apply an identical predicate. The signing addresses are
recovered from the transaction's input scripts exactly as MultiChain's own
`StreamItemEntry` does (`WeightStreamItem::publishers`).

**Indexing: the key is `node_address`, no longer the miner.** This changed, and the reason
is that a node must be able to **change cluster at any time**. The relation
`node_address -> miner_address` is therefore mutable and single-valued per declaring node,
and needs *last-confirmed-wins* semantics per node — exactly like `wpoa-weights`. Keying on
`node_address` puts all of a node's successive declarations under one key, so a
chronological scan of the confirmed items yields its current cluster and the superseded
ones simply drop out.

> **Why the old scheme could not express a cluster change.** Membership used to be keyed by
> *miner* and reconstructed through MultiChain's native `jsonobjectmerge`
> (`getstreamkeysummary` / `mc_MergeValues`), whose merge is **additive**: a company
> appeared as a field name under its miner's key and stayed there for ever. A node that
> moved from miner A to miner B would show up in **both** clusters, with no way for the
> merge to retract the first membership. The additive merge was fundamentally incompatible
> with a mutable relation, which is why the indexing had to change rather than be patched.

`C_k` is now rebuilt in two pure steps
([`weight_records.h`](../../weight_engine/weight_records.h)):

1. `mc_AccumulateLatestMembership` folds the chain-ordered items into
   `node_address -> miner_address`, newest confirmed winning;
2. `mc_BuildClustersFromMembership` inverts that into `miner -> C_k`, filtering by
   `miner_address == k`.

Two rules in the inversion, both deliberate:

- **A miner's self-declaration registers it as a cluster head.** A miner calls the RPC with
  its *own* address; that is what puts its key in the map, and what
  `ComputeLocalWeightForEpoch` tests before publishing a weight. A registered head with no
  members yet has a legitimately empty `C_k`.
- **A miner is never listed among its own companies.** Its activity already enters the raw
  weight through the separate `tau_Mk` term of
  `W_k = ESG_Mk * ( tau_Mk + sum_{i in C_k} c_i )`; also counting it as a company `i` would
  double-count it.

### 2.3 Stream lifecycle

`WeightStreamReader::EnsureInputStreams()` **creates** missing streams and **subscribes**
to them: the first node with create permission (the genesis / admin node) brings them into
existence, everyone else finds them present and subscribes.

The streams are created **CLOSED**: `MC_PTP_WRITE` is required to publish. Closed does not
mean *governance-only* — see [§6.2](#62-application-gate--per-stream-not-uniform) for which
streams grant write narrowly and which grant it to the whole network.

---

## 3. The computation pipeline

Implemented verbatim from the thesis chapter *"Gestione del peso"* in
[`weight_engine.h`](../../weight_engine/weight_engine.h), which is a **pure** core: it
depends only on the C++ standard library, so it is testable in isolation.

```
c_i^(e)   = ESG_i * tau_i^(e) / kappa                            (weighted contribution)
W_k^(e)   = ESG_Mk * ( tau_Mk^(e) + sum_{i in C_k} c_i^(e) )     (raw weight)
A_k^(e)   = alpha * Theta^(e) * W_k^(e) / W_tot^(e)              (allocation)
rho_k^(e) = R_k^(e) / ( A_k^(e) + B_k^(e-1) )  in [0,1]          (compliance rate)
B_k^(e)   = A_k^(e) - R_k^(e) + B_k^(e-1),  B_k^(0) = 0          (reconciliation)
w_k^(1)   = W_k^(1)                                              (final weight, e = 1)
w_k^(e)   = W_k^(e) * [ rho_k^(e-1) * lambda + (1 - lambda) ]    (e >= 2)
```

The final integer weight is `ToIntegerWeight(w_k)`, always `>= 1` — the weight-positivity
requirement, and also the Efraimidis–Spirakis requirement
([`wpoa_selector.h`](../wpoa_selector.h)).

> **`R_k^(e)` is chain-derived, not declared.** The formula is unchanged and `R_k` is
> still clamped to `[0, A_k + B_{k-1}]`, but the value now comes from the epoch's
> confirmed transfers to the treasury rather than from an administrator's statement
> ([§2.1](#21-activity-and-reconciliation-are-published-by-nobody)). This is the one
> point where the implementation's **source** for a Cap. 6 quantity differs from what the
> thesis text describes; the proposed wording is in
> [adr/reconciliation-onchain.md §7](adr/reconciliation-onchain.md#7-divergence-from-the-thesis-text).

### 3.1 Consensus-critical determinism

`w_k` governs proposer election, so **every honest node must compute the same integer**.
Four explicit choices guarantee it:

1. **Double precision** throughout, matching the selector core (`ScoreFromEntropy64`),
   which already treats IEEE-754 `double` as deterministic across the identical-binary
   validator set.
2. **Sums taken in ascending address order** — both `sum_i c_i` and `W_tot`. Floating
   point is not associative: without a fixed order the result would depend on input
   order.
3. **A denominator `<= 0` in `rho` yields `0`**, never `NaN`/`Inf`. This is the
   degeneration that propagated `#DIV/0!` through the reference simulation; the thesis
   form with `lambda < 1` avoids it by construction.
4. **`ToIntegerWeight`** rounds half-away-from-zero and clamps to `[1, UINT32_MAX]`.

### 3.2 Epochs and the stability margin

The epoch is **1-based**:

```
epoch(height) = height / g_weight_epoch_length + 1
```

`HeightToEpoch()` in [`weight_engine.cpp`](../../weight_engine/weight_engine.cpp). The
same function is reused by the malus registry to align epochs
([malus-registry.md](malus-registry.md)).

An epoch is computed **only once it is buried**: its last block must sit at least
`MC_WEIGHT_DEFAULT_STABILITY_MARGIN` (currently `6`) blocks below the chain tip. Because
**both** `tau` and `R` are derived from the epoch's confirmed blocks — from the same
snapshotted range, in the same pass — this prevents a shallow reorg near the tip from
making two nodes read different blocks for either quantity.

> The margin is a compile-time constant, not a chain parameter. The code itself recommends
> promoting it to a hash-enforced parameter before production, alongside
> `weightepochlength`. See
> [protocol-parameters.md §4](protocol-parameters.md#4-catalogue--weight-engine).

### 3.3 Relation to the selector — three distinct levels

The weight engine produces the **raw** weight `w_k`. The whale compression `f(w_k)`
(`WPoASelector::ApplyDumping`, governed by `-dumpfunction`) is applied **downstream**, at
election time, and so is the malus correction `w_eff = w * Psi`.

```
w_k  (engine)  ->  wpoa-weights  ->  w_eff = w * Psi  (malus)  ->  f(w_eff)  (dumping)  ->  election
```

The three levels are complementary and must be kept distinct in diagrams: `w_k` is not the
value the draw operates on.

### 3.4 Deliberate divergence from the reference simulation

This core follows the **thesis**, which defines the allocation `A_k` on the **raw** weight
`W_k`. The reference `Vers_2` simulation instead derives its *"GuadagnoEx"* entry from the
normalised, feedback-adjusted weight.

The two formulations **coincide** for epoch 1 and for `W_k` in every epoch, but the
allocation-derived quantities (`A_k`, `rho_k`, `B_k`) can diverge from epoch 2 onwards. The
thesis form is used deliberately: allocation tracks certified and current merit (`W_k`),
avoiding a feedback-on-feedback loop.

---

## 4. The engine thread

`ThreadWeightEngine()` in
[`weight_engine.cpp`](../../weight_engine/weight_engine.cpp), launched from `AppInit2`.

The loop, on each iteration:

1. waits for the wallet, permissions and connectivity to be ready, and for the initial
   block download to finish (the same gate as the wPoA thread);
2. calls `reader.EnsureInputStreams()` — creates the two missing published streams and
   subscribes;
3. identifies the **latest buried epoch**;
4. computes `w_k` **only for its own** miner address, and only if the local node is itself
   a cluster miner (`ComputeLocalWeightForEpoch`: if
   `clusters.find(local_miner) == clusters.end()`, there is nothing to publish);
5. publishes through the shared registry path, which ensures `wpoa-weights` exists and
   keeps the write idempotent;
6. sleeps `MC_WEIGHT_RETRY_INTERVAL_MS` and repeats.

A node not yet certified, with incomplete inputs, or whose epoch is not yet buried, simply
does not publish: no error, no partial value.

---

## 5. Precedence: which publisher writes

**Two publication MODES, one per node — not one publisher per cluster.** The name of this
section is about which of a node's *own* two publication paths runs, and that is still an
exclusive choice made once at startup. It has never meant "one node publishes for
everybody": each node has always published only its **own** cluster's weight
(`ComputeLocalWeightForEpoch` returns nothing when the local address heads no cluster). What
changed is that this is now **enforced and verifiable** rather than merely conventional —
see [§5.1](#51-every-node-publishes-its-own-weight-and-every-node-checks-the-others).

There is no runtime overwrite. In `AppInit2`, at the end of the wPoA block
([`init.cpp`](../../core/init.cpp)):

```cpp
if (g_wpoa_weights_enabled && pwalletMain && pwalletTxsMain && !fDisableWallet)
{
    if (g_weight_engine_enabled)
        threadGroup.create_thread(boost::bind(&ThreadWeightEngine));                     // dynamic w_k
    else
        threadGroup.create_thread(boost::bind(&ThreadRegisterNodeWeight, g_node_weight)); // static weight
}
```

The difference is **observable**: with the engine on, `-weight=500` does not produce a
record that is later superseded — it produces **no** record.

Both paths write the same stream. Reads are **newest-confirmed-wins**
(`mc_AccumulateLatestWeight`, [`weight_record.h`](../weight_record.h)), so consensus is
indifferent to which of a node's two paths produced the record.

### 5.1 Every node publishes its own weight, and every node checks the others

`wpoa-weights` stays **CLOSED**, but `.write` is now meant to be granted to **every**
node, not to one designated publisher per cluster. Two rules make that safe, and they are
worth separating because they answer different questions and fail in opposite directions.

#### Rule 1 — self-publication: *who* wrote it

A weight record is valid **only if the address that signed the publishing transaction is
the `node_address` the payload declares.** A record naming another cluster is **discarded**
by `DecodeWeightRecord` ([`stream_weight_registry.cpp`](../stream_weight_registry.cpp)):
it never reaches the weight map, so no node can publish a weight on another cluster's
behalf.

The rule is the *same predicate* the membership stream uses —
`mc_StreamItemIsSelfAttested` in [`weight_record.h`](../weight_record.h) — with one
implementation shared by both layers. Two copies of a consensus-critical predicate could
drift into a node discarding a record it does not accuse, or accusing one it does not
discard.

> **Consequence for the publisher: `publishfrom`, not `publish`.** `PublishWeightRecord`
> now names its own address explicitly. Plain `publish` lets the wallet choose whichever
> address funds the transaction, which on a multi-address wallet need not be the node's
> own — the record would be perfectly well-formed and silently discarded by every peer.
> This is not cosmetic; it is what makes the rule satisfiable.

It **fails closed**: an item whose signer cannot be recovered is rejected. The evidence —
one transaction — is always available, so its absence means the record is undecodable.

#### Rule 2 — universal verification: whether the *value* is right

Rule 1 establishes who wrote a record, not whether the number is correct. On its own it
would replace *"trust one publisher per cluster"* with *"trust every publisher"*: a miner
could publish any value it liked for its own cluster.

But the value is now checkable, because **every input of the pipeline is public and
deterministic**: `tau` is chain-derived, `C_k` is chain-derived from self-attested records,
`R_k` and `ESG` are published. So any honest node can re-run the identical pipeline over
the identical inputs and reach the identical integer. A published value that differs is
**provably wrong** — not a matter of opinion — and every node can reject it independently,
with no coordination and no privileged auditor. Implementation:
[`weight_verifier.h`](../../weight_engine/weight_verifier.h) /
[`.cpp`](../../weight_engine/weight_verifier.cpp), reported by the
`weightverifyweights` RPC.

The comparison is **exact integer equality**, which is safe precisely because of the
determinism disciplines of [§3.1](#31-consensus-critical-determinism). A tolerance band
would only create a margin for a dishonest publisher to hide in.

**A weight is compared only against its own epoch's recomputation.** Each record carries
the epoch it was computed for, and one about a different epoch — or about none, as with
the static `-weight` path — is reported as `other-epoch` and left untouched. This is not
a nicety: without it, a value legitimately published for epoch `e` would be flagged as
wrong the moment epoch `e+1` arrived, and the malus would turn that false accusation into
a real weight penalty. (It was observed in a live run before the epoch field existed: an
honest node's own weight was reported as failing verification on every epoch rollover.)

Because publication necessarily **lags** the epoch it describes — a node can only compute
`w_k^{(e)}` once epoch `e` is buried, so its record lands during `e+1` — verification
targets the **previous** epoch: at epoch `e` it checks the records for `e-1`, by which
time every honest node has had a full epoch to publish. That is the same inter-epoch
alignment the rest of the system uses (`rho^{(e-1)}` drives `w^{(e)}`; a proved malus
takes effect from the epoch after).

Two consequences, both deliberate:

- **A node whose weight did not change publishes nothing** (`RegisterLocalWeight` is
  idempotent), so it is simply not compared that round. Correctly so: there is no new
  claim to check, and its previous record was checked when it was made.
- Verification therefore catches every **dishonest publication**, not every node every
  epoch — which is the right target. To gain from a wrong weight a node must *publish*
  it, and any publication it makes is epoch-stamped and gets compared. A node that stops
  publishing keeps its last confirmed weight, which is pre-existing behaviour of the
  newest-confirmed-wins stream rather than something this mechanism introduces.

It **fails open**, deliberately and unlike Rule 1: verification needs readable inputs and
a **buried** epoch, and their absence is entirely normal (a node still syncing, an epoch
not yet buried). Treating *"cannot verify"* as *"invalid"* would zero every weight on such
a node and stall the chain. Only a recomputation that **succeeded and disagreed** is a
finding.

#### ESG is the one input that cannot be recomputed

Verification establishes that a publisher applied the pipeline **honestly to the published
inputs**. It cannot establish that the ESG scores are *truthful*, because an ESG score is
an attestation with nothing inside it to check.

So after this change the trust surface of the whole system is exactly one datum: **ESG**.
Activity and membership are chain-derived, reconciliation is published and verifiable
alongside the rest, and every published weight is recomputable. The integrity of the
weights therefore rests entirely on the Certification Authority role of
[§6.4](#64-esg--the-certification-authority-role).

#### Complexity: O(clusters) per epoch instead of O(1)

Trusting a publisher blindly costs nothing; verifying every cluster costs one full
pipeline recomputation per epoch. The trade is accepted deliberately: it is the price of
removing the implicit trust in a per-cluster publisher, and without it opening `.write` to
every node would be strictly worse than the model it replaces.

The marginal cost is much smaller than O(clusters) suggests.
`WeightEngineComputeAllWeightsForEpoch` **already** folds the pipeline across every
cluster — it always did, because `ComputeEpoch` needs `W_tot` and so cannot evaluate one
cluster in isolation; the previous code computed the whole map and used a single entry.
Verification adds a map comparison to work already performed.

What *would* be prohibitive is verifying in the consensus hot path.
`GetAllNodesWeights()` is called by the miner and every validator on **every round**,
while recomputation folds forward from epoch 1 and scans each epoch's blocks — O(chain)
work. So verification runs **once per buried epoch**, inside `ThreadWeightEngine` where
the fold already happens, and caches its verdicts; the consensus path consults the cache
in O(1).

#### Where the consequence of a violation reaches consensus

The two rules take effect by different routes, matching what each is decidable from.

**Rule 1's discard is immediate**, enforced in the reader, because it is decidable from a
single transaction: a record whose signer is not its subject never enters the weight map on
any node.

**Rule 2's consequence travels through the malus registry** — the mechanism already in the
consensus path as `w_eff = w * Psi`
([§3.3](#33-relation-to-the-selector--three-distinct-levels)), whose whole purpose is to
carry *provable* findings into the election. A mismatch is not silently absorbed: it is
detected, logged unconditionally, exposed by `weightverifyweights`, and reportable as a
**`badweight`** malus that every node re-derives by re-running the same pipeline. A forged
record — Rule 1's discard — is likewise reportable, as **`selfwrite`**, so the attempt has
a price even though it changed nothing.

Both malus kinds are verified as *proofs*, never judgements, exactly like an equivocation:
[malus-registry.md §3](malus-registry.md#3-what-can-be-reported-and-why-only-these). The
routing is deliberate rather than incidental — a per-round recomputation in the consensus
read path would be O(chain) per call, whereas the malus is already consulted there and
already carries per-epoch findings.

---

## 6. Security model — two independent gates

This is the part to read carefully: the two gates are distinct and protect different
things.

### 6.1 On-chain gate — consensus-enforced

Every stream involved — the two published input streams and `wpoa-weights` — is
**CLOSED**. Only an address holding `MC_PTP_WRITE` on the stream can publish. This is what blocks arbitrary
writes, and it is enforced by MultiChain's granular permissions, not by convention.

```bash
multichain-cli <chain> grant <address> wpoa-weights.write
multichain-cli <chain> grant <address> weight-engine-esg.write
```

A node without the permission sees its publish fail and **does not appear in the weight
map: it carries no weight in the election.**

> **An unauthorized node cannot impose its own weight by any means** — not through
> `-weight`, not through RPC, not by publishing directly.

**Closed is not the same as governance-only.** All streams stay closed, but *who* the
`.write` permission is granted to now differs per stream, and that is the substance of the
authorization model:

| Stream | `.write` granted to | Why |
|---|---|---|
| `weight-engine-membership` | **every node on the network** | Records are self-verifiable: a write permission lets a node speak about *itself* and nothing more. |
| ~~`weight-engine-reconciliation`~~ | **removed** | `R_k` is derived from the blocks; there is no stream to grant. |
| `weight-engine-esg` | **Certification Authorities only** | An unverifiable external attestation about a third party. See [§6.4](#64-esg--the-certification-authority-role). |
| `wpoa-weights` | **every node** | The record is self-published *and* the value is independently recomputable — the only input class that is verifiable on both counts. See [§5.1](#51-every-node-publishes-its-own-weight-and-every-node-checks-the-others). |

For membership, network admission is still gated — but **upstream**, by the KYC-backed
`connect` permission that governs joining the network at all. Once a node is a legitimate
member of the consortium, letting it state which cluster it belongs to adds no privilege.

### 6.2 Application gate — per stream, not uniform

The two published inputs do **not** share one authorization model. The split follows a
single criterion: **can a third party verify the claim?**

The pipeline's other two inputs raise no authorization question at all, because nobody
writes them: `tau` and `R` are derived from the blocks
([§2.1](#21-activity-and-reconciliation-are-published-by-nobody)). Removing the
reconciliation stream removed an authorization surface rather than reassigning it.

| RPC (category `weight`) | Stream written | Caller | Payload |
|---|---|---|---|
| `weightsetesg` | `weight-engine-esg` | **Certification Authority only** | `{node_address, esg}`, `esg > 0` |
| `weightregistermembership` | `weight-engine-membership` | **any node** | key `node_address`, payload `{node_address, miner_address, timestamp}` |

Registered in [`rpclist.cpp`](../../rpc/rpclist.cpp). Each method, **before** publishing:

1. validates the record in **round-trip** with the *same* W1 parser the reader uses
   (`mc_Parse*RecordJson`) — so it cannot emit a malformed record the reader would
   reject;
2. applies its authorization rule
   ([`weight_authorization.h`](../../weight_engine/weight_authorization.h) holds the
   decision tables as pure functions; the on-chain lookups live in
   [`weight_publisher.cpp`](../../weight_engine/weight_publisher.cpp)):
   `IsCertificationAuthority` for ESG, and **none at all** for
   `weightregistermembership` — it takes no parameter naming *whose* membership to
   declare, so it structurally cannot write about anyone but the caller. There is no
   remaining write path in this module that requires global `admin`;
3. verifies that the address has write permission on the stream;
4. publishes **from** that address.

Any failure raises `JSONRPCError`, so the calling RPC returns a precise error.

> **`weightsetmembership` is gone, not deprecated.** The old admin-proxy RPC published a
> membership record *on a third party's behalf*. Under the self-attestation rule such a
> record is discarded by every reader — the signer would be the admin, the declared
> `node_address` the company. Keeping the RPC would only have offered a way to pay for a
> transaction with no effect, so it was removed and replaced by
> `weightregistermembership`.

### 6.3 Why opening membership is safe — and where the known limit still bites

The two write policies rest on opposite foundations, and the reason is the same asymmetry
the malus registry is built on ([malus-registry.md §2](malus-registry.md)):

| | ESG / reconciliation | membership |
|---|---|---|
| The record is | a **claim** about a third party | a **self-declaration** |
| Verifiable by a third party? | **No** — an ESG score is an attestation of trust | **Yes** — compare the signer to the declared address |
| Therefore the defence is | restrict **who** may assert it | check **the assertion itself** |
| Write policy | narrow grant | grant to everyone |

Because the membership rule is enforced against the transaction's **signature** rather than
against the writer's **privileges**, it cannot be bypassed by any route. A forged record —
one naming a `node_address` other than its signer — is discarded identically on every
honest node, whether it came from `weightregistermembership`, from the generic
`publishfrom`, or from a raw transaction. Opening the write is free in safety terms, exactly
as opening the malus stream is.

**The known limit survives, narrowed to a single stream.** Write permission is an
**independent** grant from the role check, and for ESG the reader still **trusts any
schema-valid confirmed record, regardless of its publisher**.

> For `weight-engine-esg`, the role guarantee holds **only if** operators grant
> `weight-engine-esg.write` **exclusively** to the intended certifiers. An address that
> has been granted `.write` without holding the role could publish a schema-valid but
> **forged** record using the generic `publishfrom` rather than `weightsetesg`, and the
> reader would accept it. Granting that `.write` **is** the security control, and must be
> treated as such.
>
> It applies to **nothing else**. `weight-engine-membership` is not exposed to it (its
> validity rule is cryptographic, not privilege-based), `wpoa-weights` is not
> ([§5.1](#51-every-node-publishes-its-own-weight-and-every-node-checks-the-others)), and
> `tau` and `R` are not, because they have no writer to impersonate.

### 6.4 ESG — the Certification Authority role

An ESG score cannot be verified by a peer at all. It is produced by an external
certification process — documentary review, compliance questionnaires, audit by a
third-party body or by the network operator (thesis Def. 6.1) — and there is simply no
assertion inside the record for a node to check. **The only available defence is to
restrict rigidly who may assert it, not to validate what is asserted.**

Restricting it to the *global administrator*, as the code originally did, conflates two
different competences: running the network and signing a sustainability certification.
Under that model every certifier must hold full chain-administration power, and nothing on
chain distinguishes the two roles. So the writer is now a **Certification Authority** — a
role the administrator delegates explicitly, per address, and can revoke.

```bash
multichain-cli <chain> grant  <address> high1     # confer CA status (requires admin)
multichain-cli <chain> revoke <address> high1     # withdraw it
multichain-cli <chain> grant  <address> weight-engine-esg.write
```

**Being a global administrator is not sufficient**, and that is the point. The
administrator *confers* the role; it does not hold it automatically. An admin that also
wants to certify grants itself `high1` explicitly, which keeps the two roles separately
visible in `listpermissions`.

#### Why a fixed custom permission slot

MultiChain has **no arbitrary named custom permission**: there is no
`grant <addr> custom.certauth`. It offers exactly six **fixed** slots
([`permission.h`](../../permissions/permission.h)): `low1`–`low3` (`MC_PTP_CUSTOM1..3`) and
`high1`–`high3` (`MC_PTP_CUSTOM4..6`). The role therefore occupies one of them, and it
**must be a high slot**:

> `mc_Permissions::IsActivateEnough` returns `0` for the high slots
> ([`permission.cpp`](../../permissions/permission.cpp)), so granting one requires
> `admin` and not merely `activate`. That is precisely the requirement that **only the
> administrator may confer CA status**. The low slots are grantable by any `activate`
> holder and would silently weaken it.

The wire name is defined once, as `MC_WEIGHT_CA_PERMISSION_NAME` in
[`weight_authorization.h`](../../weight_engine/weight_authorization.h), and the permission
*bit* is derived from that name at runtime through MultiChain's own `GetPermissionType`
parser — so the name shown in an error and the bit actually queried cannot drift, and
moving the role to another slot is a one-line change.

> **Operational note.** Because the slot is one of six fixed ones, a deployment already
> using `high1` for an application-level RBAC role must move that role to a different
> slot, or it would be indistinguishable from CA status.

#### Revocation, and what it does not require

Revocation takes effect immediately and **independently of `.write`**: an address whose
`high1` was revoked is refused even while it still holds `weight-engine-esg.write`. The two
grants are independent, and the CA check does not wait for `.write` to be withdrawn.

Revoking `.write` as well is still **recommended**, for a different reason: it closes the
raw `publishfrom` route of [§6.3](#63-why-opening-membership-is-safe--and-where-the-known-limit-still-bites).
A revoked CA that keeps `.write` can no longer use `weightsetesg`, but could still land a
schema-valid record directly. So a complete revocation is both:

```bash
multichain-cli <chain> revoke <address> high1
multichain-cli <chain> revoke <address> weight-engine-esg.write
```

#### This gate is not consensus-critical — deliberately

The CA check gates **local publication only**. The reader still accepts any schema-valid
confirmed ESG record regardless of publisher, exactly as before. Two nodes that disagree
about who is a CA therefore disagree only about whether their *own* RPC will publish: they
compute the same weights and cannot fork.

That is why the CA slot is a compile-time constant rather than a hash-enforced chain
parameter — making it inheritable would imply a consensus role it does not have. See
[protocol-parameters.md §4.1](protocol-parameters.md#41-no-parameter-governs-who-may-write-the-input-streams).

**Why the reader does not also enforce the role.** It would close the `publishfrom`
bypass, and it was considered and rejected: permissions are **mutable**, so a later
revocation would retroactively invalidate historical records and change already-computed
epoch weights. A node re-syncing after a revocation would fold a different history than
the one the network folded at the time — a determinism hazard worse than the limit it
removes. Membership does not have this problem precisely because its rule is a fact about
a transaction (who signed it), which is immutable, rather than a fact about current
permission state.

#### Why ESG does not adopt the self-write of membership

Membership is self-attested because a node declaring *its own* cluster makes a claim that
is checkable — compare the signer to the declared address. ESG is the opposite: a node
declaring its own ESG score would be asserting exactly the quantity it benefits from
inflating, with nothing to check it against. Self-write is safe **only** where the claim is
self-verifiable.

This makes ESG the single remaining **trusted** input in the whole pipeline. Every other
input is either chain-derived (`tau`, `R`) or self-verifiable (membership,
`wpoa-weights`), so the integrity of the weights rests entirely on the CA role and on the
grant discipline of [§6.3](#63-why-opening-membership-is-safe--and-where-the-known-limit-still-bites).

---

## 7. The complete flow

The diagram of the weight-assignment flow — from the two authorization gates through to
proposer election — lives in **one place**, so that two copies cannot diverge:

> **[implementation-status.md §0.1 — How a node's weight is assigned](implementation-status.md#01-how-a-nodes-weight-is-assigned--the-authoritative-flow)**

That diagram shows explicitly that the authoritative channel is an RPC write to the
on-chain stream by an already-authorized node, that the on-chain value takes precedence
over the local `-weight` flag, and that an unauthorized node cannot impose its own weight
by any route.

---

## 8. Threading

Every read uses the low-level, self-locking **non-WRP** wallet API and **confirmed** items
only — never the `WRP*` / `getstreamkeysummary` family, which returns stale data off the
owning thread (see the note in
[stream-weight-registry.md](stream-weight-registry.md)).

`ComputeActivityForEpoch` reads the block/undo files off-thread, taking `cs_main` only for
a minimal chain snapshot.

---

## 9. Module files

| File | Role |
|---|---|
| [`weight_streams.h`](../../weight_engine/weight_streams.h) | W1: stream names, JSON field names, parameter defaults. No logic. |
| [`weight_records.h`](../../weight_engine/weight_records.h) | W1: pure record parsers (`mc_Parse*RecordJson`), the self-attestation predicate and the cluster inversion. Testable in isolation. |
| [`weight_authorization.h`](../../weight_engine/weight_authorization.h) | W1: the pure per-stream write policy — the Certification Authority decision table and the CA role's wire name. No node dependency. |
| [`weight_engine.h`](../../weight_engine/weight_engine.h) | W2: the pure computation core. Standard library only. |
| [`weight_engine.cpp`](../../weight_engine/weight_engine.cpp) | W3: `HeightToEpoch`, `ThreadWeightEngine`, node glue, configuration globals. |
| [`weight_reader.h`](../../weight_engine/weight_reader.h) / [`.cpp`](../../weight_engine/weight_reader.cpp) | W3: `WeightStreamReader` — lifecycle of the two published streams, confirmed reads with publisher extraction, and the single-pass `ComputeActivityAndReconciliationForEpoch`. |
| [`weight_publisher.h`](../../weight_engine/weight_publisher.h) / [`.cpp`](../../weight_engine/weight_publisher.cpp) | W3: the single validated write path, the CA-gated ESG RPC, the admin reconciliation RPC and the public self-write membership RPC. |
| [`weight_verifier.h`](../../weight_engine/weight_verifier.h) / [`.cpp`](../../weight_engine/weight_verifier.cpp) | Universal verification of the published weights: the pure compare/filter, the per-epoch verdict cache and the `weightverifyweights` RPC. |

### 9.1 Tests

The module has its **own** unit suites, with a runner separate from the wPoA one:

```bash
./src/weight_engine/test/run_unit_tests.sh                    # every suite
./src/weight_engine/test/run_unit_tests.sh authorization      # one only
```

| Suite | File | Coverage |
|---|---|---|
| `records` | [`weight_records_tests.cpp`](../../weight_engine/test/weight_records_tests.cpp) | The chain-derived **reconciliation rules** (only treasury-paying outputs count; third parties, change and non-monetary outputs excluded; the signer is credited so a transfer *to* a miner never counts as one *from* it; treasury self-payment excluded; multi-transaction aggregation; order independence across nodes). Record parsing; the **self-attestation rule** (own declaration accepted, foreign / admin-proxy declaration rejected, fail-closed on an unrecoverable signer); cluster inversion, including a node changing cluster twice so only the last declaration counts, and the no-self-membership rule. |
| `authorization` | [`weight_authorization_tests.cpp`](../../weight_engine/test/weight_authorization_tests.cpp) | The ESG write decision table: CA authorized; **global admin without the role refused**; generic address refused; revocation biting while `.write` remains; CA lacking `.write`; CA-first error ordering; fail-closed on a chain without custom permissions; and that the role sits in a `high*` slot. |
| `verifier` | [`weight_verifier_tests.cpp`](../../weight_engine/test/weight_verifier_tests.cpp) | Matching values accepted; an inflated **and** an understated value rejected and dropped from the map; off-by-one rejected (no tolerance band); a weight published for a non-cluster rejected with its own reason; **fail-open** when the recomputation was unavailable, including a partial map; two honest nodes reaching identical verdicts and identical filtered maps. |
| `engine` | [`weight_engine_tests.cpp`](../../weight_engine/test/weight_engine_tests.cpp) | Order independence, zero-total guard, `rho` bounds, balance recursion, weight positivity, `ToIntegerWeight` clamp, multi-cluster allocation identity. |

Both are node-free: they do not require building the node. See [testing.md](testing.md).

---

## 10. References

- [CHANGELOG-weight-engine-refactor.md](CHANGELOG-weight-engine-refactor.md) — the
  permission model of every stream before and after, and the thesis passages needing an
  update.
- [adr/reconciliation-onchain.md](adr/reconciliation-onchain.md) — why `R_k^(e)` became
  chain-derived, the option that was rejected, and the thesis wording it supersedes.
- [protocol-parameters.md](protocol-parameters.md) — the engine's parameters, with ranges
  and validation.
- [stream-weight-registry.md](stream-weight-registry.md) — the `wpoa-weights` stream and
  its read API.
- [malus-registry.md](malus-registry.md) — the malus registry, which reuses
  `HeightToEpoch`.
- [implementation-status.md](implementation-status.md) — implementation status.
