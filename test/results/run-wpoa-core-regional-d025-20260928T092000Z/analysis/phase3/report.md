# Functional run report

| | |
|---|---|
| run | `run-wpoa-core-regional-d025-20260928T092000Z` |
| chain | `wpoa-core-regional-d025` |
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
| `registry_weights_finite_and_positive` | yes | PASS | ok: 119235 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 119235 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 26 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 35 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | FAIL | 3 certified address(es) show no ESG within an epoch: 169uUsUD5WHiZDe4XWFik7Cn1fRuqy52xfdCU9, 1AD2QV77gDq5DKY1JvDH7a7inAjJzSsEFZU6es, 1ARMkiQTg8nEokD9Ld2yhQAxAVBZDDYVjuVMgK |
| `traffic_counts_within_configured_range` | no | PASS | ok: 927 complete (epoch, node) pairs, every on-chain count inside its configured range (partial first and last epochs excluded) |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 1563 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 30 epoch(s) measured past setup-first-blocks ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 139 of 150 validator-epoch Wilson intervals contained the entitled share (7.5 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1501**.
- Goodness of fit rejected in 2 of 31 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 2 | 0.2162 | 0.2374 | 4.21 | 2 | 0.2440 |
| 3 | 0.2064 | 0.2164 | 4.62 | 2 | 0.1600 |
| 4 | 0.2391 | 0.2374 | 4.21 | 2 | 0.2440 |
| 5 | 0.2406 | 0.2586 | 3.87 | 2 | 0.2880 |
| 6 | 0.2629 | 0.2874 | 3.48 | 2 | 0.3480 |
| 7 | 0.2329 | 0.2400 | 4.17 | 2 | 0.2520 |
| 8 | 0.2526 | 0.2488 | 4.02 | 2 | 0.2560 |
| 9 | 0.2536 | 0.2646 | 3.78 | 2 | 0.3040 |
| 10 | 0.2373 | 0.2220 | 4.50 | 2 | 0.1800 |
| 11 | 0.2448 | 0.2474 | 4.04 | 2 | 0.2520 |
| 12 | 0.2545 | 0.2694 | 3.71 | 2 | 0.3200 |
| 13 | 0.2571 | 0.2710 | 3.69 | 2 | 0.3080 |
| 14 | 0.2193 | 0.2116 | 4.73 | 2 | 0.1320 |
| 15 | 0.2330 | 0.2516 | 3.97 | 2 | 0.2800 |
| 16 | 0.2279 | 0.2342 | 4.27 | 2 | 0.2280 |
| 17 | 0.2241 | 0.2562 | 3.90 | 2 | 0.2680 |
| 18 | 0.2393 | 0.2530 | 3.95 | 2 | 0.2760 |
| 19 | 0.2292 | 0.2244 | 4.46 | 2 | 0.1920 |
| 20 | 0.2362 | 0.2392 | 4.18 | 2 | 0.2480 |
| 21 | 0.2491 | 0.2454 | 4.07 | 2 | 0.2440 |
| 22 | 0.2613 | 0.2762 | 3.62 | 2 | 0.2960 |
| 23 | 0.2168 | 0.2656 | 3.77 | 2 | 0.3000 |
| 24 | 0.2134 | 0.2090 | 4.78 | 3 | 0.1160 |
| 25 | 0.3008 | 0.2802 | 3.57 | 2 | 0.2880 |
| 26 | 0.2869 | 0.3210 | 3.12 | 2 | 0.3960 |
| 27 | 0.2519 | 0.2246 | 4.45 | 2 | 0.1920 |
| 28 | 0.2253 | 0.2248 | 4.45 | 2 | 0.1960 |
| 29 | 0.2320 | 0.2060 | 4.85 | 3 | 0.0960 |
| 30 | 0.2515 | 0.2954 | 3.39 | 2 | 0.3480 |
| 31 | 0.2436 | 0.2426 | 4.12 | 2 | 0.2095 |
| all | 0.2285 | 0.2255 | 4.44 | 2 | 0.1979 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = 0.5726, p = 0.0000, n = 150.
- **Gini(published) − Gini(input) trajectory**: slope = 0.000384 over 31 epoch(s) (Spearman rho = 0.0125, p = 0.9468). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
