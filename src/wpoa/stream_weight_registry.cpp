// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA Phase 1 — Weight Registry implementation. See stream_weight_registry.h
// and src/wpoa/README.md for the design.

#include "wpoa/stream_weight_registry.h"

#include "rpc/rpcwallet.h"      // pulls rpcserver.h (create/publish/subscribe), wallet.h, wallettxs.h, multichain.h
#include "rpc/rpcutils.h"       // OpReturnFormatEntry
#include "structs/base58.h"     // CBitcoinAddress
#include "core/init.h"          // pwalletMain, pwalletTxsMain, ShutdownRequested
#include "core/main.h"          // chainActive, cs_main, IsInitialBlockDownload
#include "utils/util.h"         // GetArg, LogPrintf, RenameThread, GetBoolArg
#include "utils/utiltime.h"     // MilliSleep, GetTime
#include "wpoa/weight_record.h" // mc_ParseWeightRecordJson, mc_AccumulateLatestWeight

#include <boost/foreach.hpp>

using namespace std;
using namespace json_spirit;

uint32_t g_node_weight = MC_WPOA_DEFAULT_WEIGHT;

// wPoA Phase 1: weights-stream gate. Default off — the wpoa-weights stream is only
// created and populated when this is set (directly via -enablewpoaweights, forced on
// by any higher wPoA phase, or by the -enablewpoa master switch). Resolved once in
// AppInit2. When off the node behaves as a plain MultiChain instance (no stream).
bool g_wpoa_weights_enabled = false;

// Retry pacing for the deferred registration thread.
static const int MC_WPOA_RETRY_INTERVAL_MS = 3000;
static const int MC_WPOA_MAX_ATTEMPTS      = 200;   // ~10 minutes worst case
// After a successful publish, how long to wait for the tx to be mined & imported
// before printing the debug dump (so it shows the confirmed value, not 0).
static const int MC_WPOA_CONFIRM_ATTEMPTS  = 20;    // 20 * 3s = up to ~60s
// How many FAILED create/subscribe attempts to make before giving up. A failure can be
// transient (wallet still locked, no spendable output yet, the `create` grant not yet
// confirmed) or permanent (this node simply has no create permission, which is the normal
// case for every non-admin node). Retrying a bounded number of times rides out the former
// without logging forever about the latter. Previously a single attempt -- successful or
// not -- latched permanently, so ONE transient error wedged the node for its whole run.
static const int MC_WPOA_STREAM_SETUP_MAX_ATTEMPTS = 20;   // 20 * 3s = up to ~60s

// ---------------------------------------------------------------------------
// Construction
// ---------------------------------------------------------------------------

StreamWeightRegistry::StreamWeightRegistry(mc_WalletTxs* pwalletIn)
{
    m_pWalletTxs       = pwalletIn;
    m_StreamName       = MC_WPOA_WEIGHTS_STREAM_NAME;
    m_LocalAddress     = "";
    m_CreateBroadcast    = false;
    m_CreateFailures     = 0;
    m_SubscribeIssued    = false;
    m_SubscribeFailures  = 0;
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

// Ensures the stream exists. If missing, issues a `create` transaction and returns false
// (the stream only becomes usable once that tx confirms).
bool StreamWeightRegistry::EnsureStreamExists()
{
    mc_EntityDetails entity;
    if (GetStreamEntity(&entity))
    {
        // Also the convergence point of the multi-admin race: stream names are unique, so
        // if two admins create concurrently one transaction is rejected -- and the loser
        // finds the winner's stream here on its next tick and stops trying.
        return true;
    }

    if (m_CreateBroadcast)
    {
        // create tx already broadcast, still waiting for confirmation. Never issue a
        // second one: it would at best be rejected as a duplicate name and at worst race
        // the first.
        return false;
    }

    if (m_CreateFailures >= MC_WPOA_STREAM_SETUP_MAX_ATTEMPTS)
    {
        return false;   // gave up; almost certainly no `create` permission on this node
    }

    // create ["stream", "wpoa-weights", false] -> CLOSED (write permission
    // required). Weight updates are restricted to a subset of authorized
    // entities (consortium administrators, or a reputation oracle holding a
    // dedicated permission), enforced by MultiChain's own granular permissions
    // rather than by convention — cfr. Def. 5.16, weight-registry data model.
    // Grant the publishers explicitly:  grant <addr> wpoa-weights.write
    Array params;
    params.push_back(string("stream"));
    params.push_back(m_StreamName);
    params.push_back(false);

    try
    {
        Value result = createcmd(params, false);
        m_CreateBroadcast = true;   // latch ONLY on a real broadcast
        LogPrintf("[StreamWeightRegistry] Stream '%s' create tx broadcast: %s\n",
                  m_StreamName.c_str(), result.get_str().c_str());
    }
    catch (const Object& objError)
    {
        m_CreateFailures++;
        LogPrintf("[StreamWeightRegistry] could not create stream '%s' (attempt %d/%d): "
                  "create permission required, or the wallet has no spendable output yet\n",
                  m_StreamName.c_str(), m_CreateFailures, MC_WPOA_STREAM_SETUP_MAX_ATTEMPTS);
    }
    catch (const std::exception& e)
    {
        m_CreateFailures++;
        LogPrintf("[StreamWeightRegistry] could not create stream '%s' (attempt %d/%d): %s\n",
                  m_StreamName.c_str(), m_CreateFailures, MC_WPOA_STREAM_SETUP_MAX_ATTEMPTS, e.what());
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

    if (m_SubscribeIssued)
    {
        // subscribe already issued, the import is still catching up. Do not re-issue: a
        // redundant subscribe would restart the rescan of the stream on every tick.
        return false;
    }

    if (m_SubscribeFailures >= MC_WPOA_STREAM_SETUP_MAX_ATTEMPTS)
    {
        return false;
    }

    Array params;
    params.push_back(m_StreamName);

    try
    {
        subscribe(params, false);
        m_SubscribeIssued = true;   // latch ONLY on a call that did not throw
        LogPrintf("[StreamWeightRegistry] Subscribed to stream '%s'\n", m_StreamName.c_str());
        // Re-check: subscription import may complete synchronously for a short stream.
        return m_pWalletTxs != NULL && m_pWalletTxs->WRPFindEntity(&entStat);
    }
    catch (const Object& objError)
    {
        m_SubscribeFailures++;
        LogPrintf("[StreamWeightRegistry] could not subscribe to '%s' (attempt %d/%d)\n",
                  m_StreamName.c_str(), m_SubscribeFailures, MC_WPOA_STREAM_SETUP_MAX_ATTEMPTS);
    }
    catch (const std::exception& e)
    {
        m_SubscribeFailures++;
        LogPrintf("[StreamWeightRegistry] could not subscribe to '%s' (attempt %d/%d): %s\n",
                  m_StreamName.c_str(), m_SubscribeFailures, MC_WPOA_STREAM_SETUP_MAX_ATTEMPTS, e.what());
    }
    return false;
}

// Create-if-missing + subscribe, in that order. See the header for why this is public and
// why the publication threads must call it BEFORE they have anything to publish.
bool StreamWeightRegistry::EnsureStreamReady()
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

// Publishes one weight record: key = node address, data = {"json": {...}}.
bool StreamWeightRegistry::PublishWeightRecord(uint32_t weight, uint32_t epoch)
{
    // Build the JSON payload described in the spec.
    Object record;
    record.push_back(Pair("timestamp", (int64_t)GetTime()));
    record.push_back(Pair("node_address", m_LocalAddress));
    record.push_back(Pair("weight", (int64_t)weight));

    // The epoch the value was computed FOR, when it was computed at all. Stamping it
    // is what lets a verifier compare the value against the RIGHT epoch's inputs; a
    // weight published for epoch e checked against epoch e+1's recomputation would
    // flag an honest node as wrong. Omitted (0) for the static -weight path, which is
    // not derived from any epoch and so has nothing to be verified against.
    if (epoch > 0)
    {
        record.push_back(Pair("epoch", (int64_t)epoch));
    }

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

    // publishfrom [<address>, "wpoa-weights", <address-as-key>, {"json": {...}}]
    //
    // publishFROM, not publish. This matters and is not cosmetic: a weight record is
    // now SELF-PUBLISHED — the reader discards it unless the transaction's SIGNER is
    // the node_address in the payload (DecodeWeightRecord). Plain `publish` lets the
    // wallet choose whichever address funds the transaction, which on a multi-address
    // wallet need not be m_LocalAddress; the record would then be perfectly
    // well-formed and silently discarded by every peer. Naming the address explicitly
    // makes the signer and the declared node the same by construction.
    Array params;
    params.push_back(m_LocalAddress);
    params.push_back(m_StreamName);
    params.push_back(m_LocalAddress);
    params.push_back(data_obj);

    try
    {
        Value result = publishfrom(params, false);
        LogPrintf("[StreamWeightRegistry] Weight registered: %s = %u (tx %s)\n",
                  m_LocalAddress.c_str(), weight, result.get_str().c_str());
        return true;
    }
    catch (const Object& objError)
    {
        LogPrintf("[StreamWeightRegistry] ERROR publishing weight from %s "
                  "(write permission / funds on that address?)\n", m_LocalAddress.c_str());
    }
    catch (const std::exception& e)
    {
        LogPrintf("[StreamWeightRegistry] ERROR publishing weight: %s\n", e.what());
    }
    return false;
}

bool StreamWeightRegistry::RegisterLocalWeight(uint32_t weight, uint32_t epoch)
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

    if (!EnsureStreamReady())
    {
        return false; // created/subscribed just now, or waiting for confirmation
    }

    // Idempotency: skip if the latest confirmed record already carries this weight.
    uint32_t current = GetNodeWeight(m_LocalAddress);
    if (current == weight)
    {
        LogPrintf("[StreamWeightRegistry] Local weight already registered: %s = %u\n",
                  m_LocalAddress.c_str(), weight);
        return true;
    }

    return PublishWeightRecord(weight, epoch);
}

// ---------------------------------------------------------------------------
// Reads (low-level, self-locking, slot-free — safe from any thread)
// ---------------------------------------------------------------------------

// Decodes the addresses that SIGNED `wtx` from its input scripts — the item's
// publishers, i.e. the cryptographic identity of whoever wrote it. Mirrors
// MultiChain's own extraction in StreamItemEntry1 (rpc/rpcwalletutils.cpp): for each
// input, recover the address embedded in the scriptSig and keep it only when the
// signature commits to the whole transaction (SIGHASH_ALL) or to this very output
// (SIGHASH_SINGLE at the same index) — a signature committing to neither does not
// authenticate this item. Deduplicated, in canonical CBitcoinAddress form so it can be
// compared directly against a payload address.
static void ExtractItemPublishers(const CWalletTx& wtx, int stream_output,
                                  std::vector<string>& out)
{
    out.clear();

    std::set<uint160> seen;
    for (int i = 0; i < (int)wtx.vin.size(); i++)
    {
        const CScript& sig = wtx.vin[i].scriptSig;
        if (sig.size() == 0)
        {
            continue;
        }
        CScript::const_iterator pc = sig.begin();

        int op_addr_offset = 0;
        int op_addr_size = 0;
        int is_redeem_script = 0;
        int sighash_type = SIGHASH_NONE;

        const unsigned char* ptr = mc_ExtractAddressFromInputScript(
            (unsigned char*)(&pc[0]), (int)(sig.end() - pc),
            &op_addr_offset, &op_addr_size, &is_redeem_script, &sighash_type, 0);
        if (ptr == NULL)
        {
            continue;
        }
        if (sighash_type != SIGHASH_ALL &&
            !(sighash_type == SIGHASH_SINGLE && i == stream_output))
        {
            continue;
        }

        uint160 hash = Hash160(ptr + op_addr_offset, ptr + op_addr_offset + op_addr_size);
        if (seen.count(hash) != 0)
        {
            continue;
        }
        seen.insert(hash);

        if (is_redeem_script)
        {
            out.push_back(CBitcoinAddress((CScriptID)hash).ToString());
        }
        else
        {
            out.push_back(CBitcoinAddress((CKeyID)hash).ToString());
        }
    }
}

// Extracts (node_address, weight) from a stream item transaction whose OP_RETURN
// output belongs to the given stream short-txid. Returns false if the tx does not
// carry a decodable weight record for that stream.
//
// SELF-PUBLICATION IS ENFORCED HERE (consensus-critical). A weight record describes
// its own publisher's cluster, so it is valid only if the address that SIGNED the
// transaction is the node_address the payload declares
// (mc_StreamItemIsSelfAttested, weight_record.h). A record naming somebody else is
// DISCARDED: it never reaches the weight map, so no node can publish a weight on
// another cluster's behalf. This is what makes it safe to grant
// wpoa-weights.write to every node rather than to one publisher per cluster.
//
// `out_publishers` carries the recovered signers to the caller for logging and for the
// malus path, which accuses on exactly the discard this function performs.
static bool DecodeWeightRecord(const CWalletTx& wtx, const unsigned char* stream_short_txid,
                               string& out_addr, uint32_t& out_weight, uint32_t& out_epoch,
                               std::vector<string>& out_publishers, bool& out_forged)
{
    out_publishers.clear();
    out_forged = false;
    out_epoch = 0;

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

        // Decode into a JSON value. Use the *6-argument* overload (with a
        // format_text_out): it returns the raw formatted value — {"json": {...}}
        // for a UBJSON item — exactly like StreamItemEntry (and liststreamitems).
        //
        // Do NOT use the 3-argument overload here: it wraps the value as
        // {"format":"json","formatdata":{"json":{...}}}, which mc_ParseWeightRecordJson
        // would (correctly) reject because there is no top-level "json" key. That
        // mismatch is exactly why decoding silently failed for every item.
        string format_text;
        Value v = OpReturnFormatEntry(data, data_size, wtx.GetHash(), j, format, &format_text);
        if (mc_ParseWeightRecordJson(v, out_addr, out_weight, &out_epoch))
        {
            ExtractItemPublishers(wtx, j, out_publishers);

            // Self-publication: the signer must BE the node the record is about.
            if (!mc_StreamItemIsSelfAttested(out_addr, out_publishers))
            {
                out_forged = true;      // decodable, but published on another's behalf
                out_weight = 0;
                return false;           // DISCARD: never enters the weight map
            }
            return true;
        }
    }
    return false;
}

// Reads every record on the stream (oldest -> newest) and keeps, per address,
// the newest weight seen. Returns false only when the stream is unavailable
// (does not exist yet, or this node is not subscribed).
bool StreamWeightRegistry::ReadAllRecords(std::map<std::string, uint32_t>& out_latest,
                                          std::map<std::string, uint32_t>* out_epochs)
{
    // Verbose, per-read tracing of the stream read path. Off by default; enable
    // with -wpoadebug for troubleshooting (see src/wpoa/TESTING.md).
    static const bool dbg = GetBoolArg("-wpoadebug", false);

    out_latest.clear();
    if (out_epochs != NULL)
    {
        out_epochs->clear();
    }

    if (m_pWalletTxs == NULL)
    {
        if (dbg) LogPrintf("[wpoa-dbg] ReadAllRecords: m_pWalletTxs == NULL\n");
        return false;
    }

    mc_EntityDetails entity;
    if (!GetStreamEntity(&entity))
    {
        if (dbg) LogPrintf("[wpoa-dbg] ReadAllRecords: GetStreamEntity FAILED (stream not found)\n");
        return false; // stream not created yet
    }

    mc_TxEntityStat entStat;
    entStat.Zero();
    memcpy(&entStat, entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET, MC_AST_SHORT_TXID_SIZE);
    entStat.m_Entity.m_EntityType = MC_TET_STREAM | MC_TET_CHAINPOS;

    if (dbg)
    {
        const unsigned char* st = entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET;
        LogPrintf("[wpoa-dbg] ReadAllRecords: stream found, short-txid=%02x%02x%02x%02x%02x%02x%02x%02x, type=0x%08x\n",
                  st[0], st[1], st[2], st[3], st[4], st[5], st[6], st[7],
                  (unsigned)entStat.m_Entity.m_EntityType);
    }

    // IMPORTANT: use the *non-WRP* wallet read API here, not the WRP* family.
    //
    // The WRP* methods (WRPGetListSize/WRPGetList/WRPGetWalletTx) return data from
    // a read snapshot whose list position (m_ReadLastPos) is only refreshed for the
    // RPC read-lock protocol: a reader must hold WRPReadLock() and the snapshot is
    // advanced by the writer side via WRPSync() (on CommitTransaction / mempool
    // changes / import completion — NOT on plain block connect). A self-contained
    // reader that does not participate in that protocol (this background thread, and
    // our read RPCs which do not take the WRP read lock) observes a stale snapshot
    // and would report 0 items forever, even after the publish tx is mined.
    //
    // The non-WRP methods self-lock via Lock(0,0) and read the live list position
    // (m_LastPos), so they see every confirmed item as soon as its block connects.
    // FindEntity does not lock internally, so guard it with the wallet-txs DB lock.
    bool found;
    m_pWalletTxs->Lock();
    found = m_pWalletTxs->FindEntity(&entStat);
    m_pWalletTxs->UnLock();
    if (!found)
    {
        if (dbg) LogPrintf("[wpoa-dbg] ReadAllRecords: FindEntity(STREAM|CHAINPOS) FAILED (not subscribed)\n");
        return false; // not subscribed
    }

    // Read only CONFIRMED items. GetListSize's out-param returns the number of
    // confirmed items (m_LastClearedPos); the return value would also count
    // unconfirmed mempool items (m_LastPos). Confirmed items occupy the first
    // `confirmed` chain positions. We deliberately ignore mempool items: a weight
    // registry that feeds consensus must be identical on every node, and mempool
    // contents differ per node — so a weight only "counts" once it is on-chain.
    int confirmed = 0;
    int total = m_pWalletTxs->GetListSize(&entStat.m_Entity, entStat.m_Generation, &confirmed);
    if (dbg) LogPrintf("[wpoa-dbg] ReadAllRecords: FindEntity OK, generation=%d, total=%d confirmed=%d\n",
                       entStat.m_Generation, total, confirmed);
    if (confirmed <= 0)
    {
        return true; // subscribed, but no confirmed items yet -> empty map
    }

    mc_Buffer rows;
    rows.Initialize(MC_TDB_ENTITY_KEY_SIZE, sizeof(mc_TxEntityRow), MC_BUF_MODE_DEFAULT);

    // Ascending order (from=1), confirmed prefix only. Overwriting per address
    // makes the newest confirmed record win.
    int list_err = m_pWalletTxs->GetList(&entStat.m_Entity, entStat.m_Generation, 1, confirmed, &rows);
    if (list_err != MC_ERR_NOERROR)
    {
        if (dbg) LogPrintf("[wpoa-dbg] ReadAllRecords: GetList FAILED err=%d\n", list_err);
        return false;
    }
    if (dbg) LogPrintf("[wpoa-dbg] ReadAllRecords: GetList OK, rows=%d\n", rows.GetCount());

    const unsigned char* stream_short_txid = entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET;

    for (int i = 0; i < rows.GetCount(); i++)
    {
        mc_TxEntityRow* er = (mc_TxEntityRow*)rows.GetRow(i);

        // Chunked/off-chain items are split across extension rows; we only ever
        // publish tiny on-chain JSON, so those never occur here — skip defensively
        // (a plain m_TxId copy would be the wrong hash for an extension row).
        if (er->m_Flags & MC_TFL_IS_EXTENSION)
        {
            if (dbg) LogPrintf("[wpoa-dbg]   row %d: extension row, skipped\n", i);
            continue;
        }

        uint256 hash;
        memcpy(hash.begin(), er->m_TxId, MC_TDB_TXID_SIZE);

        int err = MC_ERR_NOERROR;
        mc_TxDefRow txdef;
        CWalletTx wtx = m_pWalletTxs->GetWalletTx(hash, &txdef, &err);
        if (err != MC_ERR_NOERROR)
        {
            if (dbg) LogPrintf("[wpoa-dbg]   row %d: GetWalletTx err=%d hash=%s\n", i, err, hash.ToString().c_str());
            continue;
        }

        string addr;
        uint32_t w = 0;
        uint32_t rec_epoch = 0;
        std::vector<string> publishers;
        bool forged = false;
        bool decoded = DecodeWeightRecord(wtx, stream_short_txid, addr, w, rec_epoch,
                                          publishers, forged);
        if (dbg) LogPrintf("[wpoa-dbg]   row %d: hash=%s vout=%d decode=%s addr=%s w=%u\n",
                           i, hash.ToString().c_str(), (int)wtx.vout.size(),
                           decoded ? "OK" : (forged ? "DISCARDED(not self-published)" : "FAIL"),
                           addr.c_str(), w);
        if (forged)
        {
            // A well-formed record published on another address's behalf. Logged
            // unconditionally, not only under -wpoadebug: it is a provable protocol
            // violation, and it is the evidence the malus registry accuses on.
            LogPrintf("[wPoA] wpoa-weights record for '%s' DISCARDED: not signed by that "
                      "address (signer%s %s), txid=%s\n",
                      addr.c_str(), publishers.size() == 1 ? "" : "s",
                      publishers.empty() ? "<unrecoverable>" : publishers[0].c_str(),
                      hash.ToString().c_str());
            continue;
        }
        if (decoded)
        {
            mc_AccumulateLatestWeight(out_latest, addr, w); // newest wins (ascending iteration)
            if (out_epochs != NULL)
            {
                (*out_epochs)[addr] = rec_epoch;            // same newest-wins record
            }
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

void StreamWeightRegistry::GetAllNodesWeightsWithEpoch(std::map<std::string, uint32_t>& weights,
                                                       std::map<std::string, uint32_t>& epochs)
{
    weights.clear();
    epochs.clear();
    ReadAllRecords(weights, &epochs);
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

bool StreamWeightRegistry::WaitForLocalWeight(uint32_t weight, int max_attempts, int interval_ms)
{
    for (int i = 0; i < max_attempts; i++)
    {
        if (ShutdownRequested())
        {
            return false;
        }

        // Quiet read (no per-attempt warning logging).
        std::map<std::string, uint32_t> weights;
        ReadAllRecords(weights);
        std::map<std::string, uint32_t>::const_iterator it = weights.find(m_LocalAddress);
        if (it != weights.end() && it->second == weight)
        {
            return true;
        }

        MilliSleep(interval_ms);
    }
    return false;
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

// True once the node is ready to create/publish and reliably read: a chain tip
// exists and (unless offline) the initial block download has finished.
//
// We deliberately do NOT require peers: a single permitted miner produces blocks
// on its own, so a peerless chain is still able to confirm the create/publish
// transactions. If this node can neither mine nor reach a miner, RegisterLocalWeight
// simply keeps returning false and eventually gives up — no harm done.
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
        return true;
    }

    return !IsInitialBlockDownload();
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
        // No epoch argument: a static -weight is not derived from any epoch, so the
        // record carries no epoch field and is deliberately NOT subject to value
        // verification — there is no pipeline run to check it against. See
        // mc_ParseWeightRecordJson.
        if (registry.RegisterLocalWeight(weight))
        {
            // The publish tx may still be in the mempool; reads only see confirmed
            // items. Wait until the record is mined & imported so the debug dump
            // shows the committed value instead of 0.
            if (registry.WaitForLocalWeight(weight, MC_WPOA_CONFIRM_ATTEMPTS, MC_WPOA_RETRY_INTERVAL_MS))
            {
                LogPrintf("[StreamWeightRegistry] Weight confirmed on-chain\n");
            }
            else
            {
                LogPrintf("[StreamWeightRegistry] Weight submitted; awaiting a block "
                          "(will become visible once mined)\n");
            }
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
