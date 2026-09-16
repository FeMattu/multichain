# ADR — `R_k^(e)` becomes chain-derived, and the reconciliation stream is removed

> **Status:** accepted, implemented.
> **Scope:** `weight-engine-reconciliation`, `weight-engine-activity`, `R_k^(e)`
> (thesis Def. 6.7), `tau_i^(e)` (Def. 6.3).
> **Register: technical-direct.** Decision record: the problem, the options weighed, the
> decision and its consequences. Module reference: [../weight-engine.md](../weight-engine.md).

---

## 1. The problem

`R_k^(e)` — how much of its allocation a cluster actually reconciled, i.e. returned to
the network operator in epoch `e` — was an **administrator attestation**: an admin
called `weightsetreconciliation` and the stated number entered the weight pipeline
verbatim.

That left an **asymmetry with no justification**. Both of the pipeline's dynamic inputs
are facts about confirmed transactions:

| Input | What it actually is | How it was obtained |
|---|---|---|
| `tau_i^(e)` | transactions signed by `i` in the epoch | **derived** from the epoch's confirmed blocks |
| `R_k^(e)` | currency transferred from `k` to the operator in the epoch | **asserted** by an admin |

Both are recoverable from the same blocks. Treating one as a fact and the other as a
claim meant:

- the pipeline's feedback term depended on trusting a single actor to state honestly a
  number the chain already recorded;
- that actor could understate a competitor's reconciliation — depressing `rho_k^(e-1)`
  and hence `w_k^(e)` — or overstate its own, and no node could contradict it, because
  the stream carried no link to the transfers it described;
- the record could contradict the ledger outright: the [experimental harness's own
  notes](../../../weight_engine/test/experimental/helpers/stream_writer.py) record that
  `R_k` had originally been a random draw *"with no on-chain counterpart — the stream
  asserted a reconciliation that never happened"*.

The requirement is therefore: **derive `R_k^(e)` from the confirmed blocks of the epoch,
as `tau` already is**, so that every honest node computes the same value and no actor has
to be trusted to state it.

---

## 2. Options considered

### Option A — keep the stream as a cache

Keep `weight-engine-reconciliation`, but stop writing it by hand. A node component
scans the epoch's confirmed blocks, sums the transfers from each miner to the treasury,
and **publishes** the result as a chain-derived record. The stream becomes a readable
cache, avoiding a re-scan of the blocks on every read.

### Option B — remove the stream, compute the value at runtime

The engine computes `R_k^(e)` directly from the epoch's confirmed blocks, exactly as
`ComputeActivityForEpoch` computes `tau`. Nothing is published. It becomes a **view**,
not a registry.

---

## 3. Analysis

### 3.1 The cost argument that Option A rests on does not survive contact with the code

Option A exists to avoid re-scanning blocks. But the engine **already scans exactly those
blocks, in exactly that range, on exactly the same schedule**:
`ComputeActivityForEpoch(e)` walks the confirmed blocks of epoch `e` and reads each
transaction's undo data to attribute inputs to signing addresses.

Reconciliation needs the *same* traversal, and it needs the *very same* per-transaction
information — the set of signing addresses — plus the output values. So the two are not
two scans that might be deduplicated: they are **one scan** that can compute both. In the
implementation the two quantities are produced by a single pass
(`ComputeActivityAndReconciliationForEpoch`), and the marginal cost of reconciliation is
a few comparisons per output.

Option A's benefit is therefore not "avoid a scan" but "avoid a handful of comparisons
inside a scan that happens anyway" — while its costs are structural.

### 3.2 Option A reintroduces the whole authorization problem it was meant to remove

A published record needs a writer, and a writer needs a rule:

- **Who publishes?** If one designated node does, the trusted single publisher is back,
  just relocated. If every node does, they all publish the same value and the stream
  fills with N copies per epoch — and a dishonest node's copy is indistinguishable from
  an honest one without... recomputing it from the blocks, which is Option B.
- **What if the record disagrees with the chain?** A new failure mode with no analogue in
  Option B: a reader would have to decide between the record and the blocks it purports
  to summarise. Answering that correctly means reading the blocks — Option B again.
- **What if nobody publishes yet?** A cache miss becomes a semantic hole: is `R_k = 0`
  because nothing was reconciled, or because the record has not been written? The
  pipeline cannot distinguish them, and they give different weights.

Every one of these questions is answered by *"consult the blocks"*, which is what Option
B does unconditionally. Option A adds a layer whose only correct behaviour is to agree
with the layer beneath it.

### 3.3 Determinism is easier without the stream

Under Option B, `R_k^(e)` is a pure function of a **buried** block range, guarded by the
same `MC_WEIGHT_DEFAULT_STABILITY_MARGIN` as `tau` and for the same reason: a shallow
reorg near the tip must not make two nodes read different blocks.

Under Option A the value would additionally depend on *when* a record was published and
*which* node published it — timing and identity, neither of which the block range
depends on.

### 3.4 It removes state rather than adding it

Option B deletes a stream, an RPC (`weightsetreconciliation`), a publisher method, a
parser, a reader path and their tests. Option A keeps all of it and adds a publisher
thread. The simpler system is also the one with fewer trust assumptions — an unusual
alignment, and worth taking.

---

## 4. Decision

**Option B.** `weight-engine-reconciliation` is **removed**. `R_k^(e)` is computed at
runtime from the epoch's confirmed blocks, in the same single pass that computes `tau`.

### No configuration flag

A `-weightreconciliationsource=onchain|stream` switch was considered and **rejected**.
It would only be justified if keeping both paths had a concrete benefit, and §3.1 shows
the supposed benefit does not exist. Worse, the flag would be actively harmful: the
source of `R_k` is **consensus-critical**, so two nodes on different settings compute
different `w_k` and fork. A switch whose only safe value is the one every node already
shares is not a configuration option — it is a footgun with a documented default.

### `weight-engine-activity` is removed too

The same reasoning applies, and here the code had already reached the conclusion without
the documentation following: `MC_WEIGHT_ACTIVITY_STREAM_NAME` was **defined but never
created, never written and never read**. The reader managed three streams, not four;
`tau` came from `ComputeActivityForEpoch` alone. Documentation describing "four input
streams" and a stream "nobody writes" was describing a name, not a mechanism.

The vestigial definition is deleted and the documentation corrected: there are **two**
published input streams (membership, ESG) and **two** chain-derived quantities (`tau`,
`R`), neither of which is materialised on chain.

---

## 5. What "a reconciliation transfer" means, precisely

`R_k^(e)` is the total native-currency value paid to the **treasury address** by
transactions signed by miner `k`, among the confirmed transactions of epoch `e`.

Made exact:

1. **Range.** The closed height range of epoch `e`, `[(e-1)*len, e*len - 1]`, and only
   once **buried** — the last height at least `MC_WEIGHT_DEFAULT_STABILITY_MARGIN` below
   the tip. Identical to `tau`'s range, from the same snapshot.
2. **Signer.** `k` must be among the addresses that signed the transaction's inputs,
   resolved from block **undo** data — the same attribution `tau` uses, so a transaction
   counted for `tau_k` is exactly one that can count for `R_k`. No dependence on
   `-txindex`.
3. **Recipient.** Only outputs paying to the configured treasury address count.
4. **Amount.** The native-currency value of those outputs, summed. Fees are not part of
   it: they go to the block's miner, not to the treasury.
5. **Exclusions.** Coinbase transactions (no resolvable signer); `OP_RETURN` and other
   provably-unspendable outputs; outputs to any other address, including a miner's own
   change; and transactions where the miner is not a signer, so that a transfer *to* a
   miner is never mistaken for one *from* it.
6. **Self-payment.** A transaction where the treasury address is itself the signer does
   not create reconciliation for a miner, because the miner is not a signer.

### The treasury address is a chain parameter

`weight-treasury-address` (`-weighttreasuryaddress`), hash-enforced like every other
weight-engine parameter. It **must** be a chain parameter, because the value of `R_k`
depends on it: two nodes with different opinions about the treasury address compute
different weights and fork.

**Deriving it implicitly was rejected.** The obvious candidate — "any address holding
`admin`" — is *mutable*: the admin set changes over time, so a node re-syncing after a
grant or revocation would attribute a historical epoch differently than the network did
at the time. That is the same retroactive-mutability hazard that kept the Certification
Authority check out of the ESG reader ([weight-engine.md §6.4](../weight-engine.md#64-esg--the-certification-authority-role)).
An explicitly configured, hash-enforced address is immutable for the chain's life.

**When unset**, `R_k^(e) = 0` for every cluster, on every node. This is deterministic,
and it is *exactly* the behaviour of the previous model on a chain where nobody published
reconciliation records — so enabling the new code on such a chain changes nothing. By
Def. 6.8 a uniformly zero `R` gives `rho_k = 0`, and by Def. 6.9
`w_k = W_k * (1 - lambda)`: a uniform scaling that leaves the *relative* weights, and
therefore the election distribution, unchanged.

---

## 6. Consequences

### Positive

- **No trusted actor in the feedback term.** `R_k` cannot be misstated, because it is
  not stated at all.
- **One fewer authorization surface.** No stream, no `.write` grant, no RPC, no
  double-write question, and nothing for a forged record to forge.
- **Verifiable end to end.** Combined with the self-published, recomputable weights, the
  only remaining trusted input to the whole pipeline is the ESG score
  ([weight-engine.md §5.1](../weight-engine.md#51-every-node-publishes-its-own-weight-and-every-node-checks-the-others)).
- **Less code.** A stream, an RPC, a publisher method, a parser and a reader path deleted.

### Negative, and accepted

- **A pruned node cannot compute `R`.** It already could not compute `tau`, for the same
  reason and with the same outcome: the epoch is skipped and nothing is published. No new
  class of failure.
- **`R` is no longer inspectable with `liststreamitems`.** It is reported instead by
  `weightverifyweights` and derivable by anyone from the blocks. A convenience lost; the
  underlying data is more accessible, not less.
- **A one-off migration.** On a chain that already carries reconciliation records, they
  are ignored from the upgrade onward and historical `R` is recomputed from blocks. Since
  the records were meant to describe those same transfers, an honest history yields the
  same values; a dishonest one is corrected, which is the point.

---

## 7. Divergence from the thesis text

**Def. 6.7 changes its source, not its meaning.** `R_k^(e)` remains *"the share of the
available allocation that was reconciled in epoch `e`"*, still constrained to
`[0, A_k^(e) + B_k^(e-1)]` and still clamped there by `ComplianceRate` / `Balance`.

What changes is **where the value comes from**. The thesis text is silent on the
mechanism, and the implementation it accompanied made it an admin attestation. Proposed
wording for the thesis:

> `R_k^(e)` is the sum of the native-currency transfers, confirmed in the blocks of epoch
> `e`, from the miner `m_k` to the treasury address of the network — a quantity derived
> from the chain and recomputable identically by every node, not a value declared by the
> administrator.

Two further corrections follow, both in Cap. 7.2:

1. The **four input streams** become **two**. `weight-engine-activity` never existed as a
   mechanism, and `weight-engine-reconciliation` is removed. The corresponding row of
   Figure 7.1 — admin-reserved writes on reconciliation — describes a stream that no
   longer exists; with membership and ESG now implemented as the figure specifies, the
   figure's "not yet reflected by the implementation" caveat can be dropped entirely,
   and the reconciliation box replaced by a chain-derived arrow like activity's.
2. The claim that *"`tau` is the only chain-derived input"* becomes: `tau` **and** `R` are
   chain-derived, from a single shared pass over the epoch's blocks.

No other Cap. 6 definition is affected: Def. 6.6 (`A_k`), 6.8 (`rho_k`) and 6.9 (`w_k`)
consume `R_k` unchanged, and the pure core implementing them is untouched by this change.
