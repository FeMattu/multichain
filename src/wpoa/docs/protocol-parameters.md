# wPoA — Protocol parameter catalogue

> **Register: technical-direct.** A reference for APIs and configuration. Short
> sentences, code terminology left verbatim, flag and parameter names exactly as they
> appear in the source. For the theoretical consensus model and its security properties
> see [thesis-project-overview.md](thesis-project-overview.md), which is written in the
> formal-academic register.

> **Single source.** This file is the **only** authoritative place for protocol
> parameters. No other document restates their defaults, ranges or semantics — the
> others link here. When a parameter changes in the code, it is updated here and
> nowhere else.

Every `file:line` reference points at the code as of this document's last revision. The
**Defined** column says where the parameter is *declared* as a chain parameter; the
**Validation** section says where its value is *checked* at node startup.

---

## Table of contents

- [1. Configuration model](#1-configuration-model)
  - [1.1 The parameters are hash-enforced](#11-the-parameters-are-hash-enforced)
  - [1.2 Master switch and precedence](#12-master-switch-and-precedence)
  - [1.3 Dependency constraints (hard failure)](#13-dependency-constraints-hard-failure)
- [2. Catalogue — wPoA phases](#2-catalogue--wpoa-phases)
  - [2.1 The Phase 4 mining delay](#21-the-phase-4-mining-delay)
- [3. Catalogue — behavioural malus registry](#3-catalogue--behavioural-malus-registry)
- [4. Catalogue — weight engine](#4-catalogue--weight-engine)
- [5. Per-node parameter — `-weight`](#5-per-node-parameter---weight)
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
[`paramlist.h`](../../chainparams/paramlist.h) carries the `MC_PRM_NOHASH` flag: every
one is `MC_PRM_USER | MC_PRM_CLONE` plus its own type. **The parameters therefore take
part in the `params.dat` hash.**

> **Operational consequence.** A local CLI override of a consensus-critical parameter is
> not a harmless customisation: it diverges this node from the rest of the validator set
> and **risks a silent fork**. `AppInit2` logs an explicit warning on every divergent
> override, but does **not** prevent startup. Use overrides only in isolated tests.

An earlier project note described these parameters as `MC_PRM_NOHASH` (inherited but not
cryptographically bound). That description is **obsolete**.

### 1.2 Master switch and precedence

`-enablewpoa` (alias `-wpoaenable`) turns **every** phase on. A more specific
`-enablewpoa*` flag then overrides its own phase.

```bash
# Full stack except sortition:
./src/multichain-util create mychain -enablewpoa=1 -enablewpoasortition=0
```

Resolution has three levels, in order: the value inherited from `params.dat` → the
runtime master `-enablewpoa` / `-wpoaenable` → the explicit per-phase flag (which wins).
Creation-time master expansion lives in
[`params.cpp`](../../chainparams/params.cpp) (`Read(argc,argv)`); runtime resolution in
[`init.cpp`](../../core/init.cpp) (`AppInit2`).

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
| `enablewpoaselection` requires `enablewpoaweights` | `init.cpp:3334` |
| `enablewpoavrf` requires `enablewpoaselection` | `init.cpp:3336` |
| `enablewpoarandao` requires `enablewpoavrf` | `init.cpp:3338` |
| `enablewpoasortition` requires `enablewpoarandao` | `init.cpp:3340` |
| `enablewpoasortition` requires `wpoarandaolookback >= 1` | `init.cpp:3342` |
| `enablewpoamalus` requires `enablewpoasortition` | `init.cpp:3426` |
| `wpoamalusequivpoints` must be `>` `wpoamalusdelaypoints` | `init.cpp:3419` |
| `enableweightengine` requires `enablewpoaweights` | `init.cpp:3498` |

The `k >= 1` constraint is not arbitrary: the reveal that sortition produces feeds
`R_tot[n]`, while its own seed reads `R_tot[n-k]`. At `k = 0` the dependency would be
circular.

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
([`paramlist.h`](../../chainparams/paramlist.h), entry `targetblocktime`), `delta` is
`-wpoasortitiondelta`, `lambda` is `-wpoasortitionlambda`, and `W` is the sum of the
compressed effective weights. Implementation: `PrivateSortition::MiningDelay()` in
[`private_sortition.h`](../private_sortition.h).

The `W` factor is what makes the normalisation real: without it the value inherits the
scale of `E/w` and collapses toward `0` for every candidate as soon as weights reach the
hundreds. With it, the **winner's** normalised score is exactly `U(0,1)`, so its delay is
uniform across the band and the mean block time lands on target.

A validator accepts a block if and only if
`block.nTime >= parent.nTime + MiningDelay(score_i, ...)`. This time bar **replaces** the
equality test on the public argmin, and its auto-relaxing nature is the liveness
mechanism: there is no hard threshold, so the online validator with the minimum score
always eventually proposes.

Full detail: [phase4-implementation-guide.md](phase4-implementation-guide.md) and
[private-sortition.md](private-sortition.md).

---

## 3. Catalogue — behavioural malus registry

Requires `-enablewpoasortition`: both evidence kinds are proved against the block's VRF
reveal over the beacon seed.

| CLI flag | `params.dat` | Type | Default | Valid range | Defined | Effect on consensus |
|---|---|---|---|---|---|---|
| `-enablewpoamalus` | `enable-wpoa-malus` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:204` | Runs the open `wpoa-weights-malus` stream and elects on the effective weight `w_eff = w * Psi` rather than the raw one. Inert when nobody carries a violation (`Psi = 1`). |
| `-wpoamalusmu` | `wpoa-malus-mu` | `STRING(32)` | `0.5` | `[0, 1)` — `1` excluded | `paramlist.h:208` | Accumulator persistence: the fraction of `M` carried into the next epoch. **`mu < 1` is what makes an exclusion reversible.** |
| `-wpoamalusmax` | `wpoa-malus-max` | `STRING(32)` | `4` | `> 0` | `paramlist.h:212` | Threshold `M_max` at which `Psi` reaches `0` and the validator becomes ineligible. |
| `-wpoamalusequivpoints` | `wpoa-malus-equiv-points` | `STRING(32)` | `4` | `> 0`, and **`>` delay points** | `paramlist.h:216` | Score of one proved equivocation (two distinct blocks at one height) — a *safety* fault. |
| `-wpoamalusdelaypoints` | `wpoa-malus-delay-points` | `STRING(32)` | `0.25` | `> 0` | `paramlist.h:220` | Score of one proved delay violation (a block mined earlier than its own score entitled it to) — a *scheduling* fault. |

The correction is `Psi = max(0, 1 - M/M_max)`, with `M` an exponential moving average.
Because `mu < 1`, an exclusion always clears after a finite number of clean epochs:
**there is no permanent ban.** The stream is deliberately **open** — anyone may report,
nobody is believed: every node re-derives the evidence from public chain data, so a false
report is discarded identically everywhere and moves no weight.

Detail: [malus-registry.md](malus-registry.md).

---

## 4. Catalogue — weight engine

The weight engine **produces** the weights the wPoA layer consumes, so it requires the
weights stream. Module detail: [weight-engine.md](weight-engine.md).

| CLI flag | `params.dat` | Type | Default | Valid range | Defined | Effect on consensus |
|---|---|---|---|---|---|---|
| `-enableweightengine` | `enable-weight-engine` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:225` | Derives each cluster's weight from the on-chain inputs (membership / ESG / activity / reconciliation) once per epoch, **instead of** the static `-weight`. |
| `-weightepochlength` | `weight-epoch-length` | `UINT32` | `100` | `[1, 1000000]` | `paramlist.h:229` | Epoch length in blocks. The epoch is **1-based**: `epoch(height) = height / n + 1`. Determines the epoch boundaries the miner and every validator must agree on. |
| `-weightkappa` | `weight-kappa` | `STRING(32)` | `100` | `> 0` | `paramlist.h:233` | Normalisation constant `kappa` in the company contribution `c_i = ESG_i * tau_i / kappa`. |
| `-weightalpha` | `weight-alpha` | `STRING(32)` | `0.2` | `[0, 1]` | `paramlist.h:237` | Allocation constant `alpha` in `A_k = alpha * Theta * W_k / W_tot`. |
| `-weightlambda` | `weight-lambda` | `STRING(32)` | `0.5` | `[0, 1)` — `1` excluded | `paramlist.h:241` | Behavioural-feedback damping in `w_k = W_k * [rho_{k,e-1} * lambda + (1 - lambda)]`. **`lambda < 1` is a correctness requirement**, not a preference: it guarantees weight positivity. |

Two related constants are **not** chain parameters yet, and are fixed at compile time in
[`weight_streams.h`](../../weight_engine/weight_streams.h):

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
| `-weight=<n>` | integer | `100` | `> 0` (positive integers) | `MC_WPOA_DEFAULT_WEIGHT`, [`stream_weight_registry.h`](../stream_weight_registry.h) | `init.cpp:3234` — `-weight <= 0` prevents startup |

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

**An unauthorized node cannot impose its own weight by any means**, neither through
`-weight` nor through RPC. Detail of the two-gate authorization model:
[weight-engine.md](weight-engine.md) and
[stream-weight-registry.md](stream-weight-registry.md).

---

## 6. Value validation at startup

Real-valued parameters travel as `MC_PRM_STRING` and are converted in `AppInit2` with
NaN/Inf-safe checks: a non-finite value is rejected, not propagated.

| Parameter | Check | Line |
|---|---|---|
| `-weight` | integer `> 0` | `init.cpp:3234` |
| `-wpoarandaolookback` | non-negative integer | `init.cpp:3285` |
| `-wpoasortitiondelta` | number in `(0, 1)` | `init.cpp:3297` |
| `-wpoasortitionlambda` | number in `[0, 1]` | `init.cpp:3308` |
| `-wpoamalusmu` | number in `[0, 1)` | `init.cpp:3394` |
| `-wpoamalusmax` | number `> 0` | `init.cpp:3400` |
| `-wpoamalusequivpoints` | number `> 0` | `init.cpp:3406` |
| `-wpoamalusdelaypoints` | number `> 0` | `init.cpp:3412` |
| `-weightepochlength` | integer in `[1, 1000000]` | `init.cpp:3468` |
| `-weightkappa` | number `> 0` (and `< 1e18`) | `init.cpp:3479` |
| `-weightalpha` | number in `[0, 1]` | `init.cpp:3485` |
| `-weightlambda` | number in `[0, 1)` | `init.cpp:3491` |

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

# Full stack with the behavioural malus registry:
./src/multichain-util create mychain -enablewpoa=1 -enablewpoamalus=1

# Dynamic weights derived from the on-chain inputs, 200-block epochs:
./src/multichain-util create mychain -enablewpoa=1 \
    -enableweightengine=1 -weightepochlength=200

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
