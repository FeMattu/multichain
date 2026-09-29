# Figures

Drawn from `analysis/phase2` and `analysis/phase3` only — never from raw data, so a figure and a test can never disagree about the same quantity.

## Aggregate figures

Each of these reads the same at three validators and at thirty.

- [`weight_vs_election.png`](weight_vs_election.png)
- [`weights_boxplot_per_epoch.png`](weights_boxplot_per_epoch.png)
- [`weights_over_time.png`](weights_over_time.png)
- [`election_share_distribution.png`](election_share_distribution.png)
- [`concentration_over_time.png`](concentration_over_time.png)
- [`esg_scores.png`](esg_scores.png)
- [`gini_delta_trajectory.png`](gini_delta_trajectory.png)
- [`margin_distribution.png`](margin_distribution.png)
- [`rho_vs_next_weight.png`](rho_vs_next_weight.png)
- [`traffic_per_epoch.png`](traffic_per_epoch.png)
- [`p_value_uniformity.png`](p_value_uniformity.png)
- [`wilson_violation_heatmap.png`](wilson_violation_heatmap.png)
- [`residual_boxplot_by_validator.png`](residual_boxplot_by_validator.png)
- [`delay_recompute_mismatch.png`](delay_recompute_mismatch.png)
- [`rho_feedback_by_validator.png`](rho_feedback_by_validator.png)
- [`longitudinal_logratio.png`](longitudinal_logratio.png)
- [`sign_test_by_validator.png`](sign_test_by_validator.png)
- [`sigma_decomposition.png`](sigma_decomposition.png)
- [`prop517_gap_by_validator.png`](prop517_gap_by_validator.png)
- [`inversion_bound_vs_observed.png`](inversion_bound_vs_observed.png)
- [`phi_over_time.png`](phi_over_time.png)
- [`malus_action_funnel.png`](malus_action_funnel.png)
- [`malus_state_trajectory.png`](malus_state_trajectory.png)
- [`malus_detection_latency.png`](malus_detection_latency.png)
- [`malus_weight_effect.png`](malus_weight_effect.png)
- [`malus_invariant_audit.png`](malus_invariant_audit.png)
- [`rho_effect_weight.png`](rho_effect_weight.png)
- [`rho_effect_election.png`](rho_effect_election.png)

## Per entity

Above 6 entities a figure that draws one series each stops being readable, so those are written one file per entity instead of as a grid of small multiples — separate files can be looked at one at a time and composed by whoever needs them composed.

- [`esg_scores/`](esg_scores/) — 2 file(s)
