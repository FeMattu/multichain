# Weight versus probability of election

> The headline comparison of this experiment. For each epoch and each validator: the share of blocks the **final weight** entitled it to, against the share it actually won, with a 95% Wilson interval around the observed share and a joint goodness-of-fit test over all validators of the epoch.

## What is being compared

`p_theoretical` is built from `effective_weight_after_malus_and_dumping` — the quantity the election **actually consumes**, after the malus factor and after the dumping function — and is block-weighted across the rounds of the epoch, so an epoch whose weights moved is summarised by what was in force rather than by a snapshot of either end.

`p_hat = O_i / B` is the observed share. The Wilson interval is the 95% score interval around it; it stays inside [0,1] and has sensible width at `O_i = 0`, where the textbook interval collapses to zero.

## Per-epoch, per-validator

| epoch | validator | w_final | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | `13rurX1BBorK` | 18370 | 0.2127 | 17 | 150 | 0.1133 | [0.0720, 0.1740] | no |
| 1 | `1F2ux5rG6JbJ` | 12936 | 0.1498 | 23 | 150 | 0.1533 | [0.1044, 0.2196] | yes |
| 1 | `1GbF9tT63DtN` | 9599 | 0.1111 | 13 | 150 | 0.0867 | [0.0513, 0.1426] | yes |
| 1 | `1ZZ24eLfwd9C` | 24600 | 0.2848 | 35 | 150 | 0.2333 | [0.1728, 0.3072] | yes |
| 1 | `1ZiTV2tt2uge` | 20874 | 0.2417 | 29 | 150 | 0.1933 | [0.1381, 0.2639] | yes |
| 2 | `13rurX1BBorK` | 310723 | 0.2303 | 25 | 150 | 0.1667 | [0.1155, 0.2345] | yes |
| 2 | `1F2ux5rG6JbJ` | 206556 | 0.1535 | 25 | 150 | 0.1667 | [0.1155, 0.2345] | yes |
| 2 | `1GbF9tT63DtN` | 153816 | 0.1143 | 22 | 150 | 0.1467 | [0.0989, 0.2121] | yes |
| 2 | `1ZZ24eLfwd9C` | 326100 | 0.2446 | 37 | 150 | 0.2467 | [0.1846, 0.3214] | yes |
| 2 | `1ZiTV2tt2uge` | 346749 | 0.2572 | 41 | 150 | 0.2733 | [0.2083, 0.3496] | yes |
| 3 | `13rurX1BBorK` | 315916 | 0.2101 | 33 | 150 | 0.2200 | [0.1612, 0.2928] | yes |
| 3 | `1F2ux5rG6JbJ` | 182025 | 0.1220 | 22 | 150 | 0.1467 | [0.0989, 0.2121] | yes |
| 3 | `1GbF9tT63DtN` | 139255 | 0.0932 | 13 | 150 | 0.0867 | [0.0513, 0.1426] | yes |
| 3 | `1ZZ24eLfwd9C` | 472061 | 0.3091 | 43 | 150 | 0.2867 | [0.2203, 0.3636] | yes |
| 3 | `1ZiTV2tt2uge` | 401942 | 0.2656 | 39 | 150 | 0.2600 | [0.1964, 0.3356] | yes |
| 4 | `13rurX1BBorK` | 277104 | 0.1891 | 18 | 150 | 0.1200 | [0.0773, 0.1817] | no |
| 4 | `1F2ux5rG6JbJ` | 188380 | 0.1275 | 23 | 150 | 0.1533 | [0.1044, 0.2196] | yes |
| 4 | `1GbF9tT63DtN` | 145662 | 0.0986 | 10 | 150 | 0.0667 | [0.0366, 0.1184] | yes |
| 4 | `1ZZ24eLfwd9C` | 413180 | 0.2820 | 44 | 150 | 0.2933 | [0.2264, 0.3706] | yes |
| 4 | `1ZiTV2tt2uge` | 448624 | 0.3028 | 55 | 150 | 0.3667 | [0.2938, 0.4462] | yes |
| 5 | `13rurX1BBorK` | 289930 | 0.1995 | 31 | 150 | 0.2067 | [0.1496, 0.2784] | yes |
| 5 | `1F2ux5rG6JbJ` | 169963 | 0.1178 | 15 | 150 | 0.1000 | [0.0615, 0.1584] | yes |
| 5 | `1GbF9tT63DtN` | 152166 | 0.1047 | 11 | 150 | 0.0733 | [0.0414, 0.1265] | yes |
| 5 | `1ZZ24eLfwd9C` | 446724 | 0.3070 | 53 | 150 | 0.3533 | [0.2814, 0.4326] | yes |
| 5 | `1ZiTV2tt2uge` | 390286 | 0.2710 | 40 | 150 | 0.2667 | [0.2024, 0.3426] | yes |
| 6 | `13rurX1BBorK` | 321934 | 0.1966 | 33 | 150 | 0.2200 | [0.1612, 0.2928] | yes |
| 6 | `1F2ux5rG6JbJ` | 199475 | 0.1215 | 17 | 150 | 0.1133 | [0.0720, 0.1740] | yes |
| 6 | `1GbF9tT63DtN` | 193175 | 0.1172 | 16 | 150 | 0.1067 | [0.0667, 0.1662] | yes |
| 6 | `1ZZ24eLfwd9C` | 497262 | 0.3036 | 48 | 150 | 0.3200 | [0.2506, 0.3983] | yes |
| 6 | `1ZiTV2tt2uge` | 427451 | 0.2612 | 36 | 150 | 0.2400 | [0.1787, 0.3143] | yes |
| 7 | `13rurX1BBorK` | 337260 | 0.2122 | 34 | 150 | 0.2267 | [0.1670, 0.3000] | yes |
| 7 | `1F2ux5rG6JbJ` | 202041 | 0.1273 | 21 | 150 | 0.1400 | [0.0934, 0.2046] | yes |
| 7 | `1GbF9tT63DtN` | 166470 | 0.1057 | 19 | 150 | 0.1267 | [0.0826, 0.1894] | yes |
| 7 | `1ZZ24eLfwd9C` | 499250 | 0.3147 | 59 | 150 | 0.3933 | [0.3188, 0.4732] | no |
| 7 | `1ZiTV2tt2uge` | 378544 | 0.2401 | 17 | 150 | 0.1133 | [0.0720, 0.1740] | no |
| 8 | `13rurX1BBorK` | 275160 | 0.1834 | 32 | 150 | 0.2133 | [0.1554, 0.2856] | yes |
| 8 | `1F2ux5rG6JbJ` | 207760 | 0.1369 | 21 | 150 | 0.1400 | [0.0934, 0.2046] | yes |
| 8 | `1GbF9tT63DtN` | 152288 | 0.1009 | 13 | 150 | 0.0867 | [0.0513, 0.1426] | yes |
| 8 | `1ZZ24eLfwd9C` | 499258 | 0.3295 | 48 | 150 | 0.3200 | [0.2506, 0.3983] | yes |
| 8 | `1ZiTV2tt2uge` | 377745 | 0.2493 | 36 | 150 | 0.2400 | [0.1787, 0.3143] | yes |
| 9 | `13rurX1BBorK` | 333006 | 0.2167 | 24 | 150 | 0.1600 | [0.1099, 0.2270] | yes |
| 9 | `1F2ux5rG6JbJ` | 186868 | 0.1233 | 15 | 150 | 0.1000 | [0.0615, 0.1584] | yes |
| 9 | `1GbF9tT63DtN` | 197703 | 0.1283 | 19 | 150 | 0.1267 | [0.0826, 0.1894] | yes |
| 9 | `1ZZ24eLfwd9C` | 460983 | 0.3037 | 42 | 150 | 0.2800 | [0.2143, 0.3567] | yes |
| 9 | `1ZiTV2tt2uge` | 345972 | 0.2280 | 50 | 150 | 0.3333 | [0.2629, 0.4121] | no |
| 10 | `13rurX1BBorK` | 362259 | 0.2472 | 32 | 150 | 0.2133 | [0.1554, 0.2856] | yes |
| 10 | `1F2ux5rG6JbJ` | 190826 | 0.1306 | 16 | 150 | 0.1067 | [0.0667, 0.1662] | yes |
| 10 | `1GbF9tT63DtN` | 189113 | 0.1298 | 28 | 150 | 0.1867 | [0.1324, 0.2566] | no |
| 10 | `1ZZ24eLfwd9C` | 428988 | 0.2948 | 44 | 150 | 0.2933 | [0.2264, 0.3706] | yes |
| 10 | `1ZiTV2tt2uge` | 285979 | 0.1977 | 30 | 150 | 0.2000 | [0.1438, 0.2711] | yes |
| 11 | `13rurX1BBorK` | 287735 | 0.1967 | 30 | 150 | 0.2000 | [0.1438, 0.2711] | yes |
| 11 | `1F2ux5rG6JbJ` | 181593 | 0.1229 | 21 | 150 | 0.1400 | [0.0934, 0.2046] | yes |
| 11 | `1GbF9tT63DtN` | 178636 | 0.1210 | 21 | 150 | 0.1400 | [0.0934, 0.2046] | yes |
| 11 | `1ZZ24eLfwd9C` | 430245 | 0.2905 | 28 | 150 | 0.1867 | [0.1324, 0.2566] | no |
| 11 | `1ZiTV2tt2uge` | 403923 | 0.2690 | 50 | 150 | 0.3333 | [0.2629, 0.4121] | yes |
| 12 | `13rurX1BBorK` | 277643 | 0.1980 | 33 | 150 | 0.2200 | [0.1612, 0.2928] | yes |
| 12 | `1F2ux5rG6JbJ` | 156268 | 0.1120 | 16 | 150 | 0.1067 | [0.0667, 0.1662] | yes |
| 12 | `1GbF9tT63DtN` | 142834 | 0.1028 | 16 | 150 | 0.1067 | [0.0667, 0.1662] | yes |
| 12 | `1ZZ24eLfwd9C` | 453704 | 0.3222 | 46 | 150 | 0.3067 | [0.2385, 0.3845] | yes |
| 12 | `1ZiTV2tt2uge` | 370745 | 0.2650 | 39 | 150 | 0.2600 | [0.1964, 0.3356] | yes |
| 13 | `13rurX1BBorK` | 280177 | 0.2014 | 30 | 150 | 0.2000 | [0.1438, 0.2711] | yes |
| 13 | `1F2ux5rG6JbJ` | 227360 | 0.1611 | 19 | 150 | 0.1267 | [0.0826, 0.1894] | yes |
| 13 | `1GbF9tT63DtN` | 159394 | 0.1140 | 17 | 150 | 0.1133 | [0.0720, 0.1740] | yes |
| 13 | `1ZZ24eLfwd9C` | 408315 | 0.2951 | 49 | 150 | 0.3267 | [0.2568, 0.4052] | yes |
| 13 | `1ZiTV2tt2uge` | 315119 | 0.2284 | 35 | 150 | 0.2333 | [0.1728, 0.3072] | yes |
| 14 | `13rurX1BBorK` | 336227 | 0.2158 | 36 | 150 | 0.2400 | [0.1787, 0.3143] | yes |
| 14 | `1F2ux5rG6JbJ` | 204898 | 0.1334 | 17 | 150 | 0.1133 | [0.0720, 0.1740] | yes |
| 14 | `1GbF9tT63DtN` | 178547 | 0.1149 | 15 | 150 | 0.1000 | [0.0615, 0.1584] | yes |
| 14 | `1ZZ24eLfwd9C` | 499908 | 0.3205 | 46 | 150 | 0.3067 | [0.2385, 0.3845] | yes |
| 14 | `1ZiTV2tt2uge` | 333590 | 0.2153 | 36 | 150 | 0.2400 | [0.1787, 0.3143] | yes |
| 15 | `13rurX1BBorK` | 370648 | 0.2379 | 48 | 150 | 0.3200 | [0.2506, 0.3983] | no |
| 15 | `1F2ux5rG6JbJ` | 216276 | 0.1391 | 15 | 150 | 0.1000 | [0.0615, 0.1584] | yes |
| 15 | `1GbF9tT63DtN` | 154511 | 0.1003 | 14 | 150 | 0.0933 | [0.0564, 0.1506] | yes |
| 15 | `1ZZ24eLfwd9C` | 392659 | 0.2563 | 27 | 150 | 0.1800 | [0.1268, 0.2492] | no |
| 15 | `1ZiTV2tt2uge` | 417271 | 0.2664 | 46 | 150 | 0.3067 | [0.2385, 0.3845] | yes |
| 16 | `13rurX1BBorK` | 306848 | 0.2095 | 39 | 150 | 0.2600 | [0.1964, 0.3356] | yes |
| 16 | `1F2ux5rG6JbJ` | 198882 | 0.1351 | 15 | 150 | 0.1000 | [0.0615, 0.1584] | yes |
| 16 | `1GbF9tT63DtN` | 151568 | 0.1026 | 19 | 150 | 0.1267 | [0.0826, 0.1894] | yes |
| 16 | `1ZZ24eLfwd9C` | 453717 | 0.3051 | 40 | 150 | 0.2667 | [0.2024, 0.3426] | yes |
| 16 | `1ZiTV2tt2uge` | 363949 | 0.2478 | 37 | 150 | 0.2467 | [0.1846, 0.3214] | yes |
| 17 | `13rurX1BBorK` | 338164 | 0.2421 | 27 | 150 | 0.1800 | [0.1268, 0.2492] | yes |
| 17 | `1F2ux5rG6JbJ` | 165470 | 0.1200 | 16 | 150 | 0.1067 | [0.0667, 0.1662] | yes |
| 17 | `1GbF9tT63DtN` | 146966 | 0.1058 | 22 | 150 | 0.1467 | [0.0989, 0.2121] | yes |
| 17 | `1ZZ24eLfwd9C` | 335569 | 0.2450 | 40 | 150 | 0.2667 | [0.2024, 0.3426] | yes |
| 17 | `1ZiTV2tt2uge` | 400881 | 0.2870 | 45 | 150 | 0.3000 | [0.2324, 0.3776] | yes |
| 18 | `13rurX1BBorK` | 245350 | 0.1826 | 17 | 150 | 0.1133 | [0.0720, 0.1740] | no |
| 18 | `1F2ux5rG6JbJ` | 224144 | 0.1620 | 28 | 150 | 0.1867 | [0.1324, 0.2566] | yes |
| 18 | `1GbF9tT63DtN` | 168805 | 0.1227 | 21 | 150 | 0.1400 | [0.0934, 0.2046] | yes |
| 18 | `1ZZ24eLfwd9C` | 380015 | 0.2764 | 43 | 150 | 0.2867 | [0.2203, 0.3636] | yes |
| 18 | `1ZiTV2tt2uge` | 348072 | 0.2563 | 41 | 150 | 0.2733 | [0.2083, 0.3496] | yes |
| 19 | `13rurX1BBorK` | 367029 | 0.2133 | 9 | 35 | 0.2571 | [0.1416, 0.4207] | yes |
| 19 | `1F2ux5rG6JbJ` | 271473 | 0.1638 | 4 | 35 | 0.1143 | [0.0454, 0.2595] | yes |
| 19 | `1GbF9tT63DtN` | 144859 | 0.0944 | 4 | 35 | 0.1143 | [0.0454, 0.2595] | yes |
| 19 | `1ZZ24eLfwd9C` | 464667 | 0.2799 | 6 | 35 | 0.1714 | [0.0810, 0.3268] | yes |
| 19 | `1ZiTV2tt2uge` | 409806 | 0.2487 | 12 | 35 | 0.3429 | [0.2083, 0.5085] | yes |

## Pooled over every measured epoch

| validator | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---:|---:|---:|---:|---|---|
| `13rurX1BBorK` | 0.2101 | 548 | 2735 | 0.2004 | [0.1858, 0.2158] | yes |
| `1F2ux5rG6JbJ` | 0.1335 | 349 | 2735 | 0.1276 | [0.1156, 0.1406] | yes |
| `1GbF9tT63DtN` | 0.1102 | 313 | 2735 | 0.1144 | [0.1030, 0.1269] | yes |
| `1ZZ24eLfwd9C` | 0.2934 | 778 | 2735 | 0.2845 | [0.2679, 0.3017] | yes |
| `1ZiTV2tt2uge` | 0.2527 | 714 | 2735 | 0.2611 | [0.2449, 0.2778] | yes |

## Joint test per epoch (chi-square / exact / Monte Carlo)

| epoch | blocks | validators | method | statistic | p | reject at 0.05 | TV | round-by-round p |
|---|---:|---:|---|---:|---:|---|---:|---:|
| 1 | 117 | 5 | chi2_asymptotic | 10.624 | 0.0311 | YES | 0.1456 | - |
| 2 | 150 | 5 | chi2_asymptotic | 4.338 | 0.3622 | no | 0.0637 | 0.3645 |
| 3 | 150 | 5 | chi2_asymptotic | 1.149 | 0.8864 | no | 0.0346 | 0.8931 |
| 4 | 150 | 5 | chi2_asymptotic | 8.210 | 0.0842 | no | 0.1010 | 0.0850 |
| 5 | 150 | 5 | chi2_asymptotic | 2.912 | 0.5726 | no | 0.0535 | 0.5807 |
| 6 | 150 | 5 | chi2_asymptotic | 1.035 | 0.9045 | no | 0.0399 | 0.9067 |
| 7 | 150 | 5 | chi2_asymptotic | 13.941 | 0.0075 | YES | 0.1267 | 0.0084 |
| 8 | 150 | 5 | chi2_asymptotic | 1.137 | 0.8883 | no | 0.0330 | 0.8918 |
| 9 | 150 | 5 | chi2_asymptotic | 10.465 | 0.0333 | YES | 0.1053 | 0.0354 |
| 10 | 150 | 5 | chi2_asymptotic | 5.098 | 0.2774 | no | 0.0592 | 0.2834 |
| 11 | 150 | 5 | chi2_asymptotic | 8.690 | 0.0693 | no | 0.1038 | 0.0725 |
| 12 | 150 | 5 | chi2_asymptotic | 0.555 | 0.9679 | no | 0.0259 | 0.9690 |
| 13 | 150 | 5 | chi2_asymptotic | 1.629 | 0.8036 | no | 0.0365 | 0.8129 |
| 14 | 150 | 5 | chi2_asymptotic | 1.666 | 0.7969 | no | 0.0489 | 0.8033 |
| 15 | 150 | 5 | chi2_asymptotic | 10.291 | 0.0358 | YES | 0.1224 | 0.0367 |
| 16 | 150 | 5 | chi2_asymptotic | 4.764 | 0.3124 | no | 0.0746 | 0.3149 |
| 17 | 150 | 5 | chi2_asymptotic | 5.357 | 0.2526 | no | 0.0755 | 0.2545 |
| 18 | 150 | 5 | chi2_asymptotic | 5.094 | 0.2778 | no | 0.0692 | 0.2845 |
| 19 | 35 | 5 | monte_carlo_multinomial | 3.706 | 0.4488 | no | 0.1580 | 0.4510 |
| all | 2702 | 5 | chi2_asymptotic | 3.891 | 0.4210 | no | 0.0188 | 0.4756 |

## How to read this

- **The interval, not the point.** A `p_hat` far from `p_theoretical` means nothing if the interval is wide; with a handful of blocks per epoch it usually is. The mean interval width here is **0.1244**, which is the resolution of this run.
- **Multiple comparisons.** 10 of 95 intervals excluded the entitled share; about 4.8 are expected to by chance alone at alpha = 0.05. Only a count well above the expectation is a finding.
- **The joint test is the real one.** The per-validator intervals say *which* validator is out of line; the chi-square says whether the epoch as a whole is distinguishable from weighted sortition.
- **Round-by-round when the shares moved.** Where an epoch's shares changed mid-epoch, the pooled multinomial tests a null that was never in force, and the round-by-round Monte-Carlo p-value in the last column is the one to read.

The corresponding figure is `plots/weight_vs_election.png`, produced by `plotting/generate_plots.py`.
