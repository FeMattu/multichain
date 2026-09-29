# Functional run report

| | |
|---|---|
| run | `run-wpoa-core-regional-d075-20260929T052357Z` |
| chain | `wpoa-core-regional-d075` |
| experiment seed | 20260905 |
| final height | 3120 |
| epoch length | 100 blocks |
| setup-first-blocks | 220 |
| epochs measured | [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31] |
| epochs excluded (setup phase) | [1] |
| test constants | alpha=0.05, MC_GOF=20000, MC_STREAK=10000, seed=20260905 |

**Overall: PASS — every critical consistency check holds**

## 1. Consistency checks

Non-regression checks, not hypothesis tests. They exist to fail loudly when the collection or the pipeline has a bug.

| check | critical | result | detail |
|---|---|---|---|
| `registry_weights_finite_and_positive` | yes | PASS | ok: 119945 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 119945 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 67 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 35 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | FAIL | 1 certified address(es) show no ESG within an epoch: 18Vk8VF65N7QcMQNfB1MKCBCQUZZYpM54z1K33 |
| `traffic_counts_within_configured_range` | no | PASS | ok: 983 complete (epoch, node) pairs, every on-chain count inside its configured range (partial first and last epochs excluded) |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 1562 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 30 epoch(s) measured past setup-first-blocks ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 140 of 150 validator-epoch Wilson intervals contained the entitled share (7.5 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1497**.
- Goodness of fit rejected in 5 of 31 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 2 | 0.2167 | 0.2138 | 4.68 | 2 | 0.1374 |
| 3 | 0.2081 | 0.2214 | 4.52 | 2 | 0.1800 |
| 4 | 0.2402 | 0.2262 | 4.42 | 2 | 0.1960 |
| 5 | 0.2506 | 0.3026 | 3.30 | 2 | 0.3640 |
| 6 | 0.2573 | 0.3174 | 3.15 | 2 | 0.4200 |
| 7 | 0.2394 | 0.2402 | 4.16 | 2 | 0.2440 |
| 8 | 0.2513 | 0.2860 | 3.50 | 2 | 0.3560 |
| 9 | 0.2502 | 0.2376 | 4.21 | 2 | 0.2400 |
| 10 | 0.2304 | 0.2528 | 3.96 | 2 | 0.2720 |
| 11 | 0.2391 | 0.2634 | 3.80 | 2 | 0.3080 |
| 12 | 0.2559 | 0.2824 | 3.54 | 2 | 0.3400 |
| 13 | 0.2463 | 0.2422 | 4.13 | 2 | 0.2480 |
| 14 | 0.2167 | 0.2230 | 4.48 | 2 | 0.1760 |
| 15 | 0.2332 | 0.2452 | 4.08 | 2 | 0.2560 |
| 16 | 0.2238 | 0.2620 | 3.82 | 2 | 0.3000 |
| 17 | 0.2264 | 0.2306 | 4.34 | 2 | 0.2200 |
| 18 | 0.2399 | 0.2194 | 4.56 | 2 | 0.1640 |
| 19 | 0.2289 | 0.2254 | 4.44 | 2 | 0.1920 |
| 20 | 0.2396 | 0.2546 | 3.93 | 2 | 0.2800 |
| 21 | 0.2371 | 0.2504 | 3.99 | 2 | 0.2800 |
| 22 | 0.2535 | 0.2762 | 3.62 | 2 | 0.2960 |
| 23 | 0.2186 | 0.2290 | 4.37 | 2 | 0.2000 |
| 24 | 0.2135 | 0.2198 | 4.55 | 2 | 0.1720 |
| 25 | 0.2860 | 0.3004 | 3.33 | 2 | 0.3560 |
| 26 | 0.2732 | 0.2764 | 3.62 | 2 | 0.3400 |
| 27 | 0.2451 | 0.2722 | 3.67 | 2 | 0.3320 |
| 28 | 0.2197 | 0.2290 | 4.37 | 2 | 0.2000 |
| 29 | 0.2313 | 0.2266 | 4.41 | 2 | 0.2000 |
| 30 | 0.2455 | 0.2742 | 3.65 | 2 | 0.3040 |
| 31 | 0.2397 | 0.2200 | 4.55 | 2 | 0.1714 |
| all | 0.2255 | 0.2257 | 4.43 | 2 | 0.1990 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = 0.5961, p = 0.0000, n = 150.
- **Gini(published) − Gini(input) trajectory**: slope = 0.000132 over 31 epoch(s) (Spearman rho = -0.0726, p = 0.6980). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
