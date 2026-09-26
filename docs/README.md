# wPoA + Weight Engine documentation

> **Type:** index · **Verified against the code:** 2026-09-26, commit `3d2fc551`
>
> The map of `docs/`: what each document is for, which ones describe the code as it is and
> which ones record how it got there, and the conventions they all follow. The feature entry
> point for the code itself is [`src/wpoa/README.md`](../src/wpoa/README.md); the test
> harness has its own documentation under [`test/`](../test/README.md).

---

## Where to start

| If you want… | Read |
|---|---|
| the whole system in one document: how it is built, where it touches MultiChain, why | [wpoa-weight-engine-architecture.md](wpoa-weight-engine-architecture.md) |
| the phases and how they stack, with a link per component | [implementation-guide.md](implementation-guide.md) |
| what is done and what is not | [implementation-status.md](implementation-status.md) |
| a parameter: name, default, range, whether it is consensus | [protocol-parameters.md](protocol-parameters.md) |
| the formal model and the security argument | [thesis-project-overview.md](thesis-project-overview.md) |
| to build, test, or run a network | [testing.md](testing.md) |

---

## Reference — describes the code as it is

These documents are kept in step with the code. Each carries a *Verified against the code*
stamp in its header; if the code moves, the document is corrected, not annotated.

**System and configuration**

| Document | Covers |
|---|---|
| [wpoa-weight-engine-architecture.md](wpoa-weight-engine-architecture.md) | Technical synthesis: integration points, design disciplines, bootstrap, concurrency, known limits. |
| [implementation-guide.md](implementation-guide.md) | Phase map and component index. |
| [implementation-status.md](implementation-status.md) | The only status table. Also the weight-assignment flow diagram. |
| [protocol-parameters.md](protocol-parameters.md) | The only parameter catalogue: every chain parameter and runtime flag. |
| [node-startup.md](node-startup.md) | How `AppInit2` resolves the switches and starts the wPoA threads. |
| [thesis-project-overview.md](thesis-project-overview.md) | Research companion: problem, threat model, formal model, proofs (formal-academic register). |
| [native-poa-block-delay.md](native-poa-block-delay.md) | The native MultiChain mining-delay model that Phase 4 replaces on governed heights. |
| [multichain-internals.md](multichain-internals.md) | The MultiChain host APIs the modules build on. |

**wPoA core (`src/wpoa/`)**

| Document | Covers |
|---|---|
| [stream-weight-registry.md](stream-weight-registry.md) | Phase 1: `StreamWeightRegistry`, the `wpoa-weights` stream and its read paths. |
| [weight-record.md](weight-record.md) | Phase 1: the pure record parser and newest-wins fold (`weight_record.h`). |
| [wpoa-selector.md](wpoa-selector.md) | Phase 2: the Efraimidis–Spirakis selector, the activation predicate and the diversity hook. |
| [vrf-wrapper.md](vrf-wrapper.md) | Phase 3a: the ECVRF/DLEQ core over secp256k1. |
| [randao-accumulator.md](randao-accumulator.md) | Phase 3b: the RANDAO fold, the seed and the memoised walk. |
| [private-sortition.md](private-sortition.md) | Phase 4: score, band delay, feedback, and the shared round context. |
| [score-aware-activation.md](score-aware-activation.md) | Phase 4: a node holds back a worse-scored block for its own round, so the argmin still proposes and the fork choice picks it. |
| [malus-registry.md](malus-registry.md) | The behavioural malus: evidence kinds, EMA accumulator, `Ψ`, `w_eff`. |

**Host integration (`src/miner/`, `src/protocol/`, `src/rpc/`)**

| Document | Covers |
|---|---|
| [miner-integration.md](miner-integration.md) · [block-validation.md](block-validation.md) | Phase 2 hooks: miner election, validator check. |
| [vrf-prover.md](vrf-prover.md) · [vrf-verifier.md](vrf-verifier.md) · [block-vrf-encoding.md](block-vrf-encoding.md) | Phase 3a hooks: producing, verifying and carrying the reveal. |
| [randao-miner.md](randao-miner.md) · [randao-validator.md](randao-validator.md) | Phase 3b hooks: the seed swap on both sides. |
| [sortition-miner.md](sortition-miner.md) · [sortition-validator.md](sortition-validator.md) | Phase 4 hooks: score-timed self-election and the time bar. |
| [rpc-registration.md](rpc-registration.md) | How the wPoA and weight RPCs enter the dispatch table. |
| [rpc-result-shapes.md](rpc-result-shapes.md) | What each audit RPC actually returns. |

**Weight Engine (`src/weight_engine/`)**

| Document | Covers |
|---|---|
| [weight-engine.md](weight-engine.md) | Inputs, pipeline, thread, verification, security model. |

**Testing**

| Document | Covers |
|---|---|
| [testing.md](testing.md) | Building, the unit suites, the network harness, manual checks, debugging. |

---

## Historical records — describe the work as it was done

These are **not** updated when the code changes. Each opens with a banner giving its date and
status, what has changed since where it matters, and a link to the current reference. Paths,
identifiers and line numbers inside them are as they were at the time.

| Document | Kind | Date |
|---|---|---|
| [phase1-implementation-guide.md](phase1-implementation-guide.md) | phase guide | 2026-07-05 |
| [phase2-implementation-guide.md](phase2-implementation-guide.md) | phase guide | 2026-07-10 |
| [phase3a-implementation-guide.md](phase3a-implementation-guide.md) | phase guide | 2026-07-13 |
| [phase3b-implementation-guide.md](phase3b-implementation-guide.md) | phase guide | 2026-07-14 |
| [phase4-implementation-guide.md](phase4-implementation-guide.md) | phase guide | 2026-07-16 |
| [implementation-roadmap.md](implementation-roadmap.md) | roadmap | 2026-07-09 |
| [CHANGELOG-weight-engine-refactor.md](CHANGELOG-weight-engine-refactor.md) | changelog | 2026-08-24 |
| [adr/reconciliation-onchain.md](adr/reconciliation-onchain.md) | ADR | 2026-08-24 |
| [root-cause-report.md](root-cause-report.md) | report | 2026-09-06 |
| [adr/randao-fold-bare-xor.md](adr/randao-fold-bare-xor.md) | ADR | 2026-09-13 |
| [adr/test-restructure-2026.md](adr/test-restructure-2026.md) | ADR | 2026-09-15 |
| [adr/functional-smoke-refactor-2026.md](adr/functional-smoke-refactor-2026.md) | ADR | 2026-09-16 |
| [adr/core-emulation-2026.md](adr/core-emulation-2026.md) | ADR | 2026-09-18 |
| [evidence/json-double-rendering-2026-09-18.md](evidence/json-double-rendering-2026-09-18.md) | evidence | 2026-09-18 |
| [evidence/local-gossip-hint-inert-2026-09-21.md](evidence/local-gossip-hint-inert-2026-09-21.md) | evidence | 2026-09-21 |

The phase guides remain the best account of *why* each phase is designed as it is; for
*what* the code does today, follow their banner to the reference documents.

---

## Conventions

**Language.** Every document is in English, like the code. Thesis quantities keep the
thesis' own names where the code does (`saldo`, `Entrate`, `Uscite`).

**Header.** Every document opens, under its title, with one blockquote:

```markdown
> **Type:** reference · **Register:** technical-direct · **Verified against the code:** <date>, commit `<hash>`
>
> What the document covers, in one or two sentences, and where to go instead.
```

Historical records use `**Type:** historical record (<kind>) · **Date:** … · **Status:** …`,
followed by the "kept as written" note, a *Changed since* paragraph where it matters, and a
*For the system as it is now* pointer.

**Register.** Reference documents are *technical-direct*: short sentences, identifiers
verbatim. [thesis-project-overview.md](thesis-project-overview.md) is *formal-academic*.
A document that mixes the two says so in its header.

**Single sources.** Parameters live only in [protocol-parameters.md](protocol-parameters.md),
status only in [implementation-status.md](implementation-status.md), the weight-assignment
diagram only in [implementation-status.md §0.1](implementation-status.md#01-how-a-nodes-weight-is-assigned--the-authoritative-flow).
Other documents link there instead of restating.

**Citing code.** By symbol and file link — `WPoASortitionVerifyProposer` in
[`private_sortition.cpp`](../src/wpoa/private_sortition.cpp). A `file:line` is a
convenience that rots: it may appear only in a document whose header carries a
*Verified against the code* stamp, and it is re-checked whenever the stamp is renewed. If a
line number and a symbol disagree, trust the symbol.

**Anchors.** Section links use GitHub slugs, which drop punctuation such as `—`, `.`, `(`:
the heading `## 3. VerifyBlockMinerWPoA — line by line` is `#3-verifyblockminerwpoa--line-by-line`.

**Terminology.** "Damping" in prose, `dumping` in identifiers (`-dumpfunction`,
`DumpingFunction`), because the code spells it that way. Epochs are 1-based. The two `λ`
(`-weightlambda`, `-wpoasortitionlambda`) are always qualified.

---

## Keeping the documentation current

When a change alters behaviour:

1. Update the reference documents that describe it, in the same change, and renew their
   *Verified against the code* stamp.
2. Parameters: [protocol-parameters.md](protocol-parameters.md) only. Status:
   [implementation-status.md](implementation-status.md) only.
3. A new component gets a reference document and a row in the tables above and in
   [implementation-guide.md](implementation-guide.md).
4. A decision worth recording gets an ADR under `adr/`; a measurement that settles a question
   gets an evidence note under `evidence/`. Both are historical from the day they are written.
5. Diagrams are part of the behaviour they depict: a change that makes one stale updates it.
6. Run `graphify update .` afterwards, so the knowledge graph follows.
