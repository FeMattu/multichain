# `protocol/multichainblock.cpp` — the Phase 4 validator-side hook

> **Type:** reference · **Register:** technical-direct · **Verified against the code:**
> 2026-09-26, commit `3d2fc551`
>
> The **receiving side of private sortition**: the branch of `VerifyBlockMinerWPoA` that
> replaces the public argmin equality with a VRF-verify + score-recompute + time-bar
> eligibility test, and caches the true score for the fork-choice comparator. The sending
> side is [sortition-miner.md](sortition-miner.md); `WPoASortitionVerifyProposer` is walked
> through in [private-sortition.md](private-sortition.md); the order of all the validator
> checks is in [block-validation.md §3](block-validation.md#3-verifyblockminerwpoa--the-order-of-the-checks).

---

## 1. Why the argmin equality cannot be reused

For Phase 2/3b, `VerifyBlockMinerWPoA` recomputes the single deterministic proposer with
`WPoASelectProposer(seed, weights)` and rejects the block unless `miner == proposer`. Under
private sortition that is **impossible**: each validator's score is a VRF under its own
secret key, so a peer cannot compute anyone else's score and therefore cannot recompute the
global argmin. The check must become an **eligibility** test the peer *can* evaluate from
public data plus the block's own reveal.

## 2. The sortition branch

Inserted right after the signer/pubkey are validated (so `vchPubKey` and `sMinerAddr` are in
hand) and **before** the Phase-3a VRF-verify block, so sortition heights are intercepted
entirely and non-sortition wPoA heights fall through to the unchanged 3a/3b path:

```cpp
if(WPoASortitionActiveAtHeight(pindexNew->nHeight))
{
    std::vector<unsigned char> vrf_reveal,vrf_proof;
    if(!FindBlockVRF(pblock,vrf_reveal,vrf_proof))
        return false;                                   // REJECT: missing reveal

    std::string sReason;
    double dScore=NaN, dWeff=NaN;
    WPoASortitionVerdict verdict=WPoASortitionVerifyProposer(
            pindexNew->pprev,pindexNew->nHeight,vchPubKey,sMinerAddr,
            vrf_reveal,vrf_proof,pblock->nTime,&sReason,&dScore,&dWeff);

    if(verdict == WPOA_SORTITION_REJECT)  return false;              // provably invalid
    if(verdict == WPOA_SORTITION_SKIP)
    {
        if(fAtAdmission) { dSortitionScore = dSortitionScoreNorm = NaN; }   // "unknown", explicitly
        pindexNew->fPassedMinerPrecheck=true; return true;           // leniency
    }
    if(fAtAdmission)                                                 // WPOA_SORTITION_OK
    {
        pindexNew->dSortitionScore     = dScore;
        pindexNew->dSortitionScoreNorm = PrivateSortition::NormalizedScore(dScore,dWeff);
    }
    pindexNew->fPassedMinerPrecheck=true; return true;
}
```

- **`FindBlockVRF`** (the existing Phase-3a extractor) pulls the `(reveal, proof)` suffix out
  of the coinbase block-signature element. A sortition block with no reveal is rejected
  outright.
- **`WPoASortitionVerifyProposer`** ([private-sortition.md](private-sortition.md)) does the
  real work, in this order:
  1. recompute the beacon seed over `pindexNew->pprev` (the same tip the honest miner saw);
  2. verify the VRF over `seed ‖ "PROPOSER" ‖ height` — **before** reading the registry, so
     it binds even on the lenient path;
  3. read the registry **as of `height − 1`** and apply `WPoAApplyMalus`, exactly the
     effective weights the miner scored itself against;
  4. reject a signer absent from that map or with effective weight 0;
  5. compute `W = TotalEffectiveWeight(...)` — the same function the miner uses; the
     validator used to carry an open-coded copy of this sum;
  6. recompute the score from the reveal and enforce the time bar
     `pblock->nTime ≥ parent.nTime + floor(MiningDelay(score, W, T, δ, λ, Φ))`, with `Φ`
     from `WPoASortitionFeedback(parent)`, i.e. from block timestamps only.
- **The score cache.** On OK, and only at admission (`fAtAdmission`, set by `AcceptBlock`
  before the index enters `setBlockIndexCandidates`), the true score and its normalised
  value are written to the index for the score-based fork choice. The calls from
  `FindMostWorkChain` pass `fAtAdmission = false` and leave the fields alone: those indices
  are already keys of an ordered `std::set`. On SKIP the "unknown" marker (NaN) is written
  explicitly, because a real score is `≥ 0` and any numeric value — zero above all — would
  read back as a genuine, winning score.

## 3. The three verdicts

| Verdict | Meaning | Action |
|---------|---------|--------|
| `WPOA_SORTITION_REJECT` | Provably invalid, attributable to the block: forged/missing reveal, signer not a weighted validator (or excluded by the malus), or block mined earlier than its score entitles. | `return false` → block flagged `BLOCK_FAILED_VALID`, excluded from tip selection / rejected in `AcceptBlock`. |
| `WPOA_SORTITION_SKIP` | Cannot evaluate locally, for **node-global** reasons only: seed unrecoverable, no wallet, no weight confirmed in the prefix, `W = 0`. The VRF proof was still enforced. | Accept leniently rather than stall, mirroring the Phase 2/3b empty-registry leniency; score cached as NaN at admission. An honest block stays valid on any node that can evaluate it. |
| `WPOA_SORTITION_OK` | Eligible: valid reveal, weighted signer, `nTime` clears the time bar. | Accept; true score cached at admission. |

Because SKIP depends only on node-global state and never on a block's contents, a proposer
cannot craft a block that lands in the "unknown" bucket, and within one round a node scores
either every candidate or none — which is what keeps the fork-choice ordering consistent.

## 4. Why this is safe and agrees network-wide

- **Miner and validator seed off the same tip, and read the same prefix.** The honest
  miner's tip for a height-`m` block was `m-1`; the validator checks against
  `pindexNew->pprev`, which *is* that tip. Both derive the identical `seed[m]` and VRF input,
  and both read the registry as of `m − 1`, so they apply the identical `w_eff`, `W`, `Φ` and
  delay — the time bar is the same function on both sides, whatever each node's sync point.
  Reading the *current* registry here used to let two nodes disagree on the same block.
- **Front-running is bounded.** To clear the bar earlier a signer needs a lower score
  (unforgeable — VRF uniqueness) or a larger `nTime` (bounded above by the base-consensus
  `time-too-new` rule, and below by `time-too-old`/MTP). It cannot manufacture eligibility.
- **The reveal still verifies unconditionally.** The VRF check runs before the weight read,
  so even on the `SKIP` leniency path a forged reveal is rejected — exactly the Phase-3a
  guarantee, now over the sortition input.

## 5. What is *not* touched

The existing Phase-3a VRF-verify block (prev-hash input) and the Phase-3b seed + argmin
equality remain in place for **non-sortition** wPoA heights (e.g. a chain running
`enable-wpoa-vrf`/`enable-wpoa-randao` but not `enable-wpoa-sortition`). Only when
`WPoASortitionActiveAtHeight(height)` is true does the branch above intercept and return
first. The block-permission (`CanMine`) check and full transaction/`ConnectBlock` validation
downstream are unchanged — `VerifyBlockMinerWPoA` returning true only clears the
miner-precheck gate, exactly as in the earlier phases.

The malus `delay` predicate re-derives this same time bar when it judges a report; how its
reconstruction differs from the one above is recorded in
[wpoa-weight-engine-architecture.md §10](wpoa-weight-engine-architecture.md#10-known-limits-and-open-points).
