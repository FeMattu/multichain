// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — node-coupled glue.
// ------------------------------------------------------------------------------
// Holds the runtime configuration globals (bound to the WeightEngine chain
// parameters / CLI flags in AppInit2, src/core/init.cpp) and the background
// orchestration that, each epoch, reads the four public input streams, folds them
// forward through the pure core (weight_engine.h) and publishes THIS node's own
// cluster weight w_k to the wpoa-weights stream — reusing StreamWeightRegistry as
// the publication port, exactly as the static -weight path did.
//
// The pure math stays header-only in weight_engine.h; everything node-coupled
// (stream reads, epoch trigger off the chain tip, publish, thread) lives here and
// in weight_reader.{h,cpp}.

#include "weight_engine/weight_engine.h"
#include "weight_engine/weight_reader.h"

#include "wpoa/stream_weight_registry.h"  // StreamWeightRegistry (publish port), g_wpoa_weights_enabled
#include "core/init.h"                     // pwalletMain, pwalletTxsMain, ShutdownRequested
#include "core/main.h"                     // chainActive, cs_main, IsInitialBlockDownload
#include "utils/util.h"                    // LogPrintf, RenameThread, GetBoolArg
#include "utils/utiltime.h"                // MilliSleep

#include <map>
#include <set>
#include <string>
#include <vector>

// ---------------------------------------------------------------------------
// Runtime configuration globals (defaults from weight_streams.h; AppInit2
// overwrites them with the resolved chain-parameter / flag values).
// ---------------------------------------------------------------------------

/** -enableweightengine (default off): compute+publish w_k each epoch. */
bool g_weight_engine_enabled = false;

/** -weightepochlength: epoch length in blocks (epoch(height) = height / this). */
int g_weight_epoch_length = MC_WEIGHT_DEFAULT_EPOCH_LENGTH;

/** -weightkappa: normalization constant kappa > 0. */
double g_weight_kappa = MC_WEIGHT_DEFAULT_KAPPA;

/** -weightalpha: allocation constant alpha in [0,1]. */
double g_weight_alpha = MC_WEIGHT_DEFAULT_ALPHA;

/** -weightlambda: feedback damping lambda in [0,1). */
double g_weight_lambda = MC_WEIGHT_DEFAULT_LAMBDA;

// Retry pacing for the background thread (mirrors the wpoa registry thread).
static const int MC_WEIGHT_RETRY_INTERVAL_MS = 3000;

// ---------------------------------------------------------------------------
// Epoch mapping / activation predicate
// ---------------------------------------------------------------------------

// epoch(height) = height / epochlength + 1  (1-based, so the thesis' e = 1 special
// case — w_k = W_k, no feedback — covers the first epochlength blocks). Every node
// derives the same epoch from the height alone.
uint32_t HeightToEpoch(int height)
{
    int len = (g_weight_epoch_length > 0) ? g_weight_epoch_length : MC_WEIGHT_DEFAULT_EPOCH_LENGTH;
    if (height < 0)
    {
        height = 0;
    }
    return (uint32_t)(height / len) + 1;
}

// The weight engine governs the weights at `height` when it is enabled. (The
// dependency on the wpoa-weights stream is enforced once at flag-parse time.)
bool WeightEngineActiveAtHeight(int height)
{
    return g_weight_engine_enabled && height >= 0;
}

// ---------------------------------------------------------------------------
// Background orchestration
// ---------------------------------------------------------------------------

// address -> value lookups that never mutate the map (no operator[] insertion).
static uint32_t LookupTau(const std::map<std::string, uint32_t>& m, const std::string& k)
{
    std::map<std::string, uint32_t>::const_iterator it = m.find(k);
    return (it != m.end()) ? it->second : 0;
}
static double LookupDouble(const std::map<std::string, double>& m, const std::string& k)
{
    std::map<std::string, double>::const_iterator it = m.find(k);
    return (it != m.end()) ? it->second : 0.0;
}

// True once the node can create/publish and reliably read: a chain tip exists and
// (unless -offline) the initial block download has finished. Same gate as the wpoa
// registration thread.
static bool NodeReadyForWeight()
{
    {
        LOCK(cs_main);
        if (chainActive.Tip() == NULL)
        {
            return false;
        }
    }
    if (GetBoolArg("-offline", false))
    {
        return true;
    }
    return !IsInitialBlockDownload();
}

// Compute THIS node's own integer cluster weight for `target_epoch` by folding the
// pipeline forward from epoch 1 using purely public on-chain inputs (so every
// honest node derives the same value). Returns false when the inputs are not yet
// readable or the local node is not a cluster miner (nothing to publish).
static bool ComputeLocalWeightForEpoch(WeightStreamReader& reader, const std::string& local_miner,
                                       uint32_t target_epoch, uint32_t& out_weight)
{
    // Static inputs (latest confirmed wins).
    std::map<std::string, std::set<std::string> > clusters;
    std::map<std::string, double> esg;
    if (!reader.ReadMembership(clusters) || !reader.ReadEsg(esg))
    {
        return false;
    }

    // The local node only publishes a weight if it is itself a cluster miner.
    if (clusters.find(local_miner) == clusters.end())
    {
        return false;
    }

    // Reconciliation R (admin-attested stream), bucketed by epoch in one pass.
    // Activity tau is NOT a stream: it is derived per-epoch from the blocks below.
    std::map<uint32_t, std::map<std::string, double> > r_by_epoch;
    if (!reader.ReadReconciliationByEpoch(r_by_epoch))
    {
        return false;
    }

    const std::map<std::string, double> empty_r;

    WeightEngine::Params params(g_weight_kappa, g_weight_alpha, g_weight_lambda);
    std::map<std::string, WeightEngine::ClusterState> state;   // empty -> B_0 = 0 at epoch 1
    std::map<std::string, WeightEngine::ClusterResult> results;

    for (uint32_t e = 1; e <= target_epoch; e++)
    {
        // tau_e is DERIVED deterministically from epoch e's confirmed blocks (no
        // stream). If e is not yet buried or its block/undo data is unavailable we
        // cannot compute identically across nodes -> abort; the caller retries once
        // the epoch buries. (target_epoch is buried, so every e <= it is too.)
        std::map<std::string, uint32_t> tau_e;
        if (!reader.ComputeActivityForEpoch(e, tau_e))
        {
            return false;
        }
        std::map<uint32_t, std::map<std::string, double> >::const_iterator re = r_by_epoch.find(e);
        const std::map<std::string, double>& r_e = (re != r_by_epoch.end()) ? re->second : empty_r;

        // Build one ClusterInput per cluster (deterministic: clusters/companies are
        // sorted std::map / std::set, and ComputeEpoch re-sorts internally anyway).
        std::vector<WeightEngine::ClusterInput> inputs;
        inputs.reserve(clusters.size());
        for (std::map<std::string, std::set<std::string> >::const_iterator ci = clusters.begin();
             ci != clusters.end(); ++ci)
        {
            WeightEngine::ClusterInput in;
            in.miner      = ci->first;
            in.esg_miner  = LookupDouble(esg, ci->first);      // 0 if uncertified -> W_k = 0
            in.tau_miner  = LookupTau(tau_e, ci->first);
            in.reconciled = LookupDouble(r_e, ci->first);
            for (std::set<std::string>::const_iterator ai = ci->second.begin(); ai != ci->second.end(); ++ai)
            {
                WeightEngine::Company c;
                c.address = *ai;
                c.esg     = LookupDouble(esg, *ai);            // 0 if uncertified -> c_i = 0
                c.tau     = LookupTau(tau_e, *ai);
                in.companies.push_back(c);
            }
            inputs.push_back(in);
        }

        double theta = WeightEngine::NetworkActivity(inputs);
        std::map<std::string, WeightEngine::ClusterState> newstate;
        WeightEngine::ComputeEpoch(inputs, theta, state, params, e, results, newstate);
        state = newstate;
    }

    std::map<std::string, WeightEngine::ClusterResult>::const_iterator it = results.find(local_miner);
    if (it == results.end())
    {
        return false;
    }
    out_weight = it->second.integer_weight;
    return true;
}

// Background thread: ensures the three admin input streams exist and are subscribed
// (automatic, first-startup-on-the-genesis-node creation), then republishes this
// node's own w_k for the newest BURIED epoch. Launched from AppInit2 (in place of
// ThreadRegisterNodeWeight) when -enableweightengine is set.
void ThreadWeightEngine()
{
    RenameThread("mc-weight-engine");
    LogPrintf("[WeightEngine] background thread started (epochlen=%d, kappa=%g, alpha=%g, lambda=%g)\n",
              g_weight_epoch_length, g_weight_kappa, g_weight_alpha, g_weight_lambda);

    if (pwalletTxsMain == NULL || pwalletMain == NULL)
    {
        LogPrintf("[WeightEngine] wallet not available, aborting\n");
        return;
    }

    WeightStreamReader reader(pwalletTxsMain);
    StreamWeightRegistry registry(pwalletTxsMain);   // publication port for wpoa-weights
    std::string local = registry.GetLocalAddress();

    uint32_t last_published_epoch = 0;

    while (!ShutdownRequested())
    {
        MilliSleep(MC_WEIGHT_RETRY_INTERVAL_MS);
        if (ShutdownRequested())
        {
            break;
        }

        if (!NodeReadyForWeight())
        {
            continue;
        }

        // Auto-create (closed) + subscribe the three admin input streams. The first
        // node with create permission (the genesis / admin node) creates them;
        // everyone else finds them and subscribes. Not usable until confirmed.
        if (!reader.EnsureInputStreams())
        {
            continue;
        }

        int height = -1;
        {
            LOCK(cs_main);
            if (chainActive.Tip() != NULL)
            {
                height = chainActive.Height();
            }
        }
        if (height < 0 || !WeightEngineActiveAtHeight(height))
        {
            continue;
        }

        // Publish for the newest BURIED epoch only: the epoch whose last block sits at
        // least STABILITY_MARGIN below the tip. tau is derived from that epoch's
        // blocks, so computing an open / near-tip epoch could diverge under a reorg.
        const int len = g_weight_epoch_length;
        if (len < 1)
        {
            continue;
        }
        int stableHeight = height - MC_WEIGHT_DEFAULT_STABILITY_MARGIN;
        if (stableHeight < 0)
        {
            continue; // nothing buried yet
        }
        uint32_t epoch = (uint32_t)((stableHeight + 1) / len);   // largest e with e*len-1 <= stableHeight
        if (epoch < 1 || epoch == last_published_epoch)
        {
            continue; // no buried epoch yet, or already published for it
        }

        uint32_t w = 0;
        if (!ComputeLocalWeightForEpoch(reader, local, epoch, w))
        {
            // Not a certified miner yet, or inputs incomplete / epoch not buried —
            // retry next tick without advancing the epoch marker.
            continue;
        }

        // Publish via the shared registry path (ensures wpoa-weights exists +
        // subscribed, idempotent when the value is unchanged).
        if (registry.RegisterLocalWeight(w))
        {
            LogPrintf("[WeightEngine] epoch %u (height %d): w_k = %u for %s\n",
                      epoch, height, w, local.c_str());
            last_published_epoch = epoch;
        }
    }

    LogPrintf("[WeightEngine] background thread stopped\n");
}
