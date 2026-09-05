# run6-tbt-10s / nazionale

| | |
|---|---|
| Target block time | 10 s |
| Damping function (dumpfunction) | none |
| Malus | enabled, registry empty (0 records) |
| Epoch length | 100 blocks |
| Measured epochs | 5 (3 fully measured), epochs 2–6 |
| Blocks | 446 measured of 598 total (setup 152), final height 598 |
| Sortition | delta 0.5, lambda 0.2, RANDAO lookback 1 |
| Weight engine | kappa 100, alpha 0.2, lambda_w 0.5 |


## Epoch by epoch, per validator

#### Epoch 2 — 47 blocks, heights 100–199, buried

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.672 | 0.532 | expected OUTSIDE Wilson 95 % CI [0.392, 0.667] |
| m2 | 0.260 | 0.383 | expected inside Wilson 95 % CI [0.258, 0.526] |
| m3 | 0.068 | 0.085 | expected inside Wilson 95 % CI [0.034, 0.199] |

Expected share outside the Wilson 95 % CI for m1 (observed 0.532, CI [0.392, 0.667], expected 0.672).
Weight engine: 1 of 3 published weights were not reproduced by the independent recomputation: m1 (implied raw delta over esg_miner 1.0).

#### Epoch 3 — 100 blocks, heights 200–299, buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.674 | 0.610 | expected inside Wilson 95 % CI [0.512, 0.700] |
| m2 | 0.261 | 0.280 | expected inside Wilson 95 % CI [0.201, 0.375] |
| m3 | 0.065 | 0.110 | expected inside Wilson 95 % CI [0.063, 0.186] |

Weight engine: 2 of 3 published weights were not reproduced by the independent recomputation: m1 (implied raw delta over esg_miner 1.0), m2 (implied raw delta over esg_miner 1.3426).

#### Epoch 4 — 100 blocks, heights 300–399, buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.703 | 0.710 | expected inside Wilson 95 % CI [0.615, 0.790] |
| m2 | 0.230 | 0.240 | expected inside Wilson 95 % CI [0.167, 0.332] |
| m3 | 0.067 | 0.050 | expected inside Wilson 95 % CI [0.022, 0.112] |

Weight engine: 1 of 3 published weights were not reproduced by the independent recomputation: m1 (implied raw delta over esg_miner 0.9999).

#### Epoch 5 — 100 blocks, heights 400–499, buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.680 | 0.830 | expected OUTSIDE Wilson 95 % CI [0.745, 0.891] |
| m2 | 0.256 | 0.170 | expected OUTSIDE Wilson 95 % CI [0.109, 0.255] |
| m3 | 0.064 | 0.000 | expected OUTSIDE Wilson 95 % CI [0.000, 0.037] |

GoF rejected at alpha = 0.05 (`chi2_asymptotic`, p = 0.00187); the deviation is carried by m1, which won 83 blocks against 68.01 expected.
Expected share outside the Wilson 95 % CI for m1 (observed 0.830, CI [0.745, 0.891], expected 0.680); m2 (observed 0.170, CI [0.109, 0.255], expected 0.256); m3 (observed 0.000, CI [0.000, 0.037], expected 0.064).
Weight engine: 2 of 3 published weights were not reproduced by the independent recomputation: m1 (implied raw delta over esg_miner 2.0001), m2 (implied raw delta over esg_miner 0.9998).

#### Epoch 6 — 99 blocks, heights 500–599, not buried — weights changed inside the epoch

| node | p_expected | p_observed | verdict |
|---|---|---|---|
| m1 | 0.677 | 0.636 | expected inside Wilson 95 % CI [0.538, 0.724] |
| m2 | 0.260 | 0.273 | expected inside Wilson 95 % CI [0.195, 0.368] |
| m3 | 0.064 | 0.091 | expected inside Wilson 95 % CI [0.049, 0.164] |

Inversion rate 0.141 against a pooled 0.094 for the run (1.50 x); 8 of the inverted rounds coincided with a competing block.
Streaks: repeat probability 0.643 against a Monte Carlo mean of 0.530 (p = 0.0345).


## Trend by epoch

| epoch | blocks | GoF p (method) | HHI | N_eff | Nakamoto ½ | timer race KS p | inversion rate | block success | WE conformity |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 47 | 0.11 (exact) | 0.437 | 2.29 | 1 | 0.933 | 0.064 | 0.870 | 2/3 |
| 3 | 100 | 0.145 (chi2) | 0.463 | 2.16 | 1 | 0.937 | 0.110 | 0.926 | 0/3 |
| 4 | 100 | 0.79 (chi2) | 0.564 | 1.77 | 1 | 0.0702 | 0.070 | 0.935 | 2/3 |
| 5 | 100 | 0.00187* (chi2) | 0.718 | 1.39 | 1 | 0.0253 | 0.070 | 0.971 | 1/3 |
| 6 | 99 | 0.483 (chi2) | 0.488 | 2.05 | 1 | 0.169 | 0.141 | 0.868 | 0/3 |

1 weight-engine epoch falls outside the measured range (epoch 1): it is a setup epoch or the trailing partial epoch, not missing data.
Clusters that published no weight at all, and therefore lower the conformity ratio by absence rather than by mismatch: epoch 3 (1 of 3), epoch 6 (3 of 3).


## How the system behaved

**Does the system converge to the theoretical behaviour?** Pooled over the run, almost exactly:
`gof_pooled_method` = `chi2_asymptotic` with `gof_pooled_p` = 0.989 (`gof_pooled_min_expected` =
29.03, round-by-round Monte Carlo `gof_pooled_mc_round_by_round_p` = 0.993), and `TV_pooled` =
`MaxAE_pooled` = 0.003 — three tenths of a share point of total variation. That agreement is an
average, not a property of the individual epochs: 1 of the 5 tested epochs rejects on its own
(`epochs_gof_reject_alpha05` of `epochs_gof_tested`), and the longitudinal fit gives
`glm_beta1_logw` = 1.748 with CI [1.504, 1.992], excluding 1. Selection is super-proportional epoch
by epoch; the epoch deviations happen to cancel when pooled, so the pooled test is the weakest
evidence in this experiment, not the strongest.

**Does the network introduce a measurable deviation from proportionality?** Not the network.
`sigma_S1_s` = 0.0051 s is the maximum one-way propagation latency between miners taken from the
topology, described in `wpoa_sigma.csv` as "propagation latency; deterministic (jitter 0 us), not a
variance": the Shadow topologies declare zero jitter, so latency contributes no randomness. The
race is decided by `sigma_S2_s` = 0.70 s, whose `what_it_measures` reads "quantisation of the 1 s
time bar and block timestamps plus miner loop granularity" (median 0.85 s, p90 1.84 s). The
observed `inversion_rate` = 0.094 [0.070, 0.125] lies well above the Prop. 5.18 bound at the
topology sigma (`inversion_bound_S1` = 0.032) and well below the bound at the scheduler sigma
(`inversion_bound_S2` = 0.843), and its interval covers the Gaussian-noise Monte Carlo at sigma_S2
(`inversion_mc_prob_gaussian_S2` = 0.103). `inversion_with_fork_n` = 20 inversions coincided with a
competing block.

**Did the weight engine reward conformity in later epochs?** Not measurably.
`spearman_rho_to_w_next_pooled` = 0.200 with `spearman_p_pooled` = 0.555. The reason is the
absence of variation to correlate: 10 of the 11 epoch pairs have rho exactly 1
(`n_pairs_rho_equal_1`), and the tautological control
`spearman_rho_e_vs_w_next_over_W_raw_next` = 0.501 (p = 0.116) only re-tests the deterministic part
of Def. 6.9. `gini_delta_slope` = 0.000556 per epoch with `gini_verdict` = "amplification by
feedback (published Gini grows faster than input Gini)", fitted over five epochs one of which has
an incomplete publication, so the verdict is descriptive only. `weight_recompute_mismatches` = 6 of
`weight_rows` = 18 published weights were not reproduced. Traffic is exogenous
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

* The longitudinal sheet contradicts the pooled fit. Between `epoch_first` and `epoch_last` of
  `wpoa_longitudinal_validators.csv`, m1 gained 0.220 of observed share against a theoretical gain
  of 0.006, and its first and last Wilson intervals do not overlap (`intervals_overlap` = 0); m3
  lost 0.110 against a theoretical −0.001, also with `intervals_overlap` = 0. The two validators drifted in opposite directions while the
  weights that were supposed to drive them barely moved.
* Pooled over the run every validator sits inside its Wilson interval and the fit is essentially
  exact: m1 won 303 blocks against `E_i` = 304.30, m2 114 against 112.67, m3 29 against 29.03. Read
  together with the previous bullet, the pooled agreement is cancellation between epochs, not
  stability.
* The KS against `2*Dmax*Beta(1,n)` rejects (`ks_beta_pooled_p` < 0.001) while the KS against the
  exact Monte Carlo of the implemented sortition does not (`ks_mc_pooled_p` = 0.898). The first
  rejection is the expected outcome, not a failure: `ks_beta_note` states "iid-uniform delays
  assumed (Prop. 5.18); invalid for concentrated weights". The reference test is the second, and it
  passes comfortably.
* The longest streak of consecutive wins, `L_max_observed` = 16, is compatible with the sortition
  alone (`L_max_mc_mean` = 14.11, `L_max_mc_p_value` = 0.281), but the repeat probability is not:
  `repeat_prob_observed` = 0.645 against `repeat_prob_mc_mean` = 0.534, `repeat_prob_mc_p_value`
  < 0.001.
* Every failed weight recomputation lands on the two heavy clusters and the gap is quantised:
  `implied_raw_delta_over_esg_miner` takes the values 1.0, 1.3426, 1.0, 0.9999, 0.9998 and 2.0001,
  i.e. the published raw weight exceeds the independent recomputation by one or two whole
  `esg_miner` units. m3 reproduces exactly in every epoch in which it published.
* Model consistency: `delay_recompute_mismatch_rounds` = 0 while `phi_mismatch_rounds` = 5 rounds
  have miners disagreeing on the feedback term Phi. Two of the 18 Prop. 5.17 classes reject — epoch
  4 m2 (n = 29, `ks_p` = 0.0322, `mean_gap_x_rate` = 0.733) and epoch 5 m2 (n = 20, `ks_p` =
  0.0245, `mean_gap_x_rate` = 1.574) — both on the same validator and in opposite directions
  against `expected_mean` = 1.0.

Upstream gap: phase 3 reports `phi_mismatch_rounds` as a bare count, with no per-round breakdown in
any sheet, so the 5 divergent rounds cannot be attributed to a miner or a height from `phase3/`.

