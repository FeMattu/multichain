# Functional run report

| | |
|---|---|
| run | `run-wpoa-core-intercontinental-20260922T195913Z` |
| chain | `wpoa-core-intercontinental` |
| experiment seed | 20260905 |
| final height | 6659 |
| epoch length | 100 blocks |
| setup-first-blocks | 207 |
| epochs measured | [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66] |
| epochs excluded (setup phase) | [1] |
| test constants | alpha=0.05, MC_GOF=20000, MC_STREAK=10000, seed=20260905 |

**Overall: PASS — every critical consistency check holds**

## 1. Consistency checks

Non-regression checks, not hypothesis tests. They exist to fail loudly when the collection or the pipeline has a bug.

| check | critical | result | detail |
|---|---|---|---|
| `registry_weights_finite_and_positive` | yes | PASS | ok: 545580 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 545580 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 71 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 25 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | PASS | ok: every certified address shows a non-zero ESG in the engine's own view |
| `traffic_counts_within_configured_range` | no | FAIL | 60 of 1600 (epoch, node) pairs outside range, e.g. company-0 epoch 63: 5 not in [30,60]; company-1 epoch 63: 1 not in [30,60]; company-10 epoch 63: 3 not in [30,60] |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 1194 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 65 epoch(s) measured past setup-first-blocks ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 297 of 325 validator-epoch Wilson intervals contained the entitled share (16.2 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1512**.
- Goodness of fit rejected in 9 of 66 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 2 | 0.2065 | 0.2086 | 4.80 | 3 | 0.1125 |
| 3 | 0.2086 | 0.2178 | 4.59 | 2 | 0.1520 |
| 4 | 0.2104 | 0.2310 | 4.33 | 2 | 0.2080 |
| 5 | 0.2071 | 0.2334 | 4.28 | 2 | 0.2280 |
| 6 | 0.2078 | 0.2046 | 4.89 | 3 | 0.0840 |
| 7 | 0.2065 | 0.2216 | 4.51 | 2 | 0.1800 |
| 8 | 0.2064 | 0.2170 | 4.61 | 2 | 0.1640 |
| 9 | 0.2057 | 0.2246 | 4.45 | 2 | 0.1960 |
| 10 | 0.2046 | 0.2304 | 4.34 | 2 | 0.2160 |
| 11 | 0.2057 | 0.2442 | 4.10 | 2 | 0.2560 |
| 12 | 0.2098 | 0.2130 | 4.69 | 3 | 0.1360 |
| 13 | 0.2071 | 0.2130 | 4.69 | 3 | 0.1360 |
| 14 | 0.2064 | 0.2300 | 4.35 | 2 | 0.2080 |
| 15 | 0.2074 | 0.2090 | 4.78 | 2 | 0.1160 |
| 16 | 0.2085 | 0.2286 | 4.37 | 2 | 0.2040 |
| 17 | 0.2071 | 0.2480 | 4.03 | 2 | 0.2560 |
| 18 | 0.2045 | 0.2260 | 4.42 | 2 | 0.2000 |
| 19 | 0.2078 | 0.2064 | 4.84 | 3 | 0.0840 |
| 20 | 0.2089 | 0.2130 | 4.69 | 3 | 0.1360 |
| 21 | 0.2106 | 0.2174 | 4.60 | 2 | 0.1640 |
| 22 | 0.2077 | 0.2226 | 4.49 | 2 | 0.1800 |
| 23 | 0.2061 | 0.2074 | 4.82 | 3 | 0.1000 |
| 24 | 0.2067 | 0.2184 | 4.58 | 2 | 0.1680 |
| 25 | 0.2065 | 0.2266 | 4.41 | 2 | 0.1880 |
| 26 | 0.2105 | 0.2292 | 4.36 | 2 | 0.2080 |
| 27 | 0.2121 | 0.2112 | 4.73 | 2 | 0.1280 |
| 28 | 0.2076 | 0.2178 | 4.59 | 2 | 0.1640 |
| 29 | 0.2103 | 0.2088 | 4.79 | 3 | 0.1120 |
| 30 | 0.2059 | 0.2218 | 4.51 | 2 | 0.1840 |
| 31 | 0.2074 | 0.2184 | 4.58 | 2 | 0.1600 |
| 32 | 0.2085 | 0.2306 | 4.34 | 2 | 0.2200 |
| 33 | 0.2077 | 0.2502 | 4.00 | 2 | 0.2520 |
| 34 | 0.2075 | 0.2034 | 4.92 | 3 | 0.0720 |
| 35 | 0.2044 | 0.2140 | 4.67 | 2 | 0.1480 |
| 36 | 0.2088 | 0.2244 | 4.46 | 2 | 0.1800 |
| 37 | 0.2088 | 0.2366 | 4.23 | 2 | 0.2360 |
| 38 | 0.2073 | 0.2166 | 4.62 | 2 | 0.1560 |
| 39 | 0.2089 | 0.2074 | 4.82 | 3 | 0.1080 |
| 40 | 0.2053 | 0.2410 | 4.15 | 2 | 0.2480 |
| 41 | 0.2068 | 0.2218 | 4.51 | 2 | 0.1840 |
| 42 | 0.2078 | 0.2190 | 4.57 | 2 | 0.1480 |
| 43 | 0.2103 | 0.2166 | 4.62 | 2 | 0.1600 |
| 44 | 0.2074 | 0.2158 | 4.63 | 2 | 0.1480 |
| 45 | 0.2056 | 0.2086 | 4.79 | 3 | 0.1080 |
| 46 | 0.2086 | 0.2140 | 4.67 | 3 | 0.1400 |
| 47 | 0.2073 | 0.2094 | 4.78 | 3 | 0.1120 |
| 48 | 0.2048 | 0.2108 | 4.74 | 3 | 0.1240 |
| 49 | 0.2042 | 0.2186 | 4.57 | 2 | 0.1680 |
| 50 | 0.2052 | 0.2154 | 4.64 | 2 | 0.1520 |
| 51 | 0.2116 | 0.2170 | 4.61 | 2 | 0.1400 |
| 52 | 0.2077 | 0.2248 | 4.45 | 2 | 0.1960 |
| 53 | 0.2071 | 0.2340 | 4.27 | 2 | 0.2160 |
| 54 | 0.2077 | 0.2314 | 4.32 | 2 | 0.2120 |
| 55 | 0.2105 | 0.2224 | 4.50 | 2 | 0.1880 |
| 56 | 0.2051 | 0.2296 | 4.36 | 2 | 0.2160 |
| 57 | 0.2046 | 0.2236 | 4.47 | 2 | 0.1680 |
| 58 | 0.2058 | 0.2146 | 4.66 | 2 | 0.1440 |
| 59 | 0.2078 | 0.2046 | 4.89 | 3 | 0.0840 |
| 60 | 0.2057 | 0.2166 | 4.62 | 3 | 0.1480 |
| 61 | 0.2047 | 0.2216 | 4.51 | 2 | 0.1800 |
| 62 | 0.2068 | 0.2046 | 4.89 | 3 | 0.0800 |
| 63 | 0.2057 | 0.2062 | 4.85 | 3 | 0.0960 |
| 64 | 0.2060 | 0.2310 | 4.33 | 2 | 0.2160 |
| 65 | 0.2084 | 0.2062 | 4.85 | 3 | 0.0960 |
| 66 | 0.2062 | 0.2256 | 4.43 | 2 | 0.1933 |
| all | 0.2069 | 0.2087 | 4.79 | 3 | 0.1130 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = 0.0778, p = 0.1617, n = 325.
- **Gini(published) − Gini(input) trajectory**: slope = 0.000001 over 66 epoch(s) (Spearman rho = 0.0318, p = 0.7997). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
