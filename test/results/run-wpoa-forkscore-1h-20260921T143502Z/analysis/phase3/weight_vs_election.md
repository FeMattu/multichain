# Weight versus probability of election

> The headline comparison of this experiment. For each epoch and each validator: the share of blocks the **final weight** entitled it to, against the share it actually won, with a 95% Wilson interval around the observed share and a joint goodness-of-fit test over all validators of the epoch.

## What is being compared

`p_theoretical` is built from `effective_weight_after_malus_and_dumping` — the quantity the election **actually consumes**, after the malus factor and after the dumping function — and is block-weighted across the rounds of the epoch, so an epoch whose weights moved is summarised by what was in force rather than by a snapshot of either end.

`p_hat = O_i / B` is the observed share. The Wilson interval is the 95% score interval around it; it stays inside [0,1] and has sensible width at `O_i = 0`, where the textbook interval collapses to zero.

**Epochs [1] are excluded**: their rounds lie at or below `setup-first-blocks = 112`, where the chain is governed by native MultiChain round robin rather than by wPoA. Testing them would measure the wrong mechanism.

## Per-epoch, per-validator

| epoch | validator | w_final | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---|---:|---:|---:|---:|---:|---|---|
| 2 | `18VGDtNzFSoy` | 366 | 0.1671 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 2 | `1A9tPhymKcFC` | 393 | 0.1808 | 11 | 40 | 0.2750 | [0.1611, 0.4283] | yes |
| 2 | `1KmKgDW1Vbyd` | 339 | 0.1601 | 10 | 40 | 0.2500 | [0.1419, 0.4019] | yes |
| 2 | `1L51GRy46DAx` | 282 | 0.1358 | 1 | 40 | 0.0250 | [0.0044, 0.1288] | no |
| 2 | `1QrpSHGbytWz` | 256 | 0.1190 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 2 | `1UmL87cqSz7o` | 406 | 0.1891 | 1 | 40 | 0.0250 | [0.0044, 0.1288] | no |
| 2 | `1aS6ZBnfY8iT` | 79 | 0.0481 | 0 | 40 | 0.0000 | [0.0000, 0.0876] | yes |
| 3 | `18VGDtNzFSoy` | 308 | 0.1395 | 7 | 40 | 0.1750 | [0.0875, 0.3195] | yes |
| 3 | `1A9tPhymKcFC` | 445 | 0.1906 | 8 | 40 | 0.2000 | [0.1050, 0.3476] | yes |
| 3 | `1KmKgDW1Vbyd` | 321 | 0.1419 | 8 | 40 | 0.2000 | [0.1050, 0.3476] | yes |
| 3 | `1L51GRy46DAx` | 317 | 0.1361 | 6 | 40 | 0.1500 | [0.0706, 0.2907] | yes |
| 3 | `1QrpSHGbytWz` | 317 | 0.1339 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 3 | `1UmL87cqSz7o` | 523 | 0.2192 | 3 | 40 | 0.0750 | [0.0258, 0.1986] | no |
| 3 | `1aS6ZBnfY8iT` | 91 | 0.0389 | 3 | 40 | 0.0750 | [0.0258, 0.1986] | yes |
| 4 | `18VGDtNzFSoy` | 346 | 0.1456 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 4 | `1A9tPhymKcFC` | 373 | 0.1656 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 4 | `1KmKgDW1Vbyd` | 413 | 0.1703 | 6 | 40 | 0.1500 | [0.0706, 0.2907] | yes |
| 4 | `1L51GRy46DAx` | 369 | 0.1547 | 1 | 40 | 0.0250 | [0.0044, 0.1288] | no |
| 4 | `1QrpSHGbytWz` | 294 | 0.1278 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 4 | `1UmL87cqSz7o` | 449 | 0.1981 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 4 | `1aS6ZBnfY8iT` | 87 | 0.0378 | 1 | 40 | 0.0250 | [0.0044, 0.1288] | yes |
| 5 | `18VGDtNzFSoy` | 320 | 0.1407 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 5 | `1A9tPhymKcFC` | 404 | 0.1729 | 4 | 40 | 0.1000 | [0.0396, 0.2305] | yes |
| 5 | `1KmKgDW1Vbyd` | 337 | 0.1521 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 5 | `1L51GRy46DAx` | 359 | 0.1566 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 5 | `1QrpSHGbytWz` | 306 | 0.1320 | 2 | 40 | 0.0500 | [0.0138, 0.1650] | yes |
| 5 | `1UmL87cqSz7o` | 491 | 0.2099 | 8 | 40 | 0.2000 | [0.1050, 0.3476] | yes |
| 5 | `1aS6ZBnfY8iT` | 81 | 0.0358 | 3 | 40 | 0.0750 | [0.0258, 0.1986] | yes |
| 6 | `18VGDtNzFSoy` | 395 | 0.1515 | 4 | 21 | 0.1905 | [0.0767, 0.4000] | yes |
| 6 | `1A9tPhymKcFC` | 403 | 0.1653 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |
| 6 | `1KmKgDW1Vbyd` | 368 | 0.1469 | 1 | 21 | 0.0476 | [0.0085, 0.2267] | yes |
| 6 | `1L51GRy46DAx` | 382 | 0.1535 | 3 | 21 | 0.1429 | [0.0498, 0.3464] | yes |
| 6 | `1QrpSHGbytWz` | 319 | 0.1290 | 4 | 21 | 0.1905 | [0.0767, 0.4000] | yes |
| 6 | `1UmL87cqSz7o` | 534 | 0.2130 | 6 | 21 | 0.2857 | [0.1381, 0.4996] | yes |
| 6 | `1aS6ZBnfY8iT` | 108 | 0.0408 | 1 | 21 | 0.0476 | [0.0085, 0.2267] | yes |

## Pooled over every measured epoch

| validator | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---:|---:|---:|---:|---|---|
| `18VGDtNzFSoy` | 0.1486 | 38 | 181 | 0.2099 | [0.1570, 0.2750] | no |
| `1A9tPhymKcFC` | 0.1761 | 34 | 181 | 0.1878 | [0.1377, 0.2510] | yes |
| `1KmKgDW1Vbyd` | 0.1550 | 30 | 181 | 0.1657 | [0.1186, 0.2267] | yes |
| `1L51GRy46DAx` | 0.1467 | 20 | 181 | 0.1105 | [0.0727, 0.1645] | yes |
| `1QrpSHGbytWz` | 0.1283 | 25 | 181 | 0.1381 | [0.0953, 0.1959] | yes |
| `1UmL87cqSz7o` | 0.2051 | 23 | 181 | 0.1271 | [0.0862, 0.1835] | no |
| `1aS6ZBnfY8iT` | 0.0402 | 8 | 181 | 0.0442 | [0.0226, 0.0848] | yes |

## Joint test per epoch (chi-square / exact / Monte Carlo)

| epoch | blocks | validators | method | statistic | p | reject at 0.05 | TV | round-by-round p |
|---|---:|---:|---|---:|---:|---|---:|---:|
| 2 | 37 | 7 | monte_carlo_multinomial | 17.085 | 0.0089 | YES | 0.3086 | 0.0126 |
| 3 | 40 | 7 | monte_carlo_multinomial | 6.545 | 0.3572 | no | 0.1530 | 0.3615 |
| 4 | 40 | 7 | monte_carlo_multinomial | 11.235 | 0.0762 | no | 0.2359 | 0.0775 |
| 5 | 40 | 7 | monte_carlo_multinomial | 8.406 | 0.2018 | no | 0.1919 | 0.2037 |
| 6 | 21 | 7 | monte_carlo_multinomial | 3.417 | 0.7593 | no | 0.1799 | 0.7641 |
| all | 178 | 7 | chi2_asymptotic | 12.049 | 0.0609 | no | 0.1077 | 0.1225 |

## How to read this

- **The interval, not the point.** A `p_hat` far from `p_theoretical` means nothing if the interval is wide; with a handful of blocks per epoch it usually is. The mean interval width here is **0.2001**, which is the resolution of this run.
- **Multiple comparisons.** 4 of 35 intervals excluded the entitled share; about 1.8 are expected to by chance alone at alpha = 0.05. Only a count well above the expectation is a finding.
- **The joint test is the real one.** The per-validator intervals say *which* validator is out of line; the chi-square says whether the epoch as a whole is distinguishable from weighted sortition.
- **Round-by-round when the shares moved.** Where an epoch's shares changed mid-epoch, the pooled multinomial tests a null that was never in force, and the round-by-round Monte-Carlo p-value in the last column is the one to read.

The corresponding figure is `plots/weight_vs_election.png`, produced by `plotting/generate_plots.py`.
