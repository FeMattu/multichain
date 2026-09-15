# ADR — restructuring the test tree, and realigning the suites with the code

> **Status:** analysis complete, **awaiting confirmation** on four points (§7). No file
> has been moved or modified yet other than this document.
> **Scope:** `src/weight_engine/test/`, `src/wpoa/test/`, a new project-level
> `test/functional/`. Explicitly **out of scope:** `/experiments` (the Python network
> topology emulation framework) and `src/weight_engine/test/experimental/` (the MyLedger
> economic simulation harness — see §2.3).
> **Register: technical-direct.** Decision record: the inventory, the discrepancies
> verified one by one, the decisions and their consequences. Module references:
> [../../src/wpoa/docs/testing.md](../../src/wpoa/docs/testing.md),
> [../../src/wpoa/docs/weight-engine.md](../../src/wpoa/docs/weight-engine.md).
> Sibling ADRs: [../../src/wpoa/docs/adr/reconciliation-onchain.md](../../src/wpoa/docs/adr/reconciliation-onchain.md),
> [../../src/wpoa/docs/adr/randao-fold-bare-xor.md](../../src/wpoa/docs/adr/randao-fold-bare-xor.md).

---

## 1. Why this document exists

The test tree grew module by module. `src/wpoa/test/` and `src/weight_engine/test/` each
hold unit tests *and* functional tests, and the functional ones are not module-scoped at
all: `functional_test_weight_engine_bootstrap.sh` already reaches across the boundary and
sources `src/wpoa/test/functional_lib.sh`
([functional_test_weight_engine_bootstrap.sh:50](../../src/weight_engine/test/functional_test_weight_engine_bootstrap.sh#L50)).
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
([lines 170–177](../../src/weight_engine/test/functional_test_weight_engine.sh#L170)):

```bash
echo "$r" | grep -qiE 'method not found|unknown command|help' \
  && ok "weightsetreconciliation is gone (R_k is chain-derived)" \
  || bad "weightsetreconciliation still exists: $r"
```

Lines 179–183 do the same for the two streams. This is correct and intentional: it pins the
removal that [adr/reconciliation-onchain.md](../../src/wpoa/docs/adr/reconciliation-onchain.md)
decided. **Keep both, unchanged.**

Every other hit is prose *explaining* the removal (the CHANGELOG, the ADR,
`protocol-parameters.md`, `weight_streams.h:73-74`, `weight_reader.h:28,244-246`,
`weight_records_tests.cpp:410-412`). All historically accurate.

Line-by-line verification of the current payload model in both scripts: **no test publishes
or expects `tau`, `reconciled` or an `epoch` field on a reconciliation payload**, because no
such payload exists in either file. The stream-count assertion is already
`-eq 2`, with a comment naming the reason
([functional_test_weight_engine.sh:87-89](../../src/weight_engine/test/functional_test_weight_engine.sh#L87)).

**One real defect found, and it is cosmetic.** The script's own header still says *"the
**three** input streams are auto-created"*
([line 6](../../src/weight_engine/test/functional_test_weight_engine.sh#L6)) while the
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
[functional_test_weight_engine.sh:228-231](../../src/weight_engine/test/functional_test_weight_engine.sh#L228):

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
[line 19](../../src/wpoa/test/functional_test_wpoa_system.sh#L19) reads *"(both malus
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
  ([functional_lib.sh:244](../../src/wpoa/test/functional_lib.sh#L244)), and
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

## 7. Open questions — I have stopped here, as instructed

**7.1 The native currency (§6.2) — blocking.** Do you want
`initial-block-reward`/`first-block-reward` enabled in the large-network test's
`params.dat`? Without it the GAS-refuel requirement is a no-op **and** the restitution-rate
feedback is inert for all 50 epochs. This is the one item that changes what the test
measures, and it contradicts the mandate's premise that GAS-the-native-currency already
exists.

**7.2 `k = 101 > epoch_len = 100` (§4) — confirm intent.** Legal, but it means every
selection seed reads an accumulator 101 blocks stale, and for the first 101 blocks the
lookback clamps to height 0 (`randao_accumulator.cpp:211-214`). Is `k > epoch_len` the
property you want exercised, or was `k > 1` (i.e. "not the default") the intent?

**7.3 Three items where I found no defect, so I propose no fix beyond comments.** §3.2
(`weightsetreconciliation` is a deliberate negative assertion — keep it), §3.5 (all four
malus kinds already covered; "both families" is correct terminology). Confirm you are happy
with "no change" rather than the corrections the mandate anticipated.

**7.4 `experimental/` (§2.3).** I agree it should not move. Confirming explicitly because
you asked to be told if I thought otherwise.

**Not blocking, for the record:** I found **no bug in production code**. Every discrepancy
is in a test, a comment, or a configuration choice. Mandate point 5's stop-and-ask clause
was not triggered.

---

## 8. Commit plan

Per the mandate, the move is separated from the content changes so each diff stays readable:

1. `docs(adr): record the test-restructure analysis` *(this document)*
2. `test: move the functional suites to a project-level test/functional` — pure `git mv`, zero content change
3. `test: repoint every reference at test/functional` — docs, READMEs, the one `.cpp` comment
4. `test(functional): consolidate the shared bash helpers into one library`
5. `test(randao): name the seed inputs for the h[n]/n+1 convention`
6. `test(weight-engine): assert the epoch-scoped verification verdicts`
7. `test(weight-engine): add the large-network functional suite`

Steps 2–7 are **not started**; they await §7.

---

## 9. Consequences

**Positive.** Functional tests sit where their scope says they belong. One shared library
instead of one library plus one ad-hoc reimplementation. The weight-engine functional tests
become reachable from a runner for the first time. The `h[n]`/`n+1` convention gets its
first test of any kind. `other-epoch` gets functional coverage, closing the false-negative
hazard §3.3 identifies before it can bite.

**Negative.** Nine documents change paths. `git log --follow` is required to trace the moved
files (mitigated by using `git mv` in a commit of its own). A root-level `test/` appears
alongside the upstream MultiChain `src/test/`, which is a small ambiguity — the new
`test/functional/README.md` will name the distinction.

**Neutral.** No build-system change, in either direction (§5.2). No production code change.
