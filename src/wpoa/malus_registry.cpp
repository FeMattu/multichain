// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA — behavioural malus registry implementation. See malus_registry.h for the
// design and malus_record.h for the pure record/accumulator core.
//
// The one structural difference from the weight registry it mirrors: this stream
// is created OPEN. Anyone may accuse; nobody is believed. Every report is
// re-derived here, from public chain data only (ValidReport = Def. 5.20), so two
// honest nodes always reach the same verdict and a false accusation is inert.

#include "wpoa/malus_registry.h"

#include "wpoa/malus_record.h"            // MalusAccumulator, mc_ParseMalusRecordJson
#include "wpoa/wpoa_selector.h"           // WPoAActiveAtHeight, WPoASelector, g_dumping_function
#include "wpoa/private_sortition.h"       // PrivateSortition, WPoASortitionActiveAtHeight
#include "wpoa/randao_accumulator.h"      // WPoARandaoSelectionSeed
#include "wpoa/vrf_wrapper.h"             // WPoAVRF::Verify
#include "wpoa/stream_weight_registry.h"  // StreamWeightRegistry (raw weights)
#include "weight_engine/weight_engine.h"  // HeightToEpoch — the shared height->epoch map

#include "rpc/rpcwallet.h"      // pulls rpcserver.h (create/publish/subscribe), wallet, multichain
#include "rpc/rpcutils.h"       // OpReturnFormatEntry
#include "structs/base58.h"     // CBitcoinAddress
#include "core/init.h"          // pwalletMain, pwalletTxsMain, ShutdownRequested
#include "core/main.h"          // mapBlockIndex, chainActive, cs_main, ReadBlockFromDisk
#include "utils/util.h"         // LogPrintf, LogPrint, RenameThread, strprintf, fDebug
#include "utils/utiltime.h"     // MilliSleep, GetTime

#include <boost/foreach.hpp>

using namespace std;
using namespace json_spirit;

// ---------------------------------------------------------------------------
// Runtime configuration (AppInit2 overwrites these with the resolved values)
// ---------------------------------------------------------------------------

bool   g_wpoa_malus_enabled  = false;
double g_wpoa_malus_mu       = MC_WPOA_DEFAULT_MALUS_MU;
double g_wpoa_malus_max      = MC_WPOA_DEFAULT_MALUS_MAX;
double g_wpoa_malus_p_equiv  = MC_WPOA_DEFAULT_MALUS_P_EQUIV;
double g_wpoa_malus_p_delay  = MC_WPOA_DEFAULT_MALUS_P_DELAY;

// Retry pacing for the background stream-provisioning thread (mirrors the weight
// registry thread).
static const int MC_WPOA_MALUS_RETRY_INTERVAL_MS = 3000;
static const int MC_WPOA_MALUS_MAX_ATTEMPTS      = 200;   // ~10 minutes worst case

bool WPoAMalusActiveAtHeight(int height)
{
    // Rides on top of the weighted selection: the correction only means anything
    // where wPoA already elects the proposer. Both conditions are pure functions
    // of shared data, so the miner and every validator agree from the height alone.
    return g_wpoa_malus_enabled && WPoAActiveAtHeight(height);
}

// ---------------------------------------------------------------------------
// Construction / stream provisioning
// ---------------------------------------------------------------------------

MalusRegistry::MalusRegistry(mc_WalletTxs* pwalletIn)
{
    m_pWalletTxs         = pwalletIn;
    m_StreamName         = MC_WPOA_MALUS_STREAM_NAME;
    m_CreateAttempted    = false;
    m_SubscribeAttempted = false;
}

MalusRegistry::~MalusRegistry()
{
    // m_pWalletTxs is borrowed, nothing to free.
}

bool MalusRegistry::GetStreamEntity(mc_EntityDetails* entity)
{
    if (mc_gState == NULL || mc_gState->m_Assets == NULL)
    {
        return false;
    }
    if (mc_gState->m_Assets->FindEntityByName(entity, m_StreamName.c_str()) == 0)
    {
        return false;
    }
    return (entity->GetEntityType() == MC_ENT_TYPE_STREAM);
}

bool MalusRegistry::EnsureStreamExists()
{
    mc_EntityDetails entity;
    if (GetStreamEntity(&entity))
    {
        return true;
    }

    if (m_CreateAttempted)
    {
        return false; // create tx already broadcast, still waiting for confirmation
    }

    // create ["stream", "wpoa-weights-malus", true] -> OPEN, by design (Def. 5.17).
    // Unlike wpoa-weights, reporting misbehaviour is deliberately open to every
    // participant: the safety of that openness rests on ValidReport, not on who is
    // allowed to speak.
    Array params;
    params.push_back(string("stream"));
    params.push_back(m_StreamName);
    params.push_back(true);

    m_CreateAttempted = true;
    try
    {
        Value result = createcmd(params, false);
        LogPrintf("[MalusRegistry] Stream '%s' create tx broadcast (open): %s\n",
                  m_StreamName.c_str(), result.get_str().c_str());
    }
    catch (const Object& objError)
    {
        LogPrintf("[MalusRegistry] ERROR creating stream '%s' (create permission required?)\n",
                  m_StreamName.c_str());
    }
    catch (const std::exception& e)
    {
        LogPrintf("[MalusRegistry] ERROR creating stream '%s': %s\n", m_StreamName.c_str(), e.what());
    }
    return false; // not usable until confirmed
}

bool MalusRegistry::EnsureSubscribed()
{
    mc_EntityDetails entity;
    if (!GetStreamEntity(&entity))
    {
        return false;
    }

    mc_TxEntityStat entStat;
    entStat.Zero();
    memcpy(&entStat, entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET, MC_AST_SHORT_TXID_SIZE);
    entStat.m_Entity.m_EntityType = MC_TET_STREAM | MC_TET_CHAINPOS;
    if (m_pWalletTxs != NULL && m_pWalletTxs->WRPFindEntity(&entStat))
    {
        return true;
    }

    if (m_SubscribeAttempted)
    {
        return false; // subscribe issued, import still catching up
    }

    Array params;
    params.push_back(m_StreamName);

    m_SubscribeAttempted = true;
    try
    {
        subscribe(params, false);
        LogPrintf("[MalusRegistry] Subscribed to stream '%s'\n", m_StreamName.c_str());
        return m_pWalletTxs != NULL && m_pWalletTxs->WRPFindEntity(&entStat);
    }
    catch (const Object& objError)
    {
        LogPrintf("[MalusRegistry] ERROR subscribing to '%s'\n", m_StreamName.c_str());
    }
    catch (const std::exception& e)
    {
        LogPrintf("[MalusRegistry] ERROR subscribing to '%s': %s\n", m_StreamName.c_str(), e.what());
    }
    return false;
}

bool MalusRegistry::EnsureStream()
{
    if (m_pWalletTxs == NULL || pwalletMain == NULL)
    {
        return false;
    }
    if (!EnsureStreamExists())
    {
        return false;
    }
    return EnsureSubscribed();
}

// ---------------------------------------------------------------------------
// Reads (low-level, self-locking, slot-free — safe from any thread)
// ---------------------------------------------------------------------------

// Decode one stream item transaction into a malus report. Mirrors
// DecodeWeightRecord in stream_weight_registry.cpp — including the use of a
// stack-local mc_Script (thread safety) and of the 6-argument OpReturnFormatEntry
// overload, which returns the raw {"json":{...}} value the parser expects.
static bool DecodeMalusRecord(const CWalletTx& wtx, const unsigned char* stream_short_txid,
                              MalusKind& kind, string& addr, int& height,
                              vector<string>& blocks)
{
    mc_Script script; // local instance -> thread-safe (no shared temp buffers)

    for (int j = 0; j < (int)wtx.vout.size(); j++)
    {
        const CScript& spk = wtx.vout[j].scriptPubKey;
        if (spk.size() == 0)
        {
            continue;
        }
        CScript::const_iterator pc = spk.begin();

        script.Clear();
        script.SetScript((unsigned char*)(&pc[0]), (size_t)(spk.end() - pc), MC_SCR_TYPE_SCRIPTPUBKEY);

        if (!script.IsOpReturnScript() || script.GetNumElements() == 0)
        {
            continue;
        }

        uint32_t format;
        unsigned char* chunk_hashes = NULL;
        int chunk_count = 0;
        int64_t total_chunk_size = 0;
        script.ExtractAndDeleteDataFormat(&format, &chunk_hashes, &chunk_count, &total_chunk_size);

        unsigned char short_txid[MC_AST_SHORT_TXID_SIZE];
        script.SetElement(0);
        if (script.GetEntity(short_txid) != 0)
        {
            continue;
        }
        if (memcmp(short_txid, stream_short_txid, MC_AST_SHORT_TXID_SIZE) != 0)
        {
            continue;
        }

        int n = script.GetNumElements();
        if (n < 1)
        {
            continue;
        }
        size_t data_size = 0;
        const unsigned char* data = script.GetData(n - 1, &data_size);
        if (data == NULL || data_size == 0)
        {
            continue;
        }

        string format_text;
        Value v = OpReturnFormatEntry(data, data_size, wtx.GetHash(), j, format, &format_text);
        if (mc_ParseMalusRecordJson(v, kind, addr, height, blocks))
        {
            return true;
        }
    }
    return false;
}

bool MalusRegistry::ReadAllReports(std::vector<Report>& out)
{
    out.clear();

    if (m_pWalletTxs == NULL)
    {
        return false;
    }

    mc_EntityDetails entity;
    if (!GetStreamEntity(&entity))
    {
        return false; // stream not created yet
    }

    mc_TxEntityStat entStat;
    entStat.Zero();
    memcpy(&entStat, entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET, MC_AST_SHORT_TXID_SIZE);
    entStat.m_Entity.m_EntityType = MC_TET_STREAM | MC_TET_CHAINPOS;

    // Non-WRP read family: self-locking and reading the live list position, so a
    // caller outside the RPC read-lock protocol still observes every confirmed item
    // (see the long note in StreamWeightRegistry::ReadAllRecords).
    bool found;
    m_pWalletTxs->Lock();
    found = m_pWalletTxs->FindEntity(&entStat);
    m_pWalletTxs->UnLock();
    if (!found)
    {
        return false; // not subscribed
    }

    // CONFIRMED items only: a registry that feeds consensus must be identical on
    // every node, and mempool contents differ per node.
    int confirmed = 0;
    m_pWalletTxs->GetListSize(&entStat.m_Entity, entStat.m_Generation, &confirmed);
    if (confirmed <= 0)
    {
        return true; // subscribed, nothing confirmed yet -> empty list
    }

    mc_Buffer rows;
    rows.Initialize(MC_TDB_ENTITY_KEY_SIZE, sizeof(mc_TxEntityRow), MC_BUF_MODE_DEFAULT);

    if (m_pWalletTxs->GetList(&entStat.m_Entity, entStat.m_Generation, 1, confirmed, &rows) != MC_ERR_NOERROR)
    {
        return false;
    }

    const unsigned char* stream_short_txid = entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET;

    for (int i = 0; i < rows.GetCount(); i++)
    {
        mc_TxEntityRow* er = (mc_TxEntityRow*)rows.GetRow(i);
        if (er->m_Flags & MC_TFL_IS_EXTENSION)
        {
            continue; // we only ever publish tiny on-chain JSON
        }

        uint256 hash;
        memcpy(hash.begin(), er->m_TxId, MC_TDB_TXID_SIZE);

        int err = MC_ERR_NOERROR;
        mc_TxDefRow txdef;
        CWalletTx wtx = m_pWalletTxs->GetWalletTx(hash, &txdef, &err);
        if (err != MC_ERR_NOERROR)
        {
            continue;
        }

        Report r;
        if (DecodeMalusRecord(wtx, stream_short_txid, r.kind, r.address, r.height, r.blocks))
        {
            out.push_back(r);
        }
    }
    return true;
}

// ---------------------------------------------------------------------------
// Valid(e) — the local decidability predicate (Def. 5.20)
// ---------------------------------------------------------------------------

// Extract the VRF reveal AND proof from a block's coinbase OP_RETURN, using a
// stack-local mc_Script so this is safe to call off the validation thread (same
// reasoning as ExtractBlockReveal in randao_accumulator.cpp).
static bool ExtractBlockVRF(const CBlock& block,
                            std::vector<unsigned char>& reveal,
                            std::vector<unsigned char>& proof)
{
    mc_Script scriptTmp;

    reveal.clear();
    proof.clear();

    for (unsigned int i = 0; i < block.vtx.size(); i++)
    {
        const CTransaction& tx = block.vtx[i];
        if (!tx.IsCoinBase())
        {
            continue;
        }
        for (unsigned int j = 0; j < tx.vout.size(); j++)
        {
            const CScript& spk = tx.vout[j].scriptPubKey;
            if (spk.size() == 0)
            {
                continue;
            }

            scriptTmp.Clear();
            CScript::const_iterator pc = spk.begin();
            scriptTmp.SetScript((unsigned char*)(&pc[0]), (size_t)(spk.end() - pc),
                                MC_SCR_TYPE_SCRIPTPUBKEY);

            for (int e = 0; e < scriptTmp.GetNumElements(); e++)
            {
                scriptTmp.SetElement(e);
                unsigned char reveal_buf[255];
                unsigned char proof_buf[255];
                int rsize = sizeof(reveal_buf);
                int psize = sizeof(proof_buf);
                if (scriptTmp.GetBlockVRF(reveal_buf, &rsize, proof_buf, &psize) == 0)
                {
                    reveal.assign(reveal_buf, reveal_buf + rsize);
                    proof.assign(proof_buf, proof_buf + psize);
                    return true;
                }
            }
        }
    }
    return false;
}

// Everything ValidReport needs from one accused block, resolved from the local
// block index and the block file. Returns false when the block is unknown here.
struct AccusedBlock
{
    const CBlockIndex*         pindex;
    std::vector<unsigned char> pubkey;
    std::string                address;
    std::vector<unsigned char> reveal;
    std::vector<unsigned char> proof;
    uint32_t                   ntime;
};

static bool LoadAccusedBlock(const std::string& block_hash_hex, AccusedBlock& out,
                             std::string* reason_out)
{
    uint256 hash;
    hash.SetHex(block_hash_hex);
    if (hash == uint256(0))
    {
        if (reason_out) *reason_out = "malformed block hash";
        return false;
    }

    CBlock block;
    {
        LOCK(cs_main);
        BlockMap::iterator mi = mapBlockIndex.find(hash);
        if (mi == mapBlockIndex.end() || mi->second == NULL)
        {
            if (reason_out) *reason_out = "block " + block_hash_hex + " is unknown to this node";
            return false;
        }
        out.pindex = mi->second;
        if ((out.pindex->nStatus & BLOCK_HAVE_DATA) == 0 || !ReadBlockFromDisk(block, out.pindex))
        {
            if (reason_out) *reason_out = "block " + block_hash_hex + " has no data on this node";
            return false;
        }
    }

    if (block.vSigner[0] == 0)
    {
        if (reason_out) *reason_out = "block " + block_hash_hex + " has no signer";
        return false;
    }
    out.pubkey.assign(block.vSigner + 1, block.vSigner + 1 + block.vSigner[0]);

    CPubKey pk(out.pubkey);
    if (!pk.IsValid())
    {
        if (reason_out) *reason_out = "block " + block_hash_hex + " has an invalid signer pubkey";
        return false;
    }
    out.address = CBitcoinAddress(pk.GetID()).ToString();
    out.ntime   = block.nTime;

    if (!ExtractBlockVRF(block, out.reveal, out.proof))
    {
        if (reason_out) *reason_out = "block " + block_hash_hex + " carries no VRF reveal";
        return false;
    }
    return true;
}

// Verify the block's sortition reveal against the beacon seed derived over its
// parent — the same check the block validator ran (§5.12.3 step 3).
static bool VerifyAccusedVRF(const AccusedBlock& b, int height, std::string* reason_out)
{
    if (b.pindex->pprev == NULL)
    {
        if (reason_out) *reason_out = "accused block has no parent";
        return false;
    }

    unsigned char seed[32];
    if (!WPoARandaoSelectionSeed(b.pindex->pprev, seed))
    {
        if (reason_out) *reason_out = "beacon seed not recomputable for this height";
        return false;
    }

    std::vector<unsigned char> input;
    PrivateSortition::VRFInput(seed, (uint32_t)height, input);
    if (!WPoAVRF::Verify(b.pubkey, input, b.reveal, b.proof))
    {
        if (reason_out) *reason_out = "VRF reveal does not verify over the sortition input";
        return false;
    }
    return true;
}

bool MalusRegistry::ValidReport(MalusKind kind, const std::string& node_address, int height,
                                const std::vector<std::string>& blocks, double psi_prev,
                                std::string* reason_out)
{
    // The two kinds are only decidable where the private sortition governs the
    // height: both proofs rest on the block-carried VRF reveal over the beacon
    // seed, which only exists there.
    if (!WPoASortitionActiveAtHeight(height))
    {
        if (reason_out) *reason_out = "height is not governed by private sortition";
        return false;
    }

    if (kind == MALUS_EQUIV)
    {
        if (blocks.size() != 2 || blocks[0] == blocks[1])
        {
            if (reason_out) *reason_out = "equivocation needs two DISTINCT block hashes";
            return false;
        }

        AccusedBlock a, b;
        if (!LoadAccusedBlock(blocks[0], a, reason_out)) return false;
        if (!LoadAccusedBlock(blocks[1], b, reason_out)) return false;

        // Same height, same parent -> same beacon seed, hence the same VRF input:
        // this is what makes VRF uniqueness bite (Def. 5.18).
        if (a.pindex->nHeight != height || b.pindex->nHeight != height)
        {
            if (reason_out) *reason_out = "the two blocks are not both at the reported height";
            return false;
        }
        if (a.pindex->pprev != b.pindex->pprev)
        {
            if (reason_out) *reason_out = "the two blocks do not share a parent (different rounds)";
            return false;
        }
        if (a.address != node_address || b.address != node_address)
        {
            if (reason_out) *reason_out = "the two blocks are not both signed by the accused";
            return false;
        }
        if (!VerifyAccusedVRF(a, height, reason_out)) return false;
        if (!VerifyAccusedVRF(b, height, reason_out)) return false;

        // Two distinct, validly-revealed blocks at one height from one key. An
        // honest validator cannot produce that: for a fixed key and input the VRF
        // output is unique, so proposing twice is a deliberate act.
        return true;
    }

    if (kind == MALUS_DELAY)
    {
        if (blocks.size() != 1)
        {
            if (reason_out) *reason_out = "a delay violation names exactly one block";
            return false;
        }

        AccusedBlock a;
        if (!LoadAccusedBlock(blocks[0], a, reason_out)) return false;

        if (a.pindex->nHeight != height)
        {
            if (reason_out) *reason_out = "the block is not at the reported height";
            return false;
        }
        if (a.address != node_address)
        {
            if (reason_out) *reason_out = "the block is not signed by the accused";
            return false;
        }
        if (!VerifyAccusedVRF(a, height, reason_out)) return false;

        // Reproduce the delay the block validator enforced. The weight is the
        // EFFECTIVE weight that was in force at this height, i.e. the raw registry
        // weight corrected by Psi^(e-1) — the caller passes that Psi in, so this
        // predicate never has to resolve the epoch's own reports (which would make
        // the definition circular).
        if (pwalletTxsMain == NULL)
        {
            if (reason_out) *reason_out = "weight registry unavailable";
            return false;
        }
        StreamWeightRegistry registry(pwalletTxsMain);
        std::map<std::string, uint32_t> weights = registry.GetAllNodesWeights();
        if (weights.empty())
        {
            if (reason_out) *reason_out = "weight registry not synced";
            return false;
        }

        std::map<std::string, uint32_t>::const_iterator wi = weights.find(node_address);
        if (wi == weights.end())
        {
            if (reason_out) *reason_out = "accused is not a weighted validator";
            return false;
        }

        // Only the accused's own weight was corrected at that height; every other
        // validator's Psi is irrelevant to ITS delay, but the total effective weight
        // that scales the delay is taken over the same map the validator used.
        std::map<std::string, uint32_t> eff(weights);
        eff[node_address] = MalusAccumulator::EffectiveWeight(wi->second, psi_prev);

        uint32_t w = eff[node_address];
        if (w == 0)
        {
            if (reason_out) *reason_out = "accused carried no effective weight at this height";
            return false;
        }

        double weff = 0.0;
        for (std::map<std::string, uint32_t>::const_iterator it = eff.begin(); it != eff.end(); ++it)
        {
            weff += WPoASelector::ApplyDumping(it->second, g_dumping_function);
        }
        if (!(weff > 0.0))
        {
            if (reason_out) *reason_out = "total effective weight is zero";
            return false;
        }

        double score = PrivateSortition::ScoreFromVRFOutput(a.reveal.data(), w, g_dumping_function);
        double delay = PrivateSortition::MiningDelay(score, weff, g_wpoa_sortition_delay);

        int64_t earliest = a.pindex->pprev->GetBlockTime() + (int64_t)delay;
        if ((int64_t)a.ntime >= earliest)
        {
            if (reason_out)
            {
                *reason_out = strprintf("block was NOT early (nTime %u >= parent + delay %ds)",
                                        a.ntime, (int)delay);
            }
            return false;
        }
        return true;
    }

    if (reason_out) *reason_out = "unknown violation kind";
    return false;
}

// ---------------------------------------------------------------------------
// Accumulator: one forward pass over the epochs
// ---------------------------------------------------------------------------

bool MalusRegistry::GetAccumulators(uint32_t epoch, std::map<std::string, double>& out)
{
    out.clear();

    std::vector<Report> reports;
    if (!ReadAllReports(reports))
    {
        return false;
    }
    if (reports.empty() || epoch < 1)
    {
        return true;
    }

    // Bucket the reports by the epoch of the height they accuse, so the fold below
    // is a single pass over epochs rather than a rescan per epoch.
    std::map<uint32_t, std::vector<const Report*> > by_epoch;
    for (size_t i = 0; i < reports.size(); i++)
    {
        by_epoch[HeightToEpoch(reports[i].height)].push_back(&reports[i]);
    }

    // Fold forward: at epoch e the reports are validated against Psi^(e-1) — the
    // correction that was actually in force at those heights — and only then
    // folded into M^(e). This ordering is what keeps the definition acyclic.
    std::map<std::string, double> M;   // address -> M^(e-1), then M^(e)
    for (uint32_t e = 1; e <= epoch; e++)
    {
        std::map<std::string, double> points;   // this epoch's valid score per address

        std::map<uint32_t, std::vector<const Report*> >::const_iterator bi = by_epoch.find(e);
        if (bi != by_epoch.end())
        {
            for (size_t i = 0; i < bi->second.size(); i++)
            {
                const Report& r = *bi->second[i];

                std::map<std::string, double>::const_iterator mi = M.find(r.address);
                double psi_prev = (mi == M.end())
                                      ? 1.0
                                      : MalusAccumulator::CorrectionFactor(mi->second, g_wpoa_malus_max);

                if (!ValidReport(r.kind, r.address, r.height, r.blocks, psi_prev, NULL))
                {
                    continue;   // false, malformed or unverifiable here: discarded
                }
                points[r.address] += MalusAccumulator::Points(r.kind, g_wpoa_malus_p_equiv,
                                                              g_wpoa_malus_p_delay);
            }
        }

        // Decay every carried address, then add this epoch's points.
        std::map<std::string, double> next;
        for (std::map<std::string, double>::const_iterator it = M.begin(); it != M.end(); ++it)
        {
            double folded = MalusAccumulator::Fold(it->second, 0.0, g_wpoa_malus_mu);
            if (folded > 0.0)
            {
                next[it->first] = folded;
            }
        }
        for (std::map<std::string, double>::const_iterator it = points.begin(); it != points.end(); ++it)
        {
            next[it->first] += it->second;
        }
        M.swap(next);
    }

    out.swap(M);
    return true;
}

double MalusRegistry::GetAccumulator(const std::string& address, uint32_t epoch)
{
    std::map<std::string, double> all;
    if (!GetAccumulators(epoch, all))
    {
        return 0.0;
    }
    std::map<std::string, double>::const_iterator it = all.find(address);
    return (it != all.end()) ? it->second : 0.0;
}

// ---------------------------------------------------------------------------
// Publication
// ---------------------------------------------------------------------------

std::string MalusRegistry::PublishReport(MalusKind kind, const std::string& node_address,
                                         int height, const std::vector<std::string>& blocks)
{
    if (!EnsureStream())
    {
        throw JSONRPCError(RPC_ENTITY_NOT_FOUND,
                           string("Stream '") + m_StreamName + "' is not available yet "
                           "(enable the malus registry so it is created, then retry)");
    }

    // Validate against the correction currently in force for the accused, i.e.
    // Psi of the epoch before the accused height — the same value every other node
    // will use when it re-derives this record.
    const uint32_t epoch = HeightToEpoch(height);
    double psi_prev = 1.0;
    if (epoch >= 2)
    {
        psi_prev = MalusAccumulator::CorrectionFactor(GetAccumulator(node_address, epoch - 1),
                                                      g_wpoa_malus_max);
    }

    std::string reason;
    if (!ValidReport(kind, node_address, height, blocks, psi_prev, &reason))
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER,
                           string("Evidence rejected by the local Valid() check: ") + reason);
    }

    Object record;
    record.push_back(Pair(MC_WPOA_MALUS_FIELD_KIND, string(mc_MalusKindToString(kind))));
    record.push_back(Pair(MC_WPOA_MALUS_FIELD_ADDR, node_address));
    record.push_back(Pair(MC_WPOA_MALUS_FIELD_HEIGHT, (int64_t)height));
    Array block_arr;
    for (size_t i = 0; i < blocks.size(); i++)
    {
        block_arr.push_back(blocks[i]);
    }
    record.push_back(Pair(MC_WPOA_MALUS_FIELD_BLOCKS, block_arr));

    Object data_obj;
    data_obj.push_back(Pair("json", record));

    // publish ["wpoa-weights-malus", <accused-address-as-key>, {"json": {...}}]
    Array params;
    params.push_back(m_StreamName);
    params.push_back(node_address);
    params.push_back(data_obj);

    Value result = publish(params, false);
    LogPrintf("[MalusRegistry] Report published: %s against %s at height %d (tx %s)\n",
              mc_MalusKindToString(kind), node_address.c_str(), height,
              result.get_str().c_str());
    return result.get_str();
}

// ---------------------------------------------------------------------------
// The consensus-path entry point
// ---------------------------------------------------------------------------

std::map<std::string, uint32_t> WPoAApplyMalus(const std::map<std::string, uint32_t>& weights,
                                               int height)
{
    if (!WPoAMalusActiveAtHeight(height) || weights.empty() || pwalletTxsMain == NULL)
    {
        return weights;
    }

    // Heights in epoch e are governed by Psi^(e-1): a malus proved in an epoch
    // takes effect from the next one, mirroring the weight layer's own inter-epoch
    // feedback and keeping the delay-report predicate acyclic.
    const uint32_t epoch = HeightToEpoch(height);
    if (epoch < 2)
    {
        return weights;   // no previous epoch yet -> no correction
    }

    MalusRegistry registry(pwalletTxsMain);
    std::map<std::string, double> accumulators;
    if (!registry.GetAccumulators(epoch - 1, accumulators) || accumulators.empty())
    {
        return weights;   // stream unavailable or nobody carries any malus
    }

    std::map<std::string, uint32_t> effective;
    MalusAccumulator::ApplyToWeights(weights, accumulators, g_wpoa_malus_max, effective);

    if (fDebug)
    {
        for (std::map<std::string, double>::const_iterator it = accumulators.begin();
             it != accumulators.end(); ++it)
        {
            std::map<std::string, uint32_t>::const_iterator raw = weights.find(it->first);
            std::map<std::string, uint32_t>::const_iterator eff = effective.find(it->first);
            if (raw != weights.end() && eff != effective.end())
            {
                LogPrint("wpoa", "[wpoa-malus] height=%d epoch=%u %s: M=%.6g Psi=%.6g w=%u -> w_eff=%u\n",
                         height, epoch, it->first.c_str(), it->second,
                         MalusAccumulator::CorrectionFactor(it->second, g_wpoa_malus_max),
                         raw->second, eff->second);
            }
        }
    }

    return effective;
}

// ---------------------------------------------------------------------------
// Background stream provisioning (launched from AppInit2)
// ---------------------------------------------------------------------------

void ThreadMalusRegistry()
{
    RenameThread("mc-wpoa-malus");
    LogPrintf("[MalusRegistry] provisioning thread started (mu=%g, Mmax=%g, p_equiv=%g, p_delay=%g)\n",
              g_wpoa_malus_mu, g_wpoa_malus_max, g_wpoa_malus_p_equiv, g_wpoa_malus_p_delay);

    if (pwalletTxsMain == NULL || pwalletMain == NULL)
    {
        LogPrintf("[MalusRegistry] wallet not available, aborting\n");
        return;
    }

    MalusRegistry registry(pwalletTxsMain);
    int attempts = 0;

    while (!ShutdownRequested())
    {
        MilliSleep(MC_WPOA_MALUS_RETRY_INTERVAL_MS);
        if (ShutdownRequested())
        {
            break;
        }

        {
            LOCK(cs_main);
            if (chainActive.Tip() == NULL)
            {
                continue;
            }
        }
        if (!GetBoolArg("-offline", false) && IsInitialBlockDownload())
        {
            continue;
        }

        attempts++;
        if (registry.EnsureStream())
        {
            LogPrintf("[MalusRegistry] stream '%s' ready\n", MC_WPOA_MALUS_STREAM_NAME);
            return;
        }
        if (attempts >= MC_WPOA_MALUS_MAX_ATTEMPTS)
        {
            LogPrintf("[MalusRegistry] giving up stream provisioning after %d attempts\n", attempts);
            return;
        }
    }
}

// ---------------------------------------------------------------------------
// RPC commands
// ---------------------------------------------------------------------------

// The epoch whose accumulators currently govern selection, i.e. the one before the
// tip's epoch (see WPoAApplyMalus). 0 when there is no previous epoch yet.
static uint32_t GoverningMalusEpoch()
{
    int height = 0;
    {
        LOCK(cs_main);
        if (chainActive.Tip() != NULL)
        {
            height = chainActive.Height();
        }
    }
    uint32_t epoch = HeightToEpoch(height);
    return (epoch >= 2) ? (epoch - 1) : 0;
}

Value getallmalus(const Array& params, bool fHelp)
{
    if (fHelp || params.size() != 0)
    {
        throw runtime_error(
            "getallmalus\n"
            "\nReturns the behavioural malus currently applied to every validator:\n"
            "the accumulator M, the correction factor Psi and the resulting effective\n"
            "weight w_eff = w * Psi that the proposer election consumes.\n"
            "\nResult:\n"
            "{\n"
            "  \"epoch\": n,        (numeric) epoch whose accumulators govern selection\n"
            "  \"enabled\": bool,   (boolean) whether the malus registry is active\n"
            "  \"validators\": {\n"
            "     \"address\": { \"malus\": x, \"psi\": x, \"weight\": n, \"effective\": n,\n"
            "                    \"excluded\": bool, \"epochs_to_clear\": n }\n"
            "  }\n"
            "}\n");
    }
    if (pwalletTxsMain == NULL)
    {
        throw JSONRPCError(RPC_WALLET_ERROR, "Wallet not available");
    }

    const uint32_t epoch = GoverningMalusEpoch();

    StreamWeightRegistry wregistry(pwalletTxsMain);
    std::map<std::string, uint32_t> weights = wregistry.GetAllNodesWeights();

    std::map<std::string, double> accumulators;
    if (epoch >= 1)
    {
        MalusRegistry mregistry(pwalletTxsMain);
        mregistry.GetAccumulators(epoch, accumulators);
    }

    Object validators;
    for (std::map<std::string, uint32_t>::const_iterator it = weights.begin();
         it != weights.end(); ++it)
    {
        std::map<std::string, double>::const_iterator mi = accumulators.find(it->first);
        double M   = (mi != accumulators.end()) ? mi->second : 0.0;
        double psi = MalusAccumulator::CorrectionFactor(M, g_wpoa_malus_max);
        uint32_t eff = MalusAccumulator::EffectiveWeight(it->second, psi);

        Object entry;
        entry.push_back(Pair("malus", M));
        entry.push_back(Pair("psi", psi));
        entry.push_back(Pair("weight", (int64_t)it->second));
        entry.push_back(Pair("effective", (int64_t)eff));
        entry.push_back(Pair("excluded", eff == 0));
        entry.push_back(Pair("epochs_to_clear",
                             MalusAccumulator::EpochsToClear(M, g_wpoa_malus_max, g_wpoa_malus_mu)));
        validators.push_back(Pair(it->first, entry));
    }

    Object obj;
    obj.push_back(Pair("epoch", (int64_t)epoch));
    obj.push_back(Pair("enabled", g_wpoa_malus_enabled));
    obj.push_back(Pair("validators", validators));
    return obj;
}

Value getnodemalus(const Array& params, bool fHelp)
{
    if (fHelp || params.size() != 1)
    {
        throw runtime_error(
            "getnodemalus \"address\"\n"
            "\nReturns the behavioural malus of one validator.\n"
            "\nArguments:\n"
            "1. \"address\"  (string, required) the validator address\n"
            "\nResult:\n"
            "{\n"
            "  \"address\": \"...\",     (string) the queried address\n"
            "  \"epoch\": n,             (numeric) epoch governing selection\n"
            "  \"malus\": x,             (numeric) accumulator M\n"
            "  \"psi\": x,               (numeric) correction factor in [0,1]\n"
            "  \"weight\": n,            (numeric) raw registry weight\n"
            "  \"effective\": n,         (numeric) w * Psi, consumed by the election\n"
            "  \"excluded\": bool,       (boolean) whether Psi has reached 0\n"
            "  \"epochs_to_clear\": n    (numeric) clean epochs needed to become eligible\n"
            "}\n");
    }
    if (pwalletTxsMain == NULL)
    {
        throw JSONRPCError(RPC_WALLET_ERROR, "Wallet not available");
    }

    const std::string address = params[0].get_str();
    const uint32_t epoch = GoverningMalusEpoch();

    StreamWeightRegistry wregistry(pwalletTxsMain);
    uint32_t weight = wregistry.GetNodeWeight(address);

    double M = 0.0;
    if (epoch >= 1)
    {
        MalusRegistry mregistry(pwalletTxsMain);
        M = mregistry.GetAccumulator(address, epoch);
    }
    double psi = MalusAccumulator::CorrectionFactor(M, g_wpoa_malus_max);
    uint32_t eff = MalusAccumulator::EffectiveWeight(weight, psi);

    Object obj;
    obj.push_back(Pair("address", address));
    obj.push_back(Pair("epoch", (int64_t)epoch));
    obj.push_back(Pair("malus", M));
    obj.push_back(Pair("psi", psi));
    obj.push_back(Pair("weight", (int64_t)weight));
    obj.push_back(Pair("effective", (int64_t)eff));
    obj.push_back(Pair("excluded", eff == 0));
    obj.push_back(Pair("epochs_to_clear",
                       MalusAccumulator::EpochsToClear(M, g_wpoa_malus_max, g_wpoa_malus_mu)));
    return obj;
}

Value reportmalus(const Array& params, bool fHelp)
{
    if (fHelp || params.size() < 4 || params.size() > 5)
    {
        throw runtime_error(
            "reportmalus \"kind\" \"address\" height \"blockhash\" [\"blockhash2\"]\n"
            "\nPublishes a misbehaviour report to the open wpoa-weights-malus stream.\n"
            "Any node may report: the evidence is re-verified independently by every\n"
            "peer, so a false report is discarded and changes nothing. This node runs\n"
            "the same check BEFORE broadcasting and refuses to publish evidence that\n"
            "does not hold locally.\n"
            "\nArguments:\n"
            "1. \"kind\"        (string, required) \"equiv\" or \"delay\"\n"
            "2. \"address\"     (string, required) the accused validator\n"
            "3. height          (numeric, required) the height the accusation refers to\n"
            "4. \"blockhash\"   (string, required) the offending block\n"
            "5. \"blockhash2\"  (string, optional) the competing block, for \"equiv\"\n"
            "\nResult:\n"
            "\"txid\"  (string) the publish transaction id\n");
    }
    if (pwalletTxsMain == NULL)
    {
        throw JSONRPCError(RPC_WALLET_ERROR, "Wallet not available");
    }

    MalusKind kind = mc_MalusKindFromString(params[0].get_str());
    if (kind == MALUS_NONE)
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "kind must be \"equiv\" or \"delay\"");
    }

    const std::string address = params[1].get_str();

    int64_t height = 0;
    if (params[2].type() == int_type)
    {
        height = params[2].get_int64();
    }
    else if (params[2].type() == str_type)   // the CLI sends numbers as strings
    {
        const std::string hs = params[2].get_str();
        char* end = NULL;
        long long v = strtoll(hs.c_str(), &end, 10);
        if (hs.empty() || end == hs.c_str() || *end != '\0')
        {
            throw JSONRPCError(RPC_INVALID_PARAMETER, "height must be an integer");
        }
        height = (int64_t)v;
    }
    else
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "height must be an integer");
    }
    if (height < 1 || height > (int64_t)0x7fffffff)
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "height out of range");
    }

    std::vector<std::string> blocks;
    blocks.push_back(params[3].get_str());
    if (params.size() == 5)
    {
        blocks.push_back(params[4].get_str());
    }

    MalusRegistry registry(pwalletTxsMain);
    return registry.PublishReport(kind, address, (int)height, blocks);
}
