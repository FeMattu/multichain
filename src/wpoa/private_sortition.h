// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA (Weighted Proof of Authority) — Phase 4: Efraimidis private sortition
// -----------------------------------------------------------------------
// THE SECURITY FIX. Phases 2/3a/3b built a weight-proportional proposer election
// over a proper VRF + RANDAO beacon, but selection stayed PUBLIC: every node
// scores every validator as
//
//   u_i = HMAC-SHA256(seed, address_i);  score_i = -ln(u_i) / f(w_i)
//
// over the public beacon seed, so ANY observer can recompute the next proposer a
// full block in advance — the leader-predictability / targeted-DoS window this
// project exists to close (docs/thesis-project-overview.md §3).
//
// Phase 4 makes the score PRIVATE. The entropy of u_i moves from a public HMAC to
// a per-validator VRF evaluated under that validator's SECRET key:
//
//   (y_i, π_i) = VRF_sk_i( seed ‖ "PROPOSER" ‖ height )
//   u_i        = top64(y_i) / 2^64                       ∈ (0,1]
//   score_i    = -ln(u_i) / f(w_i)                       (Exp(f(w_i))-distributed)
//   winner     = argmin_i(score_i)
//
// Because score_i depends on sk_i — known only to validator i — NO OTHER NODE can
// compute it, so the proposer's identity is unknown to the network until that node
// reveals it by proposing. The distribution is UNCHANGED (Pr[i]=w_i/Σw, Efraimidis
// & Spirakis 2006; docs/thesis-project-overview.md §7.4): only *who* can compute
// the winner and *when* it becomes known change. The u→E→score transform is the
// SAME one Phase 2 uses (WPoASelector::ScoreFromEntropy64) — the sole change is the
// source of the entropy (a private VRF output instead of a public HMAC digest).
//
// AGREEMENT WITHOUT A REVEAL ROUND (score-timed self-election). A validator cannot
// know it is the global argmin (it cannot compute the others' private scores), so
// the network cannot use the Phase-2 "miner == recomputed argmin" check. Instead:
//
//   * MINER side  — validator i mines only after a delay that INCREASES with its
//                   score:  start_i = now + MiningDelay(score_i, …). The lowest
//                   score (the argmin) therefore proposes FIRST; once its block
//                   propagates, higher-score validators see the new tip and stand
//                   down. So ~one block is produced per round and it is the argmin's
//                   — preserving Pr[i]=w_i/Σw without any extra messages.
//   * VALIDATOR side — a peer verifies π_i, recomputes score_i from the block-carried
//                   y_i and the signer's registry weight, and accepts iff the block's
//                   nTime is no earlier than the score entitles:
//                       block.nTime ≥ parent.nTime + MiningDelay(score_i, …)
//                   This is the *eligibility* test that REPLACES the argmin equality.
//                   It also bounds front-running: to mine earlier a node would need a
//                   lower score (which it cannot forge — VRF uniqueness) or a future
//                   timestamp (bounded by the base-consensus time-too-new rule).
//
// This removes the zero-proposer gap entirely: there is no hard threshold, so the
// minimum-score ONLINE validator always eventually proposes — the auto-relaxing
// time bar IS the liveness fallback. See docs/phase4-implementation-guide.md.
//
// CONSENSUS-CRITICAL. The VRF input encoding, the score transform, the delay map,
// the effective-weight sum and the time-bar comparison must be bit-identical on the
// miner and every validator, or they disagree on which blocks are valid and the
// chain forks. The math below is therefore a PURE, node-free core (this header,
// like the Phase 2/3a/3b cores) that never reads a global; the runtime flag/scale
// binding and the node walk live in the glue (private_sortition.cpp).
//
// Requires the full wPoA stack (wpoa → vrf → randao) and lookback k ≥ 1: the
// sortition VRF input depends on seed[n]=H(R_tot[n-k]‖…) and the reveal it produces
// feeds R_tot[n], so k ≥ 1 keeps that dependency acyclic (validated in AppInit2).

#ifndef WPOA_PRIVATE_SORTITION_H
#define WPOA_PRIVATE_SORTITION_H

#include <cmath>
#include <limits>
#include <string>
#include <vector>
#include <stddef.h>
#include <stdint.h>

#include "wpoa/wpoa_selector.h"   // WPoASelector::{FoldTop64,ScoreFromEntropy64}, DumpingFunction

/**
 * PrivateSortition — pure, deterministic, node-free Phase-4 sortition math.
 *
 * All methods are static and depend only on the C++ standard library and the
 * (header-only) Phase-2 score transform, so they can be exercised by the
 * Boost.Test unit suite without linking the wallet / node runtime (see
 * test/private_sortition_tests.cpp), exactly like the Phase 2/3a/3b cores.
 */
class PrivateSortition
{
public:
    /**
     * Domain-separation tag mixed between the beacon seed and the height in the
     * VRF input, so a sortition reveal can never collide with the Phase-3a
     * prev-hash reveal or any other VRF usage. Part of the consensus-critical wire
     * contract — changing it forks the chain.
     */
    static const char* ProposerTag() { return "PROPOSER"; }
    static const size_t PROPOSER_TAG_LEN = 8;      // strlen("PROPOSER"), NUL dropped

    /**
     * Build the per-round VRF input:  seed32 ‖ "PROPOSER" ‖ height_be(4).
     *
     * `height` is serialized as 4 big-endian bytes (the same fixed, platform-
     * independent encoding RandaoAccumulator::DeriveSeed uses), so the input is
     * bit-identical across nodes. This is the public input every validator's VRF
     * is evaluated over; only the secret key differs between them.
     *
     * @param seed32  HASH_SIZE (32) bytes — the Phase-3b beacon seed[n+1].
     * @param height  The height n+1 of the block being elected.
     * @param out     [out] cleared and filled with the 44-byte input.
     */
    static void VRFInput(const unsigned char* seed32, uint32_t height,
                         std::vector<unsigned char>& out)
    {
        out.clear();
        out.reserve(32 + PROPOSER_TAG_LEN + 4);
        out.insert(out.end(), seed32, seed32 + 32);
        const char* tag = ProposerTag();
        out.insert(out.end(), tag, tag + PROPOSER_TAG_LEN);
        out.push_back((unsigned char)((height >> 24) & 0xff));
        out.push_back((unsigned char)((height >> 16) & 0xff));
        out.push_back((unsigned char)((height >>  8) & 0xff));
        out.push_back((unsigned char)( height        & 0xff));
    }

    /**
     * The private Efraimidis–Spirakis score from a VRF output.
     *
     * Folds the top 64 bits of the VRF output into the entropy word and runs the
     * SAME transform Phase 2 applies to its HMAC digest (WPoASelector) — so, given
     * identical (entropy, weight, dumping), the private score is byte-identical to
     * what the public selector would produce. Smaller wins.
     *
     * @param vrf_output  At least 8 readable bytes (a WPoAVRF reveal, 32 bytes).
     * @param weight      The proposer's registry weight (0 ⇒ +inf, can never win).
     * @param dumping     Weight-dumping function (CONSENSUS-CRITICAL: must match).
     * @return score = -ln(u)/f(weight), u = (top64(vrf_output)+1)/2^64.
     */
    static double ScoreFromVRFOutput(const unsigned char* vrf_output, uint32_t weight,
                                     DumpingFunction dumping = DUMP_NONE)
    {
        return WPoASelector::ScoreFromEntropy64(
                   WPoASelector::FoldTop64(vrf_output), weight, dumping);
    }

    /**
     * Upper bound on the mining delay / time-bar offset, in seconds. Keeps the
     * `parent.nTime + delay` sum well clear of any uint32 overflow and prevents a
     * pathological (score, weight) product from stalling the chain for years; a
     * capped delay still preserves the argmin ordering among realistic scores.
     */
    static double MaxDelaySeconds() { return 100000.0; } // ~27.7 h

    /**
     * Map a score to the mining delay (seconds) — the score-timing that makes the
     * argmin propose first and, dually, the auto-relaxing time bar the validator
     * enforces.
     *
     *   delay = scale · score · total_eff_weight
     *
     * Multiplying by `total_eff_weight = Σ_j f(w_j)` makes the delay weight-SCALE
     * invariant: the minimum score across m validators is ~Exp(Σf(w_j)), so
     * score·Σf(w_j) is ~Exp(1)-scaled regardless of the absolute weight magnitudes,
     * and `scale` (seconds) then sets the real-time spread between successive
     * proposers directly. Strictly increasing in `score`, so argmin(score) =
     * earliest allowed proposer = the winner — the distribution is preserved.
     *
     * Tuning: larger `scale` ⇒ larger inter-proposer gaps ⇒ fewer simultaneous
     * proposers (fewer forks) but slower blocks. See docs/phase4-implementation-guide.md.
     *
     * @param score             The proposer's sortition score (≥ 0).
     * @param total_eff_weight  Σ_j f(w_j) over all validators (> 0).
     * @param scale             Seconds per unit of normalized score (-wpoasortitiondelay).
     * @return the delay in seconds, clamped to [0, MaxDelaySeconds()].
     */
    static double MiningDelay(double score, double total_eff_weight, double scale)
    {
        // Defensive: a non-finite or negative input must not produce a negative or
        // NaN delay (which would make the time-bar meaningless). Treat any such
        // degenerate case as "maximally delayed" so the node effectively stands down.
        if (!(score >= 0.0) || !(total_eff_weight > 0.0) || !(scale >= 0.0) ||
            !std::isfinite(score) || !std::isfinite(total_eff_weight) || !std::isfinite(scale))
        {
            return MaxDelaySeconds();
        }

        double d = scale * score * total_eff_weight;
        if (!std::isfinite(d) || d < 0.0)
        {
            return MaxDelaySeconds();
        }
        if (d > MaxDelaySeconds())
        {
            return MaxDelaySeconds();
        }
        return d;
    }
};

// ---------------------------------------------------------------------------
// Node-coupled glue (defined in private_sortition.cpp; NOT compiled into the
// node-free unit test, which only uses the PrivateSortition core above).
// ---------------------------------------------------------------------------

class CBlock;        // forward-declared: the glue reads a block's coinbase reveal
class CBlockIndex;   // forward-declared: the glue walks the block index for the seed

/**
 * Set once from -enablewpoasortition in AppInit2. Default false = Phase 3b
 * behavior: the PUBLIC Efraimidis election over the beacon seed. Must be set
 * uniformly across the validator set (like the Phase 2/3a/3b flags), or nodes
 * disagree on block validity and the chain forks.
 */
extern bool g_wpoa_sortition_enabled;

/**
 * Delay scale (seconds per unit of normalized score) in
 * delay = scale · score · Σf(w). Set once from -wpoasortitiondelay in AppInit2
 * (default MC_WPOA_DEFAULT_SORTITION_DELAY). CONSENSUS-CRITICAL: must be identical
 * on all nodes (it enters the validator's time-bar).
 */
extern double g_wpoa_sortition_delay;

#define MC_WPOA_DEFAULT_SORTITION_DELAY 1.0

/**
 * True when the block at `height` is elected by private sortition rather than the
 * public Phase-3b argmin. Requires -enablewpoasortition AND that the RANDAO beacon
 * already governs the height (WPoARANDAOActiveAtHeight) — sortition consumes the
 * beacon seed as its public VRF input. A pure function of shared data (flags +
 * chain params + height), so the miner and every validator agree from the height
 * alone which blocks are sortition-governed.
 */
bool WPoASortitionActiveAtHeight(int height);

/**
 * Miner side: compute this node's private sortition score and the mining delay for
 * the block that follows `pindexTip` (height pindexTip->nHeight+1).
 *
 * Derives the beacon seed over `pindexTip`, builds the VRF input, evaluates the VRF
 * under `sk32`, scores the resulting output against this node's registry weight, and
 * returns the score and delay = MiningDelay(score, Σf(w), g_wpoa_sortition_delay).
 *
 * @param pindexTip   The current tip (parent of the block to mine; may be NULL).
 * @param address     This node's mining address (its StreamWeightRegistry key).
 * @param sk32        This node's 32-byte secret key (for WPoAVRF::Prove).
 * @param score_out   [out] the sortition score.
 * @param delay_out   [out] the mining delay in seconds.
 * @return true if a score/delay was produced; false (leaving outputs untouched) if
 *         the seed, weight map or VRF are unavailable — the caller then stands down.
 */
bool WPoASortitionLocalScoreDelay(const CBlockIndex* pindexTip,
                                  const std::string& address,
                                  const unsigned char* sk32,
                                  double* score_out, double* delay_out);

/**
 * Miner side: build the VRF input for the reveal embedded in `block`, when that
 * block's height is sortition-governed. Looks the block's parent up in the block
 * index, derives the beacon seed and returns VRFInput(seed, height).
 *
 * @param block      The block being signed (its hashPrevBlock identifies the parent).
 * @param input_out  [out] the VRF input bytes on success.
 * @return true if the block is sortition-governed and the input was built; false
 *         otherwise (the caller then uses the Phase-3a prev-hash input).
 */
bool WPoASortitionVRFInputForBlock(const CBlock* block,
                                   std::vector<unsigned char>& input_out);

/** Verdicts for WPoASortitionVerifyProposer (mirrors the caller's reject/skip/ok). */
enum WPoASortitionVerdict
{
    WPOA_SORTITION_REJECT = -1,   // provably invalid: reject the block
    WPOA_SORTITION_SKIP   =  0,   // cannot evaluate locally (e.g. weights unsynced): accept leniently
    WPOA_SORTITION_OK     =  1    // eligible proposer: accept
};

/**
 * Validator side: verify that `pubkey`/`miner_addr` is an eligible sortition
 * proposer for the block at `height` whose parent is `pindexParent`.
 *
 * Recomputes the beacon seed over `pindexParent`, verifies the VRF proof over the
 * sortition input, recomputes the score from the revealed VRF output and the
 * signer's registry weight, and checks the time bar
 * block_ntime ≥ parent.nTime + MiningDelay(score, Σf(w), scale).
 *
 * @param pindexParent  pindexNew->pprev — the tip the honest miner saw.
 * @param height        pindexNew->nHeight — the block's height.
 * @param pubkey        The signer's serialized public key.
 * @param miner_addr    The signer's address (registry key).
 * @param vrf_reveal    The block-carried VRF output y (WPoAVRF::OUTPUT_SIZE bytes).
 * @param vrf_proof     The block-carried VRF proof π (WPoAVRF::PROOF_SIZE bytes).
 * @param block_ntime   The block's nTime (seconds).
 * @param reason_out    [out, optional] human-readable reason on REJECT (for logging).
 * @return a WPoASortitionVerdict.
 */
WPoASortitionVerdict WPoASortitionVerifyProposer(const CBlockIndex* pindexParent,
                                                 int height,
                                                 const std::vector<unsigned char>& pubkey,
                                                 const std::string& miner_addr,
                                                 const std::vector<unsigned char>& vrf_reveal,
                                                 const std::vector<unsigned char>& vrf_proof,
                                                 uint32_t block_ntime,
                                                 std::string* reason_out);

/**
 * Miner-loop guard against re-proposing a height whose tip has not advanced.
 *
 * Under sortition a node's block can legitimately lose the fork race; because the
 * tip hash (the miner's timing-cache key) is then unchanged, the loop would spin
 * re-mining the same height. WPoASortitionMarkProposed records the highest height
 * this node has already mined; WPoASortitionAlreadyProposed reports whether a given
 * height is at or below it, so the miner stands down until the tip advances.
 */
void WPoASortitionMarkProposed(int height);
bool WPoASortitionAlreadyProposed(int height);

#endif // WPOA_PRIVATE_SORTITION_H
