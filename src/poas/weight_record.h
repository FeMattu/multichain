// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA Phase 1 — pure, dependency-light helpers for weight records.
//
// This header intentionally depends only on json_spirit (plus <string>), so the
// parsing/aggregation logic can be unit-tested in isolation, without linking the
// wallet / node runtime. See src/poas/test/wpoa_weight_tests.cpp.

#ifndef MC_POAS_WEIGHT_RECORD_H
#define MC_POAS_WEIGHT_RECORD_H

#include <map>
#include <string>
#include <stdint.h>

#include "json/json_spirit_value.h"
#include <boost/foreach.hpp>

/**
 * Parse a wpoa-weights item payload into (node_address, weight).
 *
 * @param data_value  The value produced by OpReturnFormatEntry for a JSON item,
 *                    i.e. an object of the form
 *                    { "json": { "node_address": "...", "weight": n, ... } }.
 * @param node_address  Out: the record's node_address (cleared on failure).
 * @param weight        Out: the record's weight (0 on failure).
 * @return true only for a well-formed record with a non-empty address and a
 *         strictly positive integer weight; false otherwise.
 */
inline bool mc_ParseWeightRecordJson(const json_spirit::Value& data_value,
                                     std::string& node_address, uint32_t& weight)
{
    node_address = "";
    weight = 0;

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
    }

    if (addr.empty() || w <= 0)
    {
        return false;
    }

    node_address = addr;
    weight = (uint32_t)w;
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

#endif // MC_POAS_WEIGHT_RECORD_H
