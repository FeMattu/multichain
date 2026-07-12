# `wpoa_selector.h` + `wpoa_selector.cpp`

> Detailed technical walkthrough of the **core of wPoA (Weighted Proof-of-Authority)
> weighted miner selection — Phase 2**: the deterministic proposer election.

These two files are documented together (interface/pure core + node-coupled glue). The
split is unusual and deliberate — read §1 first.

| File | Role |
|------|------|
| `wpoa_selector.h` | Two things in one header: **(a)** the header-only, node-free `WPoASelector` class (the whole scoring + argmin **math**, defined inline), and **(b)** the *declarations* of the node-coupled glue (`g_wpoa_enabled`, `WPoAActiveAtHeight`, `WPoASelectProposer`). |
| `wpoa_selector.cpp` | The *definitions* of the node-coupled glue only: the runtime flag, the height activation predicate, and the registry-backed proposer wrapper. It does **not** re-implement any math — it calls `WPoASelector`. |

### 1. Why is the math in the header and the glue in the `.cpp`?

Because the election is **consensus-critical** and must be tested exhaustively without a
running node. The header comment states it directly:

> *"The scoring core (WPoASelector) is intentionally free of node/wallet dependencies so
> it can be unit-tested in isolation; the node-coupled glue (registry read, activation
> predicate, runtime flag) is declared at the bottom and defined in wpoa_selector.cpp."*

- **The pure core is header-only** (`static` methods defined inline in the class). A unit
  test (`test/wpoa_selector_tests.cpp`) `#include`s the header and links only
  HMAC-SHA256 + Boost.Test — no wallet, no chain, no node. That lets it run 200 000-seed
  statistical tests in milliseconds.
- **The glue must touch the node** (it reads the weight registry, the chain params, a
  global flag), so it cannot be node-free. It lives in the `.cpp`, compiled into
  `libbitcoin_wallet`, and is deliberately kept as thin as possible.

This mirrors the Phase 1 split between `weight_record.h` (pure, testable) and
`stream_weight_registry.cpp` (node-coupled). See
[weight-record.md](weight-record.md).

`static` methods (not free functions) are used for the core so the whole thing is one
self-contained, namespaced unit with no per-instance state — you never construct a
`WPoASelector`.

---

## 2. `wpoa_selector.h`

### 2.1 Includes and their provenance

```cpp
#include <cmath>       // std::log
#include <limits>      // std::numeric_limits<double>::infinity()
#include <map>         // std::map (the weight map type)
#include <string>      // std::string (addresses)
#include <stdint.h>    // uint32_t (weight), uint64_t (digest fold)
#include "crypto/hmac_sha256.h"  // CHMAC_SHA256
```

- `<cmath>` → `std::log` (natural logarithm, base *e*) and `std::sqrt`. Used for
  `E = -ln(u)` and for the weight-dumping transforms (§2.2).
- `<limits>` → `std::numeric_limits<double>::infinity()`, a portable IEEE-754 `+∞`.
  Returned for a zero-weight node so it can never be the argmin.
- `<map>`, `<string>`, `<stdint.h>` → STL/C standard types.
- `crypto/hmac_sha256.h` → **`CHMAC_SHA256`**, MultiChain/Bitcoin's HMAC-SHA256
  implementation. Its interface (from that header):
  - `static const size_t OUTPUT_SIZE = 32;` — the MAC length (32 bytes = 256 bits).
  - `CHMAC_SHA256(const unsigned char* key, size_t keylen);` — constructor takes the key.
  - `CHMAC_SHA256& Write(const unsigned char* data, size_t len);` — feeds message bytes;
    returns `*this` so calls **chain**.
  - `void Finalize(unsigned char hash[OUTPUT_SIZE]);` — writes the 32-byte MAC.

### 2.2 Weight-dumping (`-dumpfunction`) — whale compression

Before the Efraimidis–Spirakis draw, each validator weight is passed through an optional
**dumping** (damping) function. Without it, election probability is exactly proportional
to raw weight, so a validator with 100× the stake wins ~100× as often — a single
**whale** dominates block production, and its share grows without bound as it accrues more
weight. The dumping function is a **concave, strictly-increasing** transform that
*compresses* that gap while never reordering validators (a heavier node is still more
likely to be chosen — just not proportionally so).

```cpp
enum DumpingFunction
{
    DUMP_NONE = 0,   // f(w) = w         raw weight, no compression   (default)
    DUMP_LOG,        // f(w) = ln(1 + w) strong compression
    DUMP_SQRT        // f(w) = sqrt(w)   moderate compression
};

#define MC_WPOA_DEFAULT_DUMPING_FUNCTION DUMP_NONE

extern DumpingFunction g_dumping_function;   // set from -dumpfunction; defined in the .cpp
```

The transform itself is a pure static helper, so the node-free unit test can exercise
every mode directly:

```cpp
static double ApplyDumping(uint32_t weight, DumpingFunction dumping)
{
    switch (dumping)
    {
        case DUMP_SQRT: return std::sqrt((double)weight);
        case DUMP_LOG:  return std::log(1.0 + (double)weight);
        case DUMP_NONE:
        default:        return (double)weight;
    }
}
```

- **Why `ln(1 + w)` and not `ln(w)`?** The registry's smallest positive weight is `1`, and
  `ln(1) = 0` would make `E / f(w)` divide by zero → `+∞` → a weight-1 validator could
  **never** win. `ln(1 + w)` gives `ln(2) ≈ 0.693 > 0`, so every legal weight keeps a
  positive effective weight and a finite score. `sqrt(1) = 1` is fine unchanged.
- **Return type is `double`, not `int`.** The score math is already floating-point;
  truncating `sqrt`/`log` to an integer would collapse most weights to the same bucket
  (e.g. `sqrt(2) → 1`) and destroy the ordering. The effective weight stays a `double`
  all the way into `E / f(w)`.
- **Effect (measured, `test/wpoa_selector_tests.cpp`):** for weights 50 vs 500 (raw 10×),
  the heavy/light win ratio is ≈ 9.8 under `none`, ≈ 3.15 under `sqrt` (→ √10), and ≈ 1.57
  under `log` (→ ln(501)/ln(51)). Ordering is always preserved; the whale's edge shrinks.
- **CONSENSUS-CRITICAL.** The miner and every validator must apply the **same** function
  or they compute different scores, elect different proposers, and fork. This is why the
  choice is a value **threaded into the pure core** (never read from a global inside it):
  the sole binding to the runtime flag `g_dumping_function` happens once, in the node glue
  (§3.4). `g_dumping_function` is declared `extern` here and defined in `wpoa_selector.cpp`
  (§3.2), exactly like `g_wpoa_enabled`.

### 2.3 `WPoASelector::ComputeScore` — the per-node score

```cpp
static double ComputeScore(const unsigned char* seed, size_t seed_len,
                           const std::string& address, uint32_t weight,
                           DumpingFunction dumping = DUMP_NONE)
{
    if (weight == 0)
        return std::numeric_limits<double>::infinity();

    unsigned char mac[CHMAC_SHA256::OUTPUT_SIZE];
    CHMAC_SHA256(seed, seed_len)
        .Write(reinterpret_cast<const unsigned char*>(address.data()), address.size())
        .Finalize(mac);

    uint64_t d = 0;
    for (int i = 0; i < 8; i++)
        d = (d << 8) | (uint64_t)mac[i];

    const double two64 = 18446744073709551616.0; // 2^64, exact in double
    double u = ((double)d + 1.0) / two64;

    double E = -std::log(u);                     // Exp(1)-distributed
    return E / ApplyDumping(weight, dumping);    // Exp(f(weight))-distributed
}
```

Line by line:

- **`static double ComputeScore(...)`** — `static` = no instance needed
  (`WPoASelector::ComputeScore(...)`). Returns a `double` score; **smaller wins**.
- **Parameters:** `seed`/`seed_len` are the raw seed bytes (Phase 2: the 32 bytes of the
  previous block hash); `address` is the validator's registry-key string; `weight` its
  weight; `dumping` selects the weight-dumping transform (§2.2, default `DUMP_NONE`). The
  default keeps every existing caller and unit test byte-for-byte unchanged; the node glue
  passes the configured `g_dumping_function`.
- **`if (weight == 0) return …infinity();`** — a zero-weight node gets `+∞`, so it can
  never be the minimum. Defensive: the registry never stores weight 0 (Phase 1 rejects
  it), but the core must not assume its caller filtered.
- **`unsigned char mac[CHMAC_SHA256::OUTPUT_SIZE];`** — a 32-byte stack buffer for the
  MAC. Using the class constant keeps it correct if the primitive ever changes.
- **The HMAC computation** — one chained expression:
  - `CHMAC_SHA256(seed, seed_len)` constructs the hasher **keyed by the seed**. This is
    the crux of Efraimidis–Spirakis here: the *seed is the key*, the *address is the
    message*, so each validator gets an independent pseudo-random value that every node
    can reproduce from public data.
  - `.Write(reinterpret_cast<const unsigned char*>(address.data()), address.size())`
    feeds the address bytes. `address.data()` returns a `const char*`;
    `reinterpret_cast<const unsigned char*>` reinterprets those same bytes as unsigned
    (no copy, no conversion) because `Write` wants `unsigned char*`. `address.size()` is
    the byte length.
  - `.Finalize(mac)` writes the 32-byte result into `mac`. The chaining works because
    `Write` returns `CHMAC_SHA256&`.
- **Folding the top 64 bits:**
  ```cpp
  uint64_t d = 0;
  for (int i = 0; i < 8; i++) d = (d << 8) | (uint64_t)mac[i];
  ```
  Takes the first 8 bytes of the MAC, most-significant first (**big-endian**):
  each iteration shifts the accumulator left one byte (`<< 8`) and ORs in the next byte.
  After 8 iterations `d` holds `mac[0..7]` as a 64-bit integer. Only 8 bytes are used
  because a `double` has a 53-bit mantissa — 64 bits already exceeds what the later
  floating-point math can resolve, so more bytes cannot change the outcome (comment
  lines 78-81).
- **Normalize to (0, 1]:**
  ```cpp
  const double two64 = 18446744073709551616.0; // 2^64
  double u = ((double)d + 1.0) / two64;
  ```
  `2^64` is exactly representable in `double` (it is a power of two). `d` ranges over
  `[0, 2^64−1]`, so `d + 1` ranges over `[1, 2^64]` and `u = (d+1)/2^64` over
  `(0, 1]`. The `+ 1.0` is done **in `double`** so it never wraps the `uint64_t` (which
  would overflow to 0 at `d = 2^64−1`). This guarantees `u > 0`, so `-ln(u)` is finite;
  `u == 1` (score `0`) is a legitimate minimum reached only when `d == 2^64−1`.
- **The exponential transform:**
  ```cpp
  double E = -std::log(u);                     // -ln(u): Exp(1)-distributed
  return E / ApplyDumping(weight, dumping);    //         Exp(f(weight))-distributed
  ```
  If `u` is uniform on `(0,1]`, then `-ln(u)` is Exponential(1). Dividing by the
  **dumped** weight `f(weight)` makes the score Exponential(f(weight)). The minimum over
  independent Exp(f(w_i)) variables is attained by node `i` with probability
  `f(w_i) / Σ f(w_j)` — the Efraimidis–Spirakis result over the transformed weights. Hence
  **argmin of the scores = weighted random selection over the dumped weights**. With the
  default `DUMP_NONE`, `f(w) = w` and this is exactly `w_i / Σ w_j` as before.

### 2.4 `WPoASelector::SelectProposer` — the argmin

```cpp
static std::string SelectProposer(const unsigned char* seed, size_t seed_len,
                                  const std::map<std::string, uint32_t>& weights,
                                  DumpingFunction dumping = DUMP_NONE)
{
    std::string best_addr;
    double best_score = 0.0;
    bool have = false;

    for (std::map<std::string, uint32_t>::const_iterator it = weights.begin();
         it != weights.end(); ++it)
    {
        if (it->second == 0)
            continue; // defensive: registry never stores weight 0

        double s = ComputeScore(seed, seed_len, it->first, it->second, dumping);

        if (!have || s < best_score || (s == best_score && it->first < best_addr))
        {
            best_score = s;
            best_addr = it->first;
            have = true;
        }
    }
    return best_addr;
}
```

- **Inputs:** the same seed, plus `weights` = the `address → weight` map from Phase 1
  (`GetAllNodesWeights()`; `const&` avoids copying the map), plus `dumping` — the
  weight-dumping function (§2.2) applied to every weight before the draw. It is threaded
  straight through to each `ComputeScore`, so the whole election runs under one consistent
  transform. Defaults to `DUMP_NONE`; the glue supplies `g_dumping_function`.
- **`best_addr` / `best_score` / `have`** — the running argmin. `have` distinguishes
  "no candidate yet" from a genuine score of `0.0` (which is possible — see §2.3).
- **Iteration** with a `const_iterator` (`it->first` = address, `it->second` = weight).
  Pre-C++11 style, matching the codebase.
- **`if (it->second == 0) continue;`** — skip zero weights defensively.
- **The winner test** is the total order from the spec:
  ```
  !have                                  → first candidate always taken
  || s < best_score                      → strictly smaller score wins
  || (s == best_score && it->first < best_addr)  → exact tie: smaller address wins
  ```
  This is written so the result is **independent of iteration order**: whichever order
  the map yields, the same `(score, address)` pair is globally minimal. That
  order-independence is *why* Phase 2 uses argmin rather than a cumulative-range walk
  (which would depend on a canonical order) — see
  [phase2-implementation-guide.md §5.1](phase2-implementation-guide.md#5-design-decisions).
- **Return** the winning address, or `""` (default-constructed `std::string`) if the map
  had no positive-weight entry.

### 2.5 The node-glue declarations (bottom of the header)

```cpp
extern bool g_wpoa_enabled;
bool WPoAActiveAtHeight(int height);
std::string WPoASelectProposer(const unsigned char* seed, size_t seed_len, int height);
```

These are **declarations only** — defined in the `.cpp`. They are the boundary between
the pure core and the node:

- `extern bool g_wpoa_enabled;` — the runtime flag, set once from `-enablewpoa` in
  `AppInit2`.
- `WPoAActiveAtHeight(int height)` — the activation predicate (is wPoA governing this
  height?).
- `WPoASelectProposer(...)` — the registry-backed convenience wrapper the miner and
  validator actually call. `height` is carried for logging and Phase 4
  forward-compatibility; in Phase 2 the seed is the previous block hash alone.

They are declared in this header (not a separate one) so the miner/validator/`init`
only need a single `#include "wpoa/wpoa_selector.h"`.

---

## 3. `wpoa_selector.cpp` — the node glue

### 3.1 Includes

```cpp
#include "wpoa/wpoa_selector.h"          // the declarations above + the pure core
#include "wpoa/stream_weight_registry.h" // StreamWeightRegistry, GetAllNodesWeights
#include "core/init.h"                   // pwalletTxsMain
#include "utils/util.h"                  // LogPrint, LogPrintf, fDebug
#include "chainparams/state.h"           // mc_gState, IsProtocolMultichain,
                                         //   GetInt64Param, MCP_ANYONE_CAN_MINE
```

Each include is the source of the symbols used:
- `stream_weight_registry.h` → the Phase 1 `StreamWeightRegistry` class and its
  `GetAllNodesWeights()`.
- `init.h` → the global `pwalletTxsMain` (the wallet-txs DB pointer).
- `util.h` → `LogPrint(category, …)` (category-gated logging), `LogPrintf` (always-on),
  and `fDebug` (the master debug flag).
- `chainparams/state.h` → `mc_gState` (global state singleton), the network-params
  accessors `IsProtocolMultichain()` / `GetInt64Param(...)`, and the `MCP_ANYONE_CAN_MINE`
  macro.

### 3.2 The flag definitions

```cpp
bool g_wpoa_enabled = false;
DumpingFunction g_dumping_function = MC_WPOA_DEFAULT_DUMPING_FUNCTION;   // = DUMP_NONE
```
The **definitions** of the two globals declared `extern` in the header. `g_wpoa_enabled`
defaults `false` — with the flag unset the node keeps its native round-robin
mining-diversity behavior unchanged. `g_dumping_function` defaults `DUMP_NONE` — raw
weights, so an operator who never sets `-dumpfunction` gets the undamped Efraimidis–Spirakis
distribution. Both are written once, on the init thread, before any miner/validator thread
reads them (§node-startup), so they need no lock.

A file-local `DumpingFunctionName()` helper maps the enum to `"none"`/`"sqrt"`/`"log"` for
the debug log only — it never influences selection.

### 3.3 `WPoAActiveAtHeight` — the activation predicate

```cpp
bool WPoAActiveAtHeight(int height)
{
    if (!g_wpoa_enabled)                                        return false;
    if (mc_gState == NULL || mc_gState->m_NetworkParams == NULL) return false;
    if (!mc_gState->m_NetworkParams->IsProtocolMultichain())    return false;
    if (MCP_ANYONE_CAN_MINE)                                    return false;

    int setup_blocks = (int)mc_gState->m_NetworkParams->GetInt64Param("setupfirstblocks");
    return height >= setup_blocks;
}
```

Four gates, then the height check — **every one must pass** for wPoA to govern `height`:

1. **`!g_wpoa_enabled` → false.** Opt-in: an unflagged node is byte-for-byte native.
2. **null `mc_gState`/`m_NetworkParams` → false.** Defensive; these are set up early in
   startup but the predicate must be safe if called before then.
3. **`!IsProtocolMultichain()` → false.** wPoA is a MultiChain-protocol,
   permissioned-miner mechanism; it does not apply to a plain-Bitcoin-protocol chain.
4. **`MCP_ANYONE_CAN_MINE` → false.** If anyone may mine (no miner permission), there is
   no permissioned validator set to weight, so wPoA does not apply. `MCP_ANYONE_CAN_MINE`
   is a MultiChain chain-parameter macro.
5. **`height >= setupfirstblocks`.** `GetInt64Param("setupfirstblocks")` reads the chain's
   setup period (the initial blocks where the admin bootstraps permissions and the weight
   stream). wPoA engages only at/after it, so the chain bootstraps under native rules and
   weights have time to converge.

The comment (lines 43-47) records the key invariant: because this is a **pure function
of the height and chain params**, the miner (asking about `tip+1`) and the validator
(asking about the received block's height) **always agree** on whether a given block is
governed by wPoA. That agreement is what prevents a fork at the native↔wPoA boundary.

### 3.4 `WPoASelectProposer` — registry-backed election

```cpp
std::string WPoASelectProposer(const unsigned char* seed, size_t seed_len, int height)
{
    if (pwalletTxsMain == NULL)
        return "";

    StreamWeightRegistry registry(pwalletTxsMain);
    std::map<std::string, uint32_t> weights = registry.GetAllNodesWeights();

    std::string proposer = WPoASelector::SelectProposer(seed, seed_len, weights,
                                                        g_dumping_function);

    if (fDebug)
        LogPrint("wpoa", "[wpoa] SelectProposer height=%d validators=%u dumping=%s -> %s\n",
                 height, (unsigned)weights.size(),
                 DumpingFunctionName(g_dumping_function),
                 proposer.empty() ? "(none)" : proposer.c_str());

    return proposer;
}
```

- **`if (pwalletTxsMain == NULL) return "";`** — no wallet/tx store → no weight map → no
  proposer. The callers treat `""` as "cannot elect" (the miner waits; the validator is
  lenient — see [block-validation.md](block-validation.md)).
- **`StreamWeightRegistry registry(pwalletTxsMain);`** — constructs a short-lived Phase 1
  registry over the borrowed wallet-txs pointer. Cheap; no state persists between calls.
- **`registry.GetAllNodesWeights()`** — returns the **confirmed** `address → weight` map
  (mempool excluded, newest-record-wins), read via the non-WRP self-locking wallet API,
  so this is safe to call from the miner thread *and* the validation thread. See
  [stream-weight-registry.md](stream-weight-registry.md) §2.7.
- **`WPoASelector::SelectProposer(seed, seed_len, weights, g_dumping_function)`** — hands
  the confirmed map *and the configured dumping function* to the pure core and returns the
  winning address. This is the single line that connects the node glue to the math, and the
  **only** place `g_dumping_function` is read — so the pure core stays node-free and every
  height on this node is elected under one consistent transform (§2.2).
- **`if (fDebug) LogPrint("wpoa", …)`** — traces the election under `-debug=wpoa`, now
  including `dumping=%s` (via `DumpingFunctionName`) so an operator can confirm from
  `debug.log` which transform is live. The `fDebug` guard avoids building the log arguments
  when debugging is off; `proposer.empty() ? "(none)" : proposer.c_str()` prints a readable
  placeholder for the no-proposer case.

---

## 4. Connections to the other files

```mermaid
flowchart TD
    INIT["core/init.cpp<br/>g_wpoa_enabled = GetBoolArg(-enablewpoa)<br/>g_dumping_function = parse(-dumpfunction)"] -.writes.-> FLAG["g_wpoa_enabled"]
    INIT -.writes.-> DUMP["g_dumping_function"]

    MINER["miner/miner.cpp<br/>GetMinerAndExpectedMiningStartTime"] -->|"WPoAActiveAtHeight(tip+1)"| GATE
    VALID["protocol/multichainblock.cpp<br/>VerifyBlockMinerWPoA"] -->|"WPoAActiveAtHeight(h)"| GATE

    subgraph selc ["wpoa_selector.cpp (glue)"]
        GATE["WPoAActiveAtHeight"] --> FLAG
        WRAP["WPoASelectProposer"] --> DUMP
    end
    MINER -->|"seed=hash(tip)"| WRAP
    VALID -->|"seed=hash(h-1)"| WRAP

    WRAP -->|"GetAllNodesWeights"| REG["StreamWeightRegistry (Phase 1)"]
    WRAP -->|"SelectProposer(…, g_dumping_function)"| CORE["WPoASelector (wpoa_selector.h, pure)"]
    CORE -->|"HMAC-SHA256"| HMAC["crypto/hmac_sha256.h"]

    TEST["test/wpoa_selector_tests.cpp"] -.includes only.-> CORE
```

- **`wpoa_selector.h` (core) ← unit test:** the test includes only the header and links
  only HMAC-SHA256 — the entire reason the math lives in the header.
- **`wpoa_selector.cpp` → `stream_weight_registry.h`:** consumes the Phase 1 confirmed
  weight map. This is the sole dependency of Phase 2 on Phase 1.
- **`wpoa_selector.cpp` → `core/init.h`:** reads `pwalletTxsMain`; `g_wpoa_enabled` and
  `g_dumping_function` are set in `init.cpp` from `-enablewpoa` and `-dumpfunction`. See
  [node-startup.md](node-startup.md).
- **`miner/miner.cpp` and `protocol/multichainblock.cpp`** are the only callers of
  `WPoAActiveAtHeight`/`WPoASelectProposer`. See [miner-integration.md](miner-integration.md)
  and [block-validation.md](block-validation.md).
- **`crypto/hmac_sha256.h`** supplies the keyed hash that generates the per-validator
  randomness.
