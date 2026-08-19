# Native MultiChain PoA — Block-Creation Delay: Formula, Convergence, Edge Cases

> **Registro: tecnico-diretto.** Trascrizione e analisi del codice di temporizzazione
> nativo. Le sezioni 3 e 4 (convergenza, legge dei grandi numeri) adottano un registro
> più formale, come esplicitato al loro inizio.
>
> **Criterio di riferimento al codice.** Questo documento cita il codice per **simbolo**
> (funzione, variabile) e non per numero di riga: gli ancoraggi di riga si degradano a
> ogni modifica del sorgente, e in una precedente revisione erano scivolati di 30–90
> righe, puntando a graffe chiuse e righe vuote. Il punto d'ingresso di tutto ciò che
> segue è **`GetMinerAndExpectedMiningStartTime()`** in
> [`miner/miner.cpp`](../../miner/miner.cpp).

This documents the **native** (pre-wPoA) MultiChain Proof-of-Authority block-creation
delay — the round-robin / mining-diversity timing gate that wPoA Phase 2 *replaces* for
a weighted election (see the `/* MCHN START - wPoA Phase 2 */` comment at
[`miner/miner.cpp:1184-1185`](../../miner/miner.cpp): *"Replace the
round-robin mining-diversity timing gate with a weighted election..."*). It is the
baseline the wPoA delay formula (`docs/phase4-implementation-guide.md` §4,
the banded `D = T + δ·T·(2·score_norm − 1) + λ·Φ`, see
[protocol-parameters.md §2.1](protocol-parameters.md#21-il-ritardo-di-mining-della-fase-4))
was built to supersede, and is still the code path
taken whenever wPoA is disabled (`-enablewpoa=0`, the default).

---

## Indice

- [1. Where it lives](#1-where-it-lives)
- [2. The formula, transcribed from the code](#2-the-formula-transcribed-from-the-code)
  - [2.1 Constants ([miner.cpp](../../miner/miner.cpp))](#21-constants-minercpp)
  - [2.2 Target-time anchor ([miner.cpp](../../miner/miner.cpp))](#22-target-time-anchor-minercpp)
  - [2.3 Pool sizing and membership ([miner.cpp](../../miner/miner.cpp))](#23-pool-sizing-and-membership-minercpp)
  - [2.4 Active-miner estimate and pool admission ([miner.cpp](../../miner/miner.cpp))](#24-active-miner-estimate-and-pool-admission-minercpp)
  - [2.5 Start-time assignment ([miner.cpp](../../miner/miner.cpp))](#25-start-time-assignment-minercpp)
- [3. Relationship between the per-proposer delay, n, and T](#3-relationship-between-the-per-proposer-delay-n-and-t)
- [4. Law of Large Numbers: empirical block time → T](#4-law-of-large-numbers-empirical-block-time--t)
- [5. Edge cases and their effect on convergence](#5-edge-cases-and-their-effect-on-convergence)
- [6. Summary](#6-summary)

---
## 1. Where it lives

| Symbol | File : line | Role |
|---|---|---|
| `GetMinerAndExpectedMiningStartTime()` | [`miner/miner.cpp:1040`](../../miner/miner.cpp) | The whole delay computation; called once per new tip from the miner thread, cached until the tip or mempool changes. |
| Native (non-wPoA) branch | [`miner/miner.cpp:1240-1434`](../../miner/miner.cpp) | The round-robin diversity + emergency-miner backoff math analyzed below. |
| `LastActiveMiners()` | [`miner/miner.cpp:956-1019`](../../miner/miner.cpp) | Scans back over the recent chain to find the set of distinct miners who have proposed recently (the "pool"). |
| `Params().TargetSpacing()` | [`chainparams/chainparams.h:79`](../../chainparams/chainparams.h) | `T`, the configured target block time, backed by the `targetblocktime` chain parameter ([`chainparams/paramlist.h:29-30`](../../chainparams/paramlist.h), default 15s). |
| `Params().MiningTurnover()` | [`chainparams/chainparams.h:67`](../../chainparams/chainparams.h) | The `miningturnover` parameter — fraction of active miners rotated into the pool each round. |
| `GetMaxActiveMinersCount()` | [`miner/miner.cpp:1021-1038`](../../miner/miner.cpp) | `n`, the number of currently-permissioned active miners (`CPermissions::GetActiveMinerCount()`), or effectively unbounded if `-anyonecanmine`. |
| `mc_gState->m_Permissions->GetMinerCount()` / `GetActiveMinerCount()` | [`permissions/permission.h:349-350`](../../permissions/permission.h) | Total permissioned miners vs. those flagged *active* (recently seen mining). |

---

## 2. The formula, transcribed from the code

For the block that follows tip `pindexTip` (protocol = MultiChain, `-anyonecanmine=0`,
the ordinary PoA configuration):

### 2.1 Constants ([`miner.cpp`](../../miner/miner.cpp))

```
nMinerPoolSizeMin = 4              nMinerPoolSizeMax = 16
dRelativeSpread   = 1.0            dRelativeMinerPoolSize = 0.25
dAverageCreateBlockTime = 2s       (bumped up to the measured wAvBlockTime if larger)
dEmergencyMinersConvergenceRate = 2.0
nPastBlocks = 12
```

### 2.2 Target-time anchor ([`miner.cpp`](../../miner/miner.cpp))

```
T           = Params().TargetSpacing()                       // target-block-time
dSpread     = T                                               // ± scheduling window
dExpectedTimeByLast = parent.dTimeReceived + T
dExpectedTimeByPast = mean(last ≤12 inter-arrival times) + (windowSize+1)/2 · T
dExpectedTime       = clamp(dExpectedTimeByPast, dExpectedTimeByLast ± T/2)   // homeostat
```

`dExpectedTimeByPast` is a feedback term: it averages the *actual* observed gaps over
the last `nPastBlocks` blocks and re-centers on `T` via the additive `(windowSize+1)/2·T`
term, then the result is clamped back into a `±T/2` band around `parent+T`. This is the
mechanism that pulls the empirical cadence back toward `T` whenever it drifts (§4).

### 2.3 Pool sizing and membership ([`miner.cpp`](../../miner/miner.cpp))

```
nStdMinerPoolSize = clamp( round(0.25 · T / dAverageCreateBlockTime), [4, 16] )
nStdMinerPoolSize = round(dMinerDrift · nStdMinerPoolSize) + 1     // dMinerDrift = MiningTurnover(), ∈[0,1]
sThisMinerPool    = LastActiveMiners(pindexTip, nStdMinerPoolSize)  // ≤ nStdMinerPoolSize distinct recent miners
nMinerPoolSize    = |sThisMinerPool|
```

`LastActiveMiners` ([`miner.cpp`](../../miner/miner.cpp)) walks
`nWindowSize = 5·nMinerPoolSize + nDiversityMiners` blocks back from the tip collecting
distinct signer pubkeys, where `nDiversityMiners = nTotalMiners - nActiveMiners`
([`miner.cpp`](../../miner/miner.cpp)) — the count of permissioned-but-
currently-inactive miners, which widens the lookback window when many miners are offline
(edge case, §5).

### 2.4 Active-miner estimate and pool admission ([`miner.cpp`](../../miner/miner.cpp))

```
if (fInMinerPool) OR (kLastMiner not in previous pool) OR (n̂ uninitialized):
    n̂ = (n - nMinerPoolSize) / dMinerDrift          // n = GetMaxActiveMinersCount()
n̂ *= (1 - dMinerDrift)                              // exponential decay per round
n̂ = max(n̂, 1)

if !fInMinerPool and dMinerDrift ≥ ε:
    with prob. dMinerDrift / n̂ :  fInMinerPool = true,  nMinerPoolSize += 1   // random "catch-up" admission
```

### 2.5 Start-time assignment ([`miner.cpp`](../../miner/miner.cpp))

```
if fInMinerPool:                                           // this node just rotated into the pool
    start = dExpectedTime + U·T − T/(nMinerPoolSize+1)      // U ~ Uniform(0,1), fresh draw each round
else:                                                       // "cooled down" — waits for a catch-up slot
    start = dExpectedTimeMax + T − T/(nMinerPoolSize+1)
            + dAverageCreateBlockTime · (1 + U)
    dEmergencyMiners = n
    while dEmergencyMiners > 0.5 and U' > 1/dEmergencyMiners:      // geometric backoff, fresh U' each iteration
        start += dAverageCreateBlockTime
        dEmergencyMiners /= 2
```

---

## 3. Relationship between the per-proposer delay, `n`, and `T`

Two regimes coexist, both anchored on `T` but scaled differently by `n`:

**In-pool proposers** (the ordinary case — a node whose address just rotated into
`sThisMinerPool`): the start time is `dExpectedTime` (which tracks `parent + T`) plus an
independent draw `U·T` shifted by `-T/(m+1)`, where `m = nMinerPoolSize`. Writing
`Δ_pool` for the *offset from the anchor*:

$$
\Delta_{\text{pool}} \;=\; U\cdot T \;-\; \frac{T}{m+1}, \qquad U\sim\mathrm{Unif}(0,1)
$$

$$
\mathbb E[\Delta_{\text{pool}}] \;=\; \frac{T}{2}-\frac{T}{m+1}
\xrightarrow[m\to\infty]{} \frac{T}{2},
\qquad
\mathrm{Var}(\Delta_{\text{pool}}) = \frac{T^{2}}{12}
$$

so each of the `m` pool members independently draws a start time uniformly spread across
a window of width `T` centered near `parent+T` — a **randomized** round-robin (the
"priority shuffling" of §5) rather than fixed equal slots, whose per-member expectation
is nudged toward `1/(m+1)` fractions of `T` by the subtracted term.

**Out-of-pool (cooled-down) proposers** wait an extra, `n`-dependent term. The `while`
loop is a geometric backoff: at each iteration the probability of *stopping* (not adding
another `dAverageCreateBlockTime`) is `1/\hat n_k` where `\hat n_k = n/2^{k}` after `k`
iterations. Let `K` = number of loop iterations before it stops. Then

$$
\Pr[K \ge k] \;=\; \prod_{j=0}^{k-1}\Big(1-\frac{1}{n/2^{j}}\Big),
\qquad
\mathbb E[\text{extra delay}] \;=\; \text{dAverageCreateBlockTime}\cdot \mathbb E[K]
$$

Because the "stopping probability" `1/\hat n_k` doubles every iteration (`\hat n_k`
halves), `\mathbb E[K] = O(\log_2 n)`: the more permissioned miners exist, the longer a
cooled-down miner's expected catch-up backoff, `\Theta(\log n)` block-times — this is
what prevents every previously-active miner from re-attempting simultaneously once the
in-pool slot passes.

So, informally:

$$
\text{delay}(i) \;=\;
\begin{cases}
T + O(T) & i \in \text{pool (fresh rotation)}\\[4pt]
2T + \Theta(\log_2 n)\cdot \text{dAverageCreateBlockTime} + O(T) & i \notin \text{pool}
\end{cases}
$$

and because exactly the pool path is what produces the *accepted* next block in the
common case (the out-of-pool path only fires when the in-pool candidates fail to
produce a block — see §5), **the target-block-time `T` is the mean of the accepted
inter-block gap**, with `n` entering only as the (logarithmic) size of the liveness
fallback, not the steady-state mean.

---

## 4. Law of Large Numbers: empirical block time → `T`

Let `G_k = t_k - t_{k-1}` be the observed gap between block `k-1` and block `k`'s
`nTime`/arrival. From §2.2–§2.5, `G_k` is generated from:

1. an **anchor** `dExpectedTime_k` that the feedback term
   `dExpectedTimeByPast` (mean of the last 12 gaps, re-centered by `+(w+1)/2·T`, clamped
   to `parent+T ± T/2`) pulls toward `T` whenever the realized average departs from it
   — i.e. `dExpectedTime_k` is itself a *bounded, self-correcting* estimator of `T`, not
   a free-running one;
2. a **bounded random offset** (`U·T` term, or the geometric-backoff extra delay in the
   rare stand-in case), drawn fresh (new calls to `mc_RandomDouble()`) each round,
   independent of the offsets used in blocks more than `nPastBlocks = 12` back.

Because each `G_k` depends only on a **bounded lookback window** (12 blocks) of past
gaps plus *fresh, mutually independent* randomness at round `k`, the sequence
`{G_k}_{k\ge1}` is a stationary, `12`-dependent (`m`-dependent) stochastic process with
finite mean `\mu = T` (by construction of the anchor, §2.2) and finite variance
(`\mathrm{Var}(\Delta_{\text{pool}}) = T^2/12`, finite; the rare emergency-backoff tail is
geometrically bounded, so its contribution to the variance is also finite).

`m`-dependent stationary sequences with finite variance are **ergodic** and satisfy the
strong Law of Large Numbers for stationary ergodic processes (a direct generalization of
Kolmogorov's SLLN for i.i.d. sequences — see e.g. Birkhoff's ergodic theorem applied to
the shift on the join of the finite-window state and the i.i.d. randomness stream). Hence:

$$
\bar G_N \;=\; \frac{1}{N}\sum_{k=1}^{N} G_k \;\xrightarrow[N\to\infty]{\text{a.s.}}\; \mathbb E[G] \;=\; T
$$

and, since the `G_k` are only short-range (12-block) dependent, a CLT for `m`-dependent
sequences gives the finite-`N` fluctuation

$$
\bar G_N - T \;=\; O_P\!\left(\frac{\sigma_{\text{eff}}}{\sqrt N}\right),
\qquad \sigma_{\text{eff}}^2 = \mathrm{Var}(G_1) + 2\sum_{j=1}^{12}\mathrm{Cov}(G_1,G_{1+j})
$$

i.e. the empirical average block time converges to the configured `target-block-time T`
at the standard `1/\sqrt N` rate, with a constant inflated by the 12-block
autocorrelation the moving-average feedback term deliberately introduces.

---

## 5. Edge cases and their effect on convergence

**Offline proposers.** `LastActiveMiners` only ever fills `sThisMinerPool` from miners
who actually appear in the recent chain, and widens its lookback window by
`nDiversityMiners = nTotalMiners - nActiveMiners`
([`miner.cpp`](../../miner/miner.cpp)) when many permissioned miners
are inactive — so the pool still fills, just from a smaller pool of genuinely live
signers. The compensating mechanism (§3's out-of-pool geometric backoff) uses
`n = GetMaxActiveMinersCount()`, i.e. the **permissioned** miner count, not the online
one. If a large fraction of permissioned miners are actually offline, the expected
catch-up backoff `Θ(log₂ n)` is calibrated against a `n` larger than the truly-live set,
so a real proposer shortfall inflates the *empirical* average gap above `T` — the
ergodic-LLN limit in §4 still holds (the process is still stationary given a *fixed*
active-miner set), but its mean shifts upward until governance updates the permission
list to match who is actually online. This is the exact structural analogue of the wPoA
delay's own offline-validator sensitivity: in `PrivateSortition::MiningDelay`
([`private_sortition.h`](../private_sortition.h), `NormalizedScore` / `MiningDelay`), the delay uses
`total_eff_weight = Σ_j f(w_j)` over the **full registry** (online + offline), while only
the online subset can actually achieve the minimum score; the winning proposer's
realized delay then has mean `scale·(W_total/W_online)` instead of `scale`, i.e. inflated
by exactly the total/online effective-weight ratio.

**Priority shuffling.** The in-pool start-time offset `U·T` (§3) is an independent
uniform draw *per validator per round* (`mc_RandomDouble()` — [`miner.cpp`](../../miner/miner.cpp)),
not a fixed round-robin slot; likewise the "catch-up" pool-admission coin flip
(`prob = dMinerDrift/n̂`, [`miner.cpp`](../../miner/miner.cpp)) reshuffles which
cooled-down miners re-enter the pool each round. Being i.i.d. across rounds and bounded,
this randomization only adds **variance** to each `G_k` (already accounted for in
`σ²_eff` above) — it does not bias the mean away from `T`, since the `-T/(m+1)` centering
term is applied identically regardless of which specific miner draws which slot.
Its downside is *within-round* risk: two shuffled candidates can draw start times close
enough together that both propose (a transient fork, resolved by ordinary first-seen /
longest-chain adoption, mirroring the wPoA "simultaneous qualifiers" case in
[`phase4-implementation-guide.md §13`](phase4-implementation-guide.md#13-accepted-properties-risks--phase-5-hooks)) —
this affects the *variance* of individual gaps, not the LLN limit.

---

## 6. Summary

| Quantity | Native PoA (this doc) | wPoA Phase 4 (for contrast) |
|---|---|---|
| Delay formula | `dExpectedTime ± jitter(T, n, pool-size)` | `D = T + δ·T·(2·score_norm − 1) + λ·Φ`, a band around the target ([`private_sortition.h`](../private_sortition.h), `MiningDelay`) |
| Role of `n` | Logarithmic liveness-fallback term only | Enters only through `Σf(w)`; steady-state mean delay is `scale`, independent of `n` (proved in `phase4-implementation-guide.md` §5) |
| Role of `T` | Direct anchor (`dExpectedTime = parent+T`, feedback-corrected) | Direct anchor too: the band is centred on `T` and `lambda*Phi` corrects the realized mean, reusing the native moving-average-plus-clip shape |
| LLN limit | `\bar G_N \to T` | `\bar G_N \to \text{scale}` (mean of `Exp(1)` scaled by `scale`, since `\min_i \text{score}_i \sim \mathrm{Exp}(\Sigma f(w))` and `\Sigma f(w)\cdot\min_i\text{score}_i \sim \mathrm{Exp}(1)`) |
| Offline-validator effect | Inflates mean gap by (permissioned / active) mismatch | Inflates mean delay by `W_total / W_online` |
