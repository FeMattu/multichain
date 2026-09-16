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
#include "weight_engine/weight_engine.h"         // the pipeline core + epoch detail
#include "weight_engine/weight_reader.h"         // WeightStreamReader
#include "weight_engine/weight_streams.h"        // stream names, stability margin
#include "core/init.h"                           // pwalletTxsMain

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

// ---------------------------------------------------------------------------
// Epoch audit: every intermediate quantity of the weight pipeline
// ---------------------------------------------------------------------------
//
// READ-ONLY INSPECTION OF THE PIPELINE. One RPC family per thesis definition, so a
// published weight can be checked a step at a time instead of being taken whole:
//
//   c_i^(e)       = ESG_i * tau_i^(e) / kappa                  Def. contributo-pesato
//   W_k^(e)       = ESG_Mk * ( tau_Mk^(e) + sum_i c_i^(e) )    Def. peso-grezzo
//   R_k^(e)       = paid to the treasury by the miner          Def. restituzione
//   g_k^(e)       = Entrate - Uscite (R_k excluded)            Def. guadagno
//   saldo_k^(e)   = saldo_k^(e-1) + g_k^(e)                    Def. saldo
//   phi_k^(e)     = R_k^(e) / saldo_k^(e)                      Def. tasso-restituzione
//   w_k^(e)       = W_k^(e) * [phi_k^(e-1)*lambda_w + 1-lambda_w]  Def. peso-finale
//
// Every one of these is read off WeightEngineComputeEpochDetail, the SAME fold the
// publishing thread and the verifier run — this file computes none of them itself, so
// an audit cannot disagree with what the node published.
//
// FINALITY. An epoch is only computable once buried (its last block at least
// MC_WEIGHT_DEFAULT_STABILITY_MARGIN below the tip): before that a shallow reorg could
// change the answer, so these RPCs refuse rather than return a value that may move.

/** Accept an int or a numeric-string JSON value as an epoch (the CLI sends
 *  unconverted arguments as strings). */
static int64_t RpcEpochInteger(const Value& v)
{
    if (v.type() == int_type)
    {
        return v.get_int64();
    }
    if (v.type() == str_type)
    {
        const std::string s = v.get_str();
        char* end = NULL;
        long long parsed = strtoll(s.c_str(), &end, 10);
        if (!s.empty() && end != s.c_str() && *end == '\0')
        {
            return (int64_t)parsed;
        }
    }
    throw JSONRPCError(RPC_INVALID_PARAMETER, "epoch must be an integer");
}

/** The engine must be running for any of this to be defined. */
static void RpcRequireWeightEngine()
{
    if (!g_weight_engine_enabled)
    {
        throw JSONRPCError(RPC_NOT_SUPPORTED,
                           "The weight engine is disabled on this node (-enableweightengine), "
                           "so there is no pipeline to recompute and nothing to inspect.");
    }
    if (pwalletTxsMain == NULL)
    {
        throw JSONRPCError(RPC_WALLET_ERROR, "Wallet not available");
    }
}

/**
 * The epoch to audit: the optional argument at `idx`, defaulting to the newest fully
 * buried one. An epoch past that bound is REFUSED — computing it would mean reading
 * blocks a shallow reorg can still replace, so the answer would not be the one the
 * network will settle on.
 */
static uint32_t RpcResolveEpoch(const Array& params, size_t idx)
{
    const uint32_t buried = WeightEngineLastBuriedEpoch();
    if (buried < 1)
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER,
                           "epoch not yet finalized: no epoch is fully buried yet "
                           "(the chain is shorter than one epoch plus the stability margin)");
    }

    if (params.size() <= idx || params[idx].type() == null_type)
    {
        return buried;
    }

    int64_t epoch = RpcEpochInteger(params[idx]);
    if (epoch < 1)
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "epoch must be >= 1");
    }
    if (epoch > (int64_t)buried)
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER,
                           strprintf("epoch not yet finalized: epoch %d is not buried "
                                     "(newest buried epoch is %u)",
                                     (int)epoch, buried));
    }
    return (uint32_t)epoch;
}

/** The whole epoch, folded once from epoch 1 — the single read every handler shares. */
static void RpcEpochDetail(uint32_t epoch,
                           std::map<std::string, WeightEpochCluster>& out)
{
    WeightStreamReader reader(pwalletTxsMain);
    if (!WeightEngineComputeEpochDetail(reader, epoch, out))
    {
        throw JSONRPCError(RPC_MISC_ERROR,
                           strprintf("Epoch %u is not computable on this node: the input "
                                     "streams are unreadable (not subscribed), or the "
                                     "epoch's block/undo data is unavailable (pruned node)",
                                     epoch));
    }
}

/** This node's own address — the company/miner identity the pipeline keys on. */
static std::string RpcLocalWeightAddress()
{
    return WeightPublisher::ResolveLocalNodeAddress();
}

static const WeightEpochCluster* RpcFindCluster(
    const std::map<std::string, WeightEpochCluster>& detail, const std::string& miner)
{
    std::map<std::string, WeightEpochCluster>::const_iterator it = detail.find(miner);
    return (it != detail.end()) ? &it->second : NULL;
}

static void RpcRequireCluster(const WeightEpochCluster* c, const std::string& miner,
                              uint32_t epoch)
{
    if (c == NULL)
    {
        throw JSONRPCError(RPC_INVALID_ADDRESS_OR_KEY,
                           strprintf("%s heads no cluster in epoch %u: no node has declared "
                                     "membership of it on " MC_WEIGHT_MEMBERSHIP_STREAM_NAME,
                                     miner.c_str(), epoch));
    }
}

// --- 1. company contribution  c_i = ESG_i * tau_i / kappa ----------------

/** One company's contribution, plus the two inputs it is the product of. */
static Object RpcContributionEntry(const std::string& address, const std::string& cluster,
                                   double esg, uint32_t tau)
{
    Object o;
    o.push_back(Pair("address", address));
    o.push_back(Pair("cluster", cluster));
    o.push_back(Pair("esg_score", esg));
    o.push_back(Pair("activity", (int64_t)tau));
    o.push_back(Pair("kappa", g_weight_kappa));
    o.push_back(Pair("contribution",
                     WeightEngine::CompanyContribution(esg, tau, g_weight_kappa)));
    return o;
}

/** Locate one company across the epoch's clusters. Membership is last-confirmed-wins
 *  per declaring node, so a node belongs to at most one cluster. */
static bool RpcFindCompany(const std::map<std::string, WeightEpochCluster>& detail,
                           const std::string& address, std::string& cluster_out,
                           double& esg_out, uint32_t& tau_out)
{
    for (std::map<std::string, WeightEpochCluster>::const_iterator ci = detail.begin();
         ci != detail.end(); ++ci)
    {
        const std::vector<WeightEngine::Company>& companies = ci->second.input.companies;
        for (size_t i = 0; i < companies.size(); i++)
        {
            if (companies[i].address == address)
            {
                cluster_out = ci->first;
                esg_out     = companies[i].esg;
                tau_out     = companies[i].tau;
                return true;
            }
        }
    }
    return false;
}

static Object RpcContributionFor(const std::map<std::string, WeightEpochCluster>& detail,
                                 const std::string& address, uint32_t epoch)
{
    std::string cluster;
    double esg = 0.0;
    uint32_t tau = 0;

    Object obj;
    if (RpcFindCompany(detail, address, cluster, esg, tau))
    {
        obj = RpcContributionEntry(address, cluster, esg, tau);
        obj.push_back(Pair("member", true));
    }
    else
    {
        // Not a declared member of any cluster. A legitimate state — an address that
        // never published on the membership stream simply contributes to nobody — so
        // it is reported as a zero contribution rather than as a lookup error. Note a
        // MINER's own activity does not pass through c_i at all: it enters W_k
        // directly as tau_Mk (Def. peso-grezzo), which weightgetnodeclusterweight shows.
        obj = RpcContributionEntry(address, "", 0.0, 0);
        obj.push_back(Pair("member", false));
        obj.push_back(Pair("cluster_head", RpcFindCluster(detail, address) != NULL));
    }
    obj.push_back(Pair("epoch", (int64_t)epoch));
    return obj;
}

Value weightgetlocalcontribution(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const std::string address = RpcLocalWeightAddress();
    const uint32_t epoch = RpcResolveEpoch(params, 0);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);
    return RpcContributionFor(detail, address, epoch);
}

Value weightgetnodecontribution(const Array& params, bool fHelp)
{
    if (fHelp || params.size() < 1 || params.size() > 2)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const std::string address = params[0].get_str();
    const uint32_t epoch = RpcResolveEpoch(params, 1);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);
    return RpcContributionFor(detail, address, epoch);
}

Value weightlistcontributions(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const uint32_t epoch = RpcResolveEpoch(params, 0);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);

    Object contributions;
    int count = 0;
    for (std::map<std::string, WeightEpochCluster>::const_iterator ci = detail.begin();
         ci != detail.end(); ++ci)
    {
        const std::vector<WeightEngine::Company>& companies = ci->second.input.companies;
        for (size_t i = 0; i < companies.size(); i++)
        {
            contributions.push_back(Pair(companies[i].address,
                                         RpcContributionEntry(companies[i].address, ci->first,
                                                              companies[i].esg,
                                                              companies[i].tau)));
            count++;
        }
    }

    Object obj;
    obj.push_back(Pair("epoch", (int64_t)epoch));
    obj.push_back(Pair("kappa", g_weight_kappa));
    obj.push_back(Pair("companies", count));
    obj.push_back(Pair("contributions", contributions));
    return obj;
}

// --- 2. cluster weight, raw and final ------------------------------------

static Object RpcClusterWeightEntry(const std::string& miner, const WeightEpochCluster& c,
                                    uint32_t epoch)
{
    // Re-summed with WeightEngine::CompanyContribution in the same ascending-address
    // order RawWeight uses, so the printed sum is the one that entered W_k.
    std::vector<std::string> addresses;
    std::map<std::string, const WeightEngine::Company*> by_address;
    for (size_t i = 0; i < c.input.companies.size(); i++)
    {
        by_address[c.input.companies[i].address] = &c.input.companies[i];
    }
    double sum_c = 0.0;
    for (std::map<std::string, const WeightEngine::Company*>::const_iterator it = by_address.begin();
         it != by_address.end(); ++it)
    {
        sum_c += WeightEngine::CompanyContribution(it->second->esg, it->second->tau,
                                                   g_weight_kappa);
    }

    Object o;
    o.push_back(Pair("miner", miner));
    o.push_back(Pair("epoch", (int64_t)epoch));
    o.push_back(Pair("miner_esg_score", c.input.esg_miner));
    o.push_back(Pair("miner_activity", (int64_t)c.input.tau_miner));
    o.push_back(Pair("companies", (int)c.input.companies.size()));
    o.push_back(Pair("companies_contribution_sum", sum_c));
    o.push_back(Pair("kappa", g_weight_kappa));
    o.push_back(Pair("raw_cluster_weight", c.result.raw_weight));
    // rho_k^{(e-1)}: undefined at epoch 1, where w_k = W_k by construction.
    o.push_back(Pair("previous_epoch_return_rate",
                     c.has_restitution_prev ? Value(c.restitution_prev) : Value::null));
    o.push_back(Pair("lambda_w", g_weight_lambda));
    o.push_back(Pair("final_cluster_weight", c.result.weight));
    o.push_back(Pair("published_weight", (int64_t)c.result.integer_weight));
    return o;
}

Value weightgetlocalclusterweight(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const std::string miner = RpcLocalWeightAddress();
    const uint32_t epoch = RpcResolveEpoch(params, 0);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);
    const WeightEpochCluster* c = RpcFindCluster(detail, miner);
    RpcRequireCluster(c, miner, epoch);
    return RpcClusterWeightEntry(miner, *c, epoch);
}

Value weightgetnodeclusterweight(const Array& params, bool fHelp)
{
    if (fHelp || params.size() < 1 || params.size() > 2)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const std::string miner = params[0].get_str();
    const uint32_t epoch = RpcResolveEpoch(params, 1);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);
    const WeightEpochCluster* c = RpcFindCluster(detail, miner);
    RpcRequireCluster(c, miner, epoch);
    return RpcClusterWeightEntry(miner, *c, epoch);
}

Value weightlistclusterweights(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const uint32_t epoch = RpcResolveEpoch(params, 0);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);

    Object clusters;
    for (std::map<std::string, WeightEpochCluster>::const_iterator it = detail.begin();
         it != detail.end(); ++it)
    {
        clusters.push_back(Pair(it->first, RpcClusterWeightEntry(it->first, it->second, epoch)));
    }

    Object obj;
    obj.push_back(Pair("epoch", (int64_t)epoch));
    obj.push_back(Pair("kappa", g_weight_kappa));
    obj.push_back(Pair("lambda_w", g_weight_lambda));
    obj.push_back(Pair("clusters", (int)detail.size()));
    obj.push_back(Pair("cluster_weights", clusters));
    return obj;
}

// --- 3. restitution R_k --------------------------------------------------

static Object RpcReturnsEntry(const std::string& miner, const WeightEpochCluster& c,
                              uint32_t epoch)
{
    Object o;
    o.push_back(Pair("miner", miner));
    o.push_back(Pair("epoch", (int64_t)epoch));
    o.push_back(Pair("treasury_address", g_weight_treasury_address));
    o.push_back(Pair("returns", c.input.restituted));
    return o;
}

Value weightgetlocalreturns(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const std::string miner = RpcLocalWeightAddress();
    const uint32_t epoch = RpcResolveEpoch(params, 0);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);
    const WeightEpochCluster* c = RpcFindCluster(detail, miner);
    RpcRequireCluster(c, miner, epoch);
    return RpcReturnsEntry(miner, *c, epoch);
}

Value weightgetnodereturns(const Array& params, bool fHelp)
{
    if (fHelp || params.size() < 1 || params.size() > 2)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const std::string miner = params[0].get_str();
    const uint32_t epoch = RpcResolveEpoch(params, 1);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);
    const WeightEpochCluster* c = RpcFindCluster(detail, miner);
    RpcRequireCluster(c, miner, epoch);
    return RpcReturnsEntry(miner, *c, epoch);
}

Value weightlistreturns(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const uint32_t epoch = RpcResolveEpoch(params, 0);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);

    Object returns;
    for (std::map<std::string, WeightEpochCluster>::const_iterator it = detail.begin();
         it != detail.end(); ++it)
    {
        returns.push_back(Pair(it->first, it->second.input.restituted));
    }

    Object obj;
    obj.push_back(Pair("epoch", (int64_t)epoch));
    obj.push_back(Pair("treasury_address", g_weight_treasury_address));
    obj.push_back(Pair("clusters", (int)detail.size()));
    obj.push_back(Pair("returns", returns));
    return obj;
}

// --- 4. gain g_k and restitution rate phi_k ------------------------------

static Object RpcEarningsEntry(const std::string& miner, const WeightEpochCluster& c,
                               uint32_t epoch)
{
    // Uscite EXCLUDING this epoch's own restitution, which is what Def. guadagno
    // subtracts — the reader hands over gross debits with R_k still inside.
    const double r = (c.input.restituted > 0.0) ? c.input.restituted : 0.0;

    Object o;
    o.push_back(Pair("miner", miner));
    o.push_back(Pair("epoch", (int64_t)epoch));
    o.push_back(Pair("income", c.input.credits));
    o.push_back(Pair("expenses_gross", c.input.debits));
    o.push_back(Pair("expenses_excl_return", c.input.debits - r));
    o.push_back(Pair("earnings", c.result.gain));
    o.push_back(Pair("return_amount", c.input.restituted));
    o.push_back(Pair("balance", c.result.saldo));
    o.push_back(Pair("return_rate", c.result.restitution));
    return o;
}

Value weightgetlocalearnings(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const std::string miner = RpcLocalWeightAddress();
    const uint32_t epoch = RpcResolveEpoch(params, 0);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);
    const WeightEpochCluster* c = RpcFindCluster(detail, miner);
    RpcRequireCluster(c, miner, epoch);
    return RpcEarningsEntry(miner, *c, epoch);
}

Value weightgetnodeearnings(const Array& params, bool fHelp)
{
    if (fHelp || params.size() < 1 || params.size() > 2)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const std::string miner = params[0].get_str();
    const uint32_t epoch = RpcResolveEpoch(params, 1);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);
    const WeightEpochCluster* c = RpcFindCluster(detail, miner);
    RpcRequireCluster(c, miner, epoch);
    return RpcEarningsEntry(miner, *c, epoch);
}

Value weightlistearnings(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const uint32_t epoch = RpcResolveEpoch(params, 0);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);

    Object earnings;
    for (std::map<std::string, WeightEpochCluster>::const_iterator it = detail.begin();
         it != detail.end(); ++it)
    {
        earnings.push_back(Pair(it->first, RpcEarningsEntry(it->first, it->second, epoch)));
    }

    Object obj;
    obj.push_back(Pair("epoch", (int64_t)epoch));
    obj.push_back(Pair("clusters", (int)detail.size()));
    obj.push_back(Pair("earnings", earnings));
    return obj;
}

// --- 5. running balance saldo_k ------------------------------------------

static Object RpcBalanceEntry(const std::string& miner, const WeightEpochCluster& c,
                              uint32_t epoch)
{
    Object o;
    o.push_back(Pair("miner", miner));
    o.push_back(Pair("epoch", (int64_t)epoch));
    o.push_back(Pair("earnings", c.result.gain));
    o.push_back(Pair("balance", c.result.saldo));
    return o;
}

Value weightgetlocalbalance(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const std::string miner = RpcLocalWeightAddress();
    const uint32_t epoch = RpcResolveEpoch(params, 0);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);
    const WeightEpochCluster* c = RpcFindCluster(detail, miner);
    RpcRequireCluster(c, miner, epoch);
    return RpcBalanceEntry(miner, *c, epoch);
}

Value weightgetnodebalance(const Array& params, bool fHelp)
{
    if (fHelp || params.size() < 1 || params.size() > 2)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const std::string miner = params[0].get_str();
    const uint32_t epoch = RpcResolveEpoch(params, 1);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);
    const WeightEpochCluster* c = RpcFindCluster(detail, miner);
    RpcRequireCluster(c, miner, epoch);
    return RpcBalanceEntry(miner, *c, epoch);
}

Value weightlistbalances(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRequireWeightEngine();
    const uint32_t epoch = RpcResolveEpoch(params, 0);

    std::map<std::string, WeightEpochCluster> detail;
    RpcEpochDetail(epoch, detail);

    Object balances;
    for (std::map<std::string, WeightEpochCluster>::const_iterator it = detail.begin();
         it != detail.end(); ++it)
    {
        balances.push_back(Pair(it->first, it->second.result.saldo));
    }

    Object obj;
    obj.push_back(Pair("epoch", (int64_t)epoch));
    obj.push_back(Pair("clusters", (int)detail.size()));
    obj.push_back(Pair("balances", balances));
    return obj;
}
