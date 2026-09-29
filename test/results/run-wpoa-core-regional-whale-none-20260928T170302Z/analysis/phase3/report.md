# Functional run report

| | |
|---|---|
| run | `run-wpoa-core-regional-whale-none-20260928T170302Z` |
| chain | `wpoa-core-regional-whale-none` |
| experiment seed | 20260905 |
| final height | 5120 |
| epoch length | 100 blocks |
| setup-first-blocks | 220 |
| epochs measured | [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51] |
| epochs excluded (setup phase) | [1] |
| test constants | alpha=0.05, MC_GOF=20000, MC_STREAK=10000, seed=20260905 |

**Overall: PASS — every critical consistency check holds**

## 1. Consistency checks

Non-regression checks, not hypothesis tests. They exist to fail loudly when the collection or the pipeline has a bug.

| check | critical | result | detail |
|---|---|---|---|
| `registry_weights_finite_and_positive` | yes | PASS | ok: 198430 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 198430 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 49 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 35 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | FAIL | 2 certified address(es) show no ESG within an epoch: 1PJZEA5mCczfe7gDSUiDNE81j2UipABLaXsGXa, 1XPy45GVqYWF69QD6PCE63cyHj3KeywgzuD5Be |
| `traffic_counts_within_configured_range` | no | PASS | ok: 1615 complete (epoch, node) pairs, every on-chain count inside its configured range (partial first and last epochs excluded) |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 2612 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 50 epoch(s) measured past setup-first-blocks ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 239 of 250 validator-epoch Wilson intervals contained the entitled share (12.5 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1115**.
- Goodness of fit rejected in 1 of 51 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 2 | 0.5467 | 0.4422 | 2.26 | 1 | 0.4660 |
| 3 | 0.5273 | 0.5546 | 1.80 | 1 | 0.5800 |
| 4 | 0.5746 | 0.5702 | 1.75 | 1 | 0.6040 |
| 5 | 0.5502 | 0.5836 | 1.71 | 1 | 0.6160 |
| 6 | 0.5540 | 0.6722 | 1.49 | 1 | 0.6720 |
| 7 | 0.5622 | 0.6108 | 1.64 | 1 | 0.6280 |
| 8 | 0.5471 | 0.4488 | 2.23 | 1 | 0.5040 |
| 9 | 0.5711 | 0.6846 | 1.46 | 1 | 0.6760 |
| 10 | 0.5791 | 0.5568 | 1.80 | 1 | 0.5920 |
| 11 | 0.5486 | 0.6098 | 1.64 | 1 | 0.6240 |
| 12 | 0.5458 | 0.4520 | 2.21 | 1 | 0.5280 |
| 13 | 0.5502 | 0.5418 | 1.85 | 1 | 0.5720 |
| 14 | 0.5700 | 0.5944 | 1.68 | 1 | 0.6000 |
| 15 | 0.5338 | 0.4918 | 2.03 | 1 | 0.5320 |
| 16 | 0.5492 | 0.5166 | 1.94 | 1 | 0.5560 |
| 17 | 0.5595 | 0.5264 | 1.90 | 1 | 0.5400 |
| 18 | 0.5757 | 0.5410 | 1.85 | 1 | 0.5680 |
| 19 | 0.5671 | 0.5422 | 1.84 | 1 | 0.5760 |
| 20 | 0.5356 | 0.6554 | 1.53 | 1 | 0.6640 |
| 21 | 0.5345 | 0.5130 | 1.95 | 1 | 0.5200 |
| 22 | 0.5777 | 0.6106 | 1.64 | 1 | 0.6280 |
| 23 | 0.5537 | 0.5962 | 1.68 | 1 | 0.6160 |
| 24 | 0.6053 | 0.6242 | 1.60 | 1 | 0.6320 |
| 25 | 0.6139 | 0.7786 | 1.28 | 1 | 0.7000 |
| 26 | 0.5600 | 0.6814 | 1.47 | 1 | 0.6440 |
| 27 | 0.5413 | 0.5794 | 1.73 | 1 | 0.5800 |
| 28 | 0.5816 | 0.5338 | 1.87 | 1 | 0.5920 |
| 29 | 0.6067 | 0.5704 | 1.75 | 1 | 0.6000 |
| 30 | 0.5738 | 0.5166 | 1.94 | 1 | 0.5560 |
| 31 | 0.6152 | 0.6398 | 1.56 | 1 | 0.6480 |
| 32 | 0.5606 | 0.5974 | 1.67 | 1 | 0.6240 |
| 33 | 0.5391 | 0.4594 | 2.18 | 1 | 0.5200 |
| 34 | 0.5460 | 0.5514 | 1.81 | 1 | 0.6040 |
| 35 | 0.5951 | 0.6822 | 1.47 | 1 | 0.6520 |
| 36 | 0.5577 | 0.5554 | 1.80 | 1 | 0.5840 |
| 37 | 0.5750 | 0.5706 | 1.75 | 1 | 0.6040 |
| 38 | 0.5545 | 0.6256 | 1.60 | 1 | 0.6400 |
| 39 | 0.5583 | 0.6018 | 1.66 | 1 | 0.6440 |
| 40 | 0.5417 | 0.5074 | 1.97 | 1 | 0.5640 |
| 41 | 0.5177 | 0.4934 | 2.03 | 1 | 0.5440 |
| 42 | 0.5213 | 0.5434 | 1.84 | 1 | 0.5800 |
| 43 | 0.5592 | 0.5034 | 1.99 | 1 | 0.5400 |
| 44 | 0.5632 | 0.5786 | 1.73 | 1 | 0.5680 |
| 45 | 0.5702 | 0.5786 | 1.73 | 1 | 0.5680 |
| 46 | 0.5650 | 0.5366 | 1.86 | 1 | 0.6000 |
| 47 | 0.5553 | 0.6076 | 1.65 | 1 | 0.6000 |
| 48 | 0.5696 | 0.6232 | 1.60 | 1 | 0.6240 |
| 49 | 0.5509 | 0.5726 | 1.75 | 1 | 0.6120 |
| 50 | 0.5518 | 0.6246 | 1.60 | 1 | 0.6360 |
| 51 | 0.5593 | 0.6054 | 1.65 | 1 | 0.6476 |
| all | 0.5598 | 0.5674 | 1.76 | 1 | 0.5841 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = -0.0260, p = 0.6823, n = 250.
- **Gini(published) − Gini(input) trajectory**: slope = -0.000006 over 51 epoch(s) (Spearman rho = -0.1866, p = 0.1898). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
