// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA Phase 4 — node-coupled glue for private (VRF-scored) sortition.
// The pure sortition math lives (header-only) in private_sortition.h so it can be
// unit-tested without the node; this file wires that core to the running node:
// the runtime flags, the global delay feedback, the height activation predicate, the
// miner-side local score + delay, the reveal VRF-input builder, and the validator-side
// eligibility (VRF-verify + score + time-bar) check that replaces the argmin equality.
//
// See docs/phase4-implementation-guide.md.

#include "wpoa/private_sortition.h"

#include "wpoa/wpoa_selector.h"           // WPoASelector::ApplyDumping, g_dumping_function
#include "wpoa/randao_accumulator.h"      // WPoARANDAOActiveAtHeight, WPoARandaoSelectionSeed
#include "wpoa/vrf_wrapper.h"             // WPoAVRF::Prove / Verify
#include "wpoa/stream_weight_registry.h"  // StreamWeightRegistry, GetAllNodesWeights
#include "wpoa/malus_registry.h"          // WPoAApplyMalus (w_eff = w * Psi)
#include "core/init.h"                    // pwalletTxsMain
#include "core/main.h"                    // CBlockIndex, CBlock, mapBlockIndex, BlockMap
#include "utils/util.h"                   // LogPrint, LogPrintf, strprintf, fDebug
#include "utils/sync.h"                   // CCriticalSection, LOCK

#include <map>
#include <string>
#include <vector>

using namespace std;

// Default off: with the flag unset the node behaves exactly as in Phase 3b — the
// PUBLIC Efraimidis argmin over the beacon seed. Set once from -enablewpoasortition.
bool g_wpoa_sortition_enabled = false;

// Band half-width as a fraction of target-block-time, and the feedback gain. Bound
// once from -wpoasortitiondelta / -wpoasortitionlambda in AppInit2.
// CONSENSUS-CRITICAL (both enter the validator's time bar, so they must match on all
// nodes).
double g_wpoa_sortition_delta  = MC_WPOA_DEFAULT_SORTITION_DELTA;
double g_wpoa_sortition_lambda = MC_WPOA_DEFAULT_SORTITION_LAMBDA;

// ---------------------------------------------------------------------------
// Phi — the global delay feedback (Def. 5.12 / Def. 5.14)
// ---------------------------------------------------------------------------
//
// Same shape MultiChain's native scheduler already uses to keep its block cadence on
// target (miner.cpp: a mean over `nPastBlocks` past blocks, then a clip into a band
// around the per-last-block target), with one deliberate substitution: the native code
// averages `pindex->dTimeReceived`, the LOCAL wall-clock arrival time, which differs
// from node to node and is zero for every block on a node that synced from scratch.
// That is fine for a purely local scheduling hint, but Phi enters the validator's time
// bar, so Def. 5.12 requires it to be a deterministic function of finalized state.
// We therefore average BLOCK TIMESTAMPS, which live in the header and are identical
// on every node.
double WPoASortitionFeedback(const CBlockIndex* pindexTip)
{
    if (pindexTip == NULL)
    {
        return 0.0;
    }

    const double Tblock = (double)Params().TargetSpacing();
    if (!(Tblock > 0.0))
    {
        return 0.0;
    }

    // Walk back a fixed window of finalized blocks. Fewer than a full window (a young
    // chain, or one just past genesis) means there is nothing to average yet: run
    // uncorrected rather than act on a partial sample, mirroring the native
    // `nWindowSize < nPastBlocks` branch.
    const int window = MC_WPOA_SORTITION_FEEDBACK_WINDOW;
    const CBlockIndex* pold = pindexTip;
    for (int i = 0; i < window && pold != NULL; i++)
    {
        pold = pold->pprev;
    }
    if (pold == NULL)
    {
        return 0.0;
    }

    // Mean spacing actually realized over the window, from consensus timestamps only.
    int64_t span = pindexTip->GetBlockTime() - pold->GetBlockTime();
    if (span <= 0)
    {
        return 0.0;   // non-monotonic timestamps: no usable signal, stay neutral
    }
    double mean_spacing = (double)span / (double)window;

    // Blocks too slow (mean spacing above target) -> negative Phi -> shorter timers;
    // too fast -> positive Phi -> longer timers.
    double phi = Tblock - mean_spacing;

    // Clip to +/-M. M is the admissibility ceiling of Cor. 5.15, additionally capped by
    // MultiChain's own half-spread (0.5 * target-block-time, `dRelativeSpread` in
    // miner.cpp) so the correction never exceeds the magnitude the native scheduler
    // considers reasonable.
    double M = 0.5 * Tblock;
    double Mstar = PrivateSortition::MaxFeedback(Tblock, g_wpoa_sortition_delta,
                                                 g_wpoa_sortition_lambda);
    if (Mstar < M)
    {
        M = Mstar;
    }
    if (!(M > 0.0) || !std::isfinite(M))
    {
        return 0.0;
    }
    if (phi >  M) phi =  M;
    if (phi < -M) phi = -M;

    if (fDebug)
    {
        LogPrint("wpoa", "[wpoa-sortition] feedback height=%d window=%d mean_spacing=%.3fs "
                 "Tblock=%.3fs -> Phi=%+.3fs (|Phi| <= %.3fs)\n",
                 pindexTip->nHeight, window, mean_spacing, Tblock, phi, M);
    }
    return phi;
}

bool WPoASortitionActiveAtHeight(int height)
{
    // Sortition consumes the RANDAO beacon seed as its public VRF input, so it can
    // only engage where the beacon already governs the height. Being a pure
    // function of shared data (flags + chain params + height), the miner and every
    // validator agree from the height alone which blocks are sortition-governed.
    return g_wpoa_sortition_enabled && WPoARANDAOActiveAtHeight(height);
}

// ---------------------------------------------------------------------------
// Shared context: the beacon seed over `pindexTip`, the confirmed weight map
// corrected by the behavioural malus, and its effective-weight sum Σ_j f(w_j).
// Read the SAME way on the miner, the validator and the read-only audit RPCs so
// all three derive identical scores/delays. Returns false when the seed or a
// usable weight map is unavailable — the caller then stands down / accepts
// leniently rather than acting on a half-synced view.
//
// Determinism note: Σ f(w_j) is summed in the std::map's sorted-key (address) order
// by WPoASelector::TotalEffectiveWeight, which is identical on every node, so the
// floating-point sum is reproducible.
// ---------------------------------------------------------------------------
bool WPoABuildRoundContext(const CBlockIndex* pindexTip, int height,
                           WPoARoundContext& out)
{
    if (pwalletTxsMain == NULL)
    {
        return false;
    }

    // Seed selection mirrors the miner (miner.cpp): the RANDAO beacon where it
    // governs the height and can be derived, the previous block hash otherwise. An
    // audit at a historical height therefore reproduces the seed that actually
    // governed it.
    WPoARoundContext ctx;
    ctx.height = height;
    if (WPoARANDAOActiveAtHeight(height))
    {
        // Beacon-governed height: the seed MUST come from the accumulator. A failure
        // here is not recoverable by falling back — the validator would derive a
        // different seed and the two would disagree on the proposer — so the caller
        // stands down, exactly as before this context was shared with the RPCs.
        if (!WPoARandaoSelectionSeed(pindexTip, ctx.seed))
        {
            return false;
        }
        ctx.randao_seed = true;
    }
    else
    {
        if (pindexTip == NULL)
        {
            return false;
        }
        uint256 h = pindexTip->GetBlockHash();
        memcpy(ctx.seed, h.begin(), sizeof(ctx.seed));
        ctx.randao_seed = false;
    }

    StreamWeightRegistry registry(pwalletTxsMain);
    ctx.raw_weights = registry.GetAllNodesWeights();
    if (ctx.raw_weights.empty())
    {
        return false;
    }

    // w_eff = w * Psi (Def. psi-peso-effettivo): the sortition scores the
    // behaviourally corrected weight, never the raw registry value. Returns the map
    // unchanged when the malus registry is disabled or nobody carries a proved
    // violation.
    ctx.weights = WPoAApplyMalus(ctx.raw_weights, height);

    ctx.total_eff_weight = WPoASelector::TotalEffectiveWeight(ctx.weights, g_dumping_function);
    if (!(ctx.total_eff_weight > 0.0))
    {
        return false;
    }

    out = ctx;
    return true;
}

bool WPoASortitionLocalScoreDelay(const CBlockIndex* pindexTip,
                                  const std::string& address,
                                  const unsigned char* sk32,
                                  double* score_out, double* delay_out)
{
    if (pindexTip == NULL)
    {
        return false;
    }

    const int height = pindexTip->nHeight + 1;

    WPoARoundContext ctx;
    if (!WPoABuildRoundContext(pindexTip, height, ctx))
    {
        return false;
    }
    const double weff = ctx.total_eff_weight;

    // Only a weighted validator can self-elect; a node absent from the registry (or
    // whose effective weight the malus has driven to 0) has an infinite score and
    // never proposes.
    std::map<std::string, uint32_t>::const_iterator it = ctx.weights.find(address);
    if (it == ctx.weights.end() || it->second == 0)
    {
        return false;
    }
    uint32_t weight = it->second;

    std::vector<unsigned char> input;
    PrivateSortition::VRFInput(ctx.seed, (uint32_t)height, input);

    unsigned char vrf_out[WPoAVRF::OUTPUT_SIZE];
    unsigned char vrf_proof[WPoAVRF::PROOF_SIZE];
    if (!WPoAVRF::Prove(sk32, input.data(), input.size(), vrf_out, vrf_proof))
    {
        return false;
    }

    double score = PrivateSortition::ScoreFromVRFOutput(vrf_out, weight, g_dumping_function);
    double delay = PrivateSortition::MiningDelay(score, weff,
                                                 (double)Params().TargetSpacing(),
                                                 g_wpoa_sortition_delta,
                                                 g_wpoa_sortition_lambda,
                                                 WPoASortitionFeedback(pindexTip));

    *score_out = score;
    *delay_out = delay;
    return true;
}

bool WPoASortitionVRFInputForBlock(const CBlock* block,
                                   std::vector<unsigned char>& input_out)
{
    if (block == NULL)
    {
        return false;
    }

    BlockMap::iterator mi = mapBlockIndex.find(block->hashPrevBlock);
    if (mi == mapBlockIndex.end() || mi->second == NULL)
    {
        return false;
    }
    const CBlockIndex* pprev = mi->second;
    const int height = pprev->nHeight + 1;

    if (!WPoASortitionActiveAtHeight(height))
    {
        return false;
    }

    unsigned char seed[32];
    if (!WPoARandaoSelectionSeed(pprev, seed))
    {
        return false;
    }

    PrivateSortition::VRFInput(seed, (uint32_t)height, input_out);
    return true;
}

WPoASortitionVerdict WPoASortitionVerifyProposer(const CBlockIndex* pindexParent,
                                                 int height,
                                                 const std::vector<unsigned char>& pubkey,
                                                 const std::string& miner_addr,
                                                 const std::vector<unsigned char>& vrf_reveal,
                                                 const std::vector<unsigned char>& vrf_proof,
                                                 uint32_t block_ntime,
                                                 std::string* reason_out)
{
    // Recompute the beacon seed over the parent (the same tip the honest miner saw).
    // If it cannot be recomputed locally (degenerate tip), accept leniently rather
    // than stall — an honest block stays valid on any node that CAN recompute it.
    unsigned char seed[32];
    if (pindexParent == NULL || !WPoARandaoSelectionSeed(pindexParent, seed))
    {
        return WPOA_SORTITION_SKIP;
    }

    // 1) The VRF proof must verify over the sortition input (seed ‖ "PROPOSER" ‖ n).
    //    This is unforgeable (VRF uniqueness) and independent of the weight map, so
    //    it is enforced even on the empty-registry leniency path below.
    std::vector<unsigned char> input;
    PrivateSortition::VRFInput(seed, (uint32_t)height, input);
    if (!WPoAVRF::Verify(pubkey, input, vrf_reveal, vrf_proof))
    {
        if (reason_out) *reason_out = "invalid or missing VRF reveal over the sortition input";
        return WPOA_SORTITION_REJECT;
    }

    // 2) Read the confirmed weight map. Empty ⇒ weights not yet synced: cannot
    //    recompute the score, accept leniently (the VRF proof above still held).
    if (pwalletTxsMain == NULL)
    {
        return WPOA_SORTITION_SKIP;
    }
    StreamWeightRegistry registry(pwalletTxsMain);
    std::map<std::string, uint32_t> weights = registry.GetAllNodesWeights();
    if (weights.empty())
    {
        return WPOA_SORTITION_SKIP;
    }

    // Same correction the honest miner applied when it scored itself (Def. 5.22):
    // both sides must consume w_eff, or they compute different delays and disagree.
    weights = WPoAApplyMalus(weights, height);

    // The signer must be a weighted validator (mirrors the Phase-2 recompute: a
    // block from a non-registered miner would fail the argmin check there too). A
    // validator whose effective weight the malus has zeroed is ineligible here too.
    std::map<std::string, uint32_t>::const_iterator it = weights.find(miner_addr);
    if (it == weights.end() || it->second == 0)
    {
        if (reason_out) *reason_out = "signer is not a weighted validator in the registry";
        return WPOA_SORTITION_REJECT;
    }
    uint32_t weight = it->second;

    double weff = 0.0;
    for (std::map<std::string, uint32_t>::const_iterator jt = weights.begin();
         jt != weights.end(); ++jt)
    {
        weff += WPoASelector::ApplyDumping(jt->second, g_dumping_function);
    }
    if (!(weff > 0.0))
    {
        return WPOA_SORTITION_SKIP;
    }

    // 3) Time bar: the block's nTime must be no earlier than the proposer's score
    //    entitles. delay is floored to whole seconds (block times have 1s
    //    resolution); the fine sub-second ordering is done miner-side. This bounds
    //    front-running: a lower earliest-time needs a lower score (unforgeable) or a
    //    future timestamp (bounded by the base-consensus time-too-new rule).
    double score = PrivateSortition::ScoreFromVRFOutput(vrf_reveal.data(), weight, g_dumping_function);
    double delay = PrivateSortition::MiningDelay(score, weff,
                                                 (double)Params().TargetSpacing(),
                                                 g_wpoa_sortition_delta,
                                                 g_wpoa_sortition_lambda,
                                                 WPoASortitionFeedback(pindexParent));

    int64_t parent_ntime = pindexParent->GetBlockTime();
    int64_t earliest     = parent_ntime + (int64_t)delay;   // (int64_t)delay == floor for delay >= 0
    if ((int64_t)block_ntime < earliest)
    {
        if (reason_out)
        {
            *reason_out = strprintf("block mined too early for its sortition score "
                                    "(nTime %u < parent %ld + delay %ds; score=%.9g)",
                                    block_ntime, (long)parent_ntime, (int)delay, score);
        }
        return WPOA_SORTITION_REJECT;
    }

    if (fDebug)
    {
        LogPrint("wpoa", "[wpoa-sortition] verify OK height=%d signer=%s score=%.9g delay=%ds "
                 "nTime=%u parent=%ld\n",
                 height, miner_addr.c_str(), score, (int)delay, block_ntime, (long)parent_ntime);
    }
    return WPOA_SORTITION_OK;
}

// ---------------------------------------------------------------------------
// Miner-loop guard: highest height this node has already proposed a block for.
// Serialized by a leaf lock (the miner loop touches it from two functions).
// ---------------------------------------------------------------------------
static CCriticalSection cs_sortition_proposed;
static int g_sortition_proposed_height = -1;

void WPoASortitionMarkProposed(int height)
{
    LOCK(cs_sortition_proposed);
    if (height > g_sortition_proposed_height)
    {
        g_sortition_proposed_height = height;
    }
}

bool WPoASortitionAlreadyProposed(int height)
{
    LOCK(cs_sortition_proposed);
    return height <= g_sortition_proposed_height;
}
