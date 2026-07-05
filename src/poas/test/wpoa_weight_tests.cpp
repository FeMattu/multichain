// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA Phase 1 — unit tests for the pure weight-record parsing/aggregation
// helpers (src/poas/weight_record.h).
//
// These tests are self-contained: they depend only on json_spirit headers and
// Boost.Test (header-only "included" variant), NOT on the wallet / node runtime.
// Build & run with src/poas/test/run_unit_tests.sh.

#define BOOST_TEST_MODULE wPoAWeightTests
#include <boost/test/included/unit_test.hpp>

#include <map>
#include <string>

#include "poas/weight_record.h"

using namespace json_spirit;

// ---- helpers -------------------------------------------------------------

// Build the inner record object: { "node_address": addr, "weight": w,
// "timestamp": ts, "height": h }.
static Object make_inner(const std::string& addr, int64_t weight,
                         int64_t ts = 1751630400, int64_t height = 42)
{
    Object inner;
    inner.push_back(Pair("timestamp", ts));
    inner.push_back(Pair("node_address", addr));
    inner.push_back(Pair("weight", weight));
    inner.push_back(Pair("height", height));
    return inner;
}

// Wrap an inner record as the value returned by OpReturnFormatEntry: {"json": inner}.
static Value wrap_json(const Value& inner)
{
    Object outer;
    outer.push_back(Pair("json", inner));
    return Value(outer);
}

// The 3-argument OpReturnFormatEntry overload wraps the value one level deeper:
// {"format":"json","formatdata":{"json": inner}}. The parser must accept this too
// (see stream_weight_registry.cpp / weight_record.h). Regression guard for the bug
// where every on-chain item silently failed to decode.
static Value wrap_formatdata(const Value& inner)
{
    Object outer;
    outer.push_back(Pair("format", std::string("json")));
    outer.push_back(Pair("formatdata", wrap_json(inner)));
    return Value(outer);
}

// ---- parsing: happy paths ------------------------------------------------

BOOST_AUTO_TEST_CASE(parse_valid_record)
{
    Value data = wrap_json(make_inner("1A1z7agoat3FwzZqK6YXYaSJKcqF5L5KvD", 100));

    std::string addr;
    uint32_t weight = 999;
    BOOST_CHECK(mc_ParseWeightRecordJson(data, addr, weight));
    BOOST_CHECK_EQUAL(addr, "1A1z7agoat3FwzZqK6YXYaSJKcqF5L5KvD");
    BOOST_CHECK_EQUAL(weight, 100u);
}

BOOST_AUTO_TEST_CASE(parse_wrapped_formatdata_shape)
{
    // Value as produced by the 3-arg OpReturnFormatEntry overload.
    Value data = wrap_formatdata(make_inner("1A1z7agoat3FwzZqK6YXYaSJKcqF5L5KvD", 137));

    std::string addr;
    uint32_t weight = 0;
    BOOST_CHECK(mc_ParseWeightRecordJson(data, addr, weight));
    BOOST_CHECK_EQUAL(addr, "1A1z7agoat3FwzZqK6YXYaSJKcqF5L5KvD");
    BOOST_CHECK_EQUAL(weight, 137u);
}

BOOST_AUTO_TEST_CASE(parse_field_order_independent)
{
    // node_address / weight can appear in any position among other fields.
    Object inner;
    inner.push_back(Pair("weight", (int64_t)80));
    inner.push_back(Pair("height", (int64_t)7));
    inner.push_back(Pair("node_address", std::string("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2")));
    inner.push_back(Pair("timestamp", (int64_t)123));

    std::string addr;
    uint32_t weight = 0;
    BOOST_CHECK(mc_ParseWeightRecordJson(wrap_json(inner), addr, weight));
    BOOST_CHECK_EQUAL(addr, "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2");
    BOOST_CHECK_EQUAL(weight, 80u);
}

BOOST_AUTO_TEST_CASE(parse_weight_as_real_is_truncated)
{
    // UBJSON round-tripping could surface a numeric as real; accept and truncate.
    Object inner = make_inner("1dice8EMCQAqQxWhZgWmwBYz4MPnPCfQNV", 0);
    // replace the int weight with a real value
    for (size_t i = 0; i < inner.size(); i++)
    {
        if (inner[i].name_ == "weight") inner[i].value_ = Value(50.0);
    }

    std::string addr;
    uint32_t weight = 0;
    BOOST_CHECK(mc_ParseWeightRecordJson(wrap_json(inner), addr, weight));
    BOOST_CHECK_EQUAL(weight, 50u);
}

BOOST_AUTO_TEST_CASE(parse_large_weight)
{
    Value data = wrap_json(make_inner("addrX", 4000000000LL)); // > INT32_MAX, fits uint32
    std::string addr;
    uint32_t weight = 0;
    BOOST_CHECK(mc_ParseWeightRecordJson(data, addr, weight));
    BOOST_CHECK_EQUAL(weight, 4000000000u);
}

// ---- parsing: rejections -------------------------------------------------

BOOST_AUTO_TEST_CASE(reject_non_object_value)
{
    std::string addr = "sentinel";
    uint32_t weight = 7;
    BOOST_CHECK(!mc_ParseWeightRecordJson(Value("just a string"), addr, weight));
    BOOST_CHECK_EQUAL(addr, "");       // cleared on failure
    BOOST_CHECK_EQUAL(weight, 0u);     // zeroed on failure
}

BOOST_AUTO_TEST_CASE(reject_missing_json_wrapper)
{
    // A bare record object, not wrapped in {"json": ...}.
    Value data = Value(make_inner("addrY", 100));
    std::string addr;
    uint32_t weight = 0;
    BOOST_CHECK(!mc_ParseWeightRecordJson(data, addr, weight));
}

BOOST_AUTO_TEST_CASE(reject_json_not_object)
{
    Object outer;
    outer.push_back(Pair("json", std::string("oops")));
    std::string addr;
    uint32_t weight = 0;
    BOOST_CHECK(!mc_ParseWeightRecordJson(Value(outer), addr, weight));
}

BOOST_AUTO_TEST_CASE(reject_missing_address)
{
    Object inner;
    inner.push_back(Pair("weight", (int64_t)100));
    std::string addr;
    uint32_t weight = 0;
    BOOST_CHECK(!mc_ParseWeightRecordJson(wrap_json(inner), addr, weight));
}

BOOST_AUTO_TEST_CASE(reject_empty_address)
{
    Value data = wrap_json(make_inner("", 100));
    std::string addr;
    uint32_t weight = 0;
    BOOST_CHECK(!mc_ParseWeightRecordJson(data, addr, weight));
}

BOOST_AUTO_TEST_CASE(reject_missing_weight)
{
    Object inner;
    inner.push_back(Pair("node_address", std::string("addrZ")));
    std::string addr;
    uint32_t weight = 0;
    BOOST_CHECK(!mc_ParseWeightRecordJson(wrap_json(inner), addr, weight));
}

BOOST_AUTO_TEST_CASE(reject_zero_weight)
{
    Value data = wrap_json(make_inner("addrZero", 0));
    std::string addr;
    uint32_t weight = 5;
    BOOST_CHECK(!mc_ParseWeightRecordJson(data, addr, weight));
    BOOST_CHECK_EQUAL(weight, 0u);
}

BOOST_AUTO_TEST_CASE(reject_negative_weight)
{
    Value data = wrap_json(make_inner("addrNeg", -10));
    std::string addr;
    uint32_t weight = 0;
    BOOST_CHECK(!mc_ParseWeightRecordJson(data, addr, weight));
}

BOOST_AUTO_TEST_CASE(reject_weight_wrong_type)
{
    Object inner;
    inner.push_back(Pair("node_address", std::string("addrStr")));
    inner.push_back(Pair("weight", std::string("100"))); // string, not numeric
    std::string addr;
    uint32_t weight = 0;
    BOOST_CHECK(!mc_ParseWeightRecordJson(wrap_json(inner), addr, weight));
}

BOOST_AUTO_TEST_CASE(reject_address_wrong_type)
{
    Object inner;
    inner.push_back(Pair("node_address", (int64_t)12345)); // numeric, not string
    inner.push_back(Pair("weight", (int64_t)100));
    std::string addr;
    uint32_t weight = 0;
    BOOST_CHECK(!mc_ParseWeightRecordJson(wrap_json(inner), addr, weight));
}

// ---- aggregation: newest wins -------------------------------------------

BOOST_AUTO_TEST_CASE(aggregation_newest_wins)
{
    // Simulate iterating a chain-ordered (oldest -> newest) item list.
    std::map<std::string, uint32_t> latest;
    mc_AccumulateLatestWeight(latest, "A", 100);
    mc_AccumulateLatestWeight(latest, "B", 80);
    mc_AccumulateLatestWeight(latest, "A", 150); // A re-registers with a new weight
    mc_AccumulateLatestWeight(latest, "C", 50);
    mc_AccumulateLatestWeight(latest, "B", 90);  // B re-registers

    BOOST_CHECK_EQUAL(latest.size(), 3u);
    BOOST_CHECK_EQUAL(latest["A"], 150u); // newest A wins
    BOOST_CHECK_EQUAL(latest["B"], 90u);  // newest B wins
    BOOST_CHECK_EQUAL(latest["C"], 50u);

    uint64_t total = 0;
    for (std::map<std::string, uint32_t>::const_iterator it = latest.begin(); it != latest.end(); ++it)
    {
        total += it->second;
    }
    BOOST_CHECK_EQUAL(total, 290u); // 150 + 90 + 50
}

BOOST_AUTO_TEST_CASE(aggregation_end_to_end_three_nodes)
{
    // Parse three well-formed records and aggregate, mirroring the spec example.
    const char* addrs[3] = {
        "1A1z7agoat3FwzZqK6YXYaSJKcqF5L5KvD",
        "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
        "1dice8EMCQAqQxWhZgWmwBYz4MPnPCfQNV"
    };
    int64_t weights[3] = {100, 80, 50};

    std::map<std::string, uint32_t> latest;
    for (int i = 0; i < 3; i++)
    {
        std::string addr;
        uint32_t w = 0;
        BOOST_REQUIRE(mc_ParseWeightRecordJson(wrap_json(make_inner(addrs[i], weights[i])), addr, w));
        mc_AccumulateLatestWeight(latest, addr, w);
    }

    BOOST_CHECK_EQUAL(latest.size(), 3u);
    uint64_t total = 0;
    for (std::map<std::string, uint32_t>::const_iterator it = latest.begin(); it != latest.end(); ++it)
    {
        total += it->second;
    }
    BOOST_CHECK_EQUAL(total, 230u); // 100 + 80 + 50, as in the spec's expected output
}
