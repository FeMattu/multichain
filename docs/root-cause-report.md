# wPoA — Root-cause analysis report (Phase 1)

> **Type:** historical record (report) · **Date:** 2026-09-03, follow-up §8 later ·
> **Status:** both fixes implemented and merged
>
> Kept as written: it records the work as it was done and is **not** updated when the
> code changes, so paths, identifiers and line numbers may no longer match the tree. The
> line numbers are those **at the time of the diagnosis**, deliberately: rewriting them
> would make the text cite lines that no longer mean what the prose says. Translated into
> English on 2026-09-25 with the content unchanged.
>
> **Changed since:** the shell suites cited here (`src/wpoa/test/functional_lib.sh`,
> `functional_test_wpoa_system.sh`, later moved under `test/functional/`) and the `shadow/`
> harness were replaced by the Python harness in [`test/`](../test/README.md), whose
> network emulation now runs on CORE ([`test/docs/core-fabric.md`](../test/docs/core-fabric.md)).
> The gap noted in §8.5 — the in-file `enable-wpoa` master being ignored by `AppInit2` —
> was fixed afterwards ([protocol-parameters.md §1bis](protocol-parameters.md#1bis-the-master-switch-and-how-it-expands)).
> The deferred activation that followed these fixes (the `WPoAEverElectable` latch) is
> described in [weight-engine.md §4bis](weight-engine.md#4bis-deferred-activation--when-wpoa-actually-takes-over).
>
> **For the system as it is now:** [wpoa-weight-engine-architecture.md §3.2 and §7](wpoa-weight-engine-architecture.md#32-the-mining-diversity-gate-one-function-pointer-instead-of-n-patches).

Repository: `/home/mattu/multichain` — a fork of MultiChain 2.3
Starting branch of the analysis: `tests/shadow-simulator` (HEAD `7e7d9a6`)
Date: 2026-09-03

Every path in this document was **verified by searching the code**, not assumed. The real
structure of the fork differs from the nominal upstream: the custom modules live in
`src/wpoa/` and `src/weight_engine/`, and the orchestration harness in `shadow/tools/` as
well as in `src/wpoa/test/`.

---

## 0. Executive summary

Two bugs, both confirmed, but **the starting state is not the one the mandate expected**:

* **Bug 1 (mining-diversity spacing)** has already been *partially* patched by commit
  `c81e513` ("wPoA: drop the mining-diversity spacing on wPoA-governed heights"), which is
  an ancestor of HEAD. The patch covers 2 call sites out of ~9. Call sites that reproduce the
  same bug in different contexts remain uncovered, and **the most damaging call site is not
  the one already patched**: it is `CWallet::GetKeyFromAddressBook(..., MC_PTP_MINE)`, which
  the wPoA miner calls on itself every round. Moreover the existing patch introduces an
  unintended **consensus divergence** (permissions evaluated in the mempool).
* **Bug 2 (`wpoa-weights` stream bootstrap)** is confirmed and is an **ordering** problem,
  not an unsolvable circular dependency. The `shadow/tools/role_admin.sh` harness already
  works around it on the script side; the C++ code, however, stays deadlocked on any clean
  network started without that harness, and the `src/wpoa/test/functional_lib.sh` harness
  does not work around it (it only waits, and gives up with a WARNING).

Consequence for the strategy: **I do not multiply patches on individual call sites**. Bug 1
must be fixed at its *single point of truth* (`IsBarredByDiversity`), which neutralises every
call site at once, and the two existing point patches must be brought back to `CanMine()` to
remove the mempool divergence. Full argument in §2.4 and §4.

---

## 1. Map of the files involved (real paths, confirmed)

| Role | Real path | Symbol / line |
|---|---|---|
| Native `mining-diversity` constraint | `src/permissions/permission.cpp` | `mc_Permissions::CanMine` :1692 |
| Spacing arithmetic | `src/permissions/permission.cpp` | `mc_Permissions::IsBarredByDiversity` :1979 |
| Declarations | `src/permissions/permission.h` | `CanMine` :365, `IsBarredByDiversity` :395 |
| Consensus-side miner permission check | `src/protocol/multichainblock.cpp` | `CheckBlockPermissions` :1150 (check at :1200-1210) |
| wPoA validation path | `src/protocol/multichainblock.cpp` | `VerifyBlockMinerWPoA` :769, dispatched from `VerifyBlockMiner` :923 (early return :942) |
| Native diversity replay (non-wPoA branch) | `src/protocol/multichainblock.cpp` | `CanMineBlockOnFork` :1090, :1100 |
| New block construction | `src/miner/miner.cpp` | `CreateNewBlock` — `canMine` probe :723-738 |
| Miner timing / election | `src/miner/miner.cpp` | wPoA Phase 2 branch :1203-1249; Phase 4 sortition branch :~1141-1195; native path :1250+ |
| Native miner pool | `src/miner/miner.cpp` | `LastActiveMiners` :969 (`CanMine` :1014) |
| wPoA activation predicate | `src/wpoa/wpoa_selector.cpp` | `WPoAActiveAtHeight` :48; flag `g_wpoa_enabled` :23 |
| Weight registry | `src/wpoa/stream_weight_registry.{h,cpp}` | class `StreamWeightRegistry`; `EnsureStreamExists` cpp:115, `EnsureSubscribed` cpp:160, `RegisterLocalWeight` cpp:272, `ThreadRegisterNodeWeight` cpp:774 |
| Weight engine (the real publisher) | `src/weight_engine/weight_engine.cpp` | `ThreadWeightEngine` :225 (publish at :358) |
| Input-stream auto-create (precedent) | `src/weight_engine/weight_reader.cpp` | `EnsureOneStream` :~60, `EnsureInputStreams` :134 |
| wPoA flag resolution | `src/core/init.cpp` | block :3231-3365, globals committed at :3348-3358; thread launch :3637-3650 |
| Weight-engine dependency guard | `src/core/init.cpp` | :3586-3590 (existing `InitError`, the pattern for the new ordering guard) |
| Epoch stability margin | `src/weight_engine/weight_streams.h` | `MC_WEIGHT_DEFAULT_STABILITY_MARGIN` :147 (= 6) |
| wPoA chain parameters | `src/chainparams/paramlist.h` | `enablewpoa*` :161-209 (protocol 20014), `miningdiversity` :115 |
| Shadow harness (geographic network) | `shadow/tools/role_admin.sh` | `do_grant` :53, create `wpoa-weights` :88-93 |
| wPoA functional harness | `src/wpoa/test/functional_lib.sh` | `fl_start_network` :188, `fl_grant_weights_write` :233 |
| System functional test | `src/wpoa/test/functional_test_wpoa_system.sh` | orchestration at the end of the file |
| wPoA unit suite | `src/wpoa/test/run_unit_tests.sh` + `*_tests.cpp` | self-contained Boost.Test |

### Logical duplication between the wPoA path and the standard path

`VerifyBlockMiner` (`multichainblock.cpp:923`) **returns early** into
`VerifyBlockMinerWPoA` when `WPoAActiveAtHeight(pindexNew->nHeight)` is true
(:942-945). So the native diversity replay (`CanMineBlockOnFork`, :1090/:1100) is **not
reachable** on wPoA-governed heights: the two paths are mutually exclusive, not duplicated.
`CheckBlockPermissions`, on the other hand, is **common to both regimes** (it is called
upstream, for every height) — which is why that is where the bug showed up.

---

## 2. Bug 1 — mining-diversity spacing active under wPoA

### 2.1 Mechanics of the defect

`IsBarredByDiversity(block, last, miner_count)` (`permission.cpp:1979`):

```
diversity = (miner_count * miningdiversity - 1) / 1000000      // MC_PRM_DECIMAL_GRANULARITY
diversity++                                                     // clamp in [1, miner_count]
if ((block - last) <= diversity - 1) return 1;                  // barred
```

`miningdiversity` defaults to `300000` = 0.3 (`paramlist.h:116`). Hence:

| N miners | `diversity` | bar condition | effect |
|---|---|---|---|
| 3 | `(900000-1)/1e6 + 1` = **1** | `(block-last) <= 0` | never true (Δ≥1) → **inert** |
| 4 | `(1200000-1)/1e6 + 1` = **2** | `(block-last) <= 1` | **bars two consecutive blocks** |
| 10 | `(3000000-1)/1e6 + 1` = **3** | `(block-last) <= 2` | bars two rounds apart |

This **confirms the masking quantitatively**: the default `NODES` is `3`
(`functional_lib.sh:37`), so the whole functional suite ran in a regime where the spacing is
arithmetically inert. From 4 miners upwards it bites.

Under wPoA every address with the `mine` permission takes part in **every** round and the
selection is weighted: a heavy validator legitimately wins two consecutive rounds. The
native round-robin spacing rejects that.

### 2.2 Call graph — every call site of `CanMine()` and its classification

Exhaustive search (`grep -rn "CanMine\s*(" src/`), plus the indirect consumers via
`GetAllPermissions` and `IsBarredByDiversity`.

| # | Call site | Context | Reachable under wPoA? | Verdict |
|---|---|---|---|---|
| 1 | `permission.cpp:1692` | definition of `CanMine` | — | unchanged (the gate goes underneath, in `IsBarredByDiversity`) |
| 2 | `permission.cpp:1209` (`GetAllPermissions`) | `if(type & MC_PTP_MINE) result \|= CanMine(...)` | **yes** | **BUG — to fix** (see §2.3, it is the most damaging vector) |
| 3 | `permission.cpp:1727` (`CanMine`) | internal application of the spacing | yes | fixed by the gate |
| 4 | `permission.cpp:1853` (`CanMineBlock`) | unused function (upstream comment: *"function not used"*) | no (dead) | fixed by the gate, no risk |
| 5 | `permission.cpp:1967` (`CanMineBlockOnFork`) | diversity replay on a fork | **no** — early return :942 | fixed by the gate (defence in depth) |
| 6 | `multichainblock.cpp:1206` (`CheckBlockPermissions`) | **block admission** | yes | **already patched** by `c81e513`, but with the mempool defect → to be brought back to `CanMine()` |
| 7 | `miner.cpp:736` (`CreateNewBlock`) | `canMine` probe for the validity self-test | yes | **already patched** by `c81e513`, same mempool defect → to be brought back |
| 8 | `miner.cpp:1014` (`LastActiveMiners`) | miner pool of the **native** timing | **no** — the wPoA branch at :1203 always `return`s before :1360 | **unchanged** |
| 9 | `multichainblock.cpp:1090`, `:1100` (`CanMineBlockOnFork`) | native replay | **no** — early return :942 | **unchanged** |
| 10 | `multichaintx.cpp:1811` | `receive` exemption for the miner's coinbase | **yes** | **latent BUG — to fix** (see §2.3) |
| 11 | `main.cpp:3710` (`UpdateChainMiningStatus`) | computation of `pindexNew->nCanMine` | **yes** | **BUG — to fix** (see §2.3) |
| 12 | `main.cpp:4496` | commented-out copy of `UpdateChainMiningStatus` | dead code | unchanged |
| 13 | `rpcpermissions.cpp:711` | permission introspection RPC | yes | **unchanged by choice**: it must report the *effective* permission; under wPoA the gate makes it consistent automatically |
| 14 | `rpcpermissions.cpp:1434` (`IsBarredByDiversity`) | `listminers` estimate of the next admitted block | yes | fixed by the gate: the `while` exits at once, `m_WaitBlocks=0`, `m_NextAllowed=next_block` — which under wPoA **is the right answer** |

#### Indirect consumers via `GetAllPermissions` (#2) — the main vector

`CWallet::GetKeyFromAddressBook(result, type)` (`wallet/wallet.cpp:3611`) uses
`GetAllPermissions(NULL, keyID, type)` and accepts the key only if `perm == type`
(`wallet.cpp:3626` and `:3642`). With `type == MC_PTP_MINE`, if `CanMine()` returns 0 because
of the spacing, **the local mining key is declared non-existent**. Call sites reachable under
wPoA:

| Path | Line | Effect when the node mined the previous block |
|---|---|---|
| `src/miner/miner.cpp` | **1205** — wPoA Phase 2 branch | `kThisMiner` invalid → log *"no local mining key, waiting"* → `MiningStartTime = now + 3600` → **the elected proposer does not mine its own block: a one-hour stall** |
| `src/miner/miner.cpp` | **1154** — wPoA Phase 4 branch (private sortition) | the same, on the production path |
| `src/miner/miner.cpp` | 906 (`CreateNewBlock`), 1092, 1136, 1365, 1430 | coinbase key selection / native path |
| `src/core/main.cpp` | 3942, 3994, 6923, 7000 | `nCanMine` → fork-choice ordering |
| `src/wpoa/stream_weight_registry.cpp` | **75-77** (`ResolveLocalAddress`) | `GetKeyFromAddressBook(MC_PTP_MINE)` fails → **fallback to `MC_PTP_CONNECT`, i.e. a DIFFERENT address** → `m_LocalAddress` changes identity depending on whether the node mined or not |
| `src/weight_engine/weight_publisher.cpp` | **72-74** | identical |

The last point is what **links the two bugs**: `StreamWeightRegistry` is built afresh on
every call of `WPoASelectProposer` (`wpoa_selector.cpp:~93`), so `m_LocalAddress` can
oscillate between two different addresses *of the same node* depending on who mined the
previous block. Consequences: the `sProposer == sLocalAddr` comparison in the miner
(`miner.cpp:1230`) can be made against the wrong identity, and a weight record can be
published under an address that is not the one registered as a validator (a self-published
record → discarded by every peer, cf. `PublishWeightRecord`).

#### `main.cpp:3710` → fork choice (#11)

`nCanMine` is consumed by the comparator `CBlockIndexWorkComparator` (`main.cpp:172-174`):

```cpp
if((pa->nCanMine > 0) && (pb->nCanMine == 0)) return false;
if((pa->nCanMine == 0) && (pb->nCanMine > 0)) return true;
```

A block whose miner is barred gets `nCanMine = 0` and its branch is **demoted** in
`setBlockIndexCandidates`. Under wPoA, a validator's second consecutive win demotes the
legitimate tip: spurious reorg pressure and a failure to advance. It is the same bug in a
completely different context (chain selection, not block admission) — exactly the kind of
call site the mandate asked to look for.

#### `multichaintx.cpp:1811` (#10)

```cpp
if(tx.IsCoinBase()) fCanReceive |= mc_gState->m_Permissions->CanMine(NULL,ptr);
```

An exemption: the miner may pay itself the coinbase without the `receive` permission. Under
wPoA, on the second consecutive win `CanMine` is 0 → the exemption vanishes → a validator
with `mine` **but without `receive`** has its own coinbase rejected, and with it the block.
Latent in the current harnesses (they always grant `connect,send,receive,mine`), real in
production with minimal permissions.

### 2.3 Defect introduced by the existing patch `c81e513` — mempool divergence

The patch replaces `CanMine()` with `CanCustom(NULL, addr, MC_PTP_MINE)`. But:

| | `GetPermission(..., checkmempool)` |
|---|---|
| `CanMine` (`permission.cpp:1719`) | `check_mempool = 0` |
| `CanCustom` (`permission.cpp:1635`) → `GetPermission(e,a,t)` (`:1179`) | `checkmempool = **1**` |

So the patch did not only remove the spacing (intended): it also **switched on the
evaluation of permission grants still in the mempool** inside `CheckBlockPermissions`, which
is a **consensus** check. The mempool is local by definition and different on every node: a
block signed by an address whose `mine` grant is still unconfirmed would be **accepted by the
node that has the transaction in its mempool and rejected by those that do not**. That is a
consensus divergence, i.e. a fork. Not observed in the harnesses because grants confirm long
before use, but it is a real defect and must be removed.

`CanCustom` also lacks the two short-circuits of `CanMine` (`IsProtocolMultichain()==0`,
`MCP_ANYONE_CAN_MINE`): harmless here only because `WPoAActiveAtHeight` already returns
`false` in both cases — an implicit, fragile dependency between two distant functions.

### 2.4 Choice of fix: a single point of truth

Two options:

**(A) Patch every call site**, replacing `CanMine()` with the raw permission under wPoA.
*Against*: ~7 places to touch in 5 files, in `permission.cpp` / `wallet.cpp` / `main.cpp` /
`multichaintx.cpp`; every future call site reintroduces the bug; it duplicates the activation
predicate in non-wPoA code; it is exactly the pattern that already produced an incomplete
patch with side effects (§2.3).

**(B) Neutralise the spacing at its source**, in `IsBarredByDiversity`, when the height is
wPoA-governed. *For*: a single semantic change in a single place; it fixes at once every call
site in the table (#2, #3, #5, #10, #11, #14) and every indirect consumer via
`GetKeyFromAddressBook`; `IsBarredByDiversity` already receives the **height** as its first
argument, so the gate is a pure function of `(height, chain params)` — identical on miner and
validator, which is the design requirement stated in `wpoa_selector.cpp:66-70`; it allows
**restoring `CanMine()`** at the two patched points, removing the mempool divergence.

**Choice: (B)**, plus restoring `CanMine()` at the two points of `c81e513`.

#### Linking constraint (verified) and its solution

`permissions/permission.cpp` is compiled into **three** targets (`src/Makefile.am`):

* `multichain_libbitcoin_multichain_a` (:361) — does **not** include `wpoa/*`
* `libbitcoinconsensus_la` (:698) — the standalone consensus library
* (through the first) the `multichain-util` / `multichain-cli` tools

`wpoa/wpoa_selector.cpp` is **only** in `libbitcoin_wallet_a` (:311). Calling
`WPoAActiveAtHeight()` directly from `permission.cpp` would produce an **unresolved symbol**
in `libbitcoinconsensus` and in the tools → a broken build.

Adopted solution: **a function-pointer hook**. `permission.{h,cpp}` declares/defines
`mc_WPoAGovernsMiningHook`, initialised to `NULL`; `wpoa/wpoa_selector.cpp` installs it at
**static-init time** (before `main()`), pointing to a thunk over `WPoAActiveAtHeight`. Thus:

* no new link dependencies: the targets without `wpoa/*` keep the hook `NULL` and therefore
  a **byte-identical** native behaviour;
* **no duplication** of the predicate: `WPoAActiveAtHeight` remains the only definition of
  "wPoA governs height h";
* no new init-ordering risk: the gate's value follows `g_wpoa_enabled` exactly like every
  other wPoA consumer.

---

## 3. Bug 2 — bootstrap of the `wpoa-weights` stream (priority)

### 3.1 The reconstructed bootstrap sequence

Who *should* create the stream: the **genesis admin node**, the only one with the `create`
permission on a permissioned chain. The code that does it already exists:
`StreamWeightRegistry::EnsureStreamExists()` (`stream_weight_registry.cpp:115`), which issues
`create ["stream","wpoa-weights",false]` → **CLOSED**, as per Def. 5.16.

The problem is **when** it is called. `EnsureStreamExists()` is `private` and has **a single
caller**: `RegisterLocalWeight()` (`:283`). And `RegisterLocalWeight` is invoked in two
mutually exclusive ways, decided in `init.cpp:3641-3650`:

```
if (g_wpoa_weights_enabled && wallet) {
    if (g_weight_engine_enabled)  ThreadWeightEngine();          // the real path
    else                          ThreadRegisterNodeWeight(g_node_weight);  // -weight fallback
}
```

**Static `-weight` path** (`ThreadRegisterNodeWeight`, `:774`): calls
`registry.RegisterLocalWeight(weight)` **straight away**, with `weight = g_node_weight`
(default 100). A weight always exists → `EnsureStreamExists()` runs on the first tick → the
admin creates the stream. **The cycle does not arise.**

**Weight-engine path** (`ThreadWeightEngine`, `weight_engine.cpp:225`) — the real one in
production: `RegisterLocalWeight` is reached **only at the end** of a chain of gates
(`:279-355`):

```
NodeReadyForWeight()                       → tip present, IBD finished
reader.EnsureInputStreams()                → membership + esg created and subscribed
WeightEngineActiveAtHeight(height)
epoch = (height - STABILITY_MARGIN + 1)/len  ≥ 1     → needs a BURIED epoch
ComputeLocalWeightForEpoch(...)            → needs to be a CERTIFIED miner
   └─► RegisterLocalWeight(w, epoch)  ─►  EnsureStreamExists()
```

### 3.2 Why the cycle does not break by itself

```
wpoa-weights does not exist
   └─► GetAllNodesWeights() returns {} on every node
        └─► WPoASelectProposer() elects nobody  ("0 validators, total=0")
             └─► no node mines beyond setup-first-blocks
                  └─► the height does not advance → no epoch gets buried
                       └─► ComputeLocalWeightForEpoch() never produces a weight
                            └─► RegisterLocalWeight() is never called
                                 └─► EnsureStreamExists() is never called
                                      └─► wpoa-weights does not exist  ◄── the cycle closes
```

The trigger height is the same on both sides: `WPoAActiveAtHeight` engages at
`height >= setupfirstblocks` (`wpoa_selector.cpp:71-73`). Up to there the chain advances under
the native rules; from there on it needs the weight registry, which does not exist. Hence the
exact stall observed: `0 validators, total=0` and `cannot score (unsynced or unweighted)`.

**It is not an unsolvable circular dependency: it is an ordering problem.** Creating the
stream does not *logically* depend on having a weight to publish — it depends only on the
`create` permission, available on the admin **from block 1**. The cycle exists only because
the creation was *implemented as a side effect of publication*, i.e. sequenced after an event
that itself requires it. Moving the creation **before** the epoch gate breaks this half of
the cycle deterministically: the precondition (`create` permission, wallet ready, tip
present) holds at every start of a clean network, whatever the state of the weights.

#### The ordering invariant (a correction to the initial analysis)

Bringing the `create` forward is **not sufficient on its own**, however, and this must be
stated precisely because it changes the design of the patch. The stall has two independent
halves:

1. **the stream does not exist** → the `.write` grants are silently discarded and nothing
   can be published;
2. **the registry is empty** → `WPoASelectProposer` elects nobody and no node mines.

Bringing the `create` forward solves (1). But (2) depends on *when the first weight becomes
computable*, which is a function of the chain parameters alone:

```
first buried epoch at   h_w = weight-epoch-length + STABILITY_MARGIN - 1
wPoA engages at          h_p = setup-first-blocks
```

The registry is populated in time **if and only if** the invariant holds

> **`setup-first-blocks  >  weight-epoch-length + STABILITY_MARGIN - 1`**

with `MC_WEIGHT_DEFAULT_STABILITY_MARGIN = 6` (`weight_streams.h:147`).

Check against the real values:

| Configuration | epoch-length | margin | h_w | setup-first-blocks | invariant |
|---|---|---|---|---|---|
| **product default** (`paramlist.h:112`, `:238`) | 100 | 6 | **105** | **60** | **VIOLATED** → stall |
| shadow (`shadow/config/params.overrides`) | 12 | 6 | 17 | 60 | holds |

The product default **violates the invariant**: a clean network started with
`-enablewpoa=1 -enableweightengine=1` and otherwise default parameters stops at height 60,
which is exactly the reported symptom. The shadow harness does not run into the stall because
its configuration respects the invariant by construction — and says so in the comment next to
the parameter:

```
WEIGHT_EPOCH_LENGTH=12
SETUP_FIRST_BLOCKS=60         # > epoch(12) + stability margin(6) = 18
```

So the explicit `create` in `role_admin.sh` is not what keeps the shadow network alive: what
keeps it alive is **the respected invariant**. The explicit `create` only removes the latency
and the lost grants of half (1).

Consequence for the design of the fix: the patch must cover **both** halves — bring the
creation forward (deterministic, always) *and* make a violation of the invariant detectable,
which would otherwise show up as a silent stall at `setup-first-blocks` with no message
pointing at the cause.

The proof that this is the right pattern is **already in the same codebase**:
`reader.EnsureInputStreams()` (`weight_reader.cpp:134`, `EnsureOneStream` :~60) creates
`weight-engine-membership` and `weight-engine-esg` — also CLOSED — and is called
**unconditionally on every tick, before any epoch gate** (`weight_engine.cpp:262`).
`wpoa-weights` is the only one of the three streams without this treatment. The bug is an
**asymmetry**, not a design choice.

### 3.3 Secondary defect: a permanent latch on a transient failure

In `EnsureStreamExists` (`:123-127`, `:139`) and in `EnsureOneStream`:

```cpp
m_CreateAttempted = true;      // ← set BEFORE the try
try { createcmd(params,false); } catch (...) { /* log */ }
```

The flag latches **even when the `create` fails**. And the `registry` object in
`ThreadWeightEngine` / `ThreadRegisterNodeWeight` lives for the whole lifetime of the thread:
a **transient** failure (wallet not yet unlocked, UTXOs not available, `create` grant not yet
confirmed) **wedges the node forever** — the loop keeps running but will never retry the
`create`. It must be fixed together with the main bug: without this, the code-side solution
would only be reliable on the first try.

### 3.4 Current state of the harnesses

| Harness | Creates `wpoa-weights`? | Note |
|---|---|---|
| `shadow/tools/role_admin.sh` :88-93 | **yes**, idempotently (`rpc_ok ... \|\| "already present"`), CLOSED, before the `.write` grants :97, with `wait_stream` | a workaround already in place; the comment :82-87 documents exactly this stall |
| `src/wpoa/test/functional_lib.sh` :233 | **no** | `fl_grant_weights_write` only **waits** for the stream to appear (60 attempts), then *"WARNING: wpoa-weights does not exist yet; write grants skipped"* and carries on. With the weight engine on, the wait can never be satisfied |
| `src/weight_engine/test/functional_test_weight_engine.sh` | no | single node, uses the `-weight` path (where the cycle does not arise) |

### 3.5 Choice: harness-only vs code-side auto-creation

**Option H — harness only** (explicitly create the stream in `role_admin.sh` /
`functional_lib.sh` before the grants).
*For*: zero risk on the consensus code; already shown to work in `role_admin.sh`.
*Against*: **it is not a fix, it is a workaround**. It holds only for networks started by
those scripts. Any clean network started by an operator, or by the second harness, or in
production, stays deadlocked. It makes the protocol's liveness depend on a manual step not
documented in the code. And it leaves defect §3.3 in place.

**Option C — idempotent node-side auto-creation.**
*For*: it breaks the cycle **at its origin**, on every start, with no operational step; the
`create` permission is already the right security gate (non-admins cannot create, and must
not); it realigns `wpoa-weights` with the treatment already given to the other two streams
(§3.2), so it removes special code instead of adding some; it allows fixing §3.3 in the same
place; it makes the functional test a check of the *product*, not of the harness.
*Against*: it touches the node's startup path; it must be made robust on a multi-admin
network (§5).

**Choice: Option C**, implemented alone. The two options are **redundant**, not
complementary: both guarantee "the stream exists before a weight is needed", and H is an
operational subset of C. With C active, the `create` in `role_admin.sh` becomes a benign no-op
(it remains idempotent and harmless — **I do not remove it**, it is the belt-and-braces for
shadow networks already running), and the wait loop of `functional_lib.sh:233` **starts being
satisfied**, so it needs no change.

### 3.6 Covering the second half: detecting a violation of the invariant

For the invariant of §3.2 there are three possibilities:

**(i) A blocking `InitError`** on the parameter combination that will stall.
*Against, decisively*: a node joining a chain **already past** `setup-first-blocks` —
advanced with weights published by other means (the static `-weight` path on some nodes, or
a manual publication) — syncs from height 0 and would see the same parameter combination,
refusing to start on a healthy network. Risk of *bricking* existing deployments:
**discarded**.

**(ii) The selector falling back to the native rules on an empty registry.** It would change
the consensus semantics of the election, and it is asymmetric with `VerifyBlockMinerWPoA`,
which on an empty registry already *skips* the check (`multichainblock.cpp:902`): the
validator is lenient, the miner refuses to mine, and the stall comes precisely from this
asymmetry. Touching consensus for a configuration problem is disproportionate:
**discarded**.

**(iii) A specific startup WARNING**, naming the three numbers and the exact height at which
the network will stop, emitted only when the weight engine **and** wPoA selection are both
on. It cannot break anything, and it turns a silent stall into an error diagnosable on the
first start. It is also the pattern **already used in the same block** of `init.cpp` for
consensus-critical divergences (`init.cpp:3599-3606`, `:3620-3626`).

**Choice: (iii)**, together with Option C. The two are complementary, not redundant: C
guarantees the ordering in the half the code controls (the stream's existence), (iii) makes
immediately visible the half that depends on the chain configuration and that the code cannot
fix by itself without touching consensus.

---

## 4. Interaction between the two fixes, and the merge decision

The two fixes are **logically independent** (one touches the mining-permission gate, the
other the ordering of the stream bootstrap) but they have **one real point of contact**,
identified in §2.2: `StreamWeightRegistry::ResolveLocalAddress()`
(`stream_weight_registry.cpp:75-77`) and `weight_publisher.cpp:72-74` use
`GetKeyFromAddressBook(MC_PTP_MINE)`, which is affected by Bug 1. Until Bug 1 is fixed, the
local identity used to publish the weight can change depending on whether the node mined the
previous block.

Practical consequence: the **functional test of Fix 2** (clean network, N≥4, weight engine
on, check that the registry is not empty at the switch to wPoA) on a branch containing *only*
Fix 2 could be unstable for a cause that belongs to Fix 1.

Decision: the two fixes stay on **separate, unmerged branches**, as requested — neither
depends on the other to *compile* or to be reviewed. The dependency is only one of *runtime
observed stability*, and it is declared here and in the test's docstring rather than resolved
with a convenience merge. At integration time the two branches must be applied together.

---

## 5. Collateral risks per proposed change

### Fix 1 — gate in `IsBarredByDiversity`

| Risk | Assessment |
|---|---|
| **Chains not using wPoA** | Hook `NULL` (tools, `libbitcoinconsensus`) or `g_wpoa_enabled == false` → `IsBarredByDiversity` unchanged **byte for byte**. `WPoAActiveAtHeight` already returns `false` when `IsProtocolMultichain()==0` or `MCP_ANYONE_CAN_MINE`. |
| **Pre-setup heights on the same wPoA chain** | `WPoAActiveAtHeight` is `height >= setupfirstblocks`; below that threshold the spacing stays fully active, as today. |
| **3-node networks (where the bug was masked)** | At N=3 the computed spacing is 1, i.e. already inert (§2.1): the gate cannot change anything observable. To be checked for regression anyway with the suite at `NODES=3`. |
| **d=0 / uniform weight / wPoA off** | `miningdiversity = 0` → `diversity = 0+1 = 1` → already inert, independently of the gate. Uniform weight with wPoA on: the selection stays weighted (uniform), the gate only removes the spacing, which is the intended behaviour. |
| **Removing the spacing = losing a security guarantee?** | Under wPoA the rotation of proposers is guaranteed by the weighted selection + VRF/RANDAO beacon, not by the round-robin spacing: they are two alternative mechanisms for the same purpose, and the design (§5.12.3) explicitly prescribes the first. On non-wPoA heights nothing changes. |
| **Restoring `CanMine()` at the 2 points of `c81e513`** | Restores the `checkmempool=0` semantics that are correct for consensus (§2.3). No loss: the spacing is already neutralised by the gate. |
| **`listminers` (`rpcpermissions.cpp:1434`)** | `m_WaitBlocks` becomes 0 and `m_NextAllowed` = next block for every active miner. Semantically correct under wPoA, but it **changes an RPC's output**: to be noted for whoever consumes the value. |
| **Init ordering (pre-existing)** | `g_wpoa_enabled` is assigned at `init.cpp:3349`, **after** `LoadBlockIndex` (:2761) and `ActivateBestChain` (:3086). During the initial load every wPoA predicate is `false`, so `UpdateChainMiningStatus` computes `nCanMine` with the spacing. A **pre-existing defect**, affecting `VerifyBlockMiner` and every other wPoA consumer equally; neither introduced nor worsened by this patch. Impact limited to the fork-choice ranking of already accepted blocks. Reported, out of scope. |

### Fix 2 — idempotent auto-creation

| Risk | Assessment |
|---|---|
| **Idempotence across repeated calls** | `EnsureStreamExists` queries `FindEntityByName` on every invocation and returns `true` at once if the stream exists: no second `create`. |
| **Race between several admins creating in parallel** | Stream names are unique: if two `create`s land in the same block one is rejected at transaction acceptance. The loser finds the winner's stream through `FindEntityByName` on the next tick and converges. **Necessary condition**: the latch must not prevent the re-check — guaranteed because the existence check precedes the latch. |
| **Unbounded retries on non-admin nodes** | A `create` on a node without the `create` permission *always* fails. Fixing §3.3 with an unbounded retry would spam the log every 3 s. Mitigation: a **bounded** attempt counter (not a boolean), so transient failures are overcome and permanent ones stop. |
| **Nodes without the `create` permission** | Correct and unchanged behaviour: they do not create, they wait and subscribe. Security remains entrusted to MultiChain permissions, not to conventions. |
| **Chain without the weight engine** | The `-weight` path already called `EnsureStreamExists` on the first tick: no observable change in behaviour. |
| **Chain with `enablewpoaweights=0`** | `init.cpp:3641` launches no thread: the stream is never created, as today. |
| **Early creation of the stream** | The stream is created before any weight exists: `getallweights` will report `0 validators` on an **existing, empty** stream instead of on a missing one. A correct transient state, more diagnosable than today's. |
| **Order relative to `setup-first-blocks`** | The `create` starts as soon as the node is ready (tip present, IBD finished), i.e. **well before** `setupfirstblocks` (default 30 in the harness): confirmed with a wide margin before wPoA engages. It is the margin that breaks the cycle reproducibly. |
| **Order relative to the `.write` grants** | A `wpoa-weights.write` grant issued before the stream exists is silently discarded — exactly why `functional_lib.sh:227-232` re-issues them. With early creation, the initial grant of `_fl_bootstrap_node:173` is much more likely to take, and the re-issue stays as a safety net. |
| **Bounded retry instead of the permanent latch** | The latch stays on the **successful broadcast** (never two `create` transactions, hence no risk of a duplicate stream should MultiChain accept a name already present but unconfirmed); the bounded retry acts only on **failures**. Worst cost on a node without `create`: N failed attempts and then silence, instead of just one. |
| **Create broadcast but never confirmed** | If the `create` transaction ends up in the mempool and the chain stops, the latch prevents re-broadcasting. A pre-existing defect, not worsened: with the fix the `create` starts while the chain advances under native rules, so it confirms with a wide margin. Noted, not solved. |
| **Invariant WARNING — false positives** | The warning fires only with the weight engine **and** wPoA selection both on. On a node joining a healthy chain already past `setup-first-blocks` (advanced with weights published by other means) the warning is a false positive: it is the price of not using an `InitError`, which would instead prevent startup (cf. §3.6). The message text says explicitly that it concerns starting a **clean** network. |
| **Invariant WARNING — no effect on consensus** | It is only a `LogPrintf`: it changes no flag, parameter or validation path. |

---

## 6. Intervention plan (outcome of Phase 1)

**Branch `fix/wpoa-diversity-spacing-canmine`**
1. `src/permissions/permission.h` — declare the hook `mc_WPoAGovernsMiningHook`.
2. `src/permissions/permission.cpp` — define it `NULL`; gate at the top of
   `IsBarredByDiversity`.
3. `src/wpoa/wpoa_selector.cpp` — thunk over `WPoAActiveAtHeight` + static-init installation.
4. `src/protocol/multichainblock.cpp` — restore `CanMine()` in `CheckBlockPermissions`.
5. `src/miner/miner.cpp` — restore `CanMine()` in the `CreateNewBlock` probe.
6. Test: a targeted regression case "a double consecutive win at N≥4 is accepted".

**Branch `fix/wpoa-weights-stream-bootstrap`**
1. `src/wpoa/stream_weight_registry.h/.cpp` — expose a public `EnsureStreamReady()`; replace
   the boolean `create` latch with "latch on successful broadcast + bounded retry on
   failures", so a transient error does not wedge the node forever.
2. `src/weight_engine/weight_engine.cpp` — call `EnsureStreamReady()` next to
   `EnsureInputStreams()`, **before** the epoch gate.
3. `src/core/init.cpp` — a startup WARNING on a violation of the invariant of §3.2, with the
   three numbers and the expected stall height.
4. Test: a clean network with the weight engine on a configuration that respects the
   invariant; check that the stream exists **before** the transition, that the registry is
   not empty at the transition height, and that at least one validator can be scored.

No merge into the main branch: the two fixes are independent (§4).

---

## 7. Outcome of the experimental verification

All the runs below are on a real multi-node network (not simulated), with the binaries built
from the respective branches. Clean build on both (`EXIT=0`), including `multichain-util`,
`multichain-cli` and `libbitcoinconsensus.la`: exactly the targets that would have failed with
an unresolved symbol had the gate been written as a direct call to `WPoAActiveAtHeight` from
`permission.cpp` (§2.4).

Symbol check, confirming the hook design:

| Target | `mc_WPoAGovernsMiningHook` | thunk + installer |
|---|---|---|
| `multichaind` | present (BSS) | **present** → gate active |
| `multichain-util` | present (BSS, = NULL) | absent → native behaviour unchanged |
| `libbitcoinconsensus` | present (= NULL) | absent → native behaviour unchanged |

### Fix 1 — `fix/wpoa-diversity-spacing-canmine`

Spacing arithmetic checked against the C++ formula (`fl_native_diversity_spacing`):
`d=0.3` → N=3 ⇒ 1 (inert), N=4 ⇒ 2, N=10 ⇒ 3; `d=0` → 1 at every N (the "d=0 unchanged" case
is confirmed by construction).

| Run | Outcome |
|---|---|
| `NODES=4 WEIGHTS="100 200 400 800"` | **PASS** (9/9 checks). Native spacing = 2 (the regime where the bug bites). **19 pairs of consecutive blocks by the same miner** in a 30-block window, all accepted. 0 `Permission denied for miner`, 0 `cannot mine now`, 0 `no local mining key`. |
| `NODES=3` (the regime where the bug was masked) | **PASS** (10/10 checks). The check correctly detects spacing = 1 and declares the regime inert; the three symptom assertions run anyway and are at zero. The dedicated 4-node scenario starts automatically and reproduces **19 consecutive pairs**, all accepted. |

The 19 consecutive pairs are the direct measure of the fix: each of them, before the patch,
would have been rejected in `CheckBlockPermissions` or — more likely — never produced, because
the elected proposer would have considered itself without a mining key
(`GetKeyFromAddressBook`, §2.2) and slept for an hour.

For comparison, the measurement quoted in the comment of `shadow/config/params.overrides` on
the same phenomenon: *"0 consecutive blocks out of 190 measured, against ~99 expected"* with
`MINING_DIVERSITY` on — which is why that configuration had to zero `MINING_DIVERSITY` to
measure the weighted selection alone. With this fix zeroing it is no longer necessary: the
spacing is inert on wPoA-governed heights and stays fully active elsewhere.

### Fix 2 — `fix/wpoa-weights-stream-bootstrap`

A clean 3-node network, `-enablewpoa=1 -enableweightengine=1 -weightepochlength=10`,
`setup-first-blocks=30` (the invariant of §3.2 holds: `30 > 10+6-1 = 15`).

| Check | Outcome | Evidence |
|---|---|---|
| `stream_created_early` | **PASS** | `wpoa-weights` exists **at height 7**, i.e. before the transition (30) and before a weight is computable (15). Before the patch the stream could not exist at height 7. Created CLOSED (`restrict.write = true`), as per Def. 5.16 |
| `no_stall_at_transition` | **PASS** | chain at height 60 > 30 |
| `registry_populated` | **PASS** | all 3 nodes report `validators=3`; 3 validators with a non-zero weight (scorable) |
| `no_scoring_stall_logs` | **PASS** | **0** occurrences of `cannot score (unsynced or unweighted)` on every node |
| `weights_agree_across_nodes` | **PASS** | no divergence on the aggregate |

Weight pipeline confirmed end to end from the node log, not only from the RPCs:

```
[WeightEngine] epoch 2 (height 25): w_k = 3750 for 19tAT23FWx8TYAHje...
[StreamWeightRegistry] All nodes weights: 3 validators, total=6750
```

i.e. the weight was **derived** by the engine (self-attested membership + ESG signed by the
CA + activity and reconciliation from the blocks) and published, with the registry populated
**before** height 30. In the same run there are 10 `wPoA-sortition` elections between heights
30 and 59: the chain is governed by wPoA and advances.

**Negative control of the WARNING.** On the test configuration (invariant satisfied) the
warning is correctly **absent**. On default parameters, instead, it fires with the exact
numbers:

```
[WeightEngine] WARNING: bootstrap ordering. The first weight cannot exist before height 105
(weight-epoch-length=100 + stability margin=6 - 1), but wPoA starts electing proposers at
setup-first-blocks=60. On a clean network the weights stream is still empty there, no
proposer can be elected, and the chain will stall at height 60. Set setup-first-blocks
greater than 105, or lower weight-epoch-length, in params.dat BEFORE starting the network.
```

### Independence of the two branches (verified)

Intersection of the files modified by the two branches relative to `master`: **empty**. Trial
merge (`git merge-tree`, no side effects): **0 conflicts**. No merge performed, as per §4.

---

## 8. Follow-up — a `setup-first-blocks` floor derived at genesis

Branch: `fix/wpoa-setup-first-blocks-floor` (from `master`, commit `8e1ca88`).

### 8.1 The FAIL reported on `diversity_spacing_4n` was not a regression

Reported symptoms: `0` consecutive pairs with spacing 2 and **137** occurrences of
`no local mining key, waiting`. It is the exact signature of the **pre-fix** bug described in
§2.2.

Cause: **a stale binary**. `src/multichaind` was from 09-04 10:04 — the build of branch
`fix/wpoa-weights-stream-bootstrap`, which starts from `master` and does **not** contain Fix 1.
The sources were from 09-05 (post-merge), but `make` had not been re-run. Direct check on the
binary: `0` occurrences of `WPoAGovernsMiningThunk` and no `mc_WPoAGovernsMiningHook` symbol.
After `make`, both present. No code fix needed — only a rebuild.

### 8.2 The invariant becomes a derived value

Up to here the invariant of §3.2 was only *reported* by a WARNING. Now it is **derived**:
when the weight engine feeds wPoA selection, `setup-first-blocks` is raised to its floor; a
larger value is left intact (a longer setup phase is a legitimate operator choice).

**A correction to the requested arithmetic.** The floor is not `epoch + margin`. That is the
height at which the first weight becomes *computable*; but the selector reads **confirmed
items only**, and the value still has to be noticed by the engine's tick, published and
**mined** — in a block that the **native** rules can still produce, because from
`setup-first-blocks` onwards a block requires precisely the registry that block would
populate. With the floor at `epoch + margin` the confirming block falls exactly on the first
wPoA height: **a deadlock one block wide**. Hence `MC_WEIGHT_SETUP_PUBLISH_MARGIN` (3 blocks:
engine tick, confirmation, propagation) and the `+1`:

```
first_computable = weight-epoch-length + STABILITY_MARGIN - 1
floor            = first_computable + MC_WEIGHT_SETUP_PUBLISH_MARGIN + 1
```

For `epoch=40`: computable at 45, confirmable by 48, floor **49**.

### 8.3 Where it is applied, and why only there

Only on the chain **creation** path:

* `AppInit2`, on the genesis node's branch, **before** `Build()` — which computes the
  parameter hash. The corrected value thus becomes part of the chain's identity and reaches
  every joining node through the ordinary `params.dat` inheritance.
* `multichain-util create` / `clone`, so that the file the operator opens is already
  consistent.

Rewriting it on a chain **already running** must never happen: `setup-first-blocks` is
hash-enforced and changing it later would fork the network. The runtime WARNING of §3.6 stays
as a safety net for chains created before this rule.

The two switches are passed **by the caller**, not read from `params.dat`: at genesis they may
arrive from the command line on a file that still says `false` — and that is exactly the
configuration that stalls. The resolution mirrors `AppInit2`'s (master switch from the CLI
included), on purpose: deriving the floor from a wPoA that then does not run would lengthen
the setup needlessly.

`SetParam()` cannot be used — it serves only `CALCULATED`/`COMMENT` parameters and refuses
those already present — so the value is written directly into the parameter store. It is not
exposed as a generic "overwrite a user parameter" helper: rewriting a hash-enforced parameter
is legitimate **only** here.

### 8.4 Verification

| Case | Configuration | Outcome |
|---|---|---|
| value too low, flags in params.dat | epoch 40, setup 20 | **20 → 46/49**, WARNING, written into `params.dat` |
| value too low, flags from the CLI | params.dat `false`, `-enablewpoa -enableweightengine` | **20 → 49** — the case that reading `params.dat` alone would have missed |
| sufficient value | epoch 40, setup 90 | **90 unchanged** |
| weight engine off | epoch 40, setup 20 | **20 unchanged** |
| `multichain-util create` | `-enableweightengine=1 -weightepochlength=40 -setupfirstblocks=20` | **20 → 46**, WARNING on screen, in `params.dat` |

**End to end on the configuration that used to stall** (3 nodes, epoch 40,
`setup-first-blocks` 20 — which without the floor stops at height 20 with 0 weight
publications): 6/6 checks PASS. Floor 20→49; chain at **162**; `validators=3 total=2250` on
every node; **0** `cannot score (unsynced or unweighted)`; weights in agreement.

The `setup_first_blocks_floor` check reads the value from `getblockchainparams`, not from the
seed node's file: it shows that the corrected value really is the **chain's**, hence inherited
by everybody.

### 8.5 A collateral finding (not fixed here)

`AppInit2` resolves the wPoA flags by reading from `params.dat` only the **per-phase** keys
(`enable-wpoa-weights`, `enable-wpoa-selection`, …); the `enable-wpoa` master is consulted
**only** from the command line (`init.cpp:3321-3324`). So setting only `enable-wpoa = true` in
the file leaves every phase off — and, with `enable-weight-engine = true`, the node refuses to
start with *"-enableweightengine requires the wPoA weights stream"*.

Out of scope for this branch, hence **not fixed**. The bootstrap test works around it by
putting only `weight-epoch-length` in `params.dat` (the value the floor derives from, which
must be a chain value) and passing the switches from the CLI, with a comment explaining why.
