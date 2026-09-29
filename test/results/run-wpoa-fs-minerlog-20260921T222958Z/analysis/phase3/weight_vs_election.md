# Weight versus probability of election

> The headline comparison of this experiment. For each epoch and each validator: the share of blocks the **final weight** entitled it to, against the share it actually won, with a 95% Wilson interval around the observed share and a joint goodness-of-fit test over all validators of the epoch.

## What is being compared

`p_theoretical` is built from `effective_weight_after_malus_and_dumping` — the quantity the election **actually consumes**, after the malus factor and after the dumping function — and is block-weighted across the rounds of the epoch, so an epoch whose weights moved is summarised by what was in force rather than by a snapshot of either end.

`p_hat = O_i / B` is the observed share. The Wilson interval is the 95% score interval around it; it stays inside [0,1] and has sensible width at `O_i = 0`, where the textbook interval collapses to zero.

**Epochs [1] are excluded**: their rounds lie at or below `setup-first-blocks = 112`, where the chain is governed by native MultiChain round robin rather than by wPoA. Testing them would measure the wrong mechanism.

## Per-epoch, per-validator

| epoch | validator | w_final | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---|---:|---:|---:|---:|---:|---|---|
| 2 | `14zXbtYFEypA` | 77 | 0.0482 | 0 | 40 | 0.0000 | [0.0000, 0.0876] | yes |
| 2 | `162PqeW6xHCs` | 273 | 0.1347 | 6 | 40 | 0.1500 | [0.0706, 0.2907] | yes |
| 2 | `1D6m6XANPew4` | 250 | 0.1157 | 3 | 40 | 0.0750 | [0.0258, 0.1986] | yes |
| 2 | `1DEgPiSmRTvH` | 393 | 0.1842 | 6 | 40 | 0.1500 | [0.0706, 0.2907] | yes |
| 2 | `1HhYACu8MLvD` | 366 | 0.1703 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 2 | `1NYZc5JBmxEU` | 339 | 0.1592 | 3 | 40 | 0.0750 | [0.0258, 0.1986] | yes |
| 2 | `1QzD9EtfXcbs` | 406 | 0.1877 | 4 | 40 | 0.1000 | [0.0396, 0.2305] | yes |
| 3 | `14zXbtYFEypA` | 92 | 0.0391 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | no |
| 3 | `162PqeW6xHCs` | 326 | 0.1378 | 7 | 40 | 0.1750 | [0.0875, 0.3195] | yes |
| 3 | `1D6m6XANPew4` | 320 | 0.1339 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 3 | `1DEgPiSmRTvH` | 445 | 0.1901 | 12 | 40 | 0.3000 | [0.1807, 0.4543] | yes |
| 3 | `1HhYACu8MLvD` | 308 | 0.1392 | 2 | 40 | 0.0500 | [0.0138, 0.1650] | yes |
| 3 | `1NYZc5JBmxEU` | 321 | 0.1415 | 3 | 40 | 0.0750 | [0.0258, 0.1986] | yes |
| 3 | `1QzD9EtfXcbs` | 523 | 0.2185 | 6 | 40 | 0.1500 | [0.0706, 0.2907] | yes |
| 4 | `14zXbtYFEypA` | 87 | 0.0379 | 1 | 40 | 0.0250 | [0.0044, 0.1288] | yes |
| 4 | `162PqeW6xHCs` | 369 | 0.1552 | 4 | 40 | 0.1000 | [0.0396, 0.2305] | yes |
| 4 | `1D6m6XANPew4` | 296 | 0.1288 | 4 | 40 | 0.1000 | [0.0396, 0.2305] | yes |
| 4 | `1DEgPiSmRTvH` | 373 | 0.1656 | 3 | 40 | 0.0750 | [0.0258, 0.1986] | yes |
| 4 | `1HhYACu8MLvD` | 346 | 0.1456 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 4 | `1NYZc5JBmxEU` | 413 | 0.1703 | 10 | 40 | 0.2500 | [0.1419, 0.4019] | yes |
| 4 | `1QzD9EtfXcbs` | 444 | 0.1965 | 13 | 40 | 0.3250 | [0.2008, 0.4798] | no |
| 5 | `14zXbtYFEypA` | 81 | 0.0358 | 0 | 40 | 0.0000 | [0.0000, 0.0876] | yes |
| 5 | `162PqeW6xHCs` | 359 | 0.1565 | 8 | 40 | 0.2000 | [0.1050, 0.3476] | yes |
| 5 | `1D6m6XANPew4` | 306 | 0.1321 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 5 | `1DEgPiSmRTvH` | 404 | 0.1729 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 5 | `1HhYACu8MLvD` | 320 | 0.1407 | 6 | 40 | 0.1500 | [0.0706, 0.2907] | yes |
| 5 | `1NYZc5JBmxEU` | 337 | 0.1521 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 5 | `1QzD9EtfXcbs` | 493 | 0.2100 | 3 | 40 | 0.0750 | [0.0258, 0.1986] | no |
| 6 | `14zXbtYFEypA` | 108 | 0.0408 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |
| 6 | `162PqeW6xHCs` | 382 | 0.1533 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |
| 6 | `1D6m6XANPew4` | 319 | 0.1289 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |
| 6 | `1DEgPiSmRTvH` | 403 | 0.1651 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |
| 6 | `1HhYACu8MLvD` | 395 | 0.1514 | 3 | 21 | 0.1429 | [0.0498, 0.3464] | yes |
| 6 | `1NYZc5JBmxEU` | 368 | 0.1467 | 5 | 21 | 0.2381 | [0.1063, 0.4509] | yes |
| 6 | `1QzD9EtfXcbs` | 536 | 0.2137 | 5 | 21 | 0.2381 | [0.1063, 0.4509] | yes |

## Pooled over every measured epoch

| validator | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---:|---:|---:|---:|---|---|
| `14zXbtYFEypA` | 0.0403 | 8 | 181 | 0.0442 | [0.0226, 0.0848] | yes |
| `162PqeW6xHCs` | 0.1469 | 27 | 181 | 0.1492 | [0.1046, 0.2083] | yes |
| `1D6m6XANPew4` | 0.1278 | 23 | 181 | 0.1271 | [0.0862, 0.1835] | yes |
| `1DEgPiSmRTvH` | 0.1767 | 32 | 181 | 0.1768 | [0.1281, 0.2389] | yes |
| `1HhYACu8MLvD` | 0.1492 | 25 | 181 | 0.1381 | [0.0953, 0.1959] | yes |
| `1NYZc5JBmxEU` | 0.1547 | 26 | 181 | 0.1436 | [0.1000, 0.2022] | yes |
| `1QzD9EtfXcbs` | 0.2044 | 31 | 181 | 0.1713 | [0.1234, 0.2328] | yes |

## Joint test per epoch (chi-square / exact / Monte Carlo)

| epoch | blocks | validators | method | statistic | p | reject at 0.05 | TV | round-by-round p |
|---|---:|---:|---|---:|---:|---|---:|---:|
| 2 | 31 | 7 | monte_carlo_multinomial | 6.352 | 0.3762 | no | 0.2355 | 0.3198 |
| 3 | 40 | 7 | monte_carlo_multinomial | 14.924 | 0.0215 | YES | 0.2330 | 0.0217 |
| 4 | 40 | 7 | monte_carlo_multinomial | 8.170 | 0.2168 | no | 0.2082 | 0.2158 |
| 5 | 40 | 7 | monte_carlo_multinomial | 8.849 | 0.1742 | no | 0.1979 | 0.1759 |
| 6 | 21 | 7 | monte_carlo_multinomial | 4.056 | 0.6687 | no | 0.1702 | 0.6698 |
| all | 172 | 7 | chi2_asymptotic | 1.340 | 0.9694 | no | 0.0328 | 0.7792 |

## How to read this

- **The interval, not the point.** A `p_hat` far from `p_theoretical` means nothing if the interval is wide; with a handful of blocks per epoch it usually is. The mean interval width here is **0.1990**, which is the resolution of this run.
- **Multiple comparisons.** 3 of 35 intervals excluded the entitled share; about 1.8 are expected to by chance alone at alpha = 0.05. Only a count well above the expectation is a finding.
- **The joint test is the real one.** The per-validator intervals say *which* validator is out of line; the chi-square says whether the epoch as a whole is distinguishable from weighted sortition.
- **Round-by-round when the shares moved.** Where an epoch's shares changed mid-epoch, the pooled multinomial tests a null that was never in force, and the round-by-round Monte-Carlo p-value in the last column is the one to read.

The corresponding figure is `plots/weight_vs_election.png`, produced by `plotting/generate_plots.py`.
