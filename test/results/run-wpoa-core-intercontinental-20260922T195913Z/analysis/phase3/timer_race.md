# The timer race

> The margin between the two fastest delays is the window in which an inversion can occur. This report carries the margin itself, what the timing noise is made of, and the two propositions that bound it.


## The winner's real score

Every `_public` quantity in the next section is derived from the PUBLIC Efraimidis score, `HMAC-SHA256(seed, address)` — the only form computable for a validator whose secret key this node does not hold. Under private sortition the election draws from a VRF under each proposer's own key, so the public score is **statistically independent** of the one the timers were set from: `inversion_rate_public` has expectation `1 - 1/n` whatever the protocol does, and `corr(dt_prev, delay_public)` has expectation 0. Those columns cannot show the mechanism working **or** broken.

This section uses the winner's REAL score instead, recomputed from the VRF reveal its own block carries — the same recomputation the validator performs to enforce the time bar.

| quantity | value | works | decoupled |
|---|---:|---:|---:|
| rounds with a real score | 6443 |  |  |
| corr(dt_prev, delay_true) — Q1 | 0.26658 | ~1 | ~0 |
| residual mean (s) | 8.72053 | ~0 | < 0 |
| residual sd (s) | 14.25510 | ~sigma S1 | ~sd(band) |
| mean score_norm of winner — Q2 | 0.55482 | 0.5 | ~1 |
| KS vs U(0,1), p — Q2 | 0.00000 | not rej. | ~0 |
| winner is the argmin (KS not rejected) | no | true | false |

Q2 needs only the winner because the minimum of the field is `Exp(W)`, so `1 - exp(-W*min)` is exactly `U(0,1)` (Prop. 5.10); a winner drawn without regard to score carries its own score instead, whose normalised value piles up against 1.

**Read the pooled KS line with the split below, not on its own.** A round won *at the top of the delay band* — the winner's timer ran all the way out to `T(1+delta) + lambda*Phi` — is a round in which the lower-score validators did not propose at all. Its winner scores against its own draw rather than the minimum of the field, so its `score_norm` sits against 1 by construction. That is a liveness question, not an ordering one, and pooling it with the racing rounds makes a KS test reject a mechanism that the racing rounds show working.

| quantity | racing rounds | won at the band top |
|---|---:|---:|
| rounds | 6020 | 423 |
| share of measured rounds | | 0.06564 |
| corr(dt_prev, delay_true) | 0.24251 | — |
| residual sd (s) | 13.86342 | — |
| mean score_norm of winner | 0.52360 | — |
| KS vs U(0,1), p | 0.00000 | — |

## The public-score model audit

Kept, and suffixed `_public`, because these numbers have been published. Read them as an audit of the model and its inputs, never as a statement about who actually won.

| quantity | value |
|---|---|
| rounds measured | 6444 |
| margins observed | 6444 |
| mean margin G (s) | 2.80324 |
| KS vs Beta(1,n) — straw man, p | 0.00000 |
| KS vs simulated exact — reference, p | 0.70134 |
| sigma S1 (topology) | 0.031353 |
| sigma S2 (scheduler residual, public) | 15.218849 |
| inversion bound (Prop. 5.18, public) | 1.00000 |
| inversion probability, MC with sigma_S2 (public) | 0.73188 |
| inversions observed (public) | 5152 |
| inversion rate observed (public) | 0.79963 |

The Beta(1,n) test is a **straw man**: it assumes uniform weights and is expected to reject whenever they are not uniform. The reference test is the KS against the simulated exact distribution of the implemented sortition.

S1 is the propagation term: the spread of the end-to-end one-way delay between validator pairs, over the shortest paths of the map this run used. Under an emulated map it is a measurement; in the native regime every node is a local process, so there is no map and S1 is reported as 0 because it is absent, not because it came out small. Either way the bound below rests on S2 alone -- whether the two sources should be combined is a modelling decision that has not been taken here, so S1 is reported beside the bound and not inside it.

![margin distribution](../plots/margin_distribution.png)
![sigma decomposition](../plots/sigma_decomposition.png)
![prop517 gap by validator](../plots/prop517_gap_by_validator.png)
![inversion bound vs observed](../plots/inversion_bound_vs_observed.png)

