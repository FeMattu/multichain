# `private_sortition.{h,cpp}` — walkthrough (Phase 4)

> **Type:** reference · **Register:** technical-direct · **Verified against the code:**
> 2026-09-26, commit `3d2fc551`
>
> The **Phase 4 module**: the pure core (`private_sortition.h`, class `PrivateSortition` —
> VRF input, private score, normalised score, band delay, feedback bound) and the node
> glue (`private_sortition.cpp` — switches, `Φ`, the shared round context, the miner and
> validator entry points, the already-proposed guard). Call sites:
> [sortition-miner.md](sortition-miner.md) and [sortition-validator.md](sortition-validator.md).
> Why the formula looks like this:
> [wpoa-weight-engine-architecture.md §4.5](wpoa-weight-engine-architecture.md#45-phase-4-timed-private-sortition).

---

## Table of contents
- [1. The pure core (private_sortition.h)](#1-the-pure-core-private_sortitionh)
  - [1.1 VRFInput(seed32, height, out) — the public VRF input](#11-vrfinputseed32-height-out--the-public-vrf-input)
  - [1.2 ScoreFromVRFOutput(vrf_output, weight, dumping) — the private score](#12-scorefromvrfoutputvrf_output-weight-dumping--the-private-score)
  - [1.3 MiningDelay(score, W, T, delta, lambda, Phi) — score-timing / time bar](#13-miningdelayscore-w-t-delta-lambda-phi--score-timing--time-bar)
- [2. The node glue (private_sortition.cpp)](#2-the-node-glue-private_sortitioncpp)
  - [2.1 Flags](#21-flags)
  - [2.1b WPoASortitionFeedback(pindexTip) — Φ](#21b-wpoasortitionfeedbackpindextip--φ)
  - [2.2 WPoASortitionActiveAtHeight(height)](#22-wpoasortitionactiveatheightheight)
  - [2.3 WPoABuildRoundContext(pindexTip, height, &ctx) — shared read path](#23-wpoabuildroundcontextpindextip-height-ctx--shared-read-path)
  - [2.4 WPoASortitionLocalScoreDelay(pindexTip, address, sk32, &score, &delay) — miner](#24-wpoasortitionlocalscoredelaypindextip-address-sk32-score-delay--miner)
  - [2.5 WPoASortitionVRFInputForBlock(block, &input) — miner, at signing](#25-wpoasortitionvrfinputforblockblock-input--miner-at-signing)
  - [2.6 WPoASortitionVerifyProposer(...) — validator](#26-wpoasortitionverifyproposer--validator)
  - [2.7 Already-proposed guard](#27-already-proposed-guard)
  - [2.8 Score-aware activation state](#28-score-aware-activation-state)
- [3. Why this file is split core-vs-glue](#3-why-this-file-is-split-core-vs-glue)

---
## 1. The pure core (`private_sortition.h`)

`PrivateSortition` is header-only and node-free (it depends only on the Phase-2 score
transform in [`wpoa_selector.h`](../src/wpoa/wpoa_selector.h)), so the unit suite exercises it
without linking the node — exactly like the Phase 2/3a/3b cores.

### 1.1 `VRFInput(seed32, height, out)` — the public VRF input

Builds the 44-byte, consensus-critical input the per-validator VRF is evaluated over:

```
out = seed(32) ‖ "PROPOSER"(8) ‖ BE32(height)
```

- `seed32` is the Phase-3b beacon seed `seed[n+1] = H(R_tot[n-k] ‖ h[n] ‖ n+1)`.
- `"PROPOSER"` is a domain-separation tag (`ProposerTag()`, `PROPOSER_TAG_LEN = 8`) so a
  sortition reveal can never collide with the Phase-3a prev-hash reveal or any other VRF
  usage.
- `height` is serialized big-endian (the same fixed encoding
  `RandaoAccumulator::DeriveSeed` uses), so the bytes are identical on every platform.

This is exactly the input from [thesis §6.2](thesis-project-overview.md#62-efraimidisspirakis-sortition-private-local-score-computation).
Changing the tag, the order or the height encoding forks the chain.

### 1.2 `ScoreFromVRFOutput(vrf_output, weight, dumping)` — the private score

```cpp
return WPoASelector::ScoreFromEntropy64(WPoASelector::FoldTop64(vrf_output), weight, dumping);
```

It folds the top 64 bits of the VRF output and calls the **same** transform the public
Phase-2 selector applies to its HMAC digest. That is the single source of truth for the
score math: given identical `(entropy, weight, dumping)`, `ScoreFromVRFOutput(y,…)` is
byte-identical to `WPoASelector::ComputeScore(seed,addr,…)` — the property the unit test
`score_matches_shared_transform` pins. `weight == 0 ⇒ +inf` (via `ScoreFromEntropy64`), so
an unweighted node can never be the argmin.

The refactor that made this possible lives in [`wpoa_selector.h`](../src/wpoa/wpoa_selector.h):
`FoldTop64(buf)` (big-endian top-64-bit fold) and `ScoreFromEntropy64(d, weight, dumping)`
(`u=(d+1)/2^64; E=-ln(u); score=E/f(weight)`) were extracted from the old `ComputeScore`,
which now just does `HMAC → FoldTop64 → ScoreFromEntropy64`.

### 1.3 `MiningDelay(score, W, T, delta, lambda, Phi)` — score-timing / time bar

```cpp
static double MiningDelay(double score, double total_eff_weight,
                          double target_block_time, double delta,
                          double lambda, double feedback);
```

```
norm  = NormalizedScore(score, W)                     // 1 - e^(-W·score), in (0,1)
delay = clamp( T + delta·T·DelayShape(norm) + lambda·Phi , 0 , MaxDelaySeconds() )
DelayShape(x) = 2x - 1                                // symmetric band around T
```

- **Strictly increasing in `score`** ⇒ the argmin has the smallest delay ⇒ it proposes
  first ⇒ it wins the round ⇒ the distribution stays `f(w_i)/Σf(w)`.
- **The `W` factor** is what makes the normalisation real. Without it `norm` would inherit
  the scale of `E/w` and collapse towards 0 for every candidate once weights reach the
  hundreds. With it, `min_i score_i ~ Exp(W)`, so `W·min ~ Exp(1)`, and applying that
  distribution's CDF gives the **winner** an exactly uniform `norm` on `(0,1)`, whatever the
  number of candidates and the weights. The winner's delay is then uniform over the band
  and the mean block time lands on `T` (`NormalizedScore`, Prop. 5.10).
- **`delta` is a fraction of `T`**, so the band half-width is `Δmax = delta·T` and the knob
  is invariant to a change of `T`.
- **`lambda·Phi` is identical for every candidate** of a round, so it cancels in every
  pairwise difference and cannot reorder anyone; it only corrects the aggregate cadence.
  `MaxFeedback(T, delta, lambda) = T(1−delta)/lambda` (Cor. 5.15) is the largest `|Phi|`
  that keeps every delay non-negative; the caller clips `Phi` to it.
- **Degenerate-safe**: a non-finite or out-of-domain parameter returns `MaxDelaySeconds()`
  (the node stands down); a degenerate `score`/`W` gives `norm = 1` (maximally delayed); a
  negative total is clamped to 0; the ceiling `MaxDelaySeconds()` keeps `parent.nTime +
  delay` clear of `uint32` overflow.

`MaxDelaySeconds() = 100000` (~27.7 h): a cap high enough never to bind on realistic
scores, low enough to bound the worst case.

---

## 2. The node glue (`private_sortition.cpp`)

### 2.1 Flags

Four runtime globals, all set once in `AppInit2` and never written again:

- `g_wpoa_sortition_enabled` — the activation gate, from `enable-wpoa-sortition`.
- `g_wpoa_sortition_delta` — the band half-width **as a fraction** of
  target-block-time, so the absolute half-width is `Δmax = δ·T_block`. Must be in
  `(0,1)`: at `δ ≥ 1` the most favoured candidate's timer would fall *before* the
  round opened.
- `g_wpoa_sortition_lambda` — the feedback gain `λ`. At `0` the global correction is
  disabled entirely (Cor. 5.14).
- `g_wpoa_fork_score_enabled` — the score-based fork choice, read unlocked by the chain
  comparator in `main.cpp`. It has no flag: `AppInit2` sets it to `g_wpoa_sortition_enabled`,
  because the score-aware activation (§2.8) depends on it; see
  [wpoa-weight-engine-architecture.md §3.6](wpoa-weight-engine-architecture.md#36-fork-choice-the-true-score-in-the-chain-comparator).

The first three are **consensus-critical**: they enter the validator's time bar, so a node
holding different values computes a different bar and forks. The fourth is not: it changes
which valid tip this node prefers, never which blocks are valid.

> **Defaults and valid ranges:
> [protocol-parameters.md §2](protocol-parameters.md#2-catalogue--wpoa-phases).**

#### Sizing δ against the network

`Δmax = δ·T_block` is an *absolute* time, so δ has to be read together with the chain's
target-block-time. Prop. 5.17 bounds the probability that jitter overturns the score
ordering by `O((n·σ/Δmax)^{2/3})`, so what matters is Δmax against the network's timer
jitter σ — not δ on its own.

Measured on 3 validators at 100/200/300, the median spread between the first and second
candidate:

| `T_block` | δ = 0.5 | δ = 0.8 | δ = 0.9 |
|---|---|---|---|
| 2 s  | 504 ms | 808 ms | 909 ms |
| 15 s (default) | 3.8 s | 6.1 s | 6.8 s |

At the stock 15 s target, δ = 0.5 already gives a far wider spread than the open-ended
ramp it replaced (~1.15 s), which is why 0.5 is the protocol default. On a chain with a
deliberately short target the band shrinks with it: the former shell functional test
compressed target-block-time to 2 s and correspondingly raised δ to 0.9, and the effect was
measurable — at δ = 0.5 the observed proposer distribution drifts (median χ² ≈ 11 over
30-block samples, against ≈ 1.4 expected), while at δ = 0.9 it returns to the level of
the previous delay law (median χ² ≈ 3.5 vs ≈ 3.8).

Raising δ also tightens the feedback headroom: `M* = T_block(1−δ)/λ` (Cor. 5.15) shrinks
as δ → 1, and `WPoASortitionFeedback` clips to `min(0.5·T_block, M*)`, so a wide band and
an aggressive λ cannot be configured at the same time — the clip resolves the tension
automatically rather than letting the timer go admissible-negative.

### 2.1b `WPoASortitionFeedback(pindexTip)` — Φ

```
Φ = clip( T_block − mean_observed_spacing , −M , +M )
mean_observed_spacing = ( h[n].nTime − h[n−12].nTime ) / 12
M = min( 0.5·T_block , M* )        M* = T_block(1−δ)/λ   (Cor. 5.15)
```

This is deliberately the **same shape MultiChain's native scheduler already uses** to hold
its cadence on target (`miner.cpp`: a mean over `nPastBlocks = 12` past blocks, then a clip
into a band around the per-last-block target), with one substitution that matters.

The native code averages `pindex->dTimeReceived` — the **local wall-clock arrival time**,
assigned in `main.cpp` when the block comes in. That is per-node data: two nodes disagree on
it, and a node that synced from scratch has it zero for every historical block. Harmless for
a purely local scheduling hint, but Φ enters the validator's time bar, and Def. 5.12 requires
Φ to be a deterministic public function of the finalized state. So the average is taken over
**block timestamps**, which live in the header and are identical everywhere.

Sign: blocks arriving too slowly (mean spacing above target) give Φ < 0, which shortens every
candidate's timer; too fast gives Φ > 0, which lengthens it — negative feedback on the
cadence. Because Φ is common to all candidates of the round it cancels in every pairwise
timer difference and cannot reorder anyone (Prop. 5.11). Fewer than a full window of history
yields `Φ = 0`, mirroring the native `nWindowSize < nPastBlocks` branch, so a young chain
simply runs uncorrected.

The window is a compile-time constant (`MC_WPOA_SORTITION_FEEDBACK_WINDOW`) rather than an
operator knob: it is consensus-critical, and the thesis leaves only δ and λ open to tuning
(Table 5.2).

### 2.2 `WPoASortitionActiveAtHeight(height)`

```cpp
return g_wpoa_sortition_enabled && WPoARANDAOActiveAtHeight(height);
```

Sortition consumes the beacon seed as its VRF input, so it engages exactly where the RANDAO
beacon governs the height (which itself requires VRF + wPoA + `height ≥ setup`). A pure
function of shared data, so the miner and every validator agree from the height alone.

### 2.3 `WPoABuildRoundContext(pindexTip, height, &ctx)` — shared read path

```cpp
struct WPoARoundContext
{
    int                             height;            // the round being elected
    std::map<std::string, uint32_t> raw_weights;       // w, as of height - 1
    std::map<std::string, uint32_t> weights;           // w_eff = w * Psi
    double                          total_eff_weight;  // W = sum_j f(w_eff_j) > 0
    unsigned char                   seed[32];          // beacon seed, or prev-block hash
    bool                            randao_seed;
};
bool WPoABuildRoundContext(const CBlockIndex* pindexTip, int height, WPoARoundContext& out);
```

Everything a round needs, derived in one place:

1. **Seed** — the RANDAO seed over `pindexTip` when the beacon governs `height` (a failure
   there is fatal: falling back would make the validator derive a different seed), the
   previous block hash otherwise. So an audit at a historical height reproduces the seed
   that actually governed it.
2. **Weights** — `GetAllNodesWeightsAsOf(height − 1)`: the records confirmed in the prefix,
   not whatever this node has synced by now. The bound comes from the block's own height,
   so the miner, the validator and an audit RPC run long afterwards compute the same bound.
3. **Malus** — `WPoAApplyMalus(raw_weights, height)` gives `w_eff`.
4. **`W`** — `WPoASelector::TotalEffectiveWeight(weights, g_dumping_function)`, summed in
   sorted-key order so the floating-point value is identical on every node.

Returns false — leaving `out` untouched — when the wallet, the weight map or the seed is
unavailable, or `W` is not positive. The miner path and the round audit RPCs
(`wpoaget*` / `wpoalist*`) call it; the validator reproduces the same four steps inline
(§2.6).

### 2.4 `WPoASortitionLocalScoreDelay(pindexTip, address, sk32, &score, &delay)` — miner

`WPoABuildRoundContext(tip, tip->nHeight+1)`; look up this node's own **effective** weight
(absent or zero ⇒ false, cannot self-elect); `VRFInput(seed, height)`;
`WPoAVRF::Prove(sk32, input, …)` → output; `score = ScoreFromVRFOutput(output, w_eff,
dumping)`; `delay = MiningDelay(score, W, T, g_wpoa_sortition_delta,
g_wpoa_sortition_lambda, WPoASortitionFeedback(tip))`. Returns the score and delay for the
miner's start time. A `false` makes the miner stand down — or, during the bootstrap window,
fall back to native mining ([sortition-miner.md §1](sortition-miner.md#1-score-timed-self-election-getminerandexpectedminingstarttime)).

### 2.5 `WPoASortitionVRFInputForBlock(block, &input)` — miner, at signing

Looks the block's parent up in `mapBlockIndex`; if `height = parent->nHeight+1` is
sortition-governed, returns `VRFInput(seed_over_parent, height)`. Returns false off sortition
heights (the caller then embeds the Phase-3a prev-hash reveal). This is what makes the
block-carried reveal be the score material on sortition heights.

### 2.6 `WPoASortitionVerifyProposer(...)` — validator

```cpp
WPoASortitionVerdict WPoASortitionVerifyProposer(const CBlockIndex* pindexParent, int height,
        const std::vector<unsigned char>& pubkey, const std::string& miner_addr,
        const std::vector<unsigned char>& vrf_reveal, const std::vector<unsigned char>& vrf_proof,
        uint32_t block_ntime, std::string* reason_out,
        double* score_out = NULL, double* weff_out = NULL);
```

Returns a `WPoASortitionVerdict` (`REJECT` / `SKIP` / `OK`):

1. The beacon must govern `height`, and the seed over `pindexParent` must be derivable;
   otherwise → `SKIP`.
2. `VRFInput(seed, height)`; `WPoAVRF::Verify(pubkey, input, reveal, proof)`. Fail → `REJECT`
   ("invalid or missing VRF reveal over the sortition input"). Unforgeable and independent
   of the weight map, so it is enforced even on the lenient path.
3. `GetAllNodesWeightsAsOf(height − 1)`. No wallet or empty ⇒ `SKIP`.
4. `WPoAApplyMalus(weights, height)`. Signer absent or at effective weight 0 ⇒ `REJECT`
   ("signer is not a weighted validator in the registry").
5. `W = TotalEffectiveWeight(weights, dumping)` — the same function the miner uses (this
   was an open-coded loop that agreed with the miner only because `f(0) = 0`). `W ≤ 0` ⇒
   `SKIP`.
6. `score = ScoreFromVRFOutput(reveal, w_eff, dumping)`;
   `delay = MiningDelay(score, W, T, δ, λ, WPoASortitionFeedback(pindexParent))`.
7. **Time bar**: `block_ntime ≥ parent.nTime + (int64_t)delay` (floor). Fail ⇒ `REJECT`
   ("block mined too early for its sortition score"). Else `OK`, and only then
   `*score_out` / `*weff_out` are written — so a caller that seeded them with NaN keeps its
   "unknown" marker on REJECT and SKIP. The validator uses them to fill the fork-choice
   score cache ([sortition-validator.md](sortition-validator.md)).

`SKIP` is reserved for node-global conditions; every defect attributable to the block is a
`REJECT`. The floor gives implicit sub-second leniency; the fine ordering is done
miner-side. Steps 3–5 are the same as `WPoABuildRoundContext`'s, written out because this
function is also the one place that must verify the reveal before reading the registry.

### 2.7 Already-proposed guard

`WPoASortitionMarkProposed(height)` records the highest height this node has mined;
`WPoASortitionAlreadyProposed(height)` reports whether a height is at or below it. Guarded by
the leaf lock `cs_sortition_proposed`. The miner checks it before the timing cache so a node whose block
lost a fork does not spin re-mining the same (unchanged-tip) height. See
[sortition-miner.md](sortition-miner.md).

### 2.8 Score-aware activation state

The round this node is counting down for, and the blocks for that round it holds back.
Guarded by the leaf lock `cs_sortition_pending`; `cs_sortition_proposed` is read before it,
never under it.

| function | caller | does |
|---|---|---|
| `WPoASortitionSetPendingRound(parent, height, score, slot_time)` | miner, with every countdown | records parent, height, own true score, local slot time; resets the per-round state when the round changes |
| `WPoASortitionShouldDeferActivation(pindex)` | `FindMostWorkChain`, under `cs_main` | true for a direct child of that parent, at that height, with a known score strictly worse than ours, not mined by us, while our round is open (not proposed, not past the slot plus `MC_WPOA_DEFER_GRACE_S` = 2 s). Logs `[wpoa-fork] defer` once per block |
| `WPoASortitionTakeDeferredRelay(&hash)` | `ProcessNewBlock`, outside `cs_main` | hands out each held block once, for relay |
| `WPoASortitionDeferralExpired()` | miner loop, no lock held | true once when a block was held and the grace ran out without our proposing; logs `[wpoa-fork] defer-release` |

Why and how the pieces fit: [score-aware-activation.md](score-aware-activation.md).

---

## 3. Why this file is split core-vs-glue

Identical rationale to Phase 2/3a/3b: the consensus-critical math (`VRFInput`, the score,
the normalised score, the delay, the feedback bound) is pure and node-free so it can be
unit-tested exhaustively — the `sortition` suite, including real-VRF probability
preservation and winner-delay uniformity, and the `audit` suite — without a node, while the
parts that must touch the wallet key, the weight registry and the block index live in the
`.cpp`. Keeping `MiningDelay` and
`ScoreFromVRFOutput` pure is what lets the unit suite prove — offline — that the private
election is distribution-neutral and that the delay ordering is correct.
