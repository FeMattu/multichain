# ADR — restructuring the test tree, and realigning the suites with the code

> **Note on paths (2026-09-17).** This document refers to `test/functional/`,
> `test/output/` or `test/experimental/`, trees that were replaced when `test/` was
> rebuilt as a Python harness. The references are kept as written because they record the
> work as it was done; for the current structure see
> [`../../test/README.md`](../../test/README.md) and [`../../test/docs/fixes-changelog.md`](../../test/docs/fixes-changelog.md).


> **Status:** accepted, implemented. The four open points of §7 were resolved on
> 2026-09-15; §7 records the answers.
> **Scope:** `src/weight_engine/test/`, `src/wpoa/test/`, a new project-level
> `test/functional/`. Explicitly **out of scope:** `/experiments` (the Python network
> topology emulation framework) and `src/weight_engine/test/experimental/` (the MyLedger
> economic simulation harness — see §2.3).
> **Register: technical-direct.** Decision record: the inventory, the discrepancies
> verified one by one, the decisions and their consequences. Module references:
> [../../src/wpoa/docs/testing.md](../testing.md),
> [../../src/wpoa/docs/weight-engine.md](../weight-engine.md).
> Sibling ADRs: [../../src/wpoa/docs/adr/reconciliation-onchain.md](../adr/reconciliation-onchain.md),
> [../../src/wpoa/docs/adr/randao-fold-bare-xor.md](../adr/randao-fold-bare-xor.md).
>
> **On the paths cited in §1–§4.** Those sections were written *before* the move and cite
> files at the locations they occupied then, with line numbers referring to their content
> at that moment. Such citations are marked *as audited* and are deliberately plain text
> rather than links: after the move and the alignment edits, a link would resolve to a file
> whose line numbers no longer match what the surrounding text claims — worse than no
> link. §5 onward cites the current tree and links normally.

---

## 1. Why this document exists

The test tree grew module by module. `src/wpoa/test/` and `src/weight_engine/test/` each
hold unit tests *and* functional tests, and the functional ones are not module-scoped at
all: `functional_test_weight_engine_bootstrap.sh` already reaches across the boundary and
sources `src/wpoa/test/functional_lib.sh`
(`src/weight_engine/test/functional_test_weight_engine_bootstrap.sh:50`, as audited).
A functional run exercises wPoA, the weight engine, the malus registry and the streams as
one system, so filing those scripts under one module's directory misstates what they test.

This ADR records the inventory, the verification of five suspected discrepancies, and the
decisions that follow — **before** anything moves, so the restructuring diff stays a pure
rename.

---

## 2. Inventory and classification

Classification rule used throughout:

- **unit** — a self-contained `BOOST_AUTO_TEST_CASE` module, compiled straight from
  source by `g++`, starting no `multichaind`. Verified mechanically: every one of the ten
  `.cpp` files includes only pure headers plus `crypto/sha256.h` (see the include audit in
  §2.1), so none of them can link the node runtime.
- **functional** — a bash script that launches real `multichaind` / `multichain-cli`
  processes and asserts network behaviour.
- **neither** — tooling and analysis harnesses.

### 2.1 `src/weight_engine/test/`

| File | Class | Notes |
|---|---|---|
| `weight_authorization_tests.cpp` | **unit** | includes only `weight_engine/weight_authorization.h` |
| `weight_engine_tests.cpp` | **unit** | only `weight_engine/weight_engine.h`; already on the restitution-rate formulation (`g_k → saldo_k → rho_k → w_k`) |
| `weight_records_tests.cpp` | **unit** | only `weight_engine/weight_records.h` |
| `weight_verifier_tests.cpp` | **unit** | only `weight_engine/weight_verifier.h` |
| `run_unit_tests.sh` | runner (unit) | compiles with `g++ -I$SRC_DIR`; **does not use autotools** |
| `functional_test_weight_engine.sh` | **functional** | single node, own `mcli`/`ok`/`bad` helpers — does **not** source `functional_lib.sh` |
| `functional_test_weight_engine_bootstrap.sh` | **functional** | multi-node, **does** source `src/wpoa/test/functional_lib.sh` |
| `experimental/` (31 files) | **neither** | MyLedger economic simulation harness — see §2.3 |

### 2.2 `src/wpoa/test/`

| File | Class | Notes |
|---|---|---|
| `wpoa_weight_tests.cpp` | **unit** | `wpoa/weight_record.h` |
| `wpoa_malus_tests.cpp` | **unit** | `wpoa/malus_record.h` |
| `wpoa_selector_tests.cpp` | **unit** | `wpoa/wpoa_selector.h` + `crypto/*` |
| `vrf_wrapper_tests.cpp` | **unit** | links `libsecp256k1.a` |
| `randao_accumulator_tests.cpp` | **unit** | `wpoa/randao_accumulator.h` + `crypto/sha256.h` |
| `private_sortition_tests.cpp` | **unit** | links `libsecp256k1.a` |
| `run_unit_tests.sh` | runner (unit) | six suites: `weight malus selector vrf randao sortition` |
| `functional_lib.sh` | **functional** (library) | sourced, never executed; 398 lines of shared bootstrap |
| `functional_test_wpoa_system.sh` | **functional** | one network, nine checks, three scenarios |
| `run_functional_tests.sh` | runner (functional) | thin wrapper: hard timeout + `QUICK` |
| `run_all_tests.sh` | runner (aggregate) | unit → functional |
| `analyze_distribution.py` | **neither** | chi-square proposer-distribution analyzer, invoked *by* the functional test |
| `README.md` | docs | documents the current layout; will need rewriting |

### 2.3 `experimental/` — confirmed: leave it exactly where it is

Agreed with the mandate, and for a stronger reason than "it is neither unit nor
functional". `experimental/` is not a test at all: it has **no pass/fail contract**. Its
own README states it plainly — *"it is **not** a pass/fail functional test […] its product
is a set of CSVs, an `.xlsx` report and a log for plotting and statistics"*
([experimental/README.md:7](../../src/weight_engine/test/experimental/README.md#L7)).

Three further reasons not to touch it:

1. **It is a consumer of the weight engine specifically**, not of the system. Its research
   question is *"does the deployed weight engine compute the weight the POESIA / Vers_2
   model specifies"* — a `src/weight_engine/` question. Its current path is correct.
2. **It carries committed output.** `output/*.csv` and `output/report.xlsx` are tracked
   reference results. Moving them would break the provenance of the "20/20 cells exact"
   claim in its README.
3. **It is a behavioural reference for this work, not a subject of it.** §5.2 below adopts
   its `-weighttreasuryaddress` sequencing as the model for the bash harness.

**No action proposed.** Flagged for your confirmation in §7 only because the mandate asked
to be told if I thought otherwise — I do not.

---

## 3. The five suspected discrepancies, verified

### 3.1 `RandaoAccumulator::DeriveSeed` vs `randao_accumulator_tests.cpp`

**Your premise is right about the commit and wrong about the consequence.** Both halves
matter, so here is exactly what I found.

**The commit.** It was not the fold commit. The convention changed in **`ef08074c`**
*"wPoA: anchor the selection seed to h[n] and n+1 per Def. 5.4"* (2026-08-18), which
touched exactly two files:

```
src/wpoa/randao_accumulator.cpp | 14 +++++++-------
src/wpoa/randao_accumulator.h   | 33 +++++++++++++++----------------
```

`git log -S 'h_tip32' -- src/wpoa/test/randao_accumulator_tests.cpp` returns **nothing**.
So yes: **the commit that renamed `h_prev32` → `h_tip32` never touched the test file.**
(The later fold commit `c1879600` *did* touch it, but for the XOR, not the seed.)

**The consequence — and this is where the instruction does not apply.** The test file
exercises the **pure core**, and the pure core is *convention-agnostic*. `DeriveSeed`
([randao_accumulator.h:176](../../src/wpoa/randao_accumulator.h#L176)) computes

```
SHA256( rtot_lookback32 ‖ h_tip32 ‖ height_be )
```

It has no idea whether the caller passes `h[n]` or `h[n-1]`, `n` or `n+1` — it hashes three
opaque inputs in a fixed order. **The byte layout is identical before and after
`ef08074c`.** `ef08074c`'s own commit message says as much: *"the pure DeriveSeed core is
unchanged (its `h_prev32` parameter is renamed `h_tip32` to match)"*.

So the unit tests are **not testing a different formula from the one implemented**. There
is no wrong-formula bug to fix. What I actually found is two smaller things:

**(a) The tests are nominally stale — misleading, not wrong.** The helper parameter is
still called `hprev`
([randao_accumulator_tests.cpp:66,100](../../src/wpoa/test/randao_accumulator_tests.cpp#L100)),
the module header comment still states the formula as
`DeriveSeed == H(R_tot ‖ h_prev ‖ height_be)`
([line 13](../../src/wpoa/test/randao_accumulator_tests.cpp#L13)), and
`seed_is_sensitive_to_every_input` asserts *"prev-hash matters"*
([line 378](../../src/wpoa/test/randao_accumulator_tests.cpp#L378)). A reader of the test
suite would conclude the old convention is still in force. Worth fixing as naming, and
cheap.

Note that lines 193–198 and 259–260 *already* use the new language ("commits to the tip
hash and to the height being elected", `bytes hn = make_val(77)`) — the `c1879600` pass
updated the prose it touched and left the rest. So the file is currently inconsistent with
itself.

**(b) The real gap: nothing pins the glue-level convention.** The choice of `h[n]` over
`h[n-1]` and `n+1` over `n` lives entirely in `WPoARandaoSelectionSeed`
([randao_accumulator.cpp:195](../../src/wpoa/randao_accumulator.cpp#L195)):

```cpp
uint256 hn = pindexTip->GetBlockHash();
RandaoAccumulator::DeriveSeed(rtot.begin(), hn.begin(), (uint32_t)(n + 1), seed_out);
```

That is the line `ef08074c` fixed, and **it has no test of either kind.** A future edit
reverting it to `pindexTip->pprev` and `n` would pass the entire suite. That is a genuine
coverage hole, and it is the one worth closing.

**Proposed action.** Rename `hprev` → `h_tip` throughout the test file, correct the three
stale comments, and add a functional assertion that the seed really is anchored to the tip
(§5.3). The pure-core test cases themselves need no logic change. **This is a
documentation-and-coverage fix, not the formula correction the mandate anticipated.**

### 3.2 Stale `weightsetreconciliation` / `weight-engine-reconciliation` / `weight-engine-activity` references

**Not a problem today. The one live occurrence is a deliberate regression guard, and
removing it would be a regression in itself.**

A repository-wide grep across `.sh`, `.cpp`, `.h`, `.py` and `.md` returns exactly **one**
occurrence in either functional test:

```
src/weight_engine/test/functional_test_weight_engine.sh:174
  r=$(mcli weightsetreconciliation "$ADMIN" 10 1 2>&1)
```

and its assertion is **negative** — it asserts the RPC is *gone*
(`functional_test_weight_engine.sh:170-177`, as audited):

```bash
echo "$r" | grep -qiE 'method not found|unknown command|help' \
  && ok "weightsetreconciliation is gone (R_k is chain-derived)" \
  || bad "weightsetreconciliation still exists: $r"
```

Lines 179–183 do the same for the two streams. This is correct and intentional: it pins the
removal that [adr/reconciliation-onchain.md](../adr/reconciliation-onchain.md)
decided. **Keep both, unchanged.**

Every other hit is prose *explaining* the removal (the CHANGELOG, the ADR,
`protocol-parameters.md`, `weight_streams.h:73-74`, `weight_reader.h:28,244-246`,
`weight_records_tests.cpp:410-412`). All historically accurate.

Line-by-line verification of the current payload model in both scripts: **no test publishes
or expects `tau`, `reconciled` or an `epoch` field on a reconciliation payload**, because no
such payload exists in either file. The stream-count assertion is already
`-eq 2`, with a comment naming the reason
(`functional_test_weight_engine.sh:87-89`, as audited).

**One real defect found, and it is cosmetic.** The script's own header still says *"the
**three** input streams are auto-created"*
(`functional_test_weight_engine.sh:6`, as audited) while the
assertion at line 88 correctly demands two. Header comment vs. code, in the same file.
Also line 3 still describes the module as *"WeightEngine publish side (admin
attestations)"*, which is the pre-ADR model. Both are one-line fixes.

### 3.3 Epoch-scoped `weightverifyweights` / `mc_VerifyPublishedWeights`

**Confirmed present in the production code, confirmed covered at unit level, confirmed
uncovered at functional level. Your concern about false negatives is well founded but the
existing tests do not currently trip on it.**

The production semantics are exactly as you describe. `ThreadWeightEngine` verifies `e-1`
while the tip is in `e` ([weight_engine.cpp:361](../../src/weight_engine/weight_engine.cpp#L361)):

```cpp
if (epoch >= 2 && (epoch - 1) != last_verified_epoch)
{
    ...
    if (WeightEngineVerifyAndCacheEpoch(reader, epoch - 1, published, published_epochs))
```

and `mc_VerifyPublishedWeights` returns `MC_WEIGHT_VERDICT_OTHER_EPOCH` for any record whose
`published_epoch != epoch`, including `0`
([weight_verifier.h:247-253](../../src/weight_engine/weight_verifier.h#L247)). `other-epoch`
is **not** invalid: `mc_WeightVerdictIsInvalid` returns true only for `MISMATCH` and
`NOT_A_CLUSTER` ([weight_verifier.h:196](../../src/weight_engine/weight_verifier.h#L196)).

**Unit coverage is thorough** — five cases in `weight_verifier_tests.cpp` assert
`OTHER_EPOCH` (lines 265, 288, 307, 325, 344), plus the string round-trip (406) and the
not-invalid property (413). Those are the "fake maps" cases the mandate refers to.

**Functional coverage is effectively nil.** The only functional touch is
`functional_test_weight_engine.sh:228-231` (as audited):

```bash
r=$(mcli weightverifyweights 2>&1)
echo "$r" | grep -qE '"epoch"|weight engine is disabled'
```

It asserts the RPC *answers*. It does not read a single verdict. So:

- **No existing functional test assumes instantaneous current-epoch verification**, which
  means no false negative exists today. Your hypothesis describes a real hazard, but the
  hazard has not been realised — the existing assertion is too weak to be wrong.
- **The weakness is the finding.** On this single-node chain with `-weightepochlength=4`,
  `getblockchainparams`-level arithmetic puts the first verification at height ≥ `2·4+5 = 13`,
  which the run does reach — so a real assertion is available and simply is not made.

**Proposed action.** Strengthen this assertion, and cover the epoch cycle properly in the
new large-network test (§5.3, §6). Chosen level: **functional**, because the unit level is
already saturated and what is unproven is precisely the *node-level* epoch bookkeeping
(`last_verified_epoch`, the `epoch >= 2` gate, `WeightEngineGetVerdicts`'s
single-epoch cache) that a fake map cannot exercise.

### 3.4 The `setup-first-blocks` floor — the formula in the mandate is not the one in the code

**The floor exists and is enforced. But it is `epoch + 9`, not `epoch + MC_WEIGHT_SETUP_PUBLISH_MARGIN`.**

The authoritative implementation is `mc_MultichainParams::AdjustSetupFirstBlocks`
([params.cpp:1257](../../src/chainparams/params.cpp#L1257)):

```cpp
first_computable = epoch + MC_WEIGHT_DEFAULT_STABILITY_MARGIN - 1;   // epoch + 5
required         = first_computable + MC_WEIGHT_SETUP_PUBLISH_MARGIN + 1;  // + 4
```

With `MC_WEIGHT_DEFAULT_STABILITY_MARGIN = 6` and `MC_WEIGHT_SETUP_PUBLISH_MARGIN = 3`
([weight_streams.h:148,158](../../src/weight_engine/weight_streams.h#L148)):

$$\text{floor} = \text{epoch\_len} + 6 - 1 + 3 + 1 = \text{epoch\_len} + 9$$

The `+1` is load-bearing, and the header explains why: *"Setting the floor at exactly
epoch+margin puts the confirming block at the first wPoA height, which cannot be produced
without the registry it would populate."*

Three gating conditions, all from the caller, not from `params.dat`: the weight engine on,
wPoA **selection** on, and **the genesis path only** (`init.cpp:1810`, inside the
`Build()` block — the last moment before the parameter hash is taken). On an existing
chain `AppInit2` only warns ([init.cpp:3683-3697](../../src/core/init.cpp#L3683)).

**Numbers for the new large-network test, with `weight-epoch-length = 100`:**

| Quantity | Formula | Value |
|---|---|---|
| First weight computable | `100 + 6 - 1` | height **105** |
| First weight confirmable | `105 + 3` | height **108** |
| `setup-first-blocks` floor | `108 + 1` | **109** |
| First epoch buried (`e=1`) | `100·1 + 5` | height **105** |
| First verification runs (`e=2`, verifies `e=1`) | `100·2 + 5` | height **205** |
| Epoch 50 published | `100·50 + 5` | height **5005** |
| Epoch 50 **verified** (needs `e=51`) | `100·51 + 5` | height **5105** |

**Decision: do not set `setup-first-blocks` at all.** Leave it to the genesis-time
derivation and read back the effective value from `getblockchainparams`, exactly as
`functional_test_weight_engine_bootstrap.sh:97` does. A hardcoded 109 would silently rot
the moment either margin constant changes; the derivation cannot. The test will log the
effective value and assert it is `> 108`.

**Consequence for the block budget.** The mandate's "≥ 5000 blocks" is slightly short of
what "traverse 50 epochs *and verify them*" requires. The honest target is **5105 + stability
margin**, and the test will compute and log it rather than hardcode it. Budget used:
`(50+1)·100 + 6 = 5106`, driven to **5120** for slack.

### 3.5 Malus family coverage — all four kinds are already covered, in both suites

**Your premise is incorrect, and there is a terminology trap worth naming.**

The code defines **four kinds** in **two families**
([malus_record.h:74-110,153](../../src/wpoa/malus_record.h#L74)):

| Family | Kinds | Evidence |
|---|---|---|
| behavioural | `MALUS_EQUIV` (`equiv`), `MALUS_DELAY` (`delay`) | a block |
| data-integrity | `MALUS_SELF_WRITE` (`selfwrite`), `MALUS_INVALID_WEIGHT` (`badweight`) | a publishing transaction |

`mc_MalusKindIsDataIntegrity()` is the discriminator.

**`wpoa_malus_tests.cpp` covers all four.** Beyond `parse_equivocation_record` and
`parse_delay_record`: `parse_selfwrite_record` (218), `parse_badweight_record` (235),
`parse_rejects_selfwrite_without_its_fields` (252),
`parse_rejects_selfwrite_accusing_an_honest_record` (269),
`parse_rejects_badweight_without_epoch_or_value` (279),
`parse_rejects_badweight_where_the_values_agree` (292),
`parse_accepts_badweight_against_a_non_cluster` (302),
`parse_rejects_data_integrity_with_two_references` (313),
`kind_families_are_classified` (330), `points_covers_the_data_integrity_kinds` (352),
`a_proved_badweight_reduces_effective_weight_then_decays` (386).

**`functional_test_wpoa_system.sh` covers all four, passively, exactly as the mandate
wants.** `check_malus` refuses false `delay` and `equiv` reports at lines 201–206, then
refuses false `selfwrite` and `badweight` reports across a height sweep at lines 225–236,
and asserts the wire spellings are advertised at 248.

**The terminology trap.** The header comment at
`functional_test_wpoa_system.sh:19` (as audited) reads *"(both malus
families)"* — which the mandate read as "only the two original kinds". It is **correct as
written**: two families, four kinds, all exercised. I propose sharpening it to *"both malus
families, all four kinds"* to remove the ambiguity that caused this item, but **no test
change is needed.**

---

## 4. Chain parameter names — confirmed against `paramlist.h`

Both names in the mandate are **correct as given**. Verified in
[src/chainparams/paramlist.h](../../src/chainparams/paramlist.h):

| Quantity | Runtime flag | `params.dat` key | `paramlist.h` | Default | Range |
|---|---|---|---|---|---|
| RANDAO lookback `k` | `-wpoarandaolookback` | `wpoa-randao-lookback` | L188 | `MC_WPOA_DEFAULT_RANDAO_LOOKBACK` = 1 | `0..1000000`; **`>= 1`** when sortition is on |
| Feedback damping `lambda` | `-weightlambda` | `weight-lambda` | L249 | `MC_WEIGHT_DEFAULT_LAMBDA` = **0.5** | `[0, 1)`, strict |
| Epoch length | `-weightepochlength` | `weight-epoch-length` | L237 | `MC_WEIGHT_DEFAULT_EPOCH_LENGTH` = 100 | `[1, 1000000]` |
| Treasury | `-weighttreasuryaddress` | `weight-treasury-address` | L253 | *(empty → `R_k = 0`)* | a valid address, or empty |

Notes that bear on the new test:

- `lambda` is a **string-valued** parameter parsed with NaN/Inf-safe checks
  ([init.cpp:3624-3628](../../src/core/init.cpp#L3624)); `lambda < 1` is enforced at
  flag-parse time as a correctness requirement (Prop. *positività-peso*).
- `MC_WEIGHT_DEFAULT_LAMBDA` is defined in `weight_streams.h:130`, **not** in
  `weight_engine.h` as the mandate's phrasing suggests. `weight_engine.h:500` only declares
  the extern.
- `k > weight-epoch-length` (i.e. `k = 101` with `epoch = 100`) is **legal** — the range
  admits it and no init check couples the two. But see §7.2: it is worth confirming this is
  what you intend, because it is an unusual regime.
- All four are consensus-critical. They belong in `params.dat`, not on the command line —
  `FL_PARAM_OVERRIDES` is the mechanism
  (`functional_lib.sh:244`, as audited), and
  `functional_test_weight_engine_bootstrap.sh:64-73` documents precisely why.
  `-weighttreasuryaddress` is the exception, by necessity: the address does not exist until
  the genesis node has a wallet, so it arrives as a runtime flag on every node (§5.2).

---

## 5. Decisions on the restructuring

### 5.1 Where the functional tests go, and what stays behind

**Adopted as specified in the mandate**, with one addition.

```
test/
└── functional/
    ├── lib/functional_lib.sh
    ├── weight_engine/
    │   ├── functional_test_weight_engine.sh
    │   ├── functional_test_weight_engine_bootstrap.sh
    │   └── functional_test_weight_engine_large_network.sh   (new)
    ├── wpoa/
    │   ├── functional_test_wpoa_system.sh
    │   └── analyze_distribution.py          ← the addition
    ├── README.md                            ← the addition
    └── run_functional_tests.sh
```

`analyze_distribution.py` moves too. It is invoked *by* `functional_test_wpoa_system.sh`
(`check_distribution`) and has no other consumer; leaving it in `src/wpoa/test/` would
split one test across two trees for no gain.

**After the move, `src/weight_engine/test/` holds exactly** the four `.cpp` files,
`run_unit_tests.sh`, and `experimental/` — as mandated. **`src/wpoa/test/` holds** the six
`.cpp` files, `run_unit_tests.sh`, `run_all_tests.sh`, and `README.md`.

**`run_all_tests.sh` is kept as an aggregator** and re-pointed at
`test/functional/run_functional_tests.sh`. It is the only entrypoint that runs everything,
and its unit-first-then-functional sequencing with `CONTINUE_ON_UNIT_FAIL` is worth
preserving. Its location in `src/wpoa/test/` becomes slightly arbitrary once the functional
tests leave, but moving it would break the muscle memory recorded in five documents for no
functional benefit. **No symlink** — a symlink would be invisible in `git log --follow` and
adds a failure mode on checkout for zero clarity.

### 5.2 Build system: nothing to update, and that is worth stating explicitly

**This is the single most important finding for the mechanics of the move.**
`Makefile.am`, `configure.ac` and the `*.mk` files contain **zero** references to either
test directory. Verified:

```
grep -rn "wpoa/test\|weight_engine/test\|functional_lib\|functional_test\|run_unit_tests" \
     --include=Makefile.am --include=*.mk --include=configure.ac .
→ (no output)
```

The unit runners do not use autotools at all. They invoke `g++` directly with
`-I$SRC_DIR`, resolving sources through `$SCRIPT_DIR`
([wpoa/test/run_unit_tests.sh:100](../../src/wpoa/test/run_unit_tests.sh#L100)). So:

- **Moving the `.sh` files cannot break the `.cpp` builds**, because the `.cpp` files do not
  move and the runners locate them relative to themselves.
- The autotools question in the mandate has an empty answer: there is no `Makefile.am`
  change to make, in either direction. That also settles the "move vs. symlink" trade-off
  on build-system grounds — **there is no build-system cost either way**, so the decision
  rests on clarity alone, and moving wins.
- There is **no CI** in this repository (`.github/workflows`, `.travis.yml`, `.gitlab-ci.yml`
  all absent), so no pipeline to update.

**Documentation references that must be updated** (found by recursive grep, not from
memory):

| File | Lines |
|---|---|
| `src/wpoa/docs/testing.md` | 55, 56, 358, 368–372, 380, 381 |
| `src/wpoa/README.md` | 415, 416 |
| `src/wpoa/docs/phase1-implementation-guide.md` | 101 |
| `src/wpoa/docs/phase2-implementation-guide.md` | 125, 601, 652, 656, 659 |
| `src/wpoa/docs/phase3b-implementation-guide.md` | 155, 629, 650, 654 |
| `src/wpoa/docs/phase4-implementation-guide.md` | 164, 457 |
| `src/wpoa/docs/malus-registry.md` | 401 |
| `src/weight_engine/test/weight_records_tests.cpp` | 420 (comment) |
| `src/wpoa/test/README.md` | whole "Layout" section |

**`src/wpoa/docs/root-cause-report.md` is deliberately excluded** (lines 28, 60, 61, 96,
388, 389, 394, 413, 493). It is a dated forensic report that cites `functional_lib.sh:233`
and similar *line numbers as they were at diagnosis time*. Rewriting its paths would make
it cite a file whose line numbers no longer mean what the prose says. A historical document
should age, not be retconned. I will add one dated note at its head instead.

`src/weight_engine/` has **no README.md** — the mandate asks to update it. I propose
creating a short one that points at the new tree, since a reader arriving at the module has
nowhere to look today.

### 5.3 `functional_lib.sh` consolidation

`functional_lib.sh` is already well factored and already shared by
`functional_test_wpoa_system.sh` and `functional_test_weight_engine_bootstrap.sh`. The
**duplication is confined to one file**: `functional_test_weight_engine.sh` reimplements
its own `mcli` (line 47), `say`/`ok`/`bad` (41–43), RPC-up polling (67–73), `first_addr`
(48) and `cleanup` (51).

**Decision: consolidate, but conservatively.** That script is a *single-node* test that
creates its chain directly with `multichain-util`, while `fl_start_network` is a
multi-node bootstrap with a grant/rejoin dance. Forcing it through `fl_start_network` would
change its behaviour, which the mandate forbids. Instead:

- Add a `fl_start_single_node` to the library, factored out of the script's existing
  lines 54–77 **verbatim**, and a `fl_cli`-compatible shim so the script keeps its exact
  assertion semantics.
- Keep `PASS`/`FAIL` counting as-is in that script rather than converting it to
  `fl_check_begin`/`fl_check_end`: the conversion would alter its output contract and its
  exit-code behaviour for no test-coverage gain.
- Move the shared bits that *are* identical (`is_txid`, the request-JSON stripping) into the
  library.

New library helpers the large-network test needs (§6): `fl_native_balance`,
`fl_refuel_node`, `fl_epoch_at_height`, `fl_verify_verdicts`, `fl_proposer_tally`.

### 5.4 Stream creation ordering (mandate point 4)

`EnsureStreamReady()` is called by `ThreadWeightEngine` **before** the epoch gate
([weight_engine.cpp:294](../../src/weight_engine/weight_engine.cpp#L294)), and
`EnsureInputStreams()` immediately before it (line 277). The deadlock is fixed in the node.

Two tests create or grant streams manually. **Both should stay, and for different reasons:**

- `functional_test_weight_engine_bootstrap.sh:161-167` grants
  `weight-engine-membership.write` and `high1` explicitly. These are **permissions, not
  creations** — the node auto-creates the streams but deliberately grants nothing, so
  without these grants no input ever reaches the pipeline. Required.
- `functional_lib.sh:285-301` (`fl_grant_weights_write`) waits for `wpoa-weights` to appear
  and then re-issues the write grants. Its own comment explains the race it covers (a grant
  landing before the create confirms). With `EnsureStreamReady` the initial grant now
  usually sticks, but the re-issue is a cheap safety net **and** a passive assertion that
  the stream appears at all — it logs a warning if it does not. Required.
- `functional_test_weight_engine.sh:108-110` grants write on both input streams after
  observing them auto-created. This is **exactly the automatic-creation path under test**
  (assertion 1 at lines 80–89). Required.

**No removals proposed.** Every manual step I found is either a permission the node does not
grant itself, or an assertion about the automatic creation.

---

## 6. The new large-network test — and the one place the mandate cannot be implemented as written

### 6.1 Parameters

| Knob | Env override | Default | Source of the choice |
|---|---|---|---|
| Miners | `WE_LARGE_MINERS` | 10 | mandate |
| Companies (non-miner) | `WE_LARGE_COMPANIES` | 20 | mandate |
| Certification Authorities | `WE_LARGE_CAS` | 2 | mandate |
| Admin / genesis | — | 1 | mandate |
| `weight-epoch-length` | `WE_LARGE_EPOCH_LEN` | 100 | mandate (`>= 100`) |
| Epochs traversed | `WE_LARGE_EPOCHS` | 50 (`--fast` → 5) | mandate |
| `wpoa-randao-lookback` | `WE_LARGE_LOOKBACK` | 101 | mandate (`k > epoch_len`) — see §7.2 |
| `weight-lambda` | `WE_LARGE_LAMBDA` | 0.2 | mandate (system default is 0.5) |
| `setup-first-blocks` | *(unset)* | derived → 109 | §3.4 |
| Total blocks | *(computed, logged)* | 5120 | §3.4 |
| Refuel threshold | `WE_LARGE_GAS_FLOOR` | see §6.2 | mandate |

`--fast` keeps 100 blocks/epoch and every structural constraint, reducing only
`WE_LARGE_EPOCHS` to 5 → 615 blocks.

### 6.2 **The GAS problem — this contradicts the mandate and needs your decision**

> The mandate says: *"Monitorare il saldo di unità GAS (**la valuta nativa**) di ogni nodo."*

**On this chain, as configured by every existing test, the native currency does not exist.**

`initial-block-reward` defaults to **0**
([paramlist.h:267](../../src/chainparams/paramlist.h#L267)). The repository states the
consequence in three places, most explicitly in
[experimental/docs/experiment.md §6.5](../../src/weight_engine/test/experimental/docs/experiment.md):

> *"A default MultiChain has `initial-block-reward = 0`, so there is no spendable native
> currency. GAS is therefore a purpose-issued **divisible asset** […] Nothing in the model
> depends on the asset-versus-native choice; **only the word 'native' does.**"*

So "GAS, the native currency" names two different things in this repo: the **modelled** GAS
(an issued asset, in `experimental/`) and the **actual** native currency (which is zero
everywhere). Two consequences, and the second is the serious one:

**(a) The refuel requirement is unimplementable as written.** With no native currency,
`getbalance` is 0 on every node forever and the admin has nothing to send. A refuel loop
over the native currency would be a no-op with a misleading log.

**(b) Without native currency the 50-epoch feedback loop measures a constant.** This is the
part worth your attention. `ComputeEpochFacts` derives `credits`, `debits` **and `R_k`**
from `txn.vout[ov].nValue` — **native** values
([weight_reader.cpp:618,622](../../src/weight_engine/weight_reader.cpp#L618)). With no native
currency:

```
credits = debits = R_k = 0  →  Gain = 0  →  saldo = 0
RestitutionRate(0, 0) → 0          (weight_engine.h:295-300, the saldo <= 0 guard)
w_k = W_k · (rho·lambda + 1 - lambda) = W_k · (1 - lambda) = W_k · 0.8
```

A **uniform** scaling. The election is unchanged, but `rho` is pinned at 0 for every
cluster in every one of the 50 epochs. The restitution-rate feedback — the mechanism this
whole branch was built to introduce (`530357bb`) — would be **inert for the entire run**,
and `-weightlambda=0.2` vs `0.3` would be indistinguishable. The test would burn ~5000
blocks proving nothing about the thing it is named after.

**Proposed resolution (needs your confirmation — §7.1).** Enable the native currency in
this test's `params.dat`, via `FL_PARAM_OVERRIDES`:

```
initial-block-reward = <positive>     # miners earn native GAS per block
first-block-reward   = <large>        # premine to the genesis admin, to fund non-miners
```

This is a **test-configuration change only** — no production code touched, consistent with
mandate point 5. It makes all four of the mandate's requirements simultaneously achievable:
real balances to monitor, a real refuel path, `R_k != 0`, and a `rho` that actually varies
per cluster across 50 epochs.

The alternative — model GAS as an issued asset, as `experimental/` does — would satisfy the
*monitoring* requirement but not (b): asset transfers would still leave `R_k = 0`, because
the engine reads native values. I do not recommend it.

### 6.3 Refuel direction — verified safe, with one trap

The mandate is right to insist on the direction check, and I verified it.

`mc_AccumulateReconciliation`
([weight_records.h:371](../../src/weight_engine/weight_records.h#L371)) credits `R` to the
**signers** of a transaction, by the value that transaction pays **to the treasury**:

```cpp
for (signers) { if (*it == treasury) continue; r_raw[*it] += value_to_treasury; }
```

- **node → treasury**: signer = node, output = treasury ⇒ `r_raw[node] += value`. **This is
  a reconciliation.** Correct.
- **admin → node (refuel)**: signer = admin, outputs = node ⇒ `mc_ValuePaidToTreasury`
  returns 0 ⇒ nothing accumulates. **Not a reconciliation.** Correct.

**The trap.** If the treasury address *is* the admin's address — which is what
`experimental/` does ([chain_setup.py:405-408](../../src/weight_engine/test/experimental/helpers/chain_setup.py#L405))
— then a refuel transaction's **change output returns to the admin, i.e. to the treasury**,
and `value_to_treasury > 0`. It survives only because of the `*it == treasury` guard:
signer == treasury, so the credit is skipped. Safe, but it depends on a single `continue`.

**Decision: use a treasury address distinct from the admin's mining address.** The refuel
path then cannot touch the treasury at all, and the safety no longer rests on the change-output
guard. The test will assert this directly: it will snapshot `R_k` before and after a
refuel and assert it did not move.

### 6.4 Treasury flag sequencing

Adopted from `experimental/helpers/chain_setup.py:396-415`, adapted to shell rather than
transliterated. The constraint is that the address does not exist until the genesis node has
a wallet, so:

1. start the genesis node **without** `-weighttreasuryaddress`;
2. read its address; derive a dedicated treasury address (§6.3);
3. add `-weighttreasuryaddress=<addr>` to the args every node will use;
4. **stop and relaunch the genesis node with the flag** — otherwise it is the one node
   computing `R_k = 0`, and it disagrees with the network;
5. bootstrap the remaining 32 nodes, all carrying the flag.

Step 4 is the one that is easy to omit and the reason the Python harness comments on it.

### 6.5 Assertions

1. Network of 33 nodes comes up; effective `setup-first-blocks` read from
   `getblockchainparams` and asserted `> 108`; computed block target logged.
2. Chain driven to the computed height (5120 default, 615 under `--fast`).
3. **Every miner elected at least once.** Non-critical: with 10 miners over ~5000 governed
   blocks, `P(a given miner never wins) ≈ (1-p)^5000`, negligible for equal weights — but
   weights diverge as `rho` does, so a starved miner is reported with its weight share and
   an expected-count figure rather than failing the run, as the mandate asks.
4. `weightverifyweights` polled every epoch: zero `mismatch`, zero `not-a-cluster`;
   `other-epoch` counted and reported as **expected**, not as a failure (§3.3).
5. Malus: `psi == 1` and `effective == weight` for every honest node; false reports of all
   **four** kinds refused on every node (§3.5).
6. Native balance of all 33 nodes sampled per epoch; refuel below the floor, logging
   `node / balance-before / balance-after / amount / txid`; `R_k` asserted unchanged across
   each refuel (§6.3).
7. All nodes agree on the block hash at the final buried height.

### 6.6 Runner integration

`test/functional/run_functional_tests.sh` gains `--suite <name>` with
`weight-engine-large` **not** in the default set. Worth noting: the current
`run_functional_tests.sh` runs **only** the wPoA system test — the two weight-engine
functional tests are not wired into any runner at all today. The new runner fixes that,
which is a coverage gain independent of the move.

---

## 7. Open questions — resolved 2026-09-15

**7.1 The native currency (§6.2) — RESOLVED: enable it.** The large-network test enables
the native currency in its own `params.dat` via `FL_PARAM_OVERRIDES`
(`initial-block-reward`, plus `first-block-reward` to premine the genesis admin). Test
configuration only; no production code is touched, per mandate point 5. This is what makes
all four of the mandate's economic requirements simultaneously achievable: real balances to
sample, a real refuel path, `R_k != 0`, and a `rho` that varies per cluster across the 50
epochs instead of sitting pinned at 0.

Rejected: modelling GAS as an issued asset (as `experimental/` does). It satisfies balance
monitoring but leaves `R_k = 0`, because the engine reads native values — so the
restitution-rate feedback would still be inert, which is the defect that mattered.

**7.2 `k = 101 > epoch_len = 100` (§4) — RESOLVED: as mandated.** `WE_LARGE_LOOKBACK`
defaults to 101. The consequence is documented in the test itself: the seed reads
`R_tot[n-101]`, so it moves far more slowly than one epoch, and below height 101 the
lookback clamps to 0 (`randao_accumulator.cpp:211-214`). The knob stays overridable.

**7.3 The three non-defects — RESOLVED: no test change.** §3.2's
`weightsetreconciliation` call stays exactly as it is (it pins the RPC's removal); §3.5's
four malus kinds stay as they are (already covered in both suites). Only the misleading
comments are corrected: the "three input streams" header, the "publish side (admin
attestations)" header, and "both malus families" sharpened to name the four kinds.

**7.4 `experimental/` — RESOLVED: unmoved, unrenamed.** Confirmed.

**For the record:** no bug was found in production code. Every discrepancy is in a test, a
comment, or a configuration choice. Mandate point 5's stop-and-ask clause was not
triggered.

---

## 8. Commit plan, as executed

The move is separated from the content changes so each diff stays readable:

| # | Commit | Note |
|---|---|---|
| 1 | `docs(adr): record the test-restructure analysis…` | this document |
| 2 | `test: move the functional suites to a project-level test/functional` | **pure `git mv`**, zero content change |
| 3 | `test(functional): wire up the new tree — runner, shared library, references` | |
| 4 | `test(randao): name the seed inputs for the h[n]/n+1 convention, and pin it` | |
| 5 | `test(weight-engine): assert the epoch-scoped verdicts, and set the treasury` | |
| 6 | `test(weight-engine): add the large-network functional suite` | |
| 7 | `docs(adr): record the execution and the test results` | this section + §10 |

**Deviation from the plan as first written:** steps 3 and 4 of the original list ("repoint
every reference" and "consolidate the shared bash helpers") were committed **together**.
They are one unit of work — the previous commit deliberately leaves the tree broken, and
splitting "make it work" across two commits would have left an intermediate state where
the runner pointed at a library that had not yet moved its helpers. The pure-rename
separation, which is the one the mandate asked for, is intact.

Commit 2 leaves the scripts **broken on purpose** (their relative source paths still point
at the old tree) and commit 3 repairs them. That is stated in commit 2's own message.

## 9. Consequences

**Positive.** Functional tests sit where their scope says they belong. One shared library
instead of one library plus one ad-hoc reimplementation. The weight-engine functional tests
become reachable from a runner for the first time. The `h[n]`/`n+1` convention gets its
first test of any kind. `other-epoch` gets functional coverage, closing the false-negative
hazard §3.3 identifies before it can bite.

**Negative.** Twelve documents change paths. `git log --follow` is required to trace the
moved files (mitigated by using `git mv` in a commit of its own).

A first draft of this section claimed the new root-level `test/` would sit "alongside the
upstream MultiChain `src/test/`". That was wrong: **this fork has no `src/test/`** (nor the
upstream `qa/` tree — see §11). There is no ambiguity to name, and `test/functional/README.md`
says so instead.

**Neutral.** No build-system change, in either direction (§5.2). No production code change.

---

## 10. Test results

### 10.1 Unit suites — 10 of 10 pass

Run with `./src/wpoa/test/run_unit_tests.sh` and
`./src/weight_engine/test/run_unit_tests.sh`. Both compile straight from source with
`g++`; neither needs a built node, which is why they are runnable here.

| Suite | File | Result |
|---|---|---|
| `weight` | `src/wpoa/test/wpoa_weight_tests.cpp` | **PASS** |
| `malus` | `src/wpoa/test/wpoa_malus_tests.cpp` | **PASS** |
| `selector` | `src/wpoa/test/wpoa_selector_tests.cpp` | **PASS** |
| `vrf` | `src/wpoa/test/vrf_wrapper_tests.cpp` | **PASS** |
| `randao` | `src/wpoa/test/randao_accumulator_tests.cpp` | **PASS** (incl. the new `seed_operands_are_not_interchangeable`) |
| `sortition` | `src/wpoa/test/private_sortition_tests.cpp` | **PASS** |
| `records` | `src/weight_engine/test/weight_records_tests.cpp` | **PASS** |
| `authorization` | `src/weight_engine/test/weight_authorization_tests.cpp` | **PASS** |
| `engine` | `src/weight_engine/test/weight_engine_tests.cpp` | **PASS** |
| `verifier` | `src/weight_engine/test/weight_verifier_tests.cpp` | **PASS** |

`*** No errors detected` on every one. The move did not touch the `.cpp` files or the
runners' source resolution, which is why this is unsurprising — and worth recording
precisely because it confirms §5.2's claim that the move cannot break a build.

### 10.2 Functional suites — NOT RUN, and cannot be run in this environment

`src/multichaind` in this tree was linked against **Boost 1.74**; this host has **1.88 /
1.90**. The binary does not start:

```
$ ./src/multichaind --help
./src/multichaind: error while loading shared libraries:
libboost_filesystem.so.1.74.0: cannot open shared object file
```

The binaries are also dated 2026-09-10 and owned by `root`, so they predate the RANDAO
fold (`c1879600`, 09-13) and the restitution-rate change (`530357bb`, 09-14) — even if
they ran, they would not be testing this code. Rebuilding against Boost 1.90 is not a
side task for a test-restructuring change: this is a MultiChain 2.3 fork of an old
Bitcoin Core, and Boost removed APIs that vintage uses.

| Suite | Result |
|---|---|
| `wpoa` | **NOT RUN** — no runnable node |
| `weight-engine` | **NOT RUN** — no runnable node |
| `weight-engine-bootstrap` | **NOT RUN** — no runnable node |
| `weight-engine-large` | **NOT RUN** — no runnable node |

### 10.3 What WAS verified without a node

| Check | Result |
|---|---|
| `bash -n` on all six scripts + the library | clean |
| Path resolution from each script's new depth | correct (`FUNC_DIR`, `REPO_ROOT`, `SRC_DIR`, the library) |
| `run_functional_tests.sh --list`, `--suite`, `--all`, `--fast`, `DRY_RUN=1` | correct, incl. per-suite timeouts (1800 s / 28800 s / 3600 s under `--fast`) |
| `run_all_tests.sh` delegating to the project-level runner | resolves and runs end to end under `DRY_RUN=1` |
| Library epoch arithmetic vs. §3.4 | `floor(100)=109`, `buried_epoch_at(105)=1`, `(104)=0`, `height_for_buried_epoch(50)=5005`, `(51)=5105` |
| Large-suite plan output | floor 109, epoch 50 published 5005, verified 5105, target **5120**; `--fast` → 620 |
| Large-suite role array | `1 admin + 10 miner + 20 company + 2 ca = 33` |
| RANDAO log parser | correct against a synthetic derivation line (two-space separators, 64-hex operands) |
| RANDAO convention discriminator | `tip=41/max=42` passes; `tip=41/max=41` is flagged as the `ef08074c` regression |
| `weightverifyweights` verdict parser | correct tally against a synthetic 4-entry report (3 `ok` + 1 `other-epoch`) |
| Treasury-payment parser | returns `5.5` for a 2-output transaction paying the treasury 5.5 |
| `fl_lt` / `fl_is_zero` decimal comparators | correct on `0.5<1.0`, `2.0<1.0`, `10<9.5`, `0`, `5.5` |

### 10.4 How to run the functional suites where the node builds

```bash
./autogen.sh && ./configure && make          # on a host with the matching Boost
./test/functional/run_functional_tests.sh                          # the fast three
./test/functional/run_functional_tests.sh --suite weight-engine-large --fast   # ~620 blocks
./test/functional/run_functional_tests.sh --suite weight-engine-large          # 50 epochs
WE_LARGE_LAMBDA=0.3 ./test/functional/run_functional_tests.sh --suite weight-engine-large
./src/wpoa/test/run_all_tests.sh                                   # unit + functional
```

The first thing to check in a large run is the `PLAN` block: it prints the derived
`setup-first-blocks` floor and the computed block target before mining anything, so a
misconfiguration is visible in the first seconds rather than after an hour. The first
thing to check in its output is `gas_seeded` — if the admin has no native balance,
`initial-block-reward` did not take effect and every economic assertion downstream is
vacuous (the suite fails loudly on exactly that, rather than proceeding).

---

## 11. Cleanup pass — residues and structural incoherences

A follow-up sweep over the test tree, after the restructuring landed. Four classes of
finding, and one thing that was deliberately **not** deleted.

### 11.1 Dangling links the first pass missed — 7, all fixed

The reference-repointing pass in commit 3 used a regex over ``[`path`](path)`` and bare
repo-relative paths. It missed `[text](path)` where the link **text differs from the
target**, which is the shape four of the guides used:

| File | Broken link |
|---|---|
| `src/wpoa/docs/implementation-roadmap.md` | `../test/functional_test_wpoa_system.sh` |
| `src/wpoa/docs/implementation-status.md` | `../test/functional_test_wpoa_system.sh`, `../test/run_functional_tests.sh` |
| `src/wpoa/docs/phase3a-implementation-guide.md` | `../test/functional_test_wpoa_system.sh` |
| `src/weight_engine/test/experimental/README.md` | `../../../wpoa/test/functional_lib.sh` |
| `src/weight_engine/test/experimental/docs/experiment.md` | `../../../wpoa/test/functional_lib.sh`, `…functional_test_wpoa_system.sh` |

A scan over **every tracked `.md`** now reports zero unresolved relative links, outside
`/experiments` (which is out of scope and has one pre-existing broken link of its own,
`experiments/docs/pipeline/README.md → 00-fase0-…md`).

### 11.2 `qa/` — an upstream test tree that never existed here

`Makefile.am` referenced the Bitcoin Core `qa/` tree in three places, inherited at fork
time. **`git log --all -- qa/` finds zero files ever tracked**, so none of these has ever
resolved in this repository:

| Location | Status |
|---|---|
| `EXTRA_DIST` — `qa/pull-tester/rpc-tests.sh`, `qa/pull-tester/run-bitcoin-cli`, `qa/rpc-tests` | **removed.** Unconditional, and an unresolvable `EXTRA_DIST` entry makes `make dist` fail |
| `check-local` under `if USE_COMPARISON_TOOL` | **removed.** Self-contained, and enabling the conditional could only ever fail |
| `block_test.info` and the `make cov` chain below it | **annotated, kept.** `total_coverage.info` depends on it, and unpicking that chain is a coverage-tooling change rather than test-structure cleanup. A comment now says `make cov` does not work here and names `test_bitcoin_coverage.info` as the usable target |

`src/Makefile.am` needed nothing: `TESTS =` is empty and the `ENABLE_TESTS` /
`ENABLE_QT_TESTS` blocks are commented out — consistent with §5.2's finding that the unit
runners bypass autotools entirely.

### 11.3 `src/test/` does not exist — an error this ADR introduced

§9 originally said the new root-level `test/` would sit "alongside the upstream MultiChain
`src/test/`", and `test/functional/README.md` repeated it as a "not to be confused with"
note. **There is no `src/test/` in this fork.** Both are corrected; the README now states
the actual arrangement (no `src/test/`, no `qa/`, unit tests beside their modules).

### 11.4 `testing.md` had drifted

The module's principal testing document still described the pre-restructuring world:

* the layers diagram listed **five** unit suites, omitting `malus`, and showed
  `run_functional_tests.sh` as a "wrapper: timeout + QUICK" rather than a four-suite
  selector. Redrawn with both unit runners, all four functional suites, and
  `weight-engine-large` shown as opt-in;
* the shared-run check list named six checks; it is now ten (`stream_permissions`,
  `malus`, `diversity_spacing` and the new `randao_seed_convention` were missing);
* `cd ./src/wpoa/test` — a directory the script no longer lives in;
* "the system run (full)" described the runner's default as one suite, now three;
* a "prefer the wrapper" link pointed at `src/wpoa/test/README.md`, which after the split
  documents the **unit** tests. Repointed at `test/functional/README.md`;
* §7 is retitled and gains the suite table, with the old content as §7.1.

### 11.5 `experimental/` — NOT deleted, and the reason matters

It was proposed for deletion as a test that is no longer needed. It is neither.

**It is not a test.** No pass/fail contract; its product is CSVs, an `.xlsx` and a log
(§2.3). Deleting it as "a test that no longer serves" would be deleting it on the strength
of a category it never belonged to.

**It is not stale.** The RPCs it actually calls are `getallweights`,
`weightregistermembership` and `weightsetesg` — all current. Its only mentions of the
removed `weightsetreconciliation` / `weight-engine-reconciliation` /
`weight-engine-activity` are in **comments explaining the removal**, which is accurate
documentation, not dead code.

**It is load-bearing evidence.** Its README carries the result that the deployed engine
computes the documented weight — *"20/20 cells exact in `wpoa` mode"* — and
`output/*.csv` plus `output/report.xlsx` are the tracked reference data behind that claim.
An accepted ADR cites it as evidence for a design decision:
[reconciliation-onchain.md](../adr/reconciliation-onchain.md) line 34
points at `helpers/stream_writer.py` for the note that a reconciliation record could
contradict the ledger. Deleting the harness would leave that ADR citing nothing.

It also remains the behavioural reference this work adopted twice: the
`-weighttreasuryaddress` start → read → restart sequence in `functional_lib.sh` and in
both weight-engine suites is modelled on `helpers/chain_setup.py`.

**Unchanged, in place, under its original name.**

### 11.6 Observed but out of scope

`graphify-out/` carries three dated snapshot directories (`2026-09-13`, `-14`, `-15`),
15 tracked files, **19 MB**, and `graphify update` adds one per run. They are graph
tooling backups, and git history already serves that purpose, so tracking them is pure
duplication that will keep growing. Not touched here — it is neither a test file nor a
structural question about tests — but worth a `.gitignore` entry and a one-off
`git rm -r --cached graphify-out/20*`.

---

## 12. The stall, and the statistics the suites were missing

Reported from a real environment: the large-network suite **stops the chain very quickly**
and it never recovers. Diagnosed, and fixed, along with the two gaps the same report named.

### 12.1 The stall is a race, not an arithmetic error

§3.4 got the *floor* right — `epoch_len + 9`, which the node derives itself — and then
used it as though it were the whole answer. It is not. wPoA engaging is a race between two
quantities measured in different units:

| | measured in | at 33 nodes, `target-block-time` 2 |
|---|---|---|
| the chain reaching `setup-first-blocks` | blocks | 109 blocks ≈ **218 s** |
| this harness finishing the bootstrap | seconds | 8–20 s/node × 32 ≈ **256–640 s** |

The bootstrap wins. The chain sails past 109 before a single membership record exists, wPoA
takes over an **empty** weight registry, `WPoASelectProposer` elects nobody, and the chain
stops dead — reporting `0 validators, total=0`, which reads like a weight-pipeline fault
and is really a stopwatch.

The bootstrap suite never caught it because at 3 nodes and `EPOCH_LEN=10` the race runs the
other way. The failure mode only appears once the network is large enough for the mandate's
own topology, which is exactly the configuration §6 introduced.

**Three fixes, in order of how much they matter.**

1. **Parallel bootstrap** (`_fl_bootstrap_role_nodes_parallel`). The join is independent per
   node — each talks only to the seed — so only the grant pass has to be serial. Three
   phases: concurrent first launch, one serialised grant pass from node 0, concurrent
   relaunch. This attacks the cause rather than the symptom. `fl_restart_all_nodes` is
   parallelised for the same reason: 33 sequential stop/start cycles were minutes of
   degraded network during the treasury restart.
2. **A setup budget that includes the wall clock** (`fl_setup_blocks_for_network`), derived
   from the node count and `target-block-time` rather than from epoch geometry alone. Safe
   by construction: `AdjustSetupFirstBlocks` only ever *raises* `setup-first-blocks` to its
   floor and leaves a larger value untouched, so this cannot conflict with the derivation
   the mandate warns about. At 33 nodes / epoch 100 it gives **325** against a floor of 109.
   Overridable with `WE_LARGE_SETUP_BLOCKS`.
3. **An explicit readiness gate** (`fl_wait_registry_ready`), and this is the part worth
   keeping regardless of the other two. The suite now refuses to proceed until the registry
   carries validators with a **non-zero** weight — non-zero because Efraimidis–Spirakis
   cannot draw a zero-weight key (Cor. 5.4), so a registry of ten validators at 0 elects
   nobody just as surely as an empty one. If the tip reaches `setup-first-blocks` first it
   **fails with the diagnosis and the remedy**, instead of leaving a silent dead chain.

### 12.2 The suites tested structure, not distributions

The other half of the report: the suites did not perform the statistical tests the work
needs. True, and the gap was in kind rather than degree — every check was structural (did
it stall, was a verdict invalid, did a node run dry). None asked whether the **election**
was correct, which is a question about a distribution and needs a stated null hypothesis.

`test/functional/lib/we_stats.py` adds two tests, and the reason there are two is the
substance of the design:

* the **empirical chi-square** runs against *this binary* on *this run*, so it exercises
  the compiled selector, the VRF, the beacon and the weight pipeline together. Its sample
  is however many blocks were mined, which gives it **no power in the tail**: over 5000
  blocks a 0.1 %-weight validator expects 5 blocks;
* the **Monte Carlo** re-implements `ScoreFromEntropy64` and `ApplyDumping` from
  `wpoa_selector.h` and draws as many times as asked, so the tail is testable. It cannot
  catch a C++ bug — it is not running the C++. The 64-bit entropy comes from a uniform
  source rather than a VRF, which is the intended test: Prop. 5.11 requires the VRF to be
  indistinguishable from uniform, so substituting a uniform source tests the algorithm
  *above* the randomness source.

Read together they **localise** a fault: Monte Carlo PASS with empirical FAIL says the
design is right and the implementation is not. That is not a hypothetical — the negative
control below produces exactly that signature.

Also computed: Gini and normalised Shannon entropy (for weights and for proposals,
descriptive rather than verdicts — under weighted selection the target is not uniformity),
Wilson score intervals per validator, per-epoch weight dispersion, and the gas trajectory.
Scenarios cover the uniform case, a 95/4/1 skew, two zero-weight cases pinning Cor. 5.4, a
500:1 decade, **and the run's own weight vector** — the one configuration a report about
this run most needs tested at a sample size the run itself could not reach.

Standard library only, matching `analyze_distribution.py`: chi-square p-values come from a
regularised incomplete gamma implemented in the module, so it runs on a bare node host.

### 12.3 Output

`test/output/<experiment>/` per run: `report.md` and `summary.txt`, the raw observations
(`proposers.csv`, `weights.csv`, `epochs.csv`, `gas.csv`, `refuels.csv`) and the derived
tables (`montecarlo.csv`, `distribution.csv`, `concentration.csv`, `epoch_stats.csv`,
`gas_stats.csv`). The analysis re-runs over the raw files without touching a network.

Recording streams out **during** the drive loop rather than at the end, deliberately: a run
that stalls at epoch 12 still leaves twelve epochs of evidence, which is precisely the case
where the evidence matters. The data is gitignored — a fresh run supersedes the last, and
it is reproducible from the raw files — while this directory's `README.md` is tracked so it
explains itself on a clean clone.

### 12.4 Validating the statistics themselves

A statistics module nobody checks is worse than none. `--selfcheck` validates chi-square
p-values against textbook critical values (3.841/1, 5.991/2, 11.070/5, 15.507/8 → 0.05),
Gini and entropy against closed forms, Wilson bracketing, and Cor. 5.4 over 20 000 draws —
plus a **negative control**: a deliberately unweighted draw against 90/10 weights must be
rejected. Without that last one, a chi-square that could only ever pass would look exactly
like a passing test.

Registered as the `stats-selfcheck` suite, in the default set. It needs no node, which
makes it the only suite in this tree runnable on a host where `multichaind` does not build
— including the one this work was authored on.

**End-to-end verification, since the node does not run here.** A synthetic run was written
in exactly the layout the bash recorders produce, with proposers drawn by the real
algorithm: analysed **PASS**, every verdict green. A second synthetic run with proposers
drawn **uniformly**, a node at zero balance and an epoch carrying real mismatches: analysed
**FAIL**, exit 1, with `chi2 = 1767.099, df = 9, p = 0.0000` on the empirical test while
every Monte Carlo scenario still passed — the fault-localisation signature above, produced
on demand.

---

## 13. The large run crashed in the harness — 2026-09-16

### 13.1 What happened

The first real execution of `weight-engine-large` on a host with a working node got
**further than any previous attempt**, then died:

```
▶ CHECK: registry_ready_before_wpoa
  waiting for >= 5 validator(s) with a non-zero weight (timeout 650s)...
  registry ready: 11 scoreable validator(s) at height 108
  ✔ the registry carries scoreable weights with the chain still at 108 < 325
  → registry_ready_before_wpoa: PASS
...
  reached height 331.
functional_lib.sh: line 1104: from: unbound variable
```

Two separate facts, and they should not be conflated:

1. **The stall fix in §12 works.** The readiness gate reports 11 scoreable validators at
   height 108, against a setup budget of 325 — the registry was populated with 217 blocks
   of margin. Under the old geometry-only floor of 109 that margin was **one block**, and
   losing the race is what produced the dead chain. This is the first direct confirmation;
   §12 could only argue it from the numbers.
2. **The harness itself had a bug**, in the recording layer added by the same change.

### 13.2 The bug

```bash
fl_record_proposers() {
    local from=$1 to=$2 h=$from        # <-- $from is the OUTER, unset variable
```

`local` is a **builtin**, so every one of its arguments is word-expanded *before* any
assignment takes effect. `h=$from` therefore reads the caller's `from`, not the one being
declared on the same line. Under `set -uo pipefail` that is fatal.

Three properties made it expensive, and they are the interesting part:

* **`bash -n` accepts it.** It is valid syntax; only the semantics are wrong. Syntax
  checking was the only static gate this tree had, and it cannot see this class at all.
* **It only executes at the first epoch rollover.** `fl_record_proposers` is not called
  during setup, bootstrap or the readiness gate — so the failure arrives *after* the
  expensive part has already succeeded.
* **No other suite records.** `wpoa`, `weight-engine` and `weight-engine-bootstrap` never
  call it, so the whole default set passes with the bug present.

A repository-wide scan for the same pattern found **exactly one** instance, the one above.
The three apparent hits in `functional_test_wpoa_system.sh` are the safe idiom
`local cur; cur="$(...)"; cur="${cur:-0}"` — three separate commands, where the assignment
genuinely precedes the read.

### 13.3 The fix, and one more defect found while fixing it

`fl_record_proposers` now declares and assigns separately, and takes each row's height
**from the block object** instead of from a counter seeded at `$from`:

```bash
fl_cli 0 listblocks "$from-$to" | python3 -c '... print("%s,%s" % (b["height"], b["miner"]))'
```

The counter was a second, latent defect. `listblocks` makes no ordering guarantee, and any
mismatch between the blocks returned and the width of the requested range would have
shifted every following row — mislabelling the proposer of each block while still producing
a well-formed CSV. That corrupts a statistical result **silently**, which is strictly worse
than crashing. The regression check drives the recorder with deliberately out-of-order
blocks; a counter-based implementation gets all three rows wrong and fails it.

### 13.4 The real conclusion: the harness needed its own tests

Fixing one line does not address why it cost hours to find. The gap was structural: **the
harness had no tests of its own**, so functions that run only deep inside an expensive suite
were first exercised by that suite. The response is a new `lib-lint` suite,
[`test/functional/lib/lint_lib.sh`](../../test/functional/lib/lint_lib.sh) — **no node, about
one second, first in the default set**:

| Group | What it checks |
|---|---|
| Static | every script under `test/functional/` parses; and a targeted scan for the same-statement `local` self-reference, which nothing else can see (shellcheck is not installed here) |
| Pure helpers | the epoch geometry against known values (floor = `len + 9`; epoch 50 buried at 5005) **and as inverse functions** over 15 (length, epoch) pairs; the setup budget at or above the floor for every size tried and **non-decreasing in the node count**, since a non-monotonic budget is how the stall returns; `fl_lt` / `fl_is_zero` / `fl_is_txid` / diversity spacing |
| Recorders | every `fl_record_*` driven against **stubbed RPCs**: headers written, epoch stamped, role resolved, decimal balances preserved, `meta.json` valid; inert when recording is disabled; survivable on empty, malformed and field-less RPC answers; and heights taken from the block, not a counter |
| Contract | `we_stats.py` consumes what the recorders wrote without raising, and exits one of the documented 0/1/2; every raw file the harness writes is documented in `test/output/README.md` |

15 checks, all passing.

**Validated by negative control**, because a guard that can only pass is worth nothing. The
pre-fix function was reinstated in a scratch copy of the tree: `bash -n` still passed — the
point — while `lib-lint` failed it **twice over**, once in the static scan and once at
runtime with the user's own error text:

```
no_self_reference_in_a_single_local: FAIL
  functional_lib.sh:1114: local from=$1 to=$2 h=$from   <-- "h=$from" reads $from ...
record_proposers_does_not_crash_under_set_u: FAIL
  ✗ fl_record_proposers read an unbound variable: line 1114: from: unbound variable
```

### 13.5 Audit for the same class elsewhere

The CHECKS section of the large suite also runs only at the very end of a multi-hour run, so
it carries the same risk profile. Two sweeps:

* Every accumulator it reads (`REFUELS`, `STALLED`, `MAX_VERIFIED_EPOCH`, `VERIFY_*`,
  `EPOCH_*`, `LAST_RECORDED_HEIGHT`) is initialised **unconditionally** before the drive
  loop, so no path through the loop can leave one unset.
* A cross-file scan for reads of variables never assigned in either the script or the
  library: **0 unresolved references** across all five functional scripts.

### 13.6 Consequence

The immediate one: `weight-engine-large` can now get past its first epoch rollover.

The one worth keeping: **the harness is code, and it was the only code here without tests.**
Its most expensive functions were also its least exercised, which is exactly backwards. The
cost of `lib-lint` is about a second per run; the cost of not having it was measured in
hours of mining.

One honest limit. §12 stated that the stall fix was *diagnosed, not observed*. That is now
resolved: the readiness gate is confirmed working on a real network, at height 108 of a
325-block budget. What remains unobserved is everything **after** the first epoch — the
50-epoch coverage, the restitution feedback moving, and the statistics over real data. Those
need a full run to make any claim about.
