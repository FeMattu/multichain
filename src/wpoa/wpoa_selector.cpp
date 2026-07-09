// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA Phase 2 — node-coupled glue for the weighted proposer selector.
// The pure scoring/argmin core lives (header-only) in wpoa_selector.h so it
// can be unit-tested without the node; this file wires that core to the
// running node: the runtime flag, the height-based activation predicate, and
// the StreamWeightRegistry read.

#include "wpoa/wpoa_selector.h"

#include "wpoa/stream_weight_registry.h" // StreamWeightRegistry, GetAllNodesWeights
#include "core/init.h"                   // pwalletTxsMain
#include "utils/util.h"                  // LogPrint, LogPrintf, fDebug
#include "chainparams/state.h"           // mc_gState, IsProtocolMultichain,
                                         //   GetInt64Param, MCP_ANYONE_CAN_MINE

using namespace std;

// Default off: with the flag unset the node keeps its native round-robin
// mining-diversity behavior unchanged.
bool g_wpoa_enabled = false;

bool WPoAActiveAtHeight(int height)
{
    if (!g_wpoa_enabled)
    {
        return false;
    }
    if (mc_gState == NULL || mc_gState->m_NetworkParams == NULL)
    {
        return false;
    }
    // wPoA is a permissioned-miner mechanism over the MultiChain protocol.
    if (!mc_gState->m_NetworkParams->IsProtocolMultichain())
    {
        return false;
    }
    if (MCP_ANYONE_CAN_MINE)
    {
        return false;
    }
    // Engage only at/after the setup period, so the chain still bootstraps with
    // native rules (admin establishes permissions and the weight stream). This
    // predicate is a pure function of the height and chain params, so the miner
    // (next height) and the validator (received-block height) always agree on
    // whether a given block is governed by wPoA.
    int setup_blocks = (int)mc_gState->m_NetworkParams->GetInt64Param("setupfirstblocks");
    return height >= setup_blocks;
}

std::string WPoASelectProposer(const unsigned char* seed, size_t seed_len, int height)
{
    if (pwalletTxsMain == NULL)
    {
        return "";
    }

    StreamWeightRegistry registry(pwalletTxsMain);
    std::map<std::string, uint32_t> weights = registry.GetAllNodesWeights();

    std::string proposer = WPoASelector::SelectProposer(seed, seed_len, weights);

    if (fDebug)
    {
        LogPrint("wpoa", "[wpoa] SelectProposer height=%d validators=%u -> %s\n",
                 height, (unsigned)weights.size(),
                 proposer.empty() ? "(none)" : proposer.c_str());
    }

    return proposer;
}
