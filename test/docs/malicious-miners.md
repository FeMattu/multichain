# Malicious miners and the behavioural malus

> **Register: technical-direct.** How the harness makes a chosen subset of miners
> misbehave, how an honest node proves and reports it, and how the analysis measures the
> malus that results — all without touching a single line of the C/C++ consensus core.
>
> For the protocol side of the malus (the `Valid(e)` predicate, the accumulator `M`, the
> correction `Psi`, `w_eff = w * Psi`) see [`../../docs/malus-registry.md`](../../docs/malus-registry.md).
> For the profile fields see [`../config/schema.md`](../config/schema.md#malicious-optional).

---

## 1. What can be injected, and what cannot

The protocol accepts four malus kinds. Two are proved from a **block** and its VRF reveal
(`equiv`, `delay`); two from a publishing **transaction** (`selfwrite`, `badweight`). Only
the transaction-proved pair can be produced from outside the node, because a block's
timestamp and VRF reveal are minted inside `miner.cpp` and `multichainblock.cpp` — the
consensus core this work must not modify.

So the harness implements exactly two, and the loader **rejects** a profile that asks for
the other two, naming the reason:

| Kind | Evidence | How the harness produces it | Implemented |
|---|---|---|---|
| `selfwrite` | a record on a self-attested stream whose `node_address` is not the signer | the miner publishes such a record, signed by itself, declaring a victim's address | **yes** |
| `badweight` | a `wpoa-weights` value that fails recomputation | the miner publishes a self-attested weight record for a buried epoch with a deliberately wrong value | **yes** |
| `delay` | a block earlier than its score entitles | produced in `miner.cpp` | no — core change |
| `equiv` | two blocks at one height from one key | produced in `miner.cpp` | no — core change |

Each payload is built to satisfy **exactly one** evidence predicate of
`MalusRegistry::ValidDataIntegrityReport` and to stay decodable by the same parsers the
honest readers use (`mc_ParseWeightRecordJson`, `mc_ParseMembershipRecordJson`). A
malformed record would be discarded before it reached the predicate, and the experiment
would then measure "the node ignores garbage" rather than "the node proves a specific
offence".

- **selfwrite** — `weight-engine-membership` by default (a forged record there cannot
  perturb the weight registry even for the instant before it is discarded), or `wpoa-weights`
  if the profile asks. The declared `node_address` is a real participant other than the
  signer; the record parses, and what it violates is the self-attestation rule.
- **badweight** — a `wpoa-weights` record about the miner *itself* (so it is not a
  selfwrite — the two are kept disjoint), stating a non-zero, already-buried epoch and a
  weight inflated well away from the recomputable value. It is the one implemented offence
  that *succeeds*: it enters the election until a node recomputes the epoch.

## 2. Who misbehaves, and how much

**Selection.** `malicious.miner_count` miners are drawn from a seeded shuffle of the miner
list — only miners, never a CA or a company. The draw depends on `malicious.seed` alone, so
every process that loads the profile derives the same set with no coordination, and the run
manifest records both the seed and the selected ids/addresses. An experiment where every
miner is malicious is legal; the detector then runs on the admin (§4).

**The opportunity.** The realised rate needs a denominator that is countable per
(miner, epoch) and **independent of how the miner is faring** — otherwise a miner penalised
to `Psi = 0` wins no blocks, and a win-based denominator would freeze its rate and make the
controller diverge. So an *opportunity* is exactly one event per malicious miner per epoch
of the active window: not a block, not a win, not a poll cycle. It is also the protocol's own
grain — one weight per epoch, one membership statement per epoch — so a second opportunity
inside an epoch would either repeat a record or saturate `M` within a single epoch and
destroy the decay dynamics the experiment exists to watch.

**The split.** The aggregate target `target_action_rate * O_total` is divided across the
selected miners in proportion to their **initial share of the published weight** (uniform
when no weight is available yet — recorded as such, not silently applied). A miner holding
more of the election's probability mass therefore carries more of the misbehaviour, which is
the interesting case: that is where a malus moves the distribution most.

**The controller.** Each miner runs a deficit controller on its own opportunities: at
opportunity *k* it should have attempted `rate * k` actions and has attempted `a`; it acts
with probability `clamp(rate * k - a, 0, 1)`. The expectation tracks `rate * k`, so the
realised rate converges on the target with no messaging between miners; a miner that fell
behind acts at every chance until it catches up (so a short run still lands near the
target); and the clamp at 0 stops a miner that ran ahead from being asked again, so the
target is never systematically overshot. The draw is seeded from `(seed, miner, epoch,
opportunity_index)` — the whole decision sequence is a pure function of the plan and the
epochs reached.

## 3. Timing, idempotency, logging

- **Window and order inside the epoch.** The opportunity fires *first* in the epoch, before
  the honest restitutions, and a `badweight` targets the newest **buried** epoch — the one
  the honest weight engine has already published its own weight for — so the injection
  follows the correct publication rather than racing it, and the offence is immediately
  recomputable by a detector.
- **Idempotency.** Every action has a deterministic `action_id = sha256(run, miner, epoch,
  opportunity_index, action)[:24]`, used as the stream-item **key**. Before publishing, the
  injector asks `liststreamkeyitems <stream> <action_id>`; if the action is already on
  chain (a retry, or a restart), it is not sent again. The decision itself is replayed from
  the plan, and the sent/confirmed history is replayed from the miner's own log, so a
  restarted daemon resumes exactly where it left off with no private state file.
- **Logging.** The ground truth is four event types in `events.jsonl`, via the existing
  `event_log.py`: `malicious_opportunity` (every opportunity, acted on or not — the line
  that says "no action" is what makes the denominator a fact), `malicious_action_sent`
  (broadcast, with the txid), `malicious_action_confirmed` (observed on chain), and
  `malus_detection` (the honest verdict). Each opportunity line carries the run id, epoch,
  miner, `is_malicious`, the chosen action or none, the `action_id`, the target/deficit and
  the opportunity denominator, so the realised rate is directly measurable.

## 4. The honest side: detection without ground truth

One detector process, on the **admin** node — the one node up for the whole run, funded,
subscribed to every stream, running the weight engine. It scans the two self-attested
streams and, for each confirmed item, calls the node's own `reportmalus`. It does **not**
read the malicious daemons' logs: the node's `Valid()` predicate — the same one every peer
runs — accepts a genuine offence and refuses an honest record, and the detector records
whichever verdict came back (`reported`, `refused`, or `deferred` when the epoch is not yet
recomputable). Running exactly one detector keeps every offence reported at most once, which
matters because the accumulator folds *every* valid report.

That independence is the point: the detector's verdicts and the injectors' ground truth are
produced by two parties that never talk, so comparing them measures detection rather than
bookkeeping.

## 5. What the analysis reports

Phase 1 flattens the four ground-truth event types and the plan into tables; phase 2 joins
them (funnel, per-action thread through sent → confirmed → reported, per-miner rate, the
per-epoch malus trajectory with the `w_eff` invariant recomputed); phase 3 tests:

- **rate**: target vs attempted, with a Wilson band per miner and in aggregate;
- **funnel**: opportunity → attempt → RPC accepted → confirmed → valid malus, per kind;
- **detection**: precision, recall and F1 against **confirmed** actions, plus the
  false-positive count (reports against non-malicious records — the safety property says 0);
- **latency**: detection latency in blocks (confirmation → first report) and activation
  latency in epochs (a proved malus governs selection from the epoch after, so 1 is the
  minimum);
- **weight effect**: relative change of `w_eff`, malicious vs honest, matched within an
  initial-weight band (so it reads as "penalised nodes moved relative to comparable
  unpenalised ones", not a bare before/after);
- **invariants**: `Psi in [0,1]`, `w_eff = round(w * Psi)` against an independent
  recomputation, and no proved malus ⇒ `Psi = 1` — the last of which fails the run loudly if
  the mechanism ever penalises an innocent.

The figures are `malus_action_funnel`, `malus_state_trajectory`, `malus_detection_latency`,
`malus_weight_effect`, `malus_invariant_audit`, and the weight↔election diagnostics
`p_value_uniformity`, `wilson_violation_heatmap`, `residual_boxplot_by_validator`.

## 6. Limits

- Only the two transaction-proved kinds are exercised; `delay` and `equiv` are out of reach
  without modifying the consensus core.
- One detector, so the false-positive rate is measured against a single honest observer, not
  a quorum.
- No network emulation anywhere in this harness, so nothing here speaks to latency-driven
  behaviour.
- A run may inject actions that never confirm, or confirm too late for their epoch to bury
  before shutdown; those are reported as attempted/confirmed without a valid malus rather
  than hidden, and a non-critical check flags "confirmed but never detected".

## 7. Files

| File | Role |
|---|---|
| [`../bootstrap/malicious.py`](../bootstrap/malicious.py) | Pure logic: config validation, selection, quota split, rate controller, ids, payloads, the resolved plan. |
| [`../traffic/malicious_injector.py`](../traffic/malicious_injector.py) | Drives one selected miner's opportunities from inside `miner_gas_daemon.py`. |
| [`../bootstrap/malus_detector.py`](../bootstrap/malus_detector.py) | The honest detector on the admin node. |
| [`../analysis/pipeline/stat/malus.py`](../analysis/pipeline/stat/malus.py) | Detection metrics, latency, rate convergence — closed-form, dependency-free. |
| [`../unit/`](../unit/) | Unit tests for every one of the above. |
