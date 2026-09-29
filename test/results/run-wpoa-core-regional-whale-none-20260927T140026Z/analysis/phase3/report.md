# Functional run report

| | |
|---|---|
| run | `run-wpoa-core-regional-whale-none-20260927T140026Z` |
| chain | `wpoa-core-regional-whale-none` |
| experiment seed | 20260905 |
| final height | 1625 |
| epoch length | 100 blocks |
| setup-first-blocks | 220 |
| epochs measured | [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16] |
| epochs excluded (setup phase) | [1] |
| test constants | alpha=0.05, MC_GOF=20000, MC_STREAK=10000, seed=20260905 |

**Overall: PASS — every critical consistency check holds**

## 1. Consistency checks

Non-regression checks, not hypothesis tests. They exist to fail loudly when the collection or the pipeline has a bug.

| check | critical | result | detail |
|---|---|---|---|
| `registry_weights_finite_and_positive` | yes | PASS | ok: 60875 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 60875 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 44 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 35 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | FAIL | 2 certified address(es) show no ESG within an epoch: 1EKW9gXoGtAKabb3kS7BjVBccWrjthEk6LMern, 1EWs2GdeMYzdkkHNmSd75k55141LFq9rjL3Jz7 |
| `traffic_counts_within_configured_range` | no | PASS | ok: 459 complete (epoch, node) pairs, every on-chain count inside its configured range (partial first and last epochs excluded) |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 807 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 15 epoch(s) measured past setup-first-blocks ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 71 of 75 validator-epoch Wilson intervals contained the entitled share (3.8 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1103**.
- Goodness of fit rejected in 2 of 16 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 2 | 0.5852 | 0.4648 | 2.15 | 1 | 0.5440 |
| 3 | 0.5641 | 0.5072 | 1.97 | 1 | 0.5520 |
| 4 | 0.6102 | 0.6832 | 1.46 | 1 | 0.6640 |
| 5 | 0.5908 | 0.6226 | 1.61 | 1 | 0.6200 |
| 6 | 0.5723 | 0.5568 | 1.80 | 1 | 0.5920 |
| 7 | 0.5979 | 0.4938 | 2.03 | 1 | 0.5480 |
| 8 | 0.5735 | 0.5046 | 1.98 | 1 | 0.5480 |
| 9 | 0.5927 | 0.6420 | 1.56 | 1 | 0.6600 |
| 10 | 0.6121 | 0.5856 | 1.71 | 1 | 0.6240 |
| 11 | 0.5773 | 0.6214 | 1.61 | 1 | 0.6040 |
| 12 | 0.5891 | 0.6418 | 1.56 | 1 | 0.6560 |
| 13 | 0.5677 | 0.5606 | 1.78 | 1 | 0.6280 |
| 14 | 0.5744 | 0.6320 | 1.58 | 1 | 0.6720 |
| 15 | 0.5557 | 0.6402 | 1.56 | 1 | 0.6520 |
| 16 | 0.5763 | 0.5888 | 1.70 | 1 | 0.6769 |
| all | 0.5825 | 0.5770 | 1.73 | 1 | 0.6031 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = 0.0544, p = 0.6431, n = 75.
- **Gini(published) − Gini(input) trajectory**: slope = 0.000009 over 16 epoch(s) (Spearman rho = 0.1692, p = 0.5309). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
