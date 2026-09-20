// Copyright (c) 2010 Satoshi Nakamoto
// Copyright (c) 2014-2016 The Bitcoin Core developers
// Original code was distributed under the MIT software license.
// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA RPC surface — the "wpoa" command category.
// ---------------------------------------------------------------------------
// Read access to the two registries the protocol maintains, plus the one write
// path into the open one:
//
//   getlocalweight / getallweights / getnodeweight   wpoa-weights        (read)
//   getallmalus    / getnodemalus                    wpoa-weights-malus  (read)
//   reportmalus                                      wpoa-weights-malus  (write)
//
// These are handlers only: every decision lives behind StreamWeightRegistry
// (wpoa/stream_weight_registry.h) and MalusRegistry (wpoa/malus_registry.h), so
// this file marshals parameters, calls the registries and shapes the JSON. That
// separation is what lets the registries be driven from the consensus path and
// the background threads without dragging the RPC surface along.


#include "rpc/rpcwallet.h"

#include "wpoa/stream_weight_registry.h"    // StreamWeightRegistry
#include "wpoa/malus_registry.h"            // MalusRegistry, the malus runtime globals
#include "wpoa/malus_record.h"              // MalusAccumulator, mc_MalusKind*
#include "wpoa/wpoa_selector.h"             // WPoASelector, g_dumping_function
#include "wpoa/private_sortition.h"         // WPoARoundContext, PrivateSortition, Phi
#include "wpoa/randao_accumulator.h"        // WPoAExtractBlockReveal (thread-safe)
#include "wpoa/vrf_wrapper.h"               // WPoAVRF::OUTPUT_SIZE
#include "chainparams/chainparams.h"        // Params().TargetSpacing()
#include "weight_engine/weight_engine.h"    // HeightToEpoch (shared height->epoch map)
#include "weight_engine/weight_streams.h"   // MC_WEIGHT_MEMBERSHIP_STREAM_NAME
#include "weight_engine/weight_verifier.h"  // WeightEngineRecomputeWeightForEpoch
#include "core/init.h"                      // pwalletTxsMain
#include "core/main.h"                      // chainActive, cs_main

#include <cmath>

/** Cap on one wpoalistblocksortition call: the audit reads every block from disk. */
#define MC_WPOA_MAX_SORTITION_AUDIT_ROWS 1000

// ---------------------------------------------------------------------------
// Weight registry
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

// ---------------------------------------------------------------------------
// Malus registry
// ---------------------------------------------------------------------------

static uint32_t RpcGoverningMalusEpoch(int height);   // defined with the round audit below

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
    return RpcGoverningMalusEpoch(height);
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
            "reportmalus \"kind\" \"address\" height \"evidence\" [\"blockhash2\"]\n"
            "\nPublishes a misbehaviour report to the open wpoa-weights-malus stream.\n"
            "Any node may report: the evidence is re-verified independently by every\n"
            "peer, so a false report is discarded and changes nothing. This node runs\n"
            "the same check BEFORE broadcasting and refuses to publish evidence that\n"
            "does not hold locally.\n"
            "\nFOUR KINDS, in two families. Both are proved from public chain data; they\n"
            "differ in what the evidence is and what the offence damages.\n"
            "\n  Consensus-behavioural — evidence is a BLOCK:\n"
            "    equiv      two distinct blocks at one height from one key (safety)\n"
            "    delay      a block timestamped earlier than its own score allowed\n"
            "\n  Published-data integrity — evidence is the publishing TRANSACTION:\n"
            "    selfwrite  a record on a self-attested stream (wpoa-weights or\n"
            "               weight-engine-membership) naming a node_address other than\n"
            "               the signer. Readers discard it, so the attempt is the offence\n"
            "    badweight  a wpoa-weights value that fails independent recomputation\n"
            "               from the public pipeline inputs\n"
            "\nArguments:\n"
            "1. \"kind\"       (string, required) equiv | delay | selfwrite | badweight\n"
            "2. \"address\"    (string, required) the accused node (for the data-integrity\n"
            "                   kinds: the SIGNER of the offending transaction)\n"
            "3. height         (numeric, required) the height the accusation refers to;\n"
            "                   for the data-integrity kinds, the height that CONFIRMED\n"
            "                   the offending transaction\n"
            "4. \"evidence\"   (string, required) the offending block hash, or — for the\n"
            "                   data-integrity kinds — the offending transaction id\n"
            "5. \"blockhash2\" (string, optional) the competing block, for \"equiv\" only\n"
            "\nThe data-integrity kinds take no further arguments: what they allege is\n"
            "derived from the referenced transaction, so a caller cannot mis-state it.\n"
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
        throw JSONRPCError(RPC_INVALID_PARAMETER,
                           "kind must be \"equiv\", \"delay\", \"selfwrite\" or "
                           "\"badweight\"");
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

    // The DATA-INTEGRITY kinds need no extra arguments from the caller: everything they
    // allege is derivable from the referenced transaction, so the RPC derives it here
    // rather than asking. That is deliberate — a caller cannot mis-state the accusation,
    // and the published record still carries the derived fields so a third party can
    // audit it without re-searching. Argument 4 is the offending TRANSACTION id for
    // these kinds, not a block hash.
    MalusDataDetail detail;
    if (mc_MalusKindIsDataIntegrity(kind))
    {
        if (params.size() != 4)
        {
            throw JSONRPCError(RPC_INVALID_PARAMETER,
                               "a data-integrity report takes exactly one evidence txid");
        }

        if (kind == MALUS_SELF_WRITE)
        {
            // Try both self-attested streams: the caller supplies a txid, and which
            // stream it belongs to is a fact about the transaction, not a choice.
            const char* candidates[2] = { MC_WPOA_WEIGHTS_STREAM_NAME,
                                          MC_WEIGHT_MEMBERSHIP_STREAM_NAME };
            bool found = false;
            std::string last_reason = "evidence transaction carries no self-attested item";
            for (int ci = 0; ci < 2 && !found; ci++)
            {
                MalusRegistry::AccusedItem probe;
                std::string why;
                if (MalusRegistry::LoadAccusedItem(pwalletTxsMain, blocks[0], candidates[ci],
                                                   probe, &why))
                {
                    detail.stream = candidates[ci];
                    detail.declared_address = probe.declared;
                    found = true;
                }
                else
                {
                    last_reason = why;
                }
            }
            if (!found)
            {
                throw JSONRPCError(RPC_INVALID_PARAMETER, last_reason);
            }
        }
        else   // MALUS_INVALID_WEIGHT
        {
            MalusRegistry::AccusedItem probe;
            std::string why;
            if (!MalusRegistry::LoadAccusedItem(pwalletTxsMain, blocks[0],
                                                MC_WPOA_WEIGHTS_STREAM_NAME, probe, &why))
            {
                throw JSONRPCError(RPC_INVALID_PARAMETER, why);
            }
            uint32_t recomputed = 0;
            bool is_cluster = false;
            if (!WeightEngineRecomputeWeightForEpoch(probe.epoch, address, is_cluster,
                                                     recomputed))
            {
                throw JSONRPCError(RPC_MISC_ERROR,
                                   "this node cannot recompute that epoch (inputs "
                                   "unreadable, epoch not buried, or the weight engine is "
                                   "off), so it cannot substantiate the report");
            }
            detail.epoch      = probe.epoch;
            detail.declared   = probe.weight;
            detail.recomputed = is_cluster ? recomputed : 0;
        }
    }

    return registry.PublishReport(kind, address, (int)height, blocks, detail);
}

// ---------------------------------------------------------------------------
// Round audit: score, delay and the two weight stages
// ---------------------------------------------------------------------------
//
// READ-ONLY INSPECTION OF THE PUBLIC MODEL. These reproduce, for an arbitrary
// height, the quantities the consensus path derives for the round — but from the
// PUBLIC Efraimidis form (entropy = HMAC-SHA256(seed, address)), which is the only
// form recomputable without a validator's secret key. On a sortition-governed chain
// the real election runs the same transform over a PRIVATE VRF output, so these
// scores are an audit of the model and its inputs, never a prediction of the actual
// proposer: the winner stays unknown until it proposes, which is the property the
// whole private-sortition design exists to provide.
//
// Everything below consumes WPoABuildRoundContext (wpoa/private_sortition.h), the
// same context the miner and the validator consume, so an inspection can never
// report a seed, a weight or a normalizer the consensus would not have used.

/** The weight a candidate is actually scored on, and everything derived from it. */
struct RpcRoundEntry
{
    uint32_t raw;         //!< w, straight off wpoa-weights
    uint32_t effective;   //!< w_eff = w * Psi (Def. psi-peso-effettivo)
    double   dumped;      //!< g(w_eff) (Def. smorzamento)
    bool     eligible;    //!< w_eff > 0, i.e. in V+ for this round
    double   score;       //!< +inf when not eligible (Cor. efraimidis-peso-nullo)
    double   score_norm;  //!< 1 - exp(-W * score) (Def. score-normalizzato)
    double   delay;       //!< D_i in seconds (Def. correzione-globale)

    RpcRoundEntry()
        : raw(0), effective(0), dumped(0.0), eligible(false),
          score(0.0), score_norm(0.0), delay(0.0) {}
};

/** One round's shared context plus the parent it was derived over. */
struct RpcRound
{
    const CBlockIndex* pprev;     //!< block n, parent of the round n+1
    WPoARoundContext   ctx;
    double             feedback;  //!< Phi^(n) (Def. correzione-globale)

    RpcRound() : pprev(NULL), feedback(0.0) {}
};

// Accept an int or a numeric-string JSON value as a height/epoch (multichain-cli
// sends unconverted arguments as strings). Mirrors the parsing reportmalus does.
static int64_t RpcInteger(const Value& v, const char* field)
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
    throw JSONRPCError(RPC_INVALID_PARAMETER, std::string(field) + " must be an integer");
}

// The round to audit: the optional argument at `idx`, defaulting to tip+1 (the round
// about to be elected). Heights above tip+1 are refused rather than extrapolated —
// their seed does not exist yet.
static int RpcResolveRoundHeight(const Array& params, size_t idx)
{
    int tip = -1;
    {
        LOCK(cs_main);
        if (chainActive.Tip() != NULL)
        {
            tip = chainActive.Height();
        }
    }
    if (tip < 0)
    {
        throw JSONRPCError(RPC_MISC_ERROR, "No chain tip yet");
    }

    int64_t height = (int64_t)tip + 1;
    if (params.size() > idx && params[idx].type() != null_type)
    {
        height = RpcInteger(params[idx], "height");
    }
    if (height < 1)
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER, "height must be >= 1");
    }
    if (height > (int64_t)tip + 1)
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER,
                           strprintf("height %d is beyond the next round (tip+1 = %d): the "
                                     "beacon seed for it does not exist yet",
                                     (int)height, tip + 1));
    }
    return (int)height;
}

static void RpcBuildRound(const Array& params, size_t idx, RpcRound& out)
{
    const int height = RpcResolveRoundHeight(params, idx);

    {
        LOCK(cs_main);
        out.pprev = chainActive[height - 1];
    }
    if (out.pprev == NULL)
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER,
                           strprintf("no block at height %d in the active chain", height - 1));
    }
    if (!WPoABuildRoundContext(out.pprev, height, out.ctx))
    {
        throw JSONRPCError(RPC_MISC_ERROR,
                           "Round not evaluable on this node: the beacon seed or the "
                           "weight registry is unavailable (wallet not ready, not "
                           "subscribed to wpoa-weights, or no validator carries a "
                           "positive effective weight)");
    }
    out.feedback = WPoASortitionFeedback(out.pprev);
}

// Everything the round derives for one address. Weight 0 — absent from the registry,
// or driven to 0 by the malus — is a legitimate outcome, not an error: the validator
// is simply outside V+ for this round, with an infinite score and no chance of
// election (Cor. efraimidis-peso-nullo / Oss. peso-nullo-malus).
static RpcRoundEntry RpcEvalAddress(const RpcRound& r, const std::string& address)
{
    RpcRoundEntry e;

    std::map<std::string, uint32_t>::const_iterator ri = r.ctx.raw_weights.find(address);
    e.raw = (ri != r.ctx.raw_weights.end()) ? ri->second : 0;

    std::map<std::string, uint32_t>::const_iterator ei = r.ctx.weights.find(address);
    e.effective = (ei != r.ctx.weights.end()) ? ei->second : 0;

    e.dumped   = WPoASelector::ApplyDumping(e.effective, g_dumping_function);
    e.eligible = (e.effective > 0);

    e.score = WPoASelector::ComputeScore(r.ctx.seed, sizeof(r.ctx.seed), address,
                                         e.effective, g_dumping_function);
    e.score_norm = PrivateSortition::NormalizedScore(e.score, r.ctx.total_eff_weight);
    e.delay = PrivateSortition::MiningDelay(e.score, r.ctx.total_eff_weight,
                                            (double)Params().TargetSpacing(),
                                            g_wpoa_sortition_delta,
                                            g_wpoa_sortition_lambda,
                                            r.feedback);
    return e;
}

/** Operator-facing name of the active dumping function (Def. smorzamento). */
static const char* RpcDumpingName(DumpingFunction f)
{
    switch (f)
    {
        case DUMP_SQRT: return "sqrt";
        case DUMP_LOG:  return "log";
        case DUMP_NONE:
        default:        return "none";
    }
}

/** A score is +inf for an ineligible validator, which JSON cannot carry: null. */
static Value RpcScoreValue(const RpcRoundEntry& e)
{
    if (!e.eligible || !std::isfinite(e.score))
    {
        return Value::null;
    }
    return Value(e.score);
}

/** This node's own validator identity, as the weight registry keys it. */
static std::string RpcLocalAddress()
{
    if (pwalletTxsMain == NULL)
    {
        throw JSONRPCError(RPC_WALLET_ERROR, "Wallet not available");
    }
    StreamWeightRegistry registry(pwalletTxsMain);
    std::string addr = registry.GetLocalAddress();
    if (addr.empty() || addr == "unknown")
    {
        throw JSONRPCError(RPC_WALLET_ERROR,
                           "This node has no resolvable validator address (no mine / "
                           "connect key and no wallet default key)");
    }
    return addr;
}

/** Fields common to every round answer, so each output states what it was computed over. */
static void RpcAddRoundContext(Object& obj, const RpcRound& r)
{
    obj.push_back(Pair("height", r.ctx.height));
    obj.push_back(Pair("seed", HexStr(r.ctx.seed, r.ctx.seed + sizeof(r.ctx.seed))));
    obj.push_back(Pair("seed_source", r.ctx.randao_seed ? "randao" : "prevblockhash"));
    obj.push_back(Pair("dumping_function", RpcDumpingName(g_dumping_function)));
    obj.push_back(Pair("total_effective_weight", r.ctx.total_eff_weight));
}

// --- score ---------------------------------------------------------------

static Object RpcScoreEntry(const RpcRoundEntry& e)
{
    Object o;
    o.push_back(Pair("score", RpcScoreValue(e)));
    o.push_back(Pair("weight", (int64_t)e.raw));
    o.push_back(Pair("effective_weight", (int64_t)e.effective));
    o.push_back(Pair("eligible", e.eligible));
    return o;
}

Value wpoagetlocalscore(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    const std::string address = RpcLocalAddress();
    RpcRound r;
    RpcBuildRound(params, 0, r);

    Object obj = RpcScoreEntry(RpcEvalAddress(r, address));
    obj.push_back(Pair("address", address));
    RpcAddRoundContext(obj, r);
    return obj;
}

Value wpoagetnodescore(const Array& params, bool fHelp)
{
    if (fHelp || params.size() < 1 || params.size() > 2)
    {
        throw runtime_error("Help message not found\n");
    }
    const std::string address = params[0].get_str();
    RpcRound r;
    RpcBuildRound(params, 1, r);

    Object obj = RpcScoreEntry(RpcEvalAddress(r, address));
    obj.push_back(Pair("address", address));
    RpcAddRoundContext(obj, r);
    return obj;
}

Value wpoalistscores(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRound r;
    RpcBuildRound(params, 0, r);

    // Ascending address order — the same iteration SelectProposer uses, so a reader
    // can replay the argmin comparison in the printed order.
    Object scores;
    for (std::map<std::string, uint32_t>::const_iterator it = r.ctx.weights.begin();
         it != r.ctx.weights.end(); ++it)
    {
        scores.push_back(Pair(it->first, RpcScoreEntry(RpcEvalAddress(r, it->first))));
    }

    Object obj;
    obj.push_back(Pair("validators", (int)r.ctx.weights.size()));
    obj.push_back(Pair("scores", scores));
    RpcAddRoundContext(obj, r);
    return obj;
}

// --- delay ---------------------------------------------------------------

static Object RpcDelayEntry(const RpcRoundEntry& e)
{
    Object o;
    o.push_back(Pair("delay", e.delay));
    o.push_back(Pair("score", RpcScoreValue(e)));
    o.push_back(Pair("score_norm", e.score_norm));
    o.push_back(Pair("effective_weight", (int64_t)e.effective));
    o.push_back(Pair("eligible", e.eligible));
    return o;
}

/** The delay answers additionally state the three chain-wide terms of Def. correzione-globale. */
static void RpcAddDelayContext(Object& obj, const RpcRound& r)
{
    obj.push_back(Pair("target_block_time", (int64_t)Params().TargetSpacing()));
    obj.push_back(Pair("delta", g_wpoa_sortition_delta));
    obj.push_back(Pair("lambda", g_wpoa_sortition_lambda));
    obj.push_back(Pair("feedback", r.feedback));
    RpcAddRoundContext(obj, r);
}

Value wpoagetlocaldelay(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    const std::string address = RpcLocalAddress();
    RpcRound r;
    RpcBuildRound(params, 0, r);

    Object obj = RpcDelayEntry(RpcEvalAddress(r, address));
    obj.push_back(Pair("address", address));
    RpcAddDelayContext(obj, r);
    return obj;
}

Value wpoagetnodedelay(const Array& params, bool fHelp)
{
    if (fHelp || params.size() < 1 || params.size() > 2)
    {
        throw runtime_error("Help message not found\n");
    }
    const std::string address = params[0].get_str();
    RpcRound r;
    RpcBuildRound(params, 1, r);

    Object obj = RpcDelayEntry(RpcEvalAddress(r, address));
    obj.push_back(Pair("address", address));
    RpcAddDelayContext(obj, r);
    return obj;
}

Value wpoalistdelays(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRound r;
    RpcBuildRound(params, 0, r);

    Object delays;
    for (std::map<std::string, uint32_t>::const_iterator it = r.ctx.weights.begin();
         it != r.ctx.weights.end(); ++it)
    {
        delays.push_back(Pair(it->first, RpcDelayEntry(RpcEvalAddress(r, it->first))));
    }

    Object obj;
    obj.push_back(Pair("validators", (int)r.ctx.weights.size()));
    obj.push_back(Pair("delays", delays));
    RpcAddDelayContext(obj, r);
    return obj;
}

// --- effective weight (dumping only) -------------------------------------

/** g(w) over the RAW registry weight: the dumping stage in isolation, before any
 *  behavioural correction (Def. smorzamento). */
static Object RpcEffectiveWeightEntry(const RpcRoundEntry& e)
{
    Object o;
    o.push_back(Pair("raw_weight", (int64_t)e.raw));
    o.push_back(Pair("dumping_function", RpcDumpingName(g_dumping_function)));
    o.push_back(Pair("effective_weight",
                     WPoASelector::ApplyDumping(e.raw, g_dumping_function)));
    return o;
}

Value wpoagetlocaleffectiveweight(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    const std::string address = RpcLocalAddress();
    RpcRound r;
    RpcBuildRound(params, 0, r);

    Object obj = RpcEffectiveWeightEntry(RpcEvalAddress(r, address));
    obj.push_back(Pair("address", address));
    obj.push_back(Pair("height", r.ctx.height));
    return obj;
}

Value wpoagetnodeeffectiveweight(const Array& params, bool fHelp)
{
    if (fHelp || params.size() < 1 || params.size() > 2)
    {
        throw runtime_error("Help message not found\n");
    }
    const std::string address = params[0].get_str();
    RpcRound r;
    RpcBuildRound(params, 1, r);

    Object obj = RpcEffectiveWeightEntry(RpcEvalAddress(r, address));
    obj.push_back(Pair("address", address));
    obj.push_back(Pair("height", r.ctx.height));
    return obj;
}

Value wpoalisteffectiveweights(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRound r;
    RpcBuildRound(params, 0, r);

    Object weights;
    for (std::map<std::string, uint32_t>::const_iterator it = r.ctx.raw_weights.begin();
         it != r.ctx.raw_weights.end(); ++it)
    {
        weights.push_back(Pair(it->first, RpcEffectiveWeightEntry(RpcEvalAddress(r, it->first))));
    }

    Object obj;
    obj.push_back(Pair("height", r.ctx.height));
    obj.push_back(Pair("dumping_function", RpcDumpingName(g_dumping_function)));
    obj.push_back(Pair("validators", (int)r.ctx.raw_weights.size()));
    obj.push_back(Pair("effective_weights", weights));
    return obj;
}

// --- final weight (malus, then dumping) ----------------------------------

/** The malus epoch that governs `height`: epoch(height) - 1, since a proved violation
 *  bites from the epoch AFTER the one it was proved in (Def. accumulatore-malus). */
static uint32_t RpcGoverningMalusEpoch(int height)
{
    uint32_t epoch = HeightToEpoch(height);
    return (epoch >= 2) ? (epoch - 1) : 0;
}

/** g(w * Psi): the weight the election actually consumes, with the two stages shown
 *  separately so the composition order is auditable (Def. psi-peso-effettivo, then
 *  Def. smorzamento). */
static Object RpcFinalWeightEntry(const RpcRoundEntry& e, double malus)
{
    const double psi = MalusAccumulator::CorrectionFactor(malus, g_wpoa_malus_max);

    Object o;
    o.push_back(Pair("raw_weight", (int64_t)e.raw));
    o.push_back(Pair("malus", malus));
    o.push_back(Pair("malus_factor", psi));
    o.push_back(Pair("weight_after_malus", (int64_t)e.effective));
    o.push_back(Pair("dumping_function", RpcDumpingName(g_dumping_function)));
    o.push_back(Pair("effective_weight_after_malus_and_dumping", e.dumped));
    o.push_back(Pair("eligible", e.eligible));
    return o;
}

/** M for one address at the epoch governing `height` (0 when the registry is
 *  unavailable or no proved violation is carried). */
static double RpcMalusAt(uint32_t epoch, const std::string& address)
{
    if (epoch < 1 || pwalletTxsMain == NULL)
    {
        return 0.0;
    }
    MalusRegistry registry(pwalletTxsMain);
    return registry.GetAccumulator(address, epoch);
}

Value wpoagetlocalfinalweight(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    const std::string address = RpcLocalAddress();
    RpcRound r;
    RpcBuildRound(params, 0, r);

    const uint32_t epoch = RpcGoverningMalusEpoch(r.ctx.height);
    Object obj = RpcFinalWeightEntry(RpcEvalAddress(r, address), RpcMalusAt(epoch, address));
    obj.push_back(Pair("address", address));
    obj.push_back(Pair("height", r.ctx.height));
    obj.push_back(Pair("malus_epoch", (int64_t)epoch));
    return obj;
}

Value wpoagetnodefinalweight(const Array& params, bool fHelp)
{
    if (fHelp || params.size() < 1 || params.size() > 2)
    {
        throw runtime_error("Help message not found\n");
    }
    const std::string address = params[0].get_str();
    RpcRound r;
    RpcBuildRound(params, 1, r);

    const uint32_t epoch = RpcGoverningMalusEpoch(r.ctx.height);
    Object obj = RpcFinalWeightEntry(RpcEvalAddress(r, address), RpcMalusAt(epoch, address));
    obj.push_back(Pair("address", address));
    obj.push_back(Pair("height", r.ctx.height));
    obj.push_back(Pair("malus_epoch", (int64_t)epoch));
    return obj;
}

Value wpoalistfinalweights(const Array& params, bool fHelp)
{
    if (fHelp || params.size() > 1)
    {
        throw runtime_error("Help message not found\n");
    }
    RpcRound r;
    RpcBuildRound(params, 0, r);

    const uint32_t epoch = RpcGoverningMalusEpoch(r.ctx.height);

    // One accumulator pass for the whole map: GetAccumulators folds every report once,
    // where a per-address GetAccumulator would refold the stream for each validator.
    std::map<std::string, double> accumulators;
    if (epoch >= 1 && pwalletTxsMain != NULL)
    {
        MalusRegistry registry(pwalletTxsMain);
        registry.GetAccumulators(epoch, accumulators);
    }

    Object weights;
    for (std::map<std::string, uint32_t>::const_iterator it = r.ctx.raw_weights.begin();
         it != r.ctx.raw_weights.end(); ++it)
    {
        std::map<std::string, double>::const_iterator mi = accumulators.find(it->first);
        const double malus = (mi != accumulators.end()) ? mi->second : 0.0;
        weights.push_back(Pair(it->first,
                               RpcFinalWeightEntry(RpcEvalAddress(r, it->first), malus)));
    }

    Object obj;
    obj.push_back(Pair("height", r.ctx.height));
    obj.push_back(Pair("malus_epoch", (int64_t)epoch));
    obj.push_back(Pair("dumping_function", RpcDumpingName(g_dumping_function)));
    obj.push_back(Pair("validators", (int)r.ctx.raw_weights.size()));
    obj.push_back(Pair("final_weights", weights));
    return obj;
}

// ---------------------------------------------------------------------------
// Block sortition audit — the winner's REAL, private score
// ---------------------------------------------------------------------------
// Everything above this line scores candidates with the PUBLIC Efraimidis form
// (HMAC-SHA256(seed, address)), which is all a node can compute for a validator
// whose secret key it does not hold. On a sortition-governed chain that form is a
// model audit, NOT the quantity the election ran on — the real score is drawn from
// a VRF under the proposer's own secret key.
//
// For the WINNER of a round, though, the real score IS publicly recomputable: the
// block carries the VRF reveal y_i, and score_i = -ln(top64(y_i)/2^64) / f(w_eff,i)
// follows from it and the signer's registry weight. That is exactly what
// WPoASortitionVerifyProposer recomputes to enforce the time bar at accept time
// (private_sortition.cpp), so these handlers re-expose a consensus computation
// read-only rather than introducing a second one.
//
// This is the only audit surface in this file that reports the score the protocol
// actually used. Anything comparing realised timing against "the score" must read
// it from here, not from the *score/*delay families above.

/** The reveal a block carries, or false when it carries none.
 *
 *  A short reveal is refused rather than scored: FoldTop64 reads the top 8 bytes
 *  unconditionally, and unlike the validation path this audit does not re-verify
 *  the proof (VerifyBlockMinerWPoA already did, at accept time), so nothing else
 *  here would notice a truncated one.
 */
static bool RpcBlockReveal(const CBlock& block, std::vector<unsigned char>& reveal_out)
{
    unsigned char buf[255];
    int len = sizeof(buf);
    if (!WPoAExtractBlockReveal(block, buf, &len) ||
        len <= 0 || (size_t)len < WPoAVRF::OUTPUT_SIZE)
    {
        return false;
    }
    reveal_out.assign(buf, buf + len);
    return true;
}

/** The address that signed a block, "" when it carries no usable signer. */
static std::string RpcBlockSigner(const CBlock& block)
{
    if (block.vSigner[0] == 0)
    {
        return "";
    }
    std::vector<unsigned char> vchPubKey(block.vSigner + 1,
                                         block.vSigner + 1 + block.vSigner[0]);
    CPubKey pubkey(vchPubKey);
    if (!pubkey.IsValid())
    {
        return "";
    }
    return CBitcoinAddress(pubkey.GetID()).ToString();
}

/**
 * One height's answer. `verdict` names why a row carries no score, so a gap in the
 * series is always explained rather than silently absent:
 *
 *   ok             — score recomputed from the block's reveal
 *   not-sortition  — the height is not sortition-governed (setup, or an earlier phase)
 *   no-reveal      — sortition-governed but the block carries no VRF reveal
 *   no-signer      — the block carries no usable signer pubkey
 *   no-weight      — the signer is absent from the registry, or its w_eff is 0
 *   unevaluable    — seed or weight map unavailable on this node right now
 */
static Object RpcBlockSortitionEntry(int height, int sample_height)
{
    Object o;
    o.push_back(Pair("height", height));

    const CBlockIndex* pindex = NULL;
    const CBlockIndex* pprev  = NULL;
    CBlock block;
    bool have_block = false;

    {
        LOCK(cs_main);
        pindex = chainActive[height];
        if (pindex != NULL)
        {
            pprev = pindex->pprev;
            if ((pindex->nStatus & BLOCK_HAVE_DATA) != 0)
            {
                have_block = ReadBlockFromDisk(block, pindex);
            }
        }
    }

    if (pindex == NULL)
    {
        o.push_back(Pair("verdict", "no-block"));
        return o;
    }

    o.push_back(Pair("hash", pindex->GetBlockHash().ToString()));
    o.push_back(Pair("block_time", (int64_t)pindex->GetBlockTime()));
    o.push_back(Pair("parent_time", pprev ? (int64_t)pprev->GetBlockTime() : (int64_t)0));
    o.push_back(Pair("dt_prev", pprev
                     ? (int64_t)(pindex->GetBlockTime() - pprev->GetBlockTime())
                     : (int64_t)0));
    // The LOCAL arrival wall-clock of this block on THIS node, sub-second. Unlike
    // block_time (the proposer's own header timestamp, 1 s resolution) it is not
    // consensus data and differs per node -- which is exactly what makes it the
    // right clock for measuring propagation, and the wrong one for anything else.
    o.push_back(Pair("time_received", pindex->dTimeReceived));
    o.push_back(Pair("epoch", (int64_t)HeightToEpoch(height)));
    o.push_back(Pair("sample_height", sample_height));
    // Weights are read as of NOW, not as of `height`: the registry has no
    // height-bound read (see WPoABuildRoundContext). They only change on an epoch
    // boundary, so a sample taken inside the audited height's own epoch is exact,
    // and this flag marks the rows where it cannot be.
    o.push_back(Pair("sample_epoch", (int64_t)HeightToEpoch(sample_height)));
    o.push_back(Pair("weight_epoch_stale",
                     HeightToEpoch(sample_height) != HeightToEpoch(height)));

    if (!WPoASortitionActiveAtHeight(height))
    {
        o.push_back(Pair("verdict", "not-sortition"));
        return o;
    }

    const std::string signer = have_block ? RpcBlockSigner(block) : "";
    o.push_back(Pair("miner", signer));
    if (!have_block || signer.empty())
    {
        o.push_back(Pair("verdict", have_block ? "no-signer" : "no-block-data"));
        return o;
    }

    std::vector<unsigned char> reveal;
    if (!RpcBlockReveal(block, reveal))
    {
        o.push_back(Pair("verdict", "no-reveal"));
        return o;
    }

    // The same context the miner and the validator consumed for this round: the
    // beacon seed over the parent, the malus-corrected weight map, and Sigma f(w).
    WPoARoundContext ctx;
    if (pprev == NULL || !WPoABuildRoundContext(pprev, height, ctx))
    {
        o.push_back(Pair("verdict", "unevaluable"));
        return o;
    }
    const double feedback = WPoASortitionFeedback(pprev);

    std::map<std::string, uint32_t>::const_iterator it = ctx.weights.find(signer);
    const uint32_t weff = (it != ctx.weights.end()) ? it->second : 0;
    o.push_back(Pair("effective_weight", (int64_t)weff));
    if (weff == 0)
    {
        o.push_back(Pair("verdict", "no-weight"));
        return o;
    }

    const double score = PrivateSortition::ScoreFromVRFOutput(reveal.data(), weff,
                                                              g_dumping_function);
    const double score_norm = PrivateSortition::NormalizedScore(score, ctx.total_eff_weight);
    const double delay = PrivateSortition::MiningDelay(score, ctx.total_eff_weight,
                                                       (double)Params().TargetSpacing(),
                                                       g_wpoa_sortition_delta,
                                                       g_wpoa_sortition_lambda,
                                                       feedback);

    o.push_back(Pair("score", std::isfinite(score) ? Value(score) : Value::null));
    o.push_back(Pair("score_norm", score_norm));
    o.push_back(Pair("delay", delay));
    // The bar VerifyBlockMinerWPoA enforced: floor(delay), because block times have
    // 1 s resolution (private_sortition.cpp, step 3).
    o.push_back(Pair("earliest_time",
                     (int64_t)(pprev->GetBlockTime() + (int64_t)delay)));
    o.push_back(Pair("total_effective_weight", ctx.total_eff_weight));
    o.push_back(Pair("target_block_time", (int64_t)Params().TargetSpacing()));
    o.push_back(Pair("delta", g_wpoa_sortition_delta));
    o.push_back(Pair("lambda", g_wpoa_sortition_lambda));
    o.push_back(Pair("feedback", feedback));
    o.push_back(Pair("seed", HexStr(ctx.seed, ctx.seed + sizeof(ctx.seed))));
    o.push_back(Pair("seed_source", ctx.randao_seed ? "randao" : "prevblockhash"));
    o.push_back(Pair("dumping_function", RpcDumpingName(g_dumping_function)));
    o.push_back(Pair("verdict", "ok"));
    return o;
}

/** The tip this answer was computed against — the staleness reference. */
static int RpcSampleHeight()
{
    LOCK(cs_main);
    return (chainActive.Tip() != NULL) ? chainActive.Height() : -1;
}

Value wpoagetblocksortition(const Array& params, bool fHelp)
{
    if (fHelp || params.size() != 1)
    {
        throw runtime_error("Help message not found\n");
    }
    const int sample_height = RpcSampleHeight();
    if (sample_height < 0)
    {
        throw JSONRPCError(RPC_MISC_ERROR, "No chain tip yet");
    }

    const int64_t height = RpcInteger(params[0], "height");
    if (height < 0 || height > (int64_t)sample_height)
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER,
                           strprintf("height %d is not on the active chain (tip = %d)",
                                     (int)height, sample_height));
    }
    return RpcBlockSortitionEntry((int)height, sample_height);
}

Value wpoalistblocksortition(const Array& params, bool fHelp)
{
    if (fHelp || params.size() != 1)
    {
        throw runtime_error("Help message not found\n");
    }
    const int sample_height = RpcSampleHeight();
    if (sample_height < 0)
    {
        throw JSONRPCError(RPC_MISC_ERROR, "No chain tip yet");
    }

    // Same block-set grammar as listblocks ("100-199", "100", an array, ...), so an
    // observer can pass the window it already built for that call.
    std::vector<int> heights = ParseBlockSetIdentifier(params[0]);
    if (heights.size() > MC_WPOA_MAX_SORTITION_AUDIT_ROWS)
    {
        throw JSONRPCError(RPC_INVALID_PARAMETER,
                           strprintf("too many blocks requested (%d): this audit reads every "
                                     "block from disk, so it is capped at %d per call",
                                     (int)heights.size(),
                                     (int)MC_WPOA_MAX_SORTITION_AUDIT_ROWS));
    }

    Array rows;
    for (unsigned int i = 0; i < heights.size(); i++)
    {
        rows.push_back(RpcBlockSortitionEntry(heights[i], sample_height));
    }
    return rows;
}
