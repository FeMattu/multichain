# Functional run report

| | |
|---|---|
| run | `run-wpoa-core-regional-whale-sqrt-20260927T182156Z` |
| chain | `wpoa-core-regional-whale-sqrt` |
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
| `registry_weights_finite_and_positive` | yes | PASS | ok: 198085 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 198085 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | PASS | ok: the recomputed delay matches the logged one in every round (tolerance 0.0015 s) |
| `phi_consistent` | no | FAIL | 45 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 35 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | FAIL | 3 certified address(es) show no ESG within an epoch: 19phZk4ZHRrHDNuYzAsvrBybBv4E7Z7KcgfbmC, 1Bo9jQwLbt1AkXcefS2rBVqvGpaYUxT1esRBAx, 1VhPXKJEjqNvLG6zen55tYP2eGdVLFtCwKYyLQ |
| `traffic_counts_within_configured_range` | no | PASS | ok: 1565 complete (epoch, node) pairs, every on-chain count inside its configured range (partial first and last epochs excluded) |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 2609 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 50 epoch(s) measured past setup-first-blocks ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 237 of 250 validator-epoch Wilson intervals contained the entitled share (12.5 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1438**.
- Goodness of fit rejected in 4 of 51 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 2 | 0.2808 | 0.2780 | 3.60 | 2 | 0.2949 |
| 3 | 0.2759 | 0.3114 | 3.21 | 2 | 0.3600 |
| 4 | 0.2876 | 0.2870 | 3.48 | 2 | 0.3480 |
| 5 | 0.2795 | 0.2510 | 3.98 | 2 | 0.2560 |
| 6 | 0.2857 | 0.3458 | 2.89 | 1 | 0.4360 |
| 7 | 0.2841 | 0.2486 | 4.02 | 2 | 0.2600 |
| 8 | 0.2793 | 0.3676 | 2.72 | 1 | 0.4240 |
| 9 | 0.2841 | 0.2766 | 3.62 | 2 | 0.3000 |
| 10 | 0.2859 | 0.3062 | 3.27 | 2 | 0.3560 |
| 11 | 0.2790 | 0.3074 | 3.25 | 2 | 0.3640 |
| 12 | 0.2825 | 0.3582 | 2.79 | 1 | 0.4120 |
| 13 | 0.2788 | 0.2566 | 3.90 | 2 | 0.2400 |
| 14 | 0.2832 | 0.2686 | 3.72 | 2 | 0.2680 |
| 15 | 0.2765 | 0.2650 | 3.77 | 2 | 0.2960 |
| 16 | 0.2802 | 0.3458 | 2.89 | 1 | 0.3720 |
| 17 | 0.2844 | 0.2948 | 3.39 | 2 | 0.3240 |
| 18 | 0.2901 | 0.3294 | 3.04 | 1 | 0.3920 |
| 19 | 0.2868 | 0.3566 | 2.80 | 1 | 0.4000 |
| 20 | 0.2766 | 0.2656 | 3.77 | 2 | 0.3000 |
| 21 | 0.2791 | 0.2698 | 3.71 | 2 | 0.3160 |
| 22 | 0.2924 | 0.3376 | 2.96 | 1 | 0.3640 |
| 23 | 0.2849 | 0.2824 | 3.54 | 2 | 0.3080 |
| 24 | 0.2976 | 0.3184 | 3.14 | 2 | 0.3920 |
| 25 | 0.2980 | 0.3150 | 3.17 | 1 | 0.3440 |
| 26 | 0.2858 | 0.3456 | 2.89 | 1 | 0.3680 |
| 27 | 0.2779 | 0.2918 | 3.43 | 2 | 0.2880 |
| 28 | 0.2941 | 0.3050 | 3.28 | 2 | 0.3480 |
| 29 | 0.2947 | 0.3014 | 3.32 | 2 | 0.3600 |
| 30 | 0.2876 | 0.3218 | 3.11 | 1 | 0.3440 |
| 31 | 0.3031 | 0.3216 | 3.11 | 1 | 0.3440 |
| 32 | 0.2803 | 0.3620 | 2.76 | 1 | 0.4320 |
| 33 | 0.2760 | 0.2956 | 3.38 | 2 | 0.3280 |
| 34 | 0.2814 | 0.2662 | 3.76 | 2 | 0.3080 |
| 35 | 0.2905 | 0.2730 | 3.66 | 2 | 0.3000 |
| 36 | 0.2781 | 0.2364 | 4.23 | 2 | 0.2160 |
| 37 | 0.2844 | 0.3382 | 2.96 | 1 | 0.3680 |
| 38 | 0.2826 | 0.3054 | 3.27 | 2 | 0.3560 |
| 39 | 0.2818 | 0.3200 | 3.12 | 2 | 0.3880 |
| 40 | 0.2782 | 0.2786 | 3.59 | 2 | 0.3120 |
| 41 | 0.2714 | 0.3062 | 3.27 | 2 | 0.3560 |
| 42 | 0.2752 | 0.2572 | 3.89 | 2 | 0.2720 |
| 43 | 0.2836 | 0.3214 | 3.11 | 2 | 0.4200 |
| 44 | 0.2850 | 0.3186 | 3.14 | 1 | 0.3640 |
| 45 | 0.2808 | 0.2926 | 3.42 | 2 | 0.3440 |
| 46 | 0.2859 | 0.2694 | 3.71 | 2 | 0.2800 |
| 47 | 0.2844 | 0.2656 | 3.77 | 2 | 0.2960 |
| 48 | 0.2864 | 0.3202 | 3.12 | 1 | 0.3680 |
| 49 | 0.2836 | 0.2976 | 3.36 | 2 | 0.3600 |
| 50 | 0.2843 | 0.2524 | 3.96 | 2 | 0.2800 |
| 51 | 0.2826 | 0.3061 | 3.27 | 2 | 0.4000 |
| all | 0.2835 | 0.2926 | 3.42 | 2 | 0.3206 |

## 4. Streaks

The per-epoch streak and repeat tests have a report of their own: [`streak.md`](streak.md).

## 5. Timer race

The margin, the sigma decomposition and Props. 5.17/5.18 have a report of their own: [`timer_race.md`](timer_race.md).

## 6. Longitudinal

Monotonicity, the GLM and the log-ratio regression have a report of their own: [`longitudinal.md`](longitudinal.md).

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = -0.0263, p = 0.6788, n = 250.
- **Gini(published) − Gini(input) trajectory**: slope = -0.000009 over 51 epoch(s) (Spearman rho = -0.2737, p = 0.0520). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
