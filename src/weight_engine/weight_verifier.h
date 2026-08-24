// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — universal verification of published weights.
// ------------------------------------------------------------------------------
// WHY THIS EXISTS. Under the self-published model every node computes and publishes
// w_k for its OWN cluster, so the network no longer relies on a single trusted
// publisher per cluster. That removes a centralization, but on its own it would
// replace "trust one publisher" with "trust every publisher": a miner could publish
// any number it liked for its own cluster and the reader would accept it, because the
// self-publication rule only establishes WHO wrote the record, not whether the VALUE
// is right.
//
// It is now possible to check the value too, and that is what this component does.
// Every input of the pipeline is public and deterministic:
//
//   tau_i^{(e)}      chain-derived from the epoch's confirmed blocks
//   C_k              chain-derived, self-attested membership records
//   R_k^{(e)}        published on chain
//   ESG_i            published on chain
//
// so any honest node can re-run the identical pipeline over the identical public
// inputs and arrive at the identical integer w_k. A published value that does not
// match the recomputation is provably wrong — not a matter of opinion — and can be
// rejected by every node independently, with no coordination and no privileged
// auditor. This is the same epistemic move the malus registry makes: trust the
// EVIDENCE, not the publisher.
//
// EXACT INTEGER EQUALITY is the right comparison, and it is safe because of the
// determinism disciplines already imposed on the pipeline (weight-engine.md §3.1):
// double precision throughout, sums taken in ascending-address order, a zero
// denominator yielding 0 rather than NaN, and ToIntegerWeight rounding
// half-away-from-zero into [1, UINT32_MAX]. Two honest nodes on the same chain state
// produce the same uint32_t, so a tolerance band is unnecessary and would only create
// a margin for a dishonest publisher to hide in.
//
// ESG IS THE ONE INPUT THAT CANNOT BE RECOMPUTED, and therefore the one remaining
// trusted datum in the whole system. Recomputation verifies that a publisher applied
// the pipeline honestly to the published inputs; it cannot verify that the ESG scores
// themselves are truthful, because an ESG score is an attestation with nothing inside
// it to check. The integrity of the weights therefore rests entirely on the
// Certification Authority role that gates ESG writes. Everything else is now
// self-checking.
//
// ------------------------------------------------------------------------------
// TWO RULES, TWO FAILURE DIRECTIONS — the asymmetry is deliberate
// ------------------------------------------------------------------------------
// The self-publication rule (signer == node_address, wpoa/weight_record.h) FAILS
// CLOSED: it is decidable from the single publishing transaction, that evidence is
// always available, so its absence means the record is undecodable and it is
// discarded.
//
// Value verification FAILS OPEN: it needs readable input streams and a BURIED epoch,
// and their absence is entirely normal — a freshly started node, a node still syncing,
// an epoch not yet buried. Treating "cannot verify" as "invalid" would zero every
// weight on such a node and stall the chain, so an unavailable recomputation yields
// MC_WEIGHT_VERDICT_UNVERIFIED and the filter below leaves those entries untouched.
// Only a recomputation that SUCCEEDED and DISAGREED is a finding.
//
// ------------------------------------------------------------------------------
// WHICH EPOCH IS VERIFIED, and why not every record is checked every time
// ------------------------------------------------------------------------------
// A weight is a claim about a SPECIFIC epoch, so it may only be compared against that
// epoch's recomputation. The record therefore carries the epoch it was computed for, and
// a record about any other epoch — or about none, as with the static -weight path — is
// reported as MC_WEIGHT_VERDICT_OTHER_EPOCH and left alone. Without that scoping, a value
// legitimately published for epoch e would be flagged as wrong the moment epoch e+1
// arrived, and the malus would turn the false accusation into a real weight penalty.
// (This was observed in a live run before the epoch field existed: an honest node's own
// weight was reported as failing verification on every epoch rollover.)
//
// Publication necessarily LAGS the epoch it describes — a node can only compute w_k^(e)
// once epoch e is buried, so its record for e lands during e+1. Verification therefore
// targets the PREVIOUS epoch: at epoch e it checks the records for e-1, by which time
// every honest node has had a full epoch to publish. That is also the inter-epoch
// alignment the rest of the system already uses (rho^(e-1) drives w^(e), and a proved
// malus takes effect from the epoch after).
//
// TWO CONSEQUENCES worth being explicit about:
//
//   * A node whose weight did not change publishes nothing, because RegisterLocalWeight
//     is idempotent. No record is stamped for that epoch, so that node is simply not
//     compared that round — correctly: there is no new claim to check. Its previous
//     record was checked when it was made.
//   * Verification therefore catches every DISHONEST PUBLICATION, not every node every
//     epoch. That is the right target: to gain from a wrong weight a node must publish
//     it, and any publication it makes is epoch-stamped and gets compared. A node that
//     stops publishing keeps its last confirmed weight — pre-existing behaviour of the
//     newest-confirmed-wins stream, not something this mechanism introduces.
//
// ------------------------------------------------------------------------------
// COST, and why verification runs per epoch rather than per round
// ------------------------------------------------------------------------------
// Verifying every cluster is O(number of clusters) recomputations per epoch, against
// O(1) for blindly trusting a publisher. The marginal cost is however far smaller than
// that suggests: ComputeAllWeightsForEpoch already folds the pipeline forward across
// EVERY cluster (it always did — the previous code computed the whole map and then
// used a single entry), so verification adds a map comparison to work already done.
//
// What would be prohibitive is running it in the consensus hot path.
// GetAllNodesWeights() is called by the miner and by every validator on every round,
// while recomputation must fold forward from epoch 1 and scan each epoch's blocks —
// O(chain) work. So verification runs where the fold already happens, once per buried
// epoch inside ThreadWeightEngine, and deposits its verdicts in a cache that the
// consensus path can consult in O(1).
//
// The pure comparison and filter below are node-free and unit-tested in isolation
// (test/weight_verifier_tests.cpp); the node-coupled orchestration lives in
// weight_verifier.cpp.

#ifndef MC_WEIGHT_VERIFIER_H
#define MC_WEIGHT_VERIFIER_H

#include <map>
#include <string>
#include <stdint.h>

#include "json/json_spirit_value.h"   // for the RPC declaration at the end

// ---------------------------------------------------------------------------
// Verdicts
// ---------------------------------------------------------------------------

/** The outcome of checking one published weight against an independent recomputation. */
enum WeightVerdict
{
    /** No recomputation was available for this address — inputs unreadable, epoch not
     *  yet buried, or the weight engine disabled. NOT a finding: see the fail-open
     *  discussion above. The entry is left alone. */
    MC_WEIGHT_VERDICT_UNVERIFIED = 0,

    /** The published value equals the independently recomputed one. */
    MC_WEIGHT_VERDICT_OK,

    /** The recomputation succeeded and DISAGREED. Provably wrong: the record is
     *  dropped from the weight map and is grounds for a malus accusation. */
    MC_WEIGHT_VERDICT_MISMATCH,

    /** A weight was published for an address that heads no cluster at all, so there is
     *  nothing the pipeline could have produced for it. Distinguished from MISMATCH
     *  because the fault differs — publishing a weight for a non-cluster rather than a
     *  wrong weight for a real one — and an accurate reason makes the log and any
     *  accusation auditable. Treated as invalid, like MISMATCH. */
    MC_WEIGHT_VERDICT_NOT_A_CLUSTER,

    /** The record is about a DIFFERENT epoch than the one being verified, or does not
     *  say which epoch it is about at all (the static -weight path). NOT a finding.
     *
     *  This distinction is what keeps the mechanism from accusing honest nodes. A weight
     *  is a claim about a specific epoch: w_k^{(e)} is computed from epoch e's inputs.
     *  A node that legitimately published for epoch e still has that value standing when
     *  epoch e+1 comes round — publication necessarily lags the epoch it describes — and
     *  comparing it against e+1's recomputation would flag it as wrong. The malus would
     *  then turn that false accusation into a real weight penalty.
     *
     *  Kept separate from UNVERIFIED because the reasons differ and both are worth
     *  seeing: UNVERIFIED means *this node* could not recompute, OTHER_EPOCH means the
     *  record was not about the epoch recomputed. */
    MC_WEIGHT_VERDICT_OTHER_EPOCH
};

/** One address's verification result: what was published, which epoch it was published
 *  FOR, what was recomputed, and the verdict. `recomputed` is meaningful only for OK and
 *  MISMATCH; `published_epoch` is 0 when the record does not state one. */
struct WeightVerificationEntry
{
    uint32_t      published;
    uint32_t      published_epoch;
    uint32_t      recomputed;
    WeightVerdict verdict;

    WeightVerificationEntry()
        : published(0), published_epoch(0), recomputed(0),
          verdict(MC_WEIGHT_VERDICT_UNVERIFIED) {}
    WeightVerificationEntry(uint32_t p, uint32_t pe, uint32_t r, WeightVerdict v)
        : published(p), published_epoch(pe), recomputed(r), verdict(v) {}
};

/** Stable, operator-facing name of a verdict (for RPC output and logs). */
inline const char* mc_WeightVerdictToString(WeightVerdict v)
{
    switch (v)
    {
        case MC_WEIGHT_VERDICT_OK:             return "ok";
        case MC_WEIGHT_VERDICT_MISMATCH:       return "mismatch";
        case MC_WEIGHT_VERDICT_NOT_A_CLUSTER:  return "not-a-cluster";
        case MC_WEIGHT_VERDICT_OTHER_EPOCH:    return "other-epoch";
        case MC_WEIGHT_VERDICT_UNVERIFIED:
        default:                               return "unverified";
    }
}

/** True for a verdict that invalidates the record, i.e. one that must be dropped from
 *  the weight map. Single-sourced so the filter, the logs and any accusation agree on
 *  what "invalid" means. */
inline bool mc_WeightVerdictIsInvalid(WeightVerdict v)
{
    return v == MC_WEIGHT_VERDICT_MISMATCH || v == MC_WEIGHT_VERDICT_NOT_A_CLUSTER;
}

// ---------------------------------------------------------------------------
// Pure comparison and filter
// ---------------------------------------------------------------------------

/**
 * Compare a published weight map against an independent recomputation.
 *
 * @param published        address -> weight, as read from wpoa-weights.
 * @param published_epochs address -> the epoch each record was published FOR (0 when the
 *                         record does not state one).
 * @param epoch            The epoch `recomputed` was produced for. Only records claiming
 *                         THIS epoch are compared; see MC_WEIGHT_VERDICT_OTHER_EPOCH.
 * @param recomputed       address -> weight, from an independent run of the pipeline.
 * @param recompute_ok     Whether the recomputation actually succeeded. When false
 *                         every entry is UNVERIFIED regardless of `recomputed`: an
 *                         empty or partial map must never be read as "everyone is
 *                         wrong" (fail open).
 * @param out              [out] address -> verification entry (cleared first). One
 *                         entry per PUBLISHED address; a cluster that exists but has
 *                         published nothing simply has no entry, since there is no
 *                         record to accept or reject.
 */
inline void mc_VerifyPublishedWeights(const std::map<std::string, uint32_t>& published,
                                      const std::map<std::string, uint32_t>& published_epochs,
                                      uint32_t epoch,
                                      const std::map<std::string, uint32_t>& recomputed,
                                      bool recompute_ok,
                                      std::map<std::string, WeightVerificationEntry>& out)
{
    out.clear();

    for (std::map<std::string, uint32_t>::const_iterator it = published.begin();
         it != published.end(); ++it)
    {
        std::map<std::string, uint32_t>::const_iterator ei = published_epochs.find(it->first);
        const uint32_t rec_epoch = (ei != published_epochs.end()) ? ei->second : 0;

        if (!recompute_ok)
        {
            out[it->first] = WeightVerificationEntry(it->second, rec_epoch, 0,
                                                     MC_WEIGHT_VERDICT_UNVERIFIED);
            continue;
        }

        // ONLY compare like with like. A record about another epoch — or one that does
        // not say which epoch it is about — is left alone: see
        // MC_WEIGHT_VERDICT_OTHER_EPOCH for why conflating them would produce false
        // accusations against honest nodes.
        if (rec_epoch != epoch)
        {
            out[it->first] = WeightVerificationEntry(it->second, rec_epoch, 0,
                                                    MC_WEIGHT_VERDICT_OTHER_EPOCH);
            continue;
        }

        std::map<std::string, uint32_t>::const_iterator ri = recomputed.find(it->first);
        if (ri == recomputed.end())
        {
            // Published a weight for an address the pipeline knows no cluster for.
            out[it->first] = WeightVerificationEntry(it->second, rec_epoch, 0,
                                                     MC_WEIGHT_VERDICT_NOT_A_CLUSTER);
            continue;
        }

        out[it->first] = WeightVerificationEntry(
            it->second, rec_epoch, ri->second,
            (it->second == ri->second) ? MC_WEIGHT_VERDICT_OK
                                       : MC_WEIGHT_VERDICT_MISMATCH);
    }
}

/**
 * Drop every invalidated record from a published weight map.
 *
 * An address with no verdict keeps its weight — which is what makes the mechanism
 * inert on a node that has not verified anything yet, and inert on a clean chain.
 *
 * @param published  address -> weight, as read from wpoa-weights.
 * @param verdicts   address -> verification entry (may be empty, or cover a subset).
 * @param out        [out] the filtered map (cleared first).
 */
inline void mc_FilterVerifiedWeights(const std::map<std::string, uint32_t>& published,
                                     const std::map<std::string, WeightVerificationEntry>& verdicts,
                                     std::map<std::string, uint32_t>& out)
{
    out.clear();

    for (std::map<std::string, uint32_t>::const_iterator it = published.begin();
         it != published.end(); ++it)
    {
        std::map<std::string, WeightVerificationEntry>::const_iterator vi =
            verdicts.find(it->first);
        if (vi != verdicts.end() && mc_WeightVerdictIsInvalid(vi->second.verdict))
        {
            continue;   // provably wrong -> never reaches the election
        }
        out[it->first] = it->second;
    }
}

/** How many entries carry an invalidating verdict (for logs and RPC summaries). */
inline size_t mc_CountInvalidVerdicts(const std::map<std::string, WeightVerificationEntry>& verdicts)
{
    size_t n = 0;
    for (std::map<std::string, WeightVerificationEntry>::const_iterator it = verdicts.begin();
         it != verdicts.end(); ++it)
    {
        if (mc_WeightVerdictIsInvalid(it->second.verdict))
        {
            n++;
        }
    }
    return n;
}

// ---------------------------------------------------------------------------
// Node-coupled surface (defined in weight_verifier.cpp)
// ---------------------------------------------------------------------------

struct WeightStreamReader;

/**
 * Recompute every cluster's integer weight for `target_epoch` by folding the pipeline
 * forward from epoch 1 over the public on-chain inputs — the same computation each
 * honest node performs, which is what makes the comparison meaningful.
 *
 * Returns false when the inputs are not yet readable or the epoch is not buried; the
 * caller must then treat every verdict as UNVERIFIED rather than as a finding.
 */
bool WeightEngineComputeAllWeightsForEpoch(WeightStreamReader& reader,
                                           uint32_t target_epoch,
                                           std::map<std::string, uint32_t>& out_weights);

/**
 * Verify the published weight map for `epoch` and CACHE the verdicts, so the consensus
 * path can consult them without re-running the pipeline (see the cost discussion
 * above). Called once per buried epoch from ThreadWeightEngine.
 *
 * @return true when the recomputation succeeded (verdicts are meaningful).
 */
bool WeightEngineVerifyAndCacheEpoch(WeightStreamReader& reader, uint32_t epoch,
                                     const std::map<std::string, uint32_t>& published,
                                     const std::map<std::string, uint32_t>& published_epochs);

/**
 * Recompute ONE address's weight for `epoch` from the public inputs, for a third party
 * that needs to check a specific claim rather than survey the whole map.
 *
 * This is the narrow hook the malus registry uses to validate a `badweight` accusation:
 * re-running the identical pipeline is the entire proof, so the verifier must be able to
 * run it without depending on whether this node happened to cache that epoch.
 *
 * @param epoch       The epoch to recompute (1-based).
 * @param address     The cluster whose weight is wanted.
 * @param is_cluster  [out] false when `address` heads no cluster in that epoch, in which
 *                    case there is no weight the pipeline could have produced for it and
 *                    `out_weight` is 0. Reported separately from failure, because "not a
 *                    cluster" is an ANSWER while "cannot recompute" is not.
 * @param out_weight  [out] the recomputed integer weight.
 * @return false when the recomputation could not be performed at all — inputs not
 *         readable, epoch not buried, pruned node, engine disabled. The caller must then
 *         treat the question as undecided rather than answered: for an accusation that
 *         means it does not count.
 */
bool WeightEngineRecomputeWeightForEpoch(uint32_t epoch, const std::string& address,
                                         bool& is_cluster, uint32_t& out_weight);

/** The cached verdicts for `epoch`, or an empty map if that epoch was never verified. */
std::map<std::string, WeightVerificationEntry> WeightEngineGetVerdicts(uint32_t epoch);

/** The most recent epoch for which verdicts are cached; 0 when none. */
uint32_t WeightEngineLastVerifiedEpoch();

/** RPC: report the cached verification of the published weights (category "weight"). */
json_spirit::Value weightverifyweights(const json_spirit::Array& params, bool fHelp);

#endif // MC_WEIGHT_VERIFIER_H
