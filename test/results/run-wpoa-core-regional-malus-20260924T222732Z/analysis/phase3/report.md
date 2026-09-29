# Functional run report

| | |
|---|---|
| run | `run-wpoa-core-regional-malus-20260924T222732Z` |
| chain | `wpoa-core-regional-malus` |
| experiment seed | 20260905 |
| final height | 10120 |
| epoch length | 100 blocks |
| setup-first-blocks | 220 |
| epochs measured | [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101] |
| epochs excluded (setup phase) | [1] |
| test constants | alpha=0.05, MC_GOF=20000, MC_STREAK=10000, seed=20260905 |

**Overall: PASS — every critical consistency check holds**

## 1. Consistency checks

Non-regression checks, not hypothesis tests. They exist to fail loudly when the collection or the pipeline has a bug.

| check | critical | result | detail |
|---|---|---|---|
| `registry_weights_finite_and_positive` | yes | PASS | ok: 409590 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 409590 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 57 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 35 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | PASS | ok: every certified address shows a non-zero ESG in the engine's own view |
| `traffic_counts_within_configured_range` | no | FAIL | 763 of 3465 (epoch, node) pairs outside range, e.g. company-11 epoch 75: 21 not in [30,60]; company-14 epoch 75: 16 not in [30,60]; company-15 epoch 75: 12 not in [30,60] |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 5097 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `malus_psi_in_unit_interval` | yes | PASS | ok: every sampled Psi lies in [0,1] |
| `malus_effective_weight_matches_recompute` | yes | PASS | ok: w_eff = round(w_raw * Psi) in every sample |
| `malus_clean_validator_has_psi_one` | yes | PASS | ok: every validator with no proved malus has Psi = 1 (the mechanism is inert on honest behaviour) |
| `malus_detector_no_false_positives` | yes | PASS | ok: the detector reported no honest record (33 report(s), all against confirmed malicious actions) |
| `malus_confirmed_actions_were_detected` | no | PASS | ok: 33 of 33 confirmed malicious action(s) were recognised as malus |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 100 epoch(s) measured past setup-first-blocks ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 447 of 500 validator-epoch Wilson intervals contained the entitled share (25.0 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1478**.
- Goodness of fit rejected in 11 of 101 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 2 | 0.2158 | 0.2250 | 4.44 | 2 | 0.1895 |
| 3 | 0.2161 | 0.2404 | 4.16 | 2 | 0.2480 |
| 4 | 0.2351 | 0.2688 | 3.72 | 2 | 0.3120 |
| 5 | 0.2325 | 0.2554 | 3.92 | 2 | 0.2920 |
| 6 | 0.2346 | 0.2418 | 4.14 | 2 | 0.2440 |
| 7 | 0.2246 | 0.2538 | 3.94 | 2 | 0.2920 |
| 8 | 0.2363 | 0.2538 | 3.94 | 2 | 0.2920 |
| 9 | 0.2278 | 0.2338 | 4.28 | 2 | 0.2280 |
| 10 | 0.2204 | 0.2316 | 4.32 | 2 | 0.2200 |
| 11 | 0.2245 | 0.2350 | 4.26 | 2 | 0.2360 |
| 12 | 0.2384 | 0.2524 | 3.96 | 2 | 0.2800 |
| 13 | 0.2236 | 0.2720 | 3.68 | 2 | 0.3120 |
| 14 | 0.2175 | 0.2378 | 4.21 | 2 | 0.2360 |
| 15 | 0.2262 | 0.2460 | 4.07 | 2 | 0.2640 |
| 16 | 0.2205 | 0.2428 | 4.12 | 2 | 0.2560 |
| 17 | 0.2235 | 0.2342 | 4.27 | 2 | 0.2240 |
| 18 | 0.2232 | 0.2320 | 4.31 | 2 | 0.2200 |
| 19 | 0.2196 | 0.2202 | 4.54 | 2 | 0.1760 |
| 20 | 0.2240 | 0.2534 | 3.95 | 2 | 0.2720 |
| 21 | 0.3512 | 0.4030 | 2.48 | 1 | 0.4480 |
| 22 | 0.2080 | 0.2130 | 4.69 | 2 | 0.1400 |
| 23 | 0.2201 | 0.2162 | 4.63 | 2 | 0.1560 |
| 24 | 0.2600 | 0.2454 | 4.07 | 2 | 0.2400 |
| 25 | 0.2288 | 0.2420 | 4.13 | 2 | 0.2520 |
| 26 | 0.3456 | 0.3644 | 2.74 | 1 | 0.4440 |
| 27 | 0.2833 | 0.3124 | 3.20 | 2 | 0.3640 |
| 28 | 0.2143 | 0.2338 | 4.28 | 2 | 0.2120 |
| 29 | 0.2677 | 0.2806 | 3.56 | 2 | 0.3440 |
| 30 | 0.2597 | 0.2564 | 3.90 | 2 | 0.2880 |
| 31 | 0.2589 | 0.2598 | 3.85 | 2 | 0.3080 |
| 32 | 0.2639 | 0.2746 | 3.64 | 2 | 0.3400 |
| 33 | 0.2278 | 0.2384 | 4.19 | 2 | 0.2400 |
| 34 | 0.2354 | 0.2674 | 3.74 | 2 | 0.3200 |
| 35 | 0.2572 | 0.2420 | 4.13 | 2 | 0.2440 |
| 36 | 0.2219 | 0.2178 | 4.59 | 2 | 0.1640 |
| 37 | 0.2771 | 0.3488 | 2.87 | 1 | 0.3920 |
| 38 | 0.2322 | 0.2394 | 4.18 | 2 | 0.2360 |
| 39 | 0.2461 | 0.2524 | 3.96 | 2 | 0.2800 |
| 40 | 0.2217 | 0.2280 | 4.39 | 2 | 0.2000 |
| 41 | 0.2281 | 0.2404 | 4.16 | 2 | 0.2240 |
| 42 | 0.2604 | 0.2936 | 3.41 | 2 | 0.3760 |
| 43 | 0.2617 | 0.2658 | 3.76 | 2 | 0.3240 |
| 44 | 0.2648 | 0.3108 | 3.22 | 2 | 0.3840 |
| 45 | 0.2275 | 0.2254 | 4.44 | 2 | 0.1960 |
| 46 | 0.3072 | 0.3806 | 2.63 | 1 | 0.4760 |
| 47 | 0.2487 | 0.3084 | 3.24 | 2 | 0.3400 |
| 48 | 0.2695 | 0.2606 | 3.84 | 2 | 0.2880 |
| 49 | 0.2475 | 0.2898 | 3.45 | 2 | 0.3560 |
| 50 | 0.2372 | 0.2488 | 4.02 | 2 | 0.2720 |
| 51 | 0.2570 | 0.2574 | 3.89 | 2 | 0.2800 |
| 52 | 0.2496 | 0.2280 | 4.39 | 2 | 0.1920 |
| 53 | 0.2460 | 0.2294 | 4.36 | 2 | 0.2120 |
| 54 | 0.2411 | 0.3102 | 3.22 | 2 | 0.3720 |
| 55 | 0.3031 | 0.4030 | 2.48 | 1 | 0.4480 |
| 56 | 0.2455 | 0.3102 | 3.22 | 2 | 0.3720 |
| 57 | 0.2716 | 0.2888 | 3.46 | 2 | 0.3320 |
| 58 | 0.2176 | 0.2234 | 4.48 | 2 | 0.1880 |
| 59 | 0.2529 | 0.2614 | 3.83 | 2 | 0.3040 |
| 60 | 0.2974 | 0.3078 | 3.25 | 2 | 0.3960 |
| 61 | 0.2269 | 0.2656 | 3.77 | 2 | 0.3000 |
| 62 | 0.2259 | 0.2384 | 4.19 | 2 | 0.2240 |
| 63 | 0.2336 | 0.2666 | 3.75 | 2 | 0.3000 |
| 64 | 0.2215 | 0.2258 | 4.43 | 2 | 0.1960 |
| 65 | 0.2322 | 0.2486 | 4.02 | 2 | 0.2680 |
| 66 | 0.2253 | 0.2362 | 4.23 | 2 | 0.2320 |
| 67 | 0.2319 | 0.2540 | 3.94 | 2 | 0.2880 |
| 68 | 0.2249 | 0.2214 | 4.52 | 2 | 0.1800 |
| 69 | 0.2298 | 0.2186 | 4.57 | 2 | 0.1640 |
| 70 | 0.2260 | 0.2450 | 4.08 | 2 | 0.2600 |
| 71 | 0.2346 | 0.2642 | 3.79 | 2 | 0.3120 |
| 72 | 0.2144 | 0.2152 | 4.65 | 3 | 0.1160 |
| 73 | 0.2231 | 0.2256 | 4.43 | 2 | 0.1920 |
| 74 | 0.2248 | 0.2812 | 3.56 | 2 | 0.3280 |
| 75 | 0.2241 | 0.2490 | 4.02 | 2 | 0.2720 |
| 76 | 0.2304 | 0.2468 | 4.05 | 2 | 0.2640 |
| 77 | 0.2257 | 0.2220 | 4.50 | 3 | 0.1560 |
| 78 | 0.2302 | 0.2646 | 3.78 | 2 | 0.3080 |
| 79 | 0.2294 | 0.2580 | 3.88 | 2 | 0.2960 |
| 80 | 0.2236 | 0.2520 | 3.97 | 2 | 0.2640 |
| 81 | 0.2191 | 0.2284 | 4.38 | 2 | 0.2120 |
| 82 | 0.2200 | 0.2232 | 4.48 | 2 | 0.1840 |
| 83 | 0.2253 | 0.2396 | 4.17 | 2 | 0.2320 |
| 84 | 0.2207 | 0.2176 | 4.60 | 2 | 0.1600 |
| 85 | 0.2265 | 0.2380 | 4.20 | 2 | 0.2400 |
| 86 | 0.2178 | 0.2646 | 3.78 | 2 | 0.3160 |
| 87 | 0.2245 | 0.2224 | 4.50 | 2 | 0.1800 |
| 88 | 0.2239 | 0.2666 | 3.75 | 2 | 0.3120 |
| 89 | 0.2211 | 0.2324 | 4.30 | 2 | 0.2160 |
| 90 | 0.2246 | 0.2196 | 4.55 | 2 | 0.1760 |
| 91 | 0.2311 | 0.2276 | 4.39 | 2 | 0.2040 |
| 92 | 0.2260 | 0.2470 | 4.05 | 2 | 0.2600 |
| 93 | 0.2136 | 0.2418 | 4.14 | 2 | 0.2520 |
| 94 | 0.2180 | 0.2260 | 4.42 | 2 | 0.1960 |
| 95 | 0.2270 | 0.2184 | 4.58 | 2 | 0.1600 |
| 96 | 0.2271 | 0.2728 | 3.67 | 2 | 0.3280 |
| 97 | 0.2214 | 0.2536 | 3.94 | 2 | 0.2680 |
| 98 | 0.2129 | 0.2406 | 4.16 | 2 | 0.2440 |
| 99 | 0.2186 | 0.2424 | 4.13 | 2 | 0.2520 |
| 100 | 0.2297 | 0.2854 | 3.50 | 2 | 0.3400 |
| 101 | 0.2400 | 0.2653 | 3.77 | 2 | 0.3048 |
| all | 0.2185 | 0.2216 | 4.51 | 2 | 0.1836 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = 0.3449, p = 0.0000, n = 500.
- **Gini(published) − Gini(input) trajectory**: slope = 0.000024 over 101 epoch(s) (Spearman rho = 0.0161, p = 0.8730). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 7b. Malicious miners and the malus

> **Full detail: [`malus_effectiveness.md`](malus_effectiveness.md).** The summary below is the short form.

- Injection rate: target **0.400**, realised (attempted) **0.402** — on target: yes.
- Funnel: 82 opportunities → 33 attempts → 33 confirmed → 33 valid malus.
- Detection: precision **1.000**, recall **1.000**, F1 **1.000** (false positives: 0).
- Invariant violations: Psi∉[0,1] 0, w_eff mismatch 0, clean-but-penalised 0.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
