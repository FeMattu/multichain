# Weight-engine refactor — permission model before and after

> **Register: technical-direct.** A per-stream summary of what changed, for direct reuse in
> the thesis' Implementation chapter. Rationale lives in the module docs; this file is the
> table.

The refactor answers one question per stream: **can a third party verify what this record
claims?** Where the answer is yes, the write is opened and the *claim* is checked. Where it
is no, the write is restricted and the *writer* is checked. Where the data was on the chain
already, the stream is deleted and the value derived.

---

## 1. The four inputs at a glance

| Input | Before | After |
|---|---|---|
| `weight-engine-membership` | Admin writes for everyone, via `weightsetmembership`. Keyed by **miner**, accumulated with `jsonobjectmerge`. | **Every node writes its own record**, via `weightregistermembership`. Keyed by the **declaring node**, last-confirmed-wins. Reader **discards** any record whose tx signer is not its declared `node_address`. |
| `weight-engine-esg` | Admin writes, via `weightsetesg` gated by `CanAdmin`. | **Certification Authority** writes, via `weightsetesg` gated by `IsCertificationAuthority` (`high1`). Being an admin is **not** sufficient. |
| `weight-engine-reconciliation` | Admin **attests** `R_k`, via `weightsetreconciliation`. | **Stream removed.** `R_k` is derived from the epoch's confirmed transfers to the treasury address. |
| `weight-engine-activity` | Listed as a stream; **never created, written or read**. | **Removed.** `tau` was always derived; it now shares one pass with `R_k`. |
| *(output)* `wpoa-weights` | CLOSED, `.write` to a designated publisher per cluster. Reader trusts any schema-valid record. | CLOSED, `.write` to **every node**. Each node publishes only its **own** cluster, with `publishfrom`. Reader **discards** a record not signed by its subject, and every node **recomputes** every published value. |

---

## 2. Per stream, in detail

### 2.1 `weight-engine-membership` — from admin attestation to self-attestation

| | Before | After |
|---|---|---|
| Write path | `weightsetmembership` (admin only) | `weightregistermembership` (**no privilege**) |
| `.write` granted to | governance | **every node** on the network |
| Item key | miner address | **declaring node's** address |
| Payload | `{<company_addr>: <ts>, …}` | `{node_address, miner_address, timestamp}` |
| Reconstruction of `C_k` | `jsonobjectmerge` under the miner key (**additive**) | latest confirmed record per node, inverted and filtered by `miner_address == k` |
| Validity rule | any schema-valid record from a `.write` holder | **tx signer must equal the payload's `node_address`**, else discarded |
| Can a node change cluster? | **No** — the additive merge could not retract a membership, so a node that moved appeared in both clusters for ever | **Yes**, at any time: publish again, latest wins |

`weightsetmembership` was **removed**, not deprecated: under self-attestation an
admin-published record names a `node_address` other than the signer, so every reader
discards it. Keeping the RPC would only have offered a way to pay for a transaction with no
effect.

Two inversion rules: a miner's **self-declaration** registers it as a cluster head, and a
miner is **never** among its own companies (its activity already enters `W_k` through the
separate `tau_Mk` term).

### 2.2 `weight-engine-esg` — from administrator to delegated certifier

| | Before | After |
|---|---|---|
| Application gate | `CanAdmin` | `IsCertificationAuthority` |
| On-chain marker | — | `high1` (`MC_PTP_CUSTOM4`) |
| Who confers it | — | the global administrator, and only it |
| Is admin sufficient? | it *was* the requirement | **no** — the admin confers the role, it does not hold it |
| Revocation | revoke `admin` | `revoke <addr> high1`, effective immediately and **independently of `.write`** |

MultiChain has no arbitrary named custom permission: there are six fixed slots. The role
occupies a **high** slot because only those require `admin` rather than `activate` to grant
— which is exactly what makes CA status conferrable by the administrator alone.

**Still the one trusted input.** An ESG score is an attestation with nothing inside it to
check, so restricting the writer is the only available defence. The CA check gates *local
publication* and is therefore **not** consensus-critical; the reader still accepts any
schema-valid confirmed record. Reader-side enforcement was considered and rejected:
permissions are mutable, so a later revocation would retroactively change historical epoch
weights.

### 2.3 `weight-engine-reconciliation` — from attestation to derivation

| | Before | After |
|---|---|---|
| Source of `R_k^(e)` | an administrator's statement | the epoch's **confirmed transfers** to the treasury address |
| Stream | `weight-engine-reconciliation` (CLOSED) | **none** |
| RPC | `weightsetreconciliation` | **none** |
| Who can misstate it | the administrator | **nobody** — it is not stated |
| Configuration | — | `weight-treasury-address` (hash-enforced; empty ⇒ `R_k = 0` uniformly) |

`R_k^(e)` = native-currency value paid to the treasury by transactions the miner **signed**,
in the epoch's confirmed blocks. Crediting the *signer* is what makes the direction
unambiguous. Computed in the **same single pass** as `tau`, so the marginal cost is a few
comparisons per output rather than a second traversal.

Full decision record, including the rejected "keep the stream as a cache" option and why no
configuration flag was added: [adr/reconciliation-onchain.md](adr/reconciliation-onchain.md).

### 2.4 `weight-engine-activity` — a name, not a mechanism

Defined in `weight_streams.h` and **never created, written or read**. `tau` always came from
a block scan. The definition is deleted and the documentation corrected: there were never
four input streams.

### 2.5 `wpoa-weights` — from a trusted publisher to a verified one

| | Before | After |
|---|---|---|
| `.write` granted to | one designated publisher per cluster | **every node** |
| Who publishes a cluster's weight | that publisher | the cluster's **own** node |
| Publish call | `publish` (wallet picks the funding address) | **`publishfrom`** its own address |
| Record | `{timestamp, node_address, weight, height}` | `+ epoch` (the epoch the value was computed **for**) |
| *Who wrote it* | trusted | **verified**: signer must equal the record's subject, else discarded |
| *Whether the value is right* | not checkable | **verified**: every node re-runs the pipeline and compares exactly |

Two rules, failing in **opposite** directions on purpose:

- **self-publication fails closed** — decidable from one transaction, which is always
  available, so an undecodable item is rejected;
- **value verification fails open** — it needs readable inputs and a buried epoch, whose
  absence is normal (a syncing node). Treating "cannot verify" as "invalid" would zero every
  weight and stall the chain.

`publishfrom` is not cosmetic: plain `publish` lets the wallet choose the funding address,
which on a multi-address wallet need not be the node's own — the record would be well-formed
and silently discarded by every peer.

The record carries its **epoch** because a weight is a claim about a specific epoch.
Verifying epoch `e`'s record against epoch `e+1`'s recomputation flagged honest nodes on
every rollover; verification now targets the *previous* epoch, since publication necessarily
lags what it describes.

---

## 3. Malus: a second family of violations

| | Before | After |
|---|---|---|
| Kinds | `equiv`, `delay` | `+ selfwrite`, `badweight` |
| Evidence | a **block** and its VRF reveal | *also* a publishing **transaction**, its signature and payload |
| What is attacked | how the election is **executed** | *also* the **inputs** it consumes |
| Scores | 2 chain parameters | 4 |

`selfwrite` is validated as the exact **negation** of the readers' rule, through the same
shared predicate — so a node can never accuse a record it would have accepted. `badweight`
re-runs the pipeline. The two are disjoint: an unsigned record is a `selfwrite`, never a
`badweight`, so one act is never scored twice.

**`Psi` needed no change.** Adding the family touched exactly one function, the per-kind
score dispatch: `Fold`, `Psi`, `w_eff`, `EpochsToClear` and the consensus path all operate
on the accumulated severity `M` rather than on what produced it. One accumulator therefore
carries both families, and a node cannot spread misbehaviour across kinds to stay under the
threshold. Exclusion remains temporary for both, since the decay is a property of `M`.

---

## 4. Net effect on the trust surface

| Input | Before | After |
|---|---|---|
| `tau` | derived | derived |
| `C_k` (membership) | **trusted** (admin) | self-verifiable (signature) |
| `R_k` (reconciliation) | **trusted** (admin) | derived |
| `w_k` (`wpoa-weights`) | **trusted** (publisher) | self-verifiable (signature **+** recomputation) |
| `ESG_i` | **trusted** (admin) | **trusted** (Certification Authority) |

Four trusted inputs became one. **ESG is the only remaining trusted datum in the system**,
so the integrity of every weight now rests on the CA role and on the grant discipline for
`weight-engine-esg.write`.

---

## 5. Operator-facing changes

**RPCs removed:** `weightsetmembership`, `weightsetreconciliation`.
**RPCs added:** `weightregistermembership` (public), `weightverifyweights` (read).
**RPC extended:** `reportmalus` accepts `selfwrite` and `badweight`, whose evidence argument
is a **transaction id** rather than a block hash.

**New chain parameters** (all hash-enforced): `weight-treasury-address`,
`wpoa-malus-selfwrite-points`, `wpoa-malus-badweight-points`.

**Grants now required:**

```bash
# ESG: the CA role AND the stream write — independent, either revocation stops writes
multichain-cli <chain> grant <certifier> high1
multichain-cli <chain> grant <certifier> weight-engine-esg.write

# membership and weights: granted to EVERY node — both are self-verifiable, so the
# permission conveys nothing beyond speaking about oneself, and only correctly
multichain-cli <chain> grant <node> weight-engine-membership.write
multichain-cli <chain> grant <node> wpoa-weights.write

# reconciliation and activity: nothing to grant — both are derived from the blocks
```

---

## 6. Thesis text requiring an update

| Location | What is now wrong | Proposed replacement |
|---|---|---|
| **Def. 6.7** (`R_k^(e)`) | the value is *declared by the administrator* | *"the sum of the native-currency transfers, confirmed in the blocks of epoch `e`, from the miner `m_k` to the treasury address of the network — derived from the chain and recomputable identically by every node."* Meaning and domain `[0, A_k + B_{k-1}]` unchanged. |
| **Figure 7.1** | captioned as *"non ancora rispecchiato dall'attuale implementazione"* | The caveat can be **dropped entirely**. Membership and ESG are implemented as illustrated; the reconciliation box becomes a chain-derived arrow like activity's, whose stream never existed as a mechanism. Add a verification arrow: every node recomputes every other cluster's `w_k`. |
| **Cap. 7.1** | write access restricted to a subset of authorised entities; the reader trusts the publisher | The stream stays CLOSED but `.write` is granted network-wide; a record is accepted only if self-published, and its value only if it matches an independent recomputation of Def. 6.9. |
| **Cap. 7.1** (asymmetry) | `wpoa-weights` *"trust the publisher"* vs the malus *"trust the evidence"* | Both registries now rest on evidence. What differs is its *shape*, and hence the write policy: closed-but-universal for weights, fully open for accusations. |
| **Cap. 7.2** | *"four input streams"*; all three check `CanAdmin`; `tau` is the only chain-derived input | **Two** published streams and **two** derived quantities. The application gate differs per stream: a CA role for ESG, **no privilege** for membership, and none at all for `tau`/`R`, which have no writer. |
| **Cap. 7.8** | two malus kinds, both proved against a block | Four kinds in two families; the data-integrity pair is proved against a publishing transaction. `Psi` is unchanged — only the per-kind score dispatch grew. |

**No other Cap. 6 definition is affected.** Def. 6.1–6.6, 6.8 and 6.9 are consumed
unchanged, and the pure computation core implementing them was not modified by any phase —
it is precisely the determinism of Def. 6.9 that makes exact-equality verification possible.
