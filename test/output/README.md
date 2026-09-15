# Recorded runs and their analysis

Each functional run that records itself writes one directory here:

```
test/output/<experiment-name>/
├── report.md          ← the readable report: start here
├── summary.txt        ← the same verdicts, plain text, greppable
│
├── meta.json          the run's parameters and timestamps
├── proposers.csv      height, miner — one row per block
├── weights.csv        epoch, address, weight — the whole map, per epoch
├── epochs.csv         epoch, height, verified_epoch, mismatch, not_a_cluster, other_epoch, refuels
├── gas.csv            epoch, node, role, balance — every node, per epoch
├── refuels.csv        epoch, node, role, before, after, amount, txid
│
├── montecarlo.csv     one row per scenario per candidate: expected vs observed
├── distribution.csv   per validator: weight, share, expected, observed, deviation, 95% CI
├── concentration.csv  Gini / normalised entropy / max share, for weights and for proposals
├── epoch_stats.csv    per-epoch aggregates incl. weight dispersion (CV, Gini)
└── gas_stats.csv      per-node balance trajectory: first/last/min/mean/sd, refuels, ran-dry
```

The first six are **raw observations**, streamed out during the run. The last five are
**derived** by [`../functional/lib/we_stats.py`](../functional/lib/we_stats.py), which can
be re-run over the raw files at any time without touching the network:

```bash
python3 test/functional/lib/we_stats.py test/output/<experiment-name>
python3 test/functional/lib/we_stats.py test/output/<experiment-name> --draws 500000
python3 test/functional/lib/we_stats.py test/output/<experiment-name> --alpha 0.05
```

Recording happens **during** the drive loop, not at the end: a run that stalls at epoch 12
still leaves twelve epochs of evidence, which is the case where the evidence matters most.

## What is tracked in git

Nothing but this file and `.gitignore`. A 50-epoch run writes ~200 KB of `proposers.csv`
alone, a fresh run supersedes the last, and the analysis is reproducible from the raw
files — so the data is local. Keep a run you care about by copying it elsewhere, or by
committing it deliberately with `git add -f`.

## The two election tests, and why there are two

`report.md` reports a Monte Carlo test **and** an empirical chi-square. They answer
different questions and neither is sufficient alone:

| | Monte Carlo | Empirical chi-square |
|---|---|---|
| Question | is the **formula** right? | did **this binary**, on **this run**, elect in proportion to weight? |
| What it exercises | `ScoreFromEntropy64` / `ApplyDumping`, re-implemented in Python | the compiled selector, the VRF, the beacon and the weight pipeline end to end |
| Sample size | a parameter (`--draws`) | however many blocks the run mined |
| Blind spot | not running the C++ | no power in the tail: a 0.1 %-weight validator expects ~5 blocks in 5000 |

Reading them **together** is what localises a fault:

| Monte Carlo | Empirical | Reading |
|---|---|---|
| PASS | PASS | pipeline sound at both layers |
| PASS | **FAIL** | the design is right, the **implementation** is not |
| **FAIL** | either | the formula itself is wrong — fix that before reading anything else |

The 64-bit entropy in the Monte Carlo comes from `random.getrandbits(64)` rather than a
VRF. That is the intended test, not a shortcut: Prop. 5.11 requires the VRF to be
indistinguishable from uniform, so substituting a uniform source tests the algorithm
*above* the randomness source.

## Reading the numbers

- **p-value** — the probability of a deviation at least this large if the null
  (`Pr[i elected] = w_i / W_tot`, Teor. 5.3) holds. Below `--alpha` (default 0.01)
  rejects it. A *high* p is not evidence of correctness, only absence of evidence
  against.
- **Classes dropped** — validators whose expectation fell below 5 are excluded from the
  chi-square, because the approximation does not hold there. The count is printed so the
  test's real power is visible rather than implied.
- **Zero-weight picks** — must be exactly 0 (Cor. 5.4). The score returns `+inf` before
  any division, so a single selection would mean a structural guarantee had quietly
  become a probabilistic one.
- **Gini / entropy** — descriptive, **not** verdicts. Under weighted selection the target
  is not uniformity, so a Gini above 0 is correct. What is worth watching is the *gap*
  between the weights row and the proposals row: proposals markedly more concentrated
  than weights would suggest the selector is amplifying.
- **Weight CV across epochs** — if it sits flat at 0 for the whole run, the restitution
  feedback never moved. Usually that means the native currency is not actually enabled,
  in which case `R_k` is 0 everywhere, `rho` is pinned at 0, and the run proved nothing
  about the feedback no matter how many epochs it covered.

## Validating the statistics themselves

The machinery has its own self-check — chi-square p-values against textbook critical
values, Gini and entropy against closed forms, Cor. 5.4, and a **negative control** that
confirms a deliberately unweighted draw is rejected:

```bash
python3 test/functional/lib/we_stats.py --selfcheck
./test/functional/run_functional_tests.sh --suite stats-selfcheck
```

It needs no node, which makes it the one suite here that runs on a host where
`multichaind` does not build.
