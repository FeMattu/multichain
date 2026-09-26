# wPoA — Protocol parameter catalogue

> **Type:** reference · **Register:** technical-direct · **Verified against the code:**
> 2026-09-26, commit `3d2fc551`
>
> **Single source** for protocol parameters: no other document restates their defaults,
> ranges or semantics — the others link here. When a parameter changes in the code, it is
> updated here and nowhere else. Flag and parameter names are exactly as they appear in the
> source. For the formal model see [thesis-project-overview.md](thesis-project-overview.md).

Every `file:line` reference was re-read at the commit above; if one drifts, trust the
symbol. The **Defined** column says where the parameter is *declared* as a chain
parameter; [§6](#6-value-validation-at-startup) says where its value is *checked* at node
startup.

---

## Table of contents

- [1. Configuration model](#1-configuration-model)
  - [1.1 The parameters are hash-enforced](#11-the-parameters-are-hash-enforced)
  - [1.2 Master switch and precedence](#12-master-switch-and-precedence)
  - [1.3 Dependency constraints (hard failure)](#13-dependency-constraints-hard-failure)
- [1bis. The master switch, and how it expands](#1bis-the-master-switch-and-how-it-expands)
- [1ter. `setup-first-blocks` is derived, not merely validated](#1ter-setup-first-blocks-is-derived-not-merely-validated)
- [2. Catalogue — wPoA phases](#2-catalogue--wpoa-phases)
  - [2.1 The Phase 4 mining delay](#21-the-phase-4-mining-delay)
- [3. Catalogue — behavioural malus registry](#3-catalogue--behavioural-malus-registry)
- [4. Catalogue — weight engine](#4-catalogue--weight-engine)
  - [4.1 No parameter governs who may write the input streams](#41-no-parameter-governs-who-may-write-the-input-streams)
  - [4.2 The Certification Authority role is not a chain parameter either](#42-the-certification-authority-role-is-not-a-chain-parameter-either)
- [5. Per-node parameter — `-weight`](#5-per-node-parameter---weight)
- [5bis. Runtime-only flags](#5bis-runtime-only-flags)
- [6. Value validation at startup](#6-value-validation-at-startup)
- [7. Configuration recipes](#7-configuration-recipes)
- [8. References](#8-references)

---

## 1. Configuration model

Every wPoA switch and every weight-engine parameter is a **chain parameter** (protocol
`20014`). You set it once, when the chain is created, and it is written into
`params.dat`:

```bash
./src/multichain-util create mychain -enablewpoa=1
```

Any node joining the network **inherits** the configuration from `params.dat` and starts
correctly with **no command-line flags**:

```bash
./src/multichaind mychain                       # the creator / a local node
./src/multichaind mychain@<seed-ip>:<port>      # a joining node
```

The same names also work as **runtime flags** on `multichaind`. A runtime flag overrides
the inherited value **for that node only** (CLI wins).

### 1.1 The parameters are hash-enforced

No entry in the wPoA/weight block of
[`paramlist.h`](../src/chainparams/paramlist.h) carries the `MC_PRM_NOHASH` flag: every
one is `MC_PRM_USER | MC_PRM_CLONE` plus its own type. **The parameters therefore take
part in the `params.dat` hash.**

> **Operational consequence.** A local CLI override of a consensus-critical parameter is
> not a harmless customisation: it diverges this node from the rest of the validator set
> and **risks a silent fork**. `AppInit2` logs an explicit warning on every divergent
> override, but does **not** prevent startup. Use overrides only in isolated tests.

An earlier project note described these parameters as `MC_PRM_NOHASH` (inherited but not
cryptographically bound). That description is **obsolete**.

### 1.2 Master switch and precedence

`-enablewpoa` (alias `-wpoaenable`) turns **every** wPoA phase on — weights, selection,
vrf, randao, sortition and malus. A more specific `-enablewpoa*` flag then overrides its
own phase. The master does **not** turn on the weight engine (`-enableweightengine`). The
score-based fork choice has no flag at all: it is on whenever private sortition is
(§5bis).

```bash
# Full stack except sortition:
./src/multichain-util create mychain -enablewpoa=1 -enablewpoasortition=0
```

Resolution has three levels, in order: the value inherited from `params.dat` → the
runtime master `-enablewpoa` / `-wpoaenable` → the explicit per-phase flag (which wins).
Creation-time master expansion lives in
[`params.cpp`](../src/chainparams/params.cpp) (`Read(argc,argv)`); runtime resolution in
[`init.cpp`](../src/core/init.cpp) (`AppInit2`).

### 1.3 Dependency constraints (hard failure)

Phases must be enabled bottom-up:

```
weights -> selection -> vrf -> randao -> sortition -> malus
                                     \
                                      weight engine (requires weights)
```

Enabling a phase without its prerequisite is **rejected** at chain creation **and** at
node startup, with an explicit error: the node refuses to start rather than run a phase
inert.

| Constraint | Error at |
|---|---|
| `enablewpoaselection` requires `enablewpoaweights` | `src/core/init.cpp:3441` |
| `enablewpoavrf` requires `enablewpoaselection` | `src/core/init.cpp:3443` |
| `enablewpoarandao` requires `enablewpoavrf` | `src/core/init.cpp:3445` |
| `enablewpoasortition` requires `enablewpoarandao` | `src/core/init.cpp:3447` |
| `enablewpoasortition` requires `wpoarandaolookback >= 1` | `src/core/init.cpp:3449` |
| `enablewpoamalus` requires `enablewpoasortition` | `src/core/init.cpp:3577` |
| `wpoamalusequivpoints` must be `>` `wpoamalusdelaypoints` | `src/core/init.cpp:3558` |
| `wpoamalusbadweightpoints` must be `>` `wpoamalusselfwritepoints` | `src/core/init.cpp:3567` |
| `enableweightengine` requires `enablewpoaweights` | `src/core/init.cpp:3751` |

The `k >= 1` constraint is not arbitrary: the reveal that sortition produces feeds
`R_tot[n]`, while its own seed reads `R_tot[n-k]`. At `k = 0` the dependency would be
circular.

---

## 1bis. The master switch, and how it expands

`enable-wpoa` is not a switch the consensus code reads. Nothing branches on it: every
decision is taken on the six per-phase keys (`enable-wpoa-weights`, `-selection`, `-vrf`,
`-randao`, `-sortition`, `-malus`), and the master expands into all six. The master is a **convenience that expands into
them**, and where that expansion happens used to matter a great deal.

It expands in two places, and they now agree:

| Where the master arrives | Expands | Result |
|---|---|---|
| `multichain-util create -enablewpoa=1 ...` | `mc_MultichainParams::Read` writes all six per-phase keys into the generated `params.dat` | The file is explicit; every joining node inherits the six values |
| Written by hand into `params.dat` as `enable-wpoa = true` | `AppInit2` expands it at startup, to every phase still at its default (malus included) | The file stays as written; the runtime configuration is the expanded one |

**Before this was fixed, the second row did nothing.** `AppInit2` read only the per-phase
keys and never `enablewpoa`, so a `params.dat` carrying `enable-wpoa = true` was parsed,
hashed, echoed back by `getblockchainparams` — and inert. The chain ran native MultiChain
mining, and the only symptom was the weight engine refusing to start with

```
Error: weight-engine: -enableweightengine requires the wPoA weights stream (-enablewpoaweights).
```

which names a flag the operator never touched. This is the single most dangerous gap for
anyone writing `params.dat` by hand, and it is why it has a section of its own.

### What wins over what

1. A **runtime per-phase flag** (`-enablewpoaselection=0`) — always wins, for that node.
2. The **runtime master** (`-enablewpoa`) — sets the baseline for every phase without its
   own flag.
3. A **per-phase key in `params.dat`** that is `true` — explicit, and the in-file master
   never overrides it.
4. The **in-file master** — expands to every phase still at its default.

### The one thing the file cannot say

A phase written explicitly as `false` next to `enable-wpoa = true` is indistinguishable
from a phase that is simply absent: both read as the default, and `params.dat` carries no
"was this key present" bit. Such a file is self-contradictory, and the master wins. If a
node genuinely needs a phase off while the chain has it on, that is what the runtime flag
is for — and it forks that node, which the startup log says out loud.

### Reading the effective configuration

`getblockchainparams` reports what is **stored in the file**, not what the node resolved.
After an in-file master expansion the per-phase keys still read `false` there while every
phase is running. That is correct — the file is hash-enforced and must not be rewritten —
but it means the file is not the place to check. The startup log is:

```
[wPoA] params.dat sets enable-wpoa=true: expanding the master switch to weights,
       selection, vrf, randao and sortition
```

(The malus is expanded too, a few lines later in `AppInit2`, although this line does not
name it.)

---

## 1ter. `setup-first-blocks` is derived, not merely validated

Two distinct mechanisms decide when wPoA starts governing, and both are easy to miss.

### The floor applied at chain creation

`mc_MultichainParams::AdjustSetupFirstBlocks` (`src/chainparams/params.cpp:1275`, called from `init.cpp:1810` on the genesis path)
**raises** `setup-first-blocks` when the weight engine and wPoA selection are both on, and
writes the corrected value into `params.dat` *before the parameter hash is taken*:

```
first_computable = weight-epoch-length + MC_WEIGHT_DEFAULT_STABILITY_MARGIN - 1
required         = first_computable + MC_WEIGHT_SETUP_PUBLISH_MARGIN + 1
                 = weight-epoch-length + 9
```

with `MC_WEIGHT_DEFAULT_STABILITY_MARGIN = 6` and `MC_WEIGHT_SETUP_PUBLISH_MARGIN = 3`
(`src/weight_engine/weight_streams.h`). Both are **compile-time constants, not chain
parameters**: they cannot be configured, and a node built from different sources would
disagree about them.

The stability margin is how deeply an epoch must be buried before it is computed, so that
a shallow reorg cannot make two nodes read different blocks. The publish margin is the
slack on top: being *computable* is not enough, because the selector reads confirmed
stream items only — the value still has to be noticed by the engine, published as a
transaction, and mined.

A larger configured value is left alone; a smaller one is raised and the change is
reported. With the stock defaults (epoch 100, setup 60) this **always** fires. Read the
effective value back from `getblockchainparams` rather than trusting what you wrote.

### The deferred activation at runtime

Even a correct floor is a height, and a height cannot know whether the engine has managed
to publish anything. wPoA additionally waits for the registry to carry a weight it can
actually draw — see
[weight-engine.md §4bis](weight-engine.md#4bis-deferred-activation--when-wpoa-actually-takes-over).
Until then the chain runs under the native rules instead of stopping.

---

## 2. Catalogue — wPoA phases

All consensus-critical, all hash-enforced, all to be kept **identical** on every
validator.

| CLI flag | `params.dat` | Type | Default | Valid range | Defined | Effect on consensus |
|---|---|---|---|---|---|---|
| `-enablewpoa`, `-wpoaenable` | `enable-wpoa` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:164` | Master: turns every phase on. Overridden per phase by the specific flags. |
| `-enablewpoaweights` | `enable-wpoa-weights` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:168` | Phase 1: runs the `wpoa-weights` stream. No direct effect on the election, but it is the data substrate of every later phase. Can run standalone. |
| `-enablewpoaselection` | `enable-wpoa-selection` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:172` | Phase 2: weight-proportional proposer election (Efraimidis–Spirakis). Replaces the round-robin mining-diversity spacing on wPoA-governed heights. |
| `-dumpfunction` | `dump-function` | `STRING(16)` | `none` | `none` \| `sqrt` \| `log` | `paramlist.h:176` | Whale compression `f(w)` applied **before** the draw. Changes the effective proposer distribution. |
| `-enablewpoavrf` | `enable-wpoa-vrf` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:180` | Phase 3a: every elected proposer publishes a verifiable reveal `(R, pi)`; peers reject a block without a valid reveal. Selection is unchanged. |
| `-enablewpoarandao` | `enable-wpoa-randao` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:184` | Phase 3b: the selection seed becomes `H(R_tot[n-k] \|\| h[n] \|\| n+1)` instead of the previous block hash. Only the seed source changes. |
| `-wpoarandaolookback` | `wpoa-randao-lookback` | `UINT32` | `1` | `0` .. `1000000`; **`>= 1`** when sortition is on | `paramlist.h:188` | Accumulator lookback distance `k`. Determines which `R_tot` feeds the seed. |
| `-enablewpoasortition` | `enable-wpoa-sortition` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:192` | Phase 4: private sortition. Each validator scores itself with a VRF under its own key and self-elects through a mining delay. The proposer is unpredictable until it acts. |
| `-wpoasortitiondelta` | `wpoa-sortition-delta` | `STRING(32)` | `0.5` | `(0, 1)` — endpoints excluded | `paramlist.h:196` | Half-width of the delay band, as a **fraction** of `target-block-time`. Small: narrow band, more forks. Large: more latency. |
| `-wpoasortitionlambda` | `wpoa-sortition-lambda` | `STRING(32)` | `0` (off) | `[0, 1]` | `paramlist.h:200` | Gain of the global feedback `Phi`, which recentres the mean block time on target. `0` disables the feedback. |

### 2.1 The Phase 4 mining delay

The delay is **not** an open-ended ramp: it is a **band** centred on
`target-block-time`.

```
score_norm = 1 - e^{-W * score}                                          (Def. 5.10)
D_i        = T_block + delta * T_block * (2 * score_norm - 1) + lambda * Phi   (Def. 5.13)
```

where `T_block` is the native `targetblocktime`
([`paramlist.h`](../src/chainparams/paramlist.h), entry `targetblocktime`), `delta` is
`-wpoasortitiondelta`, `lambda` is `-wpoasortitionlambda`, and `W` is the sum of the
compressed effective weights. Implementation: `PrivateSortition::MiningDelay()` in
[`private_sortition.h`](../src/wpoa/private_sortition.h).

The `W` factor is what makes the normalisation real: without it the value inherits the
scale of `E/w` and collapses toward `0` for every candidate as soon as weights reach the
hundreds. With it, the **winner's** normalised score is exactly `U(0,1)`, so its delay is
uniform across the band and the mean block time lands on target.

A validator accepts a block if and only if
`block.nTime >= parent.nTime + MiningDelay(score_i, ...)`. The miner counts down from the
same instant: it starts at `parent.nTime + D_i`, moved to its local clock through the
network time offset, not at the moment it finished processing the parent
([sortition-miner.md §1](sortition-miner.md#1-score-timed-self-election-getminerandexpectedminingstarttime)). This time bar **replaces** the
equality test on the public argmin, and its auto-relaxing nature is the liveness
mechanism: there is no hard threshold, so the online validator with the minimum score
always eventually proposes.

Full detail: [private-sortition.md](private-sortition.md) and
[sortition-validator.md](sortition-validator.md); design history in
[phase4-implementation-guide.md](phase4-implementation-guide.md).

---

## 3. Catalogue — behavioural malus registry

Requires `-enablewpoasortition`: the **consensus-behavioural** evidence kinds are proved
against the block's VRF reveal over the beacon seed. The **published-data integrity**
kinds additionally need `-enableweightengine` to be decidable — not a startup failure, but
without it such reports are refused network-wide and the node logs a note.

| CLI flag | `params.dat` | Type | Default | Valid range | Defined | Effect on consensus |
|---|---|---|---|---|---|---|
| `-enablewpoamalus` | `enable-wpoa-malus` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:204` | Runs the open `wpoa-weights-malus` stream and elects on the effective weight `w_eff = w * Psi` rather than the raw one. Inert when nobody carries a violation (`Psi = 1`). |
| `-wpoamalusmu` | `wpoa-malus-mu` | `STRING(32)` | `0.5` | `[0, 1)` — `1` excluded | `paramlist.h:208` | Accumulator persistence: the fraction of `M` carried into the next epoch. **`mu < 1` is what makes an exclusion reversible.** |
| `-wpoamalusmax` | `wpoa-malus-max` | `STRING(32)` | `4` | `> 0` | `paramlist.h:212` | Threshold `M_max` at which `Psi` reaches `0` and the validator becomes ineligible. |
| `-wpoamalusequivpoints` | `wpoa-malus-equiv-points` | `STRING(32)` | `4` | `> 0`, and **`>` delay points** | `paramlist.h:216` | Score of one proved equivocation (two distinct blocks at one height) — a *safety* fault. |
| `-wpoamalusdelaypoints` | `wpoa-malus-delay-points` | `STRING(32)` | `0.25` | `> 0` | `paramlist.h:220` | Score of one proved delay violation (a block mined earlier than its own score entitled it to) — a *scheduling* fault. |
| `-wpoamalusselfwritepoints` | `wpoa-malus-selfwrite-points` | `STRING(32)` | `1` | `> 0` | `paramlist.h:224` | Score for publishing a record on a **self-attested** stream naming another address. Readers always discard it, so the score prices the *attempt* — the same reasoning as the delay score. |
| `-wpoamalusbadweightpoints` | `wpoa-malus-badweight-points` | `STRING(32)` | `2` | `> 0`, and **`>` selfwrite points** | `paramlist.h:228` | Score for a `wpoa-weights` value that fails independent recomputation. Unlike a forgery it *succeeds* unless somebody recomputes it, then distorts every round of the epoch. |

**Intended ordering: `p(Equiv) > p(BadWeight) > p(SelfWrite) > p(Delay)`** — safety first,
then a fault that takes effect, then two attempts that are rejected anyway. Two of the
three inequalities are enforced at startup (`equiv > delay`, `badweight > selfwrite`); the
defaults satisfy all three.

The correction is `Psi = max(0, 1 - M/M_max)`, with `M` an exponential moving average.
Because `mu < 1`, an exclusion always clears after a finite number of clean epochs:
**there is no permanent ban** — for either family, since the decay is a property of `M`
rather than of the offence that raised it. The stream is deliberately **open** — anyone may
report, nobody is believed: every node re-derives the evidence from public chain data, so a
false report is discarded identically everywhere and moves no weight.

**One accumulator, two families.** Adding the data-integrity kinds required only their two
scores: `Psi`, `w_eff` and the whole consensus path operate on the accumulated severity
`M`, not on what produced it, so they needed no change. A node therefore cannot spread
misbehaviour across kinds to stay under the threshold.

Detail: [malus-registry.md](malus-registry.md).

---

## 4. Catalogue — weight engine

The weight engine **produces** the weights the wPoA layer consumes, so it requires the
weights stream. Module detail: [weight-engine.md](weight-engine.md).

| CLI flag | `params.dat` | Type | Default | Valid range | Defined | Effect on consensus |
|---|---|---|---|---|---|---|
| `-enableweightengine` | `enable-weight-engine` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:233` | Derives each cluster's weight once per buried epoch from the published inputs (ESG, membership) and the block-derived ones (activity `tau`, restitution `R_k`, credits and debits), **instead of** the static `-weight`. Not turned on by the `-enablewpoa` master. |
| `-weightepochlength` | `weight-epoch-length` | `UINT32` | `100` | `[1, 1000000]` | `paramlist.h:237` | Epoch length in blocks. The epoch is **1-based**: `epoch(height) = height / n + 1`. Determines the epoch boundaries the miner and every validator must agree on. |
| `-weightkappa` | `weight-kappa` | `STRING(32)` | `100` | `> 0` (and `< 1e18`) | `paramlist.h:241` | Normalisation constant `kappa` in the company contribution `c_i = ESG_i * tau_i / kappa`. Also the scale `ToIntegerWeight` multiplies by before rounding the published weight. |
| `-weightalpha` | `weight-alpha` | `STRING(32)` | `0.2` | `[0, 1]` | `paramlist.h:245` | **DEPRECATED — parsed, validated, never read.** It scaled the allocation `A_k = alpha * Theta * W_k / W_tot` in the superseded compliance-rate formulation; the restitution-rate pipeline has no allocation. Retained because `weightalpha` is a hash-enforced params.dat field: removing it would change the file's hash and make every existing chain unjoinable. |
| `-weightlambda` | `weight-lambda` | `STRING(32)` | `0.5` | `[0, 1)` — `1` excluded | `paramlist.h:249` | Behavioural-feedback damping in `w_k = W_k * [rho_{k,e-1} * lambda + (1 - lambda)]`. **`lambda < 1` is a correctness requirement**, not a preference: it guarantees weight positivity. |
| `-weighttreasuryaddress` | `weight-treasury-address` | `STRING(64)` | *(empty)* | a valid address, or empty | `paramlist.h:253` | The recipient that defines a reconciliation transfer: `R_k^(e)` is the native-currency value paid to **this** address by transactions the miner signed, in the epoch's confirmed blocks. **Empty is legal** and means `R_k = 0` for every cluster — a uniform scaling that leaves the election unchanged. A non-empty value must parse as an address, or startup fails. |

### 4.1 No parameter governs who may write the input streams

The write policy of the pipeline's inputs is **not** configurable: it is a property of what
each record *is*, and it is enforced in code rather than by a switch.

| Stream | Write policy | Enforced by |
|---|---|---|
| `weight-engine-membership` | CLOSED, but `.write` is meant to be granted to **every node** | The reader's self-attestation rule: tx signer must equal the payload's `node_address`, else the record is discarded |
| `weight-engine-esg` | CLOSED, `.write` to **Certification Authorities** only | `IsCertificationAuthority` in the `weightsetesg` RPC — the `high1` custom permission, **not** `CanAdmin` — plus the operator's grant discipline |
| ~~`weight-engine-reconciliation`~~ | **removed** — `R_k` is chain-derived | Nothing to authorize: there is no stream and no writer. See [adr/reconciliation-onchain.md](adr/reconciliation-onchain.md) |
| ~~`weight-engine-activity`~~ | **removed** — never was a mechanism | The name was defined but never created, written or read |

Grants are therefore an **operational** step, documented in
[weight-engine.md §6](weight-engine.md#6-security-model--three-independent-layers), not a
`params.dat` value. Adding a parameter here would be actively wrong for membership: making
the self-attestation rule switchable would make it non-consensus-critical, and a node that
turned it off would fold records its peers discard — a fork.

### 4.2 The Certification Authority role is not a chain parameter either

The ESG writer must hold the **Certification Authority** role, carried on chain by
MultiChain's `high1` custom permission
([`weight_authorization.h`](../src/weight_engine/weight_authorization.h)
`MC_WEIGHT_CA_PERMISSION_NAME`). It is a **compile-time constant**, not an inheritable
parameter, and that is a deliberate consequence of what the check does:

- the CA check gates **local publication only** — the reader still accepts any
  schema-valid confirmed ESG record regardless of publisher;
- so two nodes disagreeing about who is a CA disagree only about whether their *own* RPC
  will publish. They compute identical weights and **cannot fork**;
- therefore the role is **not consensus-critical**, and putting it in `params.dat` — where
  every entry is hash-enforced precisely because divergence forks the chain — would imply
  a role it does not have.

MultiChain has no arbitrary named custom permission (`grant <addr> custom.certauth` does
not exist): there are exactly six fixed slots. The role occupies a **high** slot because
only those require `admin` rather than `activate` to grant, which is what makes CA status
conferrable by the administrator alone. Full rationale, including why the reader does not
enforce the role: [weight-engine.md §6.4](weight-engine.md#64-esg--the-certification-authority-role).

Two related constants are **not** chain parameters yet, and are fixed at compile time in
[`weight_streams.h`](../src/weight_engine/weight_streams.h):

| Constant | Value | Note |
|---|---|---|
| `MC_WEIGHT_DEFAULT_STABILITY_MARGIN` | `6` | Stability margin in blocks. An epoch is computed only once it is **buried** — its last block at least this far below the tip — so a shallow reorg cannot make two nodes read different blocks. Must be `>=` the deepest possible reorg. The code itself recommends promoting it to a chain parameter before production. |
| `MC_WEIGHT_DEFAULT_EPOCH_LENGTH` | `100` | Fallback default for `weightepochlength` when `params.dat` is unreadable. |

---

## 5. Per-node parameter — `-weight`

**`-weight` is the only parameter in this catalogue that is NOT a chain parameter.** It
is a plain runtime flag: every validator sets its own.

| CLI flag | Type | Default | Valid range | Defined | Validation |
|---|---|---|---|---|---|
| `-weight=<n>` | integer | `100` | `> 0` (positive integers) | `MC_WPOA_DEFAULT_WEIGHT`, [`stream_weight_registry.h`](../src/wpoa/stream_weight_registry.h) | `init.cpp:3311` — `-weight <= 0` prevents startup |

### 5.1 `-weight` is the fallback, not the primary path

With `-enableweightengine=1` the value of `-weight` is parsed, validated, written into
`g_node_weight` and logged — and then **never published**. The two publishers are
**mutually exclusive at startup** (`init.cpp`, end of the wPoA block in `AppInit2`):

```cpp
if (g_wpoa_weights_enabled && pwalletMain && pwalletTxsMain && !fDisableWallet)
{
    if (g_weight_engine_enabled)
        threadGroup.create_thread(boost::bind(&ThreadWeightEngine));                     // dynamic w_k
    else
        threadGroup.create_thread(boost::bind(&ThreadRegisterNodeWeight, g_node_weight)); // static weight
}
```

There is no runtime overwrite: it is an exclusive choice of publication thread. The
difference is observable — with the engine on, `-weight=500` does not produce a record
that is later superseded: it produces **no** record.

Both paths write the same `wpoa-weights` stream, where reads are
**newest-confirmed-wins**. Consensus is therefore indifferent to which publisher produced
the record.

### 5.2 Setting your own weight requires authorization

The `wpoa-weights` stream is created **CLOSED**: the `wpoa-weights.write` permission is
required to publish. A node without it sees its publish fail and **does not appear in the
weight map: it carries no weight in the election**. Grant it explicitly:

```bash
multichain-cli <chain> grant <address> wpoa-weights.write
```

**Closed, but granted network-wide.** The permission is now meant for every node, not for
one designated publisher per cluster, because a weight record no longer has to be taken on
trust: it is **self-published** (the reader discards it unless the transaction's signer is
the cluster it is about) and its value is **independently recomputable** by any node from
the public pipeline inputs. Holding `.write` therefore lets a node state its own cluster's
weight and nothing more — and state it only correctly.

**An unauthorized node cannot impose its own weight by any means**, neither through
`-weight` nor through RPC; and an authorized one cannot impose a *wrong* one, nor one
belonging to another cluster. Detail:
[weight-engine.md §5.1](weight-engine.md#51-every-node-publishes-its-own-weight-and-every-node-checks-the-others).
The three-layer authorization model (permission, application, verification):
[weight-engine.md §6](weight-engine.md#6-security-model--three-independent-layers) and
[stream-weight-registry.md](stream-weight-registry.md).

---

## 5bis. Runtime-only flags

One wPoA flag is deliberately **not** a chain parameter: it changes nothing any other node
has to agree on, so it lives only on the `multichaind` command line and never enters
`params.dat` or its hash.

| CLI flag | Type | Default | Read in | Effect |
|---|---|---|---|---|
| `-wpoadebug` | `BOOLEAN` | `0` | read once per process by the stream readers (`stream_weight_registry.cpp`, `weight_reader.cpp`) | Verbose trace of the stream read paths. Diagnostic only. See [testing.md](testing.md#deep-debugging--wpoadebug). |

The score-based fork choice used to be the second such flag (`-enablewpoaforkscore`). It
was removed: under private sortition the node always breaks same-height ties on the true
score, because the score-aware activation
([score-aware-activation.md](score-aware-activation.md)) makes the argmin propose after a
worse-scored block for its round, and only the score tie-break lets that block win.

Two compile-time constants govern that activation and are not configurable:

| Constant | Value | Where | Effect |
|---|---|---|---|
| `MC_WPOA_DEFER_GRACE_S` | `2.0` s | [`private_sortition.h`](../src/wpoa/private_sortition.h) | How long past its own slot a node keeps holding back a worse-scored block for its round, waiting for its own block, before releasing it. |

The fork-choice instrumentation (every contested round, with both the live and the legacy
winner, and the holds `[wpoa-fork] defer` / `defer-release`) is logged under
`-debug=wpoafork`.

---

## 6. Value validation at startup

Real-valued parameters travel as `MC_PRM_STRING` and are converted in `AppInit2` with
NaN/Inf-safe checks: a non-finite value is rejected, not propagated.

| Parameter | Check | Line |
|---|---|---|
| `-weight` | integer `> 0` | `init.cpp:3311` |
| `-wpoarandaolookback` | non-negative integer | `init.cpp:3392` |
| `-wpoasortitiondelta` | number in `(0, 1)` | `init.cpp:3404` |
| `-wpoasortitionlambda` | number in `[0, 1]` | `init.cpp:3415` |
| `-wpoamalusmu` | number in `[0, 1)` | `init.cpp:3516` |
| `-wpoamalusmax` | number `> 0` | `init.cpp:3522` |
| `-wpoamalusequivpoints` | number `> 0`, and `>` delay points | `init.cpp:3528`, `3565` |
| `-wpoamalusdelaypoints` | number `> 0` | `init.cpp:3534` |
| `-wpoamalusselfwritepoints` | number `> 0` | `init.cpp:3545` |
| `-wpoamalusbadweightpoints` | number `> 0`, and `>` selfwrite points | `init.cpp:3551`, `3574` |
| `-weightepochlength` | integer in `[1, 1000000]` | `init.cpp:3649` |
| `-weightkappa` | number `> 0` (and `< 1e18`) | `init.cpp:3660` |
| `-weightalpha` | number in `[0, 1]` | `init.cpp:3666` |
| `-weightlambda` | number in `[0, 1)` | `init.cpp:3672` |
| `-weighttreasuryaddress` | empty, or a valid address | `init.cpp:3700` |

Every violation produces an `InitError` with an explicit message: the node does not
start.

---

## 7. Configuration recipes

```bash
# Phase 1 only — collect weights on the stream, nothing else:
./src/multichain-util create mychain -enablewpoaweights=1

# Full stack; every joining node inherits the configuration:
./src/multichain-util create mychain -enablewpoa=1

# Full stack except sortition (the specific flag beats the master):
./src/multichain-util create mychain -enablewpoa=1 -enablewpoasortition=0

# Full stack with a narrower band and the feedback on:
./src/multichain-util create mychain -enablewpoa=1 \
    -wpoasortitiondelta=0.3 -wpoasortitionlambda=0.5

# Full stack (the master includes the malus) plus the weight engine, which also makes
# the published-data integrity kinds (selfwrite, badweight) decidable:
./src/multichain-util create mychain -enablewpoa=1 -enableweightengine=1

# Dynamic weights derived from the on-chain inputs, 200-block epochs, with the
# treasury address that defines a reconciliation transfer:
./src/multichain-util create mychain -enablewpoa=1 \
    -enableweightengine=1 -weightepochlength=200 \
    -weighttreasuryaddress=<treasury-address>

# ...then, at runtime, the per-stream authorizations (no params.dat involvement):
multichain-cli mychain grant <certifier> high1                        # CA role
multichain-cli mychain grant <certifier> weight-engine-esg.write
multichain-cli mychain grant <everynode> weight-engine-membership.write
multichain-cli mychain grant <everynode> wpoa-weights.write
# (no grant for reconciliation or activity: both are derived from the blocks)

# Static per-node weight (only meaningful when the weight engine is off):
./src/multichaind mychain -weight=250
```

---

## 8. References

- [node-startup.md](node-startup.md) — how the switches are read from `params.dat`,
  resolved, and wired into `AppInit2`, and how the publication thread is launched.
- [weight-engine.md](weight-engine.md) — the layer that produces the weights: input
  streams, computation pipeline, admin RPCs, authorization model.
- [implementation-status.md](implementation-status.md) — per-phase implementation status.
- [implementation-guide.md](implementation-guide.md) — general index and phase map.
