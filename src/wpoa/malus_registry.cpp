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
#include "weight_engine/weight_engine.h"  // HeightToEpoch (shared map), g_weight_engine_enabled
#include "weight_engine/weight_verifier.h" // WeightEngineRecomputeWeightForEpoch
#include "weight_engine/weight_streams.h"  // MC_WEIGHT_MEMBERSHIP_STREAM_NAME
#include "weight_engine/weight_records.h"  // mc_ParseMembershipRecordJson

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
double g_wpoa_malus_p_selfwrite = MC_WPOA_DEFAULT_MALUS_P_SELFWRITE;
double g_wpoa_malus_p_badweight = MC_WPOA_DEFAULT_MALUS_P_BADWEIGHT;

// The four scores as one value, resolved from the runtime globals in exactly one place
// so no call site can pick up three of them and forget the fourth.
MalusScores WPoAMalusScores()
{
    return MalusScores(g_wpoa_malus_p_equiv, g_wpoa_malus_p_delay,
                       g_wpoa_malus_p_selfwrite, g_wpoa_malus_p_badweight);
}

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
    m_Create.Zero();
    m_Subscribe.Zero();
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

    if (m_Create.Next() != MC_SSA_ACT)
    {
        return false;   // a create tx is in flight, or we have given up on this node
    }

    // create ["stream", "wpoa-weights-malus", true] -> OPEN, by design (Def. 5.17).
    // Unlike wpoa-weights, reporting misbehaviour is deliberately open to every
    // participant: the safety of that openness rests on ValidReport, not on who is
    // allowed to speak.
    Array params;
    params.push_back(string("stream"));
    params.push_back(m_StreamName);
    params.push_back(true);

    try
    {
        Value result = createcmd(params, false);
        // Latch ONLY on a real broadcast: latching before the attempt made one transient
        // failure permanent, and the report stream then never existed on that node.
        m_Create.RecordBroadcast();
        LogPrintf("[MalusRegistry] Stream '%s' create tx broadcast (open): %s\n",
                  m_StreamName.c_str(), result.get_str().c_str());
    }
    catch (const Object& objError)
    {
        m_Create.RecordFailure();
        LogPrintf("[MalusRegistry] could not create stream '%s' (attempt %d/%d): create "
                  "permission required, or the wallet has no spendable output yet; will retry\n",
                  m_StreamName.c_str(), m_Create.failures, MC_WPOA_STREAM_SETUP_MAX_FAILURES);
    }
    catch (const std::exception& e)
    {
        m_Create.RecordFailure();
        LogPrintf("[MalusRegistry] could not create stream '%s' (attempt %d/%d): %s; will retry\n",
                  m_StreamName.c_str(), m_Create.failures,
                  MC_WPOA_STREAM_SETUP_MAX_FAILURES, e.what());
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

    if (m_Subscribe.Next() != MC_SSA_ACT)
    {
        return false;   // gave up
    }

    Array params;
    params.push_back(m_StreamName);

    try
    {
        subscribe(params, false);
        m_Subscribe.RecordBroadcast();
        LogPrintf("[MalusRegistry] Subscribed to stream '%s'\n", m_StreamName.c_str());
        return m_pWalletTxs != NULL && m_pWalletTxs->WRPFindEntity(&entStat);
    }
    catch (const Object& objError)
    {
        m_Subscribe.RecordFailure();
        LogPrintf("[MalusRegistry] could not subscribe to '%s' (attempt %d/%d); will retry\n",
                  m_StreamName.c_str(), m_Subscribe.failures,
                  MC_WPOA_STREAM_SETUP_MAX_FAILURES);
    }
    catch (const std::exception& e)
    {
        m_Subscribe.RecordFailure();
        LogPrintf("[MalusRegistry] could not subscribe to '%s' (attempt %d/%d): %s; will retry\n",
                  m_StreamName.c_str(), m_Subscribe.failures,
                  MC_WPOA_STREAM_SETUP_MAX_FAILURES, e.what());
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
                              vector<string>& blocks, MalusDataDetail& detail)
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
        if (mc_ParseMalusRecordJson(v, kind, addr, height, blocks, &detail))
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
        if (DecodeMalusRecord(wtx, stream_short_txid, r.kind, r.address, r.height, r.blocks,
                              r.detail))
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

// ---------------------------------------------------------------------------
// Valid(e) for the PUBLISHED-DATA INTEGRITY kinds
// ---------------------------------------------------------------------------
// The evidence is a publishing TRANSACTION, not a block, so this branch reads that
// transaction, decodes its signer and its payload, and confirms the discrepancy the
// report alleges. Nothing here is a judgement: every step is a comparison between two
// pieces of public data, which is what lets two honest nodes reach the same verdict and
// makes a false accusation inert (Prop. 5.15).

// Load the item published by `txid` on `stream_name`, if that transaction is one.
//
// Reads through the wallet-tx store, exactly as every other confirmed-item read in this
// codebase does, so it observes only CONFIRMED state and requires this node to be
// subscribed to the stream. Not being subscribed is reported as such rather than as a
// false accusation: it means this node cannot decide the report, not that the report is
// wrong.
bool MalusRegistry::LoadAccusedItem(mc_WalletTxs* pwallet, const std::string& txid_hex,
                                    const char* stream_name, AccusedItem& out,
                                    std::string* reason_out)
{
    if (pwallet == NULL || mc_gState == NULL || mc_gState->m_Assets == NULL)
    {
        if (reason_out) *reason_out = "wallet / entity store unavailable";
        return false;
    }

    uint256 hash;
    hash.SetHex(txid_hex);
    if (hash == uint256(0))
    {
        if (reason_out) *reason_out = "malformed evidence txid";
        return false;
    }

    mc_EntityDetails entity;
    if (mc_gState->m_Assets->FindEntityByName(&entity, stream_name) == 0 ||
        entity.GetEntityType() != MC_ENT_TYPE_STREAM)
    {
        if (reason_out) *reason_out = std::string("stream '") + stream_name + "' does not exist";
        return false;
    }

    int err = MC_ERR_NOERROR;
    mc_TxDefRow txdef;
    CWalletTx wtx = pwallet->GetWalletTx(hash, &txdef, &err);
    if (err != MC_ERR_NOERROR)
    {
        if (reason_out)
        {
            *reason_out = "evidence transaction not found in this node's view "
                          "(unconfirmed, or the stream is not subscribed here)";
        }
        return false;
    }
    if (txdef.m_Block < 0)
    {
        if (reason_out) *reason_out = "evidence transaction is not confirmed";
        return false;
    }
    out.height = txdef.m_Block;

    const unsigned char* stream_short_txid = entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET;
    out.stream = stream_name;

    mc_Script script;   // local instance -> thread-safe
    for (int j = 0; j < (int)wtx.vout.size(); j++)
    {
        const CScript& spk = wtx.vout[j].scriptPubKey;
        if (spk.size() == 0) continue;
        CScript::const_iterator pc = spk.begin();

        script.Clear();
        script.SetScript((unsigned char*)(&pc[0]), (size_t)(spk.end() - pc),
                         MC_SCR_TYPE_SCRIPTPUBKEY);
        if (!script.IsOpReturnScript()) continue;
        if (script.GetNumElements() == 0) continue;

        uint32_t format;
        unsigned char* chunk_hashes = NULL;
        int chunk_count = 0;
        int64_t total_chunk_size = 0;
        script.ExtractAndDeleteDataFormat(&format, &chunk_hashes, &chunk_count,
                                          &total_chunk_size);

        unsigned char short_txid[MC_AST_SHORT_TXID_SIZE];
        script.SetElement(0);
        if (script.GetEntity(short_txid) != 0) continue;
        if (memcmp(short_txid, stream_short_txid, MC_AST_SHORT_TXID_SIZE) != 0) continue;

        int n = script.GetNumElements();
        if (n < 1) continue;
        size_t data_size = 0;
        const unsigned char* data = script.GetData(n - 1, &data_size);
        if (data == NULL || data_size == 0) continue;

        std::string format_text;
        Value v = OpReturnFormatEntry(data, data_size, wtx.GetHash(), j, format, &format_text);

        // Which payload shape to expect depends on the stream, and both are the SAME
        // parsers the readers use — so the verifier cannot disagree with the reader about
        // what a record says.
        if (strcmp(stream_name, MC_WPOA_WEIGHTS_STREAM_NAME) == 0)
        {
            uint32_t w = 0, e = 0;
            std::string addr;
            if (!mc_ParseWeightRecordJson(v, addr, w, &e)) continue;
            out.declared = addr;
            out.weight = w;
            out.epoch = e;
        }
        else
        {
            std::string node, miner;
            uint32_t ts = 0;
            if (!mc_ParseMembershipRecordJson(v, node, miner, ts)) continue;
            out.declared = node;
        }

        // The signers, recovered from the transaction's inputs the same way the readers
        // recover them (StreamItemEntry / rpcwalletutils.cpp).
        std::set<uint160> seen;
        for (int i = 0; i < (int)wtx.vin.size(); i++)
        {
            const CScript& sig = wtx.vin[i].scriptSig;
            if (sig.size() == 0) continue;
            CScript::const_iterator sc = sig.begin();

            int op_addr_offset = 0, op_addr_size = 0, is_redeem_script = 0;
            int sighash_type = SIGHASH_NONE;
            const unsigned char* ptr = mc_ExtractAddressFromInputScript(
                (unsigned char*)(&sc[0]), (int)(sig.end() - sc),
                &op_addr_offset, &op_addr_size, &is_redeem_script, &sighash_type, 0);
            if (ptr == NULL) continue;
            if (sighash_type != SIGHASH_ALL &&
                !(sighash_type == SIGHASH_SINGLE && i == j)) continue;

            uint160 h160 = Hash160(ptr + op_addr_offset, ptr + op_addr_offset + op_addr_size);
            if (seen.count(h160) != 0) continue;
            seen.insert(h160);
            out.publishers.push_back(is_redeem_script
                                         ? CBitcoinAddress((CScriptID)h160).ToString()
                                         : CBitcoinAddress((CKeyID)h160).ToString());
        }
        return true;
    }

    if (reason_out)
    {
        *reason_out = std::string("transaction carries no decodable '") + stream_name +
                      "' item";
    }
    return false;
}

bool MalusRegistry::ValidDataIntegrityReport(MalusKind kind, const std::string& node_address,
                                             int height,
                                             const std::vector<std::string>& blocks,
                                             const MalusDataDetail& detail,
                                             std::string* reason_out)
{
    if (blocks.size() != 1)
    {
        if (reason_out) *reason_out = "a data-integrity report names exactly one transaction";
        return false;
    }

    if (kind == MALUS_SELF_WRITE)
    {
        // Only the SELF-ATTESTED streams have a rule to break. Naming any other stream is
        // malformed, not merely false: there is no self-attestation to violate on a
        // stream that does not have one.
        const bool is_weights    = (detail.stream == MC_WPOA_WEIGHTS_STREAM_NAME);
        const bool is_membership = (detail.stream == MC_WEIGHT_MEMBERSHIP_STREAM_NAME);
        if (!is_weights && !is_membership)
        {
            if (reason_out)
            {
                *reason_out = "stream is not self-attested (only wpoa-weights and "
                              "weight-engine-membership are)";
            }
            return false;
        }
        // A membership item is only readable where the weight engine runs, since that is
        // what subscribes to the stream. The engine flag is a hash-enforced chain
        // parameter, so every node agrees on whether this kind is decidable at all —
        // which is what keeps the verdict uniform.
        if (is_membership && !g_weight_engine_enabled)
        {
            if (reason_out)
            {
                *reason_out = "membership reports need the weight engine (it is what "
                              "subscribes to that stream)";
            }
            return false;
        }

        AccusedItem item;
        if (!LoadAccusedItem(pwalletTxsMain, blocks[0], detail.stream.c_str(), item,
                             reason_out))
        {
            return false;
        }

        // The report's own claims must match the transaction. Checking them makes the
        // accusation auditable; it is the transaction, never the claim, that decides.
        if (item.declared != detail.declared_address)
        {
            if (reason_out)
            {
                *reason_out = "the record's node_address is not the declared_address the "
                              "report alleges";
            }
            return false;
        }
        if (item.height != height)
        {
            if (reason_out) *reason_out = "the record did not confirm at the reported height";
            return false;
        }

        // THE OFFENCE ITSELF: the accused must be a signer of the transaction, and the
        // record must declare somebody else. Both halves matter — the first establishes
        // that the accused is the one who wrote it, the second that what it wrote was a
        // forgery. Note this is the exact NEGATION of the rule the readers apply
        // (mc_StreamItemIsSelfAttested), from the same shared predicate: a report is
        // valid precisely when the readers discarded the record.
        if (!mc_StreamItemIsSelfAttested(node_address, item.publishers))
        {
            if (reason_out) *reason_out = "the accused did not sign the evidence transaction";
            return false;
        }
        if (mc_StreamItemIsSelfAttested(item.declared, item.publishers))
        {
            if (reason_out)
            {
                *reason_out = "the declared address DID sign, so the record is honest and "
                              "was not discarded";
            }
            return false;
        }
        return true;
    }

    if (kind == MALUS_INVALID_WEIGHT)
    {
        // Recomputing needs the weight engine. Its flag is a hash-enforced chain
        // parameter, so this precondition holds or fails identically on every node.
        if (!g_weight_engine_enabled)
        {
            if (reason_out)
            {
                *reason_out = "weight reports need the weight engine (there is no pipeline "
                              "to recompute without it)";
            }
            return false;
        }

        AccusedItem item;
        if (!LoadAccusedItem(pwalletTxsMain, blocks[0], MC_WPOA_WEIGHTS_STREAM_NAME, item,
                             reason_out))
        {
            return false;
        }

        if (item.declared != node_address)
        {
            if (reason_out) *reason_out = "the record is not about the accused address";
            return false;
        }
        if (!mc_StreamItemIsSelfAttested(node_address, item.publishers))
        {
            // A record the accused did not sign was already discarded on the
            // self-publication rule, so it never entered the weight map and there is
            // nothing to accuse it of HERE — that is a selfwrite report instead. Keeping
            // the two offences disjoint stops one act being scored twice.
            if (reason_out)
            {
                *reason_out = "the accused did not sign the record (that is a selfwrite "
                              "report, not a weight one)";
            }
            return false;
        }
        if (item.height != height)
        {
            if (reason_out) *reason_out = "the record did not confirm at the reported height";
            return false;
        }
        if (item.weight != detail.declared)
        {
            if (reason_out) *reason_out = "the record's weight is not the declared value alleged";
            return false;
        }
        // A record with no epoch is not value-verifiable at all (the static -weight path),
        // so it cannot be the subject of this accusation.
        if (item.epoch == 0 || item.epoch != detail.epoch)
        {
            if (reason_out)
            {
                *reason_out = "the record does not state the epoch the report alleges "
                              "(a weight with no epoch is not value-verifiable)";
            }
            return false;
        }

        // RE-RUN THE PIPELINE. This is the whole proof: the same computation over the
        // same public inputs that the accuser ran, and that any other node can run.
        uint32_t recomputed = 0;
        bool is_cluster = false;
        if (!WeightEngineRecomputeWeightForEpoch(item.epoch, node_address, is_cluster,
                                                 recomputed))
        {
            // Cannot recompute here — inputs not readable, epoch not buried, pruned
            // node. FAIL CLOSED FOR THE ACCUSATION: an unprovable accusation must not
            // count. Note the direction is the same as verification's fail-open, seen
            // from the accused's side: in both cases "cannot tell" means "no penalty".
            if (reason_out)
            {
                *reason_out = "this node cannot recompute that epoch (inputs unreadable, "
                              "epoch not buried, or pruned)";
            }
            return false;
        }

        const uint32_t expected = is_cluster ? recomputed : 0;
        if (expected != detail.recomputed)
        {
            if (reason_out)
            {
                *reason_out = strprintf("recomputation disagrees with the report "
                                        "(this node derives %u, the report alleges %u)",
                                        expected, detail.recomputed);
            }
            return false;
        }
        if (item.weight == expected)
        {
            if (reason_out)
            {
                *reason_out = strprintf("the published weight is CORRECT (%u): nothing to "
                                        "accuse", item.weight);
            }
            return false;
        }
        return true;
    }

    if (reason_out) *reason_out = "unknown data-integrity kind";
    return false;
}

bool MalusRegistry::ValidReport(MalusKind kind, const std::string& node_address, int height,
                                const std::vector<std::string>& blocks,
                                const MalusDataDetail& detail, double psi_prev,
                                std::string* reason_out)
{
    // The CONSENSUS-BEHAVIOURAL kinds are only decidable where private sortition governs
    // the height: both proofs rest on the block-carried VRF reveal over the beacon seed,
    // which exists nowhere else.
    //
    // The DATA-INTEGRITY kinds have no such precondition — their evidence is a publishing
    // transaction, whose signature and payload are decodable at any height — so they are
    // routed before this gate. They carry their own preconditions instead
    // (ValidDataIntegrityReport).
    if (mc_MalusKindIsDataIntegrity(kind))
    {
        return ValidDataIntegrityReport(kind, node_address, height, blocks, detail,
                                        reason_out);
    }

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

        // Same delay law, and the same feedback, the block validator enforced: Phi is
        // derived over the accused block's PARENT, exactly as WPoASortitionVerifyProposer
        // does, so a report is judged against the bar that actually applied.
        double score = PrivateSortition::ScoreFromVRFOutput(a.reveal.data(), w, g_dumping_function);
        double delay = PrivateSortition::MiningDelay(score, weff,
                                                    (double)Params().TargetSpacing(),
                                                    g_wpoa_sortition_delta,
                                                    g_wpoa_sortition_lambda,
                                                    WPoASortitionFeedback(a.pindex->pprev));

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

                // Pass r.detail, not a default: the data-integrity kinds carry their
                // claim in it, and validating them with an empty detail would silently
                // reject every such report here even though it was accepted at publish
                // time — the accumulator would stay at 0 and the malus would never bite.
                if (!ValidReport(r.kind, r.address, r.height, r.blocks, r.detail,
                                 psi_prev, NULL))
                {
                    continue;   // false, malformed or unverifiable here: discarded
                }
                // WPoAMalusScores(), not the two-score form: that one scores the
                // data-integrity kinds 0, so using it here would validate such a report
                // and then add nothing — the malus would never bite. All four scores come
                // from one place for exactly this reason.
                points[r.address] += MalusAccumulator::Points(r.kind, WPoAMalusScores());
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
                                         int height, const std::vector<std::string>& blocks,
                                         const MalusDataDetail& detail)
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
    if (!ValidReport(kind, node_address, height, blocks, detail, psi_prev, &reason))
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

    // The data-integrity kinds carry the fields that make the accusation self-describing:
    // a third party can see what was alleged, and re-derive it, by reading the one
    // referenced transaction rather than searching for it.
    if (kind == MALUS_SELF_WRITE)
    {
        record.push_back(Pair(MC_WPOA_MALUS_FIELD_STREAM, detail.stream));
        record.push_back(Pair(MC_WPOA_MALUS_FIELD_DECLARED_ADDR, detail.declared_address));
    }
    else if (kind == MALUS_INVALID_WEIGHT)
    {
        record.push_back(Pair(MC_WPOA_MALUS_FIELD_EPOCH, (int64_t)detail.epoch));
        record.push_back(Pair(MC_WPOA_MALUS_FIELD_DECLARED, (int64_t)detail.declared));
        record.push_back(Pair(MC_WPOA_MALUS_FIELD_RECOMPUTED, (int64_t)detail.recomputed));
    }

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
