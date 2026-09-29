# Controlled experiment on rho

> Some miners were given their own restitution behaviour (`traffic.miner_return_overrides`). The question is whether the restitution rate rho reaches the weight and, through it, the election. Each round is tested against two nulls: the shares **with** the rho feedback (the weights the election actually consumed) and the same weights with the feedback factor `lambda * rho_prev + (1 - lambda)` removed, i.e. what the engine would have published with `lambda = 0` and everything else unchanged.

**Causal lag.** Engine epoch *k* reads the blocks of block-epoch *k - 1* and is in force from early in block-epoch *k*; its factor uses rho of engine epoch *k - 1*, i.e. the restitutions of block-epoch *k - 2*. A round's *treated phase* is the restitution phase of that block-epoch, traced from the engine row its weight came from. 2900 round(s) measured, 1 dropped because some weight could not be traced.

## Overrides in this run

| miner | from epoch | returns per epoch | amount |
|---|---:|---|---|
| miner-1 | 1 | [16, 20] | [200.0, 250.0] |
| miner-1 | 15 | [0, 2] | [50.0, 100.0] |
| miner-3 | 1 | [0, 2] | [50.0, 100.0] |
| miner-3 | 15 | [16, 20] | [200.0, 250.0] |

## Likelihood ratio: feedback against no feedback

`LLR = sum over rounds of log(p_with[winner] / p_without[winner])`, the most powerful test between the two nulls (Neyman-Pearson). Both are simulated round by round with the shares in force (20000 draws).

| quantity | value |
|---|---:|
| rounds | 2900 |
| LLR observed | 207.83 |
| LLR under no feedback: mean | -222.69 |
| LLR under no feedback: sd | 21.56 |
| p-value of 'rho has no effect' | 0.000050 |
| distance from the no-feedback null, in sd | 20.0 |
| LLR under feedback: mean | 211.26 |
| LLR under feedback: sd | 19.73 |
| quantile of the observation under feedback | 0.432 |

## Joint test on totals, round by round (Monte-Carlo, 20000 draws)

| scope | null | rounds | chi-square | df | p | reject at 0.05 |
|---|---|---:|---:|---:|---:|---|
| all rounds | with rho feedback | 2900 | 1.61 | 4 | 0.7993 | no |
| all rounds | without rho feedback | 2900 | 25.13 | 4 | 0.0002 | YES |
| period 1 (miner-1 phase 0, miner-3 phase 0) | with rho feedback | 86 | 1.56 | 4 | 0.8209 | no |
| period 1 (miner-1 phase 0, miner-3 phase 0) | without rho feedback | 86 | 1.56 | 4 | 0.8209 | no |
| period 2 (miner-1 phase 1, miner-3 phase 1) | with rho feedback | 1400 | 1.78 | 4 | 0.7754 | no |
| period 2 (miner-1 phase 1, miner-3 phase 1) | without rho feedback | 1400 | 171.55 | 4 | 0.0001 | YES |
| period 3 (miner-1 phase 2, miner-3 phase 2) | with rho feedback | 1414 | 1.49 | 4 | 0.8283 | no |
| period 3 (miner-1 phase 2, miner-3 phase 2) | without rho feedback | 1414 | 152.21 | 4 | 0.0001 | YES |

## Share per miner and treated phase

| miner | phase | rounds | rho in force | factor | p without feedback | p with feedback | observed | Wilson 95% | z vs with | z vs without |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| miner-0 | 0 | 2900 | 0.0086 | 0.0186 | 0.0953 | 0.0882 | 0.0897 | [0.0798, 0.1006] | 0.27 | -1.04 |
| miner-1 | 0 | 86 | 0.0000 | 0.0100 | 0.1839 | 0.1839 | 0.2209 | [0.1462, 0.3195] | 0.89 | 0.89 |
| miner-1 | 1 | 1400 | 0.0219 | 0.0317 | 0.1678 | 0.2725 | 0.2807 | [0.2578, 0.3048] | 0.70 | 11.32 |
| miner-1 | 2 | 1414 | 0.0010 | 0.0110 | 0.1374 | 0.0726 | 0.0771 | [0.0643, 0.0922] | 0.65 | -6.59 |
| miner-2 | 0 | 2900 | 0.0097 | 0.0196 | 0.2718 | 0.2651 | 0.2576 | [0.2420, 0.2738] | -0.93 | -1.72 |
| miner-3 | 0 | 86 | 0.0000 | 0.0100 | 0.2272 | 0.2272 | 0.2326 | [0.1559, 0.3321] | 0.12 | 0.12 |
| miner-3 | 1 | 1400 | 0.0002 | 0.0102 | 0.2112 | 0.1106 | 0.1143 | [0.0987, 0.1320] | 0.44 | -8.89 |
| miner-3 | 2 | 1414 | 0.0229 | 0.0327 | 0.2400 | 0.3757 | 0.3685 | [0.3437, 0.3939] | -0.56 | 11.33 |
| miner-4 | 0 | 2900 | 0.0082 | 0.0181 | 0.2537 | 0.2309 | 0.2314 | [0.2164, 0.2471] | 0.06 | -2.77 |

## Within-miner change between phases

Same miner before and after its switch, so ESG and cluster size cancel. The observed change is compared with the change each null predicts.

| miner | phases | observed change | predicted with feedback | predicted without | z vs with | z vs without |
|---|---|---:|---:|---:|---:|---:|
| miner-1 | 0 → 1 | 0.0598 | 0.0886 | -0.0162 | -0.66 | 1.77 |
| miner-1 | 1 → 2 | -0.2036 | -0.1999 | -0.0304 | -0.27 | -12.80 |
| miner-3 | 0 → 1 | -0.1183 | -0.1166 | -0.0160 | -0.04 | -2.20 |
| miner-3 | 1 → 2 | 0.2542 | 0.2651 | 0.0288 | -0.71 | 14.33 |

## How to read this

- **The feedback works** if the winners are consistent with the null *with* feedback and inconsistent with the null *without* it, and if each switching miner's share moves by the amount the feedback predicts.
- **The counterfactual keeps everything but rho**: same ESG, same tau, same malus and dumping. Only the factor that rho sets is removed.

Figures: `plots/rho_effect_weight.png`, `plots/rho_effect_election.png`.
