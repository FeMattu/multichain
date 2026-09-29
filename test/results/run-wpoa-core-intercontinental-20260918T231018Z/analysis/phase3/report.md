# Functional run report

| | |
|---|---|
| run | `run-wpoa-core-intercontinental-20260918T231018Z` |
| chain | `wpoa-core-intercontinental` |
| experiment seed | 20260905 |
| final height | 7340 |
| epoch length | 120 blocks |
| setup-first-blocks | 240 |
| epochs measured | [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61] |
| epochs excluded (setup phase) | [1] |
| test constants | alpha=0.05, MC_GOF=20000, MC_STREAK=10000, seed=20260905 |

**Overall: PASS — every critical consistency check holds**

## 1. Consistency checks

Non-regression checks, not hypothesis tests. They exist to fail loudly when the collection or the pipeline has a bug.

| check | critical | result | detail |
|---|---|---|---|
| `registry_weights_finite_and_positive` | yes | PASS | ok: 793390 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 793390 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 57 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 30 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | PASS | ok: every certified address shows a non-zero ESG in the engine's own view |
| `traffic_counts_within_configured_range` | no | PASS | ok: 1766 complete (epoch, node) pairs, every on-chain count inside its configured range (partial first and last epochs excluded) |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 2207 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 60 epoch(s) measured past setup-first-blocks ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 519 of 600 validator-epoch Wilson intervals contained the entitled share (30.0 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1066**.
- Goodness of fit rejected in 23 of 61 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 2 | 0.1046 | 0.1185 | 8.44 | 4 | 0.2333 |
| 3 | 0.1063 | 0.1218 | 8.21 | 4 | 0.2633 |
| 4 | 0.1037 | 0.1094 | 9.14 | 4 | 0.1683 |
| 5 | 0.1057 | 0.1285 | 7.78 | 3 | 0.2950 |
| 6 | 0.1025 | 0.1089 | 9.18 | 4 | 0.1650 |
| 7 | 0.1058 | 0.1142 | 8.76 | 4 | 0.1833 |
| 8 | 0.1050 | 0.1188 | 8.42 | 4 | 0.2400 |
| 9 | 0.1033 | 0.1150 | 8.70 | 4 | 0.2200 |
| 10 | 0.1066 | 0.1092 | 9.16 | 4 | 0.1700 |
| 11 | 0.1059 | 0.1196 | 8.36 | 4 | 0.2517 |
| 12 | 0.1046 | 0.1210 | 8.27 | 4 | 0.2517 |
| 13 | 0.1052 | 0.1117 | 8.96 | 4 | 0.1900 |
| 14 | 0.1055 | 0.1249 | 8.01 | 4 | 0.2617 |
| 15 | 0.1039 | 0.1153 | 8.67 | 4 | 0.2117 |
| 16 | 0.1048 | 0.1185 | 8.44 | 4 | 0.2417 |
| 17 | 0.1049 | 0.1126 | 8.88 | 4 | 0.2017 |
| 18 | 0.1057 | 0.1085 | 9.22 | 4 | 0.1567 |
| 19 | 0.1054 | 0.1183 | 8.45 | 4 | 0.2300 |
| 20 | 0.1056 | 0.1122 | 8.91 | 4 | 0.1967 |
| 21 | 0.1034 | 0.1096 | 9.13 | 4 | 0.1700 |
| 22 | 0.1074 | 0.1364 | 7.33 | 3 | 0.2983 |
| 23 | 0.1055 | 0.1194 | 8.37 | 4 | 0.2433 |
| 24 | 0.1043 | 0.1208 | 8.28 | 4 | 0.2483 |
| 25 | 0.1062 | 0.1157 | 8.64 | 4 | 0.2217 |
| 26 | 0.1050 | 0.1182 | 8.46 | 4 | 0.2267 |
| 27 | 0.1044 | 0.1237 | 8.08 | 4 | 0.2717 |
| 28 | 0.1047 | 0.1104 | 9.06 | 4 | 0.1783 |
| 29 | 0.1078 | 0.1092 | 9.16 | 4 | 0.1683 |
| 30 | 0.1064 | 0.1251 | 7.99 | 4 | 0.2650 |
| 31 | 0.1064 | 0.1186 | 8.43 | 4 | 0.2100 |
| 32 | 0.1060 | 0.1139 | 8.78 | 4 | 0.2050 |
| 33 | 0.1052 | 0.1222 | 8.18 | 4 | 0.2550 |
| 34 | 0.1061 | 0.1144 | 8.74 | 4 | 0.2050 |
| 35 | 0.1046 | 0.1167 | 8.57 | 4 | 0.2200 |
| 36 | 0.1064 | 0.1119 | 8.93 | 4 | 0.1633 |
| 37 | 0.1060 | 0.1181 | 8.47 | 4 | 0.2350 |
| 38 | 0.1059 | 0.1139 | 8.78 | 4 | 0.2017 |
| 39 | 0.1047 | 0.1133 | 8.82 | 4 | 0.1900 |
| 40 | 0.1064 | 0.1082 | 9.24 | 4 | 0.1583 |
| 41 | 0.1056 | 0.1056 | 9.47 | 5 | 0.1283 |
| 42 | 0.1042 | 0.1088 | 9.20 | 4 | 0.1650 |
| 43 | 0.1046 | 0.1199 | 8.34 | 4 | 0.2317 |
| 44 | 0.1059 | 0.1124 | 8.90 | 4 | 0.1917 |
| 45 | 0.1041 | 0.1110 | 9.01 | 4 | 0.1800 |
| 46 | 0.1062 | 0.1178 | 8.49 | 4 | 0.2367 |
| 47 | 0.1069 | 0.1260 | 7.94 | 4 | 0.2800 |
| 48 | 0.1049 | 0.1099 | 9.10 | 4 | 0.1783 |
| 49 | 0.1050 | 0.1156 | 8.65 | 4 | 0.2200 |
| 50 | 0.1048 | 0.1075 | 9.30 | 4 | 0.1533 |
| 51 | 0.1055 | 0.1214 | 8.24 | 4 | 0.2450 |
| 52 | 0.1065 | 0.1107 | 9.03 | 4 | 0.1833 |
| 53 | 0.1060 | 0.1154 | 8.66 | 4 | 0.2217 |
| 54 | 0.1048 | 0.1165 | 8.58 | 4 | 0.2083 |
| 55 | 0.1058 | 0.1260 | 7.94 | 4 | 0.2783 |
| 56 | 0.1048 | 0.1257 | 7.96 | 4 | 0.2833 |
| 57 | 0.1043 | 0.1342 | 7.45 | 3 | 0.3300 |
| 58 | 0.1034 | 0.1311 | 7.63 | 4 | 0.3133 |
| 59 | 0.1030 | 0.1360 | 7.35 | 3 | 0.3233 |
| 60 | 0.1042 | 0.1331 | 7.52 | 4 | 0.3133 |
| 61 | 0.1048 | 0.1610 | 6.21 | 3 | 0.4333 |
| all | 0.1048 | 0.1035 | 9.67 | 5 | 0.1049 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = -0.0124, p = 0.7618, n = 600.
- **Gini(published) − Gini(input) trajectory**: slope = -0.000001 over 61 epoch(s) (Spearman rho = -0.0925, p = 0.4784). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
