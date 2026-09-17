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
    --config test/config/profiles/small.yaml
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
  config/profiles/             small.yaml, medium.yaml, large.yaml
  bootstrap/                   config_loader, rpc_client, event_log, node_process,
                               bootstrap_network (entrypoint), admin_daemon, ca_assign_esg
  traffic/                     run_company_daemons, company_daemon,
                               run_miner_daemons, miner_gas_daemon
  shutdown/stop_network.py     teardown, also usable on its own
  analysis/pipeline/           phase1_collect, phase2_aggregate, phase3_analyze
  analysis/pipeline/stat/      wilson, gof, concentration, streak, timer_race, longitudinal
  analysis/pipeline/tools/     valida_sortition_montecarlo.py, verify_stat_closed_forms.py
  plotting/generate_plots.py   figures, from phase 2 and phase 3 only
  results/                     run directories (not versioned)
```

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
  analysis/phase1/       flat tables, one row per input record
  analysis/phase2/       candidate_long, round_level, epoch_level, epoch_engine, ...
  analysis/phase3/       tests, consistency checks, report.md, weight_vs_election.md
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
   streaks, the timer race, the longitudinal checks and the WeightEngine feedback, plus
   consistency checks that fail loudly.

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
