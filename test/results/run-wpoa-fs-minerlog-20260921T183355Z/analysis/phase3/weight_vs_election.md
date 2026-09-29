# Weight versus probability of election

> The headline comparison of this experiment. For each epoch and each validator: the share of blocks the **final weight** entitled it to, against the share it actually won, with a 95% Wilson interval around the observed share and a joint goodness-of-fit test over all validators of the epoch.

## What is being compared

`p_theoretical` is built from `effective_weight_after_malus_and_dumping` — the quantity the election **actually consumes**, after the malus factor and after the dumping function — and is block-weighted across the rounds of the epoch, so an epoch whose weights moved is summarised by what was in force rather than by a snapshot of either end.

`p_hat = O_i / B` is the observed share. The Wilson interval is the 95% score interval around it; it stays inside [0,1] and has sensible width at `O_i = 0`, where the textbook interval collapses to zero.

**Epochs [1] are excluded**: their rounds lie at or below `setup-first-blocks = 112`, where the chain is governed by native MultiChain round robin rather than by wPoA. Testing them would measure the wrong mechanism.

## Per-epoch, per-validator

| epoch | validator | w_final | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---|---:|---:|---:|---:|---:|---|---|
| 2 | `14rryUruNVyj` | 77 | 0.0481 | 1 | 40 | 0.0250 | [0.0044, 0.1288] | yes |
| 2 | `171aKpPRK2RX` | 339 | 0.1622 | 6 | 40 | 0.1500 | [0.0706, 0.2907] | yes |
| 2 | `1DM3uGZzhMMc` | 359 | 0.1666 | 15 | 40 | 0.3750 | [0.2422, 0.5297] | no |
| 2 | `1MxYgqhasdDn` | 389 | 0.1816 | 0 | 40 | 0.0000 | [0.0000, 0.0876] | no |
| 2 | `1PH1kNWq4hXs` | 406 | 0.1915 | 8 | 40 | 0.2000 | [0.1050, 0.3476] | yes |
| 2 | `1PdDpXXDJFpV` | 273 | 0.1340 | 2 | 40 | 0.0500 | [0.0138, 0.1650] | yes |
| 2 | `1a6jrgAX1oUv` | 245 | 0.1161 | 0 | 40 | 0.0000 | [0.0000, 0.0876] | no |
| 3 | `14rryUruNVyj` | 92 | 0.0392 | 2 | 40 | 0.0500 | [0.0138, 0.1650] | yes |
| 3 | `171aKpPRK2RX` | 321 | 0.1420 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 3 | `1DM3uGZzhMMc` | 312 | 0.1405 | 3 | 40 | 0.0750 | [0.0258, 0.1986] | yes |
| 3 | `1MxYgqhasdDn` | 447 | 0.1908 | 10 | 40 | 0.2500 | [0.1419, 0.4019] | yes |
| 3 | `1PH1kNWq4hXs` | 516 | 0.2167 | 7 | 40 | 0.1750 | [0.0875, 0.3195] | yes |
| 3 | `1PdDpXXDJFpV` | 322 | 0.1368 | 11 | 40 | 0.2750 | [0.1611, 0.4283] | no |
| 3 | `1a6jrgAX1oUv` | 320 | 0.1340 | 2 | 40 | 0.0500 | [0.0138, 0.1650] | yes |
| 4 | `14rryUruNVyj` | 87 | 0.0376 | 0 | 40 | 0.0000 | [0.0000, 0.0876] | yes |
| 4 | `171aKpPRK2RX` | 413 | 0.1690 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 4 | `1DM3uGZzhMMc` | 350 | 0.1461 | 7 | 40 | 0.1750 | [0.0875, 0.3195] | yes |
| 4 | `1MxYgqhasdDn` | 377 | 0.1657 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 4 | `1PH1kNWq4hXs` | 452 | 0.1974 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 4 | `1PdDpXXDJFpV` | 373 | 0.1550 | 8 | 40 | 0.2000 | [0.1050, 0.3476] | yes |
| 4 | `1a6jrgAX1oUv` | 300 | 0.1293 | 2 | 40 | 0.0500 | [0.0138, 0.1650] | yes |
| 5 | `14rryUruNVyj` | 81 | 0.0357 | 1 | 40 | 0.0250 | [0.0044, 0.1288] | yes |
| 5 | `171aKpPRK2RX` | 337 | 0.1515 | 7 | 40 | 0.1750 | [0.0875, 0.3195] | yes |
| 5 | `1DM3uGZzhMMc` | 320 | 0.1405 | 8 | 40 | 0.2000 | [0.1050, 0.3476] | yes |
| 5 | `1MxYgqhasdDn` | 404 | 0.1726 | 4 | 40 | 0.1000 | [0.0396, 0.2305] | yes |
| 5 | `1PH1kNWq4hXs` | 493 | 0.2100 | 10 | 40 | 0.2500 | [0.1419, 0.4019] | yes |
| 5 | `1PdDpXXDJFpV` | 359 | 0.1563 | 6 | 40 | 0.1500 | [0.0706, 0.2907] | yes |
| 5 | `1a6jrgAX1oUv` | 310 | 0.1334 | 4 | 40 | 0.1000 | [0.0396, 0.2305] | yes |
| 6 | `14rryUruNVyj` | 108 | 0.0408 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |
| 6 | `171aKpPRK2RX` | 368 | 0.1468 | 0 | 21 | 0.0000 | [0.0000, 0.1546] | yes |
| 6 | `1DM3uGZzhMMc` | 395 | 0.1515 | 3 | 21 | 0.1429 | [0.0498, 0.3464] | yes |
| 6 | `1MxYgqhasdDn` | 403 | 0.1652 | 3 | 21 | 0.1429 | [0.0498, 0.3464] | yes |
| 6 | `1PH1kNWq4hXs` | 536 | 0.2138 | 5 | 21 | 0.2381 | [0.1063, 0.4509] | yes |
| 6 | `1PdDpXXDJFpV` | 382 | 0.1534 | 3 | 21 | 0.1429 | [0.0498, 0.3464] | yes |
| 6 | `1a6jrgAX1oUv` | 315 | 0.1285 | 5 | 21 | 0.2381 | [0.1063, 0.4509] | yes |

## Pooled over every measured epoch

| validator | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---:|---:|---:|---:|---|---|
| `14rryUruNVyj` | 0.0402 | 6 | 181 | 0.0331 | [0.0153, 0.0704] | yes |
| `171aKpPRK2RX` | 0.1551 | 27 | 181 | 0.1492 | [0.1046, 0.2083] | yes |
| `1DM3uGZzhMMc` | 0.1488 | 36 | 181 | 0.1989 | [0.1473, 0.2630] | yes |
| `1MxYgqhasdDn` | 0.1762 | 26 | 181 | 0.1436 | [0.1000, 0.2022] | yes |
| `1PH1kNWq4hXs` | 0.2050 | 35 | 181 | 0.1934 | [0.1425, 0.2570] | yes |
| `1PdDpXXDJFpV` | 0.1464 | 30 | 181 | 0.1657 | [0.1186, 0.2267] | yes |
| `1a6jrgAX1oUv` | 0.1282 | 13 | 181 | 0.0718 | [0.0425, 0.1190] | no |

## Joint test per epoch (chi-square / exact / Monte Carlo)

| epoch | blocks | validators | method | statistic | p | reject at 0.05 | TV | round-by-round p |
|---|---:|---:|---|---:|---:|---|---:|---:|
| 2 | 32 | 7 | monte_carlo_multinomial | 29.164 | 0.0004 | YES | 0.3961 | 0.0009 |
| 3 | 40 | 7 | monte_carlo_multinomial | 10.160 | 0.1109 | no | 0.2081 | 0.1134 |
| 4 | 40 | 7 | monte_carlo_multinomial | 6.859 | 0.3259 | no | 0.1893 | 0.3309 |
| 5 | 40 | 7 | monte_carlo_multinomial | 3.153 | 0.7988 | no | 0.1230 | 0.7970 |
| 6 | 21 | 7 | monte_carlo_multinomial | 6.716 | 0.3369 | no | 0.1883 | 0.3394 |
| all | 173 | 7 | chi2_asymptotic | 9.484 | 0.1481 | no | 0.0958 | 0.4948 |

## How to read this

- **The interval, not the point.** A `p_hat` far from `p_theoretical` means nothing if the interval is wide; with a handful of blocks per epoch it usually is. The mean interval width here is **0.1952**, which is the resolution of this run.
- **Multiple comparisons.** 4 of 35 intervals excluded the entitled share; about 1.8 are expected to by chance alone at alpha = 0.05. Only a count well above the expectation is a finding.
- **The joint test is the real one.** The per-validator intervals say *which* validator is out of line; the chi-square says whether the epoch as a whole is distinguishable from weighted sortition.
- **Round-by-round when the shares moved.** Where an epoch's shares changed mid-epoch, the pooled multinomial tests a null that was never in force, and the round-by-round Monte-Carlo p-value in the last column is the one to read.

The corresponding figure is `plots/weight_vs_election.png`, produced by `plotting/generate_plots.py`.
