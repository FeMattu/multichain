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

- `seed32` is the Phase-3b beacon seed `seed[n+1] = H(R_tot[n-k] ‖ h[n-1] ‖ n)`.
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
- `g_wpoa_sortition_delay` (default `MC_WPOA_DEFAULT_SORTITION_DELAY = 1.0`) — the `scale`
  in `MiningDelay`, set from `-wpoasortitiondelay`. Consensus-critical (it enters the
  validator's time bar).

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
g_wpoa_sortition_delay)`. Returns the score and delay for the miner's start-time.

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
