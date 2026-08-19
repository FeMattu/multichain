# wPoA — Weighted Proof-of-Authority for MultiChain

> A **Weighted Proof-of-Authority** consensus extension for MultiChain: every
> validator advertises a positive integer **weight** on a native append-only
> stream (Phase 1), and block proposers are elected in **proportion to that
> weight** via the Efraimidis–Spirakis weighted-sampling transform (Phase 2).
> This file is the entry point; the deep, per-phase documentation lives in
> [`docs/`](docs/) — start at the master
> [implementation-guide.md](docs/implementation-guide.md).

---

## What wPoA is

**wPoA** (*Weighted Proof-of-Authority*) extends MultiChain's round-robin
Proof-of-Authority with a notion of **validator weight**, so that block
production is biased toward higher-weight validators instead of being uniform.

Five phases are implemented today:

- **Phase 1 — Weight registry.** When `-enablewpoaweights=1` (default off; forced
  on by any higher phase or by the `-enablewpoa` master switch), each node records
  its weight on an append-only MultiChain stream (`wpoa-weights`), kept current
  (newest wins) and identical on every node (confirmed-on-chain data only), exposed
  through three RPC commands and a `StreamWeightRegistry` class. This phase can run
  standalone (e.g. to collect weights) with everything else off.
- **Phase 2 — Weighted miner selection.** When `-enablewpoaselection=1`, the miner and
  the block validator elect each height's proposer in proportion to weight via
  the Efraimidis–Spirakis argmin, seeded by the previous block hash, bypassing
  the native round-robin mining-diversity gate. This phase is intentionally
  public/predictable — the substrate-validation baseline before privacy is added
  in later phases.
- **Phase 3a — VRF randomness beacon (generation).** When `-enablewpoavrf=1`,
  each wPoA-elected proposer additionally publishes a **verifiable pseudorandom
  reveal** `R[n]=VRF_sk(h[n-1])` with proof `π[n]` in its block (an ECVRF/DLEQ
  over the bundled secp256k1), and every peer verifies it before accepting the
  block. Selection is unchanged; the VRF is a grinding-resistant contribution to
  the beacon that Phase 3b accumulates and Phase 4 consumes for private
  sortition.
- **Phase 3b — RANDAO beacon seed (accumulation).** When `-enablewpoarandao=1`,
  the per-block reveals are folded into a running accumulator
  `R_tot[n]=H(R_tot[n-1]⊕H(R[n]))` and the proposer election is seeded by the
  lookback beacon seed `seed[n+1]=H(R_tot[n-k]‖h[n]‖n+1)` instead of the plain
  previous block hash (lookback `k` set by `-wpoarandaolookback`). Only the seed
  source changes — the Efraimidis–Spirakis election stays weight-proportional —
  so the beacon is grinding-resistant with a bounded last-revealer bias, while
  leader unpredictability remains Phase 4's job.
- **Phase 4 — Efraimidis private sortition (the security fix).** When
  `-enablewpoasortition=1`, each validator evaluates its election score
  **privately** — `u_i = VRF_sk_i(seed ‖ "PROPOSER" ‖ height)` under its own
  secret key, scored with the *same* `-ln(u_i)/f(w_i)` transform as Phase 2 — so
  no peer can compute it. A validator self-elects by mining after a delay that
  increases with its score — a band around `target-block-time`,
  `D = T + δ·T·(2·score_norm − 1) + λ·Φ` with `score_norm = 1 − e^{−W·score}`, whose
  `W` factor is what keeps the candidates spread across the band instead of crushed
  against its early edge — so the argmin proposes **first**; peers accept a block
  iff its VRF reveal verifies over the sortition input and its `nTime` is no
  earlier than the score entitles (the time bar that replaces the public argmin
  equality). The proposer is thus unknowable until it acts, the distribution stays
  `Pr[i]=w_i/Σw`, and the auto-relaxing time bar is the liveness fallback (no
  zero-proposer gap). Requires `-enablewpoarandao` and lookback `k≥1`; delay scale
  set by `-wpoasortitiondelta`; optional global feedback gain `-wpoasortitionlambda`.

- **Behavioural malus registry.** When `-enablewpoamalus=1`, a second — and
  deliberately **open** — stream `wpoa-weights-malus` records proved
  misbehaviour: an *equivocation* (two distinct blocks at one height, which VRF
  uniqueness makes impossible by accident) or a *delay violation* (a block mined
  earlier than its own score entitled it to). Anyone may report; nobody is
  believed. Every node re-derives the evidence from public chain data, so a false
  report is discarded identically everywhere and moves no weight. Valid reports
  accumulate into a decaying severity `M`, which becomes the correction
  `Psi = max(0, 1 - M/M_max)`, and the election consumes the **effective weight**
  `w_eff = w * Psi` instead of the raw one. `M` is an exponential moving average,
  so an exclusion always clears after a finite number of clean epochs — there is
  no permanent ban. Inert on honest behaviour (`Psi = 1`). Requires
  `-enablewpoasortition`. Full detail:
  [malus-registry.md](docs/malus-registry.md).

Phase 5 (VDF over the beacon output, removing the residual last-revealer bias) is
planned — see the [Implementation status](#implementation-status) and the master
[implementation-guide.md](docs/implementation-guide.md).

Operators only ever touch a few things:

- the per-node parameter **`-weight=<n>`** (positive integer, default `100`) — this
  node's own validator weight, published on the `wpoa-weights` stream. It is *not* a
  chain parameter (each node sets its own);
- the wPoA switches (see **Startup configuration** below), and
- the RPC commands **`getlocalweight`**, **`getnodeweight`**, **`getallweights`**,
  and — when the malus registry is on — **`getallmalus`**, **`getnodemalus`**,
  **`reportmalus`**.

Everything else — stream layout, transaction plumbing, wallet indexes, the
election math — is hidden behind the `StreamWeightRegistry` facade and the
`WPoASelector`.

### Startup configuration — flags & `params.dat` inheritance

Every wPoA switch is a **chain parameter**: it is set when the chain is created
(`multichain-util create <chain> -enablewpoa=1 …`), written into `params.dat`, and
**inherited** by any node that joins. A fresh node therefore needs no command-line
flags — it just runs `multichaind <chain>@<seed>` and picks up the right protocol.
A chain created with no wPoA flags is a plain MultiChain instance.

The same names also work as **runtime flags** on `multichaind`, overriding the
inherited value for that node only. Because the parameters are **hash-enforced**,
a divergent override risks a silent fork; `AppInit2` logs a loud warning but does
not prevent startup.

The master switch `-enablewpoa` (alias `-wpoaenable`) turns every phase on; a more
specific `-enablewpoa*` flag then overrides its phase. Phases must be enabled
bottom-up — `weights → selection → vrf → randao → sortition → malus` — and a
violation is a **hard failure** at both chain creation and node startup.

> **Every parameter — name, type, default, valid range, defining and validating code
> line, and effect on consensus — is catalogued in one place:
> [docs/protocol-parameters.md](docs/protocol-parameters.md).**
> Do not duplicate parameter values here.

How the switches are read, resolved and wired into `AppInit2`:
[docs/node-startup.md](docs/node-startup.md).

---

## Architecture at a glance

> Macro view of the whole feature across phases. This is deliberately
> high-level; the per-phase mechanics live in the phase guides linked from the
> master [implementation-guide.md](docs/implementation-guide.md). **Keep this
> diagram in sync whenever the architecture changes** (see the
> [Documentation Maintenance](docs/implementation-guide.md#documentation-maintenance)
> process).

```mermaid
flowchart TD
    subgraph SRC [Weight assignment — see implementation-status.md §0.1 for the full flow]
        ADM([Authorized node: admin / governance]):::ok
        ADM -->|"RPC weightset* — CanAdmin gate"| ENG["WeightEngine<br/>w_k from on-chain inputs, per epoch"]
        OPCLI([Local flag -weight=N]):::weak
        OPCLI -.->|"fallback, only if -enableweightengine=0"| STATREG["ThreadRegisterNodeWeight"]
        GATE{{"wpoa-weights.write required<br/>the stream is CLOSED"}}:::gate
        ENG -->|"authoritative channel"| GATE
        STATREG --> GATE
        UNAUTH([Unauthorized node]):::bad -.->|"write refused — no weight at all"| GATE
    end

    subgraph P1 [Phase 1 — Weight registry]
        STREAM[(wpoa-weights stream<br/>append-only, on-chain, CLOSED)]
        REG["StreamWeightRegistry<br/>deferred register + read core"]
        REG -->|write via in-process RPC handlers| STREAM
        STREAM -->|"non-WRP confirmed reads, newest wins"| REG
    end

    GATE --> STREAM
    REG ==>|"OVERRIDE: the on-chain value governs,<br/>never the local flag"| OPCLI

    MALUS["WPoAApplyMalus<br/>w_eff = w · Ψ  (behavioural malus)"]
    REG -->|"w"| MALUS

    subgraph P2 [Phase 2 — Weighted selection]
        SEL["WPoASelector<br/>score_i = −ln(u_i)/f(w_eff); argmin"]
        MINE["miner.cpp<br/>mine only if elected"]
        VAL["multichainblock.cpp<br/>reject non-elected proposer"]
        SEL --> MINE
        SEL --> VAL
    end

    subgraph P3A [Phase 3a — VRF beacon]
        VRF["WPoAVRF (vrf_wrapper)<br/>Prove / Verify — ECVRF/DLEQ over secp256k1"]
        MVRF["miner.cpp<br/>embed R,π = VRF_sk(prevhash)"]
        VVRF["multichainblock.cpp<br/>reject missing/invalid reveal"]
        VRF --> MVRF
        VRF --> VVRF
    end

    subgraph P3B [Phase 3b — RANDAO beacon seed]
        RND["RandaoAccumulator<br/>R_tot=H(R_tot⊕H(R)); seed=H(R_tot[n−k]‖h[n]‖n+1)"]
        RSEED["miner.cpp / multichainblock.cpp<br/>seed from R_tot instead of prevhash"]
        RND --> RSEED
    end

    subgraph P4 [Phase 4 — Private sortition]
        PS["PrivateSortition<br/>u=VRF_sk(seed‖PROPOSER‖h); score=−ln(u)/f(w_eff)<br/>score_norm = 1−e^(−W·score)<br/>D = T + δ·T·(2·score_norm−1) + λ·Φ"]
        PMINE["miner.cpp<br/>self-elect: mine at now + D"]
        PVAL["multichainblock.cpp<br/>verify VRF + score;<br/>accept iff nTime ≥ parent.nTime + D"]
        PS --> PMINE
        PS --> PVAL
    end

    MALUS -->|"GetAllNodesWeights() → w_eff"| SEL
    MALUS -->|"w_eff + Σf(w_eff)"| PS
    MINE -.->|"elected proposer signs"| MVRF
    VAL -.->|"on wPoA-VRF heights"| VVRF
    VVRF -.->|"reveals R[n]"| RND
    RSEED -.->|"seed → WPoASelectProposer (unchanged argmin)"| SEL
    RSEED -.->|"beacon seed = private VRF input"| PS
    PVAL -.->|"reveal R[n] over sortition input"| RND
    CLI([multichain-cli getlocalweight / getnodeweight / getallweights]):::ext --> REG

    classDef ext  fill:#eee,stroke:#999,color:#333;
    classDef ok   fill:#e8f5e9,stroke:#4c9a51,color:#1b3d1f;
    classDef bad  fill:#fdd,stroke:#c66,color:#633;
    classDef weak fill:#f4f4f4,stroke:#aaa,color:#555;
    classDef gate fill:#fff4d6,stroke:#c9a227,color:#5a4708;
```

- **Phase 1** records and serves weights on the `wpoa-weights` stream via the
  `StreamWeightRegistry` facade (deferred background registration; confirmed-only
  reads that are safe from any thread). Full detail:
  [phase1-implementation-guide.md](docs/phase1-implementation-guide.md).
- **Phase 2** consumes `GetAllNodesWeights()` and elects each height's proposer
  in proportion to weight, gating the miner and the block validator behind
  `-enablewpoaselection` (or the `-enablewpoa` master switch). Full detail:
  [phase2-implementation-guide.md](docs/phase2-implementation-guide.md).
- **Phase 3a** adds the VRF beacon behind `-enablewpoavrf`: the elected proposer
  embeds a verifiable reveal `(R, π)` in its block (via `WPoAVRF`, an ECVRF/DLEQ
  over the bundled secp256k1) and every peer verifies it. Selection is unchanged.
  Full detail:
  [phase3a-implementation-guide.md](docs/phase3a-implementation-guide.md).
- **Phase 3b** adds the RANDAO beacon seed behind `-enablewpoarandao`: the
  per-block reveals are folded into `R_tot` (via `RandaoAccumulator`) and the
  selection seed becomes `H(R_tot[n-k]‖h[n]‖n+1)`, consumed identically by the
  miner and validator. Only the seed source changes; the election stays
  weight-proportional. Full detail:
  [phase3b-implementation-guide.md](docs/phase3b-implementation-guide.md).
- **Phase 4** makes selection private behind `-enablewpoasortition` (via
  `PrivateSortition`): each validator scores itself with a VRF over the beacon
  seed under its own key and self-elects by a mining delay **banded on
  target-block-time**, `D = T + δ·T·(2·score_norm − 1) + λ·Φ` with
  `score_norm = 1 − e^{−W·score}` (argmin proposes first); the validator replaces
  the public argmin equality with a VRF-verify + score-recompute +
  `nTime`-time-bar eligibility check. The proposer is unpredictable until it acts;
  the distribution is unchanged; and because the winner's normalized score is
  exactly uniform, the mean realized block time lands on the target. Full
  detail: [phase4-implementation-guide.md](docs/phase4-implementation-guide.md).

---

## Documentation Structure

This project contains multiple levels of documentation:

1. **[Thesis Project Overview](docs/thesis-project-overview.md)**
   - For researchers & students: Theory, threat modeling, literature review, mathematical foundations
   - Learn WHY we use Efraimidis–Spirakis and what security properties it provides

2. **[Implementation Roadmap](docs/implementation-roadmap.md)**
   - For developers & contributors: Phased plan, current status, components, vulnerabilities
   - Understand what's implemented, what's planned, and how pieces connect

3. **[Implementation Guide (master index)](docs/implementation-guide.md)**
   - The high-level map of all phases + links to each phase's dedicated technical
     guide, and the **Documentation Maintenance** process for future features
   - Start here for code, then dive into the phase guide you need:
     [Phase 1](docs/phase1-implementation-guide.md) ·
     [Phase 2](docs/phase2-implementation-guide.md)

---

## Documentation

All detailed documentation lives in [`docs/`](docs/). Start at the master
**[implementation-guide.md](docs/implementation-guide.md)** (phase map + links),
or the **[Documentation Structure](#documentation-structure)** above if you're
new to the project.

| Document | What it covers |
|----------|----------------|
| [implementation-guide.md](docs/implementation-guide.md) | **Master index.** High-level map of all phases, how they build on each other, links to every per-phase guide, and the Documentation Maintenance process. |
| [phase1-implementation-guide.md](docs/phase1-implementation-guide.md) | **Phase 1 — full technical guide.** Weight registry: mental model, data model, design decisions, threading & locking, full code walkthrough, control flow, "how to modify" recipes. |
| [phase2-implementation-guide.md](docs/phase2-implementation-guide.md) | **Phase 2 — full technical guide.** Weighted miner selection: mental model, algorithm, design decisions, threading, full code walkthrough, control flow, edge cases, "how to modify" recipes, tests, and accepted risks / Phase 3-4 hooks. |
| [phase3a-implementation-guide.md](docs/phase3a-implementation-guide.md) | **Phase 3a — full technical guide.** VRF randomness beacon: the ECVRF/DLEQ construction over secp256k1, on-chain carriage of the reveal, prover/verifier control flow, design decisions, edge cases, tests, and Phase 3b/4 hooks. |
| [phase3b-implementation-guide.md](docs/phase3b-implementation-guide.md) | **Phase 3b — full technical guide.** RANDAO beacon seed: the accumulator fold + lookback seed (thesis §5.4–§5.5), the memoized block-index walk, the seed swap at both selection call sites, design decisions, edge cases, tests, and Phase 4 hooks. |
| [phase4-implementation-guide.md](docs/phase4-implementation-guide.md) | **Phase 4 — full technical guide.** Efraimidis private sortition (the security fix): the private VRF score, score-timed self-election, the validator-side VRF-verify + score + time-bar eligibility that replaces the public argmin, the auto-relaxing liveness fallback, design decisions, edge cases, tests, and Phase 5 hooks. |
| [thesis-project-overview.md](docs/thesis-project-overview.md) | Research companion: problem statement, threat model, literature review, theoretical contributions behind the wPoA design (bachelor's thesis, Università di Pisa). |
| [implementation-roadmap.md](docs/implementation-roadmap.md) | Engineering companion: phased plan, rationale for private (Efraimidis) sortition over public WRS, current status, vulnerabilities & mitigations. |
| [multichain-internals.md](docs/multichain-internals.md) | Reference to the MultiChain host APIs this module builds on, with exact `file:line` pointers — entities, the wallet-tx store, script decoding, RPC-handler reuse, permissions, mining. |
| [stream-weight-registry.md](docs/stream-weight-registry.md) | Line-by-line walkthrough of the Phase 1 registry class and background thread (`stream_weight_registry.h` + `.cpp`). |
| [weight-record.md](docs/weight-record.md) | Walkthrough of the pure, dependency-light parsing/aggregation helpers (`weight_record.h`) that are unit-tested in isolation. |
| [wpoa-selector.md](docs/wpoa-selector.md) | Line-by-line walkthrough of the Phase 2 selector core and node glue (`wpoa_selector.h` + `.cpp`): scoring, argmin, activation gate, registry read. §5 covers the Phase 3a `g_wpoa_vrf_enabled` / `WPoAVRFActiveAtHeight` glue. |
| [miner-integration.md](docs/miner-integration.md) | How the weighted election is wired into block production (`miner/miner.cpp`, `GetMinerAndExpectedMiningStartTime`). |
| [block-validation.md](docs/block-validation.md) | How the election is enforced on the receiving side (`protocol/multichainblock.cpp`, `VerifyBlockMiner` → `VerifyBlockMinerWPoA`). |
| [vrf-wrapper.md](docs/vrf-wrapper.md) | **Phase 3a.** Line-by-line walkthrough of the pure VRF core (`vrf_wrapper.h` + `.cpp`): hash-to-curve, deterministic nonce, DLEQ prove/verify, point/scalar helpers over secp256k1. |
| [block-vrf-encoding.md](docs/block-vrf-encoding.md) | **Phase 3a.** How the reveal is carried on-chain (`protocol/multichainscript.h` + `.cpp`): `SetBlockVRF`/`GetBlockVRF` and the `GetBlockSignature` length relaxation. |
| [vrf-prover.md](docs/vrf-prover.md) | **Phase 3a.** How the reveal is produced and embedded (`miner/miner.cpp`, `CreateBlockSignature`). |
| [vrf-verifier.md](docs/vrf-verifier.md) | **Phase 3a.** How the reveal is extracted and enforced (`protocol/multichainblock.cpp`, `FindBlockVRF` + `VerifyBlockMinerWPoA`). |
| [randao-accumulator.md](docs/randao-accumulator.md) | **Phase 3b.** Deep line-by-line walkthrough of the pure accumulator/seed core (`randao_accumulator.h`) and the node glue (`.cpp`): the fold, the seed derivation, the memoized block-index walk, reveal extraction. |
| [randao-miner.md](docs/randao-miner.md) | **Phase 3b.** The miner-side seed swap (`miner/miner.cpp`, `GetMinerAndExpectedMiningStartTime`): defaulting to the prev-hash seed, then overwriting with the RANDAO seed when the beacon governs the next height. |
| [randao-validator.md](docs/randao-validator.md) | **Phase 3b.** The validator-side seed swap (`protocol/multichainblock.cpp`, `VerifyBlockMinerWPoA`): recomputing the same seed over the block's parent and enforcing the elected proposer. |
| [private-sortition.md](docs/private-sortition.md) | **Phase 4.** Line-by-line walkthrough of the pure sortition core (`private_sortition.h`: `VRFInput`/`ScoreFromVRFOutput`/`MiningDelay`) and the node glue (`.cpp`): activation gate, shared context, local score+delay, reveal-input builder, eligibility/time-bar verdict, anti-respin guard. |
| [sortition-miner.md](docs/sortition-miner.md) | **Phase 4.** The miner-side hook (`miner/miner.cpp`): score-timed self-election, the anti-respin guard, the reveal-input switch, and marking the proposed height. |
| [sortition-validator.md](docs/sortition-validator.md) | **Phase 4.** The validator-side hook (`protocol/multichainblock.cpp`, `VerifyBlockMinerWPoA`): the VRF-verify + score-recompute + time-bar eligibility check that replaces the public argmin equality on sortition heights. |
| [malus-registry.md](docs/malus-registry.md) | **Behavioural malus.** Why a second registry exists, why the two streams carry opposite write policies, the two evidence kinds and the `Valid(e)` predicate that makes an open stream safe, the decaying accumulator and the reversibility of an exclusion, epoch alignment, and the single point where `w_eff` enters consensus. |
| [node-startup.md](docs/node-startup.md) | How the wPoA switches — the `-enablewpoa` master, `-enablewpoaweights` (Phase 1), `-enablewpoaselection`/`-dumpfunction` (Phase 2), `-enablewpoavrf` (Phase 3a), `-enablewpoarandao`/`-wpoarandaolookback` (Phase 3b), `-enablewpoasortition`/`-wpoasortitiondelta`/`-wpoasortitionlambda` (Phase 4) — are read from `params.dat` (inherited) with CLI override, resolved (master + precedence + hard-fail constraints) and wired into `AppInit2`, and how the background thread is launched (`core/init.h` + `.cpp`, wPoA parts). |
| [rpc-registration.md](docs/rpc-registration.md) | How the three RPC commands are added to the dispatch table (`rpc/rpclist.cpp`). |
| [testing.md](docs/testing.md) | Build steps, unit tests, the MultiChain mining model, manual single-/multi-node tests, the automated smoke test, and troubleshooting. |

### Source & test files

| File | Role |
|------|------|
| [`stream_weight_registry.h`](stream_weight_registry.h) / [`.cpp`](stream_weight_registry.cpp) | Phase 1: public API + implementation of the registry, background thread and RPC handlers. |
| [`weight_record.h`](weight_record.h) | Phase 1: pure parsing/aggregation helpers (json_spirit-only, unit-testable). |
| [`wpoa_selector.h`](wpoa_selector.h) / [`.cpp`](wpoa_selector.cpp) | Phase 2: pure Efraimidis–Spirakis selector core (header-only) + node-coupled glue (flag, activation predicate, registry-backed election). Phase 3a adds the `g_wpoa_vrf_enabled` flag and `WPoAVRFActiveAtHeight`. |
| [`vrf_wrapper.h`](vrf_wrapper.h) / [`.cpp`](vrf_wrapper.cpp) | Phase 3a: pure `WPoAVRF` ECVRF/DLEQ core over secp256k1 (`Prove`/`Verify`), node-free and unit-testable. |
| [`randao_accumulator.h`](randao_accumulator.h) / [`.cpp`](randao_accumulator.cpp) | Phase 3b: pure `RandaoAccumulator` core (`Fold`/`DeriveSeed`/`Genesis`, node-free) + node glue (flag/lookback, `WPoARANDAOActiveAtHeight`, the memoized accumulator walk, and the `WPoARandaoSelectionSeed` helper). |
| [`private_sortition.h`](private_sortition.h) / [`.cpp`](private_sortition.cpp) | Phase 4: pure `PrivateSortition` core (`VRFInput`/`ScoreFromVRFOutput`/`MiningDelay`, node-free) + node glue (flag/scale, `WPoASortitionActiveAtHeight`, local score+delay, reveal-input builder, `WPoASortitionVerifyProposer`, anti-respin guard). Reuses the Phase-2 score transform (`WPoASelector::ScoreFromEntropy64`). |
| [`malus_record.h`](malus_record.h) | Behavioural malus: pure record parsing + accumulator core (`Fold`/`CorrectionFactor`/`EffectiveWeight`/`EpochsToClear`), node-free and unit-testable. |
| [`malus_registry.h`](malus_registry.h) / [`.cpp`](malus_registry.cpp) | Behavioural malus: the open `wpoa-weights-malus` stream, the `Valid(e)` evidence predicate, the per-epoch accumulator, `WPoAApplyMalus` (the single consensus entry point) and the RPCs. |
| [`test/wpoa_weight_tests.cpp`](test/wpoa_weight_tests.cpp) | Phase 1: Boost.Test unit tests for the pure registry logic. |
| [`test/wpoa_malus_tests.cpp`](test/wpoa_malus_tests.cpp) | Behavioural malus: Boost.Test unit tests for the pure core (parsing, EMA fold, `Psi`, `w_eff`, reversibility of an exclusion). |
| [`test/wpoa_selector_tests.cpp`](test/wpoa_selector_tests.cpp) | Phase 2: Boost.Test unit tests for the pure selector math (determinism, order-independence, probability preservation). |
| [`test/vrf_wrapper_tests.cpp`](test/vrf_wrapper_tests.cpp) | Phase 3a: Boost.Test unit tests for the pure VRF core (roundtrip, determinism, tamper/forgery/cross-key rejection, pseudorandomness). |
| [`test/randao_accumulator_tests.cpp`](test/randao_accumulator_tests.cpp) | Phase 3b: Boost.Test unit tests for the pure accumulator/seed core (spec conformance vs. an independent reference, determinism, order/input sensitivity, chain consistency). |
| [`test/private_sortition_tests.cpp`](test/private_sortition_tests.cpp) | Phase 4: Boost.Test unit tests for the pure sortition core (VRF-input encoding, score reuse vs. the shared transform, delay map, key-dependence/privacy, and probability preservation with real VRF keys). |
| [`test/run_unit_tests.sh`](test/run_unit_tests.sh) | Build + run **all** unit suites, or a named subset — `run_unit_tests.sh selector vrf` (no node build needed). |
| [`test/run_functional_tests.sh`](test/run_functional_tests.sh) | Wrapper around the single system run: warning banner, hard timeout, correct exit code. |
| [`test/run_all_tests.sh`](test/run_all_tests.sh) | Single entrypoint: run unit tests, then the functional run, to validate the whole system. See [`test/README.md`](test/README.md). |
| [`test/functional_test_wpoa_system.sh`](test/functional_test_wpoa_system.sh) / [`test/functional_lib.sh`](test/functional_lib.sh) / [`test/analyze_distribution.py`](test/analyze_distribution.py) | **The** functional test: ONE full-stack network, warmed up once, then all feature checks (weight, stream permissions, malus, multi-node consistency, VRF, RANDAO, sortition, chi-square distribution) on the shared run. `INCLUDE_PUBLIC_SELECTOR=1` adds the sortition-off (public argmin) regime; `QUICK=1` uses a smaller sample. |

Integration points in the host tree: [`../core/init.cpp`](../core/init.cpp)
(startup flags, incl. `-enablewpoavrf`, `-enablewpoarandao`/`-wpoarandaolookback`
and `-enablewpoasortition`/`-wpoasortitiondelta`/`-wpoasortitionlambda`),
[`../rpc/rpclist.cpp`](../rpc/rpclist.cpp) /
[`../rpc/rpchelp.cpp`](../rpc/rpchelp.cpp) (RPCs),
[`../miner/miner.cpp`](../miner/miner.cpp) (Phase 2 mining hook + Phase 3a reveal
embedding + Phase 3b selection-seed swap + Phase 4 score-timed self-election &
reveal-input switch),
[`../protocol/multichainblock.cpp`](../protocol/multichainblock.cpp)
(Phase 2 validation hook + Phase 3a reveal verification + Phase 3b selection-seed
swap + Phase 4 eligibility/time-bar check),
[`../protocol/multichainscript.cpp`](../protocol/multichainscript.cpp)
(Phase 3a `SetBlockVRF`/`GetBlockVRF` reveal carriage, reused unchanged by Phase 4),
[`../Makefile.am`](../Makefile.am) (build). See
[phase1-implementation-guide.md §7](docs/phase1-implementation-guide.md),
[phase2-implementation-guide.md §5](docs/phase2-implementation-guide.md),
[phase3a-implementation-guide.md §2](docs/phase3a-implementation-guide.md),
[phase3b-implementation-guide.md §2](docs/phase3b-implementation-guide.md) and
[phase4-implementation-guide.md §2](docs/phase4-implementation-guide.md) for
details.

---

## Implementation status

Lo stato di implementazione di ogni fase — componenti fatti, non fatti, con
riferimento diretto ai file di codice e ai test che li validano — vive in **una sola
sede**:

> **[docs/implementation-status.md](docs/implementation-status.md)**

Quel file contiene anche l'architettura di alto livello, il diagramma autorevole del
flusso di assegnazione del peso, e la distinzione fra `mining-turnover` (hint
operativo locale) e `mining-diversity` (regola di consenso vincolante).

**In sintesi:** le fasi 1, 2, 3a, 3b e 4 sono complete e validate end-to-end, così
come il registro del malus comportamentale e il weight engine. La fase 5 (VDF sopra
l'output del beacon) è pianificata e non implementata.

---

## Quick start

```bash
# Build (Makefile.am changed, so regenerate first):
cd /home/mattu/multichain
./autogen.sh && ./configure && make

# Preferred: bake the configuration into the chain at creation, so every node that
# joins inherits it via params.dat and needs no wPoA flags of its own:
./src/multichain-util create <chain> -enablewpoa=1        # whole protocol on
./src/multichaind <chain>                                 # this node ...
./src/multichaind <chain>@<seed-ip>:<port>                # ... and any joiner

# Run a node with its own validator weight (weight is per-node, not a chain param):
./src/multichaind <chain> -weight=100

# Phase 1 only (just collect weights on the wpoa-weights stream), nothing else:
./src/multichaind <chain> -weight=100 -enablewpoaweights=1

# Full stack as *runtime* flags (equivalent to the master switch). The master
# -enablewpoa=1 alone already turns all phases on; specific flags would override it
# per phase. All consensus knobs (lookback k, delay scale, dump function) must be
# identical on every validator; sortition requires the beacon and k>=1.
./src/multichaind <chain> -weight=100 -enablewpoa=1 \
                          -wpoarandaolookback=1 -wpoasortitiondelta=0.5

# Full stack EXCEPT sortition (specific flag overrides the master):
./src/multichaind <chain> -weight=100 -enablewpoa=1 -enablewpoasortition=0

# Query weights:
./src/multichain-cli <chain> getallweights
```

Full build and test instructions are in [testing.md](docs/testing.md) and
[`test/README.md`](test/README.md). All unit suites (weight, malus, selector, VRF,
RANDAO, sortition) run node-free via
[`test/run_unit_tests.sh`](test/run_unit_tests.sh) — pass a suite name to run
just one, e.g. `run_unit_tests.sh vrf`. The malus suite runs the same way
(`run_unit_tests.sh malus`). The functional tests are now a single
system-level run,
[`test/functional_test_wpoa_system.sh`](test/functional_test_wpoa_system.sh)
(wrapped by [`test/run_functional_tests.sh`](test/run_functional_tests.sh)): it
starts ONE full-stack network and verifies weight, multi-node consistency, VRF,
RANDAO, sortition and the chi-square distribution on that shared run. Run
absolutely everything with [`test/run_all_tests.sh`](test/run_all_tests.sh).
