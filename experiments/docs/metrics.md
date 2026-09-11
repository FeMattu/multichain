# Metrics

What is measured, where each number comes from, and what it is allowed to
claim.

## The catalogue is the source of truth

`experiments/metrics/catalogue.py` declares every table and every column with
one of three statuses. `metrics_schema_report.md` is **generated from it**, so
the documentation cannot drift from the code, and
`tests/unit/test_metrics.py` asserts the catalogue matches what the collectors
actually write.

| status | meaning |
|---|---|
| `observed` | read directly from a node, the kernel or the configuration |
| `derived` | computed from observed values by a stated formula |
| **`unavailable`** | declared absent, with the reason |

The third status is the one that matters. A metric that stopped being
measurable when Shadow was replaced must not quietly become an empty column.
Three are named rather than silent:

| column | why it is absent |
|---|---|
| `node_observations.confirmed_transaction_count` | MultiChain exposes no chain-wide counter; producing one would mean walking every block on every tick. Empty, not a partial count. |
| `node_observations.p2p_errors` | Not exposed over RPC. Recoverable from `debug.log` after the run; the column exists so a later extractor can fill it without a schema change. |
| `netem_conditions.measured_delay_ms` | Measuring it needs a probe on every link whose own traffic would perturb the run. Configured values are reported as configured, never as measured. |

## Three clocks, and never mixing them

This is the single most important thing to get right when comparing a new run
with the archived campaign.

| clock | where | comparable with |
|---|---|---|
| `simulated_time` | the Shadow archive only | other Shadow runs |
| `timestamp_wallclock` | every new run | other new runs, and external events |
| `timestamp_monotonic` | every new run | **differences within one run** |

Every observation row carries both new clocks. Use `monotonic` for durations —
it does not jump when the host's clock is adjusted — and `wallclock` for
alignment with anything outside the run. Neither is comparable with simulated
time; they are different quantities, not the same quantity measured twice.

### What can and cannot be compared with the archive

**Can be.** Proposer shares, chi-square statistics, Gini and entropy, epoch
weight trajectories, alternation counts, the timer-race margin `G`,
fork counts. All dimensionless or in blocks, and they mean the same thing
either side.

**Cannot be, without saying so.**

* **Timestamps.** Different quantities.
* **Block-time means.** Both carry a bias, and they are different biases. The
  archived mean of 17.9 s against a 15 s target includes the vDSO latency
  Shadow charged to every clock call; a new run has no such term but does
  include host contention. Attributing either to the protocol's `λΦ` feedback
  without separating them is the mistake this section exists to prevent.
* **Jitter.** The archive has none anywhere — the field was never implemented
  in Shadow.

## The historical tables

Twelve, with **frozen** column names. Every archived report and every
level-to-level comparison keys on them, so columns may be appended but never
renamed or reordered — `tests/golden/test_csv_contract.py` fails if they are.

```
run_index      block_times    proposers      chisq
epoch_shares   weights_trajectory            sortition_margins
alternanze     forks          verify         esg            gas
```

They are produced by the **migrated** pipeline, not recomputed here: an
archived run and a new one must be computed by the same lines, or the
comparison between them means nothing.

## The new tables

Real execution on wall-clock time makes a time series possible where the
simulator only allowed one final snapshot, because sampling inside the
simulation cost simulated time.

| table | what it is |
|---|---|
| `node_observations.csv` | one row per node per tick: height, hash, peers, mempool, sync lag, both clocks |
| `block_sightings.csv` | first time each node reported each hash |
| `block_propagation.csv` | per block: last sighting minus first, across nodes |
| `process_samples.csv` | CPU, memory and disk of every process the harness started |
| `netem_conditions.csv` | the impairment actually installed, per link and direction |
| `fork_events.csv` | per tick: whether nodes disagree at a common buried height, and for how long |

### Two resolution limits, both declared

* **Propagation time is an upper bound.** It is measured at the sampling
  interval, not on the wire. A block that reached every node within one tick
  reads as zero.
* **Fork depth is counted in ticks, not blocks.** Between two samples the
  chain may have moved several heights, so claiming a block count would
  overstate what was observed. A fork that heals between two ticks is
  invisible here; the epoch sampler's `raw/metrics/epochs/node_state_epochs.csv`
  covers the coarser case.

## What one node can see, and what needs several

This distinction is not pedantry: deriving a multi-node quantity from a single
node is inventing it, and the result looks exactly like a measurement.

### From the explorer alone (the admin node)

The admin is subscribed to every stream and its `listblocks` reports the
proposer of each height directly, so everything about **the chain as a
sequence** comes from it:

| quantity | RPC |
|---|---|
| height, hash, previous hash, block time | `getblockcount`, `getblockhash`, `getblock` |
| proposer, and its weight at that moment | `getblock` + `getallweights` |
| block size, transaction count, the transactions | `getblock` |
| the published weight map | `getallweights` |
| mining permissions | `listpermissions ["mine"]` |
| mempool depth at the explorer | `getrawmempool`, `getmempoolinfo` |
| the streams: weights, ESG, membership, malus | `liststreamitems` |
| independent recomputation of the weights | `weightverifyweights` |

`metrics/explorer_blocks.csv` and `metrics/explorer_transactions.csv` are
built from exactly these, and every raw answer is kept under `raw/rpc/`.

### Only from aggregating several nodes

| quantity | why one node cannot answer |
|---|---|
| **fork detection** | a fork is two nodes holding different hashes at one height. One node sees one hash and calls it the chain. |
| **sync lag** | "behind" is relative to the others. |
| **block propagation** | the difference between the first and last node to report a hash. |
| **peer connectivity of the network** | each node reports its own peers; the graph is the union. |
| **partition detection** | a node inside a partition sees a healthy, smaller network. |

These come from `metrics/explorer_chain_state.csv` (every node, every tick)
and `metrics/node_observations.csv`, and are reduced into
`block_propagation.csv` and `fork_events.csv`.

**The corollary for reading a report:** any claim about forks, lag or
propagation that cites only the admin is wrong, however plausible the number.

### Two RPCs the brief named that do not exist

`getvalidatorinfo` and `getweight` are **not** in this fork — checked against
`src/rpc/rpclist.cpp`, not assumed. The weight registry is:

```
getlocalweight            this node's own weight
getnodeweight <address>   one validator's weight
getallweights             {validators, total, weights: {address: weight}}
getallmalus / getnodemalus            the behavioural malus registry
weightverifyweights       independent recomputation
weightsetesg / weightregistermembership   the two write paths
```

## Where each number comes from

```
the admin's final snapshot  ──► blocks.json, weights.json, esg.json,
  (listblocks, liststreamitems)   membership.json, verify.json, node_state.csv
                                  └─► the twelve historical tables
debug.log on every node     ──► sortition scores, Phi, rejected blocks,
                                  weight-engine folds
the sampler (RPC, /proc)    ──► the six new tables
topology-realized.json      ──► netem_conditions.csv
```

The final snapshot is the primary source, and deliberately so: `listblocks`
reports the proposer of every height directly, which is far more reliable than
parsing `debug.log`. The logs supply what RPC cannot.

## The GAS unit trap

MultiChain's RPCs return the native currency already in **display** units:
`getbalance`, the amount of `send`, `qty` of `listassets`. Every CSV the role
scripts write is a direct copy, so it is **already in GAS** and must not be
converted. Converting a second time is the error.

What *is* in raw units are the chain parameters in `params.dat`:
`first-block-reward`, `initial-block-reward`, `minimum-relay-fee`,
`maximum-per-output`. The pipeline divides those by
`native-currency-multiple`, read per run and never assumed.

## Reading a metric with confidence

1. Open `<run>/reports/metrics_schema_report.md` — generated for that run.
2. Find the column. It says `observed`, `derived` or **`unavailable`**.
3. If derived, the source column gives the formula.
4. For a timestamp, check which clock.
5. For anything compared with the archive, re-read "Three clocks" above.

```bash
python3 -m experiments.cli metrics schema                  # the whole catalogue
python3 -m experiments.cli metrics schema --format json    # machine-readable
```
