// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA (Weighted Proof of Authority) — Phase 2: Weighted Miner Selection
// -----------------------------------------------------------------------
// Elects the proposer of the next block in proportion to the on-chain
// validator weights (StreamWeightRegistry, Phase 1) using the
// Efraimidis–Spirakis weighted-sampling transform.
//
//   digest_i = HMAC-SHA256(key = prev_block_hash, msg = validator_address)
//   u_i      = (top-64-bits(digest_i) + 1) / 2^64          ∈ (0, 1]
//   E_i      = -ln(u_i)                                     ∈ [0, +∞)   (Exp(1))
//   score_i  = E_i / w_i                                    (Exp(w_i))
//   proposer = argmin_i(score_i)   [ties: lexicographically smallest address]
//
// Pr[i elected] = w_i / Σ_j w_j  (Efraimidis & Spirakis, 2006; see
// docs/thesis-project-overview.md §7.4 for the probability-preservation proof).
//
// PHASE 2 IS PUBLIC AND PREDICTABLE BY DESIGN. The seed is the plain previous
// block hash and every u_i is a public function of it, so any observer can
// compute the next proposer a full block in advance. This is an accepted,
// documented property of this phase (docs/implementation-roadmap.md §9); the
// privacy fix — evaluating u_i under a per-validator VRF secret key — is
// Phase 3/4 and swaps only the randomness source, not the scoring/argmin logic
// below. See docs/phase2-weighted-selection.md.
//
// The scoring core (WPoASelector) is intentionally free of node/wallet
// dependencies so it can be unit-tested in isolation; the node-coupled glue
// (registry read, activation predicate, runtime flag) is declared at the
// bottom and defined in wpoa_selector.cpp.

#ifndef WPOA_SELECTOR_H
#define WPOA_SELECTOR_H

#include <cmath>
#include <limits>
#include <map>
#include <string>
#include <stdint.h>

#include "crypto/hmac_sha256.h"

// wPoA weight-dumping (damping) function ------------------------------------
//
// Applied to each validator weight *before* the Efraimidis–Spirakis draw. The
// transform is concave and strictly increasing, so it compresses the weight
// distribution: a single large stake ("whale") can no longer dominate proposer
// selection, and its selection share cannot grow without bound as its weight
// climbs — yet validators are never reordered (a heavier raw weight still maps
// to a larger effective weight, hence a larger win probability).
//
//   DUMP_NONE : f(w) = w           raw weight, no compression   (default)
//   DUMP_SQRT : f(w) = sqrt(w)     moderate compression
//   DUMP_LOG  : f(w) = ln(1 + w)   strong compression
//
// CONSENSUS-CRITICAL: the miner and every validator MUST apply the SAME
// function, or they disagree on the elected proposer and the chain forks. The
// choice is therefore threaded explicitly into the pure core below (which never
// reads a global) and is bound to the -dumpfunction runtime flag in exactly one
// place — the node glue in wpoa_selector.cpp.
enum DumpingFunction
{
    DUMP_NONE = 0,
    DUMP_LOG,
    DUMP_SQRT
};

#define MC_WPOA_DEFAULT_DUMPING_FUNCTION DUMP_NONE  // no dumping by default

/** Set once from -dumpfunction in AppInit2; defined in wpoa_selector.cpp. */
extern DumpingFunction g_dumping_function;

/**
 * WPoASelector — pure, deterministic, node-free proposer election.
 *
 * All methods are static and depend only on the C++ standard library and the
 * HMAC-SHA256 primitive, so they can be exercised by the Boost.Test unit suite
 * without linking the wallet / node runtime (see test/wpoa_selector_tests.cpp).
 */
class WPoASelector
{
public:

    /**
     * Apply a weight-dumping (damping) function to a raw validator weight.
     *
     * Concave and strictly increasing on w >= 1 (the registry never stores a
     * smaller positive weight), so it compresses large weights — curbing whale
     * dominance — without ever reordering validators. The result is strictly
     * positive for every w >= 1, so the caller's E / weight score stays finite:
     *   DUMP_SQRT -> sqrt(1)   = 1
     *   DUMP_LOG  -> ln(1 + 1) ~ 0.693   (the "1 +" keeps w == 1 above zero;
     *                                     plain ln(1) = 0 would give a +inf score)
     *
     * Kept pure (no global reads) so the node-free unit test can exercise every
     * mode directly; the runtime flag is bound in the node glue.
     *
     * @param weight   Raw validator weight (>= 1 in practice; weight 0 is
     *                 handled by the caller before this is reached).
     * @param dumping  Which transform to apply.
     * @return the effective weight fed to the Efraimidis–Spirakis score.
     */
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

    /**
     * Fold the top 64 bits (big-endian) of a hash-valued buffer into an integer.
     *
     * 64 bits of entropy is far more than a double's 53-bit mantissa can resolve,
     * so this is not a precision bottleneck; using more bytes would not change the
     * outcome. Shared by every entropy source that feeds the Efraimidis draw
     * (Phase 2's HMAC digest, Phase 4's VRF output) so they fold identically.
     *
     * @param buf  At least 8 readable bytes (an HMAC-SHA256 or VRF output).
     * @return the big-endian uint64 formed from buf[0..7].
     */
    static uint64_t FoldTop64(const unsigned char* buf)
    {
        uint64_t d = 0;
        for (int i = 0; i < 8; i++)
        {
            d = (d << 8) | (uint64_t)buf[i];
        }
        return d;
    }

    /**
     * The Efraimidis–Spirakis score transform, isolated from the entropy source.
     *
     *   u      = (d + 1) / 2^64        ∈ (0, 1]      (from 64 bits of entropy `d`)
     *   E      = -ln(u)                ∈ [0, +∞)     (Exp(1)-distributed)
     *   score  = E / f(weight)                       (Exp(f(weight))-distributed)
     *
     * This is the SINGLE SOURCE OF TRUTH for the score math: Phase 2's public
     * HMAC selector (ComputeScore below) and Phase 4's private VRF sortition
     * (PrivateSortition, private_sortition.h) both fold their entropy with
     * FoldTop64 and call this, so the two produce byte-identical scores from the
     * same `d` and `weight` — the only thing that differs between the public and
     * private forms is WHERE `d` comes from.
     *
     * @param d        64 bits of entropy (see FoldTop64).
     * @param weight   Validator weight; 0 yields +inf so the node can never win.
     * @param dumping  Weight-dumping function applied to `weight` before the draw.
     * @return the Efraimidis–Spirakis score; smaller wins.
     */
    static double ScoreFromEntropy64(uint64_t d, uint32_t weight,
                                     DumpingFunction dumping = DUMP_NONE)
    {
        if (weight == 0)
        {
            return std::numeric_limits<double>::infinity();
        }

        // Normalize to (0, 1]. The "+ 1.0" (done in double, so it never wraps the
        // uint64) guarantees u > 0 and therefore that -ln(u) is finite; u == 1 is
        // a legitimate minimum (score 0) reached only when d == 2^64 - 1.
        const double two64 = 18446744073709551616.0; // 2^64, exact in double
        double u = ((double)d + 1.0) / two64;

        double E = -std::log(u);                            // Exp(1)-distributed
        return E / ApplyDumping(weight, dumping);           // Exp(f(weight))-distributed
    }

    /**
     * Efraimidis–Spirakis score for one validator (Phase 2 public form).
     *
     * @param seed      Raw seed bytes (Phase 2: the previous block hash).
     * @param seed_len  Length of `seed` in bytes.
     * @param address   Validator address string (the StreamWeightRegistry key).
     * @param weight    Validator weight (> 0; a weight of 0 yields +inf so the
     *                  node can never win).
     * @param dumping   Weight-dumping function applied to `weight` before the
     *                  draw (default none). CONSENSUS-CRITICAL: the caller must
     *                  pass the same value on the miner and the validator side.
     * @return score_i = -ln(u_i) / f(weight), where u_i ∈ (0,1] is derived from
     *         HMAC-SHA256(seed, address) and f is the dumping function. Smaller
     *         wins.
     */
    static double ComputeScore(const unsigned char* seed, size_t seed_len,
                               const std::string& address, uint32_t weight,
                               DumpingFunction dumping = DUMP_NONE)
    {
        // u_i = HMAC-SHA256(key = seed, msg = address).
        unsigned char mac[CHMAC_SHA256::OUTPUT_SIZE];
        CHMAC_SHA256(seed, seed_len)
            .Write(reinterpret_cast<const unsigned char*>(address.data()), address.size())
            .Finalize(mac);

        return ScoreFromEntropy64(FoldTop64(mac), weight, dumping);
    }

    /**
     * Elect the proposer from an explicit weight map.
     *
     * The result depends ONLY on the (address, weight) set and the seed — never
     * on iteration order — because the winner is the global argmin of an
     * independent per-node score, with a lexicographic-address tie-break on the
     * (cryptographically negligible) event of a bit-exact score collision. This
     * ordering-independence is the reason Phase 2 uses the argmin form rather
     * than a cumulative-range walk over an "opaque" map (see
     * docs/phase2-weighted-selection.md).
     *
     * @param dumping   Weight-dumping function applied to every weight before
     *                  the draw (default none). CONSENSUS-CRITICAL: must match
     *                  on the miner and validator side.
     * @return the winning validator address, or "" if `weights` has no
     *         positive-weight entries.
     */
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
            {
                continue; // defensive: registry never stores weight 0
            }

            double s = ComputeScore(seed, seed_len, it->first, it->second, dumping);

            // Total order: lower score wins; on an exact tie the lexicographically
            // smaller address wins (docs/implementation-roadmap.md §9). Written so
            // the outcome is independent of the container's iteration order.
            if (!have || s < best_score || (s == best_score && it->first < best_addr))
            {
                best_score = s;
                best_addr = it->first;
                have = true;
            }
        }

        return best_addr;
    }
};

// ---------------------------------------------------------------------------
// Node-coupled glue (defined in wpoa_selector.cpp; NOT compiled into the
// node-free unit test, which only uses the WPoASelector core above).
// ---------------------------------------------------------------------------

/** Set once from -enablewpoa in AppInit2. Default false = no behavioral change. */
extern bool g_wpoa_enabled;

/**
 * True when the weighted-selection path should govern the block at `height`.
 * Requires -enablewpoa, a MultiChain-protocol chain, a permissioned miner set
 * (not anyone-can-mine), and a height at or past the setup period — so both the
 * miner and the validator agree, from the height alone, on when wPoA engages.
 */
bool WPoAActiveAtHeight(int height);

/**
 * Registry-backed convenience wrapper: reads the current confirmed weight map
 * from the wpoa-weights stream and returns WPoASelector::SelectProposer for the
 * given seed. Returns "" if the wallet or weight map is unavailable.
 *
 * `height` is carried for logging and Phase 4 forward-compatibility; in Phase 2
 * the seed is the previous block hash alone (see header comment).
 */
std::string WPoASelectProposer(const unsigned char* seed, size_t seed_len, int height);

// ---------------------------------------------------------------------------
// wPoA Phase 3a — VRF beacon activation (node glue; definitions in .cpp).
//
// Phase 3a adds the *randomness-generation* half of the wPoA beacon: the
// proposer elected by the Phase 2 public selection additionally publishes a
// per-block VRF reveal (bound to its key and the previous block hash), and every
// peer verifies it. Selection itself is UNCHANGED in Phase 3a — the VRF is a
// verifiable contribution to the beacon, not (yet) the selection mechanism (that
// is Phase 4). See docs/phase3a-implementation-guide.md.
// ---------------------------------------------------------------------------

/**
 * Set once from -enablewpoavrf in AppInit2. Default false = Phase 2 behavior:
 * no VRF reveal is produced or required. Must be set uniformly across the
 * validator set (like -enablewpoa), or nodes disagree on block validity.
 */
extern bool g_wpoa_vrf_enabled;

/**
 * True when a block at `height` must carry a verified VRF reveal. Requires
 * -enablewpoavrf AND that wPoA already governs the height (WPoAActiveAtHeight),
 * so the VRF requirement engages exactly on the wPoA-governed blocks and the
 * miner and validator agree from the height alone.
 */
bool WPoAVRFActiveAtHeight(int height);

#endif // WPOA_SELECTOR_H
