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

### 2.1 The header comment — the specification in one place

Lines 4-30 are the authoritative spec of the algorithm:

```
digest_i = HMAC-SHA256(key = prev_block_hash, msg = validator_address)
u_i      = (top-64-bits(digest_i) + 1) / 2^64          ∈ (0, 1]
E_i      = -ln(u_i)                                     ∈ [0, +∞)   (Exp(1))
score_i  = E_i / w_i                                    (Exp(w_i))
proposer = argmin_i(score_i)   [ties: lexicographically smallest address]

Pr[i elected] = w_i / Σ_j w_j  (Efraimidis & Spirakis, 2006)
```

It also records the **accepted-risk** note: Phase 2 is *public and predictable* because
the seed is the plain previous block hash; the privacy fix (per-validator VRF) is
Phase 3/4 and swaps only the randomness source, not the scoring/argmin below.

### 2.2 Includes and their provenance

```cpp
#include <cmath>       // std::log
#include <limits>      // std::numeric_limits<double>::infinity()
#include <map>         // std::map (the weight map type)
#include <string>      // std::string (addresses)
#include <stdint.h>    // uint32_t (weight), uint64_t (digest fold)
#include "crypto/hmac_sha256.h"  // CHMAC_SHA256
```

- `<cmath>` → `std::log`, the natural logarithm (base *e*). Used for `E = -ln(u)`.
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

### 2.3 `WPoASelector::ComputeScore` — the per-node score

```cpp
static double ComputeScore(const unsigned char* seed, size_t seed_len,
                           const std::string& address, uint32_t weight)
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

    double E = -std::log(u);          // Exp(1)-distributed
    return E / (double)weight;         // Exp(weight)-distributed
}
```

Line by line:

- **`static double ComputeScore(...)`** — `static` = no instance needed
  (`WPoASelector::ComputeScore(...)`). Returns a `double` score; **smaller wins**.
- **Parameters:** `seed`/`seed_len` are the raw seed bytes (Phase 2: the 32 bytes of the
  previous block hash); `address` is the validator's registry-key string; `weight` its
  weight.
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
  double E = -std::log(u);        // -ln(u): Exp(1)-distributed
  return E / (double)weight;       //        Exp(weight)-distributed
  ```
  If `u` is uniform on `(0,1]`, then `-ln(u)` is Exponential(1). Dividing by `weight`
  makes `E/weight` Exponential(weight). The minimum over independent Exp(w_i) variables
  is attained by node `i` with probability `w_i / Σ w_j` — the Efraimidis–Spirakis
  result. Hence **argmin of the scores = weighted random selection**.

### 2.4 `WPoASelector::SelectProposer` — the argmin

```cpp
static std::string SelectProposer(const unsigned char* seed, size_t seed_len,
                                  const std::map<std::string, uint32_t>& weights)
{
    std::string best_addr;
    double best_score = 0.0;
    bool have = false;

    for (std::map<std::string, uint32_t>::const_iterator it = weights.begin();
         it != weights.end(); ++it)
    {
        if (it->second == 0)
            continue; // defensive: registry never stores weight 0

        double s = ComputeScore(seed, seed_len, it->first, it->second);

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
  (`GetAllNodesWeights()`). `const&` avoids copying the map.
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
  `AppInit2`. `extern` = defined elsewhere (the `.cpp`).
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

### 3.2 The flag definition

```cpp
bool g_wpoa_enabled = false;
```
The **definition** of the global declared `extern` in the header. Default `false` — with
the flag unset the node keeps its native round-robin mining-diversity behavior unchanged.

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

    std::string proposer = WPoASelector::SelectProposer(seed, seed_len, weights);

    if (fDebug)
        LogPrint("wpoa", "[wpoa] SelectProposer height=%d validators=%u -> %s\n",
                 height, (unsigned)weights.size(),
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
- **`WPoASelector::SelectProposer(seed, seed_len, weights)`** — hands the confirmed map to
  the pure core and returns the winning address. This is the single line that connects the
  node glue to the math.
- **`if (fDebug) LogPrint("wpoa", …)`** — traces the election under `-debug=wpoa`. The
  `fDebug` guard avoids building the log arguments when debugging is off;
  `proposer.empty() ? "(none)" : proposer.c_str()` prints a readable placeholder for the
  no-proposer case.

---

## 4. Connections to the other files

```mermaid
flowchart TD
    INIT["core/init.cpp<br/>g_wpoa_enabled = GetBoolArg(-enablewpoa)"] -.writes.-> FLAG["g_wpoa_enabled"]

    MINER["miner/miner.cpp<br/>GetMinerAndExpectedMiningStartTime"] -->|WPoAActiveAtHeight(tip+1)| GATE
    VALID["protocol/multichainblock.cpp<br/>VerifyBlockMinerWPoA"] -->|WPoAActiveAtHeight(h)| GATE

    subgraph selc ["wpoa_selector.cpp (glue)"]
        GATE["WPoAActiveAtHeight"] --> FLAG
        WRAP["WPoASelectProposer"]
    end
    MINER -->|seed=hash(tip)| WRAP
    VALID -->|seed=hash(h-1)| WRAP

    WRAP -->|GetAllNodesWeights| REG["StreamWeightRegistry (Phase 1)"]
    WRAP -->|SelectProposer| CORE["WPoASelector (wpoa_selector.h, pure)"]
    CORE -->|HMAC-SHA256| HMAC["crypto/hmac_sha256.h"]

    TEST["test/wpoa_selector_tests.cpp"] -.includes only.-> CORE
```

- **`wpoa_selector.h` (core) ← unit test:** the test includes only the header and links
  only HMAC-SHA256 — the entire reason the math lives in the header.
- **`wpoa_selector.cpp` → `stream_weight_registry.h`:** consumes the Phase 1 confirmed
  weight map. This is the sole dependency of Phase 2 on Phase 1.
- **`wpoa_selector.cpp` → `core/init.h`:** reads `pwalletTxsMain`; `g_wpoa_enabled` is set
  in `init.cpp`. See [node-startup.md](node-startup.md).
- **`miner/miner.cpp` and `protocol/multichainblock.cpp`** are the only callers of
  `WPoAActiveAtHeight`/`WPoASelectProposer`. See [miner-integration.md](miner-integration.md)
  and [block-validation.md](block-validation.md).
- **`crypto/hmac_sha256.h`** supplies the keyed hash that generates the per-validator
  randomness.
