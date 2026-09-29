# Weight versus probability of election

> The headline comparison of this experiment. For each epoch and each validator: the share of blocks the **final weight** entitled it to, against the share it actually won, with a 95% Wilson interval around the observed share and a joint goodness-of-fit test over all validators of the epoch.

## What is being compared

`p_theoretical` is built from `effective_weight_after_malus_and_dumping` — the quantity the election **actually consumes**, after the malus factor and after the dumping function — and is block-weighted across the rounds of the epoch, so an epoch whose weights moved is summarised by what was in force rather than by a snapshot of either end.

`p_hat = O_i / B` is the observed share. The Wilson interval is the 95% score interval around it; it stays inside [0,1] and has sensible width at `O_i = 0`, where the textbook interval collapses to zero.

**Epochs [1, 2, 3] are excluded**: their rounds lie at or below `setup-first-blocks = 108`, where the chain is governed by native MultiChain round robin rather than by wPoA. Testing them would measure the wrong mechanism.

## Per-epoch, per-validator

| epoch | validator | w_final | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---|---:|---:|---:|---:|---:|---|---|
| 4 | `12i57cQyYos9` | 14050 | 0.2171 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 4 | `18gvN5byxrLW` | 12210 | 0.1991 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 4 | `1CEGmDw1EGvJ` | 4939 | 0.0945 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 4 | `1KjFUWP1UwVN` | 13980 | 0.2102 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 4 | `1TdNbRafPmgN` | 17088 | 0.2790 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 5 | `12i57cQyYos9` | 10088 | 0.1840 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 5 | `18gvN5byxrLW` | 14723 | 0.2312 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 5 | `1CEGmDw1EGvJ` | 4475 | 0.0758 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 5 | `1KjFUWP1UwVN` | 24654 | 0.3581 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 5 | `1TdNbRafPmgN` | 6193 | 0.1510 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 6 | `12i57cQyYos9` | 10094 | 0.1466 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | no |
| 6 | `18gvN5byxrLW` | 39655 | 0.4600 | 12 | 25 | 0.4800 | [0.3003, 0.6650] | yes |
| 6 | `1CEGmDw1EGvJ` | 3782 | 0.0582 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 6 | `1KjFUWP1UwVN` | 13006 | 0.2432 | 8 | 25 | 0.3200 | [0.1721, 0.5159] | yes |
| 6 | `1TdNbRafPmgN` | 6408 | 0.0921 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 7 | `12i57cQyYos9` | 15349 | 0.1809 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 7 | `18gvN5byxrLW` | 11398 | 0.2578 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 7 | `1CEGmDw1EGvJ` | 8475 | 0.0930 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 7 | `1KjFUWP1UwVN` | 25271 | 0.2839 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 7 | `1TdNbRafPmgN` | 17268 | 0.1845 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 8 | `12i57cQyYos9` | 24933 | 0.3011 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 8 | `18gvN5byxrLW` | 27944 | 0.3166 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 8 | `1CEGmDw1EGvJ` | 3600 | 0.0660 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 8 | `1KjFUWP1UwVN` | 7753 | 0.1674 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 8 | `1TdNbRafPmgN` | 8797 | 0.1489 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 9 | `12i57cQyYos9` | 16887 | 0.2746 | 8 | 25 | 0.3200 | [0.1721, 0.5159] | yes |
| 9 | `18gvN5byxrLW` | 14552 | 0.2614 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 9 | `1CEGmDw1EGvJ` | 10495 | 0.1251 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 9 | `1KjFUWP1UwVN` | 18888 | 0.2299 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | no |
| 9 | `1TdNbRafPmgN` | 7101 | 0.1090 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 10 | `12i57cQyYos9` | 16925 | 0.2691 | 8 | 25 | 0.3200 | [0.1721, 0.5159] | yes |
| 10 | `18gvN5byxrLW` | 19996 | 0.2957 | 8 | 25 | 0.3200 | [0.1721, 0.5159] | yes |
| 10 | `1CEGmDw1EGvJ` | 3837 | 0.0885 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 10 | `1KjFUWP1UwVN` | 14858 | 0.2530 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 10 | `1TdNbRafPmgN` | 5462 | 0.0937 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 11 | `12i57cQyYos9` | 21508 | 0.2772 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 11 | `18gvN5byxrLW` | 17959 | 0.2584 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 11 | `1CEGmDw1EGvJ` | 12286 | 0.1316 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 11 | `1KjFUWP1UwVN` | 17588 | 0.2314 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 11 | `1TdNbRafPmgN` | 8232 | 0.1014 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 12 | `12i57cQyYos9` | 44914 | 0.4060 | 9 | 25 | 0.3600 | [0.2025, 0.5548] | yes |
| 12 | `18gvN5byxrLW` | 20949 | 0.2180 | 9 | 25 | 0.3600 | [0.2025, 0.5548] | yes |
| 12 | `1CEGmDw1EGvJ` | 2988 | 0.0662 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 12 | `1KjFUWP1UwVN` | 11631 | 0.1485 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 12 | `1TdNbRafPmgN` | 17992 | 0.1613 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 13 | `12i57cQyYos9` | 7569 | 0.2143 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 13 | `18gvN5byxrLW` | 28570 | 0.3863 | 14 | 25 | 0.5600 | [0.3707, 0.7333] | yes |
| 13 | `1CEGmDw1EGvJ` | 5335 | 0.0695 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 13 | `1KjFUWP1UwVN` | 10401 | 0.1520 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 13 | `1TdNbRafPmgN` | 11082 | 0.1779 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 14 | `12i57cQyYos9` | 12050 | 0.1886 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 14 | `18gvN5byxrLW` | 9899 | 0.2543 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 14 | `1CEGmDw1EGvJ` | 3588 | 0.0698 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 14 | `1KjFUWP1UwVN` | 17901 | 0.2764 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 14 | `1TdNbRafPmgN` | 12573 | 0.2109 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 15 | `12i57cQyYos9` | 16163 | 0.2121 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 15 | `18gvN5byxrLW` | 10097 | 0.1443 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 15 | `1CEGmDw1EGvJ` | 9721 | 0.1093 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 15 | `1KjFUWP1UwVN` | 18564 | 0.2639 | 9 | 25 | 0.3600 | [0.2025, 0.5548] | yes |
| 15 | `1TdNbRafPmgN` | 22090 | 0.2704 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 16 | `12i57cQyYos9` | 15247 | 0.1729 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 16 | `18gvN5byxrLW` | 28739 | 0.2515 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | no |
| 16 | `1CEGmDw1EGvJ` | 3355 | 0.0606 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | yes |
| 16 | `1KjFUWP1UwVN` | 25202 | 0.2560 | 14 | 25 | 0.5600 | [0.3707, 0.7333] | no |
| 16 | `1TdNbRafPmgN` | 23896 | 0.2591 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 17 | `12i57cQyYos9` | 30556 | 0.3056 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 17 | `18gvN5byxrLW` | 21937 | 0.2711 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 17 | `1CEGmDw1EGvJ` | 11077 | 0.1045 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 17 | `1KjFUWP1UwVN` | 9894 | 0.1578 | 8 | 25 | 0.3200 | [0.1721, 0.5159] | no |
| 17 | `1TdNbRafPmgN` | 10715 | 0.1610 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 18 | `12i57cQyYos9` | 25507 | 0.3382 | 12 | 25 | 0.4800 | [0.3003, 0.6650] | yes |
| 18 | `18gvN5byxrLW` | 15645 | 0.2181 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 18 | `1CEGmDw1EGvJ` | 3307 | 0.0675 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 18 | `1KjFUWP1UwVN` | 24759 | 0.2625 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 18 | `1TdNbRafPmgN` | 8421 | 0.1137 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 19 | `12i57cQyYos9` | 15359 | 0.2322 | 11 | 25 | 0.4400 | [0.2667, 0.6293] | no |
| 19 | `18gvN5byxrLW` | 35402 | 0.3796 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 19 | `1CEGmDw1EGvJ` | 3570 | 0.0445 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 19 | `1KjFUWP1UwVN` | 13192 | 0.2097 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 19 | `1TdNbRafPmgN` | 11337 | 0.1339 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 20 | `12i57cQyYos9` | 40390 | 0.3340 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 20 | `18gvN5byxrLW` | 10025 | 0.1951 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 20 | `1CEGmDw1EGvJ` | 7669 | 0.0657 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 20 | `1KjFUWP1UwVN` | 33768 | 0.2804 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 20 | `1TdNbRafPmgN` | 12223 | 0.1248 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 21 | `12i57cQyYos9` | 10053 | 0.2184 | 7 | 21 | 0.3333 | [0.1719, 0.5463] | yes |
| 21 | `18gvN5byxrLW` | 9727 | 0.1225 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |
| 21 | `1CEGmDw1EGvJ` | 10416 | 0.1218 | 6 | 21 | 0.2857 | [0.1381, 0.4996] | no |
| 21 | `1KjFUWP1UwVN` | 30144 | 0.3878 | 5 | 21 | 0.2381 | [0.1063, 0.4509] | yes |
| 21 | `1TdNbRafPmgN` | 11898 | 0.1497 | 1 | 21 | 0.0476 | [0.0085, 0.2267] | yes |

## Pooled over every measured epoch

| validator | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---:|---:|---:|---:|---|---|
| `12i57cQyYos9` | 0.2488 | 112 | 446 | 0.2511 | [0.2131, 0.2934] | yes |
| `18gvN5byxrLW` | 0.2635 | 123 | 446 | 0.2758 | [0.2364, 0.3190] | yes |
| `1CEGmDw1EGvJ` | 0.0837 | 43 | 446 | 0.0964 | [0.0724, 0.1274] | yes |
| `1KjFUWP1UwVN` | 0.2416 | 108 | 446 | 0.2422 | [0.2047, 0.2840] | yes |
| `1TdNbRafPmgN` | 0.1625 | 57 | 446 | 0.1278 | [0.1000, 0.1620] | no |

## Joint test per epoch (chi-square / exact / Monte Carlo)

| epoch | blocks | validators | method | statistic | p | reject at 0.05 | TV | round-by-round p |
|---|---:|---:|---|---:|---:|---|---:|---:|
| 4 | 22 | 5 | monte_carlo_multinomial | 4.973 | 0.2834 | no | 0.1880 | 0.3138 |
| 5 | 25 | 5 | monte_carlo_multinomial | 0.374 | 0.9881 | no | 0.0550 | 0.9867 |
| 6 | 25 | 5 | monte_carlo_multinomial | 5.688 | 0.2050 | no | 0.1648 | 0.2032 |
| 7 | 25 | 5 | monte_carlo_multinomial | 5.146 | 0.2660 | no | 0.2093 | 0.2524 |
| 8 | 25 | 5 | monte_carlo_multinomial | 4.209 | 0.3720 | no | 0.1666 | 0.3531 |
| 9 | 25 | 5 | monte_carlo_multinomial | 6.950 | 0.1296 | no | 0.2350 | 0.1265 |
| 10 | 25 | 5 | monte_carlo_multinomial | 2.984 | 0.5587 | no | 0.1415 | 0.5585 |
| 11 | 25 | 5 | monte_carlo_multinomial | 3.106 | 0.5418 | no | 0.1297 | 0.5455 |
| 12 | 25 | 5 | monte_carlo_multinomial | 3.748 | 0.4357 | no | 0.1535 | 0.4311 |
| 13 | 25 | 5 | monte_carlo_multinomial | 4.972 | 0.2786 | no | 0.1817 | 0.2647 |
| 14 | 25 | 5 | monte_carlo_multinomial | 3.509 | 0.4746 | no | 0.1158 | 0.4660 |
| 15 | 25 | 5 | monte_carlo_multinomial | 2.884 | 0.5758 | no | 0.1625 | 0.5849 |
| 16 | 25 | 5 | monte_carlo_multinomial | 16.585 | 0.0035 | YES | 0.3711 | 0.0029 |
| 17 | 25 | 5 | monte_carlo_multinomial | 5.691 | 0.2138 | no | 0.1711 | 0.2046 |
| 18 | 25 | 5 | monte_carlo_multinomial | 2.534 | 0.6391 | no | 0.1481 | 0.6384 |
| 19 | 25 | 5 | monte_carlo_multinomial | 10.894 | 0.0274 | YES | 0.3139 | 0.0260 |
| 20 | 25 | 5 | monte_carlo_multinomial | 2.848 | 0.5830 | no | 0.1645 | 0.5610 |
| 21 | 21 | 5 | monte_carlo_multinomial | 8.709 | 0.0649 | no | 0.2789 | 0.0606 |
| all | 443 | 5 | chi2_asymptotic | 4.430 | 0.3510 | no | 0.0315 | 0.3905 |

## How to read this

- **The interval, not the point.** A `p_hat` far from `p_theoretical` means nothing if the interval is wide; with a handful of blocks per epoch it usually is. The mean interval width here is **0.2743**, which is the resolution of this run.
- **Multiple comparisons.** 7 of 90 intervals excluded the entitled share; about 4.5 are expected to by chance alone at alpha = 0.05. Only a count well above the expectation is a finding.
- **The joint test is the real one.** The per-validator intervals say *which* validator is out of line; the chi-square says whether the epoch as a whole is distinguishable from weighted sortition.
- **Round-by-round when the shares moved.** Where an epoch's shares changed mid-epoch, the pooled multinomial tests a null that was never in force, and the round-by-round Monte-Carlo p-value in the last column is the one to read.

The corresponding figure is `plots/weight_vs_election.png`, produced by `plotting/generate_plots.py`.
