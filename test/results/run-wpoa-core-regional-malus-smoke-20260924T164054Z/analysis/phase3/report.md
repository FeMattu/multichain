# Functional run report

| | |
|---|---|
| run | `run-wpoa-core-regional-malus-smoke-20260924T164054Z` |
| chain | `wpoa-core-regional-malus-smoke` |
| experiment seed | 20260905 |
| final height | 545 |
| epoch length | 25 blocks |
| setup-first-blocks | 108 |
| epochs measured | [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21] |
| epochs excluded (setup phase) | [1, 2, 3] |
| test constants | alpha=0.05, MC_GOF=20000, MC_STREAK=10000, seed=20260905 |

**Overall: PASS — every critical consistency check holds**

## 1. Consistency checks

Non-regression checks, not hypothesis tests. They exist to fail loudly when the collection or the pipeline has a bug.

| check | critical | result | detail |
|---|---|---|---|
| `registry_weights_finite_and_positive` | yes | PASS | ok: 22455 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 22455 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 35 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 35 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | FAIL | 2 certified address(es) show no ESG within an epoch: 1LsmVLtuqM1Auxgd5iTNtrcYiH3TLbsjaLGUTD, 1WVD5ht5v4Mfh5Zo8orZEZJUrTGZf3B6Nuo9o9 |
| `traffic_counts_within_configured_range` | no | PASS | ok: 626 complete (epoch, node) pairs, every on-chain count inside its configured range (partial first and last epochs excluded) |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 238 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `malus_psi_in_unit_interval` | yes | PASS | ok: every sampled Psi lies in [0,1] |
| `malus_effective_weight_matches_recompute` | yes | PASS | ok: w_eff = round(w_raw * Psi) in every sample |
| `malus_clean_validator_has_psi_one` | yes | PASS | ok: every validator with no proved malus has Psi = 1 (the mechanism is inert on honest behaviour) |
| `malus_detector_no_false_positives` | yes | PASS | ok: the detector reported no honest record (11 report(s), all against confirmed malicious actions) |
| `malus_confirmed_actions_were_detected` | no | PASS | ok: 11 of 11 confirmed malicious action(s) were recognised as malus |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 18 epoch(s) measured past setup-first-blocks ([4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 79 of 90 validator-epoch Wilson intervals contained the entitled share (4.5 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.2613**.
- Goodness of fit rejected in 2 of 19 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 4 | 0.2177 | 0.2650 | 3.77 | 2 | 0.3000 |
| 5 | 0.2766 | 0.3664 | 2.73 | 2 | 0.4800 |
| 6 | 0.2948 | 0.3408 | 2.93 | 2 | 0.4480 |
| 7 | 0.2862 | 0.3536 | 2.83 | 2 | 0.4800 |
| 8 | 0.2766 | 0.3632 | 2.75 | 1 | 0.4640 |
| 9 | 0.3066 | 0.3056 | 3.27 | 2 | 0.4000 |
| 10 | 0.3273 | 0.3984 | 2.51 | 1 | 0.5280 |
| 11 | 0.3306 | 0.3504 | 2.85 | 1 | 0.4480 |
| 12 | 0.3368 | 0.3792 | 2.64 | 1 | 0.4640 |
| 13 | 0.2657 | 0.3312 | 3.02 | 2 | 0.4480 |
| 14 | 0.3344 | 0.3216 | 3.11 | 2 | 0.4320 |
| 15 | 0.2858 | 0.3600 | 2.78 | 2 | 0.4800 |
| 16 | 0.2385 | 0.2736 | 3.65 | 2 | 0.3360 |
| 17 | 0.2155 | 0.2800 | 3.57 | 2 | 0.3200 |
| 18 | 0.2408 | 0.3120 | 3.21 | 2 | 0.3840 |
| 19 | 0.2427 | 0.2512 | 3.98 | 2 | 0.2560 |
| 20 | 0.2515 | 0.2992 | 3.34 | 2 | 0.3680 |
| 21 | 0.2832 | 0.3832 | 2.61 | 1 | 0.4571 |
| all | 0.2167 | 0.2243 | 4.46 | 2 | 0.1941 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = 0.7949, p = 0.0000, n = 100.
- **Gini(published) − Gini(input) trajectory**: slope = 0.003863 over 21 epoch(s) (Spearman rho = 0.3286, p = 0.1459). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 7b. Malicious miners and the malus

> **Full detail: [`malus_effectiveness.md`](malus_effectiveness.md).** The summary below is the short form.

- Injection rate: target **0.800**, realised (attempted) **0.812** — on target: yes.
- Funnel: 16 opportunities → 13 attempts → 11 confirmed → 11 valid malus.
- Detection: precision **1.000**, recall **1.000**, F1 **1.000** (false positives: 0).
- Invariant violations: Psi∉[0,1] 0, w_eff mismatch 0, clean-but-penalised 0.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
