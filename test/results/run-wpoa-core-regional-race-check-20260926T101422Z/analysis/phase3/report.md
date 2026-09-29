# Functional run report

| | |
|---|---|
| run | `run-wpoa-core-regional-race-check-20260926T101422Z` |
| chain | `wpoa-core-regional-race-check` |
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
| `registry_weights_finite_and_positive` | yes | PASS | ok: 20040 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 20040 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 43 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 35 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | PASS | ok: every certified address shows a non-zero ESG in the engine's own view |
| `traffic_counts_within_configured_range` | no | PASS | ok: 664 complete (epoch, node) pairs, every on-chain count inside its configured range (partial first and last epochs excluded) |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 238 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 18 epoch(s) measured past setup-first-blocks ([4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 88 of 90 validator-epoch Wilson intervals contained the entitled share (4.5 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.2768**.
- Goodness of fit rejected in 0 of 19 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 4 | 0.2162 | 0.2431 | 4.11 | 2 | 0.2500 |
| 5 | 0.2478 | 0.2704 | 3.70 | 2 | 0.3200 |
| 6 | 0.2970 | 0.2896 | 3.45 | 2 | 0.3520 |
| 7 | 0.2247 | 0.2960 | 3.38 | 2 | 0.3840 |
| 8 | 0.2452 | 0.2576 | 3.88 | 2 | 0.2720 |
| 9 | 0.2236 | 0.2480 | 4.03 | 2 | 0.2720 |
| 10 | 0.2425 | 0.2480 | 4.03 | 2 | 0.2720 |
| 11 | 0.2256 | 0.2416 | 4.14 | 2 | 0.2400 |
| 12 | 0.2570 | 0.2704 | 3.70 | 2 | 0.3200 |
| 13 | 0.2545 | 0.3088 | 3.24 | 2 | 0.3680 |
| 14 | 0.2274 | 0.2512 | 3.98 | 2 | 0.2560 |
| 15 | 0.2215 | 0.2736 | 3.65 | 2 | 0.3360 |
| 16 | 0.2256 | 0.2800 | 3.57 | 2 | 0.3200 |
| 17 | 0.2233 | 0.2896 | 3.45 | 2 | 0.3520 |
| 18 | 0.2438 | 0.2608 | 3.83 | 2 | 0.3040 |
| 19 | 0.2605 | 0.2736 | 3.65 | 2 | 0.3360 |
| 20 | 0.2487 | 0.2800 | 3.57 | 2 | 0.3520 |
| 21 | 0.2681 | 0.2336 | 4.28 | 2 | 0.2286 |
| all | 0.2234 | 0.2327 | 4.30 | 2 | 0.2175 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = 0.7737, p = 0.0000, n = 95.
- **Gini(published) − Gini(input) trajectory**: slope = 0.004355 over 20 epoch(s) (Spearman rho = 0.3023, p = 0.1952). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
