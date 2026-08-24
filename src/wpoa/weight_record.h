// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA Phase 1 — pure, dependency-light helpers for weight records.
//
// This header intentionally depends only on json_spirit (plus <string>), so the
// parsing/aggregation logic can be unit-tested in isolation, without linking the
// wallet / node runtime. See src/wpoa/test/wpoa_weight_tests.cpp.

#ifndef MC_WPOA_WEIGHT_RECORD_H
#define MC_WPOA_WEIGHT_RECORD_H

#include <map>
#include <string>
#include <vector>
#include <stdint.h>

#include "json/json_spirit_value.h"
#include <boost/foreach.hpp>

/**
 * THE SELF-ATTESTATION RULE (consensus-critical), shared by every stream whose
 * records describe their own publisher.
 *
 * A record is self-attested iff the address that SIGNED the publishing transaction
 * is the address the payload declares. A payload field can claim anything; an input
 * signature cannot. Streams that carry a self-description therefore need no privilege
 * check at all — the claim verifies itself — while a record failing this test must be
 * DISCARDED, never merely flagged.
 *
 * Two streams rely on it, for the same reason and with the same consequence:
 *   * weight-engine-membership — a node declaring which cluster it joined;
 *   * wpoa-weights            — a node declaring its own cluster's weight.
 *
 * IT LIVES HERE, in the lower (consensus) layer, so both layers share ONE copy. The
 * weight layer sits above wPoA and may depend downwards, so
 * weight_engine/weight_records.h delegates to this function rather than restating it:
 * two copies of a consensus-critical predicate could drift into a node discarding a
 * record it does not accuse, or accusing one it does not discard.
 *
 * `publishers` are the addresses recovered from the transaction's input scripts. A
 * transaction funded from several addresses has several publishers, and the record is
 * accepted if the declared address is ANY of them — each of them did in fact authorize
 * the transaction. An empty publisher list, i.e. an item whose signer could not be
 * recovered, is never accepted: failing closed keeps the rule decidable rather than
 * letting an undecodable item through.
 *
 * @param declared_address  The address the payload claims to be about.
 * @param publishers        The signing addresses of the publishing transaction.
 * @return true iff the record is self-attested.
 */
inline bool mc_StreamItemIsSelfAttested(const std::string& declared_address,
                                        const std::vector<std::string>& publishers)
{
    if (declared_address.empty())
    {
        return false;
    }
    for (size_t i = 0; i < publishers.size(); i++)
    {
        if (publishers[i] == declared_address)
        {
            return true;
        }
    }
    return false;   // includes the empty-publisher case: fail closed
}

/**
 * Parse a wpoa-weights item payload into (node_address, weight).
 *
 * @param data_value  The value produced by OpReturnFormatEntry for a JSON item,
 *                    i.e. an object of the form
 *                    { "json": { "node_address": "...", "weight": n, ... } }.
 * @param node_address  Out: the record's node_address (cleared on failure).
 * @param weight        Out: the record's weight (0 on failure).
 * @param epoch         Out, optional: the epoch the value was computed FOR, or 0 when
 *                      the record does not say. See the note below.
 * @return true only for a well-formed record with a non-empty address and a
 *         strictly positive integer weight; false otherwise.
 *
 * WHY THE EPOCH MATTERS, and why 0 is a legitimate answer. A weight is a claim about a
 * SPECIFIC epoch: w_k^{(e)} is computed from epoch e's inputs, so checking a published
 * value against a recomputation is only meaningful when both refer to the same epoch.
 * Without the field, a value legitimately published for epoch e would be compared
 * against epoch e+1's recomputation as soon as the epoch rolled over, and an honest
 * node would be flagged as wrong — a false accusation, which the malus would then turn
 * into a real weight penalty.
 *
 * The field is OPTIONAL, and its absence is meaningful rather than malformed:
 *   * the weight engine stamps it, because it knows which epoch it computed for;
 *   * the static -weight path does NOT, because a hand-set weight is not derived from
 *     any epoch and there is nothing to recompute it against.
 * A record with epoch 0 is therefore simply not subject to value verification, which is
 * the correct outcome in both cases. Older records predating the field read as 0 too,
 * so the change is backward-compatible.
 */
inline bool mc_ParseWeightRecordJson(const json_spirit::Value& data_value,
                                     std::string& node_address, uint32_t& weight,
                                     uint32_t* epoch = NULL)
{
    node_address = "";
    weight = 0;
    if (epoch != NULL)
    {
        *epoch = 0;
    }

    if (data_value.type() != json_spirit::obj_type)
    {
        return false;
    }

    // OpReturnFormatEntry has two output shapes for a UBJSON item, depending on the
    // overload used:
    //   * 6/7-arg overload (like StreamItemEntry): {"json": {...}}          <- direct
    //   * 3-arg  overload:  {"format":"json","formatdata":{"json":{...}}}   <- wrapped
    // Accept both: if a "formatdata" object is present, descend into it first, then
    // look for the "json" object at that level.
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

    // Unwrap {"json": {...}}.
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

    std::string addr;
    int64_t w = -1;
    int64_t e = 0;
    BOOST_FOREACH(const json_spirit::Pair& p, json_val.get_obj())
    {
        if (p.name_ == "node_address" && p.value_.type() == json_spirit::str_type)
        {
            addr = p.value_.get_str();
        }
        else if (p.name_ == "weight")
        {
            if (p.value_.type() == json_spirit::int_type)
            {
                w = p.value_.get_int64();
            }
            else if (p.value_.type() == json_spirit::real_type)
            {
                w = (int64_t)p.value_.get_real();
            }
        }
        else if (p.name_ == "epoch")
        {
            if (p.value_.type() == json_spirit::int_type)
            {
                e = p.value_.get_int64();
            }
            else if (p.value_.type() == json_spirit::real_type)
            {
                e = (int64_t)p.value_.get_real();
            }
        }
    }

    if (addr.empty() || w <= 0)
    {
        return false;
    }

    node_address = addr;
    weight = (uint32_t)w;
    if (epoch != NULL)
    {
        // Out-of-range or negative reads as "unstated" rather than wrapping: a bad epoch
        // must not make a record look like it belongs to a different one.
        *epoch = (e > 0 && e <= (int64_t)0xffffffff) ? (uint32_t)e : 0;
    }
    return true;
}

/**
 * Fold one record into an "address -> latest weight" map, mirroring how the
 * registry aggregates a chain-ordered (oldest -> newest) item list: the newest
 * value for an address overwrites any earlier one.
 */
inline void mc_AccumulateLatestWeight(std::map<std::string, uint32_t>& latest,
                                      const std::string& node_address, uint32_t weight)
{
    latest[node_address] = weight;
}

#endif // MC_WPOA_WEIGHT_RECORD_H
