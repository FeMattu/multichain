// Copyright (c) 2010 Satoshi Nakamoto
// Copyright (c) 2014-2016 The Bitcoin Core developers
// Original code was distributed under the MIT software license.
// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// WeightEngine RPC surface — the "weight" command category.
// ---------------------------------------------------------------------------
// The two published inputs of the weight pipeline, and the verification of its
// output:
//
//   weightsetesg              weight-engine-esg          write, CERTIFICATION AUTHORITY
//   weightregistermembership  weight-engine-membership   write, PUBLIC (self-attested)
//   weightverifyweights       wpoa-weights               read, open to anyone
//
// No weight RPC requires global admin. ESG needs the delegated Certification
// Authority role (an unverifiable attestation about a third party, so the writer is
// restricted); membership needs no privilege at all, being self-attested and able to
// describe only the calling node itself; tau and R have no write path, both being
// derived. See weight_engine/weight_publisher.h and weight_authorization.h.
//
// These are handlers only: authorization, round-trip validation and publication live
// in WeightPublisher, and the verdicts weightverifyweights reports are computed by the
// weight-engine thread (weight_engine/weight_verifier.h) — this file marshals
// parameters and shapes the JSON.


#include "rpc/rpcwallet.h"

#include "weight_engine/weight_publisher.h"      // WeightPublisher + the address resolvers
#include "weight_engine/weight_authorization.h"  // MC_WEIGHT_CA_PERMISSION_NAME (help text)
#include "weight_engine/weight_verifier.h"       // the cached verdicts
#include "weight_engine/weight_engine.h"         // g_weight_engine_enabled

#include <cstdlib>

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

// ---------------------------------------------------------------------------
// Published inputs
// ---------------------------------------------------------------------------

Value weightsetesg(const Array& params, bool fHelp)
{
    if (fHelp || params.size() != 2)
    {
        throw runtime_error(
            "weightsetesg \"node_address\" score\n"
            "\nCertification-Authority only. Publishes a certified ESG score for a node\n"
            "to the weight-engine-esg stream (round-trip validated before publishing).\n"
            "\nAn ESG score is an attestation of TRUST: no peer can verify it\n"
            "cryptographically, so the only defence is to restrict who may assert it.\n"
            "The writer must therefore hold the Certification Authority role, which the\n"
            "global administrator delegates per address and may revoke:\n"
            "\n  grant  <address> " MC_WEIGHT_CA_PERMISSION_NAME
            "     # confer CA status (requires admin)\n"
            "  revoke <address> " MC_WEIGHT_CA_PERMISSION_NAME
            "     # withdraw it\n"
            "\nBeing a global administrator is NOT sufficient: the administrator confers\n"
            "the role, it does not hold it automatically. This keeps 'who administers the\n"
            "network' distinguishable on chain from 'who certifies ESG scores'.\n"
            "\nAlso requires: weight-engine-esg.write on this node's address.\n"
            "\nArguments:\n"
            "1. \"node_address\"  (string, required) company or miner address\n"
            "2. score            (numeric, required) certified ESG score, strictly > 0\n"
            "\nResult:\n"
            "\"txid\"  (string) the publish transaction id\n");
    }

    std::string from = WeightPublisher::ResolveLocalCertificationAuthorityAddress();
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

    std::string own = WeightPublisher::ResolveLocalNodeAddress();
    std::string miner = params[0].get_str();
    return WeightPublisher::PublishMembership(own, own, miner);
}

// ---------------------------------------------------------------------------
// Verification of the published output
// ---------------------------------------------------------------------------

Value weightverifyweights(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 0)
    {
        throw runtime_error(
            "weightverifyweights\n"
            "\nReports this node's INDEPENDENT verification of the weights published on\n"
            "wpoa-weights, for the most recent epoch it has verified.\n"
            "\nEvery input of the weight pipeline is public and deterministic — activity\n"
            "and reconciliation are chain-derived, membership and ESG are published — so\n"
            "any node can re-run the identical pipeline and check each published value.\n"
            "A value that does not match the recomputation is provably wrong and is\n"
            "dropped from the weight map the election consumes.\n"
            "\nESG is the one input that cannot be recomputed: it is an attestation, so\n"
            "this check verifies that a publisher applied the pipeline honestly to the\n"
            "published inputs, not that the ESG scores themselves are truthful. That\n"
            "rests on the Certification Authority role instead.\n"
            "\nVerification runs once per buried epoch in the weight-engine thread, so an\n"
            "epoch of 0 simply means it has not run yet on this node.\n"
            "\nResult:\n"
            "{\n"
            "  \"epoch\": n,               (numeric) the epoch verified, 0 if none yet\n"
            "  \"verified\": true|false,   (boolean) whether the recomputation succeeded\n"
            "  \"records\": n,             (numeric) published records examined\n"
            "  \"invalid\": n,             (numeric) records that failed verification\n"
            "  \"entries\": [\n"
            "    {\n"
            "      \"address\": \"...\",     (string)  the cluster the record is about\n"
            "      \"published\": n,       (numeric) the value found on chain\n"
            "      \"published_epoch\": n, (numeric) the epoch it was published FOR, 0 if unstated\n"
            "      \"recomputed\": n,      (numeric) the value this node derived\n"
            "      \"verdict\": \"...\"      (string)  ok | mismatch | not-a-cluster |\n"
            "                                       other-epoch | unverified\n"
            "    }, ...\n"
            "  ]\n"
            "}\n");
    }

    if (!g_weight_engine_enabled)
    {
        throw JSONRPCError(RPC_NOT_SUPPORTED,
                           "The weight engine is disabled on this node, so there is no "
                           "pipeline to recompute and nothing to verify. Published "
                           "weights are accepted on the self-publication rule alone "
                           "(signer == node_address). Enable -enableweightengine to "
                           "verify values as well.");
    }

    const uint32_t epoch = WeightEngineLastVerifiedEpoch();
    std::map<std::string, WeightVerificationEntry> verdicts = WeightEngineGetVerdicts(epoch);

    // "verified" is false when nothing has been verified yet AND when the last run
    // could not recompute — in the latter case every entry is UNVERIFIED, so the two
    // are distinguishable from `records`/`entries` without a third state.
    bool any_decided = false;
    size_t invalid = 0;
    Array entries;
    for (std::map<std::string, WeightVerificationEntry>::const_iterator it = verdicts.begin();
         it != verdicts.end(); ++it)
    {
        if (it->second.verdict != MC_WEIGHT_VERDICT_UNVERIFIED)
        {
            any_decided = true;
        }
        if (mc_WeightVerdictIsInvalid(it->second.verdict))
        {
            invalid++;
        }

        Object e;
        e.push_back(Pair("address", it->first));
        e.push_back(Pair("published", (int64_t)it->second.published));
        e.push_back(Pair("published_epoch", (int64_t)it->second.published_epoch));
        e.push_back(Pair("recomputed", (int64_t)it->second.recomputed));
        e.push_back(Pair("verdict", string(mc_WeightVerdictToString(it->second.verdict))));
        entries.push_back(e);
    }

    Object out;
    out.push_back(Pair("epoch", (int64_t)epoch));
    out.push_back(Pair("verified", any_decided));
    out.push_back(Pair("records", (int64_t)verdicts.size()));
    out.push_back(Pair("invalid", (int64_t)invalid));
    out.push_back(Pair("entries", entries));
    return out;
}
