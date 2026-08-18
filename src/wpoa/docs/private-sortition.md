# `private_sortition.{h,cpp}` — line-by-line walkthrough (Phase 4)

This is the per-file companion to
[phase4-implementation-guide.md](phase4-implementation-guide.md). It walks the pure core
(`private_sortition.h`, class `PrivateSortition`) and the node glue
(`private_sortition.cpp`) in detail. For the miner/validator call sites see
[sortition-miner.md](sortition-miner.md) and [sortition-validator.md](sortition-validator.md).

---

## 1. The pure core (`private_sortition.h`)

`PrivateSortition` is header-only and node-free (it depends only on the Phase-2 score
transform in [`wpoa_selector.h`](../wpoa_selector.h)), so the unit suite exercises it
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

The refactor that made this possible lives in [`wpoa_selector.h`](../wpoa_selector.h):
`FoldTop64(buf)` (big-endian top-64-bit fold) and `ScoreFromEntropy64(d, weight, dumping)`
(`u=(d+1)/2^64; E=-ln(u); score=E/f(weight)`) were extracted from the old `ComputeScore`,
which now just does `HMAC → FoldTop64 → ScoreFromEntropy64`.

### 1.3 `MiningDelay(score, total_eff_weight, scale)` — score-timing / time bar

```
delay = clamp( scale · score · total_eff_weight , 0 , MaxDelaySeconds() )
```

- **Strictly increasing in `score`** ⇒ the argmin has the smallest delay ⇒ it proposes
  first ⇒ it wins the round ⇒ the distribution stays `w_i/Σw`.
- **`× total_eff_weight`** makes the delay weight-**scale** invariant (see
  [phase4 §5](phase4-implementation-guide.md#5-design-decisions)): the minimum score is
  `~Exp(Σf(w))`, so `score·Σf(w)` is `~Exp(1)`-scaled and `scale` (seconds) sets the
  real-time spread directly, independent of the absolute weights.
- **Degenerate-safe**: any non-finite/negative `score`, `total_eff_weight ≤ 0`, or bad
  `scale` returns `MaxDelaySeconds()` (the node stands down) rather than a negative/NaN
  delay that would make the time bar meaningless. The clamp also keeps `parent.nTime +
  delay` clear of `uint32` overflow.

`MaxDelaySeconds() = 100000` (~27.7 h): a cap high enough never to bind on realistic
scores, low enough to bound the worst case.

---

## 2. The node glue (`private_sortition.cpp`)

### 2.1 Flags

- `g_wpoa_sortition_enabled` (default `false`) — set from `-enablewpoasortition` in AppInit2.
- `g_wpoa_sortition_delta` (default `0.5`) — the band half-width as a fraction of
  target-block-time, `Δmax = δ·T_block`, set from `-wpoasortitiondelta`. Must be in `(0,1)`:
  at `δ ≥ 1` the most favoured candidate's timer would fall before the round opened.
- `g_wpoa_sortition_lambda` (default `0`) — the feedback gain λ, set from
  `-wpoasortitionlambda`. `0` disables the global correction entirely (Cor. 5.14).

Both are consensus-critical: they enter the validator's time bar, so a node holding
different values computes a different bar and forks.

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
deliberately short target the band shrinks with it: the functional test compresses
target-block-time to 2 s and correspondingly raises δ to 0.9, and the effect is
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

### 2.3 `BuildSortitionContext(pindexTip, weights, &Σf(w), seed)` — shared read path

Static helper used by both the miner-side score and (implicitly) the validator: it derives
the beacon seed over the tip (`WPoARandaoSelectionSeed`), reads the confirmed weight map
(`GetAllNodesWeights`), and sums the **effective** weights `Σ_j ApplyDumping(w_j, dumping)`.
The sum runs in the `std::map`'s sorted-key order, so its floating-point value is identical
on every node. Returns false when the seed or a non-empty weight map is unavailable — the
caller then stands down (miner) or accepts leniently (validator).

### 2.4 `WPoASortitionLocalScoreDelay(pindexTip, address, sk32, &score, &delay)` — miner

Builds the context; looks up this node's own weight (absent/zero ⇒ false, cannot self-elect);
`VRFInput(seed, tip->nHeight+1)`; `WPoAVRF::Prove(sk32, input, …)` → output; `score =
ScoreFromVRFOutput(output, weight, dumping)`; `delay = MiningDelay(score, Σf(w),
g_wpoa_sortition_delta, g_wpoa_sortition_lambda, Φ)`. Returns the score and delay for the miner's start-time.

### 2.5 `WPoASortitionVRFInputForBlock(block, &input)` — miner, at signing

Looks the block's parent up in `mapBlockIndex`; if `height = parent->nHeight+1` is
sortition-governed, returns `VRFInput(seed_over_parent, height)`. Returns false off sortition
heights (the caller then embeds the Phase-3a prev-hash reveal). This is what makes the
block-carried reveal be the score material on sortition heights.

### 2.6 `WPoASortitionVerifyProposer(parent, height, pubkey, addr, reveal, proof, block_ntime, &reason)` — validator

Returns a `WPoASortitionVerdict` (`REJECT` / `SKIP` / `OK`):

1. Recompute the beacon seed over `parent`. If it cannot be recomputed (degenerate/NULL
   tip) → `SKIP` (accept leniently).
2. `VRFInput(seed, height)`; `WPoAVRF::Verify(pubkey, input, reveal, proof)`. Fail → `REJECT`
   ("invalid or missing VRF reveal over the sortition input"). This is unforgeable and
   independent of the weight map, so it is enforced even on the leniency path.
3. Read weights. Empty ⇒ `SKIP` (unsynced). Signer absent/zero-weight ⇒ `REJECT`
   ("not a weighted validator").
4. `Σf(w)`; `score = ScoreFromVRFOutput(reveal, weight, dumping)`; `delay = MiningDelay(…)`.
5. **Time bar**: `block_ntime ≥ parent.nTime + (int64_t)delay` (floor). Fail ⇒ `REJECT`
   ("too early for its sortition score"). Else `OK`.

The floor gives implicit sub-second leniency; the fine ordering is done miner-side.

### 2.7 Anti-respin guard

`WPoASortitionMarkProposed(height)` records the highest height this node has mined;
`WPoASortitionAlreadyProposed(height)` reports whether a height is at or below it. Guarded by
a leaf `CCriticalSection`. The miner checks it before the timing cache so a node whose block
lost a fork does not spin re-mining the same (unchanged-tip) height. See
[sortition-miner.md](sortition-miner.md).

---

## 3. Why this file is split core-vs-glue

Identical rationale to Phase 2/3a/3b: the consensus-critical math (`VRFInput`, the score,
the delay) is pure and node-free so it can be unit-tested exhaustively (including real-VRF
probability preservation) without a node, while the parts that must touch the wallet key,
the weight registry and the block index live in the `.cpp`. Keeping `MiningDelay` and
`ScoreFromVRFOutput` pure is what lets the unit suite prove — offline — that the private
election is distribution-neutral and that the delay ordering is correct.
