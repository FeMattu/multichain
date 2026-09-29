# Functional run report

| | |
|---|---|
| run | `run-wpoa-long24h-large-log-20260918T235047Z` |
| chain | `wpoa-long24h-large-log` |
| experiment seed | 20260905 |
| final height | 10120 |
| epoch length | 100 blocks |
| setup-first-blocks | 210 |
| epochs measured | [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101] |
| epochs excluded (setup phase) | [1] |
| test constants | alpha=0.05, MC_GOF=20000, MC_STREAK=10000, seed=20260905 |

**Overall: PASS — every critical consistency check holds**

## 1. Consistency checks

Non-regression checks, not hypothesis tests. They exist to fail loudly when the collection or the pipeline has a bug.

| check | critical | result | detail |
|---|---|---|---|
| `registry_weights_finite_and_positive` | yes | PASS | ok: 1035430 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 1035430 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 68 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 30 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | PASS | ok: every certified address shows a non-zero ESG in the engine's own view |
| `traffic_counts_within_configured_range` | no | PASS | ok: 2969 complete (epoch, node) pairs, every on-chain count inside its configured range (partial first and last epochs excluded) |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 2498 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 100 epoch(s) measured past setup-first-blocks ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 920 of 1000 validator-epoch Wilson intervals contained the entitled share (50.0 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1175**.
- Goodness of fit rejected in 15 of 101 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 2 | 0.1002 | 0.1100 | 9.09 | 4 | 0.1800 |
| 3 | 0.1002 | 0.1194 | 8.38 | 4 | 0.2380 |
| 4 | 0.1002 | 0.1102 | 9.07 | 4 | 0.1740 |
| 5 | 0.1002 | 0.1094 | 9.14 | 4 | 0.1600 |
| 6 | 0.1002 | 0.1134 | 8.82 | 4 | 0.1940 |
| 7 | 0.1002 | 0.1090 | 9.17 | 4 | 0.1700 |
| 8 | 0.1002 | 0.1124 | 8.90 | 4 | 0.1980 |
| 9 | 0.1002 | 0.1064 | 9.40 | 5 | 0.1400 |
| 10 | 0.1002 | 0.1076 | 9.29 | 4 | 0.1520 |
| 11 | 0.1002 | 0.1082 | 9.24 | 4 | 0.1600 |
| 12 | 0.1002 | 0.1104 | 9.06 | 4 | 0.1740 |
| 13 | 0.1001 | 0.1124 | 8.90 | 4 | 0.1980 |
| 14 | 0.1002 | 0.1058 | 9.45 | 5 | 0.1320 |
| 15 | 0.1001 | 0.1082 | 9.24 | 4 | 0.1580 |
| 16 | 0.1001 | 0.1192 | 8.39 | 4 | 0.2500 |
| 17 | 0.1002 | 0.1054 | 9.49 | 5 | 0.1260 |
| 18 | 0.1002 | 0.1090 | 9.17 | 4 | 0.1640 |
| 19 | 0.1001 | 0.1110 | 9.01 | 4 | 0.1820 |
| 20 | 0.1002 | 0.1096 | 9.12 | 4 | 0.1720 |
| 21 | 0.1001 | 0.1112 | 8.99 | 4 | 0.1880 |
| 22 | 0.1002 | 0.1080 | 9.26 | 4 | 0.1540 |
| 23 | 0.1002 | 0.1090 | 9.17 | 4 | 0.1600 |
| 24 | 0.1002 | 0.1110 | 9.01 | 4 | 0.1680 |
| 25 | 0.1002 | 0.1070 | 9.35 | 5 | 0.1420 |
| 26 | 0.1002 | 0.1136 | 8.80 | 4 | 0.2040 |
| 27 | 0.1001 | 0.1066 | 9.38 | 4 | 0.1440 |
| 28 | 0.1002 | 0.1134 | 8.82 | 4 | 0.1920 |
| 29 | 0.1001 | 0.1076 | 9.29 | 4 | 0.1560 |
| 30 | 0.1001 | 0.1294 | 7.73 | 3 | 0.2960 |
| 31 | 0.1002 | 0.1120 | 8.93 | 4 | 0.1960 |
| 32 | 0.1002 | 0.1050 | 9.52 | 5 | 0.1240 |
| 33 | 0.1002 | 0.1106 | 9.04 | 4 | 0.1780 |
| 34 | 0.1002 | 0.1040 | 9.62 | 5 | 0.1120 |
| 35 | 0.1001 | 0.1228 | 8.14 | 4 | 0.2720 |
| 36 | 0.1002 | 0.1104 | 9.06 | 4 | 0.1780 |
| 37 | 0.1001 | 0.1220 | 8.20 | 4 | 0.2500 |
| 38 | 0.1002 | 0.1210 | 8.26 | 4 | 0.2360 |
| 39 | 0.1002 | 0.1070 | 9.35 | 5 | 0.1420 |
| 40 | 0.1002 | 0.1056 | 9.47 | 5 | 0.1300 |
| 41 | 0.1001 | 0.1102 | 9.07 | 4 | 0.1800 |
| 42 | 0.1002 | 0.1104 | 9.06 | 4 | 0.1780 |
| 43 | 0.1002 | 0.1128 | 8.87 | 4 | 0.2000 |
| 44 | 0.1002 | 0.1158 | 8.64 | 4 | 0.2200 |
| 45 | 0.1001 | 0.1092 | 9.16 | 4 | 0.1640 |
| 46 | 0.1001 | 0.1104 | 9.06 | 4 | 0.1660 |
| 47 | 0.1002 | 0.1132 | 8.83 | 4 | 0.2040 |
| 48 | 0.1001 | 0.1160 | 8.62 | 4 | 0.2160 |
| 49 | 0.1002 | 0.1118 | 8.94 | 4 | 0.1940 |
| 50 | 0.1002 | 0.1084 | 9.23 | 4 | 0.1620 |
| 51 | 0.1002 | 0.1100 | 9.09 | 4 | 0.1760 |
| 52 | 0.1002 | 0.1054 | 9.49 | 5 | 0.1320 |
| 53 | 0.1002 | 0.1114 | 8.98 | 4 | 0.1860 |
| 54 | 0.1002 | 0.1028 | 9.73 | 5 | 0.0920 |
| 55 | 0.1001 | 0.1066 | 9.38 | 5 | 0.1380 |
| 56 | 0.1002 | 0.1172 | 8.53 | 4 | 0.2160 |
| 57 | 0.1001 | 0.1170 | 8.55 | 4 | 0.2320 |
| 58 | 0.1002 | 0.1170 | 8.55 | 4 | 0.1960 |
| 59 | 0.1002 | 0.1102 | 9.07 | 4 | 0.1820 |
| 60 | 0.1001 | 0.1104 | 9.06 | 4 | 0.1800 |
| 61 | 0.1002 | 0.1160 | 8.62 | 4 | 0.2140 |
| 62 | 0.1002 | 0.1136 | 8.80 | 4 | 0.2080 |
| 63 | 0.1001 | 0.1114 | 8.98 | 4 | 0.1720 |
| 64 | 0.1001 | 0.1230 | 8.13 | 4 | 0.2700 |
| 65 | 0.1002 | 0.1036 | 9.65 | 5 | 0.1060 |
| 66 | 0.1001 | 0.1180 | 8.47 | 4 | 0.2240 |
| 67 | 0.1002 | 0.1116 | 8.96 | 4 | 0.1900 |
| 68 | 0.1002 | 0.1274 | 7.85 | 3 | 0.2820 |
| 69 | 0.1002 | 0.1104 | 9.06 | 4 | 0.1800 |
| 70 | 0.1002 | 0.1078 | 9.28 | 4 | 0.1580 |
| 71 | 0.1002 | 0.1118 | 8.94 | 4 | 0.1880 |
| 72 | 0.1002 | 0.1246 | 8.03 | 4 | 0.2740 |
| 73 | 0.1002 | 0.1124 | 8.90 | 4 | 0.1920 |
| 74 | 0.1002 | 0.1084 | 9.23 | 4 | 0.1460 |
| 75 | 0.1002 | 0.1170 | 8.55 | 4 | 0.2260 |
| 76 | 0.1002 | 0.1188 | 8.42 | 4 | 0.2440 |
| 77 | 0.1002 | 0.1098 | 9.11 | 4 | 0.1760 |
| 78 | 0.1002 | 0.1146 | 8.73 | 4 | 0.2160 |
| 79 | 0.1002 | 0.1116 | 8.96 | 4 | 0.1920 |
| 80 | 0.1001 | 0.1080 | 9.26 | 4 | 0.1520 |
| 81 | 0.1002 | 0.1172 | 8.53 | 4 | 0.2320 |
| 82 | 0.1002 | 0.1138 | 8.79 | 4 | 0.1940 |
| 83 | 0.1002 | 0.1106 | 9.04 | 4 | 0.1840 |
| 84 | 0.1002 | 0.1092 | 9.16 | 4 | 0.1620 |
| 85 | 0.1001 | 0.1100 | 9.09 | 4 | 0.1760 |
| 86 | 0.1002 | 0.1102 | 9.07 | 4 | 0.1780 |
| 87 | 0.1002 | 0.1090 | 9.17 | 4 | 0.1700 |
| 88 | 0.1001 | 0.1056 | 9.47 | 5 | 0.1340 |
| 89 | 0.1002 | 0.1106 | 9.04 | 4 | 0.1800 |
| 90 | 0.1002 | 0.1094 | 9.14 | 4 | 0.1720 |
| 91 | 0.1001 | 0.1136 | 8.80 | 4 | 0.1920 |
| 92 | 0.1001 | 0.1156 | 8.65 | 4 | 0.1920 |
| 93 | 0.1002 | 0.1052 | 9.51 | 5 | 0.1220 |
| 94 | 0.1002 | 0.1196 | 8.36 | 4 | 0.2480 |
| 95 | 0.1002 | 0.1136 | 8.80 | 4 | 0.2040 |
| 96 | 0.1002 | 0.1136 | 8.80 | 4 | 0.2080 |
| 97 | 0.1001 | 0.1164 | 8.59 | 4 | 0.2260 |
| 98 | 0.1001 | 0.1116 | 8.96 | 4 | 0.1920 |
| 99 | 0.1001 | 0.1350 | 7.41 | 3 | 0.3240 |
| 100 | 0.1002 | 0.1146 | 8.73 | 4 | 0.2120 |
| 101 | 0.1001 | 0.1519 | 6.58 | 3 | 0.4048 |
| all | 0.1002 | 0.1004 | 9.96 | 5 | 0.0376 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = -0.0317, p = 0.3167, n = 1000.
- **Gini(published) − Gini(input) trajectory**: slope = -0.000000 over 101 epoch(s) (Spearman rho = -0.0695, p = 0.4896). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
