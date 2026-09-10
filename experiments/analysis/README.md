# Analysis

Three layers, in decreasing order of how much you should rely on them.

```
analysis/
├── pipeline/       the three-phase pipeline: the authoritative computation
├── legacy/         single-file analysers kept for the campaign-level sheets
├── compatibility/  presents a new run to the pipeline in the shape it knows
├── reporting.py    the per-run Markdown reports and plots
├── historical/     the archived Shadow campaign, clearly labelled as such
└── cli.py          `experiments.cli analysis|report`
```

## The three-phase pipeline

`pipeline/` was **migrated, not rewritten**. Every metric definition, every
constant and every statistical test is the code that produced the archived
campaign — which is the point: an archived run and a new one must be computed
by the same lines, or the comparison between them means nothing.

The phases are separate and each is re-runnable on its own:

| phase | reads | writes | what it is allowed to do |
|---|---|---|---|
| 1 `phase1_collect` | the run's `raw/metrics/`, `runtime/data/*/debug.log` | `phase1/` | collect only. Every row traceable to a log line or an on-chain record. No aggregation, no tests. |
| 2 `phase2_aggregate` | `phase1/` | `phase2/` | aggregate to round, epoch and node level. Still no tests. |
| 3 `phase3_analyze` | `phase2/` | `phase3/` | the statistics: goodness of fit, concentration, streaks, the longitudinal fits, the timer race |

That separation is deliberate and was an explicit design decision: no test may
run before phase 3, so that a disputed p-value can be traced to a table rather
than to a function call buried in a collector.

### Both run layouts

Discovery inspects rather than being told:

* **native** — `<root>/<run-id>/` with `manifest.json` and `raw/metrics/`
* **legacy** — `<root>/runN-tbt-Ts/<level>/run/metrics/`, the Shadow archive

A native run is presented to the pipeline by `compatibility/run_adapter.py`,
which writes the level JSON and the GML the pipeline expects into
`<run>/analysis-compat/`. Nothing global is mutated; the compatibility inputs
are artefacts of the run that needed them.

```bash
python3 -m experiments.analysis.pipeline.run_pipeline --phase all
python3 -m experiments.analysis.pipeline.run_pipeline --phase 3 --only regional
```

## The legacy analysers

`legacy/` holds the single-file tools that produce the **campaign-level**
sheets — one row per run, or per run × dimension — that the thesis quotes:
`proposers.csv`, `chisq.csv`, `alternanze.csv`, `block_times.csv` and the rest.
`analizza_esperimenti.py` shares its discovery and its pure helpers with
`pipeline/common.py`, so the two cannot drift.

```bash
python3 -c "import sys; sys.argv=['a','--root','experiments/results','--out','/tmp/analisi', \
    '--force','--recompute-chisq']; \
    from experiments.analysis.legacy import analizza_esperimenti as A; A.main()"
```

`--recompute-chisq` matters: the archived sheets were produced with it, and
without it the recomputed chi-square columns are absent.

## Reports

`experiments.cli report generate --run-id <id>` writes, into the run's own
`reports/`, the five historically named files:

```
report_generale.md          chain progress, peers, propagation, forks, conditions, host
report_confronto.md         observed against expected, per run
report_asse_livello.md      where this run sits on the geography axis
report_asse_tbt.md          where it sits on the target-block-time axis
metrics_schema_report.md    generated from the metric catalogue
```

Every section labels its quantities *observed*, *derived* or **unavailable**,
and a section with no data says so instead of disappearing. Every report opens
with the same banner: these are emulation results, and the archived Shadow
numbers are not directly comparable.

## What is deliberately not here

The archived campaign's ~3 GB of raw run data. It is in git history at
`6278274`; [historical/README.md](historical/README.md) says how to get it
back and what changes if you re-analyse it.
