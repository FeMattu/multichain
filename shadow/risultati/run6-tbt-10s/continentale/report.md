# run6-tbt-10s / continentale

| | |
|---|---|
| Target block time | 10 s |
| Damping function (dumpfunction) | none |
| Malus | enabled, registry empty (0 records) |
| Epoch length | 100 blocks |
| Measured epochs | 5 (3 fully measured), epochs 2–6 |
| Blocks | 445 measured of 597 total (setup 152), final height 597 |
| Sortition | delta 0.5, lambda 0.2, RANDAO lookback 1 |
| Weight engine | kappa 100, alpha 0.2, lambda_w 0.5 |


## Epoch by epoch, per validator

#### Epoch 2 — 47 blocks, heights 100–199, buried

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.668 | 0.702 | expected inside Wilson 95 % CI [0.560, 0.813] |
| m2 | 0.264 | 0.298 | expected inside Wilson 95 % CI [0.187, 0.440] |
| m3 | 0.068 | 0.000 | expected inside Wilson 95 % CI [0.000, 0.076] |

Weight engine: 1 of 3 published weights were not reproduced by the independent recomputation: m1 (implied raw delta over esg_miner 1.0).
Streaks: repeat probability 0.739 against a Monte Carlo mean of 0.521 (p = 0.0091).

#### Epoch 3 — 100 blocks, heights 200–299, buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.677 | 0.660 | expected inside Wilson 95 % CI [0.563, 0.745] |
| m2 | 0.258 | 0.270 | expected inside Wilson 95 % CI [0.193, 0.364] |
| m3 | 0.065 | 0.070 | expected inside Wilson 95 % CI [0.034, 0.137] |

Weight engine: 2 of 3 published weights were not reproduced by the independent recomputation: m1 (implied raw delta over esg_miner 1.0), m2 (implied raw delta over esg_miner 1.3633).
Streaks: repeat probability 0.646 against a Monte Carlo mean of 0.530 (p = 0.0298).

#### Epoch 4 — 100 blocks, heights 300–399, buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.701 | 0.780 | expected inside Wilson 95 % CI [0.689, 0.850] |
| m2 | 0.231 | 0.150 | expected inside Wilson 95 % CI [0.093, 0.233] |
| m3 | 0.068 | 0.070 | expected inside Wilson 95 % CI [0.034, 0.137] |

Weight engine: 1 of 3 published weights were not reproduced by the independent recomputation: m1 (implied raw delta over esg_miner 1.0).

#### Epoch 5 — 100 blocks, heights 400–499, buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.679 | 0.620 | expected inside Wilson 95 % CI [0.522, 0.709] |
| m2 | 0.257 | 0.290 | expected inside Wilson 95 % CI [0.210, 0.385] |
| m3 | 0.065 | 0.090 | expected inside Wilson 95 % CI [0.048, 0.162] |

Weight engine: 2 of 3 published weights were not reproduced by the independent recomputation: m1 (implied raw delta over esg_miner 1.0), m2 (implied raw delta over esg_miner 1.0002).
Inversion rate 0.160 against a pooled 0.094 for the run (1.70 x); 6 of the inverted rounds coincided with a competing block.

#### Epoch 6 — 98 blocks, heights 500–599, not buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.675 | 0.755 | expected inside Wilson 95 % CI [0.661, 0.830] |
| m2 | 0.261 | 0.184 | expected inside Wilson 95 % CI [0.119, 0.272] |
| m3 | 0.064 | 0.061 | expected inside Wilson 95 % CI [0.028, 0.127] |

Compatible with the expectation, no relevant deviation.


## Trend by epoch

| epoch | blocks | GoF p (method) | HHI | N_eff | Nakamoto ½ | timer race KS p | inversion rate | block success | WE conformity |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 47 | 0.166 (exact) | 0.582 | 1.72 | 1 | 0.449 | 0.106 | 0.887 | 2/3 |
| 3 | 100 | 0.932 (chi2) | 0.513 | 1.95 | 1 | 0.241 | 0.070 | 0.943 | 1/3 |
| 4 | 100 | 0.152 (chi2) | 0.636 | 1.57 | 1 | 0.64 | 0.080 | 0.980 | 2/3 |
| 5 | 100 | 0.382 (chi2) | 0.477 | 2.10 | 1 | 0.29 | 0.160 | 0.862 | 1/3 |
| 6 | 98 | 0.206 (chi2) | 0.608 | 1.65 | 1 | 0.807 | 0.061 | 0.961 | 0/3 |

1 weight-engine epoch falls outside the measured range (epoch 1): it is a setup epoch or the trailing partial epoch, not missing data.
Clusters that published no weight at all, and therefore lower the conformity ratio by absence rather than by mismatch: epoch 6 (3 of 3).


## How the system behaved

**Does the system converge to the theoretical behaviour?** At the epoch level, yes; at the
validator level, not quite. No epoch rejects the goodness of fit
(`epochs_gof_reject_alpha05` = 0 of `epochs_gof_tested` = 5) and the pooled test is comfortable:
`gof_pooled_method` = `chi2_asymptotic`, `gof_pooled_p` = 0.567 (`gof_pooled_min_expected` = 29.20,
round-by-round Monte Carlo `gof_pooled_mc_round_by_round_p` = 0.563), with `TV_pooled` =
`MaxAE_pooled` = 0.022. The longitudinal fit still refuses proportionality: `glm_beta1_logw` =
1.517 with CI [1.297, 1.738], which excludes 1. The chi-square has no power to see this — it tests
one epoch's shares against one epoch's expectation, while the slope uses the ordering of the shares
across epochs.

**Does the network introduce a measurable deviation from proportionality?** Not the network.
`sigma_S1_s` = 0.0106 s is the maximum one-way propagation latency between miners taken from the
topology, described in `wpoa_sigma.csv` as "propagation latency; deterministic (jitter 0 us), not a
variance": the Shadow topologies declare zero jitter, so latency contributes no randomness. The
race is decided by `sigma_S2_s` = 0.71 s, whose `what_it_measures` reads "quantisation of the 1 s
time bar and block timestamps plus miner loop granularity" (median 0.81 s, p90 1.80 s). The
observed `inversion_rate` = 0.094 [0.071, 0.125] lies well above the Prop. 5.18 bound at the
topology sigma (`inversion_bound_S1` = 0.052) and well below the bound at the scheduler sigma
(`inversion_bound_S2` = 0.849), and its interval covers the Gaussian-noise Monte Carlo at sigma_S2
(`inversion_mc_prob_gaussian_S2` = 0.110). `inversion_with_fork_n` = 13 inversions coincided with a
competing block.

**Did the weight engine reward conformity in later epochs?** Not measurably.
`spearman_rho_to_w_next_pooled` = 0.131 with `spearman_p_pooled` = 0.684, because 11 of the 12
epoch pairs have rho exactly 1 (`n_pairs_rho_equal_1`) and there is almost no variation left to
correlate; the tautological control `spearman_rho_e_vs_w_next_over_W_raw_next` = 0.481 (p = 0.113)
only re-tests the deterministic part of Def. 6.9. `gini_delta_slope` = 0.000177 per epoch with
`gini_verdict` = "amplification by feedback (published Gini grows faster than input Gini)", a slope
that the next section shows to be dominated by a single epoch. `weight_recompute_mismatches` = 6 of `weight_rows` = 18 published weights were not
reproduced. Traffic is exogenous (`weight_engine_traffic_model.csv`), so rho is the only endogenous
feedback channel and it is saturated at 1.

**Were there malus events with a measurable effect on weight?** No, and this is a limit of the
campaign rather than a result of this experiment. `malus_registry_records` = 0, and every row of
`weight_engine_epoch.csv` carries `psi` = 1.0 with `malus_M` = 0.0: the mechanism is enabled but
never exercised, because the campaign contains no misbehaving actor by design.
`methodology_notes.csv` lists under `not computable on this campaign` — "dump-function effect (none
everywhere); malus trajectory and Delay-event recomputation (registry empty); VRF output y_i (not
logged); per-event network latency and jitter (1 s log resolution, jitter 0 us); packet loss".


## Notable facts and anomalies

* Pooled over the run every validator sits inside its Wilson interval: m1 won 313 blocks against
  `E_i` = 303.21 (`p_hat` 0.703, Wilson [0.659, 0.744], expected 0.681), m2 103 against 112.59
  (0.231, [0.195, 0.273], expected 0.253), m3 29 against 29.20 (0.065, [0.046, 0.092], expected
  0.066). No epoch table in section B carries a single Wilson failure either — this is the cleanest
  per-validator fit of the experiment.
* The KS against `2*Dmax*Beta(1,n)` rejects (`ks_beta_pooled_p` < 0.001) while the KS against the
  exact Monte Carlo of the implemented sortition does not (`ks_mc_pooled_p` = 0.704). The first
  rejection is the expected outcome, not a failure: `ks_beta_note` states "iid-uniform delays
  assumed (Prop. 5.18); invalid for concentrated weights". The reference test is the second, and it
  passes.
* The longest streak of consecutive wins, `L_max_observed` = 15, is compatible with the sortition
  alone (`L_max_mc_mean` = 13.98, `L_max_mc_p_value` = 0.363), but the repeat probability is not:
  `repeat_prob_observed` = 0.635 against `repeat_prob_mc_mean` = 0.533, `repeat_prob_mc_p_value`
  < 0.001. Wins persist from block to block more than the weights alone explain, even where the
  shares themselves are on target.
* Every failed weight recomputation lands on the two heavy clusters and the gap is quantised:
  `implied_raw_delta_over_esg_miner` takes the values 1.0, 1.0, 1.3633, 1.0, 1.0 and 1.0002, i.e.
  the published raw weight exceeds the independent recomputation by one whole `esg_miner` unit in
  five of the six cases. m3 reproduces exactly in every epoch in which it published.
* The inequality verdict rests on one epoch. The per-epoch `gini_delta_published_minus_input`
  values are 0.0000003, 0.00192, 0.01833, 0.00184 and 0.00093 (`gini_delta_max` = 0.01833,
  `gini_delta_last` = 0.00093, `gini_published_last3_sd` = 0.00044): one epoch is twenty times the
  others and the trajectory is flat around it, which matches the sheet's own note that "a plateau
  is consistent with lambda_w < 1 (Prop. 6.2)".
* Model consistency: `delay_recompute_mismatch_rounds` = 0 while `phi_mismatch_rounds` = 3 rounds
  have miners disagreeing on the feedback term Phi. One of the 18 Prop. 5.17 classes rejects
  (epoch 3, m3, n = 8, `ks_p` = 0.0217, `mean_gap_x_rate` = 0.391 against `expected_mean` = 1.0),
  which over 18 tests at alpha = 0.05 is what chance alone produces.

Upstream gap: phase 3 reports `phi_mismatch_rounds` as a bare count, with no per-round breakdown in
any sheet, so the 3 divergent rounds cannot be attributed to a miner or a height from `phase3/`.

