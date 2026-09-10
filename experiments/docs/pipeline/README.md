# Shadow experimental pipeline — wPoA + Weight Engine

Three separated phases that turn the archived Shadow campaign
(`shadow/esperimenti/<run>/<area>/run/`, read-only) into statistical sheets.
Design approved on 2026-09-05 (phase-0 report:
[00-fase0-ricognizione-e-checkpoint-design.md](00-fase0-ricognizione-e-checkpoint-design.md),
in Italian; the answers to its questions Q1–Q13 are recorded in §8 below).

```
shadow/tools/pipeline/
├── common.py             pure helpers shared with tools/analizza_esperimenti.py (which re-imports them)
├── phase1_collect.py     raw rows from logs / RPC snapshots / harness CSVs      -> phase1/
├── phase2_aggregate.py   deterministic recomputation, no tests                 -> phase2/
├── phase3_analyze.py     tests, intervals, Monte Carlo, xlsx + csv twins        -> phase3/ and campaign/
├── stat/                 wilson, gof, timer_race, concentration, streak, longitudinal
└── run_pipeline.py       orchestrator (--phase 1|2|3|all, --only <substring>)

shadow/risultati/                          output root (never under esperimenti/)
├── pipeline.log
├── campaign/  campaign_summary.csv, campaign_families.csv, campaign_manifest.json, campaign.xlsx,
│              sortition_algorithm_validation.csv (+ .log)   <- tools/valida_sortition_montecarlo.py, reused as-is
└── <run>/<area>/phase1/ phase2/ phase3/
```

## 1. Running

```bash
cd shadow
python3 tools/pipeline/run_pipeline.py --phase all              # 24 runs, ~1 min
python3 tools/pipeline/run_pipeline.py --phase 3 --only run6    # one phase, filtered (no campaign files)
python3 tools/pipeline/run_pipeline.py --phase 2 --no-campaign
```

Each phase reads only the previous one (phase 3 also reads `phase1/config.csv`
for its config tab). Discovery follows `runN-tbt-Ts/<area>/run/metrics/`; the
empty, off-pattern `run7-tbt7s` is ignored and named in the log. Dependencies:
Python 3.10, numpy, scipy (KS, chi², binomial test, Spearman p-values), openpyxl
(xlsx; the CSV twins are complete without it), networkx (topology matrix).
Nothing is installed by the pipeline.

## 2. Hierarchy and identifiers

The archived campaign is **experiment → area**, not area → tbt → replica:
`experiment_id` = the run directory (`run2-tbt-10s`, sealed `params.dat`),
`area` ∈ {regionale, nazionale, continentale, intercontinentale}, `replication_id` = 1
everywhere (single seed). `run6-tbt-10s` differs from `run2-tbt-10s` only by
`weight-epoch-length` (100 vs 12) and forms with it the only single-parameter
family other than tbt-at-fixed-area and area-at-fixed-tbt (`campaign_families.csv`).

## 3. Phase 1 — raw collection (`phase1/`)

One CSV per source; every row carries `source_file`/`source_line` (log) or `txid`
(chain). No aggregation. The only labels added are `epoch = h // L + 1` and
`in_setup = h <= setup-first-blocks`, pure functions of the sealed configuration.

| table | one row per | source |
|---|---|---|
| `config.csv` | parameter (`parameter, value, source, thesis_symbol, note`) | params.dat, admin_getinfo.json, node start-up lines, shadow.yaml, config/levels, .gml |
| `blocks.csv` | canonical block | `blocks.json` (listblocks) |
| `sortition_scores.csv` | (height, candidate miner): `score_raw`, `delay_logged_s`, `start_in_s`, `duplicate_index` | `mchn-miner: wPoA-sortition height=…` in every miner's debug.log |
| `phi.csv` | (tip height, host): Φ, window, mean spacing, bound, `n_occurrences` | `[wpoa-sortition] feedback height=…` |
| `verify_lines.csv` | (height, signer, nTime, parent, ⌊D⌋), with the hosts that logged it | `[wpoa-sortition] verify OK …` |
| `sortition_ok_blocks.csv` | (height, block hash) seen by any host | `VerifyBlockMinerWPoA: sortition OK block …` |
| `rejects.csv` | REJECT line (header only in this campaign) | `VerifyBlockMinerWPoA: REJECT …` |
| `weight_engine_log.csv` | publication / verification line per host and epoch | `[WeightEngine] epoch …` |
| `malus_log.csv` | malus application line (header only) | `[wpoa-malus] height=…` |
| `weights_stream.csv`, `esg_stream.csv`, `membership_stream.csv`, `malus_stream.csv` | stream item, with `confirm_height` from `txs.log` | liststreamitems snapshots |
| `traffic.csv`, `gas_transfers.csv`, `gas_balances.csv`, `reconciliation.csv`, `node_state.csv`, `verify_snapshot.csv` | harness rows, header normalised, GAS as in the RPC | `metrics/*.csv`, `verify.json` |
| `unconfirmed_txids.csv` | txid never confirmed | `txs.log` |
| `topology_latency.csv`, `topology_edges.csv` | host pair / edge: one-way and RTT ms, jitter, packet loss | `.gml` + `config/levels/<area>.json` |
| `hosts.csv` | host: address, role, cluster head, ESG, coordinates | esg_scores.csv, membership.csv, level json |
| `manifest.json` | experiment: parameters and sources, hosts, epochs (start/end/buried/fully_measured), row counts, warnings | — |

## 4. Phase 2 — deterministic derivations (`phase2/`)

Base columns on every row: `experiment_id, replication_id, area, target_block_time,
dumpfunction, malus_enabled, weight_epoch_length`.

* `candidates_long.csv` — one row per (measured round, candidate): in-force weight
  record (`weight_raw_inforce`, epoch tag, confirm height), `psi`,
  `weight_effective = g(w·Ψ)`, `W_tot_effective`, `p_theoretical`, `E_i = score·g(w_eff)`,
  `u_i = e^{-E_i}`, `score_norm`, own `phi_s`, `delay_logged_s`, `delay_recomputed_s`,
  `delay_mismatch_s`, `delay_recompute_ok` (|Δ| ≤ 1.5 ms), `W_tot_implied_by_logged_delay`
  (the W that would reproduce the logged delay when the check fails), ranks by score
  and by delay, `is_winner`, `is_theoretical_argmin_*`, block hash/time, `verify_delay_floor_s`,
  `time_bar_ok`, `fork_detected`, `n_competing_blocks`, balance sample ≤ h, `streak_position`.
* `round_level.csv` — one row per measured round: observed vs theoretical winner
  (`inversion`), `margin_G_logged_s` (D(2)−D(1)), `inversion_gap_s` (D_obs − D_min),
  `score_gap_2_1`, `W_tot_minus_argmin_weff`, `phi_identical_across_nodes`, `dt_prev_s`,
  `scheduler_residual_s = dt_prev − D_logged(winner)`, time-bar slack and verdict,
  forks/competing hashes/rejects, `streak_length_so_far`, `winner_repeats_previous`.
* `epoch_level_wpoa.csv` — one row per (epoch, validator): `O_i`, `E_i_expected = Σ_h p_i(h)`,
  block-weighted / start / end theoretical share, `w_raw|w_eff` start/end, delay
  statistics and position in the band, argmin counts (base of MissedTurnRate), forks, rejects.
* `epoch_level_weight_engine.csv` — one row per (epoch, cluster): ESG, τ, company list
  `host:esg:tau:c_i`, `theta_code` (Σ τ over clustered companies, as `NetworkActivity`),
  `theta_thesis` (all non-coinbase txs of the epoch's blocks), `W_k_raw`, `A_k`, `R_k`,
  `B_k_prev/B_k`, `rho_k`, `rho_k_prev`, `feedback_factor`, `w_k_recomputed`,
  `w_k_int_recomputed = round(w·κ)`, `w_k_published`, `recompute_match`,
  `implied_W_k_raw_from_published`, `implied_raw_delta_over_esg_miner` (the τ the node
  must have counted beyond the reconstruction), malus `M`/`Ψ`, effective weight, snapshot share.
* `weight_engine_verification.csv` — per epoch: publications and per-host verification
  verdicts from the logs (the RPC keeps only the last epoch).
* `balance_by_height.csv`, `malus_epoch.csv` (M = 0, Ψ = 1, 0 events: computed from an empty registry).
* `manifest.json` → `summary`: rounds, inversions, time-bar violations, max |D_rec − D_log|,
  rounds with a delay mismatch, Φ mismatches, forks, weight recompute mismatches.

The weight-engine fold is `common.weight_engine_fold`, the same code the legacy
script now calls; the height→epoch map is `common.epoch_of` for both modules; a
record confirmed at `h_c` is in force for blocks `h > h_c`.

## 5. Phase 3 — statistical sheets (`phase3/<run>__<area>.xlsx` + CSV per table)

Every tab opens with the parameter row (T, L, setup, δ, λ, k, g, malus on/off, μ, M_max,
malus points, κ, α, λ_w, spacing, seeds, RTT). Non-computable metrics carry
`not computable: <reason>`.

**wPoA_epoch** — per epoch and pooled (`epoch = all`):
`wpoa_epoch_validators.csv` (w_raw/w_eff, `p_theoretical_blockweighted`, `O_i`, `E_i`,
`p_hat`, Wilson 95 %, `p_theoretical_inside_wilson95`, `abs_error_p`);
`wpoa_epoch_tests.csv` (GoF with `gof_method` ∈ {chi2_asymptotic if min E ≥ 5,
exact_multinomial_enumeration ≤ 3 classes, monte_carlo_multinomial} plus a round-by-round
Monte Carlo that respects per-round shares; MAE/MaxAE/TV; KS of G vs 2Δmax·Beta(1,n) **and**
vs the exact Monte Carlo of the implemented sortition with the real per-round weights,
W_tot and Φ; inversion count/rate with Wilson, fraction coinciding with a fork, bound
(3/2)(nσ/Δmax)^{2/3} for σ_S1 and σ_S2, Gaussian-noise Monte Carlo at σ_S2; HHI, N_eff,
Nakamoto 1/3–1/2–2/3, Gini, entropy on p and p̂; L_max and repeat probability vs Monte Carlo
of the sortition alone; BlockSuccessRate, InterBlockTime median/p95/p99, forks, rejects,
time-bar violations, delay-recompute and Φ mismatches; malus lines as not computable);
`wpoa_epoch_liveness_validators.csv` (MissedTurnRate_i); `wpoa_prop517.csv` (score gap
standardised by W − w_i* vs Exp(1), per argmin class); `wpoa_sigma.csv` (S1 topology,
S2 scheduler residual sd — primary, S2b inversion gaps, S3 not computable).

**wPoA_longitudinal** — `wpoa_longitudinal_validators.csv` (first vs last fully measured
epoch: p, p̂, Wilson, gains, interval overlap; monotonicity of consecutive epochs with an
exact sign test); `wpoa_longitudinal_fits.csv` (binomial logit GLM by IRLS,
`logit(p̂) ~ b0 + b1·log(w_eff)` and `~ log(p)`, Wald CI, H0 b1 = 1; pairwise log-ratio
slope/intercept with Pearson and Spearman); `wpoa_longitudinal_logratios.csv`.

**WeightEngine_epoch** — `weight_engine_epoch.csv` (phase-2 cluster table plus the
not-computable dumpfunction/malus columns); `weight_engine_gini.csv` (Gini/entropy/HHI of
published `w_k` vs the input baseline `W_k_raw`, Δ, dominant host, verification counts);
`weight_engine_gini_summary.csv` (slope of Δ over epochs, descriptive verdict);
`weight_engine_correlations.csv` (lag-1 Spearman ρ_k(e) → w_k(e+1) per cluster and pooled,
the tautological control against w_k(e+1)/W_k(e+1), R_k vs ρ_k, tie diagnostics);
`weight_engine_traffic_model.csv` (traffic is exogenous: `role_company.sh do_traffic`).

**config**, **manifest**, **notes** (`methodology_notes.csv`).

Campaign: `campaign_summary.csv` (one row per run, ~70 key metrics), `campaign_families.csv`
(single-parameter families, `common.build_families`), `campaign.xlsx` (summary, families,
side-by-side `by_family`, `algorithm_mc`), `sortition_algorithm_validation.csv` (the standalone
Python Monte Carlo of Algorithm 1, 20 000 draws — a test of the formula, not of the binary).

Constants: α = 0.05, Wilson 95 %, Monte Carlo N = 20 000 (GoF, KS, inversion), 10 000 (streaks),
seed 20260905, delay tolerance 1.5 ms.

## 6. Verified model facts (from the outputs)

* The delay recomputed from the logged score with the in-force weight map, `W_tot` and the
  miner's own Φ reproduces the logged delay within 0.6 ms on every candidate row of 21 runs;
  in run5 (tbt 2 s) 9 rounds out of 1823 fail the check (`phase2/manifest.json →
  summary.rounds_delay_mismatch`; 1 round regionale, 4 intercontinentale, 4 nazionale). There
  `W_tot_implied_by_logged_delay` equals another `W_tot` of the same run (the value before or
  after a weight record's confirmation), i.e. one or two miners computed that round with a
  different view of the weight map (e.g. run5/regionale height 259: m2 and m3 used the map
  without m1's record confirmed at height 258).
* Time bar `nTime ≥ parent.nTime + ⌊D⌋`: checked on every measured block of all 24 runs,
  0 violations. No REJECT line anywhere.
* Weight recomputation: the fold reproduces every published weight in run1–run4 and in
  run5 except two end-of-run rows of run5/nazionale (epochs 38–39, already classified [P]
  by the legacy pipeline); run6 has 4–6 mismatches per area (D15 below).
* Φ is identical across the three miners in most rounds; the rounds where it differs are
  counted (`phi_mismatch_rounds`) — the miners' 12-block windows differ when a competing
  block sits at the tip.
* `scheduler_residual_s` ranges from about −1 s to +2.7 s: negative values are the
  ⌊·⌋ of the block timestamp, positive values are the miner loop granularity. This is the
  noise that decides the race (σ_S2 ≈ 0.6 s), two orders of magnitude above the topology
  latency (σ_S1 ≈ 2–56 ms).

## 7. Not computable on this campaign (declared in every sheet)

dump-function effect (`none` in all 24 runs); malus trajectory, Ψ decay and Delay-event
recomputation (registry empty in all 24 runs — the experiments are ideal, without
malicious actors, by design); VRF output `y_i` (not logged; `E_i`, `u_i` are derived);
per-event network latency and jitter (1 s log resolution, jitter `0 us`); packet loss;
per-epoch `weightverifyweights` snapshots (replaced by the `[WeightEngine] epoch N` log lines).

## 8. Discrepancies (reported, not resolved) and decisions

D1–D14 are in §4 of the phase-0 report. Decisions taken with the user on 2026-09-05:
output root `risultati/`, stale `tools/analisi/` removed; pure functions moved to
`common.py`; Θ per the code with Θ_thesis alongside; integer weight per the code; malus
points from the start-up log; σ_S2 primary; MissedTurnRate/BlockSuccessRate as defined above;
run6 in, run7 ignored; KS vs Beta(1,n) plus KS vs exact Monte Carlo; α/N constants as above;
everything in English; `replication_id = 1`.

New findings of this run of the pipeline:

* **D15 — run6 (L = 100) weight recomputation.** In `run6-tbt-10s` some published weights
  are not reproduced by the fold (`recompute_match = 0`) although every node's own
  independent verification reports "all matching". `implied_raw_delta_over_esg_miner`
  is +1 or +2 for m1, i.e. the node counted one or two more transactions of the miner
  address than the reconstruction (traffic + ESG + membership + weight publication +
  reconciliation). `WeightStreamReader::ComputeActivityAndReconciliationForEpoch` counts
  **every** confirmed transaction whose inputs are owned by the address (undo data), so
  any other miner transaction (permission grants, GAS movements) is activity for the node
  but invisible to the reconstruction. Runs with L = 12 are unaffected in this campaign.
  Left open: which transactions those are; resolving it requires listing the miner's
  transactions per epoch from the chain, outside the archived snapshots.
* **D16 — weight-map view divergence.** See §6: around the confirm height of a weight
  record, different miners can compute the same round with different `W_tot`, so the
  candidates of that round are not playing the same game. Observed only at tbt = 2 s.
  Counted per run in `n_rounds_delay_mismatch`; the rows carry the implied `W_tot`.

## 9. Legacy scripts

`tools/analizza_esperimenti.py`, `tools/summary_per_epoca.py`, `tools/collect_metrics.py`
keep working: the first re-imports its pure helpers from `pipeline/common.py` (output verified
byte-identical on run1 before and after the move); `tools/valida_sortition_montecarlo.py` is
invoked unchanged by the campaign step.
