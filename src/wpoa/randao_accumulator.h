// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA (Weighted Proof of Authority) — Phase 3b: RANDAO accumulator + seed
// -----------------------------------------------------------------------
// Phase 3a produces one verifiable pseudorandom reveal R[n] per block (the VRF
// beacon's *generation* half). Phase 3b is the beacon's *accumulation* half: it
// folds those reveals into a running RANDAO accumulator and derives the seed the
// proposer election consumes, so selection is no longer seeded by the raw
// previous block hash (Phase 2) but by a mixed, grinding-resistant beacon value.
//
// Formal model (docs/thesis-project-overview.md §5.4–§5.5):
//
//   R_tot[n]   = H( R_tot[n-1] ⊕ H(R[n]) )                 (global accumulator)
//   seed[n+1]  = H( R_tot[n-k] ‖ h[n-1] ‖ n )              (lookback selection seed)
//
// with `H` = SHA-256, `⊕` a byte-wise XOR over 32-byte values, `R[n]` the
// Phase-3a VRF reveal carried in block n, `h[n-1]` the hash of block n-1, `n` the
// current tip height, and `k` a constant lookback that decouples the seed from
// the most recent reveals (so a validator cannot immediately steer its own next
// re-election). The reveal R[n] is unchanged from Phase 3a — its VRF input stays
// h[n-1] (the height term is (re)introduced here, via the seed's `n`, not in the
// reveal; see docs/phase3a-implementation-guide.md §4.4).
//
// WHAT CHANGES / WHAT DOES NOT. Phase 3b swaps ONLY the bytes fed to the
// Efraimidis–Spirakis selector (the "seed" argument of WPoASelectProposer); the
// scoring/argmin/tie-break and the weight-read path are untouched, so the
// election stays weight-proportional (Pr[i]=w_i/Σw). Selection is still PUBLIC
// (anyone can recompute the beacon from the public reveals) — leader
// unpredictability is Phase 4's job; Phase 3b's contribution is a proper beacon
// (grinding-resistant via VRF uniqueness, last-revealer bias bounded per Cleve).
//
// CONSENSUS-CRITICAL. The accumulator, the seed derivation and the lookback `k`
// must be bit-identical on the miner and every validator, or they elect
// different proposers and the chain forks. The math below is therefore a PURE,
// node-free core (this header) that never reads a global; the runtime flag/param
// binding and the block-index walk that feeds it live in the node glue
// (randao_accumulator.cpp), and `k` is bound to -wpoarandaolookback in exactly
// one place (AppInit2). See docs/phase3b-implementation-guide.md.

#ifndef WPOA_RANDAO_ACCUMULATOR_H
#define WPOA_RANDAO_ACCUMULATOR_H

#include <stddef.h>
#include <stdint.h>

#include "crypto/sha256.h"

/**
 * RandaoAccumulator — pure, deterministic, node-free RANDAO math.
 *
 * All methods are static and depend only on CSHA256, so they can be exercised by
 * the Boost.Test unit suite without linking the wallet / node runtime (see
 * test/randao_accumulator_tests.cpp), exactly like the Phase 2 selector core and
 * the Phase 3a VRF core. Every value is a fixed 32-byte big-endian-agnostic blob
 * (SHA-256 output / block hash / VRF reveal), passed as a raw pointer.
 */
class RandaoAccumulator
{
public:
    /** Size, in bytes, of every hash-valued quantity the accumulator handles. */
    static const size_t HASH_SIZE = 32;

    /**
     * Genesis accumulator value R_tot used *before* the first beacon-governed
     * block, i.e. the left operand of the very first fold.
     *
     * A fixed, domain-separated constant (SHA-256 of a tag) rather than all-zero,
     * so the initial accumulator has no exploitable structure and cannot collide
     * with a plausible reveal-derived value.
     *
     * @param out32  [out] HASH_SIZE bytes — the genesis accumulator.
     */
    static void Genesis(unsigned char* out32)
    {
        static const char* kTag = "wPoA-RANDAO-accumulator-genesis-v1";
        CSHA256 h;
        h.Write(reinterpret_cast<const unsigned char*>(kTag), strlen_const(kTag));
        h.Finalize(out32);
    }

    /**
     * One accumulator step: fold a validated reveal into the running value.
     *
     *   R_tot_out = H( R_tot_prev ⊕ H(reveal) )          (thesis §5.4)
     *
     * Hashing the reveal *before* the XOR normalizes its size and removes any
     * structure; the final hash of the XOR breaks the linearity that a bare XOR
     * accumulator would expose. Deterministic and associative-free (order
     * matters): the caller must fold reveals strictly in ascending block order.
     *
     * In/out aliasing is permitted (`rtot_out32` may equal `rtot_prev32`): the
     * XOR term is computed into a local buffer before the final hash writes out.
     *
     * @param rtot_prev32  HASH_SIZE bytes — R_tot[n-1].
     * @param reveal       The block-n VRF reveal R[n] (any length; typically 32).
     * @param reveal_len   Length of `reveal`.
     * @param rtot_out32   [out] HASH_SIZE bytes — R_tot[n].
     */
    static void Fold(const unsigned char* rtot_prev32,
                     const unsigned char* reveal, size_t reveal_len,
                     unsigned char* rtot_out32)
    {
        // t = H(reveal)
        unsigned char t[HASH_SIZE];
        CSHA256().Write(reveal, reveal_len).Finalize(t);

        // x = R_tot_prev ⊕ t   (into a local buffer so in/out may alias)
        unsigned char x[HASH_SIZE];
        for (size_t i = 0; i < HASH_SIZE; i++)
        {
            x[i] = (unsigned char)(rtot_prev32[i] ^ t[i]);
        }

        // R_tot_out = H(x)
        CSHA256().Write(x, HASH_SIZE).Finalize(rtot_out32);
    }

    /**
     * Derive the proposer-selection seed from the looked-back accumulator, the
     * previous block hash and the tip height:
     *
     *   seed = H( rtot_lookback ‖ h_prev ‖ height )        (thesis §5.5)
     *
     * `height` is serialized as 4 big-endian bytes so the encoding is fixed and
     * platform-independent (consensus-critical). Both `h_prev` and `height`
     * advance every block, so the seed stays fresh per round even when the
     * looked-back accumulator changes only slowly.
     *
     * @param rtot_lookback32  HASH_SIZE bytes — R_tot[n-k].
     * @param h_prev32         HASH_SIZE bytes — h[n-1].
     * @param height           The tip height `n`.
     * @param seed_out32       [out] HASH_SIZE bytes — seed[n+1].
     */
    static void DeriveSeed(const unsigned char* rtot_lookback32,
                           const unsigned char* h_prev32,
                           uint32_t height,
                           unsigned char* seed_out32)
    {
        unsigned char height_be[4];
        height_be[0] = (unsigned char)((height >> 24) & 0xff);
        height_be[1] = (unsigned char)((height >> 16) & 0xff);
        height_be[2] = (unsigned char)((height >>  8) & 0xff);
        height_be[3] = (unsigned char)( height        & 0xff);

        CSHA256()
            .Write(rtot_lookback32, HASH_SIZE)
            .Write(h_prev32, HASH_SIZE)
            .Write(height_be, sizeof(height_be))
            .Finalize(seed_out32);
    }

private:
    // Tiny constexpr-free strlen so the header stays dependency-light (no <cstring>
    // pulled into the node-free unit test's translation unit just for a tag).
    static size_t strlen_const(const char* s)
    {
        size_t n = 0;
        while (s[n] != '\0') n++;
        return n;
    }
};

// ---------------------------------------------------------------------------
// Node-coupled glue (defined in randao_accumulator.cpp; NOT compiled into the
// node-free unit test, which only uses the RandaoAccumulator core above).
// ---------------------------------------------------------------------------

class CBlockIndex;   // forward-declared: the glue walks the block index

/**
 * Set once from -enablewpoarandao in AppInit2. Default false = Phase 3a behavior:
 * selection is seeded by the plain previous block hash. Must be set uniformly
 * across the validator set (like -enablewpoa / -enablewpoavrf), or nodes disagree
 * on the elected proposer and the chain forks.
 */
extern bool g_wpoa_randao_enabled;

/**
 * Lookback distance `k` in seed[n+1] = H(R_tot[n-k] ‖ h[n-1] ‖ n). Set once from
 * -wpoarandaolookback in AppInit2 (default MC_WPOA_DEFAULT_RANDAO_LOOKBACK).
 * CONSENSUS-CRITICAL: must be identical on all nodes.
 */
extern int g_wpoa_randao_lookback;

#define MC_WPOA_DEFAULT_RANDAO_LOOKBACK 1

/**
 * True when the block at `height` must be elected from the RANDAO beacon seed
 * rather than the plain prev-block hash. Requires -enablewpoarandao AND that the
 * VRF beacon already governs the height (WPoAVRFActiveAtHeight), because the
 * accumulator consumes the per-block VRF reveals: no reveals ⇒ no beacon. Being a
 * pure function of shared data (flags + chain params + height), the miner and
 * every validator agree from the height alone.
 */
bool WPoARANDAOActiveAtHeight(int height);

/**
 * Compute the Phase-3b proposer-selection seed for the block that follows
 * `pindexTip` (i.e. seed[pindexTip->nHeight + 1]).
 *
 * Walks the block index back to R_tot[n-k] (memoized per block hash so the amortized
 * cost is O(1) per new block, reorg-safe), reads each governed ancestor's VRF reveal
 * from disk, folds them with RandaoAccumulator::Fold, and derives the seed with
 * RandaoAccumulator::DeriveSeed over (R_tot[n-k], h[n-1], n).
 *
 * The miner passes its current tip; the validator passes the parent of the block
 * under check (pindexNew->pprev) — the same tip the honest miner saw — so both
 * derive an identical seed. Returns false (and leaves `seed_out` untouched) only on
 * a degenerate/NULL tip, in which case the caller falls back to the prev-hash seed.
 *
 * @param pindexTip  Tip after which the next block is elected (may be NULL).
 * @param seed_out   [out] the 32-byte selection seed.
 * @return true if a seed was produced.
 */
bool WPoARandaoSelectionSeed(const CBlockIndex* pindexTip, unsigned char* seed_out);

#endif // WPOA_RANDAO_ACCUMULATOR_H
