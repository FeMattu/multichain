# `miner/miner.cpp` — the Phase 4 miner-side hook (walkthrough)

Per-file companion to [phase4-implementation-guide.md](phase4-implementation-guide.md),
covering the three miner-side changes for private sortition. See
[private-sortition.md](private-sortition.md) for the helpers called here and
[sortition-validator.md](sortition-validator.md) for the receiving side.

Phase 4 adds three things to the miner, all gated on `WPoASortitionActiveAtHeight`:

1. a **score-timed self-election** branch in `GetMinerAndExpectedMiningStartTime`,
2. an **anti-respin guard** (also in that function), and
3. a **reveal-input switch** in `CreateBlockSignature`,
plus a one-line **`MarkProposed`** call in the mining loop.

---

## 1. Score-timed self-election (`GetMinerAndExpectedMiningStartTime`)

The sortition branch is placed **before** the Phase-2 branch, because sortition heights are
a strict subset of wPoA heights and must take this path:

```cpp
if(WPoASortitionActiveAtHeight(pindexTip->nHeight + 1))
{
    pwallet->GetKeyFromAddressBook(kThisMiner,MC_PTP_MINE);
    *lpkMiner=kThisMiner;
    int nHeight=pindexTip->nHeight+1;

    if(!kThisMiner.IsValid()) { wait 3600s; return; }          // no mining key

    CKey kMinerSecret;
    if(!pwallet->GetKey(kThisMiner.GetID(),kMinerSecret)) { wait 3600s; return; }
    std::string sLocalAddr=CBitcoinAddress(kThisMiner.GetID()).ToString();

    double dScore,dDelay;
    if(!WPoASortitionLocalScoreDelay(pindexTip,sLocalAddr,kMinerSecret.begin(),&dScore,&dDelay))
    { wait 3600s; return; }                                     // unsynced or unweighted

    *lpdMiningStartTime = mc_TimeNowAsDouble() + dDelay;        // score-timed
    return *lpdMiningStartTime;
}
```

The node computes **only its own** score (it has only its own secret key) and sets its
mining start to `now + delay(score)`. Lower score ⇒ earlier start ⇒ the argmin proposes
first. Every other case (no key, secret key unavailable, weights unsynced, this node
unweighted) falls back to a long wait; the caching return higher up keeps the node idle
until the tip advances.

`kMinerSecret.begin()` is the 32-byte secret key handed to `WPoAVRF::Prove` (via
`WPoASortitionLocalScoreDelay`) — the same idiom the Phase-3a reveal embed already uses.

## 2. Anti-respin guard (top of the timing function)

Placed right after `pindexTip = chainActive.Tip();`, **before** the tip-hash timing cache:

```cpp
if(WPoASortitionActiveAtHeight(pindexTip->nHeight+1) &&
   WPoASortitionAlreadyProposed(pindexTip->nHeight+1))
{
    ... set kMiner, *lpdMiningStartTime = now + 3600, hash/mempool ...
    return *lpdMiningStartTime;                                 // stand down
}
```

Why before the cache: MultiChain's timing function returns the cached start-time when the
tip hash (its cache key) is unchanged. Under sortition a node's block can legitimately lose
the fork race, leaving the tip unchanged, so the cached "mine now" would make the loop spin
re-mining the same height. The guard stands the node down until the tip advances. It is a
pure function of the disabled flag off sortition chains, so zero cost there.

## 3. Reveal-input switch (`CreateBlockSignature`)

The Phase-3a reveal embed is unchanged in wire format; only the VRF **input** switches on
sortition heights:

```cpp
if(g_wpoa_vrf_enabled)
{
    std::vector<unsigned char> vrf_input;
    if(!WPoASortitionVRFInputForBlock(block,vrf_input))
    {
        vrf_input.assign(block->hashPrevBlock.begin(),block->hashPrevBlock.end()); // Phase 3a
    }
    if(WPoAVRF::Prove(key.begin(),vrf_input.data(),vrf_input.size(),vrf_out,vrf_proof))
        lpScript->SetBlockVRF(vrf_out,WPoAVRF::OUTPUT_SIZE,vrf_proof,WPoAVRF::PROOF_SIZE);
}
```

On a sortition height the reveal is the VRF over `seed ‖ "PROPOSER" ‖ height` — i.e. the
very output whose fold is this proposer's score, so the peer that verifies the reveal can
re-score it. `WPoASortitionVRFInputForBlock` returns false off sortition heights, so 3a/3b
blocks keep the prev-hash input untouched.

## 4. Marking the proposed height (mining loop)

Right after "Block Found", once we know the mined height:

```cpp
if(pindexPrev != NULL && WPoASortitionActiveAtHeight(pindexPrev->nHeight+1))
    WPoASortitionMarkProposed(pindexPrev->nHeight+1);
```

This records the height for the anti-respin guard (§2). It fires regardless of whether
`ProcessBlockFound` ultimately wins the fork — re-mining an identical height cannot help, so
the node waits for the tip to advance either way.

---

## 5. Interaction with the existing timing/fork machinery

- **No fork-choice change.** The argmin proposing first + the network's existing first-seen
  tip selection resolve the common (single-proposer) round with one block; rare simultaneous
  qualifiers create a short fork that self-heals on the next block (accepted §11 risk).
- **`nTime`.** `UpdateTime` sets the block's `nTime = max(parent MTP+1, adjusted-now)`, so a
  node that honestly waits `delay` before mining produces `nTime ≈ parent.nTime + delay`,
  clearing the validator time bar. A node that mines early produces a too-early `nTime` and is
  rejected — the miner-side delay and the validator-side bar are the same function.
- **Mining diversity** stays bypassed for wPoA blocks (the acceptance path delegates to
  `VerifyBlockMinerWPoA` before the native diversity replay), so a legitimately self-elected
  proposer is never barred by the round-robin distance rule.
