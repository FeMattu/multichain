# Fixes changelog — from harness findings to protocol fixes

Maps each fault the functional harness isolated on a live chain to the commit that fixed
it, the test that verifies it, and the harness simplification it made possible. Written so
the methodology chapter can be reconstructed: every row began as an observation, not as a
code review.

Branch: `fix/wpoa-cpp-bugs-and-harness-simplification`.

| Commit | Contents |
|---|---|
| `4a7f00c7` | Phase A — the C++ fixes and their unit tests |
| `7f3eb829` | Phase B — the harness realignment |
| *(this commit)* | Phase C — documentation |

---

## Summary

| # | Fault | Fixed? | Where | Test | Harness change |
|---|---|---|---|---|---|
| A.1 | `enable-wpoa` inert in `params.dat` | **yes** | `src/core/init.cpp` | functional (§A.1) | comment only |
| A.2 | stream auto-create one-shot, never retried | **yes** | `weight_reader.cpp`, `malus_registry.cpp`, new `stream_setup_state.h` | unit + functional | explicit creation **kept**, reason rewritten |
| A.3 | wPoA takes over an empty registry → chain stops | **yes** | `miner.cpp`, `wpoa_selector.cpp`, `stream_weight_registry.cpp` | unit + functional | blocking wait **removed** |
| A.4 | `grant` before `create` reports `-708`, symptom appears later | **no — by decision** | — | — | two-pass grants **kept** |
| A.5 | treasury `receive` grant lost across the restart | **partly** — warning added, parameter unchanged | `src/core/init.cpp` | functional | confirm-and-verify **kept** |
| A.6 | two malus keys emitted blank instead of their defaults | **yes** | `src/chainparams/params.cpp` | functional | keys stay profile-configurable |
| A.7 | "no pid file" | **not a fault** — the claim was wrong | — | functional | note corrected |
| A.8 | double very close to 1 renders as `0` in JSON | **no — by decision** | — | — | harness recomputes the value |

---

## A.1 — The `enable-wpoa` master switch was inert in `params.dat`

**Observed.** A chain created with `enable-wpoa = true` and `enable-weight-engine = true`
written into `params.dat` refused to start:

```
Error: weight-engine: -enableweightengine requires the wPoA weights stream (-enablewpoaweights).
```

naming a flag the operator never touched.

**Cause.** `AppInit2` read only the six per-phase keys and never `enablewpoa`. The master
expanded only in `mc_MultichainParams::Read`, i.e. only when it arrived as a flag to
`multichain-util create`. In the file it was parsed, hashed, echoed by
`getblockchainparams` — and had no effect.

**Fix** (`4a7f00c7`, `src/core/init.cpp`). The in-file master now expands to every phase
still at its default, including malus. A phase the file turns **on** is explicit and wins;
the expansion only ever adds. Command-line behaviour is untouched.

**Verified.** A chain with only `enable-wpoa = true` starts, logs
`[wPoA] params.dat sets enable-wpoa=true: expanding the master switch ...`, and runs the
weight engine. Functional rather than unit: the code is inside `AppInit2`, which cannot be
compiled node-free.

**Limitation, documented not fixed.** A phase written explicitly as `false` next to a true
master is indistinguishable from an absent one — `params.dat` carries no "was this key
present" bit. Such a file is self-contradictory and the master wins.

**Harness.** No change. The profiles still write all eight keys explicitly, which keeps
`params.dat` a complete statement of what the chain runs.

---

## A.2 — Stream auto-creation was one-shot and never retried

**Observed.** A single admin node, left mining for 75 s, reported only:

```
root
weight-engine-esg
```

`wpoa-weights` and `weight-engine-membership` never appeared, and `getallweights` returned
`{"validators": 0, "total": 0, "weights": {}}` for ever. Nothing in the log said why.

**Cause.** `weight_reader.cpp` and `malus_registry.cpp` latched `create_attempted = true`
**before** the `create` call. A throw — no `create` permission yet, no spendable output
yet, both transient — was therefore remembered as success. `stream_weight_registry.cpp`
already did this correctly, which is how the three copies came to disagree.

**Fix** (`4a7f00c7`). One pure state machine, `src/wpoa/stream_setup_state.h`, now used by
all three: it latches only on a real broadcast, bounds retries at
`MC_WPOA_STREAM_SETUP_MAX_FAILURES = 20`, logs every failure with its attempt count, and
can `ReArm()` if a broadcast never confirms.

**Tests.** `src/wpoa/test/wpoa_activation_tests.cpp` — `fresh_state_acts`,
`a_failed_attempt_is_retried_not_remembered_as_done`, `a_real_broadcast_latches`,
`retries_are_bounded_then_give_up`, `re_arming_recovers_a_broadcast_that_never_confirmed`,
`broadcast_outranks_the_failure_count`, `zero_resets_everything`. The second fails on the
old logic (demonstrated against a transcription of it).

**Verified functionally.** All four streams now exist where only one did.

**Harness.** Explicit stream creation **kept**, with the justification rewritten. It is no
longer a workaround: the harness grants per-stream permissions in the very next step and an
entity permission cannot precede its entity, so relying on the auto-create would make that
ordering depend on when the engine thread next ticked. Fine in practice, but a timing
dependency in the one part of a measurement harness that must not have one. The
informative stream has to be created here regardless — the node knows nothing about it.

---

## A.3 — wPoA took over an empty registry and the chain stopped

**Observed.** A clean single-node chain with `setup-first-blocks = 25` produced blocks to
height 24 and stopped. No error, no crash; the log simply ends.

**Cause.** A circular dependency. At `setup-first-blocks` the height says wPoA governs.
The engine cannot publish a weight until an epoch is *buried*; an epoch cannot bury without
blocks; once wPoA governs, blocks come only from whoever the registry elects. With an empty
registry `SelectProposer` returns `""`, the miner sleeps an hour, and the epoch that would
have produced the first weight never arrives.

`AdjustSetupFirstBlocks` raises the floor so the *geometry* allows a weight to confirm in
time, but a floor is a height: it cannot know whether the engine had `create` permission,
whether anyone registered membership, or whether a CA ever certified a score.

**Fix** (`4a7f00c7`). Activation is deferred to the first **positive** weight. While the
registry has never carried one, both mining branches (private sortition at
`miner.cpp:1148`, Phase-2 selection at `miner.cpp:1199`) hand the round to the native
MultiChain scheduler, and the mining-diversity gate stands down with them so the bootstrap
window behaves exactly as if wPoA were off. The latch flips once and never flips back:
afterwards, "no validator eligible" is a legitimate outcome of a weighted sortition and the
chain halting is correct — logged loudly, not routed around.

**A wrong first attempt, worth recording.** The first implementation derived activation
from the chain *inside* `WPoAActiveAtHeight`. That predicate is also the mining-diversity
permission hook, so the wallet read happened under locks the permission check already held:
the node hung at height 24 — precisely the height the change was meant to rescue. The latch
is therefore a plain bool, set from `StreamWeightRegistry::ReadAllRecords`, the one read
path every weight consumer already goes through.

**Tests.** `no_proposer_and_never_activated_falls_back_to_native`,
`no_proposer_after_activation_does_not_fall_back`, `a_proposer_is_always_used`,
`the_latch_is_the_only_thing_that_separates_the_two_cases`. The first two fail on the old
rule.

**Verified functionally, both halves.** A chain with an empty registry passed
`setup-first-blocks = 25` and kept producing (heights 29, 33, `validators = 0`); a full
harness run logged
`[wPoA] ACTIVATED: the registry now carries a positive weight (... confirmed in block 26)`
and went on to measure 19 epochs of weighted election.

**Harness.** The blocking wait for a usable registry was **removed** — it existed to turn
this deadlock into a diagnosed failure, and the deadlock can no longer happen. Replaced by
a non-blocking observation during bootstrap and a post-run `check_wpoa_activated`, so the
*other* reason the registry might stay empty (membership never registered, no ESG ever
certified, engine thread stuck) is still reported. Nothing became silent.

---

## A.4 — `grant` before `create` reports `-708`, and the symptom surfaces later

**Observed.** `grant <addr> wpoa-weights.write` issued before the stream existed failed
with `-708 Entity with this name not found`. When that error was not noticed, the next
visible failure was `-704 lacks write permission` on `weightregistermembership`, several
steps later, naming a different command and a different stream.

**Not fixed, by decision.** The ordering requirement — create the entity, then grant on it
— is ordinary MultiChain behaviour, and `-708` is an accurate description of what happened.
The only candidate change was to append a hint to the error text, and that text is part of
the RPC surface: tools parse error strings, and MultiChain's error taxonomy is shared far
beyond this subsystem. The risk of breaking an unrelated consumer outweighs the benefit of
a friendlier message for one call site.

**Documented instead** in `docs/weight-engine.md` §5bis, with the required order and with
the misleading downstream symptom named explicitly, since that is the part that costs time.

**Harness.** Two-pass grants **kept** — global permissions before the peers launch,
per-stream permissions after the streams exist. The ordering is a real requirement and did
not change.

---

## A.5 — The treasury's `receive` grant died with the admin restart

**Observed.** 96 consecutive `sendfrom` failures with `-704 Destination address doesn't
have receive permission`; no restitution recorded; `R_k = 0` for every cluster. The run
otherwise looked healthy, and a flat `rho` reads as an inert feedback channel rather than
a broken permission.

**Cause.** `weight-treasury-address` is hash-enforced, so it is installed by restarting the
nodes with the flag. The `receive` grant on the treasury had been broadcast but not yet
mined when the restart happened, so it died in the mempool with the node.

**Partly fixed** (`4a7f00c7`). The node now warns at startup when the configured treasury
does not hold a confirmed `receive`.

**Not made runtime-settable, by decision.** `R_k` is defined as the value paid to *that*
address, so two nodes holding different values compute different weights and fork. Moving a
hash-enforced quantity outside the hash to close a sequencing hazard would be a larger hole
than the one it closes.

**Documented** in `docs/weight-engine.md` §5bis.

**Harness.** The confirm-and-verify around the treasury grant is **kept**. The node's
warning is a second line of defence, not a replacement: the harness fails fast with a
message naming the cause, which is more useful than a warning in a log nobody reads until
the results look strange.

---

## A.6 — Two malus keys were emitted blank instead of their defaults

**Observed.** A generated `params.dat` carried `wpoa-malus-selfwrite-points` and
`wpoa-malus-badweight-points` with empty values, while every other real in the group
carried its default.

**Cause.** `src/chainparams/params.cpp` seeded default strings for the other reals and not
for these two. Runtime was still correct — `ResolveWeightRealStr` falls back to the
compiled `1` and `2` — but **the parameter hash covers the stored bytes**: "blank" and "1"
are different chains. Two writers disagreeing about which to emit would fork a network
whose nodes all believed they were configured identically.

**Fix** (`4a7f00c7`). Both keys are now emitted with their compiled defaults.

**Verified.** `multichain-util create` emits
`wpoa-malus-selfwrite-points = 1` and `wpoa-malus-badweight-points = 2`.

**Harness.** No simplification taken. The two keys remain profile-configurable, because
they are genuine protocol parameters an experiment may want to vary — writing them was
never only a hash workaround.

---

## A.7 — "MultiChain writes no pid file" — the claim was wrong

**What the note said.** That MultiChain does not write a pid file, so a restart could not
wait on the process.

**What is actually true.** It does: `CreatePidFile(GetPidFile(), ...)` at
`src/core/init.cpp:1111` writes `<datadir>/<chain>/multichain.pid`, and the file is removed
on a clean shutdown. The original check had been made *after* the daemons exited, which is
exactly when the file is correctly absent.

**No fix needed.** Nothing to add.

**Harness.** The note is corrected in `node_process.py` and the lookup uses the real name.
The **RPC port stays the primary liveness signal**, deliberately: a pid file says a process
was started, but cannot say whether LevelDB has finished releasing its lock — the actual
failure mode, where a restart lands on a held lock — and it survives a crash. The pid is
what lets `stop()` escalate to a signal when the port refuses to close, which is the one
thing the port alone cannot do.

---

## A.8 — A double very close to 1 renders as `0` in JSON *(found during Phase B)*

**Observed.** With `wpoa-sortition-lambda` raised from 0 to 0.2, the harness's delay
recomputation began disagreeing with the node in 2 of 415 rounds, by exactly `delta·T·2`.

**Cause.** Not the delay. `wpoalistdelays` reported `"score_norm": 0` for an entry whose
`"delay"` was computed from the true value. Checked directly against the C++:
`PrivateSortition::NormalizedScore(8.59660332522089e-05, 400457)` returns
**0.99999999999999889**, and `MiningDelay` with the same inputs returns exactly the
reported `7.36666666666666`. The node is right.

The loss is in the writer. `json_spirit`'s `output_double_precision`
(`src/json/json_spirit_writer_template.h`) formats to 14 decimals and strips trailing
zeros; `0.99999999999999889` formats as `1.00000000000000`, every decimal strips, and the
precision collapses to 0. It affects any double whose 14-decimal rendering is all zeros
after the point.

**Not fixed, by decision.** That writer serialises **every numeric RPC in MultiChain**.
Changing its precision would alter output far beyond this subsystem and could break
existing consumers — the same reasoning as A.4, and with a much larger blast radius.

**Harness fix** (`7f3eb829`). Phase 2 now derives `score_norm` from `score` and
`total_effective_weight` — both of which render faithfully — and uses that for the delay
recomputation. The reported value is kept alongside in `score_norm` /
`score_norm_mismatch`, so the artefact stays visible as itself instead of being mistaken
for a protocol fault. `delay_recompute_mismatch_rounds` went from 2 to 0.

**Documented** in `docs/rpc-result-shapes.md`.

---

## What Phase B removed, and what replaced it

The one rule: **nothing became silent.** Every check removed because its underlying bug was
fixed had to leave an equivalent signal behind.

| Removed | Because | Replaced by |
|---|---|---|
| Blocking wait for a non-zero weight, failing the run at `setup-first-blocks` | A.3 — the node no longer takes over an empty registry, so the race cannot happen | A non-blocking observation during bootstrap, plus `check_wpoa_activated` after the run; and, in the node, the `[wPoA] ACTIVATED` line and the "no validator eligible" warning |
| Trusting the reported `score_norm` | A.8 — the field is lossy near 1 | Recomputation from `score` and `total_effective_weight`, with the reported value kept for comparison |
| The "no pid file" assumption | A.7 — it was wrong | The real path, with the RPC port still primary |

Kept, with reasons now recorded in the code rather than implied: explicit stream creation
(A.2), two-pass grants (A.4), treasury confirm-and-verify (A.5), explicit malus keys (A.6).

---

## Verification

```bash
./src/wpoa/test/run_unit_tests.sh            # weight malus selector vrf randao
                                             # sortition audit activation
./src/weight_engine/test/run_unit_tests.sh   # records authorization engine verifier epoch

./docker/mcsim run python3 test/bootstrap/bootstrap_network.py \
    --config test/config/profiles/small.yaml
```

Last full run on this branch: **PASS**, 19 measured epochs, `wpoa_activated: true`, zero
delay-recompute mismatches, all six critical consistency checks holding. The one
non-critical failure is `phi_consistent` — expected, and now informative rather than noise:
with `wpoa-sortition-lambda = 0.2` the feedback term is no longer multiplied by zero, so Φ
genuinely varies between rounds.
