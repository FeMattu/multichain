# A local Δ_gossip hint cannot fire at the current band — evidence

> **Type:** historical record (evidence) · **Date:** 2026-09-21 · **Status:** design rejected on measurement, no code written
>
> Kept as written: it records the work as it was done and is **not** updated when the
> code changes, so paths, identifiers and line numbers may no longer match the tree.
>
> **Design it rejects:** the *local* Δ_gossip hint — a node waits, on its own decision,
> until its preferred candidate has been held for `Δ_gossip_hint` ms before starting its
> private-sortition countdown for the next height.
> **Not affected:** the consensus-rule Δ_gossip (pending pool, relay-at-admission, chain
> parameter), which remains parked and which this note does *not* evaluate.
> **Runs cited:** `run-wpoa-forkscore-1h-20260921T143502Z` (fork-score on) and
> `run-wpoa-forkscore-1h-ctl-20260921T161325Z` (control), both intercontinental CORE,
> 20 nodes, 149 sortition-governed heights each.
>
> **For the system as it is now:** [../wpoa-weight-engine-architecture.md §3.6](../wpoa-weight-engine-architecture.md#36-fork-choice-the-true-score-in-the-chain-comparator) (fork choice).

This exists so the measurement stays citable without keeping the scratch scripts. Every
figure is a measurement, not a summary of one.

## The claim

The hint's purpose is to give a competing same-height candidate time to arrive before
this node commits to building past a worse-scored one. That presupposes the node *could*
build past it inside a propagation window. It cannot: the sortition delay band already
holds it for far longer than any path on any shipped map.

## The two quantities

**Lower edge of the delay band.** Def. 5.11 gives `D_i = T_block + δ·T_block·ψ(x) + λΦ`
with `ψ ∈ (-1,1)`, so the minimum is `T_block(1-δ)`. The measured profiles run
`T_block = 10 s`, `δ = 0.5` ⇒ **5 s**. Confirmed on both runs, 149 governed heights each:

```
                       min   p05   median   p95   max
dt_prev (observed)      5s    7s     12s    16s   16s
blocks with dt_prev < 5s:  0        with dt_prev < 1s:  0
```

**Worst one-way path delay**, from `Topology.path_delay_ms` over every shipped topology:

```
smoke-4n           3.05 ms      national          11.87 ms
regional           5.14 ms      continental       27.84 ms
                                intercontinental 181.52 ms
```

**5 s against 181.5 ms: a factor of 27.** The gossip window is entirely contained inside
the mandatory delay.

## Why both readings of the mechanism are inert

The miner anchors its countdown at wall-clock time, `*lpdMiningStartTime =
mc_TimeNowAsDouble() + dDelay` (`src/miner/miner.cpp:1199`), recomputed on every tip
change because the function is memoised on the tip hash (`:1100`). So:

* **As a floor** on the start time — `max(now + dDelay, dTimeReceived + hint)` — it never
  binds: `now + dDelay ≥ dTimeReceived + 5 s` always, and any plausible hint is ≤ 0.4 s.
* **As an anchor shift** — `dTimeReceived + hint + dDelay` — it adds latency to every
  block but changes no decision: the tie-break has already had 5 s to act before the node
  can mine at all.

A third bound sits underneath both: the mining loop repolls every `__US_Sleep(100)` =
100 ms (`:1982`), so a hint below ~100 ms is not expressible even in principle. On three
of the five maps the computed hint would fall below that floor before any margin.

## It is also not the cause of the inversions we measured

In the fork-score run the chain kept a worse-scored block at 9 of 40 contested heights.
Neither candidate mechanism explains them.

**Not incomplete dissemination.** At all 9 heights every one of the 20 nodes logged the
best-scored candidate. Mean nodes that saw it: **20.0 where it won (n=31), 20.0 where it
lost (n=9)**.

**Not premature mining inside a window.** Height 239, identically on three independent
nodes:

```
cand  h=239 hash=0052ca1dea score=0.00843158528   (seen first)
cand  h=239 hash=00b17afb1c score=0.00100862313   (seen second, 8.4x better)
round h=239 selected=00b17afb1c legacy=0052ca1dea differs=1
```

Every node preferred `00b17afb1c`, within ~0.5 s of the first arrival. The chain kept
`0052ca1dea` anyway. The loss therefore happens *after* the network has already agreed:
height 240 was built on the abandoned branch and chain work pulled everyone back. No
local wait before a countdown touches that.

## What is still unknown

Which node mined 240 on the abandoned branch, and which tip its countdown was anchored
to. The `wpoafork` log records neither a candidate's parent nor the tip the miner started
counting from. Closing that needs two extra fields in the existing log lines and one short
run — it is the prerequisite for any further work on same-height inversions, and it was
not undertaken here.

## Consequence

The local Δ_gossip hint was not implemented. It would be a no-op at `δ = 0.5`,
`T_block = 10 s`. It becomes observable only if the band's lower edge approaches the
propagation time — `δ → ~0.98`, or a far shorter `T_block` — and either change moves the
protocol to a regime the existing runs do not measure.
