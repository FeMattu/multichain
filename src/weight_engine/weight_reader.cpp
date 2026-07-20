// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W3: input-stream reader implementation.
// See weight_reader.h for the design. This mirrors, deliberately and closely,
// the proven stream access in wpoa/stream_weight_registry.cpp: the create /
// subscribe path reuses the in-process RPC handlers, and the reads use the
// low-level, self-locking, NON-WRP wallet API so they are safe off the RPC read
// thread and always observe the live confirmed state.

#include "weight_engine/weight_reader.h"

#include "weight_engine/weight_streams.h"   // stream names
#include "weight_engine/weight_records.h"   // pure parsers / accumulators (W1)

#include "rpc/rpcwallet.h"      // pulls rpcserver.h (create/subscribe), wallet.h, wallettxs.h, multichain.h
#include "rpc/rpcutils.h"       // OpReturnFormatEntry
#include "core/init.h"          // pwalletMain, pwalletTxsMain
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
    m_Streams[2].name = MC_WEIGHT_ACTIVITY_STREAM_NAME;
    m_Streams[3].name = MC_WEIGHT_RECONCILIATION_STREAM_NAME;
}

// ---------------------------------------------------------------------------
// Stream / subscription helpers (writes reuse MultiChain RPC handlers)
// ---------------------------------------------------------------------------

// Looks up a confirmed stream entity by name. True and fills *entity only when it
// exists and is a stream.
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

// Ensures one stream exists (creating it — exactly one create tx — if missing) and
// that this node is subscribed. Returns true only when it exists AND is subscribed.
// Mirrors StreamWeightRegistry::EnsureStreamExists + EnsureSubscribed.
bool WeightStreamReader::EnsureOneStream(InputStream& s)
{
    mc_EntityDetails entity;
    if (!GetStreamEntity(s.name, &entity))
    {
        if (s.create_attempted)
        {
            return false; // create tx already broadcast, waiting for confirmation
        }

        // create ["stream", <name>, true]  (open stream: any write-permitted address
        // — the certifier / activity aggregator / reconciliation process — may publish).
        Array params;
        params.push_back(string("stream"));
        params.push_back(s.name);
        params.push_back(true);

        s.create_attempted = true;
        try
        {
            Value result = createcmd(params, false);
            LogPrintf("[WeightEngine] Input stream '%s' create tx broadcast: %s\n",
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

    // Exists — ensure subscribed (required for reads).
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
        return false; // subscribe issued, import still catching up
    }

    Array params;
    params.push_back(s.name);
    s.subscribe_attempted = true;
    try
    {
        subscribe(params, false);
        LogPrintf("[WeightEngine] Subscribed to input stream '%s'\n", s.name.c_str());
        // Re-check: subscription import may complete synchronously for a short stream.
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

    // Attempt every stream on each pass (do not short-circuit) so all missing
    // creates / subscribes are issued together; ready only when all four are.
    bool all_ready = true;
    for (int i = 0; i < 4; i++)
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

// Extracts the item KEY(S) and the decoded JSON payload from the stream item whose
// OP_RETURN belongs to `stream_short_txid`. Mirrors DecodeWeightRecord but also
// walks the middle key elements (1 .. N-2). Uses a LOCAL mc_Script (never the
// shared temp buffer), so it is safe from the background thread.
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

        // Element 0 must be our stream entity.
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

        // Keys occupy the elements strictly between the entity (0) and the data (n-1).
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

        // Last element holds the item data (tiny on-chain JSON only).
        size_t data_size = 0;
        const unsigned char* data = script.GetData(n - 1, &data_size);
        if (data == NULL || data_size == 0)
        {
            continue;
        }

        // 6-argument overload: returns the raw {"json":{...}} value (like StreamItemEntry),
        // which the W1 parsers understand. See the note in DecodeWeightRecord.
        string format_text;
        out.value = OpReturnFormatEntry(data, data_size, wtx.GetHash(), j, format, &format_text);
        return true;
    }
    return false;
}

// ---------------------------------------------------------------------------
// Generic confirmed-item read (low-level, self-locking, NON-WRP)
// ---------------------------------------------------------------------------

// Reads every CONFIRMED item of the named stream (oldest -> newest) into `out`,
// each with its key(s) and decoded value. Returns false only when the stream is
// unavailable (missing or not subscribed); an empty (but subscribed) stream
// returns true with an empty vector. See the long WRP-vs-non-WRP rationale in
// StreamWeightRegistry::ReadAllRecords.
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

    // Non-WRP: self-locking FindEntity/GetListSize/GetList, so the background thread
    // sees confirmed items as soon as their block connects (see ReadAllRecords).
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
            continue; // chunked/off-chain extension row; we only publish tiny on-chain JSON
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
            continue; // membership item key IS the miner address
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

bool WeightStreamReader::ReadActivityByEpoch(std::map<uint32_t, std::map<std::string, uint32_t> >& tau_by_epoch)
{
    tau_by_epoch.clear();
    std::vector<WeightStreamItem> items;
    if (!ReadStreamItems(MC_WEIGHT_ACTIVITY_STREAM_NAME, items))
    {
        return false;
    }
    BOOST_FOREACH(const WeightStreamItem& item, items)
    {
        std::string addr;
        uint32_t tau = 0, epoch = 0;
        if (mc_ParseActivityRecordJson(item.value, addr, tau, epoch))
        {
            tau_by_epoch[epoch][addr] = tau; // newest confirmed value for (epoch,addr) wins
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
