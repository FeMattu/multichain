// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA Phase 3b — node-coupled glue for the RANDAO accumulator + selection seed.
// The pure accumulator/seed math lives (header-only) in randao_accumulator.h so
// it can be unit-tested without the node; this file wires that core to the
// running node: the runtime flag/lookback, the height-based activation predicate,
// the block-index walk that folds each governed block's Phase-3a VRF reveal into
// the running accumulator R_tot (memoized per block hash), and the derivation of
// the Efraimidis–Spirakis selection seed the miner and validator consume.
//
// See docs/phase3b-implementation-guide.md.

#include "wpoa/randao_accumulator.h"

#include "wpoa/wpoa_selector.h"          // WPoAVRFActiveAtHeight (the beacon gate)
#include "core/main.h"                   // CBlockIndex, CBlock, ReadBlockFromDisk,
                                         //   BLOCK_HAVE_DATA
#include "chain/chain.h"                 // CBlockIndex members (defensive; via main.h)
#include "protocol/multichainscript.h"   // mc_Script, GetBlockVRF, MC_SCR_TYPE_SCRIPTPUBKEY
#include "utils/util.h"                  // LogPrint, LogPrintf, fDebug
#include "utils/sync.h"                  // CCriticalSection, LOCK

#include <map>
#include <vector>
#include <string.h>

using namespace std;

// Default off: with the flag unset the node behaves exactly as in Phase 3a —
// selection is seeded by the plain previous block hash, no accumulator is built.
bool g_wpoa_randao_enabled = false;

// Lookback k in seed[n+1] = H(R_tot[n-k] ‖ h[n-1] ‖ n). Bound once from
// -wpoarandaolookback in AppInit2. CONSENSUS-CRITICAL (must match on all nodes).
int g_wpoa_randao_lookback = MC_WPOA_DEFAULT_RANDAO_LOOKBACK;

// ---------------------------------------------------------------------------
// Accumulator memoization.
//
// R_tot[b] depends only on R_tot[b->pprev] and b's own reveal, so a cache keyed
// by *block hash* is correct across forks/reorgs (a hash uniquely determines its
// ancestor chain). It is populated lazily and never invalidated; on restart it
// simply repopulates on first use. Access is serialized by a dedicated leaf lock
// because both the miner thread (computing the next selection seed) and the
// block-connection thread (validating a received block) read it.
// ---------------------------------------------------------------------------
static CCriticalSection cs_randao_cache;
static std::map<uint256, uint256> g_randao_cache;

// The genesis accumulator (left operand of the very first fold) as a uint256.
static uint256 GenesisAccumulator()
{
    unsigned char g[RandaoAccumulator::HASH_SIZE];
    RandaoAccumulator::Genesis(g);
    uint256 out;
    memcpy(out.begin(), g, RandaoAccumulator::HASH_SIZE);
    return out;
}

// Extract the Phase-3a VRF reveal from a block's coinbase OP_RETURN. Mirrors
// FindBlockVRF in multichainblock.cpp, but uses a *stack-local* mc_Script instead
// of mc_gState->m_TmpScript1: the accumulator runs on the miner thread too, and
// the shared validation-path scratch buffer must not be touched from there.
// Returns true and fills reveal_out/reveal_len on success.
static bool ExtractBlockReveal(const CBlock& block,
                               unsigned char* reveal_out, int* reveal_len)
{
    mc_Script scriptTmp; // local instance -> thread-safe (no shared temp buffers)

    for (unsigned int i = 0; i < block.vtx.size(); i++)
    {
        const CTransaction& tx = block.vtx[i];
        if (!tx.IsCoinBase())
        {
            continue;
        }
        for (unsigned int j = 0; j < tx.vout.size(); j++)
        {
            const CScript& spk = tx.vout[j].scriptPubKey;
            if (spk.size() == 0)
            {
                continue;
            }

            scriptTmp.Clear();
            CScript::const_iterator pc = spk.begin();
            scriptTmp.SetScript((unsigned char*)(&pc[0]), (size_t)(spk.end() - pc),
                                MC_SCR_TYPE_SCRIPTPUBKEY);

            for (int e = 0; e < scriptTmp.GetNumElements(); e++)
            {
                scriptTmp.SetElement(e);
                unsigned char proof_buf[255];
                int rsize = *reveal_len;
                int psize = sizeof(proof_buf);
                if (scriptTmp.GetBlockVRF(reveal_out, &rsize, proof_buf, &psize) == 0)
                {
                    *reveal_len = rsize;
                    return true;
                }
            }
        }
    }
    return false;
}

// R_tot at block `pindex`: the fold of every beacon-governed ancestor's reveal,
// from the first governed block up to and including `pindex`. Iterative (no
// recursion → no stack overflow on long chains) and memoized: it walks back only
// to the first cached ancestor (or the first pre-beacon block), then folds
// forward, caching each step. Returns the genesis accumulator for a NULL or
// pre-beacon `pindex`.
static uint256 GetAccumulator(const CBlockIndex* pindex)
{
    const uint256 genesis = GenesisAccumulator();

    if (pindex == NULL)
    {
        return genesis;
    }
    // Blocks before the beacon engages carry no reveal and contribute nothing;
    // the accumulator's base is the genesis value just below the first governed
    // block.
    if (!WPoAVRFActiveAtHeight(pindex->nHeight))
    {
        return genesis;
    }

    LOCK(cs_randao_cache);

    // Walk back collecting uncached, governed ancestors until we hit a cached
    // value (the base) or fall off the governed range (base = genesis).
    std::vector<const CBlockIndex*> pending;
    const CBlockIndex* p = pindex;
    uint256 rtot = genesis;
    while (p != NULL && WPoAVRFActiveAtHeight(p->nHeight))
    {
        std::map<uint256, uint256>::iterator it = g_randao_cache.find(p->GetBlockHash());
        if (it != g_randao_cache.end())
        {
            rtot = it->second;
            break;
        }
        pending.push_back(p);
        p = p->pprev;
    }

    // Fold forward: oldest pending block first.
    for (int i = (int)pending.size() - 1; i >= 0; i--)
    {
        const CBlockIndex* b = pending[i];
        unsigned char out[RandaoAccumulator::HASH_SIZE];

        unsigned char reveal[255];
        int reveal_len = sizeof(reveal);
        CBlock blk;

        if (((b->nStatus & BLOCK_HAVE_DATA) != 0) && ReadBlockFromDisk(blk, b) &&
            ExtractBlockReveal(blk, reveal, &reveal_len))
        {
            RandaoAccumulator::Fold(rtot.begin(), reveal, (size_t)reveal_len, out);
        }
        else
        {
            // Unreachable on an accepted chain: every beacon-governed block passed
            // VerifyBlockMinerWPoA, which rejects a missing/invalid reveal. If block
            // data is somehow unavailable, fold the block hash as a deterministic
            // fallback so all nodes still agree on R_tot rather than diverging.
            uint256 h = b->GetBlockHash();
            RandaoAccumulator::Fold(rtot.begin(), h.begin(), RandaoAccumulator::HASH_SIZE, out);
            LogPrintf("[wPoA-RANDAO] WARNING: reveal unavailable for block %s (height %d); "
                      "using deterministic fallback fold\n",
                      b->GetBlockHash().ToString().c_str(), b->nHeight);
        }

        uint256 next;
        memcpy(next.begin(), out, RandaoAccumulator::HASH_SIZE);
        g_randao_cache[b->GetBlockHash()] = next;
        rtot = next;
    }

    return rtot;
}

bool WPoARANDAOActiveAtHeight(int height)
{
    // The accumulator consumes the per-block VRF reveals, so the RANDAO seed can
    // only engage where the VRF beacon already governs the height. Both are pure
    // functions of shared data (flags + chain params + height), so the miner and
    // every validator agree on which blocks are elected from the beacon seed.
    return g_wpoa_randao_enabled && WPoAVRFActiveAtHeight(height);
}

bool WPoARandaoSelectionSeed(const CBlockIndex* pindexTip, unsigned char* seed_out)
{
    if (pindexTip == NULL)
    {
        return false;
    }

    const int n = pindexTip->nHeight;
    int k = g_wpoa_randao_lookback;
    if (k < 0)
    {
        k = 0;
    }

    // Locate the ancestor at height n-k (clamped at 0). R_tot at that block is the
    // looked-back accumulator R_tot[n-k].
    int target = n - k;
    if (target < 0)
    {
        target = 0;
    }
    const CBlockIndex* pAnc = pindexTip;
    while (pAnc != NULL && pAnc->nHeight > target)
    {
        pAnc = pAnc->pprev;
    }
    uint256 rtot = GetAccumulator(pAnc);

    // h[n-1]: the block *before* the tip (thesis §5.5). Falls back to the tip hash
    // only at heights where pprev is absent — never reached once the beacon engages
    // at height >= setupfirstblocks >= 1.
    uint256 hprev = (pindexTip->pprev != NULL) ? pindexTip->pprev->GetBlockHash()
                                               : pindexTip->GetBlockHash();

    RandaoAccumulator::DeriveSeed(rtot.begin(), hprev.begin(), (uint32_t)n, seed_out);

    if (fDebug)
    {
        uint256 seed;
        memcpy(seed.begin(), seed_out, RandaoAccumulator::HASH_SIZE);
        LogPrint("wpoa", "[wPoA-RANDAO] seed for height=%d  k=%d  R_tot[%d]=%s  h[%d]=%s -> seed=%s\n",
                 n + 1, k, target, rtot.ToString().c_str(),
                 n - 1, hprev.ToString().c_str(), seed.ToString().c_str());
    }

    return true;
}
