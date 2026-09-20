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
//   R_tot[n]   = R_tot[n-1] ⊕ R[n]                         (global accumulator)
//   seed[n+1]  = H( R_tot[n-k] ‖ h[n] ‖ n+1 )              (lookback selection seed)
//
// with `H` = SHA-256, `⊕` a byte-wise XOR over 32-byte values, `R[n]` the
// Phase-3a VRF reveal carried in block n, `h[n]` the hash of the tip (the chain
// state actually finalized when the round opens), `n+1` the height being elected,
// and `k` a constant lookback that decouples the seed from the most recent
// reveals (so a validator cannot immediately steer its own next re-election).
// The reveal R[n] is unchanged from Phase 3a — its VRF input stays h[n-1] (the
// height term belongs to the seed, not to the reveal; see
// docs/phase3a-implementation-guide.md §4.4).
//
// THE ACCUMULATOR IS THE THESIS FORM, LITERALLY. The recurrence above is Def. 5.3 as
// stated — a bare byte-wise XOR, no hash on either side — and it is what Fold computes.
// An earlier revision of this module folded the hardened variant H(R_tot[n-1] ⊕ H(R[n]))
// instead; it was realigned to the definition because the hardening bought nothing here:
//
//   * the outer hash was redundant — nothing consumes R_tot raw. DeriveSeed hashes it
//     together with h[n] and the height, so the bytes the selector actually scores are a
//     SHA-256 digest either way; hashing twice does not make the seed more uniform.
//   * the linearity argument did not apply — a bare XOR accumulator is algebraically
//     linear, so a last revealer FREE TO CHOOSE its reveal could cancel the contributions
//     before it. Here the reveal is a VRF output: by uniqueness (see vrf_wrapper.h) exactly
//     one R[n] is valid for a given key and input, and any other value fails
//     VerifyBlockMinerWPoA. There is no choice left to exploit, so there was no algebraic
//     handle for the outer hash to remove.
//   * the inner hash had nothing to normalize — R[n] is fixed-width 32 bytes on the wire
//     (WPoAVRF::OUTPUT_SIZE) and WPoAVRF::Verify rejects any other length, so a governed
//     block's reveal is always exactly one accumulator word wide.
//
// WHAT THE PURE FORM GIVES UP, AND WHY IT IS UNREACHABLE. XOR is commutative and every
// value is its own inverse, so R_tot[n] is a function of the MULTISET of reveals rather
// than of their order, and the same reveal folded twice cancels itself. Neither is
// reachable on a chain: a chain fixes the order of its own blocks, and the Phase-3a VRF
// input is the parent hash h[n-1], distinct at every height, so two governed blocks on one
// branch cannot carry the same reveal. Ordering is in any case re-bound downstream —
// seed[n+1] commits to h[n] and to n+1, both of which are position-dependent.
//
// CONSENSUS BREAK. The fold defines every seed, so this change elects different proposers
// from the same reveals. It is not backward compatible: a chain already running with
// -enablewpoarandao must be restarted from genesis, not upgraded in place. The unit suite
// pins the fold against an independent transcription of Def. 5.3
// (test/randao_accumulator_tests.cpp, fold_is_the_bare_xor_of_definition_5_3). The decision
// and the options weighed are recorded in docs/adr/randao-fold-bare-xor.md.
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
     *   R_tot_out = R_tot_prev ⊕ reveal                (thesis Def. 5.3, verbatim)
     *
     * A bare byte-wise XOR — see the note at the top of this file for why the
     * hardened H(R_tot ⊕ H(R)) variant was dropped in favour of the definition.
     *
     * A governed block's reveal is always exactly HASH_SIZE bytes (WPoAVRF::Verify
     * rejects any other length), which is the case Def. 5.3 describes and the only
     * one reachable in consensus. `reveal_len` is nonetheless honoured for the
     * degenerate inputs the glue can synthesize and the unit tests exercise: the
     * reveal is XORed cyclically over the accumulator word, so a short reveal
     * touches only its own prefix and a long one folds back over the start rather
     * than being silently truncated. Deterministic in every case.
     *
     * In/out aliasing is permitted (`rtot_out32` may equal `rtot_prev32`): the
     * previous value is copied out before any reveal byte is mixed in, and when the
     * buffers coincide that copy is a no-op.
     *
     * @param rtot_prev32  HASH_SIZE bytes — R_tot[n-1].
     * @param reveal       The block-n VRF reveal R[n] (HASH_SIZE bytes in consensus).
     * @param reveal_len   Length of `reveal`.
     * @param rtot_out32   [out] HASH_SIZE bytes — R_tot[n].
     */
    static void Fold(const unsigned char* rtot_prev32,
                     const unsigned char* reveal, size_t reveal_len,
                     unsigned char* rtot_out32)
    {
        // Start from R_tot_prev (a no-op when the caller folds in place).
        for (size_t i = 0; i < HASH_SIZE; i++)
        {
            rtot_out32[i] = rtot_prev32[i];
        }

        // R_tot_out = R_tot_prev ⊕ reveal. The modulo is the identity map in the
        // consensus case reveal_len == HASH_SIZE; it only defines the result for the
        // off-size buffers described above.
        for (size_t i = 0; i < reveal_len; i++)
        {
            rtot_out32[i % HASH_SIZE] = (unsigned char)(rtot_out32[i % HASH_SIZE] ^ reveal[i]);
        }
    }

    /**
     * Derive the proposer-selection seed from the looked-back accumulator, the
     * hash of the last finalized block and the height being elected:
     *
     *   seed = H( rtot_lookback ‖ h_tip ‖ height )         (cfr. Def. 5.4)
     *
     * `height` is serialized as 4 big-endian bytes so the encoding is fixed and
     * platform-independent (consensus-critical). Both `h_tip` and `height`
     * advance every block, so the seed stays fresh per round even when the
     * looked-back accumulator changes only slowly.
     *
     * @param rtot_lookback32  HASH_SIZE bytes — R_tot[n-k].
     * @param h_tip32          HASH_SIZE bytes — h[n], the tip hash.
     * @param height           The height being elected, `n+1`.
     * @param seed_out32       [out] HASH_SIZE bytes — seed[n+1].
     */
    static void DeriveSeed(const unsigned char* rtot_lookback32,
                           const unsigned char* h_tip32,
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
            .Write(h_tip32, HASH_SIZE)
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
class CBlock;        // forward-declared: the reveal extractor reads a whole block

/**
 * Set once from -enablewpoarandao in AppInit2. Default false = Phase 3a behavior:
 * selection is seeded by the plain previous block hash. Must be set uniformly
 * across the validator set (like -enablewpoa / -enablewpoavrf), or nodes disagree
 * on the elected proposer and the chain forks.
 */
extern bool g_wpoa_randao_enabled;

/**
 * Lookback distance `k` in seed[n+1] = H(R_tot[n-k] ‖ h[n] ‖ n+1). Set once from
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
 * RandaoAccumulator::DeriveSeed over (R_tot[n-k], h[n], n+1).
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

/**
 * Read the VRF reveal a block carries in its coinbase OP_RETURN.
 *
 * Same extraction FindBlockVRF (multichainblock.cpp) performs on the validation
 * path, but with a STACK-LOCAL mc_Script instead of the shared scratch buffer
 * mc_gState->m_TmpScript1 — so it is safe to call from the miner thread and from
 * an RPC thread, which the validation-path version is not. The proof is not
 * returned: a caller auditing a block already in the index is looking at a reveal
 * whose proof VerifyBlockMinerWPoA checked at accept time.
 *
 * @param block       the block to read.
 * @param reveal_out  [out] buffer for the reveal.
 * @param reveal_len  [in] capacity of reveal_out; [out] bytes written.
 * @return true if the block carries a reveal.
 */
bool WPoAExtractBlockReveal(const CBlock& block,
                            unsigned char* reveal_out, int* reveal_len);

#endif // WPOA_RANDAO_ACCUMULATOR_H
