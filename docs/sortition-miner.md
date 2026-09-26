# `miner/miner.cpp` — the Phase 4 miner-side hooks

> **Type:** reference · **Register:** technical-direct · **Verified against the code:**
> 2026-09-26, commit `3d2fc551`
>
> The **miner side of private sortition**: score-timed self-election, the already-proposed
> guard, the retarget abort that pins a block to the parent its countdown was earned for,
> the reveal-input switch, the proposed-height bookkeeping, and the miner's part in the
> score-aware activation. The helpers called here are
> in [private-sortition.md](private-sortition.md); the receiving side is
> [sortition-validator.md](sortition-validator.md); the Phase 2 branch that follows is
> [miner-integration.md](miner-integration.md).

Phase 4 touches the miner in six places, all gated on `WPoASortitionActiveAtHeight`:

1. a **score-timed self-election** branch in `GetMinerAndExpectedMiningStartTime`;
2. an **already-proposed guard** at the top of the same function;
3. a **retarget abort** in `CreateNewBlock`, fed by the mining loop;
4. a **reveal-input switch** in `CreateBlockSignature`;
5. a **`WPoASortitionMarkProposed`** call in the mining loop after a block is found;
6. the **score-aware activation** hooks: the round state recorded with each countdown, and
   the release of a held block at the top of the mining loop.

---

## 1. Score-timed self-election (`GetMinerAndExpectedMiningStartTime`)

The sortition branch is placed **before** the Phase 2 branch, because sortition heights are
a strict subset of wPoA heights and must take this path:

```cpp
if(WPoASortitionActiveAtHeight(pindexTip->nHeight + 1))
{
    pwallet->GetKeyFromAddressBook(kThisMiner,MC_PTP_MINE);
    *lpkMiner=kThisMiner;
    int nHeight=pindexTip->nHeight+1;

    if(!kThisMiner.IsValid()) { wait 3600 s; return; }          // no mining key

    CKey kMinerSecret;
    if(!pwallet->GetKey(kThisMiner.GetID(),kMinerSecret)) { wait 3600 s; return; }
    std::string sLocalAddr=CBitcoinAddress(kThisMiner.GetID()).ToString();

    double dScore=0.0,dDelay=0.0;
    if(!WPoASortitionLocalScoreDelay(pindexTip,sLocalAddr,kMinerSecret.begin(),&dScore,&dDelay))
    {
        if(WPoAShouldFallBackToNative(false,WPoAEverElectable()))
            goto wpoa_native_fallback;                          // bootstrap window
        wait 3600 s; return;                                    // activated, unscoreable now
    }

    double dAnchor = (double)pindexTip->GetBlockTime() - (double)GetTimeOffset();
    *lpdMiningStartTime = std::max(mc_TimeNowAsDouble(), dAnchor + dDelay);   // score-timed, parent-anchored
    WPoASortitionSetPendingRound(pindexTip->GetBlockHash(),nHeight,dScore,*lpdMiningStartTime);
    return *lpdMiningStartTime;
}
```

- The node computes **only its own** score — it holds only its own secret key — and sets its
  mining start to `parent.nTime + D(score)`, moved to the local clock through the network
  time offset. Lower score ⇒ earlier start ⇒ the argmin proposes first. A node with a worse
  score than the block that arrives sees the new tip and stands down; a node with a better
  one holds that block back and proposes its own (§7).
- **`WPoASortitionSetPendingRound`** records the round the countdown is for: parent, height,
  own true score, local slot time. The score-aware activation reads it (§7).
- **The countdown is anchored at the parent's timestamp, not at "now".** The validator
  measures the bar from the same instant (`parent.nTime + ⌊D⌋`,
  [sortition-validator.md](sortition-validator.md)). Anchoring at the moment the node had
  finished processing the parent gave the parent's own proposer a head start equal to
  everyone else's receive-and-validate time. On the regional 23h run that was ≈ 1.5 s and
  growing: 87 % of real inversions went to the outgoing miner, and the same lag was added
  to every block interval. A node that finishes processing the parent after its own slot
  has passed starts at once (`max(now, …)`), since the bar is already satisfied.
- `WPoASortitionLocalScoreDelay` goes through `WPoABuildRoundContext`, the same function the
  audit RPCs use: beacon seed over the tip, registry as of `h − 1`, malus, damping, `W`, `Φ`
  ([private-sortition.md](private-sortition.md)).
- `kMinerSecret.begin()` is the 32-byte secret handed to `WPoAVRF::Prove` — the same idiom
  the Phase 3a reveal embed uses.
- **Scoring can fail for two very different reasons**, told apart by
  `WPoAShouldFallBackToNative`. If the registry has never carried a positive weight this is
  the bootstrap window, and with sortition on this is the branch that would otherwise stall
  a clean chain one block before `setup-first-blocks`: the round is handed to the native
  schedule ([miner-integration.md §4](miner-integration.md#4-the-native-fallback)). If wPoA
  was already active, the failure is a real outcome (unsynced, or this node unweighted) and
  the node waits.
- Every other early exit (no key, no secret) waits 3600 s; the per-tip cache keeps the node
  idle until the tip advances.

## 2. Already-proposed guard (top of the timing function)

Placed right after `pindexTip = chainActive.Tip();`, **before** the per-tip cache:

```cpp
if(WPoASortitionActiveAtHeight(pindexTip->nHeight+1) &&
   WPoASortitionAlreadyProposed(pindexTip->nHeight+1))
{
    ... set kMiner, *lpdMiningStartTime = now + 3600, hash/mempool ...
    return *lpdMiningStartTime;                                 // stand down
}
```

The timing function returns the cached start time while the tip hash (its cache key) is
unchanged. Under sortition a node's block can legitimately lose the race, leaving the tip
unchanged, so the cached "mine now" would make the loop re-mine the same height forever. The
guard stands the node down until the tip advances; placing it before the cache makes it hold
on cache hits too. Off sortition chains `WPoASortitionActiveAtHeight` short-circuits on the
disabled flag, so it costs nothing there. The proposed height is kept under the leaf lock
`cs_sortition_proposed`.

## 3. Retarget abort (`CreateNewBlock` and the mining loop)

A mining attempt reads the tip **three** times: the loop's own read, the timing function
(which takes no lock), and `CreateNewBlock` — and only the third fixes `hashPrevBlock`.
Nothing holds `cs_main` across the gap, so the tip can advance in between. Before this guard
the retarget was silent: the block was built one height above the one whose delay had been
computed and waited out, and the node's own validator rejected it as *mined too early for
its sortition score*.

The mining loop therefore passes down the parent the countdown was earned for —
`hLastBlockHash`, which **is** the timing function's cache key:

```cpp
bool fStaleParent=false;
auto_ptr<CBlockTemplate> pblocktemplate(CreateNewBlock(scriptPubKey,pwallet,&kMiner,&canMine,&pindexPrev,
                                                       &hLastBlockHash,&fStaleParent));
if(fStaleParent)
{
    // drop the attempt; the next iteration earns a fresh countdown against the new tip
    continue;
}
```

and `CreateNewBlock` refuses, **inside the same `cs_main` acquisition that reads the tip**:

```cpp
if( (phExpectedPrev != NULL) && WPoASortitionActiveAtHeight(nHeight) &&
    (pindexPrev->GetBlockHash() != *phExpectedPrev) )
{
    *lpfStaleParent=true;
    return NULL;
}
```

- The comparison and the read that fixes `hashPrevBlock` are one acquisition, so the check is
  race-free by construction; checking at the caller would be check-then-act.
- Dropping the attempt also keeps §5 honest: a block built on the wrong parent would mark
  the *new* height proposed on account of a block that never reaches the network, standing
  the node down for a round it never contested.
- Scoped to sortition heights, so no other MultiChain deployment changes. Traced under
  `-debug=wpoafork` (`[wpoa-fork] retarget-abort …`, `[wpoa-fork] build …`).
- With the score-aware activation (§7) a worse-scored block for our round no longer moves the
  tip, so the abort fires only when a **better**-scored block arrives: then standing down is
  the right outcome.

## 4. Reveal-input switch (`CreateBlockSignature`)

The Phase 3a reveal embed is unchanged in wire format; only the VRF **input** switches on
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

On a sortition height the reveal is the VRF over `seed ‖ "PROPOSER" ‖ height` — the very
output whose fold is this proposer's score — so the peer that verifies the reveal can
re-score it. `WPoASortitionVRFInputForBlock` returns false off sortition heights, so 3a/3b
blocks keep the prev-hash input. Detail: [vrf-prover.md](vrf-prover.md).

## 5. Marking the proposed height (mining loop)

Right after "Block Found", once the mined height is known:

```cpp
if(pindexPrev != NULL && WPoASortitionActiveAtHeight(pindexPrev->nHeight+1))
    WPoASortitionMarkProposed(pindexPrev->nHeight+1);
```

This records the height for the guard of §2. It fires whether or not `ProcessBlockFound`
wins the race — re-mining an identical height cannot help, so the node waits for the tip to
advance either way.

---

## 6. Interaction with the timing and fork machinery

- **`nTime`.** `UpdateTime` sets `nTime = max(parent MTP + 1, adjusted-now)`, so a node that
  honestly waits `D` before mining produces `nTime ≈ parent.nTime + D`, clearing the
  validator's time bar. A node that mines early produces a too-early `nTime` and is rejected:
  the miner's delay and the validator's bar are the same function (`PrivateSortition::MiningDelay`).
- **Fork choice.** The argmin proposing first resolves the common round with one block.
  When two candidates of the same round both propagate, native MultiChain would keep the
  first seen; under private sortition every node prefers the lower true score instead,
  using the score cached at admission. It is always on and does not change validity
  ([wpoa-weight-engine-architecture.md §3.6](wpoa-weight-engine-architecture.md#36-fork-choice-the-true-score-in-the-chain-comparator)).
- **Mining diversity.** Neutralised at its source on governed heights once wPoA has
  activated ([wpoa-selector.md §3.3bis](wpoa-selector.md#33bis-the-mining-diversity-hook)),
  so a legitimately self-elected proposer finds its own key and is never barred by the
  round-robin distance rule.

---

## 7. Score-aware activation: the miner's part

The rule itself, holding back a worse-scored block for the round this node is counting down
for, lives in `FindMostWorkChain` and is described in
[score-aware-activation.md](score-aware-activation.md). The miner contributes two things:

- **The round state**, recorded with every countdown (§1): without it no block is ever held
  back.
- **The release**, at the top of the mining loop, where no lock is held:

```cpp
if(WPoASortitionDeferralExpired())
{
    CValidationState stateRelease;
    ActivateBestChain(stateRelease);
}
```

A held block waits for our own block. If the slot plus `MC_WPOA_DEFER_GRACE_S` passes
without one (creation failed, mining paused, nothing to mine), nothing else would ever
reconsider the held block. `WPoASortitionDeferralExpired` returns true once in that case, and
the chain is re-evaluated so the held block becomes the tip after all.

When our block is found, §5 marks the height proposed **before** `ProcessBlockFound`. By the
time our own block is processed nothing is held back any more, and the comparator chooses
between ours and the held one on score.

