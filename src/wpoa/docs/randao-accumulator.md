# `randao_accumulator.{h,cpp}` — Line-by-Line Walkthrough (Phase 3b)

The Phase 3b RANDAO beacon lives in two files, split the same way as the Phase 2 selector
and the Phase 3a VRF:

- [`randao_accumulator.h`](../randao_accumulator.h) — the **pure core** (`RandaoAccumulator`:
  `Fold`, `DeriveSeed`, `Genesis`), node-free and unit-tested, plus the *declarations* of the
  node glue.
- [`randao_accumulator.cpp`](../randao_accumulator.cpp) — the **node glue**: the runtime
  flag/lookback, the activation predicate, the memoized block-index walk, reveal extraction and
  the seed helper.

This document walks both. For the design rationale and the end-to-end picture see
[phase3b-implementation-guide.md](phase3b-implementation-guide.md); for the formal model see
[thesis-project-overview.md §5.4–§5.5](thesis-project-overview.md#54-global-accumulator-update).

---

## 1. The pure core (`randao_accumulator.h`)

Header-only, depends only on `crypto/sha256.h` (`CSHA256`) plus `<stddef.h>`/`<stdint.h>`. Every
value is a fixed 32-byte blob (SHA-256 output / block hash / VRF reveal) passed as a raw pointer —
so the core never pulls in `uint256` or any node type, and the unit test links only SHA256.

### 1.1 `Genesis(unsigned char* out32)`

```
out = SHA256("wPoA-RANDAO-accumulator-genesis-v1")
```

The accumulator value *before* the first beacon-governed block — the left operand of the very
first fold. A domain-separated constant (not all-zero) so the initial state has no exploitable
structure. `strlen_const` is a tiny private helper so the header needs no `<cstring>`.

### 1.2 `Fold(rtot_prev32, reveal, reveal_len, rtot_out32)`

Implements the thesis §5.4 recurrence `R_tot[n] = H(R_tot[n-1] ⊕ H(R[n]))`:

1. `t = SHA256(reveal)` — normalizes the reveal to 32 bytes and removes structure.
2. `x[i] = rtot_prev[i] ^ t[i]` for `i in 0..31` — the XOR, built into a **local** buffer `x`
   so `rtot_out32` may alias `rtot_prev32` (in-place folding is safe).
3. `rtot_out = SHA256(x)` — the final hash breaks the linearity a bare XOR would expose.

The fold is deliberately **order-sensitive**: `Fold(Fold(g,A),B) != Fold(Fold(g,B),A)`. That is
what makes `R_tot` a function of the *ordered* reveal history — a chain, not a set.

### 1.3 `DeriveSeed(rtot_lookback32, h_prev32, height, seed_out32)`

Implements the thesis §5.5 seed `seed[n+1] = H(R_tot[n-k] ‖ h[n-1] ‖ n)`:

```
seed_out = SHA256( rtot_lookback ‖ h_prev ‖ height_be32 )
```

`height` is serialized as **4 big-endian bytes** (`height_be`) so the encoding is fixed and
platform-independent — a consensus-critical detail. `h_prev` and `height` change every block, so
the seed is fresh every round even when `rtot_lookback` changes slowly.

### 1.4 Glue declarations (bottom of the header)

`class CBlockIndex;` is forward-declared (the glue walks the index). Then:

- `extern bool g_wpoa_randao_enabled;`
- `extern int g_wpoa_randao_lookback;` + `#define MC_WPOA_DEFAULT_RANDAO_LOOKBACK 1`
- `bool WPoARANDAOActiveAtHeight(int height);`
- `bool WPoARandaoSelectionSeed(const CBlockIndex* pindexTip, unsigned char* seed_out);`

All defined in the `.cpp`; none is compiled into the node-free unit test.

---

## 2. The node glue (`randao_accumulator.cpp`)

Includes `randao_accumulator.h`, `wpoa/wpoa_selector.h` (for `WPoAVRFActiveAtHeight`),
`core/main.h` (`CBlockIndex`, `CBlock`, `ReadBlockFromDisk`, `BLOCK_HAVE_DATA`),
`protocol/multichainscript.h` (`mc_Script`, `GetBlockVRF`, `MC_SCR_TYPE_SCRIPTPUBKEY`),
`utils/util.h` (logging) and `utils/sync.h` (`CCriticalSection`, `LOCK`).

### 2.1 Globals

```cpp
bool g_wpoa_randao_enabled = false;                           // -enablewpoarandao
int  g_wpoa_randao_lookback = MC_WPOA_DEFAULT_RANDAO_LOOKBACK; // -wpoarandaolookback
static CCriticalSection cs_randao_cache;                       // leaf lock for the cache
static std::map<uint256, uint256> g_randao_cache;              // block hash -> R_tot
```

The cache is keyed by **block hash**, which is what makes it reorg-safe: a hash uniquely
determines its ancestor chain, so a fork's `R_tot` never aliases the main chain's.

### 2.2 `GenesisAccumulator()`

Wraps `RandaoAccumulator::Genesis` into a `uint256` (via `memcpy(out.begin(), g, 32)`) so the
glue can work in `uint256` while the core stays byte-oriented.

### 2.3 `ExtractBlockReveal(block, reveal_out, reveal_len)`

Mirrors `FindBlockVRF` in `multichainblock.cpp` but with a **stack-local** `mc_Script scriptTmp`
instead of `mc_gState->m_TmpScript1`. This is deliberate (see
[phase3b §5.5](phase3b-implementation-guide.md#5-design-decisions)): the accumulator runs on the
**miner** thread too, and the shared validation-path scratch must not be touched there. It scans
each coinbase output's script elements and returns the first `GetBlockVRF` suffix found.

### 2.4 `GetAccumulator(pindex)` — the memoized walk

Returns `R_tot` at `pindex`:

1. Genesis for a NULL or pre-beacon `pindex` (`!WPoAVRFActiveAtHeight(pindex->nHeight)`).
2. Under `cs_randao_cache`, walk back collecting uncached governed ancestors into `pending`,
   stopping at the first cached hash (its value is the base) or when leaving the governed range
   (base = genesis).
3. Fold forward, oldest first: for each pending block, `ReadBlockFromDisk` + `ExtractBlockReveal`,
   then `Fold(rtot, reveal, ...)`, caching the result by block hash. If a reveal is unreadable
   (unreachable on an accepted chain — every governed block passed `VerifyBlockMinerWPoA`), it
   folds the **block hash** as a deterministic fallback and logs a warning, so all nodes stay in
   agreement rather than diverging.

Iterative (no recursion → no stack overflow on long chains); amortized O(1) per block because the
walk stops at the first cached ancestor.

### 2.5 `WPoARANDAOActiveAtHeight(height)`

```cpp
return g_wpoa_randao_enabled && WPoAVRFActiveAtHeight(height);
```

The beacon consumes the per-block reveals, so it engages exactly where the VRF beacon does — and,
being a pure function of shared data, the miner and every validator agree from the height alone.

### 2.6 `WPoARandaoSelectionSeed(pindexTip, seed_out)`

Computes `seed[n+1]` for the block after `pindexTip` (height `n`):

1. `target = max(n - k, 0)`; walk `pAnc` back to that height; `rtot = GetAccumulator(pAnc)`
   (= `R_tot[n-k]`, clamped to genesis if before the first governed block).
2. `hprev = hash(pindexTip->pprev)` (= `h[n-1]`; falls back to the tip hash only where pprev is
   absent, unreachable once the beacon engages at height ≥ setup ≥ 1).
3. `DeriveSeed(rtot, hprev, n, seed_out)`.

Under `-debug=wpoa` it logs the derived seed (`[wPoA-RANDAO] seed for height=…`), which the
functional test greps as positive evidence.

Returns `false` only for a NULL tip, so the caller falls back to the prev-hash seed.

---

## 3. How the two call sites use it

Both the miner ([miner.cpp](../../miner/miner.cpp), `GetMinerAndExpectedMiningStartTime`) and the
validator ([multichainblock.cpp](../../protocol/multichainblock.cpp), `VerifyBlockMinerWPoA`) do
the same thing: default the selection seed to the previous block hash, then overwrite it with
`WPoARandaoSelectionSeed(...)` when `WPoARANDAOActiveAtHeight(...)` — the miner passing its tip,
the validator passing `pindexNew->pprev` (the same tip the honest miner saw). Because both derive
the seed from identical inputs, they always agree on the elected proposer; see
[phase3b-implementation-guide.md §7.3–§7.4](phase3b-implementation-guide.md#7-full-code-walkthrough).

---

**Related documents:**
[phase3b-implementation-guide.md](phase3b-implementation-guide.md) ·
[wpoa-selector.md](wpoa-selector.md) ·
[vrf-verifier.md](vrf-verifier.md) ·
[thesis-project-overview.md](thesis-project-overview.md)
