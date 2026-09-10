# Historical results — the Shadow campaign

> **These are Shadow results, not CORE results.** Everything in this directory
> was produced by the discrete-event simulator that `experiments/` replaced.
> It is kept because it is the reference the new runs are compared against —
> and it is kept *labelled*, because presenting simulated results as emulated
> ones would be the single most damaging thing this migration could do.

## What is here

```
shadow-campaign/
├── GUIDA_LETTURA.md      how to read the campaign (reading guide, Italian)
├── PROMPT_ANALISI.md     the analysis brief the campaign was written against
├── sheets/               the 17 campaign-level CSVs (one row per run, or per run x dimension)
├── plots/                the eight figures of the campaign
├── reports/              report_generale / _confronto / _asse_livello / _asse_tbt
│                         and the metrics_schema_report of the archived data
└── campaign/             the three-phase pipeline's campaign view: manifest,
                          summary, families, the workbook and the Monte-Carlo
                          validation of the election algorithm
```

Total: about 2.2 MB. What is **not** here is the ~3 GB of raw run data those
numbers were extracted from — see "Recovering the raw data" below.

## What the campaign was

Twenty-four runs: four geographic levels (`regionale`, `nazionale`,
`continentale`, `intercontinentale`) at six target-block-times (15, 10, 5, 3, 2
and a 10 s / 100-block-epoch variant), ten nodes each — three miners, five
companies, one admin, one Certification Authority.

Its two headline results, both reproduced in the reports:

* **Native Spacing stays binding under wPoA.** With `mining-diversity = 0.3`
  no miner ever signed two consecutive blocks — 0 out of 380 measured, against
  ~34 expected per level. Setting it to 0 restored the weighted distribution
  (chi-square 0.479 against 69.50). Every configuration in
  `experiments/configs/chain-params/` therefore pins `MINING_DIVERSITY=0`.
* **At 15 s the geography is nearly invisible**, because the sortition band
  `Δmax = δ·T` is ~80 times the worst RTT. That is a result, not a failure;
  compressing `target-block-time` is what brings the two into the same range.

## Why the numbers are not directly comparable with a new run

| | Shadow campaign | `experiments/` |
|---|---|---|
| execution | real `multichaind` under a discrete-event simulator | real `multichaind` on an emulated network |
| clock | simulated time, starting 2000-01-01 | wall clock and monotonic clock |
| block-time bias | inflated by the vDSO latency charged to every clock call | no simulator artefact; host contention instead |
| jitter | 0 on every link — the field was never implemented (shadow/shadow#3601) | applied by `tc`/netem |
| nodes | 10 | 20 by default |

The block-time figures in particular carry a **known simulator artefact**: the
archived mean of 17.9 s against a 15 s target includes the latency Shadow
charged to `clock_gettime`. A new run has no such term. Comparing the two
without saying so would attribute a simulator cost to the protocol's `λΦ`
feedback. See [../../docs/metrics.md](../../docs/metrics.md), "Three clocks".

## Reproducing these numbers

The analysis code that produced them was migrated, not rewritten, and it still
reads the legacy layout. It reproduces the archive exactly — verified by
`tests/golden/test_legacy_pipeline.py`:

```bash
# recover the raw campaign from git history (~3 GB)
git checkout 6278274 -- shadow/esperimenti shadow/config

# re-run the three phases over it
python3 -m experiments.analysis.pipeline.run_pipeline \
    --phase all --root shadow/esperimenti --config shadow/config --out /tmp/risultati

# and the campaign-level sheets
python3 -c "import sys; sys.argv=['a','--root','shadow/esperimenti','--out','/tmp/analisi', \
    '--force','--recompute-chisq']; \
    from experiments.analysis.legacy import analizza_esperimenti as A; A.main()"
```

Two differences are expected and are the only ones:

* `fit_prop518.csv` changes if the input set changes — it is a regression over
  the whole campaign, and the archived sheets predate `run6`. Restricted to the
  twenty runs they were built from, it is byte-identical.
* `epoch_shares.csv` rows are ordered by address in the current code and were
  not in the version that wrote the archive. The row *contents* are identical.

## A note on the absolute paths inside these files

`sheets/run_index.csv` has a `path` column, and
`campaign/campaign_manifest.json` and the Monte-Carlo log carry a `script`
field, all holding absolute paths on the machine that ran the analysis in
2026 (`/home/mattu/multichain/shadow/...`).

They are left exactly as they were **on purpose**. They are provenance — the
archive's own record of where it was produced — not configuration, and
rewriting them would falsify the archive to satisfy a lint rule. Nothing reads
them; no code in `experiments/` contains a personal path.

## Recovering the raw data

The ~3 GB of per-run metrics, snapshots and `debug.log` files were not carried
into `experiments/`; they live in git history at commit `6278274`
(`shadow/esperimenti/`, 4663 files, ~1.1 GB, plus `shadow/risultati/`, 1185
files, ~38 MB). Nothing was lost — `git checkout 6278274 -- shadow/esperimenti`
brings it all back.

See [../../docs/migration-from-shadow.md](../../docs/migration-from-shadow.md)
for what was migrated, what was archived and why.
