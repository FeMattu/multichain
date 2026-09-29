# Weight versus probability of election

> The headline comparison of this experiment. For each epoch and each validator: the share of blocks the **final weight** entitled it to, against the share it actually won, with a 95% Wilson interval around the observed share and a joint goodness-of-fit test over all validators of the epoch.

## What is being compared

`p_theoretical` is built from `effective_weight_after_malus_and_dumping` — the quantity the election **actually consumes**, after the malus factor and after the dumping function — and is block-weighted across the rounds of the epoch, so an epoch whose weights moved is summarised by what was in force rather than by a snapshot of either end.

`p_hat = O_i / B` is the observed share. The Wilson interval is the 95% score interval around it; it stays inside [0,1] and has sensible width at `O_i = 0`, where the textbook interval collapses to zero.

**Epochs [1, 2, 3] are excluded**: their rounds lie at or below `setup-first-blocks = 108`, where the chain is governed by native MultiChain round robin rather than by wPoA. Testing them would measure the wrong mechanism.

## Per-epoch, per-validator

| epoch | validator | w_final | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---|---:|---:|---:|---:|---:|---|---|
| 4 | `14pQFm7J9sRJ` | 3063 | 0.1885 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 4 | `18BKa4qVXbpY` | 4356 | 0.2704 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 4 | `1A3RbHsec73y` | 4735 | 0.2605 | 8 | 25 | 0.3200 | [0.1721, 0.5159] | yes |
| 4 | `1JgauUAZoSen` | 1497 | 0.1100 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 4 | `1QpG25RiHwvG` | 2614 | 0.1705 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 5 | `14pQFm7J9sRJ` | 5601 | 0.2668 | 11 | 25 | 0.4400 | [0.2667, 0.6293] | yes |
| 5 | `18BKa4qVXbpY` | 1572 | 0.1351 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 5 | `1A3RbHsec73y` | 8585 | 0.4097 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 5 | `1JgauUAZoSen` | 1051 | 0.0659 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | yes |
| 5 | `1QpG25RiHwvG` | 2027 | 0.1225 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 6 | `14pQFm7J9sRJ` | 8763 | 0.4351 | 8 | 25 | 0.3200 | [0.1721, 0.5159] | yes |
| 6 | `18BKa4qVXbpY` | 2021 | 0.1045 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | yes |
| 6 | `1A3RbHsec73y` | 3611 | 0.2726 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 6 | `1JgauUAZoSen` | 1039 | 0.0573 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | yes |
| 6 | `1QpG25RiHwvG` | 2501 | 0.1305 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | no |
| 7 | `14pQFm7J9sRJ` | 6213 | 0.2778 | 8 | 25 | 0.3200 | [0.1721, 0.5159] | yes |
| 7 | `18BKa4qVXbpY` | 3142 | 0.1063 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | yes |
| 7 | `1A3RbHsec73y` | 16105 | 0.4198 | 11 | 25 | 0.4400 | [0.2667, 0.6293] | yes |
| 7 | `1JgauUAZoSen` | 2042 | 0.0648 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | yes |
| 7 | `1QpG25RiHwvG` | 3874 | 0.1312 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 8 | `14pQFm7J9sRJ` | 2294 | 0.1485 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 8 | `18BKa4qVXbpY` | 1893 | 0.1469 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 8 | `1A3RbHsec73y` | 1542 | 0.1649 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 8 | `1JgauUAZoSen` | 1249 | 0.0964 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 8 | `1QpG25RiHwvG` | 7636 | 0.4432 | 13 | 25 | 0.5200 | [0.3350, 0.6997] | yes |
| 9 | `14pQFm7J9sRJ` | 6706 | 0.4341 | 11 | 25 | 0.4400 | [0.2667, 0.6293] | yes |
| 9 | `18BKa4qVXbpY` | 1656 | 0.1255 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 9 | `1A3RbHsec73y` | 0 | 0.0000 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | no |
| 9 | `1JgauUAZoSen` | 2637 | 0.1677 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 9 | `1QpG25RiHwvG` | 2428 | 0.2726 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 10 | `14pQFm7J9sRJ` | 3244 | 0.2410 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 10 | `18BKa4qVXbpY` | 1271 | 0.1307 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 10 | `1A3RbHsec73y` | 0 | 0.0000 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | no |
| 10 | `1JgauUAZoSen` | 1023 | 0.1487 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 10 | `1QpG25RiHwvG` | 6711 | 0.4796 | 14 | 25 | 0.5600 | [0.3707, 0.7333] | yes |
| 11 | `14pQFm7J9sRJ` | 0 | 0.0000 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | no |
| 11 | `18BKa4qVXbpY` | 2127 | 0.1407 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 11 | `1A3RbHsec73y` | 2281 | 0.1609 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 11 | `1JgauUAZoSen` | 3547 | 0.2060 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 11 | `1QpG25RiHwvG` | 6282 | 0.4924 | 13 | 25 | 0.5200 | [0.3350, 0.6997] | yes |
| 12 | `14pQFm7J9sRJ` | 0 | 0.0000 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | no |
| 12 | `18BKa4qVXbpY` | 4442 | 0.2297 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 12 | `1A3RbHsec73y` | 2581 | 0.1802 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 12 | `1JgauUAZoSen` | 824 | 0.0983 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 12 | `1QpG25RiHwvG` | 8806 | 0.4918 | 14 | 25 | 0.5600 | [0.3707, 0.7333] | yes |
| 13 | `14pQFm7J9sRJ` | 0 | 0.0000 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | no |
| 13 | `18BKa4qVXbpY` | 2778 | 0.2886 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 13 | `1A3RbHsec73y` | 2533 | 0.2478 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 13 | `1JgauUAZoSen` | 1748 | 0.1495 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 13 | `1QpG25RiHwvG` | 2193 | 0.3141 | 9 | 25 | 0.3600 | [0.2025, 0.5548] | yes |
| 14 | `14pQFm7J9sRJ` | 0 | 0.0000 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | no |
| 14 | `18BKa4qVXbpY` | 5687 | 0.2774 | 9 | 25 | 0.3600 | [0.2025, 0.5548] | yes |
| 14 | `1A3RbHsec73y` | 11792 | 0.4709 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 14 | `1JgauUAZoSen` | 853 | 0.0810 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 14 | `1QpG25RiHwvG` | 3082 | 0.1707 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 15 | `14pQFm7J9sRJ` | 0 | 0.0000 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | no |
| 15 | `18BKa4qVXbpY` | 5022 | 0.3780 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 15 | `1A3RbHsec73y` | 1519 | 0.1573 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 15 | `1JgauUAZoSen` | 2772 | 0.1609 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | no |
| 15 | `1QpG25RiHwvG` | 4639 | 0.3038 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 16 | `14pQFm7J9sRJ` | 2899 | 0.1168 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 16 | `18BKa4qVXbpY` | 5392 | 0.2713 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 16 | `1A3RbHsec73y` | 4429 | 0.2093 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 16 | `1JgauUAZoSen` | 1153 | 0.0865 | 9 | 25 | 0.3600 | [0.2025, 0.5548] | no |
| 16 | `1QpG25RiHwvG` | 6870 | 0.3162 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 17 | `14pQFm7J9sRJ` | 5338 | 0.3066 | 11 | 25 | 0.4400 | [0.2667, 0.6293] | yes |
| 17 | `18BKa4qVXbpY` | 2916 | 0.1933 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 17 | `1A3RbHsec73y` | 2539 | 0.1789 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 17 | `1JgauUAZoSen` | 2875 | 0.1434 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 17 | `1QpG25RiHwvG` | 2207 | 0.1778 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 18 | `14pQFm7J9sRJ` | 5271 | 0.2964 | 12 | 25 | 0.4800 | [0.3003, 0.6650] | no |
| 18 | `18BKa4qVXbpY` | 1719 | 0.1086 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 18 | `1A3RbHsec73y` | 5177 | 0.2314 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 18 | `1JgauUAZoSen` | 888 | 0.0781 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 18 | `1QpG25RiHwvG` | 6948 | 0.2855 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 19 | `14pQFm7J9sRJ` | 5114 | 0.3145 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 19 | `18BKa4qVXbpY` | 2635 | 0.1450 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 19 | `1A3RbHsec73y` | 3151 | 0.2188 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 19 | `1JgauUAZoSen` | 893 | 0.0533 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 19 | `1QpG25RiHwvG` | 3779 | 0.2684 | 9 | 25 | 0.3600 | [0.2025, 0.5548] | yes |
| 20 | `14pQFm7J9sRJ` | 2758 | 0.1701 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 20 | `18BKa4qVXbpY` | 3115 | 0.1321 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 20 | `1A3RbHsec73y` | 10948 | 0.3579 | 11 | 25 | 0.4400 | [0.2667, 0.6293] | yes |
| 20 | `1JgauUAZoSen` | 2043 | 0.0719 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 20 | `1QpG25RiHwvG` | 7325 | 0.2680 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 21 | `14pQFm7J9sRJ` | 2582 | 0.1120 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |
| 21 | `18BKa4qVXbpY` | 3763 | 0.1513 | 4 | 21 | 0.1905 | [0.0767, 0.4000] | yes |
| 21 | `1A3RbHsec73y` | 10667 | 0.4558 | 12 | 21 | 0.5714 | [0.3655, 0.7553] | yes |
| 21 | `1JgauUAZoSen` | 3280 | 0.1237 | 1 | 21 | 0.0476 | [0.0085, 0.2267] | yes |
| 21 | `1QpG25RiHwvG` | 2279 | 0.1572 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |

## Pooled over every measured epoch

| validator | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---:|---:|---:|---:|---|---|
| `14pQFm7J9sRJ` | 0.1844 | 79 | 446 | 0.1771 | [0.1445, 0.2153] | yes |
| `18BKa4qVXbpY` | 0.1856 | 67 | 446 | 0.1502 | [0.1201, 0.1864] | yes |
| `1A3RbHsec73y` | 0.2424 | 117 | 446 | 0.2623 | [0.2237, 0.3051] | yes |
| `1JgauUAZoSen` | 0.1090 | 48 | 446 | 0.1076 | [0.0821, 0.1398] | yes |
| `1QpG25RiHwvG` | 0.2786 | 130 | 446 | 0.2915 | [0.2512, 0.3353] | yes |

## Joint test per epoch (chi-square / exact / Monte Carlo)

| epoch | blocks | validators | method | statistic | p | reject at 0.05 | TV | round-by-round p |
|---|---:|---:|---|---:|---:|---|---:|---:|
| 4 | 20 | 5 | monte_carlo_multinomial | 3.229 | 0.5246 | no | 0.2118 | 0.4692 |
| 5 | 25 | 5 | monte_carlo_multinomial | 5.394 | 0.2347 | no | 0.1732 | 0.2250 |
| 6 | 25 | 5 | monte_carlo_multinomial | 10.574 | 0.0317 | YES | 0.2769 | 0.0303 |
| 7 | 25 | 5 | monte_carlo_multinomial | 6.716 | 0.1360 | no | 0.1711 | 0.1306 |
| 8 | 25 | 5 | monte_carlo_multinomial | 5.145 | 0.2594 | no | 0.1918 | 0.2525 |
| 9 | 25 | 5 | monte_carlo_multinomial | 1.270 | 0.7526 | no | 0.0782 | 0.7441 |
| 10 | 25 | 5 | monte_carlo_multinomial | 3.993 | 0.2541 | no | 0.1717 | 0.2386 |
| 11 | 25 | 5 | monte_carlo_multinomial | 0.119 | 0.9908 | no | 0.0276 | 0.9913 |
| 12 | 25 | 5 | monte_carlo_multinomial | 0.940 | 0.8278 | no | 0.0898 | 0.8170 |
| 13 | 25 | 5 | monte_carlo_multinomial | 5.186 | 0.1512 | no | 0.1980 | 0.1459 |
| 14 | 25 | 5 | monte_carlo_multinomial | 0.898 | 0.8355 | no | 0.0826 | 0.8286 |
| 15 | 25 | 5 | monte_carlo_multinomial | 5.105 | 0.1626 | no | 0.1609 | 0.1581 |
| 16 | 25 | 5 | monte_carlo_multinomial | 25.363 | 0.0002 | YES | 0.2823 | 0.0003 |
| 17 | 25 | 5 | monte_carlo_multinomial | 2.948 | 0.5679 | no | 0.1401 | 0.5637 |
| 18 | 25 | 5 | monte_carlo_multinomial | 5.682 | 0.2102 | no | 0.2255 | 0.2035 |
| 19 | 25 | 5 | monte_carlo_multinomial | 2.469 | 0.6536 | no | 0.1466 | 0.6578 |
| 20 | 25 | 5 | monte_carlo_multinomial | 2.995 | 0.5614 | no | 0.1422 | 0.5517 |
| 21 | 21 | 5 | monte_carlo_multinomial | 2.379 | 0.6696 | no | 0.1548 | 0.6548 |
| all | 441 | 5 | chi2_asymptotic | 4.141 | 0.3872 | no | 0.0388 | 0.2085 |

## How to read this

- **The interval, not the point.** A `p_hat` far from `p_theoretical` means nothing if the interval is wide; with a handful of blocks per epoch it usually is. The mean interval width here is **0.2613**, which is the resolution of this run.
- **Multiple comparisons.** 11 of 90 intervals excluded the entitled share; about 4.5 are expected to by chance alone at alpha = 0.05. Only a count well above the expectation is a finding.
- **The joint test is the real one.** The per-validator intervals say *which* validator is out of line; the chi-square says whether the epoch as a whole is distinguishable from weighted sortition.
- **Round-by-round when the shares moved.** Where an epoch's shares changed mid-epoch, the pooled multinomial tests a null that was never in force, and the round-by-round Monte-Carlo p-value in the last column is the one to read.

The corresponding figure is `plots/weight_vs_election.png`, produced by `plotting/generate_plots.py`.
