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
- [6. Security model — two independent gates](#6-security-model--two-independent-gates)
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

The four inputs are deliberately named `weight-engine-*`, **not** `wpoa-*`: they belong to
the weight layer and its external actors (the certifier, the activity aggregator, the
reconciliation process), not to consensus. Only the **output** stream `wpoa-weights`
belongs to wPoA. The naming split mirrors the directory split.

Definitions in [`weight_streams.h`](../../weight_engine/weight_streams.h).

| Stream | Item key | Payload | Origin |
|---|---|---|---|
| `weight-engine-membership` | miner address | `{"<company_addr>": <ts>, ...}` | Admin, via RPC |
| `weight-engine-esg` | node address | `{"node_address":…, "esg":…}` | Admin, via RPC |
| `weight-engine-reconciliation` | miner address | `{"node_address":…, "reconciled":…, "epoch":…}` | Admin, via RPC |
| `weight-engine-activity` | node address | `{"node_address":…, "tau":…, "epoch":…}` | **Chain-derived** |

### 2.1 Activity is published by nobody

`tau_i^{(e)}`, the per-epoch activity counter, is derived **directly from the confirmed
blocks** of the epoch by `ComputeActivityForEpoch()`
([`weight_reader.h`](../../weight_engine/weight_reader.h)). It is a deterministic function
of the blocks, so every honest node recomputes the identical value: no publisher, no
duplicate-write risk, no trust required.

### 2.2 Reconstructing the cluster `C_k`

Membership exploits MultiChain's native `jsonobjectmerge`
(`getstreamkeysummary` / `mc_MergeValues`): every item published under a miner's key is
folded into a single object whose **field names** are the associated company addresses. The
set `C_k` is therefore reconstructed with no auxiliary structure. Parser:
`mc_ParseMembershipClusterJson` in
[`weight_records.h`](../../weight_engine/weight_records.h).

### 2.3 Stream lifecycle

`WeightStreamReader::EnsureInputStreams()` **creates** missing streams and **subscribes**
to them: the first node with create permission (the genesis / admin node) brings them into
existence, everyone else finds them present and subscribes.

The streams are created **CLOSED**: `MC_PTP_WRITE` is required to publish.

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
`tau` is derived from the epoch's confirmed blocks, this prevents a shallow reorg near the
tip from making two nodes read different blocks.

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
2. calls `reader.EnsureInputStreams()` — creates missing streams and subscribes;
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

**The two publishers are mutually exclusive at startup.** There is no runtime overwrite. In
`AppInit2`, at the end of the wPoA block ([`init.cpp`](../../core/init.cpp)):

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
indifferent to which publisher produced the record.

---

## 6. Security model — two independent gates

This is the part to read carefully: the two gates are distinct and protect different
things.

### 6.1 On-chain gate — consensus-enforced

Every stream involved — the three attestation streams and `wpoa-weights` — is **CLOSED**.
Only an address holding `MC_PTP_WRITE` on the stream can publish. This is what blocks
arbitrary writes, and it is enforced by MultiChain's granular permissions, not by
convention.

```bash
multichain-cli <chain> grant <address> wpoa-weights.write
multichain-cli <chain> grant <address> weight-engine-esg.write
```

A node without the permission sees its publish fail and **does not appear in the weight
map: it carries no weight in the election.**

> **An unauthorized node cannot impose its own weight by any means** — not through
> `-weight`, not through RPC, not by publishing directly.

### 6.2 Application gate — these RPCs only

Three inputs are **external attestations** that cannot be derived on-chain, so they are
published by governance through admin RPCs, each routed through `WeightPublisher` — the
**single** write path for these streams.

| RPC (category `weight`) | Stream written | Payload |
|---|---|---|
| `weightsetesg` | `weight-engine-esg` | `{node_address, esg}`, `esg > 0` |
| `weightsetmembership` | `weight-engine-membership` | key `miner`, payload `{<company>: ts}` |
| `weightsetreconciliation` | `weight-engine-reconciliation` | `{node_address, reconciled, epoch}`, `R >= 0`, `epoch >= 1` |

Registered in [`rpclist.cpp`](../../rpc/rpclist.cpp). Each method, **before** publishing:

1. validates the record in **round-trip** with the *same* W1 parser the reader uses
   (`mc_Parse*RecordJson`) — so it cannot emit a malformed record the reader would
   reject;
2. verifies that the acting address is a **global administrator** (`CanAdmin`,
   [`weight_publisher.cpp`](../../weight_engine/weight_publisher.cpp));
3. verifies that the address has write permission on the stream;
4. publishes **from** that address.

Any failure raises `JSONRPCError`, so the calling RPC returns a precise error.

### 6.3 Known limit — accepted risk

Write permission is an **independent** grant from admin status, and the reader **trusts any
schema-valid confirmed record, regardless of its publisher**.

> The "admin-only" guarantee holds **only if** operators grant `.write` on these streams
> **exclusively** to admin / governance addresses. A non-admin who has been granted
> `.write` could publish a schema-valid but **forged** record using the generic
> `publishfrom` rather than the `weightset*` RPCs, and the reader would accept it.

Hardening recommended by the code itself: have the reader additionally require
`CanAdmin(publisher)` before folding a record into the weight math. Not yet implemented.
Until then, granting `.write` **is** the security control, and must be treated as such.

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
| [`weight_records.h`](../../weight_engine/weight_records.h) | W1: pure record parsers (`mc_Parse*RecordJson`), testable in isolation. |
| [`weight_engine.h`](../../weight_engine/weight_engine.h) | W2: the pure computation core. Standard library only. |
| [`weight_engine.cpp`](../../weight_engine/weight_engine.cpp) | W3: `HeightToEpoch`, `ThreadWeightEngine`, node glue, configuration globals. |
| [`weight_reader.h`](../../weight_engine/weight_reader.h) / [`.cpp`](../../weight_engine/weight_reader.cpp) | W3: `WeightStreamReader` — stream lifecycle, confirmed reads, `ComputeActivityForEpoch`. |
| [`weight_publisher.h`](../../weight_engine/weight_publisher.h) / [`.cpp`](../../weight_engine/weight_publisher.cpp) | W3: the single validated write path, and the three admin RPCs. |

### 9.1 Tests

The module has its **own** unit suites, with a runner separate from the wPoA one:

```bash
./src/weight_engine/test/run_unit_tests.sh              # both suites
./src/weight_engine/test/run_unit_tests.sh engine       # one only
```

| Suite | File | Coverage |
|---|---|---|
| `records` | [`weight_records_tests.cpp`](../../weight_engine/test/weight_records_tests.cpp) | Record parsing, cluster reconstruction from the JSON merge. |
| `engine` | [`weight_engine_tests.cpp`](../../weight_engine/test/weight_engine_tests.cpp) | Order independence, zero-total guard, `rho` bounds, balance recursion, weight positivity, `ToIntegerWeight` clamp, multi-cluster allocation identity. |

Both are node-free: they do not require building the node. See [testing.md](testing.md).

---

## 10. References

- [protocol-parameters.md](protocol-parameters.md) — the engine's five parameters, with
  ranges and validation.
- [stream-weight-registry.md](stream-weight-registry.md) — the `wpoa-weights` stream and
  its read API.
- [malus-registry.md](malus-registry.md) — the malus registry, which reuses
  `HeightToEpoch`.
- [implementation-status.md](implementation-status.md) — implementation status.
