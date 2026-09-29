# Functional run report

| | |
|---|---|
| run | `run-wpoa-core-regional-rho-swap-20260929T143616Z` |
| chain | `wpoa-core-regional-rho-swap` |
| experiment seed | 20260905 |
| final height | 3120 |
| epoch length | 100 blocks |
| setup-first-blocks | 220 |
| epochs measured | [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31] |
| epochs excluded (setup phase) | [1] |
| test constants | alpha=0.05, MC_GOF=20000, MC_STREAK=10000, seed=20260905 |

**Overall: PASS — every critical consistency check holds**

## 1. Consistency checks

Non-regression checks, not hypothesis tests. They exist to fail loudly when the collection or the pipeline has a bug.

| check | critical | result | detail |
|---|---|---|---|
| `registry_weights_finite_and_positive` | yes | PASS | ok: 119980 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 119980 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 47 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 35 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | PASS | ok: every certified address shows a non-zero ESG in the engine's own view |
| `traffic_counts_within_configured_range` | no | PASS | ok: 1015 complete (epoch, node) pairs, every on-chain count inside its configured range (partial first and last epochs excluded) |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 1565 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 30 epoch(s) measured past setup-first-blocks ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 142 of 150 validator-epoch Wilson intervals contained the entitled share (7.5 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1475**.
- Goodness of fit rejected in 1 of 31 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 2 | 0.2155 | 0.2090 | 4.79 | 3 | 0.1125 |
| 3 | 0.2271 | 0.2456 | 4.07 | 2 | 0.2600 |
| 4 | 0.2524 | 0.2278 | 4.39 | 2 | 0.1960 |
| 5 | 0.2612 | 0.2738 | 3.65 | 2 | 0.3320 |
| 6 | 0.2439 | 0.2430 | 4.12 | 2 | 0.2480 |
| 7 | 0.2398 | 0.2398 | 4.17 | 2 | 0.2440 |
| 8 | 0.2414 | 0.2470 | 4.05 | 2 | 0.2560 |
| 9 | 0.2449 | 0.2470 | 4.05 | 2 | 0.2560 |
| 10 | 0.2300 | 0.2134 | 4.69 | 2 | 0.1440 |
| 11 | 0.2313 | 0.2182 | 4.58 | 2 | 0.1680 |
| 12 | 0.2392 | 0.2670 | 3.75 | 2 | 0.3160 |
| 13 | 0.2553 | 0.2744 | 3.64 | 2 | 0.3240 |
| 14 | 0.2292 | 0.2386 | 4.19 | 2 | 0.2200 |
| 15 | 0.2384 | 0.2596 | 3.85 | 2 | 0.2680 |
| 16 | 0.2235 | 0.2502 | 4.00 | 2 | 0.2760 |
| 17 | 0.2615 | 0.2766 | 3.62 | 2 | 0.3400 |
| 18 | 0.2646 | 0.2824 | 3.54 | 2 | 0.3400 |
| 19 | 0.2676 | 0.2766 | 3.62 | 2 | 0.3320 |
| 20 | 0.2945 | 0.2826 | 3.54 | 2 | 0.3320 |
| 21 | 0.2701 | 0.2528 | 3.96 | 2 | 0.2840 |
| 22 | 0.2710 | 0.2982 | 3.35 | 2 | 0.3640 |
| 23 | 0.2721 | 0.2858 | 3.50 | 2 | 0.3680 |
| 24 | 0.2802 | 0.2690 | 3.72 | 2 | 0.3280 |
| 25 | 0.2942 | 0.3042 | 3.29 | 2 | 0.3680 |
| 26 | 0.2751 | 0.2566 | 3.90 | 2 | 0.2920 |
| 27 | 0.2731 | 0.2910 | 3.44 | 2 | 0.3640 |
| 28 | 0.2747 | 0.2734 | 3.66 | 2 | 0.3120 |
| 29 | 0.2524 | 0.2530 | 3.95 | 2 | 0.2680 |
| 30 | 0.2676 | 0.2730 | 3.66 | 2 | 0.3280 |
| 31 | 0.2579 | 0.3107 | 3.22 | 2 | 0.3810 |
| all | 0.2203 | 0.2184 | 4.58 | 2 | 0.1591 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = 0.7543, p = 0.0000, n = 150.
- **Gini(published) − Gini(input) trajectory**: slope = 0.003455 over 31 epoch(s) (Spearman rho = 0.6036, p = 0.0003). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 7c. Controlled experiment on rho

> **Full detail: [`rho_contrast.md`](rho_contrast.md).** Some miners were given their own restitution behaviour (`traffic.miner_return_overrides`); the winners are tested against the weights WITH the rho feedback and against the same weights with the feedback factor removed.

- Likelihood ratio feedback vs no feedback: LLR = 207.83, p of 'rho has no effect' = 0.000050 (20.0 sd from that null); quantile under feedback 0.432.
- Null **with rho feedback**, all rounds: chi-square = 1.61, round-by-round Monte-Carlo p = 0.7993 (2900 rounds).
- Null **without rho feedback**, all rounds: chi-square = 25.13, round-by-round Monte-Carlo p = 0.0002 (2900 rounds).
- Null **with rho feedback**, period 1 (miner-1 phase 0, miner-3 phase 0): chi-square = 1.56, round-by-round Monte-Carlo p = 0.8209 (86 rounds).
- Null **without rho feedback**, period 1 (miner-1 phase 0, miner-3 phase 0): chi-square = 1.56, round-by-round Monte-Carlo p = 0.8209 (86 rounds).
- Null **with rho feedback**, period 2 (miner-1 phase 1, miner-3 phase 1): chi-square = 1.78, round-by-round Monte-Carlo p = 0.7754 (1400 rounds).
- Null **without rho feedback**, period 2 (miner-1 phase 1, miner-3 phase 1): chi-square = 171.55, round-by-round Monte-Carlo p = 0.0001 (1400 rounds).
- Null **with rho feedback**, period 3 (miner-1 phase 2, miner-3 phase 2): chi-square = 1.49, round-by-round Monte-Carlo p = 0.8283 (1414 rounds).
- Null **without rho feedback**, period 3 (miner-1 phase 2, miner-3 phase 2): chi-square = 152.21, round-by-round Monte-Carlo p = 0.0001 (1414 rounds).

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
