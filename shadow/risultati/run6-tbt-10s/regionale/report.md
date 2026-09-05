# run6-tbt-10s / regionale

| | |
|---|---|
| Target block time | 10 s |
| Damping function (dumpfunction) | none |
| Malus | enabled, registry empty (0 records) |
| Epoch length | 100 blocks |
| Measured epochs | 5 (3 fully measured), epochs 2–6 |
| Blocks | 438 measured of 590 total (setup 152), final height 590 |
| Sortition | delta 0.5, lambda 0.2, RANDAO lookback 1 |
| Weight engine | kappa 100, alpha 0.2, lambda_w 0.5 |


## Epoch by epoch, per validator

#### Epoch 2 — 47 blocks, heights 100–199, buried

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.668 | 0.809 | expected OUTSIDE Wilson 95 % CI [0.675, 0.896] |
| m2 | 0.264 | 0.149 | expected inside Wilson 95 % CI [0.074, 0.277] |
| m3 | 0.068 | 0.043 | expected inside Wilson 95 % CI [0.012, 0.142] |

Expected share outside the Wilson 95 % CI for m1 (observed 0.809, CI [0.675, 0.896], expected 0.668).
Weight engine: 1 of 3 published weights were not reproduced by the independent recomputation: m1 (implied raw delta over esg_miner 1.0).
Streaks: repeat probability 0.717 against a Monte Carlo mean of 0.522 (p = 0.0168).

#### Epoch 3 — 100 blocks, heights 200–299, buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.677 | 0.740 | expected inside Wilson 95 % CI [0.646, 0.816] |
| m2 | 0.258 | 0.190 | expected inside Wilson 95 % CI [0.125, 0.278] |
| m3 | 0.065 | 0.070 | expected inside Wilson 95 % CI [0.034, 0.137] |

Weight engine: 1 of 3 published weights were not reproduced by the independent recomputation: m2 (implied raw delta over esg_miner 1.3332).

#### Epoch 4 — 100 blocks, heights 300–399, buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.704 | 0.760 | expected inside Wilson 95 % CI [0.668, 0.833] |
| m2 | 0.227 | 0.140 | expected OUTSIDE Wilson 95 % CI [0.085, 0.221] |
| m3 | 0.068 | 0.100 | expected inside Wilson 95 % CI [0.055, 0.174] |

Expected share outside the Wilson 95 % CI for m2 (observed 0.140, CI [0.085, 0.221], expected 0.227).
Weight engine: 1 of 3 published weights were not reproduced by the independent recomputation: m1 (implied raw delta over esg_miner 2.0).
Streaks: repeat probability 0.687 against a Monte Carlo mean of 0.553 (p = 0.0151).

#### Epoch 5 — 100 blocks, heights 400–499, buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.679 | 0.690 | expected inside Wilson 95 % CI [0.594, 0.772] |
| m2 | 0.257 | 0.230 | expected inside Wilson 95 % CI [0.158, 0.322] |
| m3 | 0.064 | 0.080 | expected inside Wilson 95 % CI [0.041, 0.150] |

Weight engine: 1 of 3 published weights were not reproduced by the independent recomputation: m1 (implied raw delta over esg_miner 1.0).

#### Epoch 6 — 91 blocks, heights 500–599, not buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.675 | 0.813 | expected OUTSIDE Wilson 95 % CI [0.721, 0.880] |
| m2 | 0.260 | 0.176 | expected inside Wilson 95 % CI [0.111, 0.267] |
| m3 | 0.065 | 0.011 | expected OUTSIDE Wilson 95 % CI [0.002, 0.060] |

GoF rejected at alpha = 0.05 (`chi2_asymptotic`, p = 0.0105); the deviation is carried by m1, which won 74 blocks against 61.43 expected.
Expected share outside the Wilson 95 % CI for m1 (observed 0.813, CI [0.721, 0.880], expected 0.675); m3 (observed 0.011, CI [0.002, 0.060], expected 0.065).
Inversion rate 0.132 against a pooled 0.087 for the run (1.52 x); 5 of the inverted rounds coincided with a competing block.


## Trend by epoch

| epoch | blocks | GoF p (method) | HHI | N_eff | Nakamoto ½ | timer race KS p | inversion rate | block success | WE conformity |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 47 | 0.119 (exact) | 0.678 | 1.48 | 1 | 0.705 | 0.064 | 0.940 | 2/3 |
| 3 | 100 | 0.294 (chi2) | 0.589 | 1.70 | 1 | 0.542 | 0.030 | 0.971 | 1/3 |
| 4 | 100 | 0.0724 (chi2) | 0.607 | 1.65 | 1 | 0.857 | 0.090 | 0.952 | 2/3 |
| 5 | 100 | 0.706 (chi2) | 0.535 | 1.87 | 1 | 0.162 | 0.110 | 0.893 | 2/3 |
| 6 | 91 | 0.0105* (chi2) | 0.692 | 1.44 | 1 | 0.00109 | 0.132 | 0.938 | 0/3 |

1 weight-engine epoch falls outside the measured range (epoch 1): it is a setup epoch or the trailing partial epoch, not missing data.
Clusters that published no weight at all, and therefore lower the conformity ratio by absence rather than by mismatch: epoch 3 (1 of 3), epoch 6 (3 of 3).


## How the system behaved

**Does the system converge to the theoretical behaviour?** No. The pooled goodness of fit
(`gof_pooled_method` = `chi2_asymptotic`, `gof_pooled_min_expected` = 28.76) rejects at
`gof_pooled_p` = 0.00205, and the round-by-round Monte Carlo that respects the per-round shares
agrees (`gof_pooled_mc_round_by_round_p` = 0.00225). The deviation is nevertheless small in
absolute terms: `TV_pooled` = `MaxAE_pooled` = 0.073, at most 7.3 share points on any validator.
Only 1 of the 5 tested epochs rejects on its own (`epochs_gof_reject_alpha05` of
`epochs_gof_tested`), so it is the accumulation over the whole run, not a single bad epoch, that
makes the pooled test significant. The longitudinal fit points the same way: `glm_beta1_logw` =
1.645 with CI [1.413, 1.878], which excludes 1 — selection is super-proportional, the heaviest
validator wins more than its weight prescribes.

**Does the network introduce a measurable deviation from proportionality?** Not the network.
`sigma_S1_s` = 0.0019 s is the maximum one-way propagation latency between miners read off the
topology, and `wpoa_sigma.csv` describes it as "propagation latency; deterministic (jitter 0 us),
not a variance": the Shadow topologies declare zero jitter, so there is no latency noise to speak
of. What decides the race is `sigma_S2_s` = 0.68 s, whose `what_it_measures` reads "quantisation
of the 1 s time bar and block timestamps plus miner loop granularity" (median 0.74 s, p90 1.79 s)
— more than two orders of magnitude above S1. The observed `inversion_rate` = 0.087 [0.064, 0.117]
is far above the Prop. 5.18 bound evaluated at the topology sigma (`inversion_bound_S1` = 0.016)
and far below the bound at the scheduler sigma (`inversion_bound_S2` = 0.823), and its interval
covers the Gaussian-noise Monte Carlo at sigma_S2 (`inversion_mc_prob_gaussian_S2` = 0.102).
`inversion_with_fork_n` = 16 inversions coincided with a competing block.

**Did the weight engine reward conformity in later epochs?** Not measurably.
`spearman_rho_to_w_next_pooled` = 0.100 with `spearman_p_pooled` = 0.769: no detectable link
between an epoch's reconciliation ratio and the weight published for the next one. The sheet
explains why — 10 of the 11 epoch pairs have rho exactly 1 (`n_pairs_rho_equal_1`), so there is
almost no variation left to correlate, while the tautological control
`spearman_rho_e_vs_w_next_over_W_raw_next` = 0.501 (p = 0.116) only re-tests the deterministic part
of Def. 6.9. `gini_delta_slope` = 0.000534 per epoch and `gini_verdict` = "amplification by
feedback (published Gini grows faster than input Gini)", but that slope is fitted over five epochs
one of which has an incomplete publication, so the verdict is descriptive only.
`weight_recompute_mismatches` = 4 of `weight_rows` = 18 published weights were not reproduced.
Traffic is exogenous (`weight_engine_traffic_model.csv`), so rho is the only endogenous feedback
channel and it is saturated at 1.

**Were there malus events with a measurable effect on weight?** No, and this is a limit of the
campaign rather than a result of this experiment. `malus_registry_records` = 0, and every row of
`weight_engine_epoch.csv` carries `psi` = 1.0 with `malus_M` = 0.0: the mechanism is enabled but
never exercised, because the campaign contains no misbehaving actor by design.
`methodology_notes.csv` lists under `not computable on this campaign` — "dump-function effect (none
everywhere); malus trajectory and Delay-event recomputation (registry empty); VRF output y_i (not
logged); per-event network latency and jitter (1 s log resolution, jitter 0 us); packet loss".


## Notable facts and anomalies

* Pooled over the run, two of the three validators miss their expected share: m1 won 331 blocks
  against `E_i` = 298.88 (`p_hat` 0.756, Wilson [0.713, 0.794], expected 0.682) and m2 won 79
  against 110.36 (0.180, [0.147, 0.219], expected 0.252). m3 is the only one inside its interval
  (28 won against 28.76 expected).
* The KS against `2*Dmax*Beta(1,n)` rejects (`ks_beta_pooled_p` < 0.001) while the KS against the
  exact Monte Carlo of the implemented sortition does not (`ks_mc_pooled_p` = 0.168). The first
  rejection is the expected outcome, not a failure: `ks_beta_note` states "iid-uniform delays
  assumed (Prop. 5.18); invalid for concentrated weights". The reference test is the second, and it
  passes.
* The longest streak of consecutive wins, `L_max_observed` = 16, is compatible with the sortition
  alone (`L_max_mc_mean` = 14.02, `L_max_mc_p_value` = 0.269), but the repeat probability is not:
  `repeat_prob_observed` = 0.661 against `repeat_prob_mc_mean` = 0.534, `repeat_prob_mc_p_value`
  < 0.001. Wins persist from block to block more than the weights alone explain.
* Every failed weight recomputation lands on the two heavy clusters, and the gap is quantised:
  `implied_raw_delta_over_esg_miner` takes the values 1.0, 1.3332, 2.0 and 1.0, i.e. the published
  raw weight exceeds the independent recomputation by one or two whole `esg_miner` units. m3
  reproduces exactly in every epoch in which it published.
* Model consistency: `delay_recompute_mismatch_rounds` = 0 — the delay recomputed from the logged
  score reproduces the logged delay on every candidate round — while `phi_mismatch_rounds` = 5
  rounds have miners disagreeing on the feedback term Phi. One of the 18 Prop. 5.17 classes rejects
  (epoch 5, m3, n = 7, `ks_p` = 0.0407, `mean_gap_x_rate` = 2.007 against `expected_mean` = 1.0),
  which over 18 tests at alpha = 0.05 is what chance alone produces.
* Realised concentration exceeds the concentration the weights imply: `HHI_p_hat_pooled` = 0.608
  against `HHI_p_theoretical_pooled` = 0.533, and the pooled Gini of the observed shares is 0.461
  against 0.411 for the expected ones.

Upstream gap: phase 3 reports `phi_mismatch_rounds` as a bare count, with no per-round breakdown in
any sheet, so the 5 divergent rounds cannot be attributed to a miner or a height from `phase3/`.

