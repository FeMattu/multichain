// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — node-coupled half of the published-weight verification.
// See weight_verifier.h for the rationale, the fail-open/fail-closed asymmetry and
// the cost argument. This file holds only the orchestration: run the recomputation,
// compare, cache the verdicts, and expose them.

#include "weight_engine/weight_verifier.h"

#include "weight_engine/weight_engine.h"   // HeightToEpoch, g_weight_engine_enabled
#include "weight_engine/weight_reader.h"   // WeightStreamReader

#include "rpc/rpcwallet.h"      // JSONRPCError, RPC error codes
#include "core/init.h"          // pwalletTxsMain
#include "utils/util.h"         // LogPrintf
#include "utils/sync.h"         // CCriticalSection, LOCK

#include <stdexcept>

using namespace std;
using namespace json_spirit;

// ---------------------------------------------------------------------------
// Verdict cache
// ---------------------------------------------------------------------------
// Written once per buried epoch by the weight-engine thread, read by the RPC surface
// (and, once the malus wires the consequence, by the consensus path). Guarded by its
// own lock rather than piggy-backing on cs_main: the writer already holds no lock at
// that point, and the readers must not be able to stall block processing.
//
// Only the LAST verified epoch is kept. Verification is a statement about the state a
// published record should reflect, and only the most recent buried epoch is actionable
// — an older verdict would be about a value that has since been legitimately
// superseded. Keeping one epoch also makes the cache O(clusters) rather than
// O(clusters * epochs).

static CCriticalSection cs_weightVerdicts;
static uint32_t g_verified_epoch = 0;
static std::map<std::string, WeightVerificationEntry> g_verdicts;

// ---------------------------------------------------------------------------
// Verification
// ---------------------------------------------------------------------------

bool WeightEngineVerifyAndCacheEpoch(WeightStreamReader& reader, uint32_t epoch,
                                     const std::map<std::string, uint32_t>& published,
                                     const std::map<std::string, uint32_t>& published_epochs)
{
    // Recompute every cluster from the public inputs. A failure here is NOT a finding
    // about anybody: it means this node cannot verify right now (inputs unreadable,
    // epoch not buried), so every verdict must come out UNVERIFIED and the filter must
    // leave the published map alone. See the fail-open discussion in the header.
    std::map<std::string, uint32_t> recomputed;
    bool ok = WeightEngineComputeAllWeightsForEpoch(reader, epoch, recomputed);

    std::map<std::string, WeightVerificationEntry> verdicts;
    mc_VerifyPublishedWeights(published, published_epochs, epoch, recomputed, ok, verdicts);

    {
        LOCK(cs_weightVerdicts);
        g_verified_epoch = epoch;
        g_verdicts = verdicts;
    }

    if (!ok)
    {
        LogPrintf("[WeightEngine] epoch %u: published weights NOT verified "
                  "(inputs not yet readable) — %u record(s) left untouched\n",
                  epoch, (unsigned)published.size());
        return false;
    }

    // Count what was actually COMPARED, so the log distinguishes "everything checked out"
    // from "nothing was about this epoch". Reporting the latter as a clean pass would hide
    // the fact that nothing was verified at all.
    size_t compared = 0;
    for (std::map<std::string, WeightVerificationEntry>::const_iterator it = verdicts.begin();
         it != verdicts.end(); ++it)
    {
        if (it->second.verdict == MC_WEIGHT_VERDICT_OK ||
            mc_WeightVerdictIsInvalid(it->second.verdict))
        {
            compared++;
        }
    }

    const size_t invalid = mc_CountInvalidVerdicts(verdicts);
    if (invalid == 0)
    {
        LogPrintf("[WeightEngine] epoch %u: %u of %u published weight(s) checked against "
                  "the independent recomputation, all matching (%u about another epoch or "
                  "not epoch-stamped)\n",
                  epoch, (unsigned)compared, (unsigned)verdicts.size(),
                  (unsigned)(verdicts.size() - compared));
        return true;
    }

    // A mismatch is a provable protocol violation, so it is logged unconditionally
    // (not only under -wpoadebug) with both values: that pair, plus the public inputs
    // of the epoch, is the whole evidence a third party needs to re-derive the finding.
    LogPrintf("[WeightEngine] epoch %u: %u of %u published weight(s) FAILED independent "
              "verification\n", epoch, (unsigned)invalid, (unsigned)verdicts.size());
    for (std::map<std::string, WeightVerificationEntry>::const_iterator it = verdicts.begin();
         it != verdicts.end(); ++it)
    {
        if (!mc_WeightVerdictIsInvalid(it->second.verdict))
        {
            continue;
        }
        if (it->second.verdict == MC_WEIGHT_VERDICT_NOT_A_CLUSTER)
        {
            LogPrintf("[WeightEngine]   %s: published %u but heads no cluster -> %s\n",
                      it->first.c_str(), it->second.published,
                      mc_WeightVerdictToString(it->second.verdict));
        }
        else
        {
            LogPrintf("[WeightEngine]   %s: published %u, recomputed %u -> %s\n",
                      it->first.c_str(), it->second.published, it->second.recomputed,
                      mc_WeightVerdictToString(it->second.verdict));
        }
    }
    return true;
}

bool WeightEngineRecomputeWeightForEpoch(uint32_t epoch, const std::string& address,
                                         bool& is_cluster, uint32_t& out_weight)
{
    is_cluster = false;
    out_weight = 0;

    if (!g_weight_engine_enabled || epoch < 1 || pwalletTxsMain == NULL)
    {
        return false;
    }

    // A reader of its own, rather than one shared with the engine thread: this is called
    // from the malus verification path, which may run on an RPC thread while the engine
    // thread is mid-fold. WeightStreamReader keeps only per-stream create/subscribe
    // guards, so a short-lived instance is cheap and avoids any cross-thread sharing.
    WeightStreamReader reader(pwalletTxsMain);

    std::map<std::string, uint32_t> all;
    if (!WeightEngineComputeAllWeightsForEpoch(reader, epoch, all))
    {
        return false;   // undecided: inputs unreadable, epoch not buried, pruned
    }

    std::map<std::string, uint32_t>::const_iterator it = all.find(address);
    if (it == all.end())
    {
        return true;    // decided: the address heads no cluster in that epoch
    }
    is_cluster = true;
    out_weight = it->second;
    return true;
}

std::map<std::string, WeightVerificationEntry> WeightEngineGetVerdicts(uint32_t epoch)
{
    LOCK(cs_weightVerdicts);
    if (epoch != g_verified_epoch || g_verified_epoch == 0)
    {
        return std::map<std::string, WeightVerificationEntry>();
    }
    return g_verdicts;
}

uint32_t WeightEngineLastVerifiedEpoch()
{
    LOCK(cs_weightVerdicts);
    return g_verified_epoch;
}

// ---------------------------------------------------------------------------
// RPC
// ---------------------------------------------------------------------------

Value weightverifyweights(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 0)
    {
        throw runtime_error(
            "weightverifyweights\n"
            "\nReports this node's INDEPENDENT verification of the weights published on\n"
            "wpoa-weights, for the most recent epoch it has verified.\n"
            "\nEvery input of the weight pipeline is public and deterministic — activity\n"
            "and reconciliation are chain-derived, membership and ESG are published — so\n"
            "any node can re-run the identical pipeline and check each published value.\n"
            "A value that does not match the recomputation is provably wrong and is\n"
            "dropped from the weight map the election consumes.\n"
            "\nESG is the one input that cannot be recomputed: it is an attestation, so\n"
            "this check verifies that a publisher applied the pipeline honestly to the\n"
            "published inputs, not that the ESG scores themselves are truthful. That\n"
            "rests on the Certification Authority role instead.\n"
            "\nVerification runs once per buried epoch in the weight-engine thread, so an\n"
            "epoch of 0 simply means it has not run yet on this node.\n"
            "\nResult:\n"
            "{\n"
            "  \"epoch\": n,               (numeric) the epoch verified, 0 if none yet\n"
            "  \"verified\": true|false,   (boolean) whether the recomputation succeeded\n"
            "  \"records\": n,             (numeric) published records examined\n"
            "  \"invalid\": n,             (numeric) records that failed verification\n"
            "  \"entries\": [\n"
            "    {\n"
            "      \"address\": \"...\",     (string)  the cluster the record is about\n"
            "      \"published\": n,       (numeric) the value found on chain\n"
            "      \"published_epoch\": n, (numeric) the epoch it was published FOR, 0 if unstated\n"
            "      \"recomputed\": n,      (numeric) the value this node derived\n"
            "      \"verdict\": \"...\"      (string)  ok | mismatch | not-a-cluster |\n"
            "                                       other-epoch | unverified\n"
            "    }, ...\n"
            "  ]\n"
            "}\n");
    }

    if (!g_weight_engine_enabled)
    {
        throw JSONRPCError(RPC_NOT_SUPPORTED,
                           "The weight engine is disabled on this node, so there is no "
                           "pipeline to recompute and nothing to verify. Published "
                           "weights are accepted on the self-publication rule alone "
                           "(signer == node_address). Enable -enableweightengine to "
                           "verify values as well.");
    }

    const uint32_t epoch = WeightEngineLastVerifiedEpoch();
    std::map<std::string, WeightVerificationEntry> verdicts = WeightEngineGetVerdicts(epoch);

    // "verified" is false when nothing has been verified yet AND when the last run
    // could not recompute — in the latter case every entry is UNVERIFIED, so the two
    // are distinguishable from `records`/`entries` without a third state.
    bool any_decided = false;
    size_t invalid = 0;
    Array entries;
    for (std::map<std::string, WeightVerificationEntry>::const_iterator it = verdicts.begin();
         it != verdicts.end(); ++it)
    {
        if (it->second.verdict != MC_WEIGHT_VERDICT_UNVERIFIED)
        {
            any_decided = true;
        }
        if (mc_WeightVerdictIsInvalid(it->second.verdict))
        {
            invalid++;
        }

        Object e;
        e.push_back(Pair("address", it->first));
        e.push_back(Pair("published", (int64_t)it->second.published));
        e.push_back(Pair("published_epoch", (int64_t)it->second.published_epoch));
        e.push_back(Pair("recomputed", (int64_t)it->second.recomputed));
        e.push_back(Pair("verdict", string(mc_WeightVerdictToString(it->second.verdict))));
        entries.push_back(e);
    }

    Object out;
    out.push_back(Pair("epoch", (int64_t)epoch));
    out.push_back(Pair("verified", any_decided));
    out.push_back(Pair("records", (int64_t)verdicts.size()));
    out.push_back(Pair("invalid", (int64_t)invalid));
    out.push_back(Pair("entries", entries));
    return out;
}
