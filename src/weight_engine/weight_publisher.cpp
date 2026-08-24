// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W3: WeightPublisher + admin RPCs implementation.
// See weight_publisher.h. Publication reuses the in-process publishfrom handler and
// the W1 parsers for round-trip validation; permission checks reuse the native
// MultiChain permission DB (mc_gState->m_Permissions), exactly as the permission /
// stream RPCs do.

#include "weight_engine/weight_publisher.h"

#include "weight_engine/weight_streams.h"   // stream + field names
#include "weight_engine/weight_records.h"   // W1 round-trip parsers
#include "weight_engine/weight_engine.h"    // HeightToEpoch

#include "rpc/rpcwallet.h"      // publishfrom (via rpcserver.h), wallet, multichain, mc_gState
#include "structs/base58.h"     // CBitcoinAddress
#include "script/standard.h"    // CTxDestination
#include "core/init.h"          // pwalletMain
#include "core/main.h"          // chainActive, cs_main
#include "utils/util.h"         // strprintf, LogPrintf
#include "utils/utiltime.h"     // GetTime

#include <cstdlib>
#include <stdexcept>
#include <set>
#include <boost/variant/get.hpp>

using namespace std;
using namespace json_spirit;

// ---------------------------------------------------------------------------
// Local helpers (file scope)
// ---------------------------------------------------------------------------

// Accept an int, real, or numeric-string JSON value as a double. (multichain-cli
// sends arguments for RPCs without a numeric-conversion entry as strings, so a
// string like "15" must be accepted; a raw JSON-RPC client may send a real number.)
static double RecordDouble(const Value& v, const char* field)
{
    if (v.type() == int_type)  return (double)v.get_int64();
    if (v.type() == real_type) return v.get_real();
    if (v.type() == str_type)
    {
        const std::string s = v.get_str();
        if (!s.empty())
        {
            char* end = NULL;
            double d = strtod(s.c_str(), &end);
            if (end != s.c_str() && *end == '\0')
            {
                return d;
            }
        }
    }
    throw JSONRPCError(RPC_INVALID_PARAMETER, string(field) + " must be a number");
}

// Resolve this node's own address (mine -> connect -> default key, as the wPoA
// registry does). No permission requirement: this is the node's cryptographic
// identity, and it is the address the publishing transaction will be signed with.
static CKeyID ResolveLocalNodeKeyID()
{
    if (pwalletMain == NULL)
    {
        throw JSONRPCError(RPC_WALLET_ERROR, "Wallet not available");
    }

    CPubKey pkey;
    {
        LOCK(pwalletMain->cs_wallet);
        if (!pwalletMain->GetKeyFromAddressBook(pkey, MC_PTP_MINE))
        {
            if (!pwalletMain->GetKeyFromAddressBook(pkey, MC_PTP_CONNECT))
            {
                pkey = pwalletMain->vchDefaultKey;
            }
        }
    }
    if (!pkey.IsValid())
    {
        throw JSONRPCError(RPC_WALLET_ERROR, "No valid local node address");
    }
    return pkey.GetID();
}

// This node's own address, with no permission requirement. Used by the SELF-WRITE
// path: the caller can only ever publish a record about itself, so no privilege is
// needed beyond `<stream>.write` (checked on-chain in WeightPublishTo).
static std::string ResolveLocalNodeAddress()
{
    return CBitcoinAddress(ResolveLocalNodeKeyID()).ToString();
}

// This node's own address, additionally required to be a GLOBAL administrator.
// Throws RPC_INSUFFICIENT_PERMISSIONS if not. This is the policy gate for the
// streams that carry an EXTERNAL attestation — a claim about somebody else that no
// third party can verify — where restricting who may assert it is the only defence.
// (The on-chain gate is the closed stream's write permission, checked in
// WeightPublishTo.)
static std::string ResolveLocalAdminAddress()
{
    CKeyID keyID = ResolveLocalNodeKeyID();
    if (mc_gState->m_Permissions->CanAdmin(NULL, (unsigned char*)&keyID) == 0)
    {
        throw JSONRPCError(RPC_INSUFFICIENT_PERMISSIONS,
                           "This node's address is not an administrator; "
                           "ESG / reconciliation are admin-only");
    }
    return CBitcoinAddress(keyID).ToString();
}

// Publish a (pre-validated) record to a CLOSED WeightEngine stream. Requires the
// stream to already exist (created by WeightStreamReader::EnsureInputStreams) and
// the acting address to hold write permission on it; publishes FROM that address.
static std::string WeightPublishTo(const std::string& from_address, const char* streamName,
                                   const std::string& key, const Object& data_obj)
{
    mc_EntityDetails entity;
    if (mc_gState == NULL || mc_gState->m_Assets == NULL ||
        mc_gState->m_Assets->FindEntityByName(&entity, streamName) == 0 ||
        entity.GetEntityType() != MC_ENT_TYPE_STREAM)
    {
        throw JSONRPCError(RPC_ENTITY_NOT_FOUND,
                           string("Stream '") + streamName + "' does not exist yet "
                           "(enable the weight engine so it is created, then retry)");
    }

    CBitcoinAddress addr(from_address);
    CTxDestination dest = addr.Get();
    CKeyID* keyID = boost::get<CKeyID>(&dest);
    if (keyID == NULL)
    {
        throw JSONRPCError(RPC_INVALID_ADDRESS_OR_KEY, "Publisher address is not a pay-to-key address");
    }
    if (mc_gState->m_Permissions->CanWrite(entity.GetTxID(), (unsigned char*)keyID) == 0)
    {
        throw JSONRPCError(RPC_INSUFFICIENT_PERMISSIONS,
                           string("Address ") + from_address + " lacks write permission on '" +
                           streamName + "'. Grant it, e.g.:  grant " + from_address + " " +
                           streamName + ".write");
    }

    // publishfrom [from-address, stream, key, {"json":{...}}]
    Array params;
    params.push_back(from_address);
    params.push_back(string(streamName));
    params.push_back(key);
    params.push_back(Value(data_obj));
    Value result = publishfrom(params, false);
    return result.get_str();
}

// ---------------------------------------------------------------------------
// WeightPublisher — build record, ROUND-TRIP validate, then publish
// ---------------------------------------------------------------------------

std::string WeightPublisher::PublishEsg(const std::string& from_address,
                                        const std::string& node_address, double esg)
{
    if (node_address.empty())
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "node_address must not be empty");
    }

    Object record;
    record.push_back(Pair(MC_WEIGHT_FIELD_NODE_ADDR, node_address));
    record.push_back(Pair(MC_WEIGHT_FIELD_ESG, esg));
    Object data_obj;
    data_obj.push_back(Pair("json", record));

    // Round-trip through the reader's own parser: reject anything it would not read.
    std::string a;
    double s = 0.0;
    if (!mc_ParseEsgRecordJson(Value(data_obj), a, s))
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER,
                           "ESG record rejected by schema (score must be > 0, address non-empty)");
    }

    return WeightPublishTo(from_address, MC_WEIGHT_ESG_STREAM_NAME, node_address, data_obj);
}

// SELF-WRITE. `node_address` is not a free parameter: it MUST be the publishing
// address, because the reader discards any record whose signer differs from its
// declared node_address (weight_reader.h ReadMembership). Enforcing the equality
// here too means a caller gets a clear RPC error instead of silently paying for a
// transaction its own peers will throw away.
std::string WeightPublisher::PublishMembership(const std::string& from_address,
                                              const std::string& node_address,
                                              const std::string& miner_address)
{
    if (node_address.empty() || miner_address.empty())
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "node and miner addresses must not be empty");
    }
    if (node_address != from_address)
    {
        throw JSONRPCError(RPC_INSUFFICIENT_PERMISSIONS,
                           "membership is SELF-ATTESTED: a node may only declare its own "
                           "cluster. The record must be published by " + node_address +
                           " itself, not by " + from_address + " on its behalf "
                           "(the reader would discard it).");
    }

    Object record;
    record.push_back(Pair(MC_WEIGHT_FIELD_NODE_ADDR, node_address));
    record.push_back(Pair(MC_WEIGHT_FIELD_MINER_ADDR, miner_address));
    record.push_back(Pair(MC_WEIGHT_FIELD_TIMESTAMP, (int64_t)GetTime()));
    Object data_obj;
    data_obj.push_back(Pair("json", record));

    // Round-trip through the reader's own parser: reject anything it would not read.
    std::string n;
    std::string m;
    uint32_t ts = 0;
    if (!mc_ParseMembershipRecordJson(Value(data_obj), n, m, ts) ||
        n != node_address || m != miner_address)
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "membership record rejected by schema");
    }

    // Item key = node_address (the declaring node), so all of a node's successive
    // declarations share one key and last-confirmed-wins picks its current cluster.
    return WeightPublishTo(from_address, MC_WEIGHT_MEMBERSHIP_STREAM_NAME, node_address, data_obj);
}

std::string WeightPublisher::PublishReconciliation(const std::string& from_address,
                                                   const std::string& miner, double reconciled,
                                                   uint32_t epoch)
{
    if (miner.empty())
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "miner address must not be empty");
    }

    Object record;
    record.push_back(Pair(MC_WEIGHT_FIELD_NODE_ADDR, miner));
    record.push_back(Pair(MC_WEIGHT_FIELD_RECONCILED, reconciled));
    record.push_back(Pair(MC_WEIGHT_FIELD_EPOCH, (int64_t)epoch));
    Object data_obj;
    data_obj.push_back(Pair("json", record));

    std::string m;
    double r = 0.0;
    uint32_t e = 0;
    if (!mc_ParseReconciliationRecordJson(Value(data_obj), m, r, e))
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER,
                           "reconciliation record rejected by schema (reconciled >= 0, epoch >= 1)");
    }

    return WeightPublishTo(from_address, MC_WEIGHT_RECONCILIATION_STREAM_NAME, miner, data_obj);
}

// ---------------------------------------------------------------------------
// Admin RPCs
// ---------------------------------------------------------------------------

Value weightsetesg(const Array& params, bool fHelp)
{
    if (fHelp || params.size() != 2)
    {
        throw runtime_error(
            "weightsetesg \"node_address\" score\n"
            "\nAdmin-only. Publishes a certified ESG score for a node to the\n"
            "weight-engine-esg stream (round-trip validated before publishing).\n"
            "\nArguments:\n"
            "1. \"node_address\"  (string, required) company or miner address\n"
            "2. score            (numeric, required) certified ESG score, strictly > 0\n"
            "\nResult:\n"
            "\"txid\"  (string) the publish transaction id\n");
    }

    std::string from = ResolveLocalAdminAddress();
    std::string node_address = params[0].get_str();
    double esg = RecordDouble(params[1], "score");
    return WeightPublisher::PublishEsg(from, node_address, esg);
}

// PUBLIC (not admin). Any node may call it, and it can only ever publish a record
// about the CALLING node itself — there is deliberately no parameter for "whose"
// membership to declare. This replaces the former admin-proxy `weightsetmembership`,
// which is gone rather than deprecated: under the self-attestation rule a record
// published by an admin on a third party's behalf is discarded by every reader, so
// keeping that RPC would only offer a way to pay for a transaction with no effect.
Value weightregistermembership(const Array& params, bool fHelp)
{
    if (fHelp || params.size() != 1)
    {
        throw runtime_error(
            "weightregistermembership \"miner_address\"\n"
            "\nDeclares THIS node's membership of a miner's cluster on the\n"
            "weight-engine-membership stream, signed by this node's own address.\n"
            "\nOpen to every node: joining a cluster is a voluntary, autonomous choice,\n"
            "and the record is self-attested — the reader accepts it only because the\n"
            "signer matches the declared node_address, so nobody can declare membership\n"
            "on another node's behalf. Call it again with a different miner to change\n"
            "cluster: the latest confirmed declaration wins. A miner calls it with its\n"
            "OWN address to register itself as a cluster head.\n"
            "\nRequires: weight-engine-membership.write on this node's address.\n"
            "\nArguments:\n"
            "1. \"miner_address\"  (string, required) the cluster to join\n"
            "\nResult:\n"
            "\"txid\"  (string) the publish transaction id\n");
    }

    std::string own = ResolveLocalNodeAddress();
    std::string miner = params[0].get_str();
    return WeightPublisher::PublishMembership(own, own, miner);
}

Value weightsetreconciliation(const Array& params, bool fHelp)
{
    if (fHelp || params.size() != 3)
    {
        throw runtime_error(
            "weightsetreconciliation \"miner_address\" reconciled epoch\n"
            "\nAdmin-only. Publishes the reconciled allocation R_k for a miner in a\n"
            "given epoch to the weight-engine-reconciliation stream.\n"
            "\nArguments:\n"
            "1. \"miner_address\"  (string, required) the cluster's miner address\n"
            "2. reconciled         (numeric, required) reconciled amount, >= 0\n"
            "3. epoch              (numeric, required) 1-based epoch, <= current epoch\n"
            "\nResult:\n"
            "\"txid\"  (string) the publish transaction id\n");
    }

    std::string from = ResolveLocalAdminAddress();
    std::string miner = params[0].get_str();
    double reconciled = RecordDouble(params[1], "reconciled");

    int64_t epoch_i = 0;
    if (params[2].type() == int_type)
    {
        epoch_i = params[2].get_int64();
    }
    else if (params[2].type() == str_type)   // CLI sends it as a string
    {
        const std::string es = params[2].get_str();
        char* end = NULL;
        long long v = strtoll(es.c_str(), &end, 10);
        if (es.empty() || end == es.c_str() || *end != '\0')
        {
            throw JSONRPCError(RPC_INVALID_PARAMETER, "epoch must be an integer");
        }
        epoch_i = (int64_t)v;
    }
    else
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "epoch must be an integer");
    }
    if (epoch_i < 1 || epoch_i > (int64_t)UINT32_MAX)
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "epoch must be an integer in [1, 4294967295]");
    }

    // Bound to the current epoch: reject attestations for a future epoch. Compared as
    // int64 (no truncating uint32 cast) so a huge value cannot wrap past the bound.
    // This is a publish-time (mempool) guard, not a consensus rule — the reader only
    // ever consumes closed, buried epochs.
    int height = 0;
    {
        LOCK(cs_main);
        if (chainActive.Tip() != NULL)
        {
            height = chainActive.Height();
        }
    }
    uint32_t current_epoch = HeightToEpoch(height);
    if (epoch_i > (int64_t)current_epoch)
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER,
                           strprintf("epoch %lld is in the future (current epoch is %u)",
                                     (long long)epoch_i, current_epoch));
    }

    return WeightPublisher::PublishReconciliation(from, miner, reconciled, (uint32_t)epoch_i);
}
