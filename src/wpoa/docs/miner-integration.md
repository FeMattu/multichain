# `miner/miner.cpp` (wPoA Phase 2 parts)

> Documentation of the **miner-side integration** of wPoA weighted selection.
> `miner.cpp` is a large file that drives MultiChain block production; here we document
> **only** the wPoA branch added to `GetMinerAndExpectedMiningStartTime`. The rest is the
> native mining engine and is left untouched.

This is a **modified host file**, not a new module file. The change is one self-contained
branch delimited by `/* MCHN START - wPoA Phase 2 */ … /* MCHN END */`.

## 1. Where the change lives and why there

The function:

```cpp
double GetMinerAndExpectedMiningStartTime(
    CWallet *pwallet, CPubKey *lpkMiner, set<CTxDestination> *lpsMinerPool,
    double *lpdMiningStartTime, double *lpdActiveMiners, uint256 *lphLastBlockHash,
    int *lpnMemPoolSize, double wAvBlockTime)     // src/miner/miner.cpp:998
```

This function answers the miner loop's core question: **"when should this node try to
mine the next block, and with which key?"** It returns a mining *start time* (a
`double`, seconds since epoch as `mc_TimeNowAsDouble()` produces) through
`*lpdMiningStartTime` and also returns it directly; the mining loop
(`miner.cpp:1543`) sleeps until that time before attempting a block:

```cpp
if(mc_TimeNowAsDouble() < GetMinerAndExpectedMiningStartTime(pwallet, &kMiner, ...))
    ... // not yet time to mine
```

So to control **whether and when** this node mines the next block, the wPoA branch sets
`*lpdMiningStartTime` to *now* (mine immediately) or to *now + 3600 s* (effectively
"don't mine; wait for the tip to change"). This is exactly the lever the native
round-robin *mining-diversity* gate uses — the wPoA branch **replaces** that gate for
wPoA-governed heights without changing the function's contract.

The include added at the top of the file:

```cpp
#include "wpoa/wpoa_selector.h"   // miner.cpp:25 — WPoAActiveAtHeight, WPoASelectProposer
```

## 2. The added branch, line by line

Placed after the POW / genesis fast-paths and before the native diversity-timing code
(`miner.cpp:1065-1108`):

```cpp
/* MCHN START - wPoA Phase 2: weighted proposer election */
if(WPoAActiveAtHeight(pindexTip->nHeight + 1))
{
    pwallet->GetKeyFromAddressBook(kThisMiner,MC_PTP_MINE);
    *lpkMiner=kThisMiner;

    int nWPoAHeight=pindexTip->nHeight+1;
    if(!kThisMiner.IsValid())
    {
        *lpdMiningStartTime=mc_TimeNowAsDouble()+3600;
        LogPrint("wpoa","mchn-miner: wPoA height=%d no local mining key, waiting\n",nWPoAHeight);
        return *lpdMiningStartTime;
    }

    std::string sLocalAddr=CBitcoinAddress(kThisMiner.GetID()).ToString();
    uint256 hWPoASeed=pindexTip->GetBlockHash();
    std::string sProposer=WPoASelectProposer(hWPoASeed.begin(),hWPoASeed.size(),nWPoAHeight);

    if(!sProposer.empty() && sProposer==sLocalAddr)
    {
        *lpdMiningStartTime=mc_TimeNowAsDouble();
        LogPrint("wpoa","mchn-miner: wPoA height=%d elected LOCAL proposer %s, mining now\n",
                         nWPoAHeight,sLocalAddr.c_str());
    }
    else
    {
        *lpdMiningStartTime=mc_TimeNowAsDouble()+3600;
        LogPrint("wpoa","mchn-miner: wPoA height=%d proposer=%s (local=%s), waiting\n",
                         nWPoAHeight,sProposer.empty()?"(none)":sProposer.c_str(),sLocalAddr.c_str());
    }
    return *lpdMiningStartTime;
}
/* MCHN END */
```

### `if(WPoAActiveAtHeight(pindexTip->nHeight + 1))`
- `pindexTip` is the current chain tip (a `CBlockIndex*` already in scope in this
  function); `pindexTip->nHeight` is its height. The next block to mine is therefore at
  height `nHeight + 1`.
- `WPoAActiveAtHeight(...)` (from `wpoa_selector.cpp`) returns true only if `-enablewpoa`
  is set, the chain is a permissioned MultiChain chain, and the height is at/after the
  setup period. If it returns false, the branch is skipped entirely and the native
  diversity code below runs — **zero behavioral change when wPoA is off**.
- Asking about `tip+1` (the height being mined) is what keeps the miner and validator in
  agreement: the validator asks `WPoAActiveAtHeight(receivedHeight)` for the same block.

### Resolving the local mining key
```cpp
pwallet->GetKeyFromAddressBook(kThisMiner,MC_PTP_MINE);
*lpkMiner=kThisMiner;
```
- `GetKeyFromAddressBook(kThisMiner, MC_PTP_MINE)` fills `kThisMiner` (a `CPubKey`, in
  scope) with a wallet key that holds **mine** permission — this node's validator
  identity. `MC_PTP_MINE` is the mining-permission bit.
- `*lpkMiner = kThisMiner` publishes the chosen key back to the caller (the mining loop
  signs the block with it). This must be set on **every** return path so the caller has a
  key regardless of the election outcome.

### No local mining key → wait
```cpp
if(!kThisMiner.IsValid())
{
    *lpdMiningStartTime=mc_TimeNowAsDouble()+3600;
    LogPrint("wpoa", "... no local mining key, waiting\n", nWPoAHeight);
    return *lpdMiningStartTime;
}
```
- If the wallet has no mine-permissioned key, `kThisMiner` is invalid — this node is not
  a validator and cannot be elected. Set the start time **one hour in the future** so the
  mining loop idles. The caching path earlier in the function returns this same value on
  subsequent polls of the *same* tip, so the node stays idle cheaply until the tip
  advances (at which point this decision is recomputed).
- `mc_TimeNowAsDouble()` is MultiChain's high-resolution wall-clock (seconds as a
  `double`). `+3600` is the idle sentinel used throughout this branch.
- `LogPrint("wpoa", …)` only emits under `-debug=wpoa`.

### Compute the seed and elect
```cpp
std::string sLocalAddr=CBitcoinAddress(kThisMiner.GetID()).ToString();
uint256 hWPoASeed=pindexTip->GetBlockHash();
std::string sProposer=WPoASelectProposer(hWPoASeed.begin(),hWPoASeed.size(),nWPoAHeight);
```
- `sLocalAddr` — this node's validator address, rendered exactly as the weight registry
  stores it: `CBitcoinAddress(pubkey.GetID()).ToString()`. `GetID()` is the hash160 of
  the pubkey; `CBitcoinAddress(...).ToString()` is the Base58Check string. **It must
  match the registry key format**, or `sProposer==sLocalAddr` could never be true — this
  is why the same construction is used here, in `ResolveLocalAddress` (Phase 1), and in
  the validator.
- `hWPoASeed=pindexTip->GetBlockHash()` — the seed is the **previous** block hash, i.e.
  the hash of the current tip (block `h−1` relative to the block `h = tip+1` being
  mined). `uint256` is the 256-bit hash type.
- `WPoASelectProposer(hWPoASeed.begin(), hWPoASeed.size(), nWPoAHeight)` — `begin()`
  yields a pointer to the 32 raw hash bytes and `size()` their count (32). The function
  reads the confirmed weight map and returns the elected proposer's address. `nWPoAHeight`
  is passed for logging/forward-compat only (Phase 2 seeds from the hash alone).

### Elected → mine now; else → wait
```cpp
if(!sProposer.empty() && sProposer==sLocalAddr)
    *lpdMiningStartTime=mc_TimeNowAsDouble();          // mine now
else
    *lpdMiningStartTime=mc_TimeNowAsDouble()+3600;     // wait
return *lpdMiningStartTime;
```
- **Elected** (`sProposer` non-empty and equal to this node's address): set start time to
  *now* → the mining loop attempts the block immediately. The comment explains why no
  time-staggering is applied: Phase 2 is deterministic (exactly one proposer per height,
  serialized by the prev-hash chain dependency), so there is no proposer contention to
  spread out — unlike the native diversity gate, which staggers several eligible miners.
- **Not elected** (another address won, or `""` because weights aren't available yet):
  start time *now + 3600 s* → idle until the tip advances and the election is recomputed.
- The single `return` hands the start time back to the mining loop.

## 3. Effect on the native path

When `WPoAActiveAtHeight(tip+1)` is **false**, none of the above runs and execution falls
through to the unchanged native timing code (`miner.cpp:1110+`): mining turnover, drift,
target spacing, the `dExpectedTime*` computation, etc. So:

- `-enablewpoa` **off** → the native round-robin mining-diversity behavior is preserved
  exactly.
- `-enablewpoa` **on**, height `< setupfirstblocks` → still native (bootstrap).
- `-enablewpoa` **on**, height `>= setupfirstblocks` → the wPoA branch governs, and
  exactly one node mines each height.

## 4. Connections to the other files

```mermaid
flowchart LR
    ML["mining loop<br/>miner.cpp:1543"] -->|polls| GM["GetMinerAndExpectedMiningStartTime<br/>miner.cpp:998"]
    GM -->|WPoAActiveAtHeight(tip+1)| SEL["wpoa_selector.cpp"]
    GM -->|seed = hash(tip)<br/>WPoASelectProposer| SEL
    SEL -->|GetAllNodesWeights| REG["StreamWeightRegistry (Phase 1)"]
    GM -->|start time = now / now+3600| ML
    ML -->|if elected| SIGN["sign & broadcast block with kThisMiner"]
    SIGN --> VAL["validator: multichainblock.cpp<br/>(see block-validation.md)"]
```

- **`wpoa/wpoa_selector.h`** — provides `WPoAActiveAtHeight` and `WPoASelectProposer`
  (the only Phase 2 symbols this file uses). See [wpoa-selector.md](wpoa-selector.md).
- **Phase 1 registry** — reached indirectly through `WPoASelectProposer`, which reads the
  confirmed weight map.
- **`structs/base58.h`** (already included at `miner.cpp:15`) — supplies `CBitcoinAddress`
  used to render the local address.
- **The validator** (`protocol/multichainblock.cpp`) runs the *same* election on the
  receiving side and rejects any block whose signer is not the elected proposer — the
  enforcement counterpart of this file's *production* decision. See
  [block-validation.md](block-validation.md).
