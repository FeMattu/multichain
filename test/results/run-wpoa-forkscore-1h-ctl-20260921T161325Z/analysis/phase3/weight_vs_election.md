# Weight versus probability of election

> The headline comparison of this experiment. For each epoch and each validator: the share of blocks the **final weight** entitled it to, against the share it actually won, with a 95% Wilson interval around the observed share and a joint goodness-of-fit test over all validators of the epoch.

## What is being compared

`p_theoretical` is built from `effective_weight_after_malus_and_dumping` — the quantity the election **actually consumes**, after the malus factor and after the dumping function — and is block-weighted across the rounds of the epoch, so an epoch whose weights moved is summarised by what was in force rather than by a snapshot of either end.

`p_hat = O_i / B` is the observed share. The Wilson interval is the 95% score interval around it; it stays inside [0,1] and has sensible width at `O_i = 0`, where the textbook interval collapses to zero.

**Epochs [1] are excluded**: their rounds lie at or below `setup-first-blocks = 112`, where the chain is governed by native MultiChain round robin rather than by wPoA. Testing them would measure the wrong mechanism.

## Per-epoch, per-validator

| epoch | validator | w_final | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---|---:|---:|---:|---:|---:|---|---|
| 2 | `1AQDR6WGsouL` | 393 | 0.1825 | 8 | 40 | 0.2000 | [0.1050, 0.3476] | yes |
| 2 | `1KwjKXWqcTzn` | 273 | 0.1335 | 0 | 40 | 0.0000 | [0.0000, 0.0876] | no |
| 2 | `1LWqTJtUzobS` | 77 | 0.0480 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | no |
| 2 | `1Mk9iunnT37k` | 246 | 0.1162 | 4 | 40 | 0.1000 | [0.0396, 0.2305] | yes |
| 2 | `1Mt8KTvwQkNo` | 406 | 0.1908 | 4 | 40 | 0.1000 | [0.0396, 0.2305] | yes |
| 2 | `1UeDWkdeCAMM` | 339 | 0.1616 | 13 | 40 | 0.3250 | [0.2008, 0.4798] | no |
| 2 | `1bQ1pmcjGhNK` | 362 | 0.1674 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 3 | `1AQDR6WGsouL` | 443 | 0.1899 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 3 | `1KwjKXWqcTzn` | 322 | 0.1369 | 6 | 40 | 0.1500 | [0.0706, 0.2907] | yes |
| 3 | `1LWqTJtUzobS` | 92 | 0.0392 | 1 | 40 | 0.0250 | [0.0044, 0.1288] | yes |
| 3 | `1Mk9iunnT37k` | 321 | 0.1344 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 3 | `1Mt8KTvwQkNo` | 516 | 0.2168 | 10 | 40 | 0.2500 | [0.1419, 0.4019] | yes |
| 3 | `1UeDWkdeCAMM` | 321 | 0.1420 | 1 | 40 | 0.0250 | [0.0044, 0.1288] | no |
| 3 | `1bQ1pmcjGhNK` | 312 | 0.1408 | 4 | 40 | 0.1000 | [0.0396, 0.2305] | yes |
| 4 | `1AQDR6WGsouL` | 376 | 0.1654 | 10 | 40 | 0.2500 | [0.1419, 0.4019] | yes |
| 4 | `1KwjKXWqcTzn` | 373 | 0.1551 | 8 | 40 | 0.2000 | [0.1050, 0.3476] | yes |
| 4 | `1LWqTJtUzobS` | 87 | 0.0377 | 1 | 40 | 0.0250 | [0.0044, 0.1288] | yes |
| 4 | `1Mk9iunnT37k` | 298 | 0.1288 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 4 | `1Mt8KTvwQkNo` | 457 | 0.1990 | 6 | 40 | 0.1500 | [0.0706, 0.2907] | yes |
| 4 | `1UeDWkdeCAMM` | 413 | 0.1691 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 4 | `1bQ1pmcjGhNK` | 346 | 0.1449 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 5 | `1AQDR6WGsouL` | 404 | 0.1726 | 6 | 40 | 0.1500 | [0.0706, 0.2907] | yes |
| 5 | `1KwjKXWqcTzn` | 359 | 0.1563 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 5 | `1LWqTJtUzobS` | 81 | 0.0357 | 2 | 40 | 0.0500 | [0.0138, 0.1650] | yes |
| 5 | `1Mk9iunnT37k` | 311 | 0.1337 | 15 | 40 | 0.3750 | [0.2422, 0.5297] | no |
| 5 | `1Mt8KTvwQkNo` | 491 | 0.2097 | 3 | 40 | 0.0750 | [0.0258, 0.1986] | no |
| 5 | `1UeDWkdeCAMM` | 337 | 0.1516 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 5 | `1bQ1pmcjGhNK` | 320 | 0.1404 | 4 | 40 | 0.1000 | [0.0396, 0.2305] | yes |
| 6 | `1AQDR6WGsouL` | 403 | 0.1658 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |
| 6 | `1KwjKXWqcTzn` | 382 | 0.1540 | 4 | 21 | 0.1905 | [0.0767, 0.4000] | yes |
| 6 | `1LWqTJtUzobS` | 108 | 0.0410 | 0 | 21 | 0.0000 | [0.0000, 0.1546] | yes |
| 6 | `1Mk9iunnT37k` | 314 | 0.1288 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |
| 6 | `1Mt8KTvwQkNo` | 533 | 0.2136 | 3 | 21 | 0.1429 | [0.0498, 0.3464] | yes |
| 6 | `1UeDWkdeCAMM` | 368 | 0.1473 | 6 | 21 | 0.2857 | [0.1381, 0.4996] | yes |
| 6 | `1bQ1pmcjGhNK` | 385 | 0.1495 | 4 | 21 | 0.1905 | [0.0767, 0.4000] | yes |

## Pooled over every measured epoch

| validator | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---:|---:|---:|---:|---|---|
| `1AQDR6WGsouL` | 0.1762 | 35 | 181 | 0.1934 | [0.1425, 0.2570] | yes |
| `1KwjKXWqcTzn` | 0.1464 | 23 | 181 | 0.1271 | [0.0862, 0.1835] | yes |
| `1LWqTJtUzobS` | 0.0402 | 9 | 181 | 0.0497 | [0.0264, 0.0918] | yes |
| `1Mk9iunnT37k` | 0.1283 | 35 | 181 | 0.1934 | [0.1425, 0.2570] | no |
| `1Mt8KTvwQkNo` | 0.2052 | 26 | 181 | 0.1436 | [0.1000, 0.2022] | no |
| `1UeDWkdeCAMM` | 0.1551 | 30 | 181 | 0.1657 | [0.1186, 0.2267] | yes |
| `1bQ1pmcjGhNK` | 0.1485 | 22 | 181 | 0.1215 | [0.0817, 0.1772] | yes |

## Joint test per epoch (chi-square / exact / Monte Carlo)

| epoch | blocks | validators | method | statistic | p | reject at 0.05 | TV | round-by-round p |
|---|---:|---:|---|---:|---:|---|---:|---:|
| 2 | 39 | 7 | monte_carlo_multinomial | 19.683 | 0.0042 | YES | 0.2773 | 0.0043 |
| 3 | 40 | 7 | monte_carlo_multinomial | 7.493 | 0.2658 | no | 0.1720 | 0.2723 |
| 4 | 40 | 7 | monte_carlo_multinomial | 3.479 | 0.7534 | no | 0.1295 | 0.7537 |
| 5 | 40 | 7 | monte_carlo_multinomial | 22.133 | 0.0022 | YES | 0.2556 | 0.0020 |
| 6 | 21 | 7 | monte_carlo_multinomial | 5.314 | 0.4977 | no | 0.2159 | 0.5008 |
| all | 180 | 7 | chi2_asymptotic | 11.498 | 0.0742 | no | 0.1057 | 0.0336 |

## How to read this

- **The interval, not the point.** A `p_hat` far from `p_theoretical` means nothing if the interval is wide; with a handful of blocks per epoch it usually is. The mean interval width here is **0.2003**, which is the resolution of this run.
- **Multiple comparisons.** 6 of 35 intervals excluded the entitled share; about 1.8 are expected to by chance alone at alpha = 0.05. Only a count well above the expectation is a finding.
- **The joint test is the real one.** The per-validator intervals say *which* validator is out of line; the chi-square says whether the epoch as a whole is distinguishable from weighted sortition.
- **Round-by-round when the shares moved.** Where an epoch's shares changed mid-epoch, the pooled multinomial tests a null that was never in force, and the round-by-round Monte-Carlo p-value in the last column is the one to read.

The corresponding figure is `plots/weight_vs_election.png`, produced by `plotting/generate_plots.py`.
