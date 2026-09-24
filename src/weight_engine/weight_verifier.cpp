// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — node-coupled half of the published-weight verification.
// See weight_verifier.h for the rationale, the fail-open/fail-closed asymmetry and
// the cost argument. This file holds only the orchestration: run the recomputation,
// compare, cache the verdicts, and expose them. The RPC that reports them,
// weightverifyweights, lives in rpc/rpcweightengine.cpp.

#include "weight_engine/weight_verifier.h"

#include "weight_engine/weight_engine.h"   // HeightToEpoch, g_weight_engine_enabled
#include "weight_engine/weight_reader.h"   // WeightStreamReader
#include "weight_engine/weight_streams.h"  // MC_WEIGHT_DEFAULT_STABILITY_MARGIN

#include "core/init.h"          // pwalletTxsMain
#include "core/main.h"          // chainActive, cs_main, CBlockIndex
#include "utils/util.h"         // LogPrintf
#include "utils/sync.h"         // CCriticalSection, LOCK

using namespace std;

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

// ---------------------------------------------------------------------------
// Recomputation memo
// ---------------------------------------------------------------------------
// WHY. The malus fold (MalusRegistry::GetAccumulators) re-validates EVERY report on
// every call, and it is called on the consensus path: once per round by each miner,
// once per received block by every node (under cs_main), and by every audit RPC. For a
// `badweight` report the validation is a full recomputation, which walks every block
// from epoch 1. Measured on a 100-epoch regional run, one walk near the end costs 2-3 s,
// so a few dozen accepted reports turn each fold into tens of seconds against an 8 s
// block time. The recomputation of a buried epoch is a pure function of inputs that do
// not change once buried, so the second and every later call can be answered from here.
//
// WHAT IT IS A FUNCTION OF, and so what the key holds — all of it, so that a hit returns
// exactly what WeightEngineComputeAllWeightsForEpoch would return now:
//   * the block prefix up to the epoch's last height. The hash of the active chain's
//     block at that height commits to every block before it;
//   * the membership and ESG maps. These are read "latest confirmed wins", NOT scoped to
//     a height, so a record confirmed later can change a past epoch's recomputation.
//     They are re-read on every call (a small stream read) and compared whole.
// The params (kappa, lambda, epoch length, treasury) are hash-enforced and fixed for the
// process. The burial gate is re-applied on every call, before the memo is consulted, so
// an epoch a reorg has un-buried fails exactly as it would without the memo.
//
// The one input not in the key is the block DATA being readable: a node that pruned an
// epoch after memoizing it would answer where the uncached walk fails closed. This
// fork's nodes do not prune (weight_reader.cpp fails closed on BLOCK_HAVE_DATA for that
// reason), so the case is noted rather than handled.
//
// Guarded by its own lock, never held while cs_main is taken or while computing: the
// consensus-path callers may already hold cs_main, so the only order that occurs is
// cs_main -> cs_recomputeMemo.

namespace {

struct RecomputeMemoKey
{
    uint256 last_block_hash;                                   // active chain at lastH
    std::map<std::string, std::set<std::string> > clusters;   // membership, as read
    std::map<std::string, double> esg;                         // ESG, as read

    bool operator==(const RecomputeMemoKey& o) const
    {
        return last_block_hash == o.last_block_hash && clusters == o.clusters && esg == o.esg;
    }
};

struct RecomputeMemoEntry
{
    RecomputeMemoKey key;
    std::map<std::string, uint32_t> weights;
};

CCriticalSection cs_recomputeMemo;
std::map<uint32_t, RecomputeMemoEntry> g_recompute_memo;   // one entry per epoch

// The key for `epoch` as the chain and the streams stand now. False when the epoch is not
// buried (the same gate as WeightStreamReader::ComputeEpochFacts) or the static inputs
// are unreadable -- the two cases the uncached walk also fails on before scanning.
bool CurrentRecomputeKey(WeightStreamReader& reader, uint32_t epoch, RecomputeMemoKey& out)
{
    const int len = g_weight_epoch_length;
    if (len < 1)
    {
        return false;
    }
    const int64_t lastH = (int64_t)epoch * (int64_t)len - 1;
    {
        LOCK(cs_main);
        const int stableHeight = chainActive.Height() - MC_WEIGHT_DEFAULT_STABILITY_MARGIN;
        if (lastH < 0 || lastH > (int64_t)stableHeight)
        {
            return false;
        }
        CBlockIndex* p = chainActive[(int)lastH];
        if (p == NULL)
        {
            return false;
        }
        out.last_block_hash = p->GetBlockHash();
    }
    return reader.ReadMembership(out.clusters) && reader.ReadEsg(out.esg);
}

} // namespace

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

    RecomputeMemoKey key;
    if (!CurrentRecomputeKey(reader, epoch, key))
    {
        return false;   // undecided: epoch not buried, or static inputs unreadable
    }

    std::map<std::string, uint32_t> all;
    bool hit = false;
    {
        LOCK(cs_recomputeMemo);
        std::map<uint32_t, RecomputeMemoEntry>::const_iterator mi = g_recompute_memo.find(epoch);
        if (mi != g_recompute_memo.end() && mi->second.key == key)
        {
            all = mi->second.weights;
            hit = true;
        }
    }

    if (!hit)
    {
        if (!WeightEngineComputeAllWeightsForEpoch(reader, epoch, all))
        {
            return false;   // undecided: inputs unreadable, epoch not buried, pruned
        }
        // Store only if nothing the result depends on moved while it was computed: the
        // walk takes its own snapshot of the chain and the streams, and a reorg or a new
        // membership/ESG record in between would pair this result with the wrong key.
        RecomputeMemoKey after;
        if (CurrentRecomputeKey(reader, epoch, after) && after == key)
        {
            LOCK(cs_recomputeMemo);
            RecomputeMemoEntry& entry = g_recompute_memo[epoch];
            entry.key = key;
            entry.weights = all;
        }
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
