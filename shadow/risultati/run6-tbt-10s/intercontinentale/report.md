# run6-tbt-10s / intercontinentale

| | |
|---|---|
| Target block time | 10 s |
| Damping function (dumpfunction) | none |
| Malus | enabled, registry empty (0 records) |
| Epoch length | 100 blocks |
| Measured epochs | 6 (4 fully measured), epochs 2–7 |
| Blocks | 450 measured of 602 total (setup 152), final height 602 |
| Sortition | delta 0.5, lambda 0.2, RANDAO lookback 1 |
| Weight engine | kappa 100, alpha 0.2, lambda_w 0.5 |


## Epoch by epoch, per validator

#### Epoch 2 — 47 blocks, heights 100–199, buried

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.672 | 0.574 | expected inside Wilson 95 % CI [0.433, 0.705] |
| m2 | 0.262 | 0.383 | expected inside Wilson 95 % CI [0.258, 0.526] |
| m3 | 0.067 | 0.043 | expected inside Wilson 95 % CI [0.012, 0.142] |

Weight engine: 1 of 3 published weights were not reproduced by the independent recomputation: m2 (implied raw delta over esg_miner 1.0001).
m3 lost 2 of the 4 rounds in which it held the smallest delay (MissedTurnRate 0.500).

#### Epoch 3 — 100 blocks, heights 200–299, buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.671 | 0.740 | expected inside Wilson 95 % CI [0.646, 0.816] |
| m2 | 0.263 | 0.200 | expected inside Wilson 95 % CI [0.133, 0.289] |
| m3 | 0.065 | 0.060 | expected inside Wilson 95 % CI [0.028, 0.125] |

Weight engine: 2 of 3 published weights were not reproduced by the independent recomputation: m1 (implied raw delta over esg_miner 2.0), m2 (implied raw delta over esg_miner -0.3159).
Streaks: longest streak 16 blocks against a Monte Carlo mean of 9.72 (p = 0.0473); repeat probability 0.667 against a Monte Carlo mean of 0.525 (p = 0.0109).

#### Epoch 4 — 100 blocks, heights 300–399, buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.701 | 0.770 | expected inside Wilson 95 % CI [0.678, 0.842] |
| m2 | 0.231 | 0.180 | expected inside Wilson 95 % CI [0.117, 0.267] |
| m3 | 0.067 | 0.050 | expected inside Wilson 95 % CI [0.022, 0.112] |

Weight engine: 1 of 3 published weights were not reproduced by the independent recomputation: m1 (implied raw delta over esg_miner 1.9999).
Streaks: longest streak 18 blocks against a Monte Carlo mean of 10.73 (p = 0.0437); repeat probability 0.717 against a Monte Carlo mean of 0.550 (p = 0.0035).

#### Epoch 5 — 100 blocks, heights 400–499, buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.682 | 0.650 | expected inside Wilson 95 % CI [0.553, 0.736] |
| m2 | 0.255 | 0.260 | expected inside Wilson 95 % CI [0.184, 0.354] |
| m3 | 0.064 | 0.090 | expected inside Wilson 95 % CI [0.048, 0.162] |

Weight engine: 2 of 3 published weights were not reproduced by the independent recomputation: m1 (implied raw delta over esg_miner 1.0), m2 (implied raw delta over esg_miner 1.0).

#### Epoch 6 — 100 blocks, heights 500–599, not buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.676 | 0.790 | expected OUTSIDE Wilson 95 % CI [0.700, 0.858] |
| m2 | 0.261 | 0.190 | expected inside Wilson 95 % CI [0.125, 0.278] |
| m3 | 0.063 | 0.020 | expected inside Wilson 95 % CI [0.006, 0.070] |

GoF rejected at alpha = 0.05 (`chi2_asymptotic`, p = 0.0343); the deviation is carried by m1, which won 79 blocks against 67.65 expected.
Expected share outside the Wilson 95 % CI for m1 (observed 0.790, CI [0.700, 0.858], expected 0.676).
Streaks: longest streak 18 blocks against a Monte Carlo mean of 9.88 (p = 0.0254); repeat probability 0.717 against a Monte Carlo mean of 0.530 (p = 0.0015).

#### Epoch 7 — 3 blocks, heights 600–699, not buried

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.676 | 1.000 | expected inside Wilson 95 % CI [0.439, 1.000] |
| m2 | 0.261 | 0.000 | expected inside Wilson 95 % CI [0.000, 0.561] |
| m3 | 0.063 | 0.000 | expected inside Wilson 95 % CI [0.000, 0.561] |

Compatible with the expectation, no relevant deviation.


## Trend by epoch

| epoch | blocks | GoF p (method) | HHI | N_eff | Nakamoto ½ | timer race KS p | inversion rate | block success | WE conformity |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 47 | 0.149 (exact) | 0.478 | 2.09 | 1 | 0.316 | 0.106 | 0.887 | 2/3 |
| 3 | 100 | 0.324 (chi2) | 0.591 | 1.69 | 1 | 0.893 | 0.070 | 0.971 | 1/3 |
| 4 | 100 | 0.323 (chi2) | 0.628 | 1.59 | 1 | 0.837 | 0.060 | 0.935 | 1/3 |
| 5 | 100 | 0.535 (chi2) | 0.498 | 2.01 | 1 | 0.74 | 0.100 | 0.935 | 1/3 |
| 6 | 100 | 0.0343* (chi2) | 0.661 | 1.51 | 1 | 0.93 | 0.050 | 0.926 | 0/3 |
| 7 | 3 | 0.642 (exact) | 1.000 | 1.00 | 1 | 0.601 | 0.000 | 1.000 | 0/3 |

1 weight-engine epoch falls outside the measured range (epoch 1): it is a setup epoch or the trailing partial epoch, not missing data.
Clusters that published no weight at all, and therefore lower the conformity ratio by absence rather than by mismatch: epoch 4 (1 of 3), epoch 6 (3 of 3), epoch 7 (3 of 3).


## How the system behaved

**Does the system converge to the theoretical behaviour?** Pooled, the shares are compatible with
the expectation: `gof_pooled_method` = `chi2_asymptotic`, `gof_pooled_p` = 0.171
(`gof_pooled_min_expected` = 29.27, round-by-round Monte Carlo
`gof_pooled_mc_round_by_round_p` = 0.169), with `TV_pooled` = `MaxAE_pooled` = 0.041. One of the 6
tested epochs rejects on its own (`epochs_gof_reject_alpha05` of `epochs_gof_tested`). The
longitudinal fit is the least proportional of the whole report: `glm_beta1_logw` = 1.853 with CI
[1.630, 2.076], excluding 1 by a wide margin and reaching almost quadratic response — the heaviest
validator wins close to the square of the share its weight prescribes.

**Does the network introduce a measurable deviation from proportionality?** Not the network, even
here where the topology is widest. `sigma_S1_s` = 0.0458 s is the maximum one-way propagation
latency between miners taken from the topology, described in `wpoa_sigma.csv` as "propagation
latency; deterministic (jitter 0 us), not a variance": the Shadow topologies declare zero jitter,
so the intercontinental distances lengthen the delay without adding randomness. The race is decided
by `sigma_S2_s` = 0.73 s, whose `what_it_measures` reads "quantisation of the 1 s time bar and
block timestamps plus miner loop granularity" (median 0.85 s, p90 1.92 s) — still an order of
magnitude above S1. The observed `inversion_rate` = 0.073 [0.053, 0.101] lies below the Prop. 5.18
bound at the topology sigma (`inversion_bound_S1` = 0.136) and far below the bound at the scheduler
sigma (`inversion_bound_S2` = 0.867); the Gaussian-noise Monte Carlo at sigma_S2
(`inversion_mc_prob_gaussian_S2` = 0.112) sits above the observed interval, so quantisation noise
alone would predict slightly more inversions than actually occurred.
`inversion_with_fork_n` = 13 inversions coincided with a competing block.

**Did the weight engine reward conformity in later epochs?** Not measurably.
`spearman_rho_to_w_next_pooled` = 0.200 with `spearman_p_pooled` = 0.555, because 10 of the 11
epoch pairs have rho exactly 1 (`n_pairs_rho_equal_1`); the tautological control
`spearman_rho_e_vs_w_next_over_W_raw_next` = 0.500 (p = 0.117) only re-tests the deterministic part
of Def. 6.9. `gini_delta_slope` = −0.0179 per epoch with `gini_verdict` = "published Gini grows
slower than input Gini". The next section shows that the negative sign is produced by one epoch in
which a cluster published nothing at all, so the verdict is descriptive and must not be read as
damping. `weight_recompute_mismatches` = 6 of `weight_rows` =
21 published weights were not reproduced. Traffic is exogenous
(`weight_engine_traffic_model.csv`), so rho is the only endogenous feedback channel and it is
saturated at 1.

**Were there malus events with a measurable effect on weight?** No, and this is a limit of the
campaign rather than a result of this experiment. `malus_registry_records` = 0, and every row of
`weight_engine_epoch.csv` carries `psi` = 1.0 with `malus_M` = 0.0: the mechanism is enabled but
never exercised, because the campaign contains no misbehaving actor by design.
`methodology_notes.csv` lists under `not computable on this campaign` — "dump-function effect (none
everywhere); malus trajectory and Delay-event recomputation (registry empty); VRF output y_i (not
logged); per-event network latency and jitter (1 s log resolution, jitter 0 us); packet loss".


## Notable facts and anomalies

* One weight recomputation fails in the opposite direction from all the others: in epoch 3 cluster
  m2 published 265001 against `w_k_int_recomputed` = 265714, giving
  `implied_raw_delta_over_esg_miner` = −0.3159 — the published raw weight is *below* the
  independent recomputation, and by a fraction of an `esg_miner` unit rather than a whole multiple.
  The other five mismatches are the familiar quantised excess (1.0001, 2.0, 1.9999, 1.0, 1.0), so
  this row is a different phenomenon, not the same rounding gap.
* Pooled over the run every validator sits inside its Wilson interval, but m1 only just: its
  expected 0.682 clears the lower bound of its own interval by 0.003. m1 won 325 blocks against
  `E_i` = 306.70 (`p_hat` 0.722, Wilson [0.679, 0.762], expected 0.682),
  m2 101 against 114.03 (0.224, [0.188, 0.265], expected 0.253), m3 24 against 29.27 (0.053,
  [0.036, 0.078], expected 0.065).
* The KS against `2*Dmax*Beta(1,n)` rejects (`ks_beta_pooled_p` < 0.001) while the KS against the
  exact Monte Carlo of the implemented sortition does not (`ks_mc_pooled_p` = 0.537). The first
  rejection is the expected outcome, not a failure: `ks_beta_note` states "iid-uniform delays
  assumed (Prop. 5.18); invalid for concentrated weights". The reference test is the second, and it
  passes.
* The longest streak of consecutive wins, `L_max_observed` = 18, is still compatible with the
  sortition alone (`L_max_mc_mean` = 14.04, `L_max_mc_p_value` = 0.137), but the repeat probability
  is not: `repeat_prob_observed` = 0.664 against `repeat_prob_mc_mean` = 0.533,
  `repeat_prob_mc_p_value` < 0.001.
* The negative inequality slope is an artefact of one incomplete epoch. The per-epoch
  `gini_delta_published_minus_input` values are 0.0000003, −0.00094, 0.02006, −0.18143 and 0.00094:
  the −0.18143 comes from the epoch in which a cluster published no weight at all, so the published
  Gini is computed over two clusters against an input Gini over three, so the drop measures a
  missing publication rather than a change in inequality.
* Model consistency: `delay_recompute_mismatch_rounds` = 0 while `phi_mismatch_rounds` = 10 rounds
  have miners disagreeing on the feedback term Phi. One of the 19
  Prop. 5.17 classes rejects (epoch 3, m3, n = 7, `ks_p` = 0.0402, `mean_gap_x_rate` = 1.360
  against `expected_mean` = 1.0), which over 19 tests at alpha = 0.05 is what chance alone
  produces.

Upstream gap: phase 3 reports `phi_mismatch_rounds` as a bare count, with no per-round breakdown in
any sheet, so the 10 divergent rounds cannot be attributed to a miner or a height from `phase3/`.

