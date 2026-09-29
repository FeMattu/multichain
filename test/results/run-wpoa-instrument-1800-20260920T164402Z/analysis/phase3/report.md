# Functional run report

| | |
|---|---|
| run | `run-wpoa-instrument-1800-20260920T164402Z` |
| chain | `wpoa-instrument-1800` |
| experiment seed | 20260905 |
| final height | 1880 |
| epoch length | 60 blocks |
| setup-first-blocks | 168 |
| epochs measured | [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31] |
| epochs excluded (setup phase) | [1] |
| test constants | alpha=0.05, MC_GOF=20000, MC_STREAK=10000, seed=20260905 |

**Overall: PASS — every critical consistency check holds**

## 1. Consistency checks

Non-regression checks, not hypothesis tests. They exist to fail loudly when the collection or the pipeline has a bug.

| check | critical | result | detail |
|---|---|---|---|
| `registry_weights_finite_and_positive` | yes | PASS | ok: 170664 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 170664 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 36 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 36 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | PASS | ok: every certified address shows a non-zero ESG in the engine's own view |
| `traffic_counts_within_configured_range` | no | PASS | ok: 1043 complete (epoch, node) pairs, every on-chain count inside its configured range (partial first and last epochs excluded) |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 905 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 30 epoch(s) measured past setup-first-blocks ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 344 of 360 validator-epoch Wilson intervals contained the entitled share (18.0 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1376**.
- Goodness of fit rejected in 5 of 31 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 2 | 0.0916 | 0.1486 | 6.73 | 3 | 0.4494 |
| 3 | 0.0943 | 0.1167 | 8.57 | 3 | 0.3333 |
| 4 | 0.0953 | 0.1206 | 8.29 | 4 | 0.3722 |
| 5 | 0.0946 | 0.1239 | 8.07 | 4 | 0.3917 |
| 6 | 0.0938 | 0.1311 | 7.63 | 4 | 0.3917 |
| 7 | 0.0941 | 0.1044 | 9.57 | 4 | 0.2778 |
| 8 | 0.0942 | 0.1289 | 7.76 | 3 | 0.3972 |
| 9 | 0.0938 | 0.0994 | 10.06 | 5 | 0.2361 |
| 10 | 0.0927 | 0.1133 | 8.82 | 4 | 0.3333 |
| 11 | 0.0929 | 0.1189 | 8.41 | 4 | 0.3639 |
| 12 | 0.0950 | 0.1089 | 9.18 | 4 | 0.3000 |
| 13 | 0.0953 | 0.1150 | 8.70 | 4 | 0.3333 |
| 14 | 0.0930 | 0.1050 | 9.52 | 4 | 0.2833 |
| 15 | 0.0942 | 0.1083 | 9.23 | 4 | 0.2833 |
| 16 | 0.0939 | 0.1006 | 9.94 | 4 | 0.2556 |
| 17 | 0.0937 | 0.1122 | 8.91 | 4 | 0.3194 |
| 18 | 0.0942 | 0.1150 | 8.70 | 4 | 0.3306 |
| 19 | 0.0943 | 0.1128 | 8.87 | 4 | 0.3333 |
| 20 | 0.0967 | 0.1067 | 9.38 | 4 | 0.2806 |
| 21 | 0.0951 | 0.1328 | 7.53 | 3 | 0.4083 |
| 22 | 0.0946 | 0.1167 | 8.57 | 4 | 0.3556 |
| 23 | 0.0938 | 0.1178 | 8.49 | 4 | 0.3556 |
| 24 | 0.0922 | 0.0972 | 10.29 | 5 | 0.2222 |
| 25 | 0.0949 | 0.0983 | 10.17 | 5 | 0.2306 |
| 26 | 0.0956 | 0.1128 | 8.87 | 4 | 0.3361 |
| 27 | 0.0949 | 0.1356 | 7.38 | 3 | 0.3944 |
| 28 | 0.0946 | 0.1133 | 8.82 | 4 | 0.3417 |
| 29 | 0.0950 | 0.1061 | 9.42 | 4 | 0.2917 |
| 30 | 0.0944 | 0.1072 | 9.33 | 4 | 0.2944 |
| 31 | 0.0935 | 0.1973 | 5.07 | 2 | 0.6151 |
| all | 0.0939 | 0.0952 | 10.51 | 5 | 0.2111 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = -0.0115, p = 0.8281, n = 360.
- **Gini(published) − Gini(input) trajectory**: slope = 0.000006 over 31 epoch(s) (Spearman rho = 0.0581, p = 0.7564). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
