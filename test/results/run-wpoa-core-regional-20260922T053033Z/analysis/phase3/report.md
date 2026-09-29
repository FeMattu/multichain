# Functional run report

| | |
|---|---|
| run | `run-wpoa-core-regional-20260922T053033Z` |
| chain | `wpoa-core-regional` |
| experiment seed | 20260905 |
| final height | 2884 |
| epoch length | 150 blocks |
| setup-first-blocks | 277 |
| epochs measured | [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19] |
| epochs excluded (setup phase) | none |
| test constants | alpha=0.05, MC_GOF=20000, MC_STREAK=10000, seed=20260905 |

**Overall: PASS — every critical consistency check holds**

## 1. Consistency checks

Non-regression checks, not hypothesis tests. They exist to fail loudly when the collection or the pipeline has a bug.

| check | critical | result | detail |
|---|---|---|---|
| `registry_weights_finite_and_positive` | yes | PASS | ok: 175855 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 175855 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 64 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 25 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | PASS | ok: every certified address shows a non-zero ESG in the engine's own view |
| `traffic_counts_within_configured_range` | no | PASS | ok: 424 complete (epoch, node) pairs, every on-chain count inside its configured range (partial first and last epochs excluded) |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 970 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 19 epoch(s) measured past setup-first-blocks ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 85 of 95 validator-epoch Wilson intervals contained the entitled share (4.8 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1244**.
- Goodness of fit rejected in 4 of 20 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 1 | 0.2195 | 0.2230 | 4.48 | 2 | 0.1915 |
| 2 | 0.2157 | 0.2126 | 4.70 | 2 | 0.1333 |
| 3 | 0.2338 | 0.2272 | 4.40 | 2 | 0.2053 |
| 4 | 0.2329 | 0.2628 | 3.80 | 2 | 0.3093 |
| 5 | 0.2323 | 0.2540 | 3.94 | 2 | 0.2907 |
| 6 | 0.2275 | 0.2326 | 4.30 | 2 | 0.2213 |
| 7 | 0.2291 | 0.2546 | 3.93 | 2 | 0.2640 |
| 8 | 0.2333 | 0.2326 | 4.30 | 2 | 0.2267 |
| 9 | 0.2228 | 0.2412 | 4.15 | 2 | 0.2480 |
| 10 | 0.2210 | 0.2178 | 4.59 | 2 | 0.1600 |
| 11 | 0.2251 | 0.2252 | 4.44 | 2 | 0.1787 |
| 12 | 0.2363 | 0.2328 | 4.30 | 2 | 0.2213 |
| 13 | 0.2188 | 0.2300 | 4.35 | 2 | 0.2133 |
| 14 | 0.2267 | 0.2321 | 4.31 | 2 | 0.2160 |
| 15 | 0.2227 | 0.2476 | 4.04 | 2 | 0.2640 |
| 16 | 0.2271 | 0.2256 | 4.43 | 2 | 0.1867 |
| 17 | 0.2266 | 0.2264 | 4.42 | 2 | 0.2027 |
| 18 | 0.2167 | 0.2242 | 4.46 | 2 | 0.1920 |
| 19 | 0.2214 | 0.2392 | 4.18 | 2 | 0.2400 |
| all | 0.2241 | 0.2240 | 4.46 | 2 | 0.1917 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = 0.1264, p = 0.2352, n = 90.
- **Gini(published) − Gini(input) trajectory**: slope = 0.000016 over 19 epoch(s) (Spearman rho = 0.0456, p = 0.8529). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
