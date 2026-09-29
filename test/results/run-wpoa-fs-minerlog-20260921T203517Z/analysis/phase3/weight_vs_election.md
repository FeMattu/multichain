# Weight versus probability of election

> The headline comparison of this experiment. For each epoch and each validator: the share of blocks the **final weight** entitled it to, against the share it actually won, with a 95% Wilson interval around the observed share and a joint goodness-of-fit test over all validators of the epoch.

## What is being compared

`p_theoretical` is built from `effective_weight_after_malus_and_dumping` — the quantity the election **actually consumes**, after the malus factor and after the dumping function — and is block-weighted across the rounds of the epoch, so an epoch whose weights moved is summarised by what was in force rather than by a snapshot of either end.

`p_hat = O_i / B` is the observed share. The Wilson interval is the 95% score interval around it; it stays inside [0,1] and has sensible width at `O_i = 0`, where the textbook interval collapses to zero.

**Epochs [1] are excluded**: their rounds lie at or below `setup-first-blocks = 112`, where the chain is governed by native MultiChain round robin rather than by wPoA. Testing them would measure the wrong mechanism.

## Per-epoch, per-validator

| epoch | validator | w_final | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---|---:|---:|---:|---:|---:|---|---|
| 2 | `18VMzqsA6NSf` | 393 | 0.1814 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 2 | `19ipA5tN3ZxC` | 339 | 0.1607 | 4 | 40 | 0.1000 | [0.0396, 0.2305] | yes |
| 2 | `1EPs6eRPeMep` | 253 | 0.1183 | 0 | 40 | 0.0000 | [0.0000, 0.0876] | no |
| 2 | `1EwF2MrGmKmE` | 77 | 0.0477 | 8 | 40 | 0.2000 | [0.1050, 0.3476] | no |
| 2 | `1GhDYvdKcXxT` | 277 | 0.1345 | 3 | 40 | 0.0750 | [0.0258, 0.1986] | yes |
| 2 | `1Kbpe1mYAqeQ` | 366 | 0.1677 | 4 | 40 | 0.1000 | [0.0396, 0.2305] | yes |
| 2 | `1asyFVj6pXJa` | 406 | 0.1897 | 10 | 40 | 0.2500 | [0.1419, 0.4019] | yes |
| 3 | `18VMzqsA6NSf` | 443 | 0.1910 | 9 | 40 | 0.2250 | [0.1232, 0.3750] | yes |
| 3 | `19ipA5tN3ZxC` | 321 | 0.1428 | 4 | 40 | 0.1000 | [0.0396, 0.2305] | yes |
| 3 | `1EPs6eRPeMep` | 313 | 0.1331 | 8 | 40 | 0.2000 | [0.1050, 0.3476] | yes |
| 3 | `1EwF2MrGmKmE` | 92 | 0.0394 | 1 | 40 | 0.0250 | [0.0044, 0.1288] | yes |
| 3 | `1GhDYvdKcXxT` | 318 | 0.1366 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 3 | `1Kbpe1mYAqeQ` | 304 | 0.1389 | 3 | 40 | 0.0750 | [0.0258, 0.1986] | yes |
| 3 | `1asyFVj6pXJa` | 516 | 0.2181 | 10 | 40 | 0.2500 | [0.1419, 0.4019] | yes |
| 4 | `18VMzqsA6NSf` | 376 | 0.1656 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 4 | `19ipA5tN3ZxC` | 413 | 0.1692 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 4 | `1EPs6eRPeMep` | 300 | 0.1290 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 4 | `1EwF2MrGmKmE` | 87 | 0.0377 | 0 | 40 | 0.0000 | [0.0000, 0.0876] | yes |
| 4 | `1GhDYvdKcXxT` | 373 | 0.1549 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 4 | `1Kbpe1mYAqeQ` | 350 | 0.1457 | 6 | 40 | 0.1500 | [0.0706, 0.2907] | yes |
| 4 | `1asyFVj6pXJa` | 452 | 0.1978 | 14 | 40 | 0.3500 | [0.2213, 0.5049] | no |
| 5 | `18VMzqsA6NSf` | 404 | 0.1728 | 2 | 40 | 0.0500 | [0.0138, 0.1650] | no |
| 5 | `19ipA5tN3ZxC` | 337 | 0.1517 | 11 | 40 | 0.2750 | [0.1611, 0.4283] | no |
| 5 | `1EPs6eRPeMep` | 307 | 0.1325 | 5 | 40 | 0.1250 | [0.0546, 0.2611] | yes |
| 5 | `1EwF2MrGmKmE` | 81 | 0.0357 | 1 | 40 | 0.0250 | [0.0044, 0.1288] | yes |
| 5 | `1GhDYvdKcXxT` | 359 | 0.1564 | 7 | 40 | 0.1750 | [0.0875, 0.3195] | yes |
| 5 | `1Kbpe1mYAqeQ` | 320 | 0.1408 | 6 | 40 | 0.1500 | [0.0706, 0.2907] | yes |
| 5 | `1asyFVj6pXJa` | 492 | 0.2101 | 8 | 40 | 0.2000 | [0.1050, 0.3476] | yes |
| 6 | `18VMzqsA6NSf` | 403 | 0.1652 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |
| 6 | `19ipA5tN3ZxC` | 368 | 0.1467 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |
| 6 | `1EPs6eRPeMep` | 318 | 0.1288 | 4 | 21 | 0.1905 | [0.0767, 0.4000] | yes |
| 6 | `1EwF2MrGmKmE` | 108 | 0.0408 | 0 | 21 | 0.0000 | [0.0000, 0.1546] | yes |
| 6 | `1GhDYvdKcXxT` | 382 | 0.1534 | 7 | 21 | 0.3333 | [0.1719, 0.5463] | no |
| 6 | `1Kbpe1mYAqeQ` | 395 | 0.1515 | 3 | 21 | 0.1429 | [0.0498, 0.3464] | yes |
| 6 | `1asyFVj6pXJa` | 536 | 0.2136 | 3 | 21 | 0.1429 | [0.0498, 0.3464] | yes |

## Pooled over every measured epoch

| validator | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---:|---:|---:|---:|---|---|
| `18VMzqsA6NSf` | 0.1762 | 27 | 181 | 0.1492 | [0.1046, 0.2083] | yes |
| `19ipA5tN3ZxC` | 0.1550 | 26 | 181 | 0.1436 | [0.1000, 0.2022] | yes |
| `1EPs6eRPeMep` | 0.1283 | 22 | 181 | 0.1215 | [0.0817, 0.1772] | yes |
| `1EwF2MrGmKmE` | 0.0402 | 10 | 181 | 0.0552 | [0.0303, 0.0987] | yes |
| `1GhDYvdKcXxT` | 0.1465 | 27 | 181 | 0.1492 | [0.1046, 0.2083] | yes |
| `1Kbpe1mYAqeQ` | 0.1486 | 22 | 181 | 0.1215 | [0.0817, 0.1772] | yes |
| `1asyFVj6pXJa` | 0.2051 | 45 | 181 | 0.2486 | [0.1913, 0.3164] | yes |

## Joint test per epoch (chi-square / exact / Monte Carlo)

| epoch | blocks | validators | method | statistic | p | reject at 0.05 | TV | round-by-round p |
|---|---:|---:|---|---:|---:|---|---:|---:|
| 2 | 38 | 7 | monte_carlo_multinomial | 29.793 | 0.0003 | YES | 0.2959 | 0.0002 |
| 3 | 40 | 7 | monte_carlo_multinomial | 3.714 | 0.7195 | no | 0.1328 | 0.7204 |
| 4 | 40 | 7 | monte_carlo_multinomial | 7.293 | 0.2819 | no | 0.1565 | 0.2912 |
| 5 | 40 | 7 | monte_carlo_multinomial | 7.777 | 0.2421 | no | 0.1511 | 0.2465 |
| 6 | 21 | 7 | monte_carlo_multinomial | 7.415 | 0.2711 | no | 0.2416 | 0.2801 |
| all | 179 | 7 | chi2_asymptotic | 4.558 | 0.6016 | no | 0.0675 | 0.4932 |

## How to read this

- **The interval, not the point.** A `p_hat` far from `p_theoretical` means nothing if the interval is wide; with a handful of blocks per epoch it usually is. The mean interval width here is **0.1993**, which is the resolution of this run.
- **Multiple comparisons.** 6 of 35 intervals excluded the entitled share; about 1.8 are expected to by chance alone at alpha = 0.05. Only a count well above the expectation is a finding.
- **The joint test is the real one.** The per-validator intervals say *which* validator is out of line; the chi-square says whether the epoch as a whole is distinguishable from weighted sortition.
- **Round-by-round when the shares moved.** Where an epoch's shares changed mid-epoch, the pooled multinomial tests a null that was never in force, and the round-by-round Monte-Carlo p-value in the last column is the one to read.

The corresponding figure is `plots/weight_vs_election.png`, produced by `plotting/generate_plots.py`.
