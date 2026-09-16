// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W3: WeightPublisher, the validated write path
// behind the two input-stream RPCs (which live in rpc/rpcweightengine.cpp).
// See weight_publisher.h. Publication reuses the in-process publishfrom handler and
// the W1 parsers for round-trip validation; permission checks reuse the native
// MultiChain permission DB (mc_gState->m_Permissions), exactly as the permission /
// stream RPCs do.

#include "weight_engine/weight_publisher.h"

#include "weight_engine/weight_streams.h"       // stream + field names
#include "weight_engine/weight_records.h"       // W1 round-trip parsers
#include "weight_engine/weight_authorization.h" // W1 pure authorization policy
#include "weight_engine/weight_engine.h"        // g_weight_treasury_address (log text)

#include "rpc/rpcwallet.h"      // publishfrom (via rpcserver.h), wallet, multichain, mc_gState
#include "structs/base58.h"     // CBitcoinAddress
#include "script/standard.h"    // CTxDestination
#include "core/init.h"          // pwalletMain
#include "utils/util.h"         // strprintf, LogPrintf
#include "utils/utiltime.h"     // GetTime

#include <stdexcept>
#include <set>
#include <boost/variant/get.hpp>

using namespace std;
using namespace json_spirit;

// ---------------------------------------------------------------------------
// Local helpers, and the caller-address resolution the RPC handlers go through
// ---------------------------------------------------------------------------

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
std::string WeightPublisher::ResolveLocalNodeAddress()
{
    return CBitcoinAddress(ResolveLocalNodeKeyID()).ToString();
}

// NOTE: there is deliberately no ResolveLocalAdminAddress here any more. Its only
// caller was the reconciliation RPC, and R_k is now DERIVED from the epoch's confirmed
// blocks rather than attested by an administrator — so no write path in this file
// requires global admin. ESG requires the Certification Authority role instead (below),
// and membership requires no privilege at all. See
// wpoa/docs/adr/reconciliation-onchain.md.

// The permission BIT behind the CA role's wire name, resolved through MultiChain's
// OWN name->bit parser. Deriving it rather than restating it keeps
// MC_WEIGHT_CA_PERMISSION_NAME the single source of truth: the name printed in an
// operator-facing error and the bit actually queried can never drift apart, and moving
// the role to another slot stays a one-line change. Returns 0 for an unrecognised name
// (or before the permission DB exists), which the caller treats as "not a CA" — fail
// closed.
static uint32_t WeightCaPermissionBit()
{
    if (mc_gState == NULL || mc_gState->m_Permissions == NULL)
    {
        return 0;
    }
    return mc_gState->m_Permissions->GetPermissionType(MC_WEIGHT_CA_PERMISSION_NAME,
                                                       MC_PTP_ALL);
}

// Whether `keyID` holds the Certification Authority role on chain.
//
// The role is carried by one of MultiChain's six FIXED custom permission slots —
// there is no arbitrary `custom.<name>` — and it must be a HIGH slot, because
// mc_Permissions::IsActivateEnough returns 0 for the high slots: granting one
// requires `admin`, not merely `activate`, which is exactly the requirement that only
// the administrator may confer CA status. See weight_authorization.h.
//
// CanCustom is a plain permission lookup with no spacing/diversity logic, the same
// call the miner-permission check on wPoA heights uses.
static bool IsCertificationAuthority(const CKeyID& keyID)
{
    uint32_t bit = WeightCaPermissionBit();
    if (bit == 0)
    {
        return false;   // unknown permission name / no permission DB -> fail closed
    }
    return mc_gState->m_Permissions->CanCustom(NULL, (unsigned char*)&keyID, bit) != 0;
}

// Whether this chain's protocol version provides custom permissions at all. When it
// does not, the CA role cannot be expressed on chain and ESG publication FAILS CLOSED
// (weight_authorization.h) rather than silently reverting to an admin check.
static bool ChainSupportsCustomPermissions()
{
    if (mc_gState == NULL || mc_gState->m_Features == NULL)
    {
        return false;
    }
    return mc_gState->m_Features->CustomPermissions() != 0;
}

// This node's own address, required to hold the Certification Authority role.
//
// Deliberately NOT ResolveLocalAdminAddress: administering the chain and certifying
// ESG scores are separate competences. An administrator that also wants to certify
// grants itself the CA permission explicitly, which keeps the two roles
// distinguishable on chain.
//
// The write-permission half of the decision is left to WeightPublishTo, which owns
// the per-stream CanWrite check for every stream; passing `true` here reflects that
// division of labour rather than skipping the check.
std::string WeightPublisher::ResolveLocalCertificationAuthorityAddress()
{
    CKeyID keyID = ResolveLocalNodeKeyID();

    WeightEsgWriteDecision d = mc_WeightEsgWriteDecision(
        IsCertificationAuthority(keyID),
        true,                                  // stream write: checked in WeightPublishTo
        ChainSupportsCustomPermissions());

    if (d != MC_WEIGHT_ESG_WRITE_OK)
    {
        throw JSONRPCError(RPC_INSUFFICIENT_PERMISSIONS,
                           std::string("ESG publication refused: ") +
                           mc_WeightEsgWriteDecisionText(d));
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
