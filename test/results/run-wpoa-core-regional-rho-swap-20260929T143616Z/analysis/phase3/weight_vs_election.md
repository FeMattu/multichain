# Weight versus probability of election

> The headline comparison of this experiment. For each epoch and each validator: the share of blocks the **final weight** entitled it to, against the share it actually won, with a 95% Wilson interval around the observed share and a joint goodness-of-fit test over all validators of the epoch.

## What is being compared

`p_theoretical` is built from `effective_weight_after_malus_and_dumping` — the quantity the election **actually consumes**, after the malus factor and after the dumping function — and is block-weighted across the rounds of the epoch, so an epoch whose weights moved is summarised by what was in force rather than by a snapshot of either end.

`p_hat = O_i / B` is the observed share. The Wilson interval is the 95% score interval around it; it stays inside [0,1] and has sensible width at `O_i = 0`, where the textbook interval collapses to zero.

**Epochs [1] are excluded**: their rounds lie at or below `setup-first-blocks = 220`, where the chain is governed by native MultiChain round robin rather than by wPoA. Testing them would measure the wrong mechanism.

## Per-epoch, per-validator

| epoch | validator | w_final | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---|---:|---:|---:|---:|---:|---|---|
| 2 | `18UgQcEGcW2T` | 7699 | 0.2254 | 21 | 100 | 0.2100 | [0.1417, 0.2998] | yes |
| 2 | `1AGTXj8mawcm` | 3512 | 0.1013 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 2 | `1EXHKJyuBUQg` | 7868 | 0.2271 | 21 | 100 | 0.2100 | [0.1417, 0.2998] | yes |
| 2 | `1TM3NZRQ46ct` | 9181 | 0.2638 | 24 | 100 | 0.2400 | [0.1669, 0.3323] | yes |
| 2 | `1aqjwAwmciqr` | 6369 | 0.1825 | 18 | 100 | 0.1800 | [0.1170, 0.2667] | yes |
| 3 | `18UgQcEGcW2T` | 13485 | 0.2096 | 26 | 100 | 0.2600 | [0.1840, 0.3537] | yes |
| 3 | `1AGTXj8mawcm` | 7632 | 0.1169 | 9 | 100 | 0.0900 | [0.0481, 0.1623] | yes |
| 3 | `1EXHKJyuBUQg` | 7951 | 0.1303 | 9 | 100 | 0.0900 | [0.0481, 0.1623] | yes |
| 3 | `1TM3NZRQ46ct` | 14124 | 0.2218 | 23 | 100 | 0.2300 | [0.1584, 0.3215] | yes |
| 3 | `1aqjwAwmciqr` | 21438 | 0.3214 | 33 | 100 | 0.3300 | [0.2456, 0.4269] | yes |
| 4 | `18UgQcEGcW2T` | 22776 | 0.2884 | 25 | 100 | 0.2500 | [0.1755, 0.3430] | yes |
| 4 | `1AGTXj8mawcm` | 4400 | 0.0612 | 10 | 100 | 0.1000 | [0.0552, 0.1744] | yes |
| 4 | `1EXHKJyuBUQg` | 7211 | 0.0953 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 4 | `1TM3NZRQ46ct` | 24642 | 0.3115 | 25 | 100 | 0.2500 | [0.1755, 0.3430] | yes |
| 4 | `1aqjwAwmciqr` | 18328 | 0.2436 | 28 | 100 | 0.2800 | [0.2014, 0.3749] | yes |
| 5 | `18UgQcEGcW2T` | 13182 | 0.1967 | 22 | 100 | 0.2200 | [0.1500, 0.3107] | yes |
| 5 | `1AGTXj8mawcm` | 3875 | 0.0557 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 5 | `1EXHKJyuBUQg` | 7102 | 0.1014 | 7 | 100 | 0.0700 | [0.0343, 0.1375] | yes |
| 5 | `1TM3NZRQ46ct` | 23498 | 0.3362 | 34 | 100 | 0.3400 | [0.2546, 0.4372] | yes |
| 5 | `1aqjwAwmciqr` | 21967 | 0.3100 | 32 | 100 | 0.3200 | [0.2367, 0.4166] | yes |
| 6 | `18UgQcEGcW2T` | 25217 | 0.3120 | 28 | 100 | 0.2800 | [0.2014, 0.3749] | yes |
| 6 | `1AGTXj8mawcm` | 4336 | 0.0553 | 6 | 100 | 0.0600 | [0.0278, 0.1248] | yes |
| 6 | `1EXHKJyuBUQg` | 10454 | 0.1310 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 6 | `1TM3NZRQ46ct` | 20412 | 0.2655 | 29 | 100 | 0.2900 | [0.2101, 0.3854] | yes |
| 6 | `1aqjwAwmciqr` | 18072 | 0.2362 | 25 | 100 | 0.2500 | [0.1755, 0.3430] | yes |
| 7 | `18UgQcEGcW2T` | 21811 | 0.2580 | 24 | 100 | 0.2400 | [0.1669, 0.3323] | yes |
| 7 | `1AGTXj8mawcm` | 7286 | 0.0825 | 8 | 100 | 0.0800 | [0.0411, 0.1500] | yes |
| 7 | `1EXHKJyuBUQg` | 8457 | 0.1006 | 11 | 100 | 0.1100 | [0.0625, 0.1863] | yes |
| 7 | `1TM3NZRQ46ct` | 24905 | 0.2871 | 31 | 100 | 0.3100 | [0.2278, 0.4063] | yes |
| 7 | `1aqjwAwmciqr` | 23684 | 0.2718 | 26 | 100 | 0.2600 | [0.1840, 0.3537] | yes |
| 8 | `18UgQcEGcW2T` | 22879 | 0.2840 | 26 | 100 | 0.2600 | [0.1840, 0.3537] | yes |
| 8 | `1AGTXj8mawcm` | 5766 | 0.0730 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 8 | `1EXHKJyuBUQg` | 8621 | 0.1072 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 8 | `1TM3NZRQ46ct` | 22423 | 0.2812 | 29 | 100 | 0.2900 | [0.2101, 0.3854] | yes |
| 8 | `1aqjwAwmciqr` | 20217 | 0.2545 | 28 | 100 | 0.2800 | [0.2014, 0.3749] | yes |
| 9 | `18UgQcEGcW2T` | 24795 | 0.2896 | 29 | 100 | 0.2900 | [0.2101, 0.3854] | yes |
| 9 | `1AGTXj8mawcm` | 6061 | 0.0709 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 9 | `1EXHKJyuBUQg` | 8462 | 0.0995 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 9 | `1TM3NZRQ46ct` | 21911 | 0.2578 | 28 | 100 | 0.2800 | [0.2014, 0.3749] | yes |
| 9 | `1aqjwAwmciqr` | 24316 | 0.2821 | 26 | 100 | 0.2600 | [0.1840, 0.3537] | yes |
| 10 | `18UgQcEGcW2T` | 24931 | 0.3188 | 20 | 100 | 0.2000 | [0.1334, 0.2888] | no |
| 10 | `1AGTXj8mawcm` | 9333 | 0.1167 | 17 | 100 | 0.1700 | [0.1089, 0.2555] | yes |
| 10 | `1EXHKJyuBUQg` | 9131 | 0.1163 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 10 | `1TM3NZRQ46ct` | 15593 | 0.2046 | 26 | 100 | 0.2600 | [0.1840, 0.3537] | yes |
| 10 | `1aqjwAwmciqr` | 18679 | 0.2436 | 25 | 100 | 0.2500 | [0.1755, 0.3430] | yes |
| 11 | `18UgQcEGcW2T` | 23813 | 0.2900 | 27 | 100 | 0.2700 | [0.1927, 0.3643] | yes |
| 11 | `1AGTXj8mawcm` | 9610 | 0.1164 | 16 | 100 | 0.1600 | [0.1010, 0.2442] | yes |
| 11 | `1EXHKJyuBUQg` | 7952 | 0.0976 | 11 | 100 | 0.1100 | [0.0625, 0.1863] | yes |
| 11 | `1TM3NZRQ46ct` | 18726 | 0.2244 | 20 | 100 | 0.2000 | [0.1334, 0.2888] | yes |
| 11 | `1aqjwAwmciqr` | 22692 | 0.2717 | 26 | 100 | 0.2600 | [0.1840, 0.3537] | yes |
| 12 | `18UgQcEGcW2T` | 23257 | 0.2878 | 34 | 100 | 0.3400 | [0.2546, 0.4372] | yes |
| 12 | `1AGTXj8mawcm` | 7357 | 0.0928 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 12 | `1EXHKJyuBUQg` | 7935 | 0.0980 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 12 | `1TM3NZRQ46ct` | 24181 | 0.2941 | 33 | 100 | 0.3300 | [0.2456, 0.4269] | yes |
| 12 | `1aqjwAwmciqr` | 18087 | 0.2273 | 16 | 100 | 0.1600 | [0.1010, 0.2442] | yes |
| 13 | `18UgQcEGcW2T` | 23670 | 0.3308 | 35 | 100 | 0.3500 | [0.2636, 0.4475] | yes |
| 13 | `1AGTXj8mawcm` | 6945 | 0.0975 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 13 | `1EXHKJyuBUQg` | 7470 | 0.1049 | 13 | 100 | 0.1300 | [0.0776, 0.2098] | yes |
| 13 | `1TM3NZRQ46ct` | 9274 | 0.1427 | 13 | 100 | 0.1300 | [0.0776, 0.2098] | yes |
| 13 | `1aqjwAwmciqr` | 23490 | 0.3240 | 34 | 100 | 0.3400 | [0.2546, 0.4372] | yes |
| 14 | `18UgQcEGcW2T` | 14395 | 0.2292 | 18 | 100 | 0.1800 | [0.1170, 0.2667] | yes |
| 14 | `1AGTXj8mawcm` | 6911 | 0.1057 | 9 | 100 | 0.0900 | [0.0481, 0.1623] | yes |
| 14 | `1EXHKJyuBUQg` | 9003 | 0.1361 | 18 | 100 | 0.1800 | [0.1170, 0.2667] | yes |
| 14 | `1TM3NZRQ46ct` | 13712 | 0.2052 | 19 | 100 | 0.1900 | [0.1251, 0.2778] | yes |
| 14 | `1aqjwAwmciqr` | 21019 | 0.3238 | 36 | 100 | 0.3600 | [0.2727, 0.4576] | yes |
| 15 | `18UgQcEGcW2T` | 22912 | 0.2611 | 17 | 100 | 0.1700 | [0.1089, 0.2555] | no |
| 15 | `1AGTXj8mawcm` | 7192 | 0.0845 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 15 | `1EXHKJyuBUQg` | 8634 | 0.1023 | 11 | 100 | 0.1100 | [0.0625, 0.1863] | yes |
| 15 | `1TM3NZRQ46ct` | 23383 | 0.2654 | 19 | 100 | 0.1900 | [0.1251, 0.2778] | yes |
| 15 | `1aqjwAwmciqr` | 24626 | 0.2866 | 41 | 100 | 0.4100 | [0.3187, 0.5080] | no |
| 16 | `18UgQcEGcW2T` | 18067 | 0.2584 | 31 | 100 | 0.3100 | [0.2278, 0.4063] | yes |
| 16 | `1AGTXj8mawcm` | 7661 | 0.1075 | 7 | 100 | 0.0700 | [0.0343, 0.1375] | yes |
| 16 | `1EXHKJyuBUQg` | 9592 | 0.1343 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 16 | `1TM3NZRQ46ct` | 19931 | 0.2835 | 32 | 100 | 0.3200 | [0.2367, 0.4166] | yes |
| 16 | `1aqjwAwmciqr` | 14781 | 0.2162 | 18 | 100 | 0.1800 | [0.1170, 0.2667] | yes |
| 17 | `18UgQcEGcW2T` | 11817 | 0.1702 | 15 | 100 | 0.1500 | [0.0931, 0.2328] | yes |
| 17 | `1AGTXj8mawcm` | 4494 | 0.0655 | 2 | 100 | 0.0200 | [0.0055, 0.0700] | yes |
| 17 | `1EXHKJyuBUQg` | 29572 | 0.3902 | 40 | 100 | 0.4000 | [0.3094, 0.4980] | yes |
| 17 | `1TM3NZRQ46ct` | 17237 | 0.2418 | 24 | 100 | 0.2400 | [0.1669, 0.3323] | yes |
| 17 | `1aqjwAwmciqr` | 9129 | 0.1323 | 19 | 100 | 0.1900 | [0.1251, 0.2778] | yes |
| 18 | `18UgQcEGcW2T` | 20185 | 0.2318 | 22 | 100 | 0.2200 | [0.1500, 0.3107] | yes |
| 18 | `1AGTXj8mawcm` | 5759 | 0.0672 | 7 | 100 | 0.0700 | [0.0343, 0.1375] | yes |
| 18 | `1EXHKJyuBUQg` | 30601 | 0.3627 | 43 | 100 | 0.4300 | [0.3373, 0.5278] | yes |
| 18 | `1TM3NZRQ46ct` | 22567 | 0.2630 | 19 | 100 | 0.1900 | [0.1251, 0.2778] | yes |
| 18 | `1aqjwAwmciqr` | 6092 | 0.0753 | 9 | 100 | 0.0900 | [0.0481, 0.1623] | yes |
| 19 | `18UgQcEGcW2T` | 18882 | 0.2297 | 22 | 100 | 0.2200 | [0.1500, 0.3107] | yes |
| 19 | `1AGTXj8mawcm` | 5896 | 0.0713 | 9 | 100 | 0.0900 | [0.0481, 0.1623] | yes |
| 19 | `1EXHKJyuBUQg` | 32112 | 0.3876 | 41 | 100 | 0.4100 | [0.3187, 0.5080] | yes |
| 19 | `1TM3NZRQ46ct` | 18720 | 0.2298 | 22 | 100 | 0.2200 | [0.1500, 0.3107] | yes |
| 19 | `1aqjwAwmciqr` | 6784 | 0.0816 | 6 | 100 | 0.0600 | [0.0278, 0.1248] | yes |
| 20 | `18UgQcEGcW2T` | 11141 | 0.1387 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 20 | `1AGTXj8mawcm` | 5875 | 0.0697 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | no |
| 20 | `1EXHKJyuBUQg` | 33556 | 0.3966 | 43 | 100 | 0.4300 | [0.3373, 0.5278] | yes |
| 20 | `1TM3NZRQ46ct` | 28539 | 0.3300 | 25 | 100 | 0.2500 | [0.1755, 0.3430] | yes |
| 20 | `1aqjwAwmciqr` | 5387 | 0.0651 | 8 | 100 | 0.0800 | [0.0411, 0.1500] | yes |
| 21 | `18UgQcEGcW2T` | 29650 | 0.3230 | 30 | 100 | 0.3000 | [0.2189, 0.3958] | yes |
| 21 | `1AGTXj8mawcm` | 9990 | 0.1106 | 15 | 100 | 0.1500 | [0.0931, 0.2328] | yes |
| 21 | `1EXHKJyuBUQg` | 30877 | 0.3545 | 33 | 100 | 0.3300 | [0.2456, 0.4269] | yes |
| 21 | `1TM3NZRQ46ct` | 12710 | 0.1581 | 17 | 100 | 0.1700 | [0.1089, 0.2555] | yes |
| 21 | `1aqjwAwmciqr` | 4660 | 0.0538 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 22 | `18UgQcEGcW2T` | 28946 | 0.3334 | 39 | 100 | 0.3900 | [0.3002, 0.4880] | yes |
| 22 | `1AGTXj8mawcm` | 10757 | 0.1231 | 10 | 100 | 0.1000 | [0.0552, 0.1744] | yes |
| 22 | `1EXHKJyuBUQg` | 30723 | 0.3534 | 35 | 100 | 0.3500 | [0.2636, 0.4475] | yes |
| 22 | `1TM3NZRQ46ct` | 10632 | 0.1239 | 10 | 100 | 0.1000 | [0.0552, 0.1744] | yes |
| 22 | `1aqjwAwmciqr` | 5830 | 0.0661 | 6 | 100 | 0.0600 | [0.0278, 0.1248] | yes |
| 23 | `18UgQcEGcW2T` | 14345 | 0.1898 | 17 | 100 | 0.1700 | [0.1089, 0.2555] | yes |
| 23 | `1AGTXj8mawcm` | 6912 | 0.0889 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 23 | `1EXHKJyuBUQg` | 32047 | 0.3967 | 39 | 100 | 0.3900 | [0.3002, 0.4880] | yes |
| 23 | `1TM3NZRQ46ct` | 21433 | 0.2574 | 30 | 100 | 0.3000 | [0.2189, 0.3958] | yes |
| 23 | `1aqjwAwmciqr` | 5382 | 0.0672 | 2 | 100 | 0.0200 | [0.0055, 0.0700] | yes |
| 24 | `18UgQcEGcW2T` | 13080 | 0.1964 | 20 | 100 | 0.2000 | [0.1334, 0.2888] | yes |
| 24 | `1AGTXj8mawcm` | 6106 | 0.0919 | 9 | 100 | 0.0900 | [0.0481, 0.1623] | yes |
| 24 | `1EXHKJyuBUQg` | 29055 | 0.4365 | 38 | 100 | 0.3800 | [0.2910, 0.4779] | yes |
| 24 | `1TM3NZRQ46ct` | 11937 | 0.1865 | 27 | 100 | 0.2700 | [0.1927, 0.3643] | no |
| 24 | `1aqjwAwmciqr` | 5975 | 0.0887 | 6 | 100 | 0.0600 | [0.0278, 0.1248] | yes |
| 25 | `18UgQcEGcW2T` | 32259 | 0.3862 | 47 | 100 | 0.4700 | [0.3751, 0.5671] | yes |
| 25 | `1AGTXj8mawcm` | 6754 | 0.0844 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 25 | `1EXHKJyuBUQg` | 27312 | 0.3460 | 22 | 100 | 0.2200 | [0.1500, 0.3107] | no |
| 25 | `1TM3NZRQ46ct` | 9155 | 0.1183 | 13 | 100 | 0.1300 | [0.0776, 0.2098] | yes |
| 25 | `1aqjwAwmciqr` | 5100 | 0.0652 | 6 | 100 | 0.0600 | [0.0278, 0.1248] | yes |
| 26 | `18UgQcEGcW2T` | 32192 | 0.3536 | 34 | 100 | 0.3400 | [0.2546, 0.4372] | yes |
| 26 | `1AGTXj8mawcm` | 9313 | 0.1000 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 26 | `1EXHKJyuBUQg` | 30977 | 0.3370 | 31 | 100 | 0.3100 | [0.2278, 0.4063] | yes |
| 26 | `1TM3NZRQ46ct` | 14328 | 0.1528 | 16 | 100 | 0.1600 | [0.1010, 0.2442] | yes |
| 26 | `1aqjwAwmciqr` | 5158 | 0.0566 | 7 | 100 | 0.0700 | [0.0343, 0.1375] | yes |
| 27 | `18UgQcEGcW2T` | 21655 | 0.2722 | 31 | 100 | 0.3100 | [0.2278, 0.4063] | yes |
| 27 | `1AGTXj8mawcm` | 4714 | 0.0610 | 0 | 100 | 0.0000 | [0.0000, 0.0370] | no |
| 27 | `1EXHKJyuBUQg` | 30552 | 0.3731 | 34 | 100 | 0.3400 | [0.2546, 0.4372] | yes |
| 27 | `1TM3NZRQ46ct` | 18919 | 0.2273 | 27 | 100 | 0.2700 | [0.1927, 0.3643] | yes |
| 27 | `1aqjwAwmciqr` | 5453 | 0.0663 | 8 | 100 | 0.0800 | [0.0411, 0.1500] | yes |
| 28 | `18UgQcEGcW2T` | 24126 | 0.2671 | 24 | 100 | 0.2400 | [0.1669, 0.3323] | yes |
| 28 | `1AGTXj8mawcm` | 9992 | 0.1069 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 28 | `1EXHKJyuBUQg` | 36833 | 0.4056 | 42 | 100 | 0.4200 | [0.3280, 0.5179] | yes |
| 28 | `1TM3NZRQ46ct` | 12976 | 0.1499 | 9 | 100 | 0.0900 | [0.0481, 0.1623] | yes |
| 28 | `1aqjwAwmciqr` | 6393 | 0.0705 | 13 | 100 | 0.1300 | [0.0776, 0.2098] | no |
| 29 | `18UgQcEGcW2T` | 23219 | 0.2806 | 26 | 100 | 0.2600 | [0.1840, 0.3537] | yes |
| 29 | `1AGTXj8mawcm` | 7706 | 0.0947 | 8 | 100 | 0.0800 | [0.0411, 0.1500] | yes |
| 29 | `1EXHKJyuBUQg` | 26055 | 0.3225 | 30 | 100 | 0.3000 | [0.2189, 0.3958] | yes |
| 29 | `1TM3NZRQ46ct` | 20197 | 0.2379 | 29 | 100 | 0.2900 | [0.2101, 0.3854] | yes |
| 29 | `1aqjwAwmciqr` | 5263 | 0.0643 | 7 | 100 | 0.0700 | [0.0343, 0.1375] | yes |
| 30 | `18UgQcEGcW2T` | 21425 | 0.2705 | 27 | 100 | 0.2700 | [0.1927, 0.3643] | yes |
| 30 | `1AGTXj8mawcm` | 6998 | 0.0884 | 13 | 100 | 0.1300 | [0.0776, 0.2098] | yes |
| 30 | `1EXHKJyuBUQg` | 30895 | 0.3837 | 40 | 100 | 0.4000 | [0.3094, 0.4980] | yes |
| 30 | `1TM3NZRQ46ct` | 14324 | 0.1848 | 14 | 100 | 0.1400 | [0.0853, 0.2214] | yes |
| 30 | `1aqjwAwmciqr` | 5825 | 0.0726 | 6 | 100 | 0.0600 | [0.0278, 0.1248] | yes |
| 31 | `18UgQcEGcW2T` | 23065 | 0.2651 | 4 | 21 | 0.1905 | [0.0767, 0.4000] | yes |
| 31 | `1AGTXj8mawcm` | 7612 | 0.0872 | 1 | 21 | 0.0476 | [0.0085, 0.2267] | yes |
| 31 | `1EXHKJyuBUQg` | 30205 | 0.3585 | 10 | 21 | 0.4762 | [0.2834, 0.6763] | yes |
| 31 | `1TM3NZRQ46ct` | 20185 | 0.2143 | 4 | 21 | 0.1905 | [0.0767, 0.4000] | yes |
| 31 | `1aqjwAwmciqr` | 6643 | 0.0750 | 2 | 21 | 0.0952 | [0.0265, 0.2891] | yes |

## Pooled over every measured epoch

| validator | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---:|---:|---:|---:|---|---|
| `18UgQcEGcW2T` | 0.2649 | 753 | 2921 | 0.2578 | [0.2423, 0.2740] | yes |
| `1AGTXj8mawcm` | 0.0883 | 265 | 2921 | 0.0907 | [0.0808, 0.1017] | yes |
| `1EXHKJyuBUQg` | 0.2432 | 706 | 2921 | 0.2417 | [0.2265, 0.2576] | yes |
| `1TM3NZRQ46ct` | 0.2311 | 671 | 2921 | 0.2297 | [0.2148, 0.2453] | yes |
| `1aqjwAwmciqr` | 0.1724 | 522 | 2921 | 0.1787 | [0.1652, 0.1930] | yes |

## Joint test per epoch (chi-square / exact / Monte Carlo)

| epoch | blocks | validators | method | statistic | p | reject at 0.05 | TV | round-by-round p |
|---|---:|---:|---|---:|---:|---|---:|---:|
| 2 | 96 | 5 | chi2_asymptotic | 0.798 | 0.9387 | no | 0.0403 | 0.9426 |
| 3 | 100 | 5 | chi2_asymptotic | 3.132 | 0.5359 | no | 0.0672 | 0.5352 |
| 4 | 100 | 5 | chi2_asymptotic | 5.379 | 0.2506 | no | 0.1000 | 0.2533 |
| 5 | 100 | 5 | chi2_asymptotic | 1.344 | 0.8539 | no | 0.0371 | 0.8606 |
| 6 | 100 | 5 | chi2_asymptotic | 0.769 | 0.9426 | no | 0.0430 | 0.9430 |
| 7 | 100 | 5 | chi2_asymptotic | 0.454 | 0.9778 | no | 0.0323 | 0.9795 |
| 8 | 100 | 5 | chi2_asymptotic | 1.364 | 0.8505 | no | 0.0470 | 0.8481 |
| 9 | 100 | 5 | chi2_asymptotic | 1.401 | 0.8439 | no | 0.0430 | 0.8450 |
| 10 | 100 | 5 | chi2_asymptotic | 8.387 | 0.0784 | no | 0.1188 | 0.0791 |
| 11 | 100 | 5 | chi2_asymptotic | 2.249 | 0.6901 | no | 0.0561 | 0.6939 |
| 12 | 100 | 5 | chi2_asymptotic | 5.845 | 0.2110 | no | 0.1101 | 0.2120 |
| 13 | 100 | 5 | chi2_asymptotic | 3.218 | 0.5220 | no | 0.0602 | 0.5203 |
| 14 | 100 | 5 | chi2_asymptotic | 3.223 | 0.5212 | no | 0.0801 | 0.5214 |
| 15 | 100 | 5 | chi2_asymptotic | 12.180 | 0.0161 | YES | 0.1666 | 0.0158 |
| 16 | 100 | 5 | chi2_asymptotic | 3.567 | 0.4678 | no | 0.0880 | 0.4703 |
| 17 | 100 | 5 | chi2_asymptotic | 5.944 | 0.2034 | no | 0.0675 | 0.1978 |
| 18 | 100 | 5 | chi2_asymptotic | 3.634 | 0.4578 | no | 0.0848 | 0.4551 |
| 19 | 100 | 5 | chi2_asymptotic | 1.275 | 0.8656 | no | 0.0411 | 0.8670 |
| 20 | 100 | 5 | chi2_asymptotic | 6.451 | 0.1679 | no | 0.0987 | 0.1661 |
| 21 | 100 | 5 | chi2_asymptotic | 1.854 | 0.7626 | no | 0.0513 | 0.7631 |
| 22 | 100 | 5 | chi2_asymptotic | 1.914 | 0.7515 | no | 0.0566 | 0.7540 |
| 23 | 100 | 5 | chi2_asymptotic | 5.326 | 0.2555 | no | 0.0737 | 0.2520 |
| 24 | 100 | 5 | chi2_asymptotic | 5.404 | 0.2483 | no | 0.0870 | 0.2487 |
| 25 | 100 | 5 | chi2_asymptotic | 8.064 | 0.0892 | no | 0.1311 | 0.0885 |
| 26 | 100 | 5 | chi2_asymptotic | 1.017 | 0.9072 | no | 0.0405 | 0.9081 |
| 27 | 100 | 5 | chi2_asymptotic | 8.002 | 0.0915 | no | 0.0941 | 0.0891 |
| 28 | 100 | 5 | chi2_asymptotic | 7.895 | 0.0955 | no | 0.0870 | 0.0953 |
| 29 | 100 | 5 | chi2_asymptotic | 1.727 | 0.7858 | no | 0.0578 | 0.7901 |
| 30 | 100 | 5 | chi2_asymptotic | 3.328 | 0.5046 | no | 0.0579 | 0.5042 |
| 31 | 21 | 5 | monte_carlo_multinomial | 1.800 | 0.7998 | no | 0.1380 | 0.8001 |
| all | 2917 | 5 | chi2_asymptotic | 1.473 | 0.8314 | no | 0.0094 | 0.7993 |

## How to read this

- **The interval, not the point.** A `p_hat` far from `p_theoretical` means nothing if the interval is wide; with a handful of blocks per epoch it usually is. The mean interval width here is **0.1475**, which is the resolution of this run.
- **Multiple comparisons.** 8 of 150 intervals excluded the entitled share; about 7.5 are expected to by chance alone at alpha = 0.05. Only a count well above the expectation is a finding.
- **The joint test is the real one.** The per-validator intervals say *which* validator is out of line; the chi-square says whether the epoch as a whole is distinguishable from weighted sortition.
- **Round-by-round when the shares moved.** Where an epoch's shares changed mid-epoch, the pooled multinomial tests a null that was never in force, and the round-by-round Monte-Carlo p-value in the last column is the one to read.

The corresponding figure is `plots/weight_vs_election.png`, produced by `plotting/generate_plots.py`.
