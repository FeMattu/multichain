# Functional run report

| | |
|---|---|
| run | `run-wpoa-long10h-medium-sqrt-20260917T221554Z` |
| chain | `wpoa-long10h-medium-sqrt` |
| experiment seed | 20260905 |
| final height | 6120 |
| epoch length | 100 blocks |
| setup-first-blocks | 228 |
| epochs measured | [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61] |
| epochs excluded (setup phase) | [1] |
| test constants | alpha=0.05, MC_GOF=20000, MC_STREAK=10000, seed=20260905 |

**Overall: FAIL — 1 critical consistency check(s) failed; the statistics below are not safe to read**

## 1. Consistency checks

Non-regression checks, not hypothesis tests. They exist to fail loudly when the collection or the pipeline has a bug.

| check | critical | result | detail |
|---|---|---|---|
| `registry_weights_finite_and_positive` | yes | PASS | ok: 560616 weight samples, all finite and >= 0 |
| `no_phantom_validator_in_registry` | yes | PASS | ok: every weighted address is a known miner |
| `malus_finite_and_psi_in_unit_interval` | yes | PASS | ok: 560616 malus samples, every Psi in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | yes | FAIL | 23 round(s) disagree; max |delta| = 0.9999999999999964 s. The harness and the node disagree about the delay formula, so every timer-race result below is unsafe. |
| `phi_consistent` | no | FAIL | 47 distinct Phi values seen; logged, not fatal |
| `every_esg_publication_reached_the_stream` | yes | PASS | ok: 36 ESG publication(s), all present on weight-engine-esg |
| `certified_scores_reflected_in_the_engine` | no | PASS | ok: every certified address shows a non-zero ESG in the engine's own view |
| `traffic_counts_within_configured_range` | no | PASS | ok: 2077 complete (epoch, node) pairs, every on-chain count inside its configured range (partial first and last epochs excluded) |
| `only_miners_pay_the_treasury` | yes | PASS | ok: all 1664 treasury payments came from a miner, which is the only actor whose R_k the engine reads |
| `at_least_one_fully_measured_epoch` | yes | PASS | ok: 60 epoch(s) measured past setup-first-blocks ([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61]) |

## 2. Weight versus probability of election

> **This is the comparison the experiment exists for, and it has a report of its own: [`weight_vs_election.md`](weight_vs_election.md).** The summary below is the short form.

- 586 of 720 validator-epoch Wilson intervals contained the entitled share (36.0 expected to fail by chance at alpha = 0.05).
- Mean interval width: **0.1052**.
- Goodness of fit rejected in 49 of 61 epoch(s) at alpha = 0.05.

## 3. Concentration

| epoch | HHI (theor.) | HHI (obs.) | N_eff (obs.) | Nakamoto 1/2 | Gini (obs.) |
|---|---:|---:|---:|---:|---:|
| 2 | 0.0919 | 0.1022 | 9.78 | 4 | 0.2717 |
| 3 | 0.0944 | 0.0958 | 10.44 | 5 | 0.2183 |
| 4 | 0.0955 | 0.1196 | 8.36 | 4 | 0.3750 |
| 5 | 0.0945 | 0.0994 | 10.06 | 5 | 0.2467 |
| 6 | 0.0938 | 0.1052 | 9.51 | 4 | 0.2833 |
| 7 | 0.0941 | 0.0988 | 10.12 | 4 | 0.2433 |
| 8 | 0.0942 | 0.1448 | 6.91 | 3 | 0.4067 |
| 9 | 0.0938 | 0.1112 | 8.99 | 4 | 0.3150 |
| 10 | 0.0928 | 0.1010 | 9.90 | 5 | 0.2583 |
| 11 | 0.0930 | 0.1044 | 9.58 | 4 | 0.2750 |
| 12 | 0.0952 | 0.1072 | 9.33 | 4 | 0.2967 |
| 13 | 0.0954 | 0.1000 | 10.00 | 5 | 0.2517 |
| 14 | 0.0929 | 0.1164 | 8.59 | 4 | 0.3433 |
| 15 | 0.0944 | 0.1174 | 8.52 | 4 | 0.3550 |
| 16 | 0.0939 | 0.1086 | 9.21 | 4 | 0.3050 |
| 17 | 0.0943 | 0.1166 | 8.58 | 4 | 0.3467 |
| 18 | 0.0941 | 0.1400 | 7.14 | 3 | 0.4350 |
| 19 | 0.0946 | 0.1218 | 8.21 | 4 | 0.3683 |
| 20 | 0.0955 | 0.1172 | 8.53 | 4 | 0.3600 |
| 21 | 0.0950 | 0.1032 | 9.69 | 4 | 0.2700 |
| 22 | 0.0944 | 0.1148 | 8.71 | 4 | 0.3383 |
| 23 | 0.0935 | 0.1056 | 9.47 | 4 | 0.2883 |
| 24 | 0.0929 | 0.1122 | 8.91 | 4 | 0.3350 |
| 25 | 0.0941 | 0.1014 | 9.86 | 5 | 0.2567 |
| 26 | 0.0943 | 0.1114 | 8.98 | 4 | 0.3300 |
| 27 | 0.0940 | 0.1082 | 9.24 | 4 | 0.3100 |
| 28 | 0.0941 | 0.1086 | 9.21 | 4 | 0.3067 |
| 29 | 0.0949 | 0.1250 | 8.00 | 4 | 0.3983 |
| 30 | 0.0941 | 0.1320 | 7.58 | 3 | 0.4183 |
| 31 | 0.0937 | 0.1282 | 7.80 | 3 | 0.4067 |
| 32 | 0.0943 | 0.1094 | 9.14 | 4 | 0.3033 |
| 33 | 0.0942 | 0.1320 | 7.58 | 3 | 0.4200 |
| 34 | 0.0941 | 0.1058 | 9.45 | 4 | 0.2933 |
| 35 | 0.0938 | 0.1044 | 9.58 | 5 | 0.2667 |
| 36 | 0.0928 | 0.1112 | 8.99 | 4 | 0.3133 |
| 37 | 0.0951 | 0.1088 | 9.19 | 4 | 0.3083 |
| 38 | 0.0934 | 0.1124 | 8.90 | 4 | 0.3317 |
| 39 | 0.0937 | 0.1032 | 9.69 | 5 | 0.2633 |
| 40 | 0.0933 | 0.1218 | 8.21 | 4 | 0.3817 |
| 41 | 0.0958 | 0.1176 | 8.50 | 4 | 0.3667 |
| 42 | 0.0947 | 0.1136 | 8.80 | 4 | 0.3383 |
| 43 | 0.0938 | 0.1232 | 8.12 | 4 | 0.3900 |
| 44 | 0.0927 | 0.1166 | 8.58 | 4 | 0.3550 |
| 45 | 0.0947 | 0.1066 | 9.38 | 4 | 0.2967 |
| 46 | 0.0933 | 0.1098 | 9.11 | 4 | 0.3117 |
| 47 | 0.0949 | 0.1142 | 8.76 | 4 | 0.3233 |
| 48 | 0.0946 | 0.1420 | 7.04 | 3 | 0.4467 |
| 49 | 0.0929 | 0.1202 | 8.32 | 4 | 0.3783 |
| 50 | 0.0941 | 0.1178 | 8.49 | 4 | 0.3667 |
| 51 | 0.0947 | 0.1140 | 8.77 | 4 | 0.3367 |
| 52 | 0.0925 | 0.1244 | 8.04 | 4 | 0.3600 |
| 53 | 0.0936 | 0.1264 | 7.91 | 3 | 0.4050 |
| 54 | 0.0927 | 0.1012 | 9.88 | 5 | 0.2550 |
| 55 | 0.0955 | 0.1140 | 8.77 | 4 | 0.3433 |
| 56 | 0.0939 | 0.1198 | 8.35 | 4 | 0.3617 |
| 57 | 0.0936 | 0.1098 | 9.11 | 4 | 0.3167 |
| 58 | 0.0940 | 0.1190 | 8.40 | 4 | 0.3717 |
| 59 | 0.0951 | 0.1160 | 8.62 | 4 | 0.3550 |
| 60 | 0.0934 | 0.1324 | 7.55 | 4 | 0.4300 |
| 61 | 0.0937 | 0.1973 | 5.07 | 2 | 0.5992 |
| all | 0.0937 | 0.0969 | 10.33 | 5 | 0.2267 |

## 4. Streaks

| epoch | L_max obs | L_max MC mean | p | repeat obs | repeat MC mean | p |
|---|---:|---:|---:|---:|---:|---:|
| 2 | 4 | 2.64 | 0.0734 | 0.2424 | 0.0925 | 0.0002 |
| 3 | 5 | 2.67 | 0.0097 | 0.2222 | 0.0950 | 0.0003 |
| 4 | 3 | 2.69 | 0.5908 | 0.1919 | 0.0961 | 0.0031 |
| 5 | 4 | 2.67 | 0.0815 | 0.2121 | 0.0949 | 0.0005 |
| 6 | 3 | 2.67 | 0.5794 | 0.1010 | 0.0945 | 0.4652 |
| 7 | 4 | 2.66 | 0.0815 | 0.2727 | 0.0947 | 0.0001 |
| 8 | 5 | 2.67 | 0.0104 | 0.2424 | 0.0950 | 0.0001 |
| 9 | 3 | 2.67 | 0.5761 | 0.2424 | 0.0945 | 0.0002 |
| 10 | 3 | 2.65 | 0.5655 | 0.2121 | 0.0935 | 0.0004 |
| 11 | 4 | 2.65 | 0.0774 | 0.1818 | 0.0936 | 0.0045 |
| 12 | 3 | 2.68 | 0.5865 | 0.1414 | 0.0960 | 0.0932 |
| 13 | 3 | 2.69 | 0.5895 | 0.1919 | 0.0959 | 0.0028 |
| 14 | 5 | 2.66 | 0.0090 | 0.2525 | 0.0937 | 0.0001 |
| 15 | 5 | 2.68 | 0.0096 | 0.2020 | 0.0953 | 0.0009 |
| 16 | 2 | 2.67 | 0.9999 | 0.1313 | 0.0946 | 0.1435 |
| 17 | 4 | 2.67 | 0.0809 | 0.2323 | 0.0951 | 0.0004 |
| 18 | 6 | 2.68 | 0.0017 | 0.3535 | 0.0948 | 0.0001 |
| 19 | 5 | 2.68 | 0.0105 | 0.2424 | 0.0954 | 0.0001 |
| 20 | 4 | 2.69 | 0.0889 | 0.2525 | 0.0960 | 0.0001 |
| 21 | 3 | 2.68 | 0.5845 | 0.1616 | 0.0955 | 0.0250 |
| 22 | 6 | 2.67 | 0.0014 | 0.3030 | 0.0950 | 0.0001 |
| 23 | 2 | 2.67 | 1.0000 | 0.1717 | 0.0943 | 0.0119 |
| 24 | 4 | 2.66 | 0.0808 | 0.2424 | 0.0935 | 0.0002 |
| 25 | 5 | 2.67 | 0.0096 | 0.2727 | 0.0948 | 0.0001 |
| 26 | 4 | 2.68 | 0.0833 | 0.2222 | 0.0948 | 0.0005 |
| 27 | 3 | 2.67 | 0.5778 | 0.1818 | 0.0947 | 0.0053 |
| 28 | 4 | 2.67 | 0.0826 | 0.2121 | 0.0947 | 0.0005 |
| 29 | 4 | 2.68 | 0.0864 | 0.2323 | 0.0958 | 0.0002 |
| 30 | 4 | 2.67 | 0.0829 | 0.2424 | 0.0950 | 0.0001 |
| 31 | 4 | 2.66 | 0.0795 | 0.2828 | 0.0943 | 0.0001 |
| 32 | 4 | 2.68 | 0.0832 | 0.2828 | 0.0951 | 0.0001 |
| 33 | 3 | 2.67 | 0.5806 | 0.3131 | 0.0951 | 0.0001 |
| 34 | 3 | 2.67 | 0.5748 | 0.2222 | 0.0950 | 0.0004 |
| 35 | 4 | 2.67 | 0.0787 | 0.2323 | 0.0949 | 0.0002 |
| 36 | 4 | 2.66 | 0.0780 | 0.2828 | 0.0934 | 0.0001 |
| 37 | 3 | 2.69 | 0.5915 | 0.1717 | 0.0958 | 0.0147 |
| 38 | 3 | 2.66 | 0.5687 | 0.2245 | 0.0940 | 0.0002 |
| 39 | 4 | 2.67 | 0.0851 | 0.2525 | 0.0946 | 0.0001 |
| 40 | 5 | 2.66 | 0.0092 | 0.3030 | 0.0942 | 0.0001 |
| 41 | 3 | 2.70 | 0.5924 | 0.2424 | 0.0966 | 0.0003 |
| 42 | 5 | 2.68 | 0.0112 | 0.2222 | 0.0954 | 0.0006 |
| 43 | 6 | 2.66 | 0.0016 | 0.3030 | 0.0942 | 0.0001 |
| 44 | 3 | 2.64 | 0.5614 | 0.3030 | 0.0933 | 0.0001 |
| 45 | 5 | 2.68 | 0.0109 | 0.3030 | 0.0953 | 0.0001 |
| 46 | 6 | 2.66 | 0.0015 | 0.2626 | 0.0941 | 0.0001 |
| 47 | 4 | 2.68 | 0.0838 | 0.2959 | 0.0953 | 0.0001 |
| 48 | 5 | 2.68 | 0.0104 | 0.3535 | 0.0953 | 0.0001 |
| 49 | 7 | 2.66 | 0.0002 | 0.3333 | 0.0938 | 0.0001 |
| 50 | 3 | 2.68 | 0.5787 | 0.2222 | 0.0949 | 0.0002 |
| 51 | 6 | 2.68 | 0.0018 | 0.2323 | 0.0952 | 0.0001 |
| 52 | 6 | 2.65 | 0.0011 | 0.3333 | 0.0932 | 0.0001 |
| 53 | 4 | 2.67 | 0.0841 | 0.2929 | 0.0944 | 0.0001 |
| 54 | 6 | 2.65 | 0.0015 | 0.2959 | 0.0932 | 0.0001 |
| 55 | 5 | 2.69 | 0.0102 | 0.2959 | 0.0962 | 0.0001 |
| 56 | 7 | 2.67 | 0.0002 | 0.3434 | 0.0948 | 0.0001 |
| 57 | 7 | 2.66 | 0.0002 | 0.4040 | 0.0945 | 0.0001 |
| 58 | 4 | 2.66 | 0.0815 | 0.2755 | 0.0950 | 0.0001 |
| 59 | 6 | 2.68 | 0.0018 | 0.2857 | 0.0955 | 0.0001 |
| 60 | 8 | 2.66 | 0.0002 | 0.3571 | 0.0941 | 0.0001 |
| 61 | 3 | 2.01 | 0.1444 | 0.2632 | 0.0946 | 0.0283 |
| all | 8 | 4.51 | 0.0012 | 0.2521 | 0.0941 | 0.0001 |

## 5. Timer race

| quantity | value |
|---|---|
| rounds measured | 5885 |
| margins observed | 5885 |
| mean margin G (s) | 1.88615 |
| KS vs Beta(1,n) — straw man, p | 0.00000 |
| KS vs simulated exact — reference, p | 0.08797 |
| sigma S1 (topology) | 0.000000 |
| sigma S2 (scheduler residual) | 2.501366 |
| inversion bound (Prop. 5.18) | 1.00000 |
| inversion probability, MC with sigma_S2 | 0.61338 |
| inversions observed | 5351 |
| inversion rate observed | 0.90942 |

The Beta(1,n) test is a **straw man**: it assumes uniform weights and is expected to reject whenever they are not uniform. The reference test is the KS against the simulated exact distribution of the implemented sortition.

**S1 is structurally negligible in this harness** — every node is a local process and there is no emulated latency, so a run here cannot speak to latency-driven inversion. S2, the scheduler residual, is the primary source.

## 6. Longitudinal

- **GLM logit on log(weight)**: beta1 = 0.7609 (95% CI [0.6907, 0.8312], n = 720, converged = True). H0 of weighted sortition is beta1 = 1 — NOT consistent.
- **Pairwise log-ratio regression**: slope = 1.0450, intercept = -0.0194, Pearson r = 0.7009 (p = 0.0000), n = 3380 pairs. Proportional selection implies slope 1 and intercept 0.
- **Sign test (weight ↔ share monotonicity)**: 12 validator(s) tested; p-values 0.0220, 0.1334, 0.2950, 0.4439, 0.7050, 0.5000.

## 7. WeightEngine feedback

- **Lag-1 Spearman**, rho at epoch *e* against the weight published at *e+1* (the engine's only endogenous feedback channel): rho = -0.1255, p = 0.0007, n = 720.
- **Gini(published) − Gini(input) trajectory**: slope = -0.000004 over 61 epoch(s) (Spearman rho = -0.2187, p = 0.0904). A positive slope means the engine concentrates weight beyond the inequality of its own inputs.

## 8. Method notes

- Only epochs entirely past `setup-first-blocks` are tested: below that height the chain runs under native MultiChain round robin, not wPoA.
- `p_theoretical` uses the effective weight after malus and dumping — what the election consumes — not the raw published weight.
- Monte-Carlo p-values are `(hits + 1) / (draws + 1)`, so a p-value of exactly 0 is never reported for a finite simulation.
- No `scipy` and no `statsmodels`: the chi-square tail, the Kolmogorov distribution, Student's t, the exact binomial tail and the IRLS logit fit are all computed from their closed forms in `stat/`.
- The analysis seed (20260905) is independent of the experiment seed (20260905): the network and the tests are separately reproducible.
