# Functional run report

| | |
|---|---|
| run | `run-wpoa-core-regional-20260922T202430Z` |
| chain | `wpoa-core-regional` |
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
| `registry_weights_finite_and_positive` | yes | PASS | ok: 435565 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 435565 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 50 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 35 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | PASS | ok: every certified address shows a non-zero ESG in the engine's own view |
| `traffic_counts_within_configured_range` | no | FAIL | 764 of 3465 (epoch, node) pairs outside range, e.g. company-11 epoch 75: 21 not in [30,60]; company-14 epoch 75: 16 not in [30,60]; company-15 epoch 75: 12 not in [30,60] |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 5094 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 100 epoch(s) measured past setup-first-blocks ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 469 of 500 validator-epoch Wilson intervals contained the entitled share (25.0 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1508**.
- Goodness of fit rejected in 10 of 101 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 2 | 0.2158 | 0.2210 | 4.53 | 2 | 0.1814 |
| 3 | 0.2269 | 0.2180 | 4.59 | 2 | 0.1640 |
| 4 | 0.2318 | 0.2506 | 3.99 | 2 | 0.2760 |
| 5 | 0.2290 | 0.2184 | 4.58 | 2 | 0.1680 |
| 6 | 0.2243 | 0.2114 | 4.73 | 2 | 0.1320 |
| 7 | 0.2223 | 0.2526 | 3.96 | 2 | 0.2640 |
| 8 | 0.2272 | 0.2242 | 4.46 | 2 | 0.1920 |
| 9 | 0.2165 | 0.2374 | 4.21 | 2 | 0.2400 |
| 10 | 0.2172 | 0.2094 | 4.78 | 3 | 0.1120 |
| 11 | 0.2182 | 0.2428 | 4.12 | 2 | 0.2560 |
| 12 | 0.2272 | 0.2410 | 4.15 | 2 | 0.2520 |
| 13 | 0.2165 | 0.2172 | 4.60 | 3 | 0.1480 |
| 14 | 0.2232 | 0.2244 | 4.46 | 2 | 0.1800 |
| 15 | 0.2209 | 0.2598 | 3.85 | 2 | 0.2840 |
| 16 | 0.2226 | 0.2374 | 4.21 | 2 | 0.2400 |
| 17 | 0.2241 | 0.2586 | 3.87 | 2 | 0.3000 |
| 18 | 0.2145 | 0.2256 | 4.43 | 2 | 0.2000 |
| 19 | 0.2216 | 0.2454 | 4.07 | 2 | 0.2640 |
| 20 | 0.2193 | 0.2210 | 4.52 | 2 | 0.1800 |
| 21 | 0.2294 | 0.2626 | 3.81 | 2 | 0.3080 |
| 22 | 0.2245 | 0.2422 | 4.13 | 2 | 0.2440 |
| 23 | 0.2208 | 0.2094 | 4.78 | 3 | 0.1120 |
| 24 | 0.2202 | 0.2464 | 4.06 | 2 | 0.2560 |
| 25 | 0.2253 | 0.2262 | 4.42 | 2 | 0.1960 |
| 26 | 0.2348 | 0.2308 | 4.33 | 2 | 0.2120 |
| 27 | 0.2303 | 0.2272 | 4.40 | 2 | 0.2040 |
| 28 | 0.2218 | 0.2260 | 4.42 | 2 | 0.1920 |
| 29 | 0.2316 | 0.2298 | 4.35 | 2 | 0.1840 |
| 30 | 0.2191 | 0.2412 | 4.15 | 2 | 0.2520 |
| 31 | 0.2266 | 0.2202 | 4.54 | 2 | 0.1720 |
| 32 | 0.2220 | 0.2398 | 4.17 | 2 | 0.2360 |
| 33 | 0.2214 | 0.2496 | 4.01 | 2 | 0.2640 |
| 34 | 0.2259 | 0.2382 | 4.20 | 2 | 0.2360 |
| 35 | 0.2206 | 0.2470 | 4.05 | 2 | 0.2680 |
| 36 | 0.2190 | 0.2282 | 4.38 | 2 | 0.2080 |
| 37 | 0.2290 | 0.2250 | 4.44 | 2 | 0.1880 |
| 38 | 0.2198 | 0.2152 | 4.65 | 3 | 0.1160 |
| 39 | 0.2236 | 0.2304 | 4.34 | 2 | 0.2000 |
| 40 | 0.2169 | 0.2240 | 4.46 | 2 | 0.1920 |
| 41 | 0.2218 | 0.2514 | 3.98 | 2 | 0.2800 |
| 42 | 0.2246 | 0.2522 | 3.97 | 2 | 0.2760 |
| 43 | 0.2332 | 0.2542 | 3.93 | 2 | 0.2880 |
| 44 | 0.2223 | 0.2274 | 4.40 | 2 | 0.2000 |
| 45 | 0.2202 | 0.2286 | 4.37 | 2 | 0.2040 |
| 46 | 0.2282 | 0.2150 | 4.65 | 2 | 0.1480 |
| 47 | 0.2216 | 0.2198 | 4.55 | 2 | 0.1760 |
| 48 | 0.2163 | 0.2190 | 4.57 | 2 | 0.1720 |
| 49 | 0.2193 | 0.2500 | 4.00 | 2 | 0.2760 |
| 50 | 0.2212 | 0.2326 | 4.30 | 2 | 0.2080 |
| 51 | 0.2308 | 0.2426 | 4.12 | 2 | 0.2600 |
| 52 | 0.2210 | 0.2290 | 4.37 | 2 | 0.2120 |
| 53 | 0.2237 | 0.2218 | 4.51 | 2 | 0.1840 |
| 54 | 0.2286 | 0.2204 | 4.54 | 2 | 0.1760 |
| 55 | 0.2291 | 0.2398 | 4.17 | 2 | 0.2360 |
| 56 | 0.2158 | 0.2114 | 4.73 | 3 | 0.1320 |
| 57 | 0.2154 | 0.2266 | 4.41 | 2 | 0.2000 |
| 58 | 0.2196 | 0.2240 | 4.46 | 2 | 0.1920 |
| 59 | 0.2235 | 0.2154 | 4.64 | 2 | 0.1520 |
| 60 | 0.2207 | 0.2682 | 3.73 | 2 | 0.3240 |
| 61 | 0.2149 | 0.2188 | 4.57 | 3 | 0.1440 |
| 62 | 0.2265 | 0.2402 | 4.16 | 2 | 0.2520 |
| 63 | 0.2191 | 0.2318 | 4.31 | 2 | 0.2120 |
| 64 | 0.2203 | 0.2226 | 4.49 | 2 | 0.1880 |
| 65 | 0.2242 | 0.2470 | 4.05 | 2 | 0.2600 |
| 66 | 0.2224 | 0.2112 | 4.73 | 3 | 0.1320 |
| 67 | 0.2216 | 0.2416 | 4.14 | 2 | 0.2400 |
| 68 | 0.2209 | 0.2094 | 4.78 | 3 | 0.1120 |
| 69 | 0.2233 | 0.2306 | 4.34 | 2 | 0.2160 |
| 70 | 0.2178 | 0.2318 | 4.31 | 2 | 0.2120 |
| 71 | 0.2266 | 0.2658 | 3.76 | 2 | 0.3120 |
| 72 | 0.2193 | 0.2102 | 4.76 | 2 | 0.1160 |
| 73 | 0.2222 | 0.2452 | 4.08 | 2 | 0.2680 |
| 74 | 0.2198 | 0.2452 | 4.08 | 2 | 0.2560 |
| 75 | 0.2203 | 0.2354 | 4.25 | 2 | 0.2280 |
| 76 | 0.2233 | 0.2466 | 4.06 | 2 | 0.2680 |
| 77 | 0.2166 | 0.2266 | 4.41 | 2 | 0.1880 |
| 78 | 0.2325 | 0.2274 | 4.40 | 2 | 0.2040 |
| 79 | 0.2217 | 0.2474 | 4.04 | 2 | 0.2680 |
| 80 | 0.2155 | 0.2306 | 4.34 | 2 | 0.2160 |
| 81 | 0.2215 | 0.2266 | 4.41 | 2 | 0.1800 |
| 82 | 0.2212 | 0.2166 | 4.62 | 2 | 0.1600 |
| 83 | 0.2231 | 0.2114 | 4.73 | 3 | 0.1320 |
| 84 | 0.2205 | 0.2348 | 4.26 | 2 | 0.2280 |
| 85 | 0.2288 | 0.2332 | 4.29 | 2 | 0.2280 |
| 86 | 0.2186 | 0.2074 | 4.82 | 3 | 0.1000 |
| 87 | 0.2202 | 0.2472 | 4.05 | 2 | 0.2680 |
| 88 | 0.2212 | 0.2290 | 4.37 | 2 | 0.2120 |
| 89 | 0.2207 | 0.2332 | 4.29 | 2 | 0.2240 |
| 90 | 0.2233 | 0.2550 | 3.92 | 2 | 0.2920 |
| 91 | 0.2279 | 0.2330 | 4.29 | 2 | 0.2200 |
| 92 | 0.2209 | 0.2254 | 4.44 | 2 | 0.2000 |
| 93 | 0.2200 | 0.2292 | 4.36 | 2 | 0.2120 |
| 94 | 0.2249 | 0.2544 | 3.93 | 2 | 0.2880 |
| 95 | 0.2254 | 0.2304 | 4.34 | 2 | 0.2160 |
| 96 | 0.2279 | 0.2248 | 4.45 | 2 | 0.1920 |
| 97 | 0.2160 | 0.2086 | 4.79 | 3 | 0.1160 |
| 98 | 0.2177 | 0.2336 | 4.28 | 2 | 0.2200 |
| 99 | 0.2272 | 0.2446 | 4.09 | 2 | 0.2280 |
| 100 | 0.2212 | 0.2270 | 4.41 | 2 | 0.2040 |
| 101 | 0.2254 | 0.2562 | 3.90 | 2 | 0.2857 |
| all | 0.2211 | 0.2218 | 4.51 | 2 | 0.1792 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = 0.0355, p = 0.4283, n = 500.
- **Gini(published) − Gini(input) trajectory**: slope = 0.000000 over 101 epoch(s) (Spearman rho = -0.0052, p = 0.9590). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
