# `test/` — functional harness for wPoA + WeightEngine

A **functional / smoke** harness. Every node is a real `multichaind` process on localhost,
with its own data directory, its own P2P port and its own RPC port. There is deliberately
**no network emulation**: no netem, no jitter, no link delay, no CORE.

That is the design and not a limitation. It isolates the *protocol* — weight computation,
weighted selection, VRF/RANDAO, inter-epoch feedback, malus — from every network variable,
so a change in an observed quantity has exactly one candidate explanation. Network
behaviour is [`experiments/`](../experiments/)'s subject; this harness must never grow a
dependency on it, and nothing here reads from or writes to that directory.

Every chain created here runs the **complete wPoA stack**, bottom-up: weights → selection →
VRF → RANDAO → sortition → malus, with the weight engine on. That is fixed and is not a
configuration option.

---

## Quick start

The binaries are built against Ubuntu 22.04 with Boost 1.74 and do not run on the host, so
everything goes through the project's container:

```bash
# once, if src/multichaind is older than the RPC layer you want to audit
./docker/mcsim run mc-build

# one command: bootstrap -> traffic -> shutdown -> phase1 -> phase2 -> phase3 -> plots
./docker/mcsim run python3 test/bootstrap/bootstrap_network.py \
    --config test/config/profiles/native/small.yaml
```

That writes `test/results/run-<chain>-<UTC>/`, and finishes with

```
test/results/run-.../analysis/phase3/report.md               the full report
test/results/run-.../analysis/phase3/weight_vs_election.md   the headline comparison
test/results/run-.../analysis/plots/                         the figures
```

Useful variants:

```bash
# validate a profile and print the derived plan (ports, budgets, target height) — no chain
./docker/mcsim run python3 test/bootstrap/bootstrap_network.py --config <profile> --dry-run

# run the network but stop before the analysis
... bootstrap_network.py --config <profile> --no-analyze

# re-analyse a finished run without re-running the network
./docker/mcsim run python3 test/analysis/pipeline/phase1_collect.py --run-dir <run>
./docker/mcsim run python3 test/analysis/pipeline/phase2_aggregate.py --run-dir <run>
./docker/mcsim run python3 test/analysis/pipeline/phase3_analyze.py  --run-dir <run>
./docker/mcsim run python3 test/plotting/generate_plots.py           --run-dir <run>

# clean up after an interrupted run
./docker/mcsim run python3 test/shutdown/stop_network.py --config <profile> --run-dir <run>

# validate the sortition formula on its own, with no chain at all
./docker/mcsim run python3 test/analysis/pipeline/tools/valida_sortition_montecarlo.py

# check the hand-written statistics against scipy (the only place scipy is used at all)
./docker/mcsim run python3 test/analysis/pipeline/tools/verify_stat_closed_forms.py
```

Every script takes `--config <profile>`; no network or node parameter is hardcoded.

---

## Layout

```
test/
  docs/architecture-notes.md   what was read, what was decided, and why  <- read this first
  docs/RPCLIST.md              the node's full RPC reference
  config/schema.md             the profile format, field by field
  config/profiles/native/      small.yaml, medium.yaml, large.yaml, malicious.yaml, long*.yaml
  bootstrap/                   config_loader, rpc_client, event_log, node_process,
                               bootstrap_network (entrypoint), admin_daemon, ca_assign_esg,
                               malicious (experiment logic), malus_detector (honest reporter)
  traffic/                     run_company_daemons, company_daemon,
                               run_miner_daemons, miner_gas_daemon, malicious_injector
  shutdown/stop_network.py     teardown, also usable on its own
  analysis/pipeline/           phase1_collect, phase2_aggregate, phase3_analyze
  analysis/pipeline/stat/      wilson, gof, concentration, streak, timer_race, longitudinal, malus
  analysis/pipeline/tools/     valida_sortition_montecarlo.py, verify_stat_closed_forms.py
  plotting/generate_plots.py   figures, from phase 2 and phase 3 only
  unit/                        python unit tests (config, selection, controller, payloads, joins)
  results/                     run directories (not versioned)
```

Run the unit tests with `python3 -m unittest discover -s test/unit` (they need no chain).

## Roles

| Role | Count | What it does |
|---|---|---|
| admin | **always exactly 1** | creates the chain, grants every permission, creates the streams, holds the premine and funds everyone, and is the node the observer samples |
| CA | configurable, ≥ 1 | holds `high1` and publishes certified ESG scores. Without one, every cluster computes `W_k = 0` and publishes the positivity floor of 1, which makes the sortition uniform |
| miner | configurable, ≥ 1 | validator and cluster head; returns GAS to the treasury, which is the only flow that produces `R_k` |
| company | configurable, ≥ 1 | publishes informative transactions to a dedicated stream; this is what generates `tau` |

Each daemon is a **separate OS process** with its own `events.jsonl`, individually
killable and individually diagnosable.

## A run directory

```
run-<chain>-<UTC>/
  manifest.json          the profile, the derived values, the addresses, the treasury
  addresses.json         node_id -> address
  clusters.json          company -> miner, drawn from the seed
  treasury.txt           written early: the miner daemons read it at startup
  chains/<node>/         data directories and daemon.out
  logs/<node>/events.jsonl   the run's own JSON Lines log
  malicious_manifest.json    the resolved malicious plan (always written; disabled = off)
  analysis/phase1/       flat tables, one row per input record
  analysis/phase2/       candidate_long, round_level, epoch_level, epoch_engine, malus_*, ...
  analysis/phase3/       tests, consistency checks, report.md, weight_vs_election.md,
                         malus_effectiveness.md (only when the experiment ran)
  analysis/plots/        figures
```

## The three phases

Each phase may only read the output of the one before it. That is what makes a surprising
number in a report traceable back through a phase-2 row to a phase-1 row to a single line
of a node's `events.jsonl` and the RPC call that produced it.

1. **phase1** — read and normalise. No aggregation, no test. Its one job beyond copying is
   to flatten result shapes that do not agree with each other: of the audit RPCs,
   `weightlistreturns` and `weightlistbalances` map an address to a bare number, the other
   `*list*` families map it to an object, and `weightverifyweights` returns an array.
2. **phase2** — aggregate to round, epoch and cluster grain, and **recompute** the sortition
   delay from the logged inputs. `delay_recompute_mismatch_rounds = 0` is a pass condition:
   a mismatch means the harness and the node disagree about the mechanism itself.
3. **phase3** — the only phase that tests. Wilson intervals, goodness of fit, concentration,
   streaks, the timer race, the longitudinal checks and the WeightEngine feedback, the
   weight↔election diagnostics, and — when a `malicious` section ran — malus detection
   quality, latency, weight effect and the invariant audit, plus consistency checks that
   fail loudly.

Test constants are fixed in code and shared with the thesis: `alpha = 0.05`, Monte-Carlo
draws 20 000 (GoF) and 10 000 (streak), analysis seed `20260905`. They are **not** profile
fields. The profile's own seed drives the network and the traffic; these drive the tests.

## Reproducibility

One `seed` in the profile controls everything the harness decides: cluster assignment, ESG
scores, how many transactions each company sends each epoch, how they are spread in time,
restitution counts and amounts. Because the daemons are separate processes, each stream is
derived as `sha256(seed : purpose : node_id)` rather than drawn from one shared generator —
which gives the same guarantee across process boundaries.

What the seed cannot make deterministic: wallet keys, addresses, and block timing. Those
come from the node.

## Malicious miners (optional)

A profile may carry a `malicious` section that turns a chosen subset of miners into
attackers. **Without the section the run is identical to before**; with it, the selected
miners inject provable misbehaviour and an honest detector reports it, so the behavioural
malus can be measured end to end. See
[`docs/malicious-miners.md`](docs/malicious-miners.md) for the full design and
[`config/schema.md`](config/schema.md#malicious-optional) for the fields; the example
profile is [`config/profiles/native/malicious.yaml`](config/profiles/native/malicious.yaml).

```bash
# a full malicious run (10 miners, 2 malicious, rate 0.15, 50/50 mix, starts after bootstrap)
./docker/mcsim run python3 test/bootstrap/bootstrap_network.py \
    --config test/config/profiles/native/malicious.yaml
```

Two kinds are implemented, and only two are possible from outside the node:

- **selfwrite** — a record on a self-attested stream (`weight-engine-membership` or
  `wpoa-weights`) whose declared address is not the signer's. Honest readers discard it, so
  the *attempt* is the offence.
- **badweight** — a self-published `wpoa-weights` value that fails independent
  recomputation. It *succeeds* — it enters the election — until a node recomputes it.

`delay` and `equiv` are **not** implemented: they are produced inside the consensus core
(`miner.cpp` / `multichainblock.cpp`), which this harness must never modify, and the loader
rejects a profile that asks for them.

**Three states, never conflated.** An action is *attempted* (the controller decided to
act), *confirmed* (its transaction reached a block), and a *valid malus* only when an
honest node's `reportmalus` predicate accepts the evidence and publishes a report. Precision
and recall use **confirmed** actions as the positive class, because an action that never
confirmed cannot carry a malus. An **opportunity** is one countable event per malicious
miner per epoch of the active window; the realised rate is the attempts over those
opportunities.

**Limits.** Detection uses one honest detector on the admin node (so each offence is
reported at most once); with `delay`/`equiv` out of reach the mechanism is exercised on its
data-integrity kinds only; and, as everywhere in this harness, there is no network emulation
— latency-driven effects are out of scope.

**Files produced.** `malicious_manifest.json` (the resolved plan); phase-1 tables
`malicious_opportunities/actions/confirmations`, `malus_detections`, `malicious_miners`;
phase-2 tables `malus_state/actions/funnel/rate_by_miner/detection_events`; phase-3 tables
`malus_detection/rate/latency/weight_effect/invariants` and the report
`malus_effectiveness.md`; and the figures `malus_action_funnel.png`,
`malus_state_trajectory.png`, `malus_detection_latency.png`, `malus_weight_effect.png`,
`malus_invariant_audit.png` plus the weight↔election diagnostics `p_value_uniformity.png`,
`wilson_violation_heatmap.png`, `residual_boxplot_by_validator.png`.

## Things that will bite you

All of these were hit while building this, and each is explained in
[`docs/architecture-notes.md`](docs/architecture-notes.md):

- ~~**`enable-wpoa = true` in `params.dat` does nothing.**~~ **Fixed** — the master now
  expands from the file too. The harness still writes all eight keys explicitly, which
  keeps `params.dat` a complete statement of what the chain runs.
- ~~**Stream auto-creation is unreliable.**~~ **Fixed** — the three registries share one
  bounded-retry state machine. The admin still creates all four streams explicitly, because
  it grants per-stream permissions in the next step and an entity permission cannot precede
  its entity.
- **A stream permission cannot be granted before its stream exists** (`-708`). Grants come
  in two passes, global then per-stream.
- **A joining node exits on its first run** and prints the address it is waiting to have
  granted. The sequence is join → grant → launch.
- **Stopping a node and restarting it immediately fails** on the still-held LevelDB lock.
  The RPC port closing is the signal to wait for. MultiChain *does* write a pid file
  (`<datadir>/<chain>/multichain.pid`) and removes it on a clean shutdown, but a pid cannot
  say whether LevelDB has released its lock — it is used only to escalate to a signal.
- **`-maxtxfee` must be raised** with `minimum-relay-fee`, or every publish above ~500
  bytes fails with `-6 Transaction too large for fee policy` while plain transfers keep
  working — the network looks healthy and no record is ever written.
- **`mining-diversity` is binding even under wPoA.** At the stock `0.3` the round-robin
  spacing masks the weighted election entirely. The profiles ship `0`.
- **`liststreamitems` defaults to `count = 10`** and silently truncates.
- **The binary must be newer than the RPC layer you want to audit.** The round and epoch
  audit families are a recent addition; against an older `src/multichaind` every one of
  them answers `-32601 Method not found` and the analysis has nothing to work with.

## Related

- [`docs/architecture-notes.md`](docs/architecture-notes.md) — the exploration write-up,
  including how a node acquires its initial weight and why no self-publish is used.
- [`docs/fixes-changelog.md`](docs/fixes-changelog.md) — the faults this harness found in
  the protocol, the commits that fixed them, and what the harness stopped doing as a result.
- [`config/schema.md`](config/schema.md) — the profile format.
- [`../docs/protocol-parameters.md`](../docs/protocol-parameters.md) — the parameter catalogue.
- [`../docs/weight-engine.md`](../docs/weight-engine.md) — the pipeline this measures.
- [`../Create-Blockchain.md`](../Create-Blockchain.md) — the multi-node bootstrap this follows.
