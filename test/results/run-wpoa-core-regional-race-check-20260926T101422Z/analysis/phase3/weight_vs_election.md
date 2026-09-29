# Weight versus probability of election

> The headline comparison of this experiment. For each epoch and each validator: the share of blocks the **final weight** entitled it to, against the share it actually won, with a 95% Wilson interval around the observed share and a joint goodness-of-fit test over all validators of the epoch.

## What is being compared

`p_theoretical` is built from `effective_weight_after_malus_and_dumping` — the quantity the election **actually consumes**, after the malus factor and after the dumping function — and is block-weighted across the rounds of the epoch, so an epoch whose weights moved is summarised by what was in force rather than by a snapshot of either end.

`p_hat = O_i / B` is the observed share. The Wilson interval is the 95% score interval around it; it stays inside [0,1] and has sensible width at `O_i = 0`, where the textbook interval collapses to zero.

**Epochs [1, 2, 3] are excluded**: their rounds lie at or below `setup-first-blocks = 108`, where the chain is governed by native MultiChain round robin rather than by wPoA. Testing them would measure the wrong mechanism.

## Per-epoch, per-validator

| epoch | validator | w_final | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---|---:|---:|---:|---:|---:|---|---|
| 4 | `15BaWjzxqsg2` | 16205 | 0.2230 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 4 | `17PqEWjMBBKA` | 13054 | 0.1937 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 4 | `1EQXqsxEyzUZ` | 17155 | 0.2704 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 4 | `1TMRHdfBETRk` | 5675 | 0.0977 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 4 | `1b9Adpdc6BSi` | 15122 | 0.2153 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 5 | `15BaWjzxqsg2` | 24804 | 0.3692 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 5 | `17PqEWjMBBKA` | 13731 | 0.2214 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 5 | `1EQXqsxEyzUZ` | 6280 | 0.1478 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 5 | `1TMRHdfBETRk` | 4167 | 0.0743 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 5 | `1b9Adpdc6BSi` | 10218 | 0.1873 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 6 | `15BaWjzxqsg2` | 14165 | 0.2557 | 8 | 25 | 0.3200 | [0.1721, 0.5159] | yes |
| 6 | `17PqEWjMBBKA` | 38857 | 0.4446 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 6 | `1EQXqsxEyzUZ` | 6640 | 0.0946 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 6 | `1TMRHdfBETRk` | 3930 | 0.0581 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 6 | `1b9Adpdc6BSi` | 10094 | 0.1470 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 7 | `15BaWjzxqsg2` | 26780 | 0.2894 | 9 | 25 | 0.3600 | [0.2025, 0.5548] | yes |
| 7 | `17PqEWjMBBKA` | 12862 | 0.2608 | 8 | 25 | 0.3200 | [0.1721, 0.5159] | yes |
| 7 | `1EQXqsxEyzUZ` | 17814 | 0.1819 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 7 | `1TMRHdfBETRk` | 8453 | 0.0893 | 0 | 25 | 0.0000 | [0.0000, 0.1332] | yes |
| 7 | `1b9Adpdc6BSi` | 15940 | 0.1786 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 8 | `15BaWjzxqsg2` | 8227 | 0.1715 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 8 | `17PqEWjMBBKA` | 28292 | 0.3186 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 8 | `1EQXqsxEyzUZ` | 8826 | 0.1466 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 8 | `1TMRHdfBETRk` | 3815 | 0.0659 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 8 | `1b9Adpdc6BSi` | 25022 | 0.2974 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 9 | `15BaWjzxqsg2` | 18984 | 0.2305 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 9 | `17PqEWjMBBKA` | 14841 | 0.2627 | 9 | 25 | 0.3600 | [0.2025, 0.5548] | yes |
| 9 | `1EQXqsxEyzUZ` | 7101 | 0.1079 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 9 | `1TMRHdfBETRk` | 10806 | 0.1279 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 9 | `1b9Adpdc6BSi` | 16806 | 0.2710 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 10 | `15BaWjzxqsg2` | 14765 | 0.2643 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 10 | `17PqEWjMBBKA` | 18059 | 0.2890 | 9 | 25 | 0.3600 | [0.2025, 0.5548] | yes |
| 10 | `1EQXqsxEyzUZ` | 4661 | 0.0880 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 10 | `1TMRHdfBETRk` | 3385 | 0.0870 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 10 | `1b9Adpdc6BSi` | 16064 | 0.2718 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 11 | `15BaWjzxqsg2` | 19562 | 0.2486 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 11 | `17PqEWjMBBKA` | 18393 | 0.2543 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 11 | `1EQXqsxEyzUZ` | 8151 | 0.0962 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 11 | `1TMRHdfBETRk` | 12739 | 0.1312 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 11 | `1b9Adpdc6BSi` | 21193 | 0.2696 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 12 | `15BaWjzxqsg2` | 12168 | 0.1565 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 12 | `17PqEWjMBBKA` | 20751 | 0.2145 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 12 | `1EQXqsxEyzUZ` | 20015 | 0.1733 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 12 | `1TMRHdfBETRk` | 2918 | 0.0657 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 12 | `1b9Adpdc6BSi` | 43654 | 0.3900 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 13 | `15BaWjzxqsg2` | 11157 | 0.1546 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 13 | `17PqEWjMBBKA` | 30616 | 0.3886 | 12 | 25 | 0.4800 | [0.3003, 0.6650] | yes |
| 13 | `1EQXqsxEyzUZ` | 11260 | 0.1778 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 13 | `1TMRHdfBETRk` | 5928 | 0.0722 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 13 | `1b9Adpdc6BSi` | 7786 | 0.2068 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 14 | `15BaWjzxqsg2` | 20468 | 0.2861 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 14 | `17PqEWjMBBKA` | 10568 | 0.2520 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 14 | `1EQXqsxEyzUZ` | 13858 | 0.2093 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 14 | `1TMRHdfBETRk` | 3881 | 0.0702 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 14 | `1b9Adpdc6BSi` | 12805 | 0.1824 | 9 | 25 | 0.3600 | [0.2025, 0.5548] | no |
| 15 | `15BaWjzxqsg2` | 18164 | 0.2680 | 9 | 25 | 0.3600 | [0.2025, 0.5548] | yes |
| 15 | `17PqEWjMBBKA` | 9613 | 0.1406 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 15 | `1EQXqsxEyzUZ` | 21188 | 0.2671 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 15 | `1TMRHdfBETRk` | 9322 | 0.1074 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 15 | `1b9Adpdc6BSi` | 16480 | 0.2169 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 16 | `15BaWjzxqsg2` | 25942 | 0.2494 | 11 | 25 | 0.4400 | [0.2667, 0.6293] | no |
| 16 | `17PqEWjMBBKA` | 27869 | 0.2309 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 16 | `1EQXqsxEyzUZ` | 23495 | 0.2436 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 16 | `1TMRHdfBETRk` | 3367 | 0.0585 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 16 | `1b9Adpdc6BSi` | 22290 | 0.2176 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 17 | `15BaWjzxqsg2` | 10400 | 0.1675 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 17 | `17PqEWjMBBKA` | 22059 | 0.2815 | 11 | 25 | 0.4400 | [0.2667, 0.6293] | yes |
| 17 | `1EQXqsxEyzUZ` | 10615 | 0.1629 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 17 | `1TMRHdfBETRk` | 10818 | 0.1100 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 17 | `1b9Adpdc6BSi` | 23309 | 0.2780 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 18 | `15BaWjzxqsg2` | 26173 | 0.2742 | 5 | 25 | 0.2000 | [0.0886, 0.3913] | yes |
| 18 | `17PqEWjMBBKA` | 15802 | 0.2228 | 9 | 25 | 0.3600 | [0.2025, 0.5548] | yes |
| 18 | `1EQXqsxEyzUZ` | 8617 | 0.1164 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 18 | `1TMRHdfBETRk` | 3344 | 0.0695 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 18 | `1b9Adpdc6BSi` | 25740 | 0.3171 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 19 | `15BaWjzxqsg2` | 13289 | 0.2214 | 9 | 25 | 0.3600 | [0.2025, 0.5548] | yes |
| 19 | `17PqEWjMBBKA` | 32454 | 0.3717 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 19 | `1EQXqsxEyzUZ` | 10227 | 0.1299 | 2 | 25 | 0.0800 | [0.0222, 0.2497] | yes |
| 19 | `1TMRHdfBETRk` | 3238 | 0.0433 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 19 | `1b9Adpdc6BSi` | 14693 | 0.2336 | 6 | 25 | 0.2400 | [0.1150, 0.4343] | yes |
| 20 | `15BaWjzxqsg2` | 36138 | 0.2835 | 10 | 25 | 0.4000 | [0.2340, 0.5926] | yes |
| 20 | `17PqEWjMBBKA` | 10765 | 0.1924 | 4 | 25 | 0.1600 | [0.0640, 0.3465] | yes |
| 20 | `1EQXqsxEyzUZ` | 13776 | 0.1276 | 3 | 25 | 0.1200 | [0.0417, 0.2996] | yes |
| 20 | `1TMRHdfBETRk` | 7889 | 0.0632 | 1 | 25 | 0.0400 | [0.0071, 0.1954] | yes |
| 20 | `1b9Adpdc6BSi` | 43011 | 0.3332 | 7 | 25 | 0.2800 | [0.1428, 0.4758] | yes |
| 21 | `15BaWjzxqsg2` | 38380 | 0.4235 | 7 | 21 | 0.3333 | [0.1719, 0.5463] | yes |
| 21 | `17PqEWjMBBKA` | 10108 | 0.1151 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |
| 21 | `1EQXqsxEyzUZ` | 11805 | 0.1379 | 4 | 21 | 0.1905 | [0.0767, 0.4000] | yes |
| 21 | `1TMRHdfBETRk` | 11255 | 0.1165 | 3 | 21 | 0.1429 | [0.0498, 0.3464] | yes |
| 21 | `1b9Adpdc6BSi` | 10104 | 0.2070 | 5 | 21 | 0.2381 | [0.1063, 0.4509] | yes |

## Pooled over every measured epoch

| validator | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---:|---:|---:|---:|---|---|
| `15BaWjzxqsg2` | 0.2505 | 124 | 446 | 0.2780 | [0.2385, 0.3214] | yes |
| `17PqEWjMBBKA` | 0.2599 | 124 | 446 | 0.2780 | [0.2385, 0.3214] | yes |
| `1EQXqsxEyzUZ` | 0.1602 | 56 | 446 | 0.1256 | [0.0980, 0.1595] | no |
| `1TMRHdfBETRk` | 0.0835 | 37 | 446 | 0.0830 | [0.0608, 0.1123] | yes |
| `1b9Adpdc6BSi` | 0.2459 | 104 | 446 | 0.2332 | [0.1963, 0.2746] | yes |

## Joint test per epoch (chi-square / exact / Monte Carlo)

| epoch | blocks | validators | method | statistic | p | reject at 0.05 | TV | round-by-round p |
|---|---:|---:|---|---:|---:|---|---:|---:|
| 4 | 24 | 5 | monte_carlo_multinomial | 2.361 | 0.6688 | no | 0.1476 | 0.6831 |
| 5 | 25 | 5 | monte_carlo_multinomial | 0.914 | 0.9365 | no | 0.0678 | 0.9335 |
| 6 | 25 | 5 | monte_carlo_multinomial | 1.655 | 0.8125 | no | 0.1116 | 0.8075 |
| 7 | 25 | 5 | monte_carlo_multinomial | 4.823 | 0.2981 | no | 0.1879 | 0.2829 |
| 8 | 25 | 5 | monte_carlo_multinomial | 1.442 | 0.8448 | no | 0.1089 | 0.8401 |
| 9 | 25 | 5 | monte_carlo_multinomial | 1.573 | 0.8195 | no | 0.1094 | 0.8139 |
| 10 | 25 | 5 | monte_carlo_multinomial | 1.252 | 0.8665 | no | 0.1040 | 0.8659 |
| 11 | 25 | 5 | monte_carlo_multinomial | 1.225 | 0.8819 | no | 0.0859 | 0.8780 |
| 12 | 25 | 5 | monte_carlo_multinomial | 2.480 | 0.6491 | no | 0.1078 | 0.6434 |
| 13 | 25 | 5 | monte_carlo_multinomial | 1.913 | 0.7631 | no | 0.1046 | 0.7514 |
| 14 | 25 | 5 | monte_carlo_multinomial | 5.577 | 0.2223 | no | 0.1776 | 0.2112 |
| 15 | 25 | 5 | monte_carlo_multinomial | 3.292 | 0.5032 | no | 0.1551 | 0.5045 |
| 16 | 25 | 5 | monte_carlo_multinomial | 5.891 | 0.1971 | no | 0.2121 | 0.1933 |
| 17 | 25 | 5 | monte_carlo_multinomial | 7.271 | 0.1133 | no | 0.2484 | 0.1165 |
| 18 | 25 | 5 | monte_carlo_multinomial | 3.047 | 0.5479 | no | 0.1477 | 0.5433 |
| 19 | 25 | 5 | monte_carlo_multinomial | 3.223 | 0.5159 | no | 0.1449 | 0.5132 |
| 20 | 25 | 5 | monte_carlo_multinomial | 1.769 | 0.7939 | no | 0.1165 | 0.7844 |
| 21 | 21 | 5 | monte_carlo_multinomial | 1.121 | 0.9085 | no | 0.1101 | 0.9162 |
| all | 445 | 5 | chi2_asymptotic | 5.539 | 0.2363 | no | 0.0468 | 0.3265 |

## How to read this

- **The interval, not the point.** A `p_hat` far from `p_theoretical` means nothing if the interval is wide; with a handful of blocks per epoch it usually is. The mean interval width here is **0.2768**, which is the resolution of this run.
- **Multiple comparisons.** 2 of 90 intervals excluded the entitled share; about 4.5 are expected to by chance alone at alpha = 0.05. Only a count well above the expectation is a finding.
- **The joint test is the real one.** The per-validator intervals say *which* validator is out of line; the chi-square says whether the epoch as a whole is distinguishable from weighted sortition.
- **Round-by-round when the shares moved.** Where an epoch's shares changed mid-epoch, the pooled multinomial tests a null that was never in force, and the round-by-round Monte-Carlo p-value in the last column is the one to read.

The corresponding figure is `plots/weight_vs_election.png`, produced by `plotting/generate_plots.py`.
