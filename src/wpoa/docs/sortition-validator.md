# `protocol/multichainblock.cpp` — the Phase 4 validator-side hook (walkthrough)

Per-file companion to [phase4-implementation-guide.md](phase4-implementation-guide.md),
covering the receiving-side change for private sortition. See
[sortition-miner.md](sortition-miner.md) for the sending side and
[private-sortition.md](private-sortition.md) for `WPoASortitionVerifyProposer`.

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
    WPoASortitionVerdict verdict=WPoASortitionVerifyProposer(
            pindexNew->pprev,pindexNew->nHeight,vchPubKey,sMinerAddr,
            vrf_reveal,vrf_proof,pblock->nTime,&sReason);

    if(verdict == WPOA_SORTITION_REJECT)  return false;              // provably invalid
    if(verdict == WPOA_SORTITION_SKIP)  { pindexNew->fPassedMinerPrecheck=true; return true; }  // leniency
    pindexNew->fPassedMinerPrecheck=true; return true;               // WPOA_SORTITION_OK
}
```

- **`FindBlockVRF`** (the existing Phase-3a extractor) pulls the `(reveal, proof)` suffix out
  of the coinbase block-signature element. A sortition block with no reveal is rejected
  outright.
- **`WPoASortitionVerifyProposer`** (see [private-sortition.md §2.6](private-sortition.md))
  does the real work: recompute the beacon seed over `pindexNew->pprev` (the same tip the
  honest miner saw), verify the VRF over `seed ‖ "PROPOSER" ‖ height`, recompute the score
  from the reveal and the signer's registry weight, and enforce the time bar
  `pblock->nTime ≥ parent.nTime + floor(delay)`.

## 3. The three verdicts

| Verdict | Meaning | Action |
|---------|---------|--------|
| `WPOA_SORTITION_REJECT` | Provably invalid: forged/missing reveal, signer not a weighted validator, or block mined earlier than its score entitles. | `return false` → block flagged `BLOCK_FAILED_VALID`, excluded from tip selection / rejected in `AcceptBlock`. |
| `WPOA_SORTITION_SKIP` | Cannot evaluate locally (seed unrecoverable, or weights not yet synced). The VRF proof was still enforced. | `fPassedMinerPrecheck=true; return true` — accept leniently rather than stall, mirroring the Phase 2/3b empty-registry leniency. An honest block stays valid on any fully-synced node. |
| `WPOA_SORTITION_OK` | Eligible: valid reveal, weighted signer, `nTime` clears the time bar. | `fPassedMinerPrecheck=true; return true`. |

## 4. Why this is safe and agrees network-wide

- **Miner and validator seed off the same tip.** The honest miner's tip for a height-`m`
  block was `m-1`; the validator checks against `pindexNew->pprev`, which *is* that tip. Both
  derive the identical `seed[m]`, the identical VRF input, and (from the same weight map) the
  identical `Σf(w)` and delay — so the time bar is the same function on both sides.
- **Front-running is bounded.** To clear the bar earlier a signer needs a lower score
  (unforgeable — VRF uniqueness) or a larger `nTime` (bounded above by the base-consensus
  `time-too-new` rule, and below by `time-too-old`/MTP). It cannot manufacture eligibility.
- **The reveal still verifies unconditionally.** The VRF check runs before the weight read,
  so even on the `SKIP` leniency path a forged reveal is rejected — exactly the Phase-3a
  guarantee, now over the sortition input.

## 5. What is *not* touched

The existing Phase-3a VRF-verify block (prev-hash input) and the Phase-3b seed + argmin
equality remain in place for **non-sortition** wPoA heights (e.g. a chain running
`-enablewpoavrf`/`-enablewpoarandao` but not `-enablewpoasortition`). Only when
`WPoASortitionActiveAtHeight(height)` is true does the branch above intercept and return
first. The block-permission (`CanMine`) check and full transaction/`ConnectBlock` validation
downstream are unchanged — `VerifyBlockMinerWPoA` returning true only clears the
miner-precheck gate, exactly as in the earlier phases.
