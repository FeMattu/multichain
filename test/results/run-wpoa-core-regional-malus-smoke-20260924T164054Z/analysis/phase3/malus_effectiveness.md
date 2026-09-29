# Malicious miners and the behavioural malus

> Two of the four malus kinds are implementable from outside the node and are the ones exercised here: **selfwrite** (a record on a self-attested stream naming another node) and **badweight** (a self-published weight that fails recomputation). `delay` and `equiv` require the consensus core and are out of scope. The other two attacks are produced by real transactions and detected, independently, by an honest node's own `reportmalus` predicate.

**Three states, kept distinct throughout:** an action is *attempted* when the injector's controller decides to act, *confirmed* when its transaction reaches a block, and a *valid malus* only when an honest node accepts the evidence and publishes a report. Precision and recall below use **confirmed** actions as the positive class.

## Selection and target rate

| miner | target rate | opportunities | attempted | attempted rate | 95% CI | on target |
|---|---:|---:|---:|---:|---|---|
| `miner-2` | 0.867 | 8 | 7 | 0.875 | [0.529, 0.978] | yes |
| `miner-3` | 0.733 | 8 | 6 | 0.750 | [0.409, 0.929] | yes |

Aggregate: target **0.800**, realised (attempted) **0.812** over 16 opportunities (95% CI [0.570, 0.934]; on target: yes).

## Funnel: opportunity → attempt → sent → confirmed → valid malus

| scope | opportunities | attempts | sent | confirmed | valid malus |
|---|---:|---:|---:|---:|---:|
| all | 16 | 13 | 11 | 11 | 11 |
| selfwrite | - | 2 | 0 | 0 | 0 |
| badweight | - | 11 | 11 | 11 | 11 |

## Detection quality

| kind | TP | FP | FN | precision | recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| all | 11 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| selfwrite | 0 | 0 | 0 | - | - | - |
| badweight | 11 | 0 | 0 | 1.000 | 1.000 | 1.000 |

A false positive is a report against a record that was **not** a confirmed malicious action; the mechanism's safety property is that this count is zero.

## Latency

| measure | n | mean | median | p25 | p75 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| detection_latency_blocks | 11 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| activation_latency_epochs | 11 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| detection_latency_blocks_selfwrite | 0 | - | - | - | - | - | - |
| detection_latency_blocks_badweight | 11 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

Detection latency is in **blocks**, from the offending transaction's confirmation to the first report of it. Activation latency is in **epochs**: a proved malus is folded at the offence's epoch and governs selection from the epoch after, so a value of 1 is the protocol minimum.

## Effective-weight effect, matched by initial-weight band

| band | n malicious | n honest | median Δw_eff (malicious) | median Δw_eff (honest) | difference |
|---|---:|---:|---:|---:|---:|
| low | 0 | 2 | - | -0.725 | - |
| mid | 1 | 1 | -0.556 | -0.900 | 0.344 |
| high | 1 | 0 | -0.909 | - | - |

The comparison is within an initial-weight band, so it reads as "penalised nodes moved relative to comparable unpenalised ones" rather than as a bare before/after. No causal claim is made from an ESG or activity difference alone.

## Invariant audit

- Psi outside [0,1]: **0**
- w_eff disagreeing with the recomputation: **0**
- a clean validator (M = 0) with Psi != 1: **0**

The figure `plots/malus_invariant_audit.png` shows the per-(epoch, validator) grid these counts come from.
