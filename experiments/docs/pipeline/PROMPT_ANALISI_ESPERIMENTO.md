# Prompt — Analysing one emulated wPoA run

> Paste this whole file into a fresh session opened at the repository root. It is
> self-sufficient: the temporal model, the layout, every file you may read, the schema of
> every column, the criteria and the output format are all below. You do not need to have
> read any other prompt, the pipeline code, or the thesis.

---

## 0. What you are reading, and the one thing that changes everything

The data comes from a **network emulation with real MultiChain processes**. CORE (or Linux
network namespaces) builds the topology, `tc/netem` applies delay, jitter, loss and
bandwidth, and the wPoA fork of MultiChain 2.3 runs as ordinary processes on the machine.

> **There is no Shadow simulated time in these runs.** Use wall-clock timestamps,
> monotonic durations, block timestamps and first-seen wall clock. Never compare a
> Shadow-only quantity with one measured here without stating the methodological
> difference.

The clocks you have, and nothing else:

| name | what it is | where it comes from |
|---|---|---|
| `wall_clock_time` | UTC timestamp of the observation | the system clock |
| `monotonic_time` | local monotonic reading | `time.monotonic()` |
| `elapsed_wallclock` | seconds since the run started | monotonic difference |
| `block_timestamp` | the header timestamp the miner wrote | `getblock.time` |
| `first_seen_wallclock` | first sighting of a block or transaction | the collectors |
| `last_seen_wallclock` | last sighting, across nodes | the collectors |

The manifest declares this explicitly as `temporal_model: wall_clock_emulation`. **Check
that field before anything else.** If it is absent or says anything else, stop and report
it: the run predates this contract and its timestamps cannot be read with these rules.

A consequence worth stating in your report: under Shadow the topology declared **zero
jitter**, so what decided a timer race was the 1 s quantisation of the time bar. Here the
network really does introduce latency and jitter, so a deviation from proportional
selection may have a physical cause that did not exist before. Do not carry a Shadow-era
conclusion about the cause of inversions into an emulated run.

---

## 1. Where this prompt comes from, and what it overrides

It merges two sources. Both were written for the Shadow campaign; neither is discarded.

| source | what it contributes here |
|---|---|
| `experiments/docs/pipeline/PROMPT_REPORT_ESPERIMENTI.md` | the pipeline's shape and outputs, the discipline of reading only the sheets, the rule against recomputing a statistic, the fixed report structure |
| `shadow/analisi/PROMPT_ANALISI.md` (recoverable with `git show 15009a6^:shadow/analisi/PROMPT_ANALISI.md`) | the analytical method: the weight chain, the guiding principle, vigency, the formal results to verify, the checklist, and the distinction between a simulator artefact and a protocol effect |

**Where they conflict, this is what wins and why:**

1. **Two sets of sheets, two lineages.** `PROMPT_REPORT_ESPERIMENTI` reads
   `phase3/*.csv` and writes one `report.md` per experiment;
   `PROMPT_ANALISI` reads `fogli-di-analisi/*.csv` and writes campaign reports. Both
   pipelines are migrated and both still run (`experiments/analysis/pipeline/` and
   `experiments/analysis/legacy/`). **This prompt is about one run**, so it uses the run's
   own `metrics/` and `raw/observations/`. For the campaign view across runs, use the
   phase-3 pipeline and its own prompt — do not reconstruct it here from single runs.
2. **Report format.** `PROMPT_REPORT_ESPERIMENTI` fixes five sections A–E;
   `PROMPT_ANALISI` fixes `report_generale.md` plus per-family reports. **Neither applies
   to your output**: §6 below fixes twelve sections, and that is what you write. The
   file-based reports the harness generates keep their own shapes and are inputs to you,
   not templates for you.
3. **Provenance marks.** `PROMPT_ANALISI` marks every number `[M]` measured or `[I]`
   inferred; `PROMPT_REPORT_ESPERIMENTI` has no such mark. **Four statuses win**, because
   the emulation adds a case neither source had: `observed`, `derived`, `estimated`,
   `not applicable`. `[M]` maps to `observed`, `[I]` to `derived`. The schema in §4
   carries the status of every column, so you never have to guess.
4. **Recomputation.** `PROMPT_REPORT_ESPERIMENTI` forbids recomputing any statistic;
   `PROMPT_ANALISI` is itself an analysis. **The prohibition wins for anything the
   pipeline already computed**: quote `chisq.csv`, do not recompute a chi-square from
   `proposers.csv`. Ratios of two columns in the same row are formatting, not
   recomputation. Anything needing a distribution, a fit or a simulation is forbidden —
   report the gap instead.
5. **Time.** Both sources assume simulated time. **§0 overrides both, everywhere.**
6. **Language.** `PROMPT_REPORT_ESPERIMENTI` prescribes English reports. Write in the
   language the user asks for; column names, file names and field names never change.

---

## 2. The protocol, enough of it to read the numbers

**The chain of weight** (Chapter 6). For each cluster `k` headed by a miner:

```
ESG_i, tau_i  ->  c_i = ESG_i * tau_i / kappa      per member i
W_k           =  sum of c_i over the cluster        raw cluster weight
A_k           =  alpha * Theta * W_k / W_tot        allocation from network activity
R_k           =  reconciled amount, derived from confirmed blocks
rho_k         =  R_k / A_k                          reconciliation ratio
w_k           =  W_k * (rho_{k,e-1} * lambda + (1 - lambda))    published weight
```

`tau_i` (participation) and `R_k` (reconciliation) are **derived from the confirmed blocks
of a buried epoch**, not declared: there is no stream for either, and nothing to misstate.
`ESG_i` is certified by a Certification Authority on `weight-engine-esg`; cluster
membership is self-attested on `weight-engine-membership`, and a record whose signing
address differs from the declared `node_address` is discarded by the reader.

**Vigency.** The weight computed for epoch `e` governs selection in epoch `e+1`. A share
compared against the weight published *in* the same epoch is comparing against a weight
that was not yet in force. `epoch(h) = h // L + 1`, with `L = weight_epoch_length`.

**Sortition.** Each validator draws `score_i = E_i / g(w_i)` with `E_i = -ln u_i` from a
VRF and `g` the damping function (`dumpfunction`: `none`, `sqrt` or `log`); the smallest
score wins. The score becomes a start delay
`D = T + delta*T*(2*norm - 1) + lambda*Phi`, so the winner is whoever's timer fires first —
a **timer race**. Expected share is `g(w_i * Psi_i) / sum_j g(w_j * Psi_j)`, where `Psi` is
the malus factor.

**The guiding principle.** More weight must mean a proportionally greater probability of
proposing — not a guarantee, and not a threshold. Every check below is a way of asking
whether that held.

**Setup blocks.** The first `setup-first-blocks` heights are mined before wPoA governs
selection. Epochs entirely inside that window say nothing about the protocol and must be
excluded from any statement about proportionality. A run that never clears that height
measured nothing, however many blocks it produced — check `setup_first_blocks` in the
manifest against the final height before you interpret anything.

---

## 3. The files you may read

All paths are relative to `results/<run_id>/`. Read these and nothing else: not the node
databases, not `runtime/data/`.

```
manifest.json                     the run's sealed configuration and verdict
metrics/alternanze.csv            \
metrics/block_times.csv            |
metrics/chisq.csv                  |
metrics/epoch_shares.csv           |  the historical campaign schema,
metrics/esg.csv                    |  produced by the migrated analyser
metrics/forks.csv                  |  (column names are Italian by contract:
metrics/gas.csv                    |   every archived report keys on them)
metrics/proposers.csv              |
metrics/run_index.csv              |
metrics/sortition_margins.csv      |
metrics/verify.csv                 |
metrics/weights_trajectory.csv    /
metrics/epoch_summary.csv         the emulation-native per-epoch view (wall clock)
metrics/epoch_validators.csv      expected vs observed share, per epoch and validator
raw/observations/*.csv            what the collectors saw, per node and per block
raw/rpc/                          every raw RPC answer, with a sha256 per payload
raw/events/                       harness events: controller restarts, signals
logs/<node_id>/role_controller.log   what each controller decided
logs/<node_id>/rpc.log               every RPC it made, with latency
logs/<node_id>/process.log           its view of its own daemon
logs/<node_id>/events.jsonl          the same decisions, machine-readable
reports/summary_per_epoca.md      the migrated per-epoch report
reports/summary_per_epoca_emulation.md   the wall-clock per-epoch report
reports/report_generale.md        \
reports/report_confronto.md        |  generated reports: inputs to you,
reports/report_asse_livello.md     |  not templates for your output
reports/report_asse_tbt.md         |
reports/metrics_schema_report.md  /  what the harness promises and what is absent
plots/                            the figures, and a documented reason for each absence
```

**Read `metrics/run_index.csv` first, always.** Its `stato` and `note` say whether the run
is complete, and every other number is worth less if it says `parziale`. Then read
`manifest.json → temporal_model` and `setup_first_blocks`.

---

## 4. The schema of every table

Status has four values and they are not decoration:

| status | meaning |
|---|---|
| `observed` | read directly from a node, the kernel or the configuration |
| `derived` | computed from observed values, by the formula in the source column |
| `estimated` | modelled, with assumptions that must be quoted wherever it is used |
| `not applicable` | the harness declares it absent, with the reason in the last column |

Historical tables carry the archived campaign's own column names and are documented in
`reports/metrics_schema_report.md` of each run; the tables below are the ones this harness
declares.

<!-- BEGIN GENERATED SCHEMA -->

### `metrics/run_index.csv`

One row per run: the sealed configuration and the extraction verdict.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `run_id` | observed | — | Run identifier. | the run directory name | empty |
| `livello` | observed | — | Geographic scenario. | manifest.scenario (native) or the level directory (legacy) | empty |
| `tbt` | observed | s | target-block-time. | params.dat | empty |
| `path` | observed | — | Absolute path of the run on the machine that analysed it. | the filesystem | Machine-specific by construction; it is provenance, not data. |

### `metrics/block_times.csv`

Inter-block interval inside the wPoA window against the target.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `blocchi_misurati` | derived | — | Blocks in the measurement window. | listblocks, minus setup-first-blocks | empty |
| `dt_medio_s` | derived | s | Mean interval. | differences of the block header timestamps | empty |
| `dt_sd_s` | derived | s | Standard deviation of the interval. | same | empty |
| `scarto_pct` | derived | % | Relative gap against target-block-time. | (mean - target)/target | empty |

### `metrics/proposers.csv`

Observed block share per miner against its published weight.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `blocchi` | observed | — | Blocks proposed. | listblocks, miner field | empty |
| `quota_osservata` | derived | — | Observed share. | blocks / total | empty |
| `peso_ultimo` | observed | — | Last published weight. | wpoa-weights stream | empty |
| `quota_attesa` | derived | — | Expected share. | w_i / W_tot | empty |
| `delay_medio_s` | observed | s | Mean sortition delay. | debug.log, wPoA-sortition lines | empty |

### `metrics/chisq.csv`

Chi-square of the proposer distribution against the weights.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `chi2_ricalcolato` | derived | — | Recomputed statistic. | observed vs expected counts | empty |
| `p_value` | derived | — | p-value. | scipy.stats.chi2.sf | Declared missing, never estimated, when scipy is absent. |
| `campione_sufficiente` | derived | — | Whether the minimum expected count reaches 5. | min expected >= 5 | empty |

### `metrics/epoch_shares.csv`

Per-epoch block share against the weight in force in that epoch.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `epoca` | derived | — | Epoch index. | height // weight-epoch-length | empty |
| `peso_epoca` | observed | — | Weight readable at the chain tip then. | wpoa-weights | empty |

### `metrics/weights_trajectory.csv`

Published weight per host and epoch.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `peso` | observed | — | Published integer weight. | wpoa-weights payload | empty |
| `height` | observed | — | Confirmation height of the record. | stream item | empty |

### `metrics/sortition_margins.csv`

Timer-race margin G, the Prop. 5.18 regime indicator.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `G_medio_s` | derived | s | Mean gap between the two best delays. | debug.log sortition scores | empty |
| `frazione_G_sotto_100ms` | derived | — | Fraction of rounds whose margin is under 100 ms. | same | empty |
| `rtt_max_ms` | derived | ms | Worst end-to-end RTT of the topology. | shortest path over the .gml | empty |

### `metrics/alternanze.csv`

Consecutive blocks by the same proposer, observed against expected.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `consecutivi_osservati` | observed | — | Observed runs of length >= 2. | listblocks | empty |
| `consecutivi_attesi` | derived | — | Expected from the weight shares. | sum of squared shares | empty |

### `metrics/forks.csv`

Chain consistency across nodes at the end of the run.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `teste_distinte` | observed | — | Distinct best hashes. | node_state.csv | empty |
| `hash_sepolti_distinti` | observed | — | Distinct hashes at a common buried height. | node_state.csv | empty |

### `metrics/verify.csv`

Independent recomputation of the published weights.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `verificato` | observed | — | Whether the node verified the epoch. | weightverifyweights | empty |
| `non_validi` | observed | — | Records that failed verification. | same | empty |

### `metrics/esg.csv`

Certified ESG score per host.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `esg` | observed | — | Certified score. | weight-engine-esg stream | empty |

### `metrics/gas.csv`

GAS economy: distribution, refills, reconciliation, treasury.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `gas_riconciliato_totale` | observed | GAS | Total returned to the treasury. | reconciliation.csv | empty |
| `saldo_treasury` | observed | GAS | Final treasury balance. | getaddressbalances | empty |

### `raw/observations/node_observations.csv`

Per-node RPC sample, one row per node per tick. The time series the Shadow suite could not take, because sampling inside the simulation cost simulated time.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `run_id` | observed | — | Run identifier. | the manifest | empty |
| `scenario` | observed | — | Scenario label. | the manifest | empty |
| `seed` | observed | — | Master seed. | the manifest | empty |
| `node_id` | observed | — | Node name. | the plan | empty |
| `role` | observed | — | miner | company | admin | ca. | the plan | empty |
| `organization` | observed | — | Owning organisation. | the plan | empty |
| `geographic_scope` | observed | — | regional | national | continental | intercontinental. | the plan | empty |
| `region` | observed | — | Region of the node's location. | the topology | empty |
| `country` | observed | — | Country. | the topology | empty |
| `continent` | observed | — | Continent. | the topology | empty |
| `timestamp_wallclock` | observed | ISO-8601 | UTC time of the sample. | the host clock | Comparable across machines. NOT comparable with the Shadow campaign's simulated time; see docs/metrics.md. |
| `timestamp_monotonic` | observed | s | Monotonic clock, the only one safe for differences. | time.monotonic | Does not jump when the host clock is adjusted. |
| `block_height` | observed | — | Chain height at this node. | getinfo.blocks | empty |
| `block_hash` | observed | — | Best block hash. | getbestblockhash | empty |
| `previous_block_hash` | observed | — | Parent of the best block. | getblock | empty |
| `block_time` | observed | unix s | Header timestamp of the best block. | getblock.time | empty |
| `peer_count` | observed | — | Connected peers. | getinfo.connections | empty |
| `peer_connectivity` | derived | — | 1 when the node has any peer. | peer_count > 0 | empty |
| `transaction_count` | observed | — | Transactions in the best block. | getblock.tx | empty |
| `confirmed_transaction_count` | not applicable | — | Chain-wide confirmed transaction total. | — | MultiChain exposes no chain-wide counter; summing it would mean walking every block on every tick. Left empty rather than filled with a partial count. |
| `mempool_size` | observed | — | Unconfirmed transactions. | getmempoolinfo | empty |
| `sync_lag` | derived | blocks | Blocks behind the highest node in this sample. | max(height) - height | empty |
| `rpc_errors` | observed | — | Cumulative RPC failures for this node. | the collector's own counter | empty |
| `p2p_errors` | not applicable | — | Cumulative P2P errors. | — | Not exposed over RPC. Recoverable from debug.log after the run; the column exists so a later extractor can fill it without a schema change. |
| `reachable` | observed | — | Whether the node answered this tick. | the collector | empty |
| `pending_transaction_count` | observed | count | Transactions this node holds unconfirmed. | getmempoolinfo.size | empty |
| `process_alive` | observed | 0/1 | Whether this node's daemon was running at the sample. | the process registry | Empty when the harness did not start that node's daemon itself. |
| `controller_alive` | observed | 0/1 | Whether its role controller was running at the sample. | the scheduler | Empty before the controllers start, which is the truth rather than a zero: there is none yet. A node whose daemon answers while its controller is dead stops generating traffic, and the two failures are indistinguishable in the chain data. |

### `raw/observations/block_sightings.csv`

First time each node reported each block hash. Differences across nodes are the propagation time.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `first_seen_wallclock` | observed | ISO-8601 | First sighting, UTC. | the collector | empty |
| `first_seen_monotonic` | observed | s | First sighting, monotonic. | the collector | empty |

### `raw/observations/block_propagation.csv`

Per block: how long it took to reach every node that saw it.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `block_height` | derived | — | Height of the block. | block_sightings | empty |
| `block_hash` | observed | — | Block hash. | block_sightings | empty |
| `nodes_seen` | derived | — | Nodes that reported this hash. | block_sightings | empty |
| `first_seen_monotonic` | observed | s | Earliest sighting. | block_sightings | empty |
| `last_seen_monotonic` | observed | s | Latest sighting. | block_sightings | empty |
| `propagation_time` | derived | s | Last sighting minus first, across nodes. | last_seen_monotonic - first_seen_monotonic | Resolution is the sampling interval, so it is an upper bound rather than a wire-level measurement. |

### `raw/observations/process_samples.csv`

CPU, memory and disk of every process the harness started.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `cpu_seconds_total` | observed | s | Cumulative CPU time. | /proc/<pid>/stat | empty |
| `cpu_percent` | derived | % | CPU over the interval since the last sample. | /proc/<pid>/stat utime+stime | empty |
| `memory_bytes` | observed | B | Resident set size. | /proc/<pid>/status VmRSS | empty |
| `disk_read_bytes` | observed | B | Bytes read from disk. | /proc/<pid>/io | Empty, not zero, when unreadable - which is the normal case for a process started through sudo. |
| `disk_write_bytes` | observed | B | Bytes written to disk. | /proc/<pid>/io | empty |
| `process_restarts` | observed | — | Times the harness restarted it. | the process registry | empty |

### `raw/observations/netem_conditions.csv`

The impairment actually installed, per link and direction.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `netem_delay_ms` | observed | ms | Configured one-way delay. | topology-realized.json | empty |
| `netem_jitter_ms` | observed | ms | Configured jitter. | topology-realized.json | New. The Shadow campaign carried jitter 0 everywhere, because the field was never implemented (shadow/shadow#3601). |
| `netem_loss_percent` | observed | % | Configured loss. | topology-realized.json | empty |
| `netem_bandwidth_mbps` | observed | Mbit/s | Configured rate. | topology-realized.json | empty |
| `measured_delay_ms` | not applicable | — | Delay measured on the wire. | — | Would need a probe on every link, whose own traffic would perturb the run. Configured values are reported as configured, never as measured. |

### `raw/observations/explorer_blocks.csv`

One row per block, collected by polling the admin as a block explorer. Gap-free: every intermediate height is walked.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `height` | observed | — | Block height. | getblockhash walk | empty |
| `hash` | observed | — | Block hash. | getblock | empty |
| `previous_block_hash` | observed | — | Parent hash. | getblock | empty |
| `block_time` | observed | unix s | Header timestamp. | getblock | empty |
| `observed_wallclock` | observed | ISO-8601 | When the explorer saw it. | the collector | Bounded by the polling interval: an upper bound on when the block appeared, not when it was produced. |
| `miner` | observed | — | Proposer address. | getblock.miner | empty |
| `miner_host` | derived | — | Proposer host name. | runtime/shared/*.addr | empty |
| `proposer_weight` | observed | — | The proposer's weight in the registry at that moment. | getallweights | Empty for a node with no weight - the admin during the setup phase - which is correct, not missing. |
| `total_weight` | observed | — | Sum of all weights then. | getallweights | empty |
| `size_bytes` | observed | B | Block size. | getblock.size | empty |
| `transaction_count` | observed | — | Transactions in the block. | getblock.tx | empty |
| `gap_filled` | derived | — | 1 when the block was recovered by walking a gap rather than seen at the tip. | the collector | empty |

### `raw/observations/explorer_transactions.csv`

One row per transaction of every block.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `txid` | observed | — | Transaction id. | getblock.tx | empty |
| `index_in_block` | observed | — | Position in the block. | getblock.tx | empty |
| `size_bytes` | observed | B | Transaction size. | getblock | Empty when the build returns tx as bare txids. |
| `fee` | observed | GAS | Fee paid. | getblock | Empty unless the node returns the verbose form. |
| `kind` | derived | — | coinbase or tx. | position and vin | empty |
| `from_address` | not applicable | — | Sender. | — | Resolving it needs the previous output of every input, one RPC per input per transaction. Left empty rather than filled from the wallet, which only knows its own. |
| `first_seen_mempool_wallclock` | observed | ISO-8601 | First time the explorer saw it waiting, UTC. | getrawmempool | Empty when the transaction was mined between two polls and never observed pending. |
| `included_wallclock` | observed | ISO-8601 | When the explorer saw the block carrying it. | getblock | empty |
| `inclusion_latency_s` | derived | s | Wall-clock seconds from first mempool sighting to inclusion. | included - first_seen, both monotonic | Empty, never zero, when the first sighting is missing: zero would read as instant inclusion. |
| `status` | derived | — | confirmed, once in a block. | presence in a block | empty |

### `raw/observations/explorer_chain_state.csv`

Every node's own view, every tick: the half a single explorer cannot provide.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `node_id` | observed | — | The node reporting. | the plan | empty |
| `block_height` | observed | — | Its own height. | getinfo.blocks | empty |
| `best_hash` | observed | — | Its own tip. | getbestblockhash | empty |
| `peer_count` | observed | — | Its peers. | getinfo.connections | empty |
| `mempool_size` | observed | — | Its unconfirmed pool. | getmempoolinfo | empty |
| `reachable` | observed | — | Whether it answered. | the collector | empty |

### `raw/observations/fork_events.csv`

Divergence between nodes, observed over time.

| column | status | unit | meaning | source | when missing |
|---|---|---|---|---|---|
| `fork_detected` | derived | — | 1 when nodes disagree at a buried height. | node_observations across nodes | empty |
| `fork_depth` | derived | blocks | Heights over which the disagreement persists. | same | Bounded below by the sampling interval: a fork that heals between two ticks is invisible. The epoch sampler's node_state_epochs.csv covers the coarser case. |

<!-- END GENERATED SCHEMA -->

---

## 5. What to check, in this order

1. **Completeness before interpretation.** `run_index.csv → stato/note`; the final height
   against `setup_first_blocks`; how many epochs are outside the setup window. A run that
   measured nothing is a finding, not a failure to analyse.
2. **Weighted sortition.** Expected share against observed share, per epoch and per
   validator (`epoch_validators.csv`), always against the weight **in force** in that
   epoch, never the one published in it.
3. **Chi-square, read with the small-sample caveat.** Quote `chisq.csv` and the per-epoch
   statistic. A p-value computed on expected counts below 5 must be reported as
   uninterpretable — the tables say so in their own note column. Never turn a p-value into
   "the protocol is correct".
4. **Block times, in wall clock.** Median and spread against the target, and what the
   emulated latency accounts for.
5. **Network conditions by scenario.** `netem_conditions.csv` for what was applied,
   `block_propagation.csv` for what it produced. Distinguish configured from measured.
6. **Forks and liveness.** Count, depth, resolution time; and whether the tip ever stopped
   advancing (the collector records the longest stall and its height).
7. **Transactions.** Sent, seen pending, included, confirmed — and the inclusion latency
   where the mempool sighting exists. Where it does not, say so rather than assuming zero.
8. **Height gaps and disagreement between nodes.** `explorer_gaps.csv`,
   `explorer_chain_state.csv`, `fork_events.csv`.
9. **Sync lag and connectivity**, per node and per scenario.
10. **Crashes.** MultiChain processes and role controllers are different failures:
    `raw/events/scheduler.jsonl` records restarts, `process_samples.csv` the processes.
11. **Observed against derived.** Every number you quote carries its status from §4.
12. **Statistical limits.** Number of blocks, of epochs, of validators. Three validators
    and twenty blocks cannot support a claim about a distribution, and saying so is part
    of the analysis.

**Telling an artefact from a protocol effect.** Under Shadow the suspects were the
simulator's quantisation and its zero-jitter topology. Here they are different: an
overloaded host that slows every process at once, a controller that died and was
restarted, a daemon that was still syncing, a `tc` qdisc that was not applied. Check
`process_samples.csv` for saturation and `raw/events/` for restarts **before** attributing
a deviation to the protocol.

---

## 6. The report you write

Exactly these twelve sections, in this order, with these headings.

```
1.  Sintesi esecutiva
2.  Validazione della completezza dei dati
3.  Tabella peso atteso vs blocchi osservati
4.  Analisi per epoca
5.  Analisi geografica e di rete
6.  Transazioni e throughput
7.  Fork, liveness e safety
8.  Anomalie nei log/RPC
9.  Criticità ordinate per severità
10. Raccomandazioni operative
11. Limiti e dati mancanti
12. Verdetto finale prudente
```

Rules that hold in every section:

* **Numbers, not adjectives.** Never "significant" without the figure that makes it so.
* **Every number carries its status** (`observed` / `derived` / `estimated`) the first time
  it appears, and its source file.
* **A missing datum is written as `dato non disponibile: <motivo>`** — never omitted,
  never estimated silently, never replaced by a plausible value. If the reason is in a
  table's own note column, quote that note.
* **No number appears in two sections.** Section 3 carries the per-validator table,
  section 4 the per-epoch trend.
* **Do not recompute what the pipeline computed.** See §1 conflict 4.
* **Never a figure you did not open**, never a table copied twice.
* Section 12 is prudent by construction: with a handful of validators and a few dozen
  blocks, the honest verdict is usually "consistent with, and under-powered to prove".

---

## 7. What you must not do

* Do not invent a missing value, in any section, for any reason.
* Do not read `runtime/data/`, the node databases, or any file not listed in §3.
* Do not introduce a metric the harness does not produce. A useful missing metric is
  reported in section 11 as a gap, in one line.
* Do not compare a Shadow-era number with one from this run as if they were the same
  quantity. If a comparison is worth making, state the methodological difference first.
* Do not describe the run as a simulation, and do not use `simulation_time`: it does not
  exist here.
* Do not present a structural property of the configuration as a finding of the run. A
  malus registry that is empty because no violation was staged, a damping function set to
  `none`, a single-miner topology that cannot show alternation — these are limits of the
  design, and belong in section 11.
