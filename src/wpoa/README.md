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

Three phases are implemented today:

- **Phase 1 — Weight registry.** Each node records its weight on an append-only
  MultiChain stream (`wpoa-weights`), kept current (newest wins) and identical on
  every node (confirmed-on-chain data only), exposed through three RPC commands
  and a `StreamWeightRegistry` class.
- **Phase 2 — Weighted miner selection.** When `-enablewpoa=1`, the miner and
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
  the beacon that Phase 3b (RANDAO) will accumulate and Phase 4 will consume for
  private sortition.

Phase 3b (RANDAO accumulator), Phase 4 (private sortition) and Phase 5 (VDF) are
planned — see the [Implementation status](#implementation-status) and the master
[implementation-guide.md](docs/implementation-guide.md).

Operators only ever touch a few things:

- the startup parameters **`-weight=<n>`** (positive integer, default `100`) and
  **`-enablewpoa`** (default off; enables weighted selection), and
- the RPC commands **`getlocalweight`**, **`getnodeweight`**, **`getallweights`**.

Everything else — stream layout, transaction plumbing, wallet indexes, the
election math — is hidden behind the `StreamWeightRegistry` facade and the
`WPoASelector`.

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
    OP([Operator: multichaind -weight=N -enablewpoa]):::ext --> INIT
    INIT["AppInit2<br/>validate weight; set g_node_weight, g_wpoa_enabled<br/>launch registration thread"]

    subgraph P1 [Phase 1 — Weight registry]
        REG["StreamWeightRegistry<br/>deferred register + read core"]
        STREAM[(wpoa-weights stream<br/>append-only, on-chain)]
        REG -->|write via in-process RPC handlers| STREAM
        STREAM -->|non-WRP confirmed reads| REG
    end

    subgraph P2 [Phase 2 — Weighted selection]
        SEL["WPoASelector<br/>score_i = -ln(u_i)/w_i; argmin"]
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

    INIT --> REG
    REG -->|"GetAllNodesWeights()"| SEL
    MINE -.->|"elected proposer signs"| MVRF
    VAL -.->|"on wPoA-VRF heights"| VVRF
    CLI([multichain-cli getlocalweight / getnodeweight / getallweights]):::ext --> REG

    classDef ext fill:#eee,stroke:#999,color:#333;
```

- **Phase 1** records and serves weights on the `wpoa-weights` stream via the
  `StreamWeightRegistry` facade (deferred background registration; confirmed-only
  reads that are safe from any thread). Full detail:
  [phase1-implementation-guide.md](docs/phase1-implementation-guide.md).
- **Phase 2** consumes `GetAllNodesWeights()` and elects each height's proposer
  in proportion to weight, gating the miner and the block validator behind
  `-enablewpoa`. Full detail:
  [phase2-implementation-guide.md](docs/phase2-implementation-guide.md).
- **Phase 3a** adds the VRF beacon behind `-enablewpoavrf`: the elected proposer
  embeds a verifiable reveal `(R, π)` in its block (via `WPoAVRF`, an ECVRF/DLEQ
  over the bundled secp256k1) and every peer verifies it. Selection is unchanged.
  Full detail:
  [phase3a-implementation-guide.md](docs/phase3a-implementation-guide.md).

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
| [node-startup.md](docs/node-startup.md) | How `-weight` (Phase 1), `-enablewpoa`/`-dumpfunction` (Phase 2) and `-enablewpoavrf` (Phase 3a) are wired into `AppInit2` and how the background thread is launched (`core/init.h` + `.cpp`, wPoA parts). |
| [rpc-registration.md](docs/rpc-registration.md) | How the three RPC commands are added to the dispatch table (`rpc/rpclist.cpp`). |
| [testing.md](docs/testing.md) | Build steps, unit tests, the MultiChain mining model, manual single-/multi-node tests, the automated smoke test, and troubleshooting. |

### Source & test files

| File | Role |
|------|------|
| [`stream_weight_registry.h`](stream_weight_registry.h) / [`.cpp`](stream_weight_registry.cpp) | Phase 1: public API + implementation of the registry, background thread and RPC handlers. |
| [`weight_record.h`](weight_record.h) | Phase 1: pure parsing/aggregation helpers (json_spirit-only, unit-testable). |
| [`wpoa_selector.h`](wpoa_selector.h) / [`.cpp`](wpoa_selector.cpp) | Phase 2: pure Efraimidis–Spirakis selector core (header-only) + node-coupled glue (flag, activation predicate, registry-backed election). Phase 3a adds the `g_wpoa_vrf_enabled` flag and `WPoAVRFActiveAtHeight`. |
| [`vrf_wrapper.h`](vrf_wrapper.h) / [`.cpp`](vrf_wrapper.cpp) | Phase 3a: pure `WPoAVRF` ECVRF/DLEQ core over secp256k1 (`Prove`/`Verify`), node-free and unit-testable. |
| [`test/wpoa_weight_tests.cpp`](test/wpoa_weight_tests.cpp) | Phase 1: Boost.Test unit tests for the pure registry logic. |
| [`test/wpoa_selector_tests.cpp`](test/wpoa_selector_tests.cpp) | Phase 2: Boost.Test unit tests for the pure selector math (determinism, order-independence, probability preservation). |
| [`test/vrf_wrapper_tests.cpp`](test/vrf_wrapper_tests.cpp) | Phase 3a: Boost.Test unit tests for the pure VRF core (roundtrip, determinism, tamper/forgery/cross-key rejection, pseudorandomness). |
| [`test/run_unit_tests.sh`](test/run_unit_tests.sh) / [`test/run_selector_unit_tests.sh`](test/run_selector_unit_tests.sh) / [`test/run_vrf_unit_tests.sh`](test/run_vrf_unit_tests.sh) | Build + run the unit tests (no node build needed). |
| [`test/functional_test_wpoa.sh`](test/functional_test_wpoa.sh) | End-to-end smoke test driving a real single node. |
| [`test/functional_test_wpoa_multinode.sh`](test/functional_test_wpoa_multinode.sh) / [`test/analyze_distribution.py`](test/analyze_distribution.py) | End-to-end multi-node test + chi-square proposer-distribution analyzer. |
| [`test/functional_test_wpoa_vrf.sh`](test/functional_test_wpoa_vrf.sh) | Phase 3a: end-to-end multi-node VRF beacon test (reveals produced, verified network-wide, chain live and fork-free under mandatory verification). |

Integration points in the host tree: [`../core/init.cpp`](../core/init.cpp)
(startup flags, incl. `-enablewpoavrf`), [`../rpc/rpclist.cpp`](../rpc/rpclist.cpp) /
[`../rpc/rpchelp.cpp`](../rpc/rpchelp.cpp) (RPCs),
[`../miner/miner.cpp`](../miner/miner.cpp) (Phase 2 mining hook + Phase 3a reveal
embedding), [`../protocol/multichainblock.cpp`](../protocol/multichainblock.cpp)
(Phase 2 validation hook + Phase 3a reveal verification),
[`../protocol/multichainscript.cpp`](../protocol/multichainscript.cpp) (Phase 3a
`SetBlockVRF`/`GetBlockVRF` reveal carriage), [`../Makefile.am`](../Makefile.am)
(build). See [phase1-implementation-guide.md §7](docs/phase1-implementation-guide.md),
[phase2-implementation-guide.md §5](docs/phase2-implementation-guide.md) and
[phase3a-implementation-guide.md §2](docs/phase3a-implementation-guide.md) for
details.

---

## Implementation status

| Phase | Area | Status | Notes |
|:-----:|------|--------|-------|
| **1** | Weight configuration (`-weight`) & validation | Done | Validated in `AppInit2`; startup fails on `-weight <= 0`. |
| **1** | Deferred registration (background thread) | Done | Waits for readiness, retries, bounded budget before giving up. |
| **1** | On-chain append-only registry (`wpoa-weights`) | Done | Create + subscribe + publish via reused RPC handlers; idempotent re-registration. |
| **1** | Opaque read API (`GetLocalWeight`, `GetAllNodesWeights`, `GetNodeWeight`) | Done | Backward-search per address; hides stream mechanics from callers. |
| **1** | RPC surface (`getlocalweight`, `getnodeweight`, `getallweights`) | Done | Confirmed-only, thread-safe. |
| **1** | Read-path correctness fixes | Done | non-WRP read family (WRP snapshot bug) and 6-arg `OpReturnFormatEntry` overload. |
| **1** | Unit tests (pure parsing / aggregation) | Done | Boost.Test suite, node-free. |
| **1** | Single-node functional smoke test | Done | [`test/functional_test_wpoa.sh`](test/functional_test_wpoa.sh). |
| **1** | Multi-node functional smoke test | Done | [`test/functional_test_wpoa_multinode.sh`](test/functional_test_wpoa_multinode.sh) — bootstraps `connect`/`send`/`receive`/`mine`/`wpoa-weights.write` from node 0; asserts per-node weight. |
| **2** | Weighted miner selection (`WPoASelector` + `miner.cpp` hook) | Done | Efraimidis–Spirakis argmin seeded by prev-block hash; consumes `GetAllNodesWeights()`. See [docs/phase2-implementation-guide.md](docs/phase2-implementation-guide.md). |
| **2** | `-enablewpoa` runtime toggle | Done | Default off (native round-robin unchanged); gates miner + validation hooks. |
| **2** | Proposer validation (`VerifyBlockMiner` hook) | Done | Recomputes the election on receipt; rejects blocks not from the elected proposer. |
| **2** | Deterministic tie-break | Done | Lexicographically smallest address on exact score collision. |
| **2** | Unit tests (pure selector math) | Done | [`test/wpoa_selector_tests.cpp`](test/wpoa_selector_tests.cpp); probability preservation over 200k seeds. |
| **2** | Multi-node distribution test (chi-square) | Done | [`test/functional_test_wpoa_multinode.sh`](test/functional_test_wpoa_multinode.sh) + [`test/analyze_distribution.py`](test/analyze_distribution.py); ~1000 blocks, observed vs. expected. |
| **3a** | VRF wrapper (`WPoAVRF`, ECVRF/DLEQ over secp256k1) | Done | Pure `Prove`/`Verify`; no new build dependency. [docs/phase3a-implementation-guide.md](docs/phase3a-implementation-guide.md). |
| **3a** | `-enablewpoavrf` runtime toggle | Done | Default off; requires `-enablewpoa`. Gates reveal production + verification via `WPoAVRFActiveAtHeight`. |
| **3a** | Per-block reveal embed + verify | Done | Proposer embeds `(R, π)` as a suffix of the block-signature element; `VerifyBlockMinerWPoA` rejects a missing/invalid reveal on wPoA-VRF heights. |
| **3a** | Unit tests (pure VRF crypto) | Done | [`test/vrf_wrapper_tests.cpp`](test/vrf_wrapper_tests.cpp); roundtrip, determinism, tamper/forgery/cross-key rejection. |
| **3a** | Multi-node functional test | Done | [`test/functional_test_wpoa_vrf.sh`](test/functional_test_wpoa_vrf.sh); reveals verified network-wide, chain live and fork-free. |

**Phases 1, 2 and 3a are complete and validated end-to-end.** The multi-node
functional test bootstraps a permissioned network with distinct per-node
weights, confirms the weight map converges on every node, then mines a long run
of wPoA-governed blocks and verifies the observed proposer distribution matches
the configured weight ratios via a chi-square goodness-of-fit test (with the
observed-vs-expected table printed as evidence). The Phase 3a VRF beacon is
validated by its own multi-node test: with `-enablewpoavrf=1` every wPoA block
carries a reveal that every peer must verify to accept, so the chain advancing
past the setup height with all nodes agreeing (no fork) and zero VRF rejections
is direct end-to-end evidence that reveals are produced and verified network-wide.
Phase 3b, Phase 4 and Phase 5 are planned.

See [docs/phase3a-implementation-guide.md](docs/phase3a-implementation-guide.md)
for the Phase 3a design,
[docs/phase2-implementation-guide.md](docs/phase2-implementation-guide.md)
for the Phase 2 design, and
[phase1-implementation-guide.md §12](docs/phase1-implementation-guide.md#12-limitations--phase-2-hooks)
for the full limitations register.

---

## Quick start

```bash
# Build (Makefile.am changed, so regenerate first):
cd /home/mattu/multichain
./autogen.sh && ./configure && make

# Run a node with a weight:
./src/multichaind <chain> -weight=100

# Enable weighted selection (Phase 2) and the VRF beacon (Phase 3a).
# Both flags must be identical on every validator.
./src/multichaind <chain> -weight=100 -enablewpoa=1 -enablewpoavrf=1

# Query weights:
./src/multichain-cli <chain> getallweights
```

Full build and test instructions are in [testing.md](docs/testing.md).
The Phase 3a VRF unit tests run node-free via
[`test/run_vrf_unit_tests.sh`](test/run_vrf_unit_tests.sh); the multi-node beacon
test is [`test/functional_test_wpoa_vrf.sh`](test/functional_test_wpoa_vrf.sh).
