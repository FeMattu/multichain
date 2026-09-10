# Results

One directory per run, named `run-<experiment>-<UTC timestamp>`. Sortable,
unique, and it says what it is without being opened.

Nothing in here is versioned except this file and `.gitkeep`: a twenty-node
run produces hundreds of megabytes of `debug.log` alone. `EXPERIMENT_ROOT`
moves the whole tree off the repository volume:

```bash
export EXPERIMENT_ROOT=/data/poesia-runs
```

## Layout

```
run-regional-20260910T101500Z/
├── manifest.json              what ran, on what, with which commit and binary
├── run.log                    the harness's own log
├── config/                    the exact inputs, copied in
│   ├── experiment.yaml        ← the run is replayable from this alone
│   ├── topology.yaml
│   ├── chain-params.dat
│   ├── network-profiles/
│   ├── topology.gml
│   └── topology-edges.csv
├── runtime/
│   ├── topology-realized.json what was actually built, impairment included
│   ├── netem-events.jsonl     every mid-run condition change, both clocks
│   ├── shared/<node>.addr     the two-phase join's address exchange
│   └── data/<node>/           each node's MultiChain data directory
├── logs/<node>/               daemon stdout, each role script, archived debug.log
├── raw/
│   ├── metrics/               the admin's final chain snapshot + role CSVs
│   │   └── epochs/            per-epoch samples: verify, node state, treasury
│   └── observations/          the sampler's time series
├── analysis-compat/           the level JSON and GML the pipeline expects
├── metrics/                   the catalogued tables
├── analysis/                  phase1/ phase2/ phase3/
├── plots/
└── reports/                   report_generale.md and the four others
```

## Which file answers which question

| question | file |
|---|---|
| what ran, and can I reproduce it? | `manifest.json` |
| what did the network actually look like? | `runtime/topology-realized.json` |
| what did I change mid-run, and when? | `runtime/netem-events.jsonl` |
| why did node X misbehave? | `logs/X/` — then `debug.log` |
| what happened over time? | `metrics/node_observations.csv` |
| how fast did blocks spread? | `metrics/block_propagation.csv` |
| did the chain fork? | `metrics/fork_events.csv` |
| the headline numbers | `reports/report_generale.md` |
| where does column Y come from? | `reports/metrics_schema_report.md` |

## Housekeeping

```bash
python3 -m experiments.cli results list                      # what is here
sudo -E experiments/scripts/clean_experiment.sh              # fabric only
sudo -E experiments/scripts/clean_experiment.sh \
    --run-id <id> --purge-results                            # asks first
```

`clean_experiment.sh` removes the **emulated fabric** — namespaces, the
management bridge, stray veth ends and the qdiscs still attached to them. It
does not touch results unless you pass `--purge-results`, and then it asks.

The largest thing in a run is usually `runtime/data/<node>` and the archived
`debug.log`. Both are safe to delete once the analysis has run; `metrics/`,
`analysis/` and `reports/` are what a later comparison needs.
