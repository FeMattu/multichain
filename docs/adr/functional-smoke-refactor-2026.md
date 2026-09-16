# ADR — refactoring the functional/smoke suite around the thesis' economic model

> **Status:** analysis complete; three divergences raised for decision (§7). Implementation
> not started — the mandate's §2 gate ("no code before this report") is what this document
> discharges.
> **Scope:** `test/functional/` in its entirety. Explicitly **out of scope, and untouched:**
> `/experiments` (the CORE/netns emulation framework) and
> `src/weight_engine/test/experimental/` (the MyLedger economic simulation harness —
> confirmed protected, §1.3).
> **Register: technical-direct.** Decision record: what the code actually does, where the
> thesis and the code diverge, what the existing suite does when you run it, and what
> follows for the refactor.
> Sibling ADRs: [../../src/wpoa/docs/adr/reconciliation-onchain.md](../../src/wpoa/docs/adr/reconciliation-onchain.md),
> [../../src/wpoa/docs/adr/randao-fold-bare-xor.md](../../src/wpoa/docs/adr/randao-fold-bare-xor.md),
> [test-restructure-2026.md](test-restructure-2026.md).

---

## 0. The environment this was established in, and why it matters

Every previous revision of this suite was written on a host where `multichaind` **did not
run**: [test-restructure-2026.md §10.2](test-restructure-2026.md) records
`libboost_filesystem.so.1.74.0: cannot open shared object file`, and every functional
verdict in that document is `NOT RUN`. That is the single most important fact about the
code this refactor inherits: **it has never been executed against a live network**, so its
commit history is not evidence that it works.

This analysis was done differently. `./docker/mcsim` supplies an Ubuntu 22.04 userspace
with GCC 11 and Boost 1.74, and everything below that says "observed" was observed there.

**The tree's binaries were stale and had to be rebuilt.** `src/multichaind` was dated
2026-09-10 and owned by `root`, while the production code changed twice after that date:

| commit | date | what it changed |
|---|---|---|
| `530357bb` | 2026-09-13 | `feat(weight-engine): restitution rate replaces allocation/compliance` |
| `c1879600` | 2026-09-13 | `feat(randao)!: fold the bare XOR of Def. 5.3` |

A binary predating `530357bb` cannot test the restitution feedback, which is the entire
subject of this suite. The first `mc-build` also failed outright — the build tree carried
a `config.status` configured at `/multichain` while the container mounts the repository at
`/workspace/multichain`:

```
cd . && /bin/bash /multichain/build-aux/missing automake-1.16 --foreign Makefile
/bin/bash: /multichain/build-aux/missing: No such file or directory
make: *** [Makefile:504: Makefile.in] Error 127
```

`./docker/mcsim run mc-build --clean` reconfigures and succeeds. **Anyone re-running this
suite must do that first**; without it the run silently tests two-revision-old code.

---

## 1. What the code actually provides (verified, not assumed)

### 1.1 The RPCs exist under these names and no others

Checked against [`src/rpc/rpclist.cpp`](../../src/rpc/rpclist.cpp), the registration table
itself, rather than inferred from call sites:

| RPC | line | category |
|---|---|---|
| `getlocalweight` | 140 | wpoa |
| `getallweights` | 141 | wpoa |
| `getnodeweight` | 142 | wpoa |
| `getallmalus` | 144 | wpoa |
| `getnodemalus` | 145 | wpoa |
| `reportmalus` | 146 | wpoa |
| `weightsetesg` | 152 | weight |
| `weightregistermembership` | 153 | weight |
| `weightverifyweights` | 156 | weight |

`getvalidatorinfo` and `getweight` do **not** exist — confirming the finding already
recorded in [experiments/docs/metrics.md](../../experiments/docs/metrics.md). Neither does
`weightsetreconciliation`, whose removal
[reconciliation-onchain.md](../../src/wpoa/docs/adr/reconciliation-onchain.md) decided and
which `functional_test_weight_engine.sh:174` deliberately asserts is gone.

### 1.2 The streams are four, not three

| constant | value | file |
|---|---|---|
| `MC_WEIGHT_MEMBERSHIP_STREAM_NAME` | `weight-engine-membership` | `weight_streams.h:57` |
| `MC_WEIGHT_ESG_STREAM_NAME` | `weight-engine-esg` | `weight_streams.h:61` |
| `MC_WPOA_WEIGHTS_STREAM_NAME` | `wpoa-weights` | `stream_weight_registry.h:26` |
| `MC_WPOA_MALUS_STREAM_NAME` | `wpoa-weights-malus` | `malus_registry.h:83` |

The mandate names three; the malus registry has a fourth. The "two input streams" of
`reconciliation-onchain.md` §4 is a narrower and correct claim — two *inputs* (membership,
ESG), plus two *outputs* (weights, malus). `weight-engine-reconciliation` and
`weight-engine-activity` are absent, as that ADR decided.

### 1.3 `src/weight_engine/test/experimental/` — confirmed protected, not touched

The citation the mandate asked me to find is real and exact.
[reconciliation-onchain.md §1](../../src/wpoa/docs/adr/reconciliation-onchain.md) cites
`helpers/stream_writer.py` for the note that `R_k` had been a random draw *"with no
on-chain counterpart — the stream asserted a reconciliation that never happened"*. That
citation is load-bearing evidence for an **accepted** ADR.
[test-restructure-2026.md §11.5](test-restructure-2026.md) independently reached the same
conclusion and records `output/*.csv` + `report.xlsx` as tracked reference data behind its
"20/20 cells exact" claim.

**Decision: not moved, not renamed, not deprecated, and its logic is not duplicated.** The
refactor below takes it as a *behavioural reference* only — specifically the
`-weighttreasuryaddress` start → read → restart sequence of `helpers/chain_setup.py`,
which the bash harness already models. No tracked artefact of it is touched.

### 1.4 `R_k` is keyed by the **miner address alone** — the decisive finding

This is the fact the whole economic specification turns on, and it is not obvious from the
documentation.

`ComputeEpochFacts` ([`weight_reader.cpp:482`](../../src/weight_engine/weight_reader.cpp))
accumulates `tau`, `credits`, `debits` and `r` into maps **keyed by address**, crediting
`r` to the *signers* of any transaction that pays the treasury
(`mc_AccumulateReconciliation`, [`weight_records.h:371`](../../src/weight_engine/weight_records.h)).

But `weight_engine.cpp:183` reads only one key out of that map:

```cpp
in.restituted = LookupDouble(r_e, ci->first);   // ci->first IS the miner address
in.credits    = LookupDouble(credits_e, ci->first);
in.debits     = LookupDouble(debits_e, ci->first);
```

with the comment stating the rule outright: *"Flows are the MINER address' own: the
cluster's wallet in the thesis' accounting is the miner node, and company members pay
their own fees from their own addresses."*

**Consequence: a payment from a company to the treasury contributes to no cluster's `R_k`
at all.** It credits `r_e[company_address]`, a key nothing ever reads. Only
`r_e[miner_address]` reaches the pipeline.

This exactly matches thesis **Def. 6.6**, which was read in full and says so explicitly:

> *"la somma dei trasferimenti in native-currency, confermati nei blocchi dell'epoca e,
> **dal miner m_k** all'indirizzo di treasury della rete"*

So the mandate's §3 specification — **miners** restitute to the treasury, companies only
pay fees on informative transactions — is the one both the code and the thesis require.
§3.2 below shows the existing suite does the opposite.

---

## 2. The thesis, read against the code

Read from `Tesi.pdf`: §4.2.1 (actors, roles, GAS), §4.3.1 (economic flow, Fig. 4.1),
§4.3.2 (clusters), and Chapter 6 Def. 6.6–6.10.

**Where they agree.** Def. 6.6 (restitution, chain-derived, miner → treasury), Def. 6.7
(gain = credits − debits), Def. 6.8 (recursive `saldo`), Def. 6.9 (`φ_k = R_k / saldo_k`)
and Def. 6.10 (`w_k = W_k · [φ_k^(e-1)·λ_w + (1−λ_w)]`) are all implemented as written.
The thesis text has already been updated for the `reconciliation-onchain` ADR — §6.6 states
the chain-derived wording that ADR §7 proposed, so that divergence is closed.

**Where they diverge, and none of it is covered by an existing ADR** — raised in §7.

---

## 3. The existing suite: read in full, then run

### 3.1 What it is

| file | lines | verdict |
|---|---|---|
| `lib/functional_lib.sh` | 1180 | well factored; keep, repair |
| `lib/we_stats.py` | 889 | strong; keep, extend (§5) |
| `lib/lint_lib.sh` | 379 | keep as-is; genuinely useful |
| `run_functional_tests.sh` | 218 | keep; add the new suite |
| `wpoa/functional_test_wpoa_system.sh` | 862 | keep |
| `weight_engine/functional_test_weight_engine.sh` | 324 | keep |
| `weight_engine/..._bootstrap.sh` | 386 | keep |
| `weight_engine/..._large_network.sh` | 853 | **economics rewritten** (§3.2) |

### 3.2 The economic logic of `large_network` is wrong, in three independent ways

Not style — each one independently makes the run measure nothing.

**(a) The wrong actor restitutes.** `generate_activity` (line ~560) has *companies* pay the
treasury:

```bash
fl_cli "$idx" sendtoaddress "$TREASURY" 5      # idx ∈ COMPANY_IDX
```

By §1.4 this credits `r_e[company]`, which no cluster reads. **`R_k = 0` for every miner,
in every epoch** — so `φ_k = 0`, `w_k = W_k·(1−λ)`, a uniform scaling, and the restitution
feedback is inert for the whole run. This is precisely the failure mode
[test-restructure-2026.md §6.2](test-restructure-2026.md) set out to avoid; it was designed
around and then reintroduced one layer down.

**(b) The premine is a thousandth of what the run needs.** `first-block-reward` is in *raw*
units and `native-currency-multiple = 100000000`
([`paramlist.h:263,295`](../../src/chainparams/paramlist.h)), so the suite's

```
WE_LARGE_PREMINE=100000000     # → 1.00 GAS, not 100 million
WE_LARGE_BLOCK_REWARD=10       # → 0.0000001 GAS per block
```

give the admin **1 GAS** against a seeding requirement of `32 × 1000 = 32 000 GAS`. The
`gas_seeded` check would fail on the first epoch — which is a correct check catching a real
misconfiguration, and the reason it has never been seen is that the suite had never run.

**(c) Transaction volume is fixed at 1/epoch/company**, where the mandate specifies a
*random* 20–60, drawn independently per company per epoch. One transaction per company per
epoch produces a `tau` with no variance, so nothing in the weight pipeline moves.

### 3.3 Running it — what actually happens

`MC_CORE=0 ./docker/mcsim run ./test/functional/run_functional_tests.sh`, against the
freshly rebuilt binaries.

**The network comes up and the protocol works.** This is the first live confirmation in the
project's history:

```
chain=wpoasys258 nodes=3 weights=(100 200 300) total=600
aggregate weight 600 confirmed across all 3 node(s).
sample window: heights 30..109 (80 blocks); driving to 115
```

and the proposer distribution check passed on real data:

```
validator                                 weight   expected   observed    obs/exp
1YeDXi29o4ES64M4r9SJHr9a2MbZTqsqsZ3HQ6       300     50.00%     58.75%      1.175
1SJTKqkpgkb1emvgpgLuoNwo5dkYZynJ2QLsq3       200     33.33%     30.00%      0.900
117qVZmx8PBG1RfFuvGkjh5T8TCQFrYEdiB7QF       100     16.67%     11.25%      0.675
chi-square = 2.900   (df = 2)      α=0.001 -> 14.13
RESULT: PASS — proposer distribution matches weight ratios (chi-square).
```

**The `wpoa` suite: 10 of 11 checks PASS, one FAIL.**

| check | verdict |
|---|---|
| `weight`, `stream_permissions`, `malus`, `multinode_consistency` | PASS |
| `diversity_spacing`, `vrf`, `randao`, `sortition` | PASS |
| `distribution`, `diversity_spacing_4n` | PASS |
| **`randao_seed_convention`** | **FAIL** |

The `weight-engine` single-node suite passed **every** assertion (22 of 22), including the
epoch-scoped verdict work of [test-restructure-2026.md §3.3](test-restructure-2026.md):
*"verification has run for a real epoch (epoch=2, not the 0 that means 'not yet')"*,
*"the verified epoch trails the newest buried one (2 < 3)"*, and
*"the invalid counter equals mismatch + not-a-cluster (other-epoch excluded)"*. The
`weight-engine-bootstrap` suite reached `RESULT: PASS (all critical checks passed)`.

So the harness's protocol-level machinery is in far better shape than its never-run history
suggested. The one failure is analysed in §3.4 — and it is a defect in the test, twice over.

### 3.4 `randao_seed_convention` — two real harness defects

```
✗ seed for height=116: logged h[115]=0000bdc8…b837d9 but getblockhash(115)=00541949…3ab414
✗ seed for height=117: logged h[116]=00b8ba3a…1ef010 but getblockhash(116)=0006969e…a3df63
✗ derivations whose logged h[n] did not match the block's real hash (got 6, expected 0)
  → randao_seed_convention: FAIL
```

**(a) A whole block of checks is defined twice, and the weaker copies win.**

Not one function — **five**, in a 208-line block that `53b177d7` appended without removing
what it superseded:

| function | kept (newer) | shadowing duplicate (older) |
|---|---|---|
| `check_multinode_consistency` | 260 | 508 |
| `check_diversity_spacing` | 304 | 552 |
| `check_vrf` | 351 | 599 |
| `check_randao` | 365 | 613 |
| `check_randao_seed_convention` | 427 | 650 |

In bash a later definition silently replaces an earlier one, so **every one of these ran in
its older form**. The parent commit `53b177d7^` has each function exactly once and no
`check_randao_seed_convention` at all, which dates the defect precisely: it arrived with the
commit that was supposed to add the check.

What is lost is precisely the check commit `53b177d7` was written to add — the tip+1
discriminator that distinguishes the current convention from the `ef08074c` regression:

```bash
if [ "$maxh" -eq $(( tip + 1 )) ]; then matched=1; break; fi
...
fl_bad "highest seeded height is $maxh with tip $tip: the seed is being derived
        FOR THE TIP, i.e. h[n-1]/n -- the ef08074c regression"
```

The run output confirms it never executed: no `highest seeded height is tip+1` line appears
anywhere in the log. **`53b177d7`'s stated purpose — "pin it" — was never achieved**: the
coverage hole [test-restructure-2026.md §3.1](test-restructure-2026.md) identified was
closed in the diff and left open at runtime.

`bash -n` cannot see this: a duplicate definition is valid syntax. It is the same class as
the `local` self-reference of [test-restructure-2026.md §13.2](test-restructure-2026.md) —
correct syntax, wrong semantics — and it went unnoticed for the same reason that one did:
**nobody could run the suite.** `lint_lib.sh` gains a duplicate-definition scan (§8), which
is a two-line check that would have caught this on the day it landed.

**(b) The surviving copy hash-checks near-tip derivations, which are legitimately transient.**

```bash
lines="$(grep -oE '…' "$log" | tail -n 12)"      # the 12 MOST RECENT derivations
…
if [ "$h_idx" -le "$(fl_tip_height 0)" ]; then   # "in range", NOT "buried"
```

A node derives the seed for height `n+1` from **its own current tip** `h[n]`. When two
qualified proposers produce competing blocks at height `n` — the "transient
simultaneous-qualifier fork" the suite's own header warns about — a node logs a derivation
against the candidate it held at that moment, and a later reorg replaces it. The check then
compares that logged hash against the *final* canonical hash and calls it a mismatch.

The failures are consistent with that and with nothing else:

* every failure is at height **115 or 116**, with the tip at **117** — inside the reorg
  window, and none is buried;
* `bad_h = 0` and `bad_r = 0`: the *indices* are right on all 12 samples. A genuine
  convention regression would move the index and fire those counters first;
* `multinode_consistency` PASSED in the same run — all three nodes agree on the chain;
* `tail -n 12` deliberately samples the most recent derivations, i.e. the most reorg-prone.

**Directly confirmed on a second run**, kept with `KEEP_LOGS=1`. The three nodes' own
`[wPoA-RANDAO] seed for height=…` lines were extracted and compared as `(height, h[n])`
pairs. At **15 separate heights the nodes derived their seed from a different `h[n]`**:

```
node 0: 97 distinct (height,hash) seed operands
node 1: 96 distinct (height,hash) seed operands
node 2: 91 distinct (height,hash) seed operands

heights where the three nodes did NOT all agree on h[n]:
  30, 40, 42, 50, 51, 52, 56, 57, 59, 65, 67, 68, 84, 88, 95   (2 distinct hashes each)
```

Two nodes holding different `h[n]` for the same `n` were holding different tips at that
instant — and exactly one of those candidates ends up on the canonical chain. So a logged
`h[n]` is a **momentary** observation, and the check was comparing it against a hash
settled later. `check_multinode_consistency` PASSED in the same run, confirming the
divergence is transient rather than a real split.

**This is a test defect, not a production one**, so the mandate's stop-and-ask clause is
not triggered: the node did precisely what Def. 5.4 requires — it anchored to its tip — and
the harness mistook a race for a violation.

The fix is to hash-check only derivations whose `h_idx` is **buried**
(`h_idx <= tip - FL_STABILITY_MARGIN`), and to sample from buried derivations rather than
the newest — the same stability-margin rule the weight engine itself applies, and for the
same reason.

### 3.5 The `local`-self-reference class: swept, and it is clean

### 3.4 The `local`-self-reference class: swept, and it is clean

[test-restructure-2026.md §13.2](test-restructure-2026.md) found
`local from=$1 to=$2 h=$from`, where `local` word-expands every argument before any
assignment takes effect. A repository-wide sweep for the same class over
`test/functional/` finds **no remaining instance**: `fl_record_proposers` now declares and
assigns separately, and `lint_lib.sh` carries a static scan plus a negative control for it.
The three apparent hits in `functional_test_wpoa_system.sh` are the safe three-statement
idiom. **No new instance of this class was introduced by the analysis, and none remains.**

---

## 4. Metric portability from `experiments/` — table by table

The criterion is the one
[experiments/docs/metrics.md §"What one node can see, and what needs several"](../../experiments/docs/metrics.md)
already states: *"deriving a multi-node quantity from a single node is inventing it, and
the result looks exactly like a measurement."* Reused verbatim. A second axis is added
here, since this harness has **no network emulation at all**: a metric whose value *is* the
emulated network is not merely hard to get on localhost, it is meaningless there.

Status values follow `experiments/metrics/catalogue.py`: `observed`, `derived`,
`unavailable` — with `unavailable` required to carry its reason.

### 4.1 Portable — from the admin alone (explorer pattern)

| quantity | status | source |
|---|---|---|
| height, hash, previous hash, block time | observed | `getblockcount`, `getblockhash`, `getblock` |
| proposer per height | observed | `listblocks` (carries `miner`) |
| weight at the moment of proposal | derived | `listblocks` + `getallweights`, per epoch |
| block size, transaction count | observed | `getblock` |
| published weight map | observed | `getallweights` |
| verification verdicts | observed | `weightverifyweights` |
| malus `psi` / `effective` per node | observed | `getnodemalus` |
| stream contents (weights, ESG, membership, malus) | observed | `liststreamitems` |
| native balance per node | observed | `getbalance` per node |
| confirmed transactions per node per epoch | derived | block walk + undo attribution |
| refuel events | observed | recorded at issue: node, before, after, amount, txid |
| restitution events and amounts | observed | recorded at issue + `getrawtransaction` |
| `R_k`-equivalent per miner | derived | `fl_tx_value_to_address` against the treasury |

### 4.2 Portable — but only by aggregating every node

Kept, and collected from **all** nodes, never derived from the admin:

| quantity | why |
|---|---|
| fork detection | a fork is two nodes disagreeing at one height |
| verification disagreement | each node recomputes independently |
| weight-map agreement | a disagreement is a determinism failure |
| sync lag | "behind" is relative to the others |

### 4.3 `unavailable` — intrinsically emulated-network metrics

Declared absent with the reason, as `catalogue.py` requires — **not** silently dropped:

| quantity | reason it is unavailable here |
|---|---|
| configured link delay | no netem; there are no links to configure |
| measured link delay / RTT | loopback only; the number would be the host's scheduler |
| jitter | same |
| netem conditions (loss, duplication, reorder) | no qdisc is installed |
| block propagation time | all nodes share one kernel and one loopback; the figure measures process scheduling, not propagation |
| geographic topology / location membership | no locations exist |
| partition detection | no partition can be created without a fabric |
| per-link bandwidth | no shaped links |

Note the distinction on **block propagation**: it is `unavailable` here not because it needs
several nodes — §4.2 shows multi-node quantities are perfectly collectable — but because its
*value* would be a measurement of the host, reported in the units of a network property.
That is exactly the "looks exactly like a measurement" failure, so it is declared rather
than approximated.

---

## 5. `we_stats.py` — confirmed strong, needs one layer

Read in full (889 lines). The mandate's suspicion is correct on both counts.

**It already produces reusable tabular output**, so a plotting layer needs no new
extraction: `montecarlo.csv`, `distribution.csv`, `concentration.csv`, `epoch_stats.csv`,
`gas_stats.csv`, plus `report.md` / `summary.txt`. It streams incrementally, so a run that
stalls at epoch 12 leaves twelve usable epochs — the pattern the mandate asks to preserve.

**It generates no graphics.** No `matplotlib` import exists anywhere under
`test/functional/`.

It is standard-library only by deliberate design (chi-square p-values come from a
regularised incomplete gamma implemented in the module) so that it runs on a bare node
host. **That property must not be lost**: the plotting layer has to *degrade*, not fail,
when matplotlib is absent. The container does ship matplotlib.

`--selfcheck` validates the statistics against textbook critical values and includes a
negative control. It is registered as the `stats-selfcheck` suite and needs no node.

**Conclusion: extend, do not rewrite.** Restructuring into `lib/stats/` as the mandate
sketches is worthwhile for the new `extractors.py` / `catalogue.py` / `plots.py`, with the
existing analysis moving to `analysis.py` essentially intact.

---

## 6. Verdict on the existing structure: targeted refactor, not a rewrite

As §4 of the mandate invites me to say explicitly.

**The harness is sound; its economics are not.** `functional_lib.sh` is well factored, its
bootstrap protocol demonstrably brings a real network up, its epoch geometry is correct and
unit-tested by `lint_lib.sh`, and `we_stats.py` is a genuinely good statistical module. The
structure is close to the target layout already.

What is wrong is confined to **the economic simulation inside `large_network`** (§3.2) and
to **two missing layers** (plots, and per-tick/per-epoch extraction at the granularity the
mandate specifies).

So: repair and extend. Rewriting `functional_lib.sh` would discard the only code here with
a live-run track record, and would repeat work `lint_lib.sh` already guards.

---

## 7. Divergences raised for decision — RESOLVED 2026-09-16

Three findings where the thesis and the code disagree and **no ADR covers the gap**. Raised
under the mandate's stop-and-ask clause rather than decided unilaterally; the answers are
recorded inline below.

### 7.1 The block subsidy contradicts "emissione preminata"

**Thesis §4.2.1:** GAS is *"una moneta a emissione preminata: l'intera quantità in
circolazione è generata una tantum alla creazione della rete, **senza alcun meccanismo di
conio incrementale legato alla produzione dei blocchi**."* **Def. 6.7** makes mining income
*"le fee delle transazioni che vi sono incluse"* — the fees, not a subsidy.

**The existing suite** sets `initial-block-reward = 10`, i.e. a per-block subsidy — exactly
the incremental minting the thesis excludes. [test-restructure-2026.md §6.2/§7.1](test-restructure-2026.md)
authorised *"enable the native currency"*, and was right that something had to change, but
it did not distinguish premine-only from per-block minting, and it asserted that
`initial-block-reward` had to be positive.

**That assertion is false, and I verified it on a live chain.** A premine-only
configuration gives a fully spendable native currency:

```
first-block-reward   = 100000000000000   (1e14 raw = 1 000 000 GAS)
initial-block-reward = 0
minimum-relay-fee    = 20000000          (0.2 GAS per 1000 bytes)
→ blocks=6  balance=1000000
→ transfer of 100 GAS: vout = [100, 999899.9052]  ⇒ fee 0.0948 GAS charged and collected
```

So the thesis-faithful configuration works, and the current one is both a divergence and
unnecessary. **Recommendation: premine only** (`first-block-reward` > 0,
`initial-block-reward = 0`).

One hard constraint discovered while establishing this: **`MAX_MONEY` is
`maximum-per-output`** (`utilwrapper.cpp:953`), default `1e14` raw = 1 000 000 GAS. A
premine above it makes block 1 unminable and the chain never starts:

```
ERROR: CheckTransaction() : txout.nValue too high
ERROR: MultiChainMiner : ProcessNewBlock, block not accepted
```

1 000 000 GAS comfortably covers the mandate's volume (20 companies × ~40 tx × 50 epochs ×
0.2 GAS ≈ 8 000 GAS), so the default ceiling suffices and need not be raised.

**RESOLVED: premine only.** `first-block-reward = 100000000000000`,
`initial-block-reward = 0`. This **supersedes
[test-restructure-2026.md §6.2/§7.1](test-restructure-2026.md)**, whose claim that the
native currency requires a positive `initial-block-reward` is disproved by the live run
quoted above. That ADR was right that something had to change and wrong about what; the
correction is recorded here rather than by editing an accepted decision record, and a dated
note is added at its §7.1 pointing here.

### 7.2 The flat 0.2 GAS fee is not expressible as a chain parameter

**Thesis §4.2.1:** *"ogni transazione della rete ha un costo fisso di 0,2 unità di GAS."*

**The code has no flat per-transaction fee.** `minimum-relay-fee` is *"Minimum transaction
fee, **per 1000 bytes**"* ([`paramlist.h:291`](../../src/chainparams/paramlist.h)). Measured
above: a 474-byte transfer at `minimum-relay-fee = 2e7` paid **0.0948 GAS**, not 0.2 — the
fee scales with size, and an informative payload (a stream publication) is a different size
again.

Three options, none of which I should pick unilaterally:

1. **Set `minimum-relay-fee = 2e7` and document the fee as 0.2 GAS/KB.** Honest, simple,
   diverges from the thesis' wording. The per-transaction cost becomes size-dependent.
2. **Calibrate `minimum-relay-fee` so the *typical* informative transaction costs ≈ 0.2
   GAS.** Preserves the number at the cost of making it an artefact of payload size, and it
   drifts whenever the payload changes.
3. **Accept the divergence and record it in a thesis corrigendum**, as
   `reconciliation-onchain.md` §7 did for Def. 6.7 — the cleanest precedent in this repo.

My recommendation is **(1) plus (3)**: configure the per-KB fee, and propose thesis wording
that says a per-KB tariff rather than a flat one. But this changes a number stated in the
thesis, so it is your call.

**RESOLVED: (1) + (3).** `minimum-relay-fee = 20000000` — 0.2 GAS per 1000 bytes — and the
divergence is documented with proposed thesis wording rather than papered over. The suite
records the *measured* fee per transaction alongside the configured tariff, so a reader can
see the per-transaction cost the size distribution actually produces instead of assuming
0.2. Proposed wording for §4.2.1:

> ogni transazione della rete ha un costo proporzionale alla propria dimensione, fissato
> dal parametro di catena `minimum-relay-fee` a 0,2 unità di GAS per 1000 byte e corrisposto
> al nodo miner che la include nel blocco a titolo di fee.

Rejected: calibrating the tariff so a *typical* transaction costs exactly 0.2 GAS. It
preserves the number by making it an artefact of the payload size — the moment the payload
changes, the headline figure is wrong and nothing says so.

### 7.3 `first-block-reward` pays the *first block*, not genesis

Minor, but it changes where the float lives. The parameter is *"Different mining reward for
first block only"* — block 1, mined by whoever mines it. On these suites the genesis node
mines the setup phase, so the premine reliably lands on the admin, which is what the model
wants. It is nonetheless an assumption rather than a guarantee, and it is worth asserting
explicitly in the harness (admin balance > 0 before any seeding) rather than relied on
silently. The existing `gas_seeded` check does exactly this and should be kept.

---

## 8. What the refactor will do, once §7 is settled

Stated here so the plan is on record, not as work already done.

```
test/functional/
├── lib/
│   ├── functional_lib.sh       repaired; economic helpers reworked per §3.2
│   ├── lint_lib.sh             unchanged + new checks for the new helpers
│   └── stats/
│       ├── catalogue.py        NEW — §4's table, observed/derived/unavailable
│       ├── extractors.py       NEW — admin-as-explorer polling, atomic writes
│       ├── analysis.py         we_stats.py's analysis, intact
│       ├── plots.py            NEW — matplotlib, degrades when absent
│       └── reporting.py        report.md / summary.txt
├── smoke_network.sh            NEW — the main suite, the mandate's §3 economics
├── weight_engine/ wpoa/        kept
└── run_functional_tests.sh     + the new suite
```

Commits, separated as the mandate requires: (a) communication/bug fixes on the existing
suite, (b) structural consolidation, (c) the transactional/economic model, (d) the
stats/report/plot pipeline.

---

## 9. Test results

Recorded in §6 and completed as runs finish. Nothing in this document reports a passing
test that was not executed; anything not run says so.
