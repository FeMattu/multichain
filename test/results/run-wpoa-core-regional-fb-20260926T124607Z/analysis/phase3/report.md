# Functional run report

| | |
|---|---|
| run | `run-wpoa-core-regional-fb-20260926T124607Z` |
| chain | `wpoa-core-regional-fb` |
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
| `registry_weights_finite_and_positive` | yes | PASS | ok: 387465 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 387465 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 51 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 35 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | PASS | ok: every certified address shows a non-zero ESG in the engine's own view |
| `traffic_counts_within_configured_range` | no | FAIL | 666 of 3360 (epoch, node) pairs outside range, e.g. company-0 epoch 78: 12 not in [30,60]; company-1 epoch 78: 5 not in [30,60]; company-10 epoch 78: 7 not in [30,60] |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 5069 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 100 epoch(s) measured past setup-first-blocks ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 474 of 500 validator-epoch Wilson intervals contained the entitled share (25.0 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1504**.
- Goodness of fit rejected in 5 of 101 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 2 | 0.2184 | 0.2310 | 4.33 | 2 | 0.2189 |
| 3 | 0.2188 | 0.2242 | 4.46 | 2 | 0.1760 |
| 4 | 0.2378 | 0.2398 | 4.17 | 2 | 0.2480 |
| 5 | 0.2386 | 0.2290 | 4.37 | 2 | 0.2120 |
| 6 | 0.2403 | 0.2606 | 3.84 | 2 | 0.3000 |
| 7 | 0.2255 | 0.2210 | 4.52 | 2 | 0.1760 |
| 8 | 0.2397 | 0.2638 | 3.79 | 2 | 0.3120 |
| 9 | 0.2324 | 0.2514 | 3.98 | 2 | 0.2800 |
| 10 | 0.2236 | 0.2266 | 4.41 | 2 | 0.2000 |
| 11 | 0.2265 | 0.2220 | 4.50 | 2 | 0.1760 |
| 12 | 0.2423 | 0.2382 | 4.20 | 2 | 0.2280 |
| 13 | 0.2279 | 0.2494 | 4.01 | 2 | 0.2440 |
| 14 | 0.2188 | 0.2494 | 4.01 | 2 | 0.2720 |
| 15 | 0.2276 | 0.2228 | 4.49 | 2 | 0.1880 |
| 16 | 0.2250 | 0.2370 | 4.22 | 2 | 0.2360 |
| 17 | 0.2248 | 0.2142 | 4.67 | 2 | 0.1480 |
| 18 | 0.2284 | 0.2194 | 4.56 | 2 | 0.1720 |
| 19 | 0.2265 | 0.2236 | 4.47 | 2 | 0.1920 |
| 20 | 0.2275 | 0.2320 | 4.31 | 2 | 0.2200 |
| 21 | 0.2306 | 0.2450 | 4.08 | 2 | 0.2600 |
| 22 | 0.2316 | 0.2258 | 4.43 | 2 | 0.1720 |
| 23 | 0.2207 | 0.2384 | 4.19 | 2 | 0.2400 |
| 24 | 0.2153 | 0.2196 | 4.55 | 2 | 0.1680 |
| 25 | 0.2431 | 0.2362 | 4.23 | 2 | 0.2360 |
| 26 | 0.2477 | 0.2448 | 4.08 | 2 | 0.2640 |
| 27 | 0.2401 | 0.2460 | 4.07 | 2 | 0.2640 |
| 28 | 0.2195 | 0.2354 | 4.25 | 2 | 0.2360 |
| 29 | 0.2359 | 0.2206 | 4.53 | 2 | 0.1720 |
| 30 | 0.2307 | 0.2576 | 3.88 | 2 | 0.2960 |
| 31 | 0.2316 | 0.2282 | 4.38 | 2 | 0.2040 |
| 32 | 0.2389 | 0.2428 | 4.12 | 2 | 0.2560 |
| 33 | 0.2194 | 0.2150 | 4.65 | 2 | 0.1520 |
| 34 | 0.2266 | 0.2416 | 4.14 | 2 | 0.2480 |
| 35 | 0.2244 | 0.2202 | 4.54 | 2 | 0.1760 |
| 36 | 0.2273 | 0.2496 | 4.01 | 2 | 0.2680 |
| 37 | 0.2209 | 0.2170 | 4.61 | 2 | 0.1600 |
| 38 | 0.2287 | 0.2368 | 4.22 | 2 | 0.2320 |
| 39 | 0.2254 | 0.2584 | 3.87 | 2 | 0.3000 |
| 40 | 0.2149 | 0.2226 | 4.49 | 2 | 0.1840 |
| 41 | 0.2272 | 0.2366 | 4.23 | 2 | 0.2240 |
| 42 | 0.2345 | 0.2340 | 4.27 | 2 | 0.2320 |
| 43 | 0.2398 | 0.2746 | 3.64 | 2 | 0.3400 |
| 44 | 0.2320 | 0.2526 | 3.96 | 2 | 0.2880 |
| 45 | 0.2209 | 0.2194 | 4.56 | 2 | 0.1720 |
| 46 | 0.2362 | 0.2466 | 4.06 | 2 | 0.2680 |
| 47 | 0.2362 | 0.2296 | 4.36 | 2 | 0.2120 |
| 48 | 0.2184 | 0.2158 | 4.63 | 2 | 0.1520 |
| 49 | 0.2182 | 0.2420 | 4.13 | 2 | 0.2520 |
| 50 | 0.2212 | 0.2252 | 4.44 | 2 | 0.1960 |
| 51 | 0.2362 | 0.2562 | 3.90 | 2 | 0.2880 |
| 52 | 0.2274 | 0.2214 | 4.52 | 2 | 0.1800 |
| 53 | 0.2222 | 0.2220 | 4.50 | 2 | 0.1800 |
| 54 | 0.2409 | 0.2374 | 4.21 | 2 | 0.2240 |
| 55 | 0.2479 | 0.2368 | 4.22 | 2 | 0.2240 |
| 56 | 0.2212 | 0.2516 | 3.97 | 2 | 0.2800 |
| 57 | 0.2354 | 0.2350 | 4.26 | 2 | 0.2080 |
| 58 | 0.2111 | 0.2104 | 4.75 | 3 | 0.1200 |
| 59 | 0.2266 | 0.2280 | 4.39 | 2 | 0.2000 |
| 60 | 0.2287 | 0.2266 | 4.41 | 2 | 0.2000 |
| 61 | 0.2202 | 0.2220 | 4.50 | 3 | 0.1560 |
| 62 | 0.2320 | 0.2806 | 3.56 | 2 | 0.3560 |
| 63 | 0.2351 | 0.2342 | 4.27 | 2 | 0.2280 |
| 64 | 0.2278 | 0.2264 | 4.42 | 2 | 0.2000 |
| 65 | 0.2250 | 0.2196 | 4.55 | 2 | 0.1760 |
| 66 | 0.2277 | 0.2316 | 4.32 | 2 | 0.2240 |
| 67 | 0.2288 | 0.2314 | 4.32 | 2 | 0.2120 |
| 68 | 0.2291 | 0.2318 | 4.31 | 2 | 0.2120 |
| 69 | 0.2249 | 0.2270 | 4.41 | 2 | 0.1840 |
| 70 | 0.2257 | 0.2146 | 4.66 | 2 | 0.1480 |
| 71 | 0.2542 | 0.2650 | 3.77 | 2 | 0.3160 |
| 72 | 0.2245 | 0.2226 | 4.49 | 2 | 0.1800 |
| 73 | 0.2320 | 0.2412 | 4.15 | 2 | 0.2520 |
| 74 | 0.2247 | 0.2450 | 4.08 | 2 | 0.2640 |
| 75 | 0.2210 | 0.2202 | 4.54 | 3 | 0.1560 |
| 76 | 0.2293 | 0.2446 | 4.09 | 2 | 0.2600 |
| 77 | 0.2272 | 0.2510 | 3.98 | 2 | 0.2640 |
| 78 | 0.2393 | 0.2664 | 3.75 | 2 | 0.3200 |
| 79 | 0.2337 | 0.2154 | 4.64 | 2 | 0.1520 |
| 80 | 0.2282 | 0.2186 | 4.57 | 2 | 0.1640 |
| 81 | 0.2197 | 0.2450 | 4.08 | 2 | 0.2680 |
| 82 | 0.2209 | 0.2646 | 3.78 | 2 | 0.2760 |
| 83 | 0.2259 | 0.2496 | 4.01 | 2 | 0.2480 |
| 84 | 0.2265 | 0.2370 | 4.22 | 2 | 0.2360 |
| 85 | 0.2302 | 0.2410 | 4.15 | 2 | 0.2520 |
| 86 | 0.2226 | 0.2238 | 4.47 | 2 | 0.1880 |
| 87 | 0.2252 | 0.2414 | 4.14 | 2 | 0.2520 |
| 88 | 0.2346 | 0.2426 | 4.12 | 2 | 0.2480 |
| 89 | 0.2319 | 0.2186 | 4.57 | 2 | 0.1680 |
| 90 | 0.2228 | 0.2242 | 4.46 | 2 | 0.1920 |
| 91 | 0.2371 | 0.2566 | 3.90 | 2 | 0.2920 |
| 92 | 0.2185 | 0.2398 | 4.17 | 2 | 0.2440 |
| 93 | 0.2246 | 0.2342 | 4.27 | 2 | 0.2280 |
| 94 | 0.2220 | 0.2110 | 4.74 | 2 | 0.1280 |
| 95 | 0.2233 | 0.2418 | 4.14 | 2 | 0.2520 |
| 96 | 0.2279 | 0.2292 | 4.36 | 2 | 0.2080 |
| 97 | 0.2252 | 0.2118 | 4.72 | 2 | 0.1360 |
| 98 | 0.2236 | 0.2344 | 4.27 | 2 | 0.2240 |
| 99 | 0.2231 | 0.2184 | 4.58 | 2 | 0.1680 |
| 100 | 0.2309 | 0.2576 | 3.88 | 2 | 0.2960 |
| 101 | 0.2394 | 0.2336 | 4.28 | 2 | 0.2095 |
| all | 0.2245 | 0.2237 | 4.47 | 2 | 0.1846 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = 0.3358, p = 0.0000, n = 500.
- **Gini(published) − Gini(input) trajectory**: slope = 0.000019 over 101 epoch(s) (Spearman rho = -0.0192, p = 0.8492). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
