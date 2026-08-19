// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W3: input-stream reader implementation.
// See weight_reader.h. Stream access mirrors wpoa/stream_weight_registry.cpp
// (in-process create/subscribe, non-WRP confirmed reads). The activity counter is
// NOT read from a stream: ComputeActivityForEpoch derives it deterministically from
// the confirmed block + undo data of a buried epoch.

#include "weight_engine/weight_reader.h"

#include "weight_engine/weight_streams.h"   // stream names, STABILITY_MARGIN
#include "weight_engine/weight_records.h"   // pure parsers / accumulators (W1)
#include "weight_engine/weight_engine.h"    // g_weight_epoch_length

#include "rpc/rpcwallet.h"      // pulls rpcserver.h (create/subscribe), wallet.h, wallettxs.h, multichain.h
#include "rpc/rpcutils.h"       // OpReturnFormatEntry
#include "core/init.h"          // pwalletMain, pwalletTxsMain
#include "core/main.h"          // chainActive, cs_main, CBlockIndex, ReadBlockFromDisk, CBlockUndo
#include "chain/undo.h"         // CTxUndo, CTxInUndo
#include "script/standard.h"    // CTxDestination
#include "utils/utilparse.h"    // ExtractDestinationScriptValid
#include "structs/base58.h"     // CBitcoinAddress
#include "utils/util.h"         // LogPrintf, GetBoolArg

#include <boost/foreach.hpp>

using namespace std;
using namespace json_spirit;

// ---------------------------------------------------------------------------
// Construction
// ---------------------------------------------------------------------------

WeightStreamReader::WeightStreamReader(mc_WalletTxs* pwalletIn)
{
    m_pWalletTxs = pwalletIn;
    m_Streams[0].name = MC_WEIGHT_MEMBERSHIP_STREAM_NAME;
    m_Streams[1].name = MC_WEIGHT_ESG_STREAM_NAME;
    m_Streams[2].name = MC_WEIGHT_RECONCILIATION_STREAM_NAME;
}

// ---------------------------------------------------------------------------
// Stream / subscription helpers (writes reuse MultiChain RPC handlers)
// ---------------------------------------------------------------------------

bool WeightStreamReader::GetStreamEntity(const std::string& name, mc_EntityDetails* entity)
{
    if (mc_gState == NULL || mc_gState->m_Assets == NULL)
    {
        return false;
    }
    if (mc_gState->m_Assets->FindEntityByName(entity, name.c_str()) == 0)
    {
        return false;
    }
    return (entity->GetEntityType() == MC_ENT_TYPE_STREAM);
}

// Ensures one input stream exists (creating it CLOSED — one create tx — if missing)
// and that this node is subscribed. CLOSED (MC_PTP_WRITE required) so only
// write-permitted governance addresses can publish; the WeightPublisher admin RPCs
// are the sanctioned write path. Reading only needs a subscription, not write.
bool WeightStreamReader::EnsureOneStream(InputStream& s)
{
    mc_EntityDetails entity;
    if (!GetStreamEntity(s.name, &entity))
    {
        if (s.create_attempted)
        {
            return false; // create tx already broadcast, waiting for confirmation
        }

        // create ["stream", <name>, false]  -> CLOSED (write permission required).
        Array params;
        params.push_back(string("stream"));
        params.push_back(s.name);
        params.push_back(false);

        s.create_attempted = true;
        try
        {
            Value result = createcmd(params, false);
            LogPrintf("[WeightEngine] Input stream '%s' created (closed): %s\n",
                      s.name.c_str(), result.get_str().c_str());
        }
        catch (const Object& objError)
        {
            LogPrintf("[WeightEngine] ERROR creating stream '%s' (create permission required?)\n",
                      s.name.c_str());
        }
        catch (const std::exception& e)
        {
            LogPrintf("[WeightEngine] ERROR creating stream '%s': %s\n", s.name.c_str(), e.what());
        }
        return false; // not usable until confirmed
    }

    mc_TxEntityStat entStat;
    entStat.Zero();
    memcpy(&entStat, entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET, MC_AST_SHORT_TXID_SIZE);
    entStat.m_Entity.m_EntityType = MC_TET_STREAM | MC_TET_CHAINPOS;
    if (m_pWalletTxs != NULL && m_pWalletTxs->WRPFindEntity(&entStat))
    {
        return true; // already subscribed
    }

    if (s.subscribe_attempted)
    {
        return false;
    }

    Array params;
    params.push_back(s.name);
    s.subscribe_attempted = true;
    try
    {
        subscribe(params, false);
        LogPrintf("[WeightEngine] Subscribed to input stream '%s'\n", s.name.c_str());
        return m_pWalletTxs != NULL && m_pWalletTxs->WRPFindEntity(&entStat);
    }
    catch (const Object& objError)
    {
        LogPrintf("[WeightEngine] ERROR subscribing to '%s'\n", s.name.c_str());
    }
    catch (const std::exception& e)
    {
        LogPrintf("[WeightEngine] ERROR subscribing to '%s': %s\n", s.name.c_str(), e.what());
    }
    return false;
}

bool WeightStreamReader::EnsureInputStreams()
{
    if (m_pWalletTxs == NULL || pwalletMain == NULL)
    {
        return false;
    }
    bool all_ready = true;
    for (int i = 0; i < 3; i++)
    {
        if (!EnsureOneStream(m_Streams[i]))
        {
            all_ready = false;
        }
    }
    return all_ready;
}

// ---------------------------------------------------------------------------
// Item decoding (local mc_Script -> keys + data; thread-safe)
// ---------------------------------------------------------------------------

static bool DecodeStreamItem(const CWalletTx& wtx, const unsigned char* stream_short_txid,
                             WeightStreamItem& out)
{
    mc_Script script;

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

        if (!script.IsOpReturnScript())
        {
            continue;
        }
        if (script.GetNumElements() == 0)
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

        out.keys.clear();
        for (int e = 1; e < n - 1; e++)
        {
            script.SetElement(e);
            unsigned char keybuf[MC_ENT_MAX_ITEM_KEY_SIZE + 1];
            int keysize = 0;
            if (script.GetItemKey(keybuf, &keysize) == 0 && keysize >= 0 &&
                keysize <= MC_ENT_MAX_ITEM_KEY_SIZE)
            {
                out.keys.push_back(string((const char*)keybuf, (size_t)keysize));
            }
        }

        size_t data_size = 0;
        const unsigned char* data = script.GetData(n - 1, &data_size);
        if (data == NULL || data_size == 0)
        {
            continue;
        }

        string format_text;
        out.value = OpReturnFormatEntry(data, data_size, wtx.GetHash(), j, format, &format_text);
        return true;
    }
    return false;
}

// ---------------------------------------------------------------------------
// Generic confirmed-item read (low-level, self-locking, NON-WRP)
// ---------------------------------------------------------------------------

bool WeightStreamReader::ReadStreamItems(const std::string& name, std::vector<WeightStreamItem>& out)
{
    static const bool dbg = GetBoolArg("-wpoadebug", false);

    out.clear();

    if (m_pWalletTxs == NULL)
    {
        return false;
    }

    mc_EntityDetails entity;
    if (!GetStreamEntity(name, &entity))
    {
        if (dbg) LogPrintf("[weight-dbg] ReadStreamItems(%s): stream not found\n", name.c_str());
        return false;
    }

    mc_TxEntityStat entStat;
    entStat.Zero();
    memcpy(&entStat, entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET, MC_AST_SHORT_TXID_SIZE);
    entStat.m_Entity.m_EntityType = MC_TET_STREAM | MC_TET_CHAINPOS;

    bool found;
    m_pWalletTxs->Lock();
    found = m_pWalletTxs->FindEntity(&entStat);
    m_pWalletTxs->UnLock();
    if (!found)
    {
        if (dbg) LogPrintf("[weight-dbg] ReadStreamItems(%s): not subscribed\n", name.c_str());
        return false;
    }

    int confirmed = 0;
    m_pWalletTxs->GetListSize(&entStat.m_Entity, entStat.m_Generation, &confirmed);
    if (confirmed <= 0)
    {
        return true; // subscribed, no confirmed items yet
    }

    mc_Buffer rows;
    rows.Initialize(MC_TDB_ENTITY_KEY_SIZE, sizeof(mc_TxEntityRow), MC_BUF_MODE_DEFAULT);

    int list_err = m_pWalletTxs->GetList(&entStat.m_Entity, entStat.m_Generation, 1, confirmed, &rows);
    if (list_err != MC_ERR_NOERROR)
    {
        if (dbg) LogPrintf("[weight-dbg] ReadStreamItems(%s): GetList err=%d\n", name.c_str(), list_err);
        return false;
    }

    const unsigned char* stream_short_txid = entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET;

    for (int i = 0; i < rows.GetCount(); i++)
    {
        mc_TxEntityRow* er = (mc_TxEntityRow*)rows.GetRow(i);
        if (er->m_Flags & MC_TFL_IS_EXTENSION)
        {
            continue;
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

        WeightStreamItem item;
        if (DecodeStreamItem(wtx, stream_short_txid, item))
        {
            out.push_back(item);
        }
    }
    return true;
}

// ---------------------------------------------------------------------------
// Typed readers (parse with the W1 pure helpers; ascending order -> newest wins)
// ---------------------------------------------------------------------------

bool WeightStreamReader::ReadMembership(std::map<std::string, std::set<std::string> >& clusters)
{
    clusters.clear();
    std::vector<WeightStreamItem> items;
    if (!ReadStreamItems(MC_WEIGHT_MEMBERSHIP_STREAM_NAME, items))
    {
        return false;
    }
    BOOST_FOREACH(const WeightStreamItem& item, items)
    {
        if (item.keys.empty())
        {
            continue;
        }
        const std::string& miner = item.keys[0];
        std::set<std::string> aziende;
        if (mc_ParseMembershipClusterJson(item.value, aziende))
        {
            mc_AccumulateMembership(clusters, miner, aziende);
        }
    }
    return true;
}

bool WeightStreamReader::ReadEsg(std::map<std::string, double>& esg)
{
    esg.clear();
    std::vector<WeightStreamItem> items;
    if (!ReadStreamItems(MC_WEIGHT_ESG_STREAM_NAME, items))
    {
        return false;
    }
    BOOST_FOREACH(const WeightStreamItem& item, items)
    {
        std::string addr;
        double score = 0.0;
        if (mc_ParseEsgRecordJson(item.value, addr, score))
        {
            mc_AccumulateLatestEsg(esg, addr, score); // ascending iteration -> newest wins
        }
    }
    return true;
}

bool WeightStreamReader::ReadReconciliationByEpoch(std::map<uint32_t, std::map<std::string, double> >& r_by_epoch)
{
    r_by_epoch.clear();
    std::vector<WeightStreamItem> items;
    if (!ReadStreamItems(MC_WEIGHT_RECONCILIATION_STREAM_NAME, items))
    {
        return false;
    }
    BOOST_FOREACH(const WeightStreamItem& item, items)
    {
        std::string miner;
        double reconciled = 0.0;
        uint32_t epoch = 0;
        if (mc_ParseReconciliationRecordJson(item.value, miner, reconciled, epoch))
        {
            r_by_epoch[epoch][miner] = reconciled; // newest wins
        }
    }
    return true;
}

// ---------------------------------------------------------------------------
// Chain-derived activity (no stream) — see the determinism contract in the header.
// ---------------------------------------------------------------------------

// Immutable per-block facts snapshotted under cs_main so the disk reads below never
// touch mutable CBlockIndex fields (nStatus / file positions), which validation and
// pruning threads mutate under cs_main. Buried-block block/undo file contents are
// append-only and stable, so reading them off-lock with these positions is safe.
struct WeightBlkSnap
{
    int           nStatus;
    CDiskBlockPos blockPos;
    CDiskBlockPos undoPos;
    uint256       prevHash;
    bool          hasPrev;
};

bool WeightStreamReader::ComputeActivityForEpoch(uint32_t epoch, std::map<std::string, uint32_t>& tau)
{
    tau.clear();

    const int len = g_weight_epoch_length;
    if (epoch < 1 || len < 1)
    {
        return false; // never a silent default: a wrong len forks the metric
    }

    // Epoch -> closed height range [firstHeight, lastHeight] (int64 to avoid overflow).
    const int64_t firstH = (int64_t)(epoch - 1) * (int64_t)len;
    const int64_t lastH  = (int64_t)epoch * (int64_t)len - 1;
    if (firstH < 0 || lastH < firstH)
    {
        return false;
    }

    // Snapshot one self-consistent ancestor chain and verify the epoch is buried.
    // cs_main is held ONLY for this tiny snapshot; we copy every mutable field we
    // need (nStatus, block/undo positions, pprev hash) so nothing below reads a
    // CBlockIndex off-lock. CBlockIndex pointers are stable, but their fields are
    // not — so we do not keep the pointers, only the copied facts.
    std::vector<WeightBlkSnap> snaps;
    {
        LOCK(cs_main);
        int tipHeight = chainActive.Height();
        int stableHeight = tipHeight - MC_WEIGHT_DEFAULT_STABILITY_MARGIN;
        if (lastH > (int64_t)stableHeight)
        {
            return false; // epoch not buried yet -> undefined; caller retries later
        }
        CBlockIndex* p = chainActive[(int)lastH];
        if (p == NULL)
        {
            return false;
        }
        for (; p != NULL && (int64_t)p->nHeight >= firstH; p = p->pprev)
        {
            WeightBlkSnap s;
            s.nStatus  = p->nStatus;
            s.blockPos = p->GetBlockPos();
            s.undoPos  = p->GetUndoPos();
            s.hasPrev  = (p->pprev != NULL);
            s.prevHash = s.hasPrev ? p->pprev->GetBlockHash() : uint256();
            snaps.push_back(s);
        }
    }

    // Off-lock: iterate oldest -> newest; resolve each input's owner from undo data,
    // using only the snapshotted immutable positions/hashes.
    for (int i = (int)snaps.size() - 1; i >= 0; --i)
    {
        const WeightBlkSnap& s = snaps[i];
        if ((s.nStatus & BLOCK_HAVE_DATA) == 0)
        {
            return false; // a buried block must have its data (pruned node -> fail closed)
        }

        CBlock block;
        if (!ReadBlockFromDisk(block, s.blockPos))
        {
            return false;
        }

        CBlockUndo undo;
        bool haveUndo = false;
        if (!s.undoPos.IsNull() && s.hasPrev)
        {
            haveUndo = undo.ReadFromDisk(s.undoPos, s.prevHash);
        }

        for (size_t k = 0; k < block.vtx.size(); k++)
        {
            const CTransaction& txn = block.vtx[k];
            if (txn.IsCoinBase())
            {
                continue; // coinbase has no resolvable input signer
            }
            if (!haveUndo || k == 0 || (k - 1) >= undo.vtxundo.size())
            {
                return false; // non-coinbase tx without matching undo -> cannot resolve
            }
            const CTxUndo& tu = undo.vtxundo[k - 1];
            if (tu.vprevout.size() != txn.vin.size())
            {
                return false; // internal inconsistency -> fail closed
            }

            std::set<std::string> signers; // dedup: same address counts once per tx
            for (size_t jj = 0; jj < txn.vin.size(); jj++)
            {
                const CScript& spk = tu.vprevout[jj].txout.scriptPubKey;
                CTxDestination dest;
                if (ExtractDestinationScriptValid(spk, dest)) // 0-or-1 dest; non-standard -> nobody
                {
                    signers.insert(CBitcoinAddress(dest).ToString());
                }
            }
            for (std::set<std::string>::const_iterator it = signers.begin(); it != signers.end(); ++it)
            {
                tau[*it] += 1; // +1 per distinct signing address
            }
        }
    }
    return true;
}
