# Score-aware activation — the argmin proposes even after a worse block

> **Type:** reference · **Register:** technical-direct · **Verified against the code:**
> 2026-09-26, commit `3d2fc551`
>
> Why a node whose own round is still running holds back a worse-scored block for that
> round, and how: the round state in [`private_sortition.cpp`](../src/wpoa/private_sortition.cpp),
> the hold in `FindMostWorkChain` and the relay in `ProcessNewBlock`
> ([`main.cpp`](../src/core/main.cpp)), the release in the mining loop
> ([`miner.cpp`](../src/miner/miner.cpp)), the fork choice forced on in `AppInit2`
> ([`init.cpp`](../src/core/init.cpp)). The miner-side detail is in
> [sortition-miner.md §7](sortition-miner.md#7-score-aware-activation-the-miners-part); the
> fork choice itself in
> [wpoa-weight-engine-architecture.md §3.6](wpoa-weight-engine-architecture.md#36-fork-choice-the-true-score-in-the-chain-comparator).

## The problem it closes

Under private sortition the argmin i\* of a round should propose the block. On the
regional 23h run (`run-wpoa-core-regional-malus-20260924T222732Z`) 13.2 % of rounds were
won by someone else, and the score tie-break could not correct a single one of them.

The tie-break chooses between two blocks at the same height. In those rounds there was
only one. i\* received a worse-scored block B for its own round before its slot came, and
connected it, because B was valid and the only block at that height:

1. `ConnectTip` removed B's transactions from the mempool and moved `pcoinsTip` past the
   parent;
2. the tip changed, so the miner's countdown for the parent was dropped
   (`[wpoa-fork] retarget-abort`);
3. i\* never proposed, and the inversion was final.

## The rule

A node whose own round is still running does not let a worse-scored block for that round
become its tip. It stores and validates the block, but keeps the parent as its tip until
its own slot comes.

Because the tip does not move, nothing else moves either: the mempool and the UTXO view
are still the parent's, and the miner's countdown and retarget guard see the parent they
expect. When the slot opens, `CreateNewBlock` builds exactly the block it would have built
had B never arrived, **with its transactions**. The fork choice then prefers it over B on
every node that sees both, and the nodes that had already connected B reorganise one block.

A block is held back only when all of these hold (`WPoASortitionShouldDeferActivation`):

| condition | why |
|---|---|
| it is a direct child of the parent this node is counting down for, at that height | anything deeper already has more work, and more work wins as it always did |
| its true score is known and strictly worse than this node's own | a better block is the rightful winner; an unknown score gives no ground to prefer ours |
| it was not mined by this node | our own block is never held back |
| this node has not proposed for that height yet | once our block is out the fork choice decides |
| the slot plus `MC_WPOA_DEFER_GRACE_S` (2 s) has not passed | a node that cannot produce its block must not hold the chain back |

Only the nodes whose own score beats B hold it back. All the others connect B as before.

## The pieces

- **Round state.** Each time the miner computes a countdown it records the parent, the
  height, its own true score and the local time its slot opens
  (`WPoASortitionSetPendingRound`), under a leaf lock.
- **The hold.** `FindMostWorkChain` skips a held candidate while building its candidate
  set. The tip then stays the best candidate and `ActivateBestChain` has nothing to do.
- **Relay.** Relay is tied to tip advance in this codebase, and a held block does not
  advance the tip. `ProcessNewBlock` therefore relays each held block once, right after
  `ActivateBestChain`, outside `cs_main` (`WPoASortitionTakeDeferredRelay`). Without that,
  a node holding B back would also stop propagating it.
- **Release.** If the slot and its grace pass without a block of ours (creation failed,
  mining paused), the miner loop reruns `ActivateBestChain` once
  (`WPoASortitionDeferralExpired`), and B becomes the tip after all.
- **Fork choice always on.** Holding B back only helps if the second block wins, and only
  the score tie-break makes it win. `g_wpoa_fork_score_enabled` is therefore set to
  `g_wpoa_sortition_enabled` at startup. The former `-enablewpoaforkscore` switch is gone,
  and the harness refuses the old `runtime.fork_score` key.

## Log lines (`-debug=wpoafork`)

```
[wpoa-fork] defer height=<h> hash=<B> score=<B's score> own=<ours> slot_in=<s>
[wpoa-fork] defer-release height=<h> reason=grace-expired
```

`defer` is logged once per held block. A `defer` followed by a `displace` at the same
height is an inversion this mechanism corrected; a `defer-release` is one it could not.

## What it costs

More same-height forks, by design: every inversion the node can still correct becomes a
one-block fork that the score tie-break closes. For at most one slot, a node that is
holding a block back reports a tip one block behind its peers. Safety does not change:
the set of valid blocks is the same, and only the choice among them changes.

## What it does not cover

- A node that has not yet computed its countdown for the parent when B arrives cannot
  hold B back. The miner loop recomputes about once per second, and B arrives no earlier
  than `T_block(1 − δ)` after the parent, so in practice the round state is always ready.
- If i\* is offline, nobody holds B back and B wins, which is the liveness fallback.
