// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W1: pure, dependency-light helpers that parse
// the four WeightEngine input-stream item payloads and fold them into the
// in-memory structures the pipeline consumes.
//
// Mirrors wpoa/weight_record.h: this header depends only on json_spirit (plus
// the C++ standard library), so the parsing/aggregation logic can be unit-tested
// in isolation, without linking the wallet / node runtime. See
// src/weight_engine/test/weight_records_tests.cpp. The node-coupled reader that
// pulls the raw item values off the streams lives in weight_reader.{h,cpp} (W3).
//
// CONSENSUS-CRITICAL. These parsers are the gate that decides which on-chain
// items are allowed to enter the weight math. Every honest node must accept or
// reject the same item bit-identically, or nodes derive different w_k and fork.
// Two disciplines follow from that and are enforced here:
//   * numeric fields destined for a fixed-width integer (tau, epoch) are range-
//     and integrality-checked BEFORE the cast — an out-of-range double->uint32_t
//     conversion is undefined behavior in C++ and could differ across builds;
//   * non-finite doubles (NaN/Inf) are rejected centrally, since a NaN silently
//     passes ordinary `< 0` range guards.
// The parsers are kept explicit (one typed function per stream) rather than
// driven by a generic schema/factory: the typed out-params are the validated
// contract handed to the W3 reader, and each stream's accept/reject rule stays
// readable in one place for audit.

#ifndef MC_WEIGHT_RECORDS_H
#define MC_WEIGHT_RECORDS_H

#include <cmath>
#include <map>
#include <set>
#include <string>
#include <stdint.h>

#include "weight_engine/weight_streams.h"
#include "json/json_spirit_value.h"
#include <boost/foreach.hpp>

// ---------------------------------------------------------------------------
// Shared unwrapping / field extraction
// ---------------------------------------------------------------------------

/**
 * Unwrap a decoded stream-item value into its inner record object.
 *
 * OpReturnFormatEntry produces two shapes for a UBJSON item, depending on the
 * overload used (see wpoa/weight_record.h for the same handling):
 *   * 6/7-arg overload (like StreamItemEntry): {"json": {...}}          <- direct
 *   * 3-arg  overload:  {"format":"json","formatdata":{"json":{...}}}   <- wrapped
 * Accept both: descend into "formatdata" when present, then into "json".
 *
 * @param data_value  The value produced by OpReturnFormatEntry.
 * @param out_inner   Out: a copy of the inner record object (cleared on failure).
 * @return true iff a "json" object was found; false otherwise.
 */
inline bool mc_WeightUnwrapItemJson(const json_spirit::Value& data_value,
                                    json_spirit::Object& out_inner)
{
    out_inner.clear();

    if (data_value.type() != json_spirit::obj_type)
    {
        return false;
    }

    const json_spirit::Object* obj = &data_value.get_obj();

    json_spirit::Value formatdata_val;
    bool have_formatdata = false;
    BOOST_FOREACH(const json_spirit::Pair& p, *obj)
    {
        if (p.name_ == "formatdata" && p.value_.type() == json_spirit::obj_type)
        {
            formatdata_val = p.value_;
            have_formatdata = true;
            break;
        }
    }
    if (have_formatdata)
    {
        obj = &formatdata_val.get_obj();
    }

    json_spirit::Value json_val;
    bool have_json = false;
    BOOST_FOREACH(const json_spirit::Pair& p, *obj)
    {
        if (p.name_ == "json")
        {
            json_val = p.value_;
            have_json = true;
            break;
        }
    }
    if (!have_json || json_val.type() != json_spirit::obj_type)
    {
        return false;
    }

    out_inner = json_val.get_obj();
    return true;
}

/** Read a string field from an inner record object; false if absent/wrong type.
 *  On a duplicate field name the first occurrence wins (BOOST_FOREACH order) —
 *  deterministic across nodes. */
inline bool mc_WeightGetStr(const json_spirit::Object& inner, const char* name,
                            std::string& out)
{
    BOOST_FOREACH(const json_spirit::Pair& p, inner)
    {
        if (p.name_ == name && p.value_.type() == json_spirit::str_type)
        {
            out = p.value_.get_str();
            return true;
        }
    }
    return false;
}

/** Read a numeric field (int or real) as a FINITE double; false if absent, of
 *  the wrong type, or non-finite (NaN/Inf). Rejecting non-finite values here is
 *  consensus-critical: a NaN would otherwise slip past callers' `< 0` guards and
 *  then be cast to an integer (undefined behavior). First occurrence wins. */
inline bool mc_WeightGetNum(const json_spirit::Object& inner, const char* name,
                            double& out)
{
    BOOST_FOREACH(const json_spirit::Pair& p, inner)
    {
        if (p.name_ == name)
        {
            double v;
            if (p.value_.type() == json_spirit::int_type)
            {
                v = (double)p.value_.get_int64();
            }
            else if (p.value_.type() == json_spirit::real_type)
            {
                v = p.value_.get_real();
            }
            else
            {
                return false; // present but not numeric
            }
            if (!std::isfinite(v))
            {
                return false; // NaN / +-Inf never enter the weight math
            }
            out = v;
            return true;
        }
    }
    return false;
}

/**
 * Read a numeric field as a uint32_t counter, safely.
 *
 * The value must be a finite number, an exact non-negative integer, and within
 * [0, UINT32_MAX]. Only then is the cast performed. This closes the
 * double->uint32_t undefined-behavior hole: a producer publishing e.g.
 * tau = 1e18 or epoch = 1e10 is rejected here rather than truncated to a
 * platform-dependent value that would fork the validator set.
 *
 * @return true iff the field is present and a representable non-negative integer.
 */
inline bool mc_WeightGetBoundedU32(const json_spirit::Object& inner, const char* name,
                                   uint32_t& out)
{
    double v;
    if (!mc_WeightGetNum(inner, name, v)) // also rejects NaN/Inf
    {
        return false;
    }
    if (v < 0.0 || v > (double)UINT32_MAX)
    {
        return false; // out of range for uint32_t
    }
    if (v != std::floor(v))
    {
        return false; // must be an exact integer, not a truncated fraction
    }
    out = (uint32_t)v;
    return true;
}

// ---------------------------------------------------------------------------
// Parsers — one per input stream
// ---------------------------------------------------------------------------

/**
 * Parse a merged wpoa membership item into the set of company addresses of one
 * cluster. Item key = miner address (supplied separately by the reader, W3);
 * value = the miner's merged membership object, whose FIELD NAMES are the
 * associated company addresses:
 *   {"json":{"<azienda_addr_1>": <ts>, "<azienda_addr_2>": <ts>, ...}}.
 *
 * jsonobjectmerge (getstreamkeysummary / mc_MergeValues) accumulates one field
 * per company under the miner key, so iterating the merged object's field names
 * reconstructs the cluster set C_k (Def. peso-grezzo). Field VALUES (timestamps)
 * are irrelevant to membership and ignored.
 *
 * @param merged_value  The merged value for one miner key.
 * @param aziende       Out: the company addresses in the cluster (cleared first).
 * @return true iff the object unwraps and contains at least one non-empty field
 *         name; false for a missing wrapper or an empty cluster.
 */
inline bool mc_ParseMembershipClusterJson(const json_spirit::Value& merged_value,
                                          std::set<std::string>& aziende)
{
    aziende.clear();

    json_spirit::Object inner;
    if (!mc_WeightUnwrapItemJson(merged_value, inner))
    {
        return false;
    }

    BOOST_FOREACH(const json_spirit::Pair& p, inner)
    {
        if (!p.name_.empty())
        {
            aziende.insert(p.name_);
        }
    }

    return !aziende.empty();
}

/**
 * Parse a wpoa-esg item: {"json":{"node_address":"..","esg":n}}.
 * The ESG score must be strictly positive (Def. esg-score, ESG in R_{>0}); a
 * non-positive score is rejected so it can never enter the weight product.
 * @return true only for a non-empty address and esg > 0.
 */
inline bool mc_ParseEsgRecordJson(const json_spirit::Value& data_value,
                                  std::string& node_address, double& esg)
{
    node_address = "";
    esg = 0.0;

    json_spirit::Object inner;
    if (!mc_WeightUnwrapItemJson(data_value, inner))
    {
        return false;
    }

    std::string addr;
    double score = 0.0;
    if (!mc_WeightGetStr(inner, MC_WEIGHT_FIELD_NODE_ADDR, addr) ||
        !mc_WeightGetNum(inner, MC_WEIGHT_FIELD_ESG, score))
    {
        return false;
    }
    if (addr.empty() || score <= 0.0)
    {
        return false;
    }

    node_address = addr;
    esg = score;
    return true;
}

/**
 * Parse a wpoa-activity item: {"json":{"node_address":"..","tau":n,"epoch":e}}.
 * tau is a non-negative counter (an inactive node has tau == 0, Def.
 * contributo-pesato); epoch must be >= 1. Both are range/integrality checked.
 * @return true for a non-empty address, a representable tau >= 0 and epoch >= 1.
 */
inline bool mc_ParseActivityRecordJson(const json_spirit::Value& data_value,
                                       std::string& node_address, uint32_t& tau,
                                       uint32_t& epoch)
{
    node_address = "";
    tau = 0;
    epoch = 0;

    json_spirit::Object inner;
    if (!mc_WeightUnwrapItemJson(data_value, inner))
    {
        return false;
    }

    std::string addr;
    uint32_t tau_v = 0;
    uint32_t epoch_v = 0;
    if (!mc_WeightGetStr(inner, MC_WEIGHT_FIELD_NODE_ADDR, addr) ||
        !mc_WeightGetBoundedU32(inner, MC_WEIGHT_FIELD_TAU, tau_v) ||
        !mc_WeightGetBoundedU32(inner, MC_WEIGHT_FIELD_EPOCH, epoch_v))
    {
        return false;
    }
    if (addr.empty() || epoch_v < 1)
    {
        return false;
    }

    node_address = addr;
    tau = tau_v;
    epoch = epoch_v;
    return true;
}

/**
 * Parse a wpoa-reconciliation item:
 *   {"json":{"node_address":"..","reconciled":r,"epoch":e}}.
 * reconciled is the amount R_k^{(e)} reconciled in the epoch (>= 0, finite, Def.
 * riconciliazione); epoch must be >= 1. reconciled stays a real value (it is an
 * amount, not a counter) so it is not integrality-checked.
 * @return true for a non-empty miner address, reconciled >= 0 and epoch >= 1.
 */
inline bool mc_ParseReconciliationRecordJson(const json_spirit::Value& data_value,
                                             std::string& miner, double& reconciled,
                                             uint32_t& epoch)
{
    miner = "";
    reconciled = 0.0;
    epoch = 0;

    json_spirit::Object inner;
    if (!mc_WeightUnwrapItemJson(data_value, inner))
    {
        return false;
    }

    std::string addr;
    double r = -1.0;
    uint32_t epoch_v = 0;
    if (!mc_WeightGetStr(inner, MC_WEIGHT_FIELD_NODE_ADDR, addr) ||
        !mc_WeightGetNum(inner, MC_WEIGHT_FIELD_RECONCILED, r) ||
        !mc_WeightGetBoundedU32(inner, MC_WEIGHT_FIELD_EPOCH, epoch_v))
    {
        return false;
    }
    if (addr.empty() || r < 0.0 || epoch_v < 1)
    {
        return false;
    }

    miner = addr;
    reconciled = r;
    epoch = epoch_v;
    return true;
}

// ---------------------------------------------------------------------------
// Aggregation — fold parsed records into the pipeline's in-memory structures.
//
// The ESG/activity/reconciliation accumulators fold a chain-ordered
// (oldest -> newest) item list; the newest record for a key wins, mirroring
// mc_AccumulateLatestWeight in wpoa/weight_record.h.
//
// PRECONDITION for the activity/reconciliation accumulators: they key on address
// ONLY, so "newest wins" reconstructs a per-epoch value correctly only when the
// reader feeds items for a SINGLE target epoch. The W3 reader folds the pipeline
// forward one epoch at a time (it needs each epoch's A_k and R_k to derive
// B_{k-1} and rho_{k-1}), so it filters to one epoch before accumulating. Keep
// this contract if W3's fold strategy changes.
// ---------------------------------------------------------------------------

/** Add a cluster's companies to their miner's set C_k (membership is additive
 *  and idempotent — re-adding a company is a no-op). */
inline void mc_AccumulateMembership(std::map<std::string, std::set<std::string> >& clusters,
                                    const std::string& miner,
                                    const std::set<std::string>& aziende)
{
    std::set<std::string>& target = clusters[miner];
    target.insert(aziende.begin(), aziende.end());
}

/** address -> latest certified ESG score. */
inline void mc_AccumulateLatestEsg(std::map<std::string, double>& latest,
                                   const std::string& node_address, double esg)
{
    latest[node_address] = esg;
}

/** address -> latest activity counter tau for the epoch being read. */
inline void mc_AccumulateLatestActivity(std::map<std::string, uint32_t>& latest,
                                        const std::string& node_address, uint32_t tau)
{
    latest[node_address] = tau;
}

/** miner -> latest reconciled amount R for the epoch being read. */
inline void mc_AccumulateLatestReconciliation(std::map<std::string, double>& latest,
                                              const std::string& miner, double reconciled)
{
    latest[miner] = reconciled;
}

#endif // MC_WEIGHT_RECORDS_H
