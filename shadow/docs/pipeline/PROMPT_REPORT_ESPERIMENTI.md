# Prompt — Per-experiment reports from the phase-3 outputs (wPoA + Weight Engine, Shadow campaign)

> Paste this whole file into a fresh Claude Code session opened at the repository root
> (the directory that contains `shadow/`). It is self-sufficient: everything needed to
> execute it — the layout, the file schemas, the column meanings, the selection rule and
> the report format — is written below. You do not need to have read any other prompt.

---

## 0. What this does

The repository holds an experimental campaign of the wPoA consensus (weighted private
sortition) and of the Weight Engine, run on the Shadow network simulator. A three-phase
pipeline (`shadow/tools/pipeline/`) has already turned the raw simulation into statistical
sheets. **This prompt does not run that pipeline and does not compute any statistic.** It
reads the sheets the pipeline already produced and writes one human-readable `report.md`
per experiment, in a fixed format, so that any two reports can be compared side by side
without re-reading their structure.

Your job, in one line: **for every experiment that does not yet have a `report.md`, read
its phase-3 sheets and write one.**

### Vocabulary (enough to read the numbers)

* **Experiment** = one `(run, area)` pair. `run2-tbt-10s` is a run (a sealed chain
  configuration, here a 10 s target block time); `regionale`, `nazionale`, `continentale`,
  `intercontinentale` are the four geographic topologies. 24 experiments in total.
* **Epoch** = `epoch(h) = h // L + 1`, where `L` is `weight_epoch_length` (12 blocks in
  run1–run5, 100 in run6). Weights are recomputed and published once per epoch.
* **Validator / miner** = `m1`, `m2`, `m3`. Companies `c1`…`c5` publish traffic and belong
  to a miner's cluster; `admin` and `ca` never mine.
* **Sortition** = each validator computes `score_i = E_i / g(w_i)` with `E_i = -ln u_i`
  (`u_i` from a VRF) and `g` the damping function (`dumpfunction`, `none` in this
  campaign); the smallest score wins (argmin). The score is turned into a start delay
  `D = T + delta*T*(2*norm - 1) + lambda*Phi`, so the winner is the validator whose timer
  fires first — a **timer race**.
* **`p_theoretical` (expected share)** = `g(w_i * Psi_i) / sum_j g(w_j * Psi_j)` with the
  weights **in force** at that block, averaged over the blocks of the epoch. `Psi` is the
  malus correction factor (always 1 here: the malus registry is empty in every run).
* **`p_hat` (observed share)** = blocks won / blocks in the epoch.
* **Inversion** = a round whose observed proposer is not the validator with the smallest
  logged delay. It measures noise in the race, not a protocol violation.
* **Setup blocks** = the first `setup_blocks` heights, mined before wPoA governs
  selection. Epochs entirely inside the setup are absent from the wPoA sheets.

---

## 1. Layout (verified against the repository)

```
shadow/
├── esperimenti/<run>/<area>/run/     raw Shadow + MultiChain data — NEVER read from here
├── docs/pipeline/README.md           full description of the pipeline (English)
├── docs/pipeline/00-fase0-...md      the reconnaissance report behind its design (Italian)
├── tools/pipeline/                   phase1_collect.py, phase2_aggregate.py, phase3_analyze.py, …
└── risultati/                        THE ONLY TREE YOU READ AND THE ONLY ONE YOU WRITE
    ├── pipeline.log
    ├── campaign/                     campaign_summary.csv, campaign_families.csv,
    │                                 campaign_manifest.json, campaign.xlsx,
    │                                 sortition_algorithm_validation.csv
    └── <run>/<area>/                 ← THE EXPERIMENT DIRECTORY
        ├── phase1/                   raw rows extracted from logs — do not read
        ├── phase2/                   deterministic derivations — do not read
        ├── phase3/                   ← THE ONLY INPUT OF THIS PROMPT
        │   ├── manifest.json
        │   ├── wpoa_epoch_validators.csv
        │   ├── wpoa_epoch_tests.csv
        │   ├── wpoa_epoch_liveness_validators.csv
        │   ├── wpoa_prop517.csv
        │   ├── wpoa_sigma.csv
        │   ├── wpoa_longitudinal_validators.csv
        │   ├── wpoa_longitudinal_fits.csv
        │   ├── wpoa_longitudinal_logratios.csv
        │   ├── weight_engine_epoch.csv
        │   ├── weight_engine_gini.csv
        │   ├── weight_engine_gini_summary.csv
        │   ├── weight_engine_correlations.csv
        │   ├── weight_engine_traffic_model.csv
        │   ├── config.csv
        │   ├── methodology_notes.csv
        │   └── <run>__<area>.xlsx    the same tables as one workbook (for humans, not for you)
        └── report.md                 ← WHAT YOU WRITE
```

The 24 experiment directories are `shadow/risultati/run{1..6}-*/{regionale,nazionale,continentale,intercontinentale}/`.
`shadow/esperimenti/run7-tbt7s/` is empty and is not an experiment.

**Do not confuse** the reports you write with `shadow/analisi/report_*.md`: those belong to
an older, separate analysis pipeline and are unrelated to this task.

---

## 2. Which experiments to process

**The presence of `report.md` in the experiment directory is itself the marker.** There is
no state file, no index, no database.

1. Enumerate `shadow/risultati/*/*/` (skip `campaign/`).
2. An experiment is **to be processed** when `phase3/manifest.json` exists **and**
   `report.md` does not.
3. An experiment that already has `report.md` is skipped silently — no recomputation, no
   refresh, no "improving" of an existing report. The only exception is an explicit request
   from the user in that session ("rigenera i report", "aggiorna run4"); when that happens,
   overwrite the named reports and say which ones you overwrote.
4. If an experiment has no `phase3/manifest.json`, do not invent a report: list it at the
   end as "phase 3 missing — run `python3 tools/pipeline/run_pipeline.py --phase 3 --only <run>/<area>` first".

State up front how many experiments you found, how many you will process and how many you
skipped, then process them one at a time.

---

## 3. The files you read, and what their columns mean

Only these files. All of them live in `<experiment>/phase3/`. Column names below are the
real ones — read them verbatim, do not guess.

### 3.1 `manifest.json` — the experiment in one object

`summary` holds 73 flat keys. The ones you need:

| key | meaning |
|---|---|
| `experiment_id`, `area`, `replication_id` | identity (`replication_id` is 1 everywhere: single seed, no replicas) |
| `target_block_time`, `weight_epoch_length`, `setup_blocks`, `final_height` | chain configuration and run length |
| `dumpfunction`, `malus_enabled`, `wpoa_sortition_delta`, `wpoa_sortition_lambda`, `wpoa_randao_lookback` | sortition parameters |
| `weight_kappa`, `weight_alpha`, `weight_lambda`, `wpoa_malus_mu`, `wpoa_malus_max`, `malus_points_equiv_delay_selfwrite_badweight` | weight-engine and malus parameters |
| `n_measured_blocks`, `n_rounds_with_scores`, `measured_epochs`, `fully_measured_epochs` | coverage |
| `inversion_rate`, `inversion_n`, `inversion_wilson95_low/high`, `inversion_with_fork_n` | timer race, whole run |
| `sigma_S1_s`, `sigma_S2_s`, `inversion_bound_S1`, `inversion_bound_S2`, `inversion_mc_prob_gaussian_S2` | noise estimates and the Prop. 5.18 bound |
| `gof_pooled_method`, `gof_pooled_p`, `gof_pooled_min_expected`, `gof_pooled_mc_round_by_round_p`, `TV_pooled`, `MaxAE_pooled`, `epochs_gof_reject_alpha05`, `epochs_gof_tested` | goodness of fit, whole run and epoch counts |
| `ks_beta_pooled_p`, `ks_mc_pooled_p`, `G_median_over_Dmax` | timer-race margin tests |
| `HHI_p_hat_pooled`, `HHI_p_theoretical_pooled`, `nakamoto_1_2_p_hat` | concentration |
| `L_max_observed`, `L_max_mc_mean`, `L_max_mc_p` | consecutive-win streaks |
| `BlockSuccessRate`, `n_forks`, `InterBlockTime_median_s`, `InterBlockTime_p95_s`, `n_rejects`, `time_bar_violations` | liveness and validity |
| `delay_recompute_mismatch_rounds`, `phi_mismatch_rounds` | model-consistency counters |
| `glm_beta1_logw`, `glm_beta1_ci_low`, `glm_beta1_ci_high` | longitudinal proportionality slope |
| `weight_recompute_mismatches`, `weight_rows` | weight-engine reproducibility |
| `gini_delta_last`, `gini_delta_slope`, `gini_verdict` | inequality trajectory |
| `spearman_rho_to_w_next_pooled`, `spearman_p_pooled` | reconciliation → future weight |
| `malus_registry_records` | malus events on chain (0 in every run of this campaign) |

`constants` holds `alpha` (0.05), `mc_gof` (20000), `mc_streak` (10000), `seed`.
`row_counts` says how many rows each CSV has.

### 3.2 `wpoa_epoch_validators.csv` — one row per (epoch, validator)

Rows exist for each **measured** epoch plus a pooled row with `epoch = all`.

| column | meaning |
|---|---|
| `epoch` | epoch number, or the literal `all` (whole run pooled) |
| `epoch_buried` | 1 when the epoch's last block has ≥ 6 blocks on top of it |
| `validator_host`, `validator_address` | `m1`/`m2`/`m3` and its address |
| `w_raw_start`, `w_raw_end` | published integer weight in force at the first / last block of the epoch |
| `w_eff_start`, `w_eff_end` | the same after malus and damping: `g(w * Psi)` |
| `psi` | malus correction factor (1.0 throughout this campaign) |
| `p_theoretical_blockweighted` | **expected share**: mean over the epoch's blocks of the in-force share |
| `n_blocks` | blocks in the epoch |
| `O_i` | blocks won by this validator |
| `E_i` | expected blocks = sum over blocks of the in-force share |
| `p_hat` | **observed share** = `O_i / n_blocks` |
| `wilson95_low`, `wilson95_high` | Wilson 95 % score interval for `p_hat` |
| `p_theoretical_inside_wilson95` | 1 when the expected share falls inside that interval |
| `abs_error_p` | `|p_hat - p_theoretical_blockweighted|` |
| `share_changed_within_epoch` | 1 when the in-force weights changed inside the epoch |

### 3.3 `wpoa_epoch_tests.csv` — one row per epoch (plus `epoch = all`)

87 columns. The ones the report uses:

| column | meaning |
|---|---|
| `n_blocks`, `n_rounds_with_scores`, `n_validators`, `share_changes_within_epoch` | size and stability of the epoch |
| `gof_method` | which test was used: `chi2_asymptotic` (only when `gof_min_expected ≥ 5`), `exact_multinomial_enumeration` (≤ 3 classes, all outcomes enumerated), `monte_carlo_multinomial` |
| `gof_chi2`, `gof_df`, `gof_min_expected`, `gof_p_value`, `gof_reject_alpha05`, `gof_exact_outcomes` | the test itself; `gof_reject_alpha05 = 1` means the observed shares are incompatible with the expected ones at α = 0.05 |
| `gof_mc_round_by_round_p` | the same test with a Monte Carlo that respects the per-round shares (the honest version when weights changed inside the epoch) |
| `MAE_p`, `MaxAE_p`, `TV` | mean / max absolute error and total variation between observed and expected shares |
| `G_n`, `G_mean_s`, `G_median_s`, `G_over_Dmax_median` | the timer-race margin `G = D(2) - D(1)`, in seconds |
| `ks_beta_stat`, `ks_beta_p`, `ks_beta_note` | KS of `G` against `2*Dmax*Beta(1,n)`, the iid-uniform prediction of Prop. 5.18. **Rejection is expected**: the note says the assumption is invalid for concentrated weights |
| `ks_mc_stat`, `ks_mc_p`, `ks_mc_draws`, `ks_mc_note` | KS of `G` against the exact Monte Carlo of the implemented sortition with the real per-round weights. **This is the reference timer-race test** |
| `inversion_n`, `inversion_rounds`, `inversion_rate`, `inversion_wilson95_low/high`, `inversion_with_fork_n` | inverted rounds and how many coincided with a competing block |
| `inversion_bound_sigma_S1`, `inversion_bound_sigma_S2`, `inversion_bound_sigma_used_s`, `inversion_mc_prob_gaussian_sigma_S2` | the Prop. 5.18 bound `(3/2)(n·sigma/Dmax)^(2/3)` evaluated at each sigma, and a Gaussian-noise Monte Carlo at sigma_S2 |
| `p_theoretical_HHI`, `p_theoretical_N_eff`, `p_theoretical_nakamoto_1_3/1_2/2_3`, `p_theoretical_gini`, `p_theoretical_entropy_norm` | concentration of the **expected** shares |
| `p_hat_HHI`, `p_hat_N_eff`, `p_hat_nakamoto_1_3/1_2/2_3`, `p_hat_gini`, `p_hat_entropy_norm` | concentration of the **observed** shares |
| `L_max_observed`, `repeat_prob_observed`, `L_max_mc_mean`, `L_max_mc_p95`, `L_max_mc_p_value`, `repeat_prob_mc_mean`, `repeat_prob_mc_p_value` | longest run of consecutive wins and repeat probability, observed vs Monte Carlo of the sortition alone |
| `BlockSuccessRate`, `n_competing_blocks`, `n_forks`, `n_rejects`, `rejects_by_reason` | liveness: canonical blocks over canonical plus competing |
| `InterBlockTime_median_s`, `_p95_s`, `_p99_s`, `_mean_s`, `_max_s` | block spacing |
| `time_bar_violations`, `time_bar_checked` | blocks violating `nTime ≥ parent.nTime + floor(D)` |
| `delay_recompute_mismatch_rounds`, `phi_mismatch_rounds` | rounds where the recomputed delay or the feedback term Phi disagreed across miners |
| `malus_delay_events_recomputed`, `malus_psi` | free-text; both say the malus registry is empty |

### 3.4 `wpoa_epoch_liveness_validators.csv` — one row per (epoch, validator)

`n_rounds_theoretical_argmin` (rounds where the validator had the smallest delay),
`n_rounds_theoretical_argmin_lost`, `MissedTurnRate` = lost / argmin, `MissedTurnRate_note`
(explains an empty rate), `n_rounds_won_not_argmin`, `blocks_won`.

### 3.5 `wpoa_prop517.csv` — one row per (epoch, argmin class)

`argmin_class_host`, `n`, `ks_stat`, `ks_p`, `mean_gap_x_rate` (should be ≈ 1),
`expected_mean` (1.0), `note`. Tests that the score gap between the best and second-best
candidate follows `Exp(W − w_i*)`, i.e. Prop. 5.17 of the thesis.

### 3.6 `wpoa_sigma.csv` — four rows, the noise estimates

`sigma_id` ∈ {`S1_topology`, `S2_scheduler_residual_sd`, `S2b_inversion_gap`,
`S3_packet_loss`}, with `sigma_s`, `source`, `what_it_measures`, `n`, `median_s`, `p90_s`,
`max_s`, `note`. S2 is the primary estimate; S3 is always not computable.

### 3.7 Longitudinal sheets

* `wpoa_longitudinal_validators.csv` — one row per validator: `epoch_first`, `epoch_last`,
  `p_theoretical_first/last`, `p_hat_first/last`, Wilson bounds for both, `gain_observed`,
  `gain_theoretical`, `intervals_overlap`, and the monotonicity test
  `mono_n_pairs_informative`, `mono_n_concordant`, `mono_concordance_rate`,
  `mono_sign_test_p_greater`.
* `wpoa_longitudinal_fits.csv` — three rows (three models): `model`, `H0`, `beta1`,
  `beta1_se`, `beta1_ci_low/high`, `beta0`, `n_points`, `converged`,
  `beta1_ci_contains_1`, plus `pearson_r/p` and `spearman_rho/p` for the log-ratio model.
  `beta1 = 1` is proportional selection; `beta1 > 1` means the strong validator wins more
  than its weight implies.
* `wpoa_longitudinal_logratios.csv` — one row per (epoch, validator pair):
  `log_ratio_observed`, `log_ratio_theoretical`, `O_i`, `O_j`, `B`.

### 3.8 Weight-engine sheets

* `weight_engine_epoch.csv` — one row per (epoch, cluster head). The Chapter-6 chain:
  `esg_miner`, `tau_miner`, `companies` (a `host:esg=..:tau=..:c_i=..` list), `theta_code`
  and `theta_thesis` (two definitions of network activity), `W_k_raw`, `A_k_alloc`,
  `R_k_reconciled`, `B_k_prev`, `B_k`, `rho_k`, `rho_k_prev`, `feedback_factor`,
  `w_k_recomputed`, `w_k_int_recomputed`, `w_k_published`, `w_k_published_prev`,
  `recompute_match` (1 when the independent recomputation reproduces the published
  weight), `implied_W_k_raw_from_published`, `implied_raw_delta_over_esg_miner`,
  `malus_M`, `psi`, `w_after_malus`, `w_effective_g`, `share_snapshot`,
  `blocks_mined_epoch`, plus the free-text `dumpfunction_effect` and `malus_trajectory`.
* `weight_engine_gini.csv` — one row per epoch: `n_clusters`, `n_published`,
  `gini_w_published`, `gini_input_W_k_raw` (the baseline: inequality already present in the
  inputs, before the rho feedback), `gini_delta_published_minus_input`,
  `entropy_norm_w_published`, `HHI_w_published`, `dominant_host`, `dominant_share`,
  `n_recompute_match`, `n_recompute_mismatch`, `n_hosts_verification_ok_log`,
  `n_hosts_verification_failed_log`.
* `weight_engine_gini_summary.csv` — one row: `gini_delta_first/last/max`,
  `gini_delta_slope_per_epoch`, `gini_published_last3_sd`, `verdict_descriptive`.
* `weight_engine_correlations.csv` — one row per cluster plus a pooled row:
  `n_epoch_pairs`, `n_distinct_rho_values`, `n_pairs_rho_equal_1`,
  `spearman_rho_e_vs_w_next` (lag-1: reconciliation ratio of epoch e against the weight
  published for e+1), `spearman_p`, the tautological control
  `spearman_rho_e_vs_w_next_over_W_raw_next`, and `spearman_R_k_vs_rho_k`.
* `weight_engine_traffic_model.csv` — one row stating that traffic generation is exogenous.

### 3.9 `config.csv` and `methodology_notes.csv`

`config.csv`: one row per parameter, `parameter | value | source | thesis_symbol | note` —
the source tells you where each value was read (params.dat, the node's start-up log,
shadow.yaml, the topology file). `methodology_notes.csv`: `topic | note`, 16 rows,
including `not computable on this campaign`. Quote these instead of paraphrasing when the
report has to declare a limit.

---

## 4. The report

One file, `report.md`, in the experiment directory, with **exactly** the five sections
below in this order. Same headings, same column names, same order in every report.

Write it in **English**. (To produce Italian reports instead, change only this line and the
section headings in §4.1–4.5; nothing else in this prompt depends on the language.)

### 4.1 Section A — Header (5–8 lines, data only, no comment)

```markdown
# <experiment_id> / <area>

| | |
|---|---|
| Target block time | 10 s |
| Damping function (dumpfunction) | none |
| Malus | enabled, registry empty (0 records) |
| Epoch length | 12 blocks |
| Measured epochs | 23 (21 fully measured), epochs 6–28 |
| Blocks | 261 measured of 325 total (setup 64), final height 325 |
| Sortition | delta 0.5, lambda 0.2, RANDAO lookback 1 |
| Weight engine | kappa 100, alpha 0.2, lambda_w 0.5 |
```

All values from `manifest.json → summary`. The malus line combines `malus_enabled` with
`malus_registry_records`. No prose in this section.

### 4.2 Section B — Epoch by epoch, per validator (the detail)

For each measured epoch, in ascending order (**exclude the `all` row**, it belongs to
section D), one heading line and one table with **exactly four columns**:

```markdown
#### Epoch 10 — 12 blocks, heights 108–119, buried

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.669 | 0.833 | expected inside Wilson 95 % CI [0.552, 0.953] |
| m2 | 0.257 | 0.167 | expected inside Wilson 95 % CI [0.047, 0.448] |
| m3 | 0.074 | 0.000 | expected inside Wilson 95 % CI [0.000, 0.242] |
```

(The example is the real epoch 10 of `run2-tbt-10s/regionale`, so you can check your
renderer against it.)

* `p_expected` = `p_theoretical_blockweighted`, `p_observed` = `p_hat`, both to 3 decimals.
* `verdict` = the per-node Wilson check: `p_theoretical_inside_wilson95` rendered as
  `expected inside Wilson 95 % CI [low, high]` or `expected OUTSIDE Wilson 95 % CI [low, high]`.
* The heading line carries `n_blocks`, the height range (`epoch_start_height`–`epoch_end_height`
  from `weight_engine_epoch.csv`, or `(epoch-1)*L`–`(epoch*L - 1)` when that row is absent)
  and `buried` / `not buried` from `epoch_buried`.
* Add ` — weights changed inside the epoch` to the heading when `share_changes_within_epoch = 1`.

**Under each table, 1–3 lines of commentary, and only when one of these triggers fires.**
When none fires, write exactly one line: `Compatible with the expectation, no relevant deviation.`

| trigger | what the line must say |
|---|---|
| `gof_reject_alpha05 = 1` | the test name (`gof_method`), `gof_p_value`, and which validator carries the deviation (largest `abs_error_p`), with `O_i` vs `E_i` |
| any node with `p_theoretical_inside_wilson95 = 0` | which node, its `p_hat`, its interval, its expected share |
| `MissedTurnRate ≥ 0.5` for a node with `n_rounds_theoretical_argmin ≥ 3` | node, rate, lost/argmin counts |
| `inversion_rate` of the epoch ≥ 1.5 × the run's pooled `inversion_rate` | epoch rate vs pooled rate, and `inversion_with_fork_n` |
| `n_recompute_mismatch > 0` (same epoch, `weight_engine_gini.csv`) | how many published weights the recomputation failed to reproduce, and `implied_raw_delta_over_esg_miner` for the affected cluster |
| `n_hosts_verification_failed_log > 0` | how many nodes reported a failed independent verification |
| `time_bar_violations > 0` or `n_rejects > 0` | the count and, for rejects, `rejects_by_reason` |
| `L_max_mc_p_value < 0.05` or `repeat_prob_mc_p_value < 0.05` | observed streak vs Monte Carlo mean, with the p-value |

Numbers, not adjectives. Never write "significant", "notable", "interesting" without the
figure that makes it so.

### 4.3 Section C — Per-epoch summary over the whole experiment (the trend)

**One row per measured epoch**, no validator breakdown, exactly these columns:

```markdown
## Trend by epoch

| epoch | blocks | GoF p (method) | HHI | N_eff | Nakamoto ½ | timer race KS p | inversion rate | block success | WE conformity |
|---|---|---|---|---|---|---|---|---|---|
| 6 | 7 | 0.229 (exact) | 1.000 | 1.00 | 1 | 0.286 | 0.143 | 1.000 | 3/3 |
| 10 | 12 | 0.465 (exact) | 0.722 | 1.38 | 1 | 0.388 | 0.250 | 0.857 | 3/3 |
```

(Both rows are the real epochs 6 and 10 of `run2-tbt-10s/regionale`.)

Sources, in order: `epoch`; `n_blocks`; `gof_p_value` with `gof_method` abbreviated
(`chi2` / `exact` / `mc`) and a trailing `*` when `gof_reject_alpha05 = 1`; `p_hat_HHI`;
`p_hat_N_eff`; `p_hat_nakamoto_1_2`; `ks_mc_p` (the reference test — **not** `ks_beta_p`);
`inversion_rate`; `BlockSuccessRate`; and `n_recompute_match`/`n_clusters` from
`weight_engine_gini.csv` joined on `epoch`.

Weight-engine epochs start at 1 while wPoA epochs start after the setup, and the engine
also folds epochs past the last measured block. Join on `epoch`, put `—` where the
weight-engine row is missing, and add one line under the table saying how many
weight-engine epochs fall outside the measured range (they are setup epochs and the
trailing partial epoch, not missing data).

Do not repeat any of these numbers in section B: section B carries the per-node detail and
its commentary, section C carries the per-epoch trend.

### 4.4 Section D — How the system behaved (half a page maximum)

Four short paragraphs, using only figures already in the phase-3 sheets (mostly the
`epoch = all` rows and `manifest.json → summary`). One paragraph per question. If a
question cannot be answered from the data, say so in one sentence and move on.

1. **Does the system converge to the theoretical behaviour?** Use the pooled
   `gof_pooled_method` / `gof_pooled_p`, `epochs_gof_reject_alpha05` of
   `epochs_gof_tested`, `TV_pooled` and `MaxAE_pooled`, and the longitudinal slope
   `glm_beta1_logw` with its CI (`beta1 = 1` is proportional selection).
2. **Does the network introduce a measurable deviation from proportionality?** Use
   `sigma_S1_s` (topology latency) against `sigma_S2_s` (scheduler residual), the observed
   `inversion_rate` with its Wilson interval, the bounds `inversion_bound_S1` /
   `inversion_bound_S2`, `inversion_mc_prob_gaussian_S2`, and `inversion_with_fork_n`.
   State plainly that the Shadow topologies declare zero jitter, so the noise that decides
   the race is the 1 s quantisation of the time bar and of block timestamps, not network
   latency — the `wpoa_sigma.csv` rows say exactly this in their `source` and
   `what_it_measures` fields.
3. **Did the weight engine reward conformity in later epochs?** Use
   `spearman_rho_to_w_next_pooled` and `spearman_p_pooled`, the tautological control column,
   `gini_delta_slope`, `gini_verdict`, and `weight_recompute_mismatches` of `weight_rows`.
   Mention that traffic is exogenous (`weight_engine_traffic_model.csv`), so the only
   endogenous feedback channel is the reconciliation ratio rho.
4. **Were there malus events with a measurable effect on weight?** In this campaign the
   answer is fixed and must be stated as such: `malus_registry_records = 0`, `psi = 1.0` for
   every validator in every epoch, so the malus mechanism is enabled but never exercised —
   the campaign contains no malicious actor by design. Do not present this as a finding of
   the experiment; present it as a limit of the campaign, quoting the
   `not computable on this campaign` row of `methodology_notes.csv`.

### 4.5 Section E — Notable facts and anomalies (3–6 bullets)

The highest-density section. One quantitative fact per bullet, ordered by how much it
would change a reader's conclusion. Draw from, at least:

* epochs with `gof_reject_alpha05 = 1` (list them with their p-values);
* validators whose expected share fell outside the Wilson interval, with the numbers;
* the observed inversion rate against the Prop. 5.18 bound and against the Gaussian Monte
  Carlo, and how many inversions coincided with a fork;
* `ks_beta_p` vs `ks_mc_p` — the Beta(1,n) rejection is **expected** (the sheet's
  `ks_beta_note` says the iid-uniform assumption is invalid for concentrated weights) and
  must be reported as such, never as a failure;
* `L_max_observed` vs `L_max_mc_mean` with `L_max_mc_p_value`;
* rows with `recompute_match = 0` in `weight_engine_epoch.csv`, with
  `implied_raw_delta_over_esg_miner`;
* non-zero `delay_recompute_mismatch_rounds` or `phi_mismatch_rounds`;
* `wpoa_prop517.csv` rows with `ks_p < 0.05` and their `mean_gap_x_rate` against 1.0;
* any parameter close to its admissible limit in `config.csv`.

If a category has nothing to report, drop the bullet — do not write "no anomalies of type X".
If the whole experiment is unremarkable, three bullets of the strongest facts are enough.

---

## 5. Style

* A reader must get through one report in a few minutes. Tables for numbers, prose only
  where judgement is involved (sections D and E, and the commentary lines of B).
* No number appears in two sections.
* Normality is one line. Spend the reader's time on what deviates.
* Identical structure in every report, so two reports open side by side line up.
* One Markdown file per experiment. Never a single file covering several experiments.
* Round to 3 decimals for probabilities and shares, 2 for indices such as `N_eff`,
  3 significant digits for p-values, 2 decimals for seconds. Keep p-values below 0.001 as
  `< 0.001`.
* Do not embed the raw CSV rows, do not paste the whole `config.csv`, do not reproduce the
  xlsx.

---

## 6. What you must not do

* **Do not read** `phase1/`, `phase2/`, `shadow/esperimenti/`, or any Shadow / MultiChain
  log. If a number you want is not in `phase3/`, the report says it is missing.
* **Do not recompute a statistic.** No new test, no new interval, no re-derivation from
  raw rows. Formatting an existing column, or the ratio of two columns that already exist
  in the same row (`n_recompute_match / n_clusters`), is formatting. Anything that needs a
  distribution, a model fit, a simulation, or an aggregation over rows the sheets do not
  already aggregate is forbidden — say the datum is absent instead.
* **Do not introduce a metric** that phase 3 does not produce. A useful missing metric is
  reported as a gap of the upstream pipeline, at the end of section E, in one line.
* **Do not touch** an experiment that already has `report.md`.
* **Do not summarise across experiments** unless the user asks in that session; this prompt
  produces per-experiment reports only. `shadow/risultati/campaign/campaign_summary.csv`
  already holds the cross-experiment view.

---

## 7. Structural gaps of this campaign — state them, do not hunt for them

These hold for all 24 experiments and are documented in `methodology_notes.csv`. Report them
where the fixed structure asks for them, and never treat them as findings of a single run:

* **Malus**: enabled but never triggered, registry empty, `psi = 1.0` everywhere. No
  malus-driven weight decay exists to observe.
* **Damping**: `dumpfunction = none` in every run, so `g(w) = w` and the damping effect is
  not measurable.
* **VRF output** `y_i` is not logged; `E_i` and `u_i` are derived from the score.
* **Per-event latency and jitter** are not measurable: logs have 1 s resolution and the
  Shadow topologies declare `jitter 0 us`. Packet loss is not observable at all.
* **No replicas**: `replication_id = 1`, one seed per run, so no between-replica variance.

---

## 8. Procedure

1. Enumerate the experiments and report the counts (found / to process / skipped).
2. **Write the renderer once**, at `shadow/tools/pipeline/make_report.py`, and reuse it for
   every experiment: it reads the phase-3 CSVs and `manifest.json` of one experiment and
   emits sections A, B and C exactly as specified, leaving two anchors
   `<!-- D -->` and `<!-- E -->` for the parts that need judgement. A script guarantees the
   tables are byte-identically formatted across all 24 reports, which hand-writing cannot.
   It must not compute anything beyond formatting and the ratios allowed in §6.
3. For each selected experiment: run the renderer, then read the same sheets yourself and
   write sections D and E into the anchors.
4. Verify against the checklist in §9, then move to the next experiment.
5. At the end, report: reports written (with paths), experiments skipped, experiments
   missing phase 3, and any datum you had to declare missing.

Do not commit anything unless the user asks.

## 9. Acceptance checklist (per report)

- [ ] The five sections A–E are present, in order, with the specified headings.
- [ ] Section A has 5–8 rows and no prose.
- [ ] Section B has one table per measured epoch, four columns, no extra column, the
      `all` row excluded.
- [ ] Every epoch table is followed either by the single "compatible" line or by 1–3
      lines each carrying a figure.
- [ ] Section C has one row per measured epoch and the ten specified columns, with `—`
      where the weight-engine join is empty and the note about epochs outside the measured range.
- [ ] Section D has four paragraphs, half a page at most, every claim traceable to a named
      column, and the malus paragraph framed as a campaign limit.
- [ ] Section E has 3–6 bullets, each quantitative, and reports the Beta(1,n) rejection as
      expected rather than as a failure.
- [ ] No number appears twice; no statistic was recomputed; no file outside `phase3/` was read.
