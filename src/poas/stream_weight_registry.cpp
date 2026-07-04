// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA Phase 1 — Weight Registry implementation. See stream_weight_registry.h
// and src/poas/README.md for the design.

#include "poas/stream_weight_registry.h"

#include "rpc/rpcwallet.h"      // pulls rpcserver.h (create/publish/subscribe), wallet.h, wallettxs.h, multichain.h
#include "rpc/rpcutils.h"       // OpReturnFormatEntry
#include "structs/base58.h"     // CBitcoinAddress
#include "core/init.h"          // pwalletMain, pwalletTxsMain, ShutdownRequested
#include "core/main.h"          // chainActive, cs_main, IsInitialBlockDownload
#include "net/net.h"            // vNodes, cs_vNodes
#include "utils/util.h"         // GetArg, LogPrintf, RenameThread, GetBoolArg
#include "utils/utiltime.h"     // MilliSleep, GetTime

#include <boost/foreach.hpp>

using namespace std;
using namespace json_spirit;

uint32_t g_node_weight = MC_WPOA_DEFAULT_WEIGHT;

// Retry pacing for the deferred registration thread.
static const int MC_WPOA_RETRY_INTERVAL_MS = 3000;
static const int MC_WPOA_MAX_ATTEMPTS      = 200;   // ~10 minutes worst case

// ---------------------------------------------------------------------------
// Construction
// ---------------------------------------------------------------------------

StreamWeightRegistry::StreamWeightRegistry(mc_WalletTxs* pwalletIn)
{
    m_pWalletTxs       = pwalletIn;
    m_StreamName       = MC_WPOA_WEIGHTS_STREAM_NAME;
    m_LocalAddress     = "";
    m_CreateAttempted  = false;
    m_SubscribeAttempted = false;
    ResolveLocalAddress();
}

StreamWeightRegistry::~StreamWeightRegistry()
{
    // m_pWalletTxs is borrowed, nothing to free.
}

// Resolve the address that identifies this validator. A wPoA weight belongs to
// a miner/validator, so we prefer the mining address, then the connect address,
// then the wallet default key. Falls back to a placeholder if none is valid.
void StreamWeightRegistry::ResolveLocalAddress()
{
    m_LocalAddress = "unknown";

    if (pwalletMain == NULL)
    {
        LogPrintf("[StreamWeightRegistry] WARNING: wallet not available, using placeholder address\n");
        return;
    }

    CPubKey pkey;
    {
        // GetKeyFromAddressBook does not lock internally; hold cs_wallet since we
        // may be called from a threadSafe RPC or the background registration thread.
        LOCK(pwalletMain->cs_wallet);
        if (!pwalletMain->GetKeyFromAddressBook(pkey, MC_PTP_MINE))
        {
            if (!pwalletMain->GetKeyFromAddressBook(pkey, MC_PTP_CONNECT))
            {
                pkey = pwalletMain->vchDefaultKey;
            }
        }
    }

    if (pkey.IsValid())
    {
        m_LocalAddress = CBitcoinAddress(pkey.GetID()).ToString();
    }
    else
    {
        LogPrintf("[StreamWeightRegistry] WARNING: no valid node address, using placeholder\n");
    }
}

// ---------------------------------------------------------------------------
// Stream / subscription helpers (writes reuse MultiChain RPC handlers)
// ---------------------------------------------------------------------------

// Looks up the confirmed "wpoa-weights" stream entity by name.
// Returns true and fills *entity only when the stream exists and is a stream.
bool StreamWeightRegistry::GetStreamEntity(mc_EntityDetails* entity)
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

// Ensures the stream exists. If missing, issues exactly one `create` transaction
// and returns false (the stream only becomes usable once that tx confirms).
bool StreamWeightRegistry::EnsureStreamExists()
{
    mc_EntityDetails entity;
    if (GetStreamEntity(&entity))
    {
        return true;
    }

    if (m_CreateAttempted)
    {
        // create tx already broadcast, still waiting for confirmation
        return false;
    }

    // create ["stream", "wpoa-weights", true]  (open stream: any address with
    // write permission may publish).
    Array params;
    params.push_back(string("stream"));
    params.push_back(m_StreamName);
    params.push_back(true);

    m_CreateAttempted = true;
    try
    {
        Value result = createcmd(params, false);
        LogPrintf("[StreamWeightRegistry] Stream '%s' create tx broadcast: %s\n",
                  m_StreamName.c_str(), result.get_str().c_str());
    }
    catch (const Object& objError)
    {
        LogPrintf("[StreamWeightRegistry] ERROR creating stream '%s' (create permission required?)\n",
                  m_StreamName.c_str());
    }
    catch (const std::exception& e)
    {
        LogPrintf("[StreamWeightRegistry] ERROR creating stream '%s': %s\n", m_StreamName.c_str(), e.what());
    }
    return false; // not usable until confirmed
}

// Ensures this node is subscribed to the stream (required for reads).
bool StreamWeightRegistry::EnsureSubscribed()
{
    mc_EntityDetails entity;
    if (!GetStreamEntity(&entity))
    {
        return false;
    }

    // Already subscribed?
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
        LogPrintf("[StreamWeightRegistry] Subscribed to stream '%s'\n", m_StreamName.c_str());
        // Re-check: subscription import may complete synchronously for a short stream.
        return m_pWalletTxs != NULL && m_pWalletTxs->WRPFindEntity(&entStat);
    }
    catch (const Object& objError)
    {
        LogPrintf("[StreamWeightRegistry] ERROR subscribing to '%s'\n", m_StreamName.c_str());
    }
    catch (const std::exception& e)
    {
        LogPrintf("[StreamWeightRegistry] ERROR subscribing to '%s': %s\n", m_StreamName.c_str(), e.what());
    }
    return false;
}

// Publishes one weight record: key = node address, data = {"json": {...}}.
bool StreamWeightRegistry::PublishWeightRecord(uint32_t weight)
{
    // Build the JSON payload described in the spec.
    Object record;
    record.push_back(Pair("timestamp", (int64_t)GetTime()));
    record.push_back(Pair("node_address", m_LocalAddress));
    record.push_back(Pair("weight", (int64_t)weight));

    int height = 0;
    {
        LOCK(cs_main);
        if (chainActive.Tip() != NULL)
        {
            height = chainActive.Height();
        }
    }
    record.push_back(Pair("height", height));

    // Wrap as MultiChain formatted data: {"json": <record>}.
    Object data_obj;
    data_obj.push_back(Pair("json", record));

    // publish ["wpoa-weights", <address-as-key>, {"json": {...}}]
    Array params;
    params.push_back(m_StreamName);
    params.push_back(m_LocalAddress);
    params.push_back(data_obj);

    try
    {
        Value result = publish(params, false);
        LogPrintf("[StreamWeightRegistry] Weight registered: %s = %u (tx %s)\n",
                  m_LocalAddress.c_str(), weight, result.get_str().c_str());
        return true;
    }
    catch (const Object& objError)
    {
        LogPrintf("[StreamWeightRegistry] ERROR publishing weight (write permission / funds?)\n");
    }
    catch (const std::exception& e)
    {
        LogPrintf("[StreamWeightRegistry] ERROR publishing weight: %s\n", e.what());
    }
    return false;
}

bool StreamWeightRegistry::RegisterLocalWeight(uint32_t weight)
{
    if (weight == 0)
    {
        LogPrintf("[StreamWeightRegistry] ERROR: weight must be > 0, refusing to register\n");
        return false;
    }
    if (m_pWalletTxs == NULL || pwalletMain == NULL)
    {
        LogPrintf("[StreamWeightRegistry] ERROR: wallet not available\n");
        return false;
    }

    if (!EnsureStreamExists())
    {
        return false; // created just now or waiting for confirmation
    }
    if (!EnsureSubscribed())
    {
        return false; // subscribing / import in progress
    }

    // Idempotency: skip if the latest confirmed record already carries this weight.
    uint32_t current = GetNodeWeight(m_LocalAddress);
    if (current == weight)
    {
        LogPrintf("[StreamWeightRegistry] Local weight already registered: %s = %u\n",
                  m_LocalAddress.c_str(), weight);
        return true;
    }

    return PublishWeightRecord(weight);
}

// ---------------------------------------------------------------------------
// Reads (low-level, self-locking, slot-free — safe from any thread)
// ---------------------------------------------------------------------------

// Extracts (node_address, weight) from a stream item transaction whose OP_RETURN
// output belongs to the given stream short-txid. Returns false if the tx does not
// carry a decodable weight record for that stream.
static bool DecodeWeightRecord(const CWalletTx& wtx, const unsigned char* stream_short_txid,
                               string& out_addr, uint32_t& out_weight)
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

        if (!script.IsOpReturnScript())
        {
            continue;
        }
        if (script.GetNumElements() == 0)
        {
            continue;
        }

        // Strip the data-format meta element (mirrors StreamItemEntry).
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

        // Last element holds the item data (on-chain records only in Phase 1).
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

        // Decode into a JSON value: {"json": {...}} for UBJSON-formatted items.
        Value v = OpReturnFormatEntry(data, data_size, wtx.GetHash(), j, format);
        if (v.type() != obj_type)
        {
            continue;
        }

        // Find the "json" member.
        Value json_val;
        bool have_json = false;
        BOOST_FOREACH(const Pair& p, v.get_obj())
        {
            if (p.name_ == "json")
            {
                json_val = p.value_;
                have_json = true;
                break;
            }
        }
        if (!have_json || json_val.type() != obj_type)
        {
            continue;
        }

        // Pull node_address + weight from the record.
        string addr;
        int64_t w = -1;
        BOOST_FOREACH(const Pair& p, json_val.get_obj())
        {
            if (p.name_ == "node_address" && p.value_.type() == str_type)
            {
                addr = p.value_.get_str();
            }
            else if (p.name_ == "weight")
            {
                if (p.value_.type() == int_type)
                {
                    w = p.value_.get_int64();
                }
                else if (p.value_.type() == real_type)
                {
                    w = (int64_t)p.value_.get_real();
                }
            }
        }

        if (!addr.empty() && w > 0)
        {
            out_addr = addr;
            out_weight = (uint32_t)w;
            return true;
        }
    }
    return false;
}

// Reads every record on the stream (oldest -> newest) and keeps, per address,
// the newest weight seen. Returns false only when the stream is unavailable
// (does not exist yet, or this node is not subscribed).
bool StreamWeightRegistry::ReadAllRecords(std::map<std::string, uint32_t>& out_latest)
{
    out_latest.clear();

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
    if (!m_pWalletTxs->WRPFindEntity(&entStat))
    {
        return false; // not subscribed
    }

    int total = m_pWalletTxs->WRPGetListSize(&entStat.m_Entity, entStat.m_Generation, NULL);
    if (total <= 0)
    {
        return true; // subscribed but empty -> empty map
    }

    mc_Buffer rows;
    rows.Initialize(MC_TDB_ENTITY_KEY_SIZE, sizeof(mc_TxEntityRow), MC_BUF_MODE_DEFAULT);

    // Ascending order (from=1). Overwriting per address makes the newest win.
    if (m_pWalletTxs->WRPGetList(&entStat.m_Entity, entStat.m_Generation, 1, total, &rows) != MC_ERR_NOERROR)
    {
        return false;
    }

    const unsigned char* stream_short_txid = entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET;

    for (int i = 0; i < rows.GetCount(); i++)
    {
        mc_TxEntityRow* er = (mc_TxEntityRow*)rows.GetRow(i);

        uint256 hash;
        memcpy(hash.begin(), er->m_TxId, MC_TDB_TXID_SIZE);

        int err = MC_ERR_NOERROR;
        mc_TxDefRow txdef;
        CWalletTx wtx = m_pWalletTxs->WRPGetWalletTx(hash, &txdef, &err);
        if (err != MC_ERR_NOERROR)
        {
            continue;
        }

        string addr;
        uint32_t w = 0;
        if (DecodeWeightRecord(wtx, stream_short_txid, addr, w))
        {
            out_latest[addr] = w; // newest wins (ascending iteration)
        }
    }
    return true;
}

uint32_t StreamWeightRegistry::GetNodeWeight(const std::string& node_address)
{
    std::map<std::string, uint32_t> weights;
    ReadAllRecords(weights);

    std::map<std::string, uint32_t>::const_iterator it = weights.find(node_address);
    uint32_t w = (it != weights.end()) ? it->second : 0;
    LogPrintf("[StreamWeightRegistry] Weight of %s: %u\n", node_address.c_str(), w);
    return w;
}

uint32_t StreamWeightRegistry::GetLocalWeight()
{
    std::map<std::string, uint32_t> weights;
    ReadAllRecords(weights);

    std::map<std::string, uint32_t>::const_iterator it = weights.find(m_LocalAddress);
    uint32_t w = (it != weights.end()) ? it->second : 0;
    if (w == 0)
    {
        LogPrintf("[StreamWeightRegistry] WARNING: local node %s not registered yet\n", m_LocalAddress.c_str());
    }
    else
    {
        LogPrintf("[StreamWeightRegistry] Local weight: %u\n", w);
    }
    return w;
}

std::map<std::string, uint32_t> StreamWeightRegistry::GetAllNodesWeights()
{
    std::map<std::string, uint32_t> weights;
    ReadAllRecords(weights);

    uint64_t total = 0;
    for (std::map<std::string, uint32_t>::const_iterator it = weights.begin(); it != weights.end(); ++it)
    {
        total += it->second;
    }
    LogPrintf("[StreamWeightRegistry] All nodes weights: %u validators, total=%llu\n",
              (unsigned)weights.size(), (unsigned long long)total);
    return weights;
}

bool StreamWeightRegistry::IsLocalWeightRegistered()
{
    std::map<std::string, uint32_t> weights;
    ReadAllRecords(weights);
    return weights.find(m_LocalAddress) != weights.end();
}

void StreamWeightRegistry::DebugPrintWeights()
{
    std::map<std::string, uint32_t> weights;
    ReadAllRecords(weights);

    uint32_t local_weight = 0;
    std::map<std::string, uint32_t>::const_iterator lit = weights.find(m_LocalAddress);
    if (lit != weights.end())
    {
        local_weight = lit->second;
    }

    uint64_t total = 0;
    for (std::map<std::string, uint32_t>::const_iterator it = weights.begin(); it != weights.end(); ++it)
    {
        total += it->second;
    }

    LogPrintf("[StreamWeightRegistry] ════════════════════════════════════════\n");
    LogPrintf("[StreamWeightRegistry] === WEIGHT REGISTRY DEBUG LOG ===\n");
    LogPrintf("[StreamWeightRegistry] Stream: %s\n", m_StreamName.c_str());
    LogPrintf("[StreamWeightRegistry] Local Node Address: %s\n", m_LocalAddress.c_str());
    LogPrintf("[StreamWeightRegistry] Local Weight: %u\n", local_weight);
    LogPrintf("[StreamWeightRegistry] ────────────────────────────────────────\n");
    LogPrintf("[StreamWeightRegistry] All Registered Nodes:\n");
    for (std::map<std::string, uint32_t>::const_iterator it = weights.begin(); it != weights.end(); ++it)
    {
        LogPrintf("[StreamWeightRegistry]   %s: %u\n", it->first.c_str(), it->second);
    }
    LogPrintf("[StreamWeightRegistry] Total Weight (sum): %llu\n", (unsigned long long)total);
    LogPrintf("[StreamWeightRegistry] Number of Validators: %u\n", (unsigned)weights.size());
    LogPrintf("[StreamWeightRegistry] ════════════════════════════════════════\n");
}

// ---------------------------------------------------------------------------
// Deferred registration thread (launched from AppInit2)
// ---------------------------------------------------------------------------

// True once the node is ready to create/publish and reliably read: chain tip
// present, initial block download finished, and (unless offline) at least one
// peer so transactions can propagate and be mined.
static bool NodeReadyForWeightRegistration()
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
        return true; // offline node mines its own blocks locally
    }

    if (IsInitialBlockDownload())
    {
        return false;
    }

    LOCK(cs_vNodes);
    return !vNodes.empty();
}

void ThreadRegisterNodeWeight(uint32_t weight)
{
    RenameThread("mc-wpoa-weight");
    LogPrintf("[StreamWeightRegistry] Deferred weight registration thread started (weight=%u)\n", weight);

    if (pwalletTxsMain == NULL || pwalletMain == NULL)
    {
        LogPrintf("[StreamWeightRegistry] Wallet not available, aborting weight registration\n");
        return;
    }

    StreamWeightRegistry registry(pwalletTxsMain);
    int attempts = 0;

    while (!ShutdownRequested())
    {
        MilliSleep(MC_WPOA_RETRY_INTERVAL_MS);
        if (ShutdownRequested())
        {
            break;
        }

        if (!NodeReadyForWeightRegistration())
        {
            continue; // readiness gate, does not count as an attempt
        }

        attempts++;
        if (registry.RegisterLocalWeight(weight))
        {
            registry.DebugPrintWeights();
            LogPrintf("[StreamWeightRegistry] Weight registration completed\n");
            return;
        }

        if (attempts >= MC_WPOA_MAX_ATTEMPTS)
        {
            LogPrintf("[StreamWeightRegistry] Giving up weight registration after %d attempts\n", attempts);
            return;
        }
    }
}

// ---------------------------------------------------------------------------
// RPC commands
// ---------------------------------------------------------------------------

Value getlocalweight(const Array& params, bool fHelp)
{
    if (fHelp || params.size() != 0)
    {
        throw runtime_error(
            "getlocalweight\n"
            "\nReturns the wPoA weight registered on-chain for this node.\n"
            "\nResult:\n"
            "{\n"
            "  \"address\": \"...\",   (string) this node's address\n"
            "  \"weight\": n,          (numeric) latest confirmed weight, 0 if none\n"
            "  \"registered\": bool    (boolean) whether a confirmed record exists\n"
            "}\n");
    }
    if (pwalletTxsMain == NULL)
    {
        throw JSONRPCError(RPC_WALLET_ERROR, "Wallet not available");
    }

    StreamWeightRegistry registry(pwalletTxsMain);

    Object obj;
    obj.push_back(Pair("address", registry.GetLocalAddress()));
    obj.push_back(Pair("weight", (int64_t)registry.GetLocalWeight()));
    obj.push_back(Pair("registered", registry.IsLocalWeightRegistered()));
    return obj;
}

Value getallweights(const Array& params, bool fHelp)
{
    if (fHelp || params.size() != 0)
    {
        throw runtime_error(
            "getallweights\n"
            "\nReturns the current wPoA weight of every validator on the stream.\n"
            "\nResult:\n"
            "{\n"
            "  \"validators\": n,   (numeric) number of validators\n"
            "  \"total\": n,        (numeric) sum of all weights\n"
            "  \"weights\": { \"address\": weight, ... }\n"
            "}\n");
    }
    if (pwalletTxsMain == NULL)
    {
        throw JSONRPCError(RPC_WALLET_ERROR, "Wallet not available");
    }

    StreamWeightRegistry registry(pwalletTxsMain);
    std::map<std::string, uint32_t> weights = registry.GetAllNodesWeights();

    Object weights_obj;
    uint64_t total = 0;
    for (std::map<std::string, uint32_t>::const_iterator it = weights.begin(); it != weights.end(); ++it)
    {
        weights_obj.push_back(Pair(it->first, (int64_t)it->second));
        total += it->second;
    }

    Object obj;
    obj.push_back(Pair("validators", (int)weights.size()));
    obj.push_back(Pair("total", (int64_t)total));
    obj.push_back(Pair("weights", weights_obj));
    return obj;
}

Value getnodeweight(const Array& params, bool fHelp)
{
    if (fHelp || params.size() != 1)
    {
        throw runtime_error(
            "getnodeweight \"address\"\n"
            "\nReturns the current wPoA weight for a specific validator address.\n"
            "\nArguments:\n"
            "1. \"address\"   (string, required) the validator address\n"
            "\nResult:\n"
            "{\n"
            "  \"address\": \"...\",  (string) the queried address\n"
            "  \"weight\": n          (numeric) latest confirmed weight, 0 if none\n"
            "}\n");
    }
    if (pwalletTxsMain == NULL)
    {
        throw JSONRPCError(RPC_WALLET_ERROR, "Wallet not available");
    }

    string address = params[0].get_str();

    StreamWeightRegistry registry(pwalletTxsMain);

    Object obj;
    obj.push_back(Pair("address", address));
    obj.push_back(Pair("weight", (int64_t)registry.GetNodeWeight(address)));
    return obj;
}
