# Weight versus probability of election

> The headline comparison of this experiment. For each epoch and each validator: the share of blocks the **final weight** entitled it to, against the share it actually won, with a 95% Wilson interval around the observed share and a joint goodness-of-fit test over all validators of the epoch.

## What is being compared

`p_theoretical` is built from `effective_weight_after_malus_and_dumping` — the quantity the election **actually consumes**, after the malus factor and after the dumping function — and is block-weighted across the rounds of the epoch, so an epoch whose weights moved is summarised by what was in force rather than by a snapshot of either end.

`p_hat = O_i / B` is the observed share. The Wilson interval is the 95% score interval around it; it stays inside [0,1] and has sensible width at `O_i = 0`, where the textbook interval collapses to zero.

**Epochs [1] are excluded**: their rounds lie at or below `setup-first-blocks = 220`, where the chain is governed by native MultiChain round robin rather than by wPoA. Testing them would measure the wrong mechanism.

## Per-epoch, per-validator

| epoch | validator | w_final | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---|---:|---:|---:|---:|---:|---|---|
| 2 | `1FeWA69kpmfJ` | 1582800 | 0.7509 | 65 | 100 | 0.6500 | [0.5525, 0.7364] | no |
| 2 | `1HcbmswQDLfh` | 84315 | 0.0425 | 13 | 100 | 0.1300 | [0.0776, 0.2098] | no |
| 2 | `1KbQn4HZLiab` | 267288 | 0.1284 | 15 | 100 | 0.1500 | [0.0931, 0.2328] | yes |
| 2 | `1MikD1pDvprC` | 81487 | 0.0406 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 2 | `1YszMjQTVpHe` | 77256 | 0.0376 | 2 | 100 | 0.0200 | [0.0055, 0.0700] | yes |
| 3 | `1FeWA69kpmfJ` | 1689847 | 0.7343 | 69 | 100 | 0.6900 | [0.5937, 0.7722] | yes |
| 3 | `1HcbmswQDLfh` | 123553 | 0.0526 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 3 | `1KbQn4HZLiab` | 322188 | 0.1389 | 15 | 100 | 0.1500 | [0.0931, 0.2328] | yes |
| 3 | `1MikD1pDvprC` | 100297 | 0.0432 | 6 | 100 | 0.0600 | [0.0278, 0.1248] | yes |
| 3 | `1YszMjQTVpHe` | 70522 | 0.0310 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 4 | `1FeWA69kpmfJ` | 1725603 | 0.7701 | 82 | 100 | 0.8200 | [0.7333, 0.8830] | yes |
| 4 | `1HcbmswQDLfh` | 106477 | 0.0481 | 6 | 100 | 0.0600 | [0.0278, 0.1248] | yes |
| 4 | `1KbQn4HZLiab` | 240241 | 0.1099 | 8 | 100 | 0.0800 | [0.0411, 0.1500] | yes |
| 4 | `1MikD1pDvprC` | 96203 | 0.0431 | 2 | 100 | 0.0200 | [0.0055, 0.0700] | yes |
| 4 | `1YszMjQTVpHe` | 63946 | 0.0288 | 2 | 100 | 0.0200 | [0.0055, 0.0700] | yes |
| 5 | `1FeWA69kpmfJ` | 1659160 | 0.7566 | 78 | 100 | 0.7800 | [0.6893, 0.8500] | yes |
| 5 | `1HcbmswQDLfh` | 111351 | 0.0505 | 7 | 100 | 0.0700 | [0.0343, 0.1375] | yes |
| 5 | `1KbQn4HZLiab` | 244925 | 0.1112 | 8 | 100 | 0.0800 | [0.0411, 0.1500] | yes |
| 5 | `1MikD1pDvprC` | 103050 | 0.0466 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 5 | `1YszMjQTVpHe` | 78013 | 0.0350 | 2 | 100 | 0.0200 | [0.0055, 0.0700] | yes |
| 6 | `1FeWA69kpmfJ` | 1905549 | 0.7388 | 73 | 100 | 0.7300 | [0.6357, 0.8073] | yes |
| 6 | `1HcbmswQDLfh` | 91169 | 0.0364 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 6 | `1KbQn4HZLiab` | 393221 | 0.1493 | 13 | 100 | 0.1300 | [0.0776, 0.2098] | yes |
| 6 | `1MikD1pDvprC` | 110585 | 0.0431 | 3 | 100 | 0.0300 | [0.0103, 0.0845] | yes |
| 6 | `1YszMjQTVpHe` | 83147 | 0.0324 | 6 | 100 | 0.0600 | [0.0278, 0.1248] | yes |
| 7 | `1FeWA69kpmfJ` | 1881475 | 0.7616 | 68 | 100 | 0.6800 | [0.5834, 0.7633] | yes |
| 7 | `1HcbmswQDLfh` | 131945 | 0.0523 | 13 | 100 | 0.1300 | [0.0776, 0.2098] | no |
| 7 | `1KbQn4HZLiab` | 261876 | 0.1095 | 10 | 100 | 0.1000 | [0.0552, 0.1744] | yes |
| 7 | `1MikD1pDvprC` | 118914 | 0.0479 | 6 | 100 | 0.0600 | [0.0278, 0.1248] | yes |
| 7 | `1YszMjQTVpHe` | 70256 | 0.0288 | 3 | 100 | 0.0300 | [0.0103, 0.0845] | yes |
| 8 | `1FeWA69kpmfJ` | 1756444 | 0.7417 | 69 | 100 | 0.6900 | [0.5937, 0.7722] | yes |
| 8 | `1HcbmswQDLfh` | 121964 | 0.0515 | 6 | 100 | 0.0600 | [0.0278, 0.1248] | yes |
| 8 | `1KbQn4HZLiab` | 323484 | 0.1342 | 13 | 100 | 0.1300 | [0.0776, 0.2098] | yes |
| 8 | `1MikD1pDvprC` | 97417 | 0.0416 | 8 | 100 | 0.0800 | [0.0411, 0.1500] | yes |
| 8 | `1YszMjQTVpHe` | 73938 | 0.0310 | 4 | 100 | 0.0400 | [0.0157, 0.0984] | yes |
| 9 | `1FeWA69kpmfJ` | 1794507 | 0.7583 | 79 | 100 | 0.7900 | [0.7002, 0.8583] | yes |
| 9 | `1HcbmswQDLfh` | 101490 | 0.0436 | 1 | 100 | 0.0100 | [0.0018, 0.0545] | yes |
| 9 | `1KbQn4HZLiab` | 249377 | 0.1077 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 9 | `1MikD1pDvprC` | 112981 | 0.0474 | 3 | 100 | 0.0300 | [0.0103, 0.0845] | yes |
| 9 | `1YszMjQTVpHe` | 103757 | 0.0430 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 10 | `1FeWA69kpmfJ` | 1715851 | 0.7721 | 75 | 100 | 0.7500 | [0.6570, 0.8245] | yes |
| 10 | `1HcbmswQDLfh` | 88127 | 0.0399 | 1 | 100 | 0.0100 | [0.0018, 0.0545] | yes |
| 10 | `1KbQn4HZLiab` | 229503 | 0.1036 | 13 | 100 | 0.1300 | [0.0776, 0.2098] | yes |
| 10 | `1MikD1pDvprC` | 101837 | 0.0460 | 6 | 100 | 0.0600 | [0.0278, 0.1248] | yes |
| 10 | `1YszMjQTVpHe` | 84283 | 0.0384 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 11 | `1FeWA69kpmfJ` | 1697792 | 0.7471 | 78 | 100 | 0.7800 | [0.6893, 0.8500] | yes |
| 11 | `1HcbmswQDLfh` | 106747 | 0.0463 | 4 | 100 | 0.0400 | [0.0157, 0.0984] | yes |
| 11 | `1KbQn4HZLiab` | 254718 | 0.1112 | 7 | 100 | 0.0700 | [0.0343, 0.1375] | yes |
| 11 | `1MikD1pDvprC` | 125677 | 0.0545 | 7 | 100 | 0.0700 | [0.0343, 0.1375] | yes |
| 11 | `1YszMjQTVpHe` | 93616 | 0.0409 | 4 | 100 | 0.0400 | [0.0157, 0.0984] | yes |
| 12 | `1FeWA69kpmfJ` | 1694657 | 0.7537 | 79 | 100 | 0.7900 | [0.7002, 0.8583] | yes |
| 12 | `1HcbmswQDLfh` | 113992 | 0.0505 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 12 | `1KbQn4HZLiab` | 287672 | 0.1269 | 12 | 100 | 0.1200 | [0.0700, 0.1981] | yes |
| 12 | `1MikD1pDvprC` | 76414 | 0.0355 | 2 | 100 | 0.0200 | [0.0055, 0.0700] | yes |
| 12 | `1YszMjQTVpHe` | 73851 | 0.0334 | 2 | 100 | 0.0200 | [0.0055, 0.0700] | yes |
| 13 | `1FeWA69kpmfJ` | 1587565 | 0.7382 | 72 | 100 | 0.7200 | [0.6251, 0.7986] | yes |
| 13 | `1HcbmswQDLfh` | 108020 | 0.0502 | 3 | 100 | 0.0300 | [0.0103, 0.0845] | yes |
| 13 | `1KbQn4HZLiab` | 280255 | 0.1300 | 20 | 100 | 0.2000 | [0.1334, 0.2888] | no |
| 13 | `1MikD1pDvprC` | 99727 | 0.0454 | 3 | 100 | 0.0300 | [0.0103, 0.0845] | yes |
| 13 | `1YszMjQTVpHe` | 78659 | 0.0363 | 2 | 100 | 0.0200 | [0.0055, 0.0700] | yes |
| 14 | `1FeWA69kpmfJ` | 1765012 | 0.7438 | 78 | 100 | 0.7800 | [0.6893, 0.8500] | yes |
| 14 | `1HcbmswQDLfh` | 113934 | 0.0482 | 2 | 100 | 0.0200 | [0.0055, 0.0700] | yes |
| 14 | `1KbQn4HZLiab` | 290393 | 0.1230 | 14 | 100 | 0.1400 | [0.0853, 0.2214] | yes |
| 14 | `1MikD1pDvprC` | 120377 | 0.0505 | 6 | 100 | 0.0600 | [0.0278, 0.1248] | yes |
| 14 | `1YszMjQTVpHe` | 81625 | 0.0346 | 0 | 100 | 0.0000 | [0.0000, 0.0370] | yes |
| 15 | `1FeWA69kpmfJ` | 1761433 | 0.7289 | 79 | 100 | 0.7900 | [0.7002, 0.8583] | yes |
| 15 | `1HcbmswQDLfh` | 128295 | 0.0527 | 5 | 100 | 0.0500 | [0.0215, 0.1118] | yes |
| 15 | `1KbQn4HZLiab` | 326054 | 0.1339 | 10 | 100 | 0.1000 | [0.0552, 0.1744] | yes |
| 15 | `1MikD1pDvprC` | 117825 | 0.0488 | 6 | 100 | 0.0600 | [0.0278, 0.1248] | yes |
| 15 | `1YszMjQTVpHe` | 86723 | 0.0357 | 0 | 100 | 0.0000 | [0.0000, 0.0370] | yes |
| 16 | `1FeWA69kpmfJ` | 1722359 | 0.7441 | 19 | 26 | 0.7308 | [0.5392, 0.8630] | yes |
| 16 | `1HcbmswQDLfh` | 104887 | 0.0476 | 1 | 26 | 0.0385 | [0.0068, 0.1889] | yes |
| 16 | `1KbQn4HZLiab` | 302216 | 0.1324 | 6 | 26 | 0.2308 | [0.1103, 0.4205] | yes |
| 16 | `1MikD1pDvprC` | 92738 | 0.0425 | 0 | 26 | 0.0000 | [0.0000, 0.1287] | yes |
| 16 | `1YszMjQTVpHe` | 74996 | 0.0335 | 0 | 26 | 0.0000 | [0.0000, 0.1287] | yes |

## Pooled over every measured epoch

| validator | p_theoretical | O_i | B | p_hat | Wilson 95% | inside? |
|---|---:|---:|---:|---:|---|---|
| `1FeWA69kpmfJ` | 0.7496 | 1063 | 1426 | 0.7454 | [0.7222, 0.7674] | yes |
| `1HcbmswQDLfh` | 0.0475 | 77 | 1426 | 0.0540 | [0.0434, 0.0670] | yes |
| `1KbQn4HZLiab` | 0.1229 | 176 | 1426 | 0.1234 | [0.1074, 0.1415] | yes |
| `1MikD1pDvprC` | 0.0452 | 68 | 1426 | 0.0477 | [0.0378, 0.0600] | yes |
| `1YszMjQTVpHe` | 0.0348 | 42 | 1426 | 0.0295 | [0.0219, 0.0396] | yes |

## Joint test per epoch (chi-square / exact / Monte Carlo)

| epoch | blocks | validators | method | statistic | p | reject at 0.05 | TV | round-by-round p |
|---|---:|---:|---|---:|---:|---|---:|---:|
| 2 | 100 | 5 | monte_carlo_multinomial | 20.735 | 0.0012 | YES | 0.1184 | 0.0012 |
| 3 | 100 | 5 | monte_carlo_multinomial | 2.188 | 0.6948 | no | 0.0470 | 0.6982 |
| 4 | 100 | 5 | monte_carlo_multinomial | 2.936 | 0.5632 | no | 0.0618 | 0.5627 |
| 5 | 100 | 5 | monte_carlo_multinomial | 2.373 | 0.6677 | no | 0.0463 | 0.6659 |
| 6 | 100 | 5 | monte_carlo_multinomial | 3.517 | 0.4687 | no | 0.0412 | 0.4673 |
| 7 | 100 | 5 | monte_carlo_multinomial | 12.833 | 0.0143 | YES | 0.0911 | 0.0165 |
| 8 | 100 | 5 | monte_carlo_multinomial | 4.334 | 0.3465 | no | 0.0559 | 0.3510 |
| 9 | 100 | 5 | monte_carlo_multinomial | 3.606 | 0.4552 | no | 0.0509 | 0.4580 |
| 10 | 100 | 5 | monte_carlo_multinomial | 3.759 | 0.4296 | no | 0.0520 | 0.4306 |
| 11 | 100 | 5 | monte_carlo_multinomial | 2.201 | 0.6934 | no | 0.0484 | 0.6897 |
| 12 | 100 | 5 | monte_carlo_multinomial | 1.430 | 0.8434 | no | 0.0363 | 0.8395 |
| 13 | 100 | 5 | monte_carlo_multinomial | 5.886 | 0.1960 | no | 0.0700 | 0.1996 |
| 14 | 100 | 5 | monte_carlo_multinomial | 5.698 | 0.2122 | no | 0.0628 | 0.2166 |
| 15 | 100 | 5 | monte_carlo_multinomial | 5.210 | 0.2516 | no | 0.0722 | 0.2574 |
| 16 | 26 | 5 | monte_carlo_multinomial | 3.929 | 0.3699 | no | 0.0984 | 0.3759 |
| all | 1426 | 5 | chi2_asymptotic | 2.635 | 0.6206 | no | 0.0095 | 0.8190 |

## How to read this

- **The interval, not the point.** A `p_hat` far from `p_theoretical` means nothing if the interval is wide; with a handful of blocks per epoch it usually is. The mean interval width here is **0.1103**, which is the resolution of this run.
- **Multiple comparisons.** 4 of 75 intervals excluded the entitled share; about 3.8 are expected to by chance alone at alpha = 0.05. Only a count well above the expectation is a finding.
- **The joint test is the real one.** The per-validator intervals say *which* validator is out of line; the chi-square says whether the epoch as a whole is distinguishable from weighted sortition.
- **Round-by-round when the shares moved.** Where an epoch's shares changed mid-epoch, the pooled multinomial tests a null that was never in force, and the round-by-round Monte-Carlo p-value in the last column is the one to read.

The corresponding figure is `plots/weight_vs_election.png`, produced by `plotting/generate_plots.py`.
