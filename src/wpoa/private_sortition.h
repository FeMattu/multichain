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
//
//                   The delay is a BAND around the chain's target-block-time rather
//                   than an open-ended ramp:
//
//                     score_norm = 1 - e^{-W·score}                      (Def. 5.10)
//                     D_i        = T_block + delta·T_block·(2·score_norm - 1)
//                                          + lambda·Phi                  (Def. 5.13)
//
//                   The W factor is what makes the normalization real: without it the
//                   value inherits the scale of E/w and collapses against 0 for every
//                   candidate once weights reach the hundreds. With it, the WINNER's
//                   normalized score is exactly U(0,1) (Prop. 5.10), so its delay is
//                   uniform over the band and the mean block time lands on T_block.
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
// the effective-weight sum, the feedback Phi and the time-bar comparison must be
// bit-identical on the miner and every validator, or they disagree on which blocks
// are valid and the chain forks. The math below is therefore a PURE, node-free core (this header,
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
     * Upper bound on the mining delay / time-bar offset, in seconds. With the
     * banded delay below the value is already bounded by T_block(1+delta) + lambda*M,
     * so this is a pure defensive backstop: it keeps the `parent.nTime + delay` sum
     * clear of any uint32 overflow even under a pathological parameter set.
     */
    static double MaxDelaySeconds() { return 100000.0; } // ~27.7 h

    /**
     * The normalized score (Def. 5.10):
     *
     *   score_norm = 1 - e^{-W * score}   in (0, 1)
     *
     * The W factor — the TOTAL effective weight of the round's candidates — is what
     * makes this a normalization rather than a relabelling. Without it the value
     * would inherit the scale of score = E/w, which depends on the candidate's own
     * raw weight: on a network with weights in the hundreds E/w sits very close to 0
     * for every candidate, so 1 - e^{-score} would collapse against 0 no matter who
     * wins the round, defeating the whole purpose of spreading the delays across the
     * band. Multiplying by W corrects exactly that scale effect.
     *
     * Two properties follow, and both matter downstream:
     *   * x -> 1 - e^{-Wx} is strictly increasing at fixed W, so the normalized score
     *     induces the SAME ordering as the raw score — argmin is preserved, and with
     *     it the weighted election (Prop. 5.9 / Prop. 5.11);
     *   * the WINNER's normalized score is exactly U(0,1), for any number of
     *     candidates and any weight distribution (Prop. 5.10): min_i score_i ~ Exp(W),
     *     so W*min ~ Exp(1), and applying that distribution's own CDF yields a
     *     uniform. This is what makes the winner's delay uniform over the band, and
     *     hence the mean block time equal to T_block.
     *
     * @param score             The candidate's raw sortition score (>= 0).
     * @param total_eff_weight  W = sum_j f(w_j) over the round's candidates (> 0).
     * @return score_norm in (0, 1); 1.0 for a degenerate input, i.e. maximally
     *         delayed, so a node that cannot score itself stands down.
     */
    static double NormalizedScore(double score, double total_eff_weight)
    {
        if (!(score >= 0.0) || !(total_eff_weight > 0.0) ||
            !std::isfinite(score) || !std::isfinite(total_eff_weight))
        {
            return 1.0;
        }

        double x = total_eff_weight * score;
        if (!std::isfinite(x) || x < 0.0)
        {
            return 1.0;
        }

        double norm = 1.0 - std::exp(-x);
        if (!(norm > 0.0))  return 0.0;   // underflow for a tiny x
        if (norm > 1.0)     return 1.0;
        return norm;
    }

    /**
     * The delay shape psi (Def. 5.11), in its concrete affine form
     *
     *   psi(x) = 2x - 1,   mapping (0,1) -> (-1,1)
     *
     * so the band is symmetric around T_block: the most favoured candidate (the one
     * closest to winning) gets T_block - Delta_max, the least favoured
     * T_block + Delta_max. Strict monotonicity is the exact condition under which
     * the timer race elects the sortition winner (Prop. 5.11) — psi must stay a pure
     * monotone transform of the score, never an independent selection channel.
     */
    static double DelayShape(double x) { return 2.0 * x - 1.0; }

    /**
     * The largest feedback magnitude M compatible with timer admissibility
     * (Cor. 5.15):
     *
     *   M* = T_block (1 - delta) / lambda
     *
     * Prop. 5.13 requires Delta_max <= T_block - lambda*M for D_i >= 0 to hold for
     * every candidate and every round; with Delta_max = delta*T_block that is exactly
     * M <= M*. The node derives it from the public parameters, so no separate
     * configuration is needed.
     *
     * @return M*, or +inf when lambda == 0 — the bound is then vacuous because the
     *         lambda*Phi term vanishes regardless (Cor. 5.14).
     */
    static double MaxFeedback(double target_block_time, double delta, double lambda)
    {
        if (!(lambda > 0.0) || !std::isfinite(lambda))
        {
            return std::numeric_limits<double>::infinity();
        }
        if (!(target_block_time > 0.0) || !std::isfinite(target_block_time) ||
            !(delta >= 0.0) || !(delta < 1.0) || !std::isfinite(delta))
        {
            return 0.0;
        }
        return target_block_time * (1.0 - delta) / lambda;
    }

    /**
     * Map a score to the mining delay (seconds) — the score-timing that makes the
     * argmin propose first and, dually, the auto-relaxing time bar the validator
     * enforces (Def. 5.11 + Def. 5.13):
     *
     *   Delta_max = delta * T_block
     *   D_i       = T_block + Delta_max * psi(score_norm_i) + lambda * Phi
     *
     * Expressing Delta_max as a FRACTION of the target makes delta the real tuning
     * knob, invariant to a change of T_block scale, and gives the admissibility
     * constraint for free (Prop. 5.13).
     *
     * The three terms have cleanly separated jobs. Delta_max*psi(score_norm) orders
     * the candidates — and only that. `lambda*Phi` corrects the network's aggregate
     * temporal trajectory and is IDENTICAL for every candidate of the round, so it
     * cancels in every pairwise timer difference and cannot reorder anyone
     * (Prop. 5.11). T_block centres the band, which together with the winner's
     * uniform normalized score (Prop. 5.10) puts the mean realized delay exactly on
     * target-block-time.
     *
     * @param score             The proposer's raw sortition score (>= 0).
     * @param total_eff_weight  W = sum_j f(w_j) over the round's candidates (> 0).
     * @param target_block_time T_block, the chain's target-block-time in seconds.
     * @param delta             Delta_max / T_block, in (0,1).
     * @param lambda            Feedback gain in [0,1]; 0 disables the correction.
     * @param feedback          Phi, the global correction (already clipped to +/-M
     *                          by the caller). CONSENSUS-CRITICAL: must be derived
     *                          identically on the miner and every validator.
     * @return the delay in seconds, clamped to [0, MaxDelaySeconds()].
     */
    static double MiningDelay(double score, double total_eff_weight,
                              double target_block_time, double delta,
                              double lambda, double feedback)
    {
        // Defensive: a non-finite or out-of-domain input must not produce a negative
        // or NaN delay (which would make the time bar meaningless). Treat any such
        // degenerate case as "maximally delayed" so the node effectively stands down.
        if (!(target_block_time > 0.0) || !std::isfinite(target_block_time) ||
            !(delta >= 0.0) || !(delta < 1.0) || !std::isfinite(delta) ||
            !(lambda >= 0.0) || !std::isfinite(lambda) || !std::isfinite(feedback))
        {
            return MaxDelaySeconds();
        }

        double norm = NormalizedScore(score, total_eff_weight);
        double d = target_block_time
                 + (delta * target_block_time) * DelayShape(norm)
                 + lambda * feedback;

        // Prop. 5.13 guarantees d >= 0 whenever Delta_max <= T_block - lambda*M, which
        // the caller enforces by clipping Phi to +/-M; clamp anyway so a misconfigured
        // chain degrades to "mine now" instead of scheduling into the past.
        if (!std::isfinite(d) || d < 0.0)      return 0.0;
        if (d > MaxDelaySeconds())             return MaxDelaySeconds();
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
 * delta = Delta_max / T_block, in (0,1): the half-width of the delay band as a
 * fraction of target-block-time (Def. 5.11). Set once from -wpoasortitiondelta in
 * AppInit2. Small delta ⇒ a narrow band, candidates closer together in time, more
 * forks; large delta ⇒ a wide band, more latency on the unfavoured candidates.
 * CONSENSUS-CRITICAL: must be identical on all nodes (it enters the time bar).
 */
extern double g_wpoa_sortition_delta;

/**
 * lambda in [0,1]: the gain of the global delay feedback (Def. 5.13). 0 disables
 * the correction entirely (Cor. 5.14) and is the default; a value close to 1 makes
 * the correction dominate the score-driven term and risks a persistent oscillation
 * of the mean block time around the target. CONSENSUS-CRITICAL.
 */
extern double g_wpoa_sortition_lambda;

#define MC_WPOA_DEFAULT_SORTITION_DELTA  0.5
#define MC_WPOA_DEFAULT_SORTITION_LAMBDA 0.0

/**
 * Number of finalized blocks the feedback averages over. Reuses MultiChain's own
 * scheduling window (`nPastBlocks` in miner.cpp), so the correction is smoothed over
 * the same horizon the native delay logic already uses. CONSENSUS-CRITICAL, hence a
 * compile-time constant rather than an operator knob: the thesis leaves only delta
 * and lambda open to tuning (Table 5.2).
 */
#define MC_WPOA_SORTITION_FEEDBACK_WINDOW 12

/**
 * Phi (Def. 5.12 / Def. 5.14): the global delay correction for the round that
 * follows `pindexTip`, derived from finalized chain state alone.
 *
 *   Phi = clip( T_block - mean_observed_spacing , -M, +M )
 *
 * i.e. MultiChain's own shape — a moving average over a fixed window of past blocks,
 * then a clip — but computed on BLOCK TIMESTAMPS rather than on the native
 * `dTimeReceived`. That distinction is essential: dTimeReceived is the local
 * wall-clock arrival time (main.cpp), so it differs per node and is absent entirely
 * on a node that synced from scratch; Def. 5.12 requires Phi to be a deterministic
 * public function of the finalized state, identical everywhere, or the miner and the
 * validator would compute different time bars and the chain would fork.
 *
 * Sign: blocks arriving too slowly (mean spacing above target) yield a negative Phi,
 * which shortens every candidate's timer; too fast yields a positive Phi, which
 * lengthens it. Being common to all candidates it cannot reorder them (Prop. 5.11).
 *
 * @param pindexTip  The tip the round starts from (may be NULL).
 * @return Phi in [-M, +M]; 0 when the window is not yet available, so a young chain
 *         simply runs uncorrected.
 */
double WPoASortitionFeedback(const CBlockIndex* pindexTip);

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
