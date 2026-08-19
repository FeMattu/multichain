// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W1: unit tests for the pure input-stream
// record parsers / aggregators (src/weight_engine/weight_records.h).
//
// Self-contained: depend only on json_spirit headers and Boost.Test (header-only
// "included" variant), NOT on the wallet / node runtime. Build & run with
// src/weight_engine/test/run_unit_tests.sh.

#define BOOST_TEST_MODULE WeightRecordsTests
#include <boost/test/included/unit_test.hpp>

#include <limits>
#include <map>
#include <set>
#include <string>

#include "weight_engine/weight_records.h"

using namespace json_spirit;

// ---- helpers -------------------------------------------------------------

// Wrap an inner record as the value returned by OpReturnFormatEntry: {"json": inner}.
static Value wrap_json(const Object& inner)
{
    Object outer;
    outer.push_back(Pair("json", inner));
    return Value(outer);
}

// The 3-arg OpReturnFormatEntry overload wraps one level deeper:
// {"format":"json","formatdata":{"json": inner}}. Parsers must accept this too.
static Value wrap_formatdata(const Object& inner)
{
    Object outer;
    outer.push_back(Pair("format", std::string("json")));
    outer.push_back(Pair("formatdata", wrap_json(inner)));
    return Value(outer);
}

// A membership merged object: one field per company address (value = timestamp).
static Object membership_obj(const std::vector<std::string>& aziende)
{
    Object o;
    for (size_t i = 0; i < aziende.size(); i++)
    {
        o.push_back(Pair(aziende[i], (int64_t)(1700000000 + i)));
    }
    return o;
}

// ---- membership (merged object per miner) --------------------------------

BOOST_AUTO_TEST_CASE(membership_merged_object_yields_cluster_set)
{
    std::vector<std::string> az;
    az.push_back("AZ_1");
    az.push_back("AZ_2");
    az.push_back("AZ_3");

    std::set<std::string> aziende;
    BOOST_CHECK(mc_ParseMembershipClusterJson(wrap_json(membership_obj(az)), aziende));
    BOOST_CHECK_EQUAL(aziende.size(), 3u);
    BOOST_CHECK(aziende.count("AZ_1") == 1);
    BOOST_CHECK(aziende.count("AZ_2") == 1);
    BOOST_CHECK(aziende.count("AZ_3") == 1);
}

BOOST_AUTO_TEST_CASE(membership_wrapped_formatdata_shape)
{
    std::vector<std::string> az;
    az.push_back("AZ_9");

    std::set<std::string> aziende;
    BOOST_CHECK(mc_ParseMembershipClusterJson(wrap_formatdata(membership_obj(az)), aziende));
    BOOST_CHECK_EQUAL(aziende.size(), 1u);
    BOOST_CHECK(aziende.count("AZ_9") == 1);
}

BOOST_AUTO_TEST_CASE(membership_reject_empty_cluster)
{
    Object empty;
    std::set<std::string> aziende;
    aziende.insert("stale"); // must be cleared on failure
    BOOST_CHECK(!mc_ParseMembershipClusterJson(wrap_json(empty), aziende));
    BOOST_CHECK(aziende.empty());
}

BOOST_AUTO_TEST_CASE(membership_reject_non_object_and_missing_wrapper)
{
    std::set<std::string> aziende;
    BOOST_CHECK(!mc_ParseMembershipClusterJson(Value("just a string"), aziende));

    // bare object, not wrapped in {"json": ...}
    std::vector<std::string> az;
    az.push_back("AZ_1");
    BOOST_CHECK(!mc_ParseMembershipClusterJson(Value(membership_obj(az)), aziende));
}

BOOST_AUTO_TEST_CASE(membership_aggregation_unions_and_dedups)
{
    std::map<std::string, std::set<std::string> > clusters;

    std::set<std::string> a1;
    a1.insert("az1");
    a1.insert("az2");
    mc_AccumulateMembership(clusters, "A", a1);

    std::set<std::string> a2;
    a2.insert("az2"); // duplicate across items -> deduped
    a2.insert("az3");
    mc_AccumulateMembership(clusters, "A", a2);

    std::set<std::string> b1;
    b1.insert("az9");
    mc_AccumulateMembership(clusters, "B", b1);

    BOOST_CHECK_EQUAL(clusters.size(), 2u);
    BOOST_CHECK_EQUAL(clusters["A"].size(), 3u);
    BOOST_CHECK_EQUAL(clusters["B"].size(), 1u);
    BOOST_CHECK(clusters["A"].count("az1") == 1);
    BOOST_CHECK(clusters["A"].count("az3") == 1);
}

// ---- ESG -----------------------------------------------------------------

BOOST_AUTO_TEST_CASE(esg_valid_int_and_real)
{
    Object as_int;
    as_int.push_back(Pair("node_address", std::string("AZ_1")));
    as_int.push_back(Pair("esg", (int64_t)15));
    std::string addr;
    double esg = 0.0;
    BOOST_CHECK(mc_ParseEsgRecordJson(wrap_json(as_int), addr, esg));
    BOOST_CHECK_EQUAL(addr, "AZ_1");
    BOOST_CHECK_CLOSE(esg, 15.0, 1e-9);

    Object as_real;
    as_real.push_back(Pair("node_address", std::string("AZ_2")));
    as_real.push_back(Pair("esg", 12.5));
    BOOST_CHECK(mc_ParseEsgRecordJson(wrap_json(as_real), addr, esg));
    BOOST_CHECK_CLOSE(esg, 12.5, 1e-9);
}

BOOST_AUTO_TEST_CASE(esg_wrapped_formatdata_shape)
{
    Object inner;
    inner.push_back(Pair("node_address", std::string("AZ_7")));
    inner.push_back(Pair("esg", (int64_t)11));
    std::string addr;
    double esg = 0.0;
    BOOST_CHECK(mc_ParseEsgRecordJson(wrap_formatdata(inner), addr, esg));
    BOOST_CHECK_EQUAL(addr, "AZ_7");
    BOOST_CHECK_CLOSE(esg, 11.0, 1e-9);
}

BOOST_AUTO_TEST_CASE(esg_reject_non_positive)
{
    Object zero;
    zero.push_back(Pair("node_address", std::string("AZ_1")));
    zero.push_back(Pair("esg", (int64_t)0));
    std::string addr;
    double esg = 7.0;
    BOOST_CHECK(!mc_ParseEsgRecordJson(wrap_json(zero), addr, esg));
    BOOST_CHECK_EQUAL(addr, "");
    BOOST_CHECK_EQUAL(esg, 0.0);

    Object neg;
    neg.push_back(Pair("node_address", std::string("AZ_1")));
    neg.push_back(Pair("esg", -3.0));
    BOOST_CHECK(!mc_ParseEsgRecordJson(wrap_json(neg), addr, esg));
}

BOOST_AUTO_TEST_CASE(esg_reject_nan_and_inf)
{
    Object nan_obj;
    nan_obj.push_back(Pair("node_address", std::string("AZ_1")));
    nan_obj.push_back(Pair("esg", std::numeric_limits<double>::quiet_NaN()));
    std::string addr;
    double esg = 5.0;
    BOOST_CHECK(!mc_ParseEsgRecordJson(wrap_json(nan_obj), addr, esg));

    Object inf_obj;
    inf_obj.push_back(Pair("node_address", std::string("AZ_1")));
    inf_obj.push_back(Pair("esg", std::numeric_limits<double>::infinity()));
    BOOST_CHECK(!mc_ParseEsgRecordJson(wrap_json(inf_obj), addr, esg));
}

BOOST_AUTO_TEST_CASE(esg_aggregation_newest_wins)
{
    std::map<std::string, double> latest;
    mc_AccumulateLatestEsg(latest, "AZ_1", 10.0);
    mc_AccumulateLatestEsg(latest, "AZ_1", 18.0); // re-certified
    mc_AccumulateLatestEsg(latest, "AZ_2", 12.0);

    BOOST_CHECK_EQUAL(latest.size(), 2u);
    BOOST_CHECK_CLOSE(latest["AZ_1"], 18.0, 1e-9);
    BOOST_CHECK_CLOSE(latest["AZ_2"], 12.0, 1e-9);
}

BOOST_AUTO_TEST_CASE(esg_duplicate_field_first_wins)
{
    // Two "esg" fields in one object: the first must win, deterministically.
    Object dup;
    dup.push_back(Pair("node_address", std::string("AZ_1")));
    dup.push_back(Pair("esg", (int64_t)10));
    dup.push_back(Pair("esg", (int64_t)20));
    std::string addr;
    double esg = 0.0;
    BOOST_CHECK(mc_ParseEsgRecordJson(wrap_json(dup), addr, esg));
    BOOST_CHECK_CLOSE(esg, 10.0, 1e-9);
}

// ---- activity ------------------------------------------------------------

BOOST_AUTO_TEST_CASE(activity_valid_including_zero_tau)
{
    Object inner;
    inner.push_back(Pair("node_address", std::string("AZ_1")));
    inner.push_back(Pair("tau", (int64_t)0)); // inactive node: tau == 0 is valid
    inner.push_back(Pair("epoch", (int64_t)3));

    std::string addr;
    uint32_t tau = 99, epoch = 0;
    BOOST_CHECK(mc_ParseActivityRecordJson(wrap_json(inner), addr, tau, epoch));
    BOOST_CHECK_EQUAL(addr, "AZ_1");
    BOOST_CHECK_EQUAL(tau, 0u);
    BOOST_CHECK_EQUAL(epoch, 3u);
}

BOOST_AUTO_TEST_CASE(activity_wrapped_formatdata_shape)
{
    Object inner;
    inner.push_back(Pair("node_address", std::string("AZ_5")));
    inner.push_back(Pair("tau", (int64_t)7));
    inner.push_back(Pair("epoch", (int64_t)2));
    std::string addr;
    uint32_t tau = 0, epoch = 0;
    BOOST_CHECK(mc_ParseActivityRecordJson(wrap_formatdata(inner), addr, tau, epoch));
    BOOST_CHECK_EQUAL(tau, 7u);
    BOOST_CHECK_EQUAL(epoch, 2u);
}

BOOST_AUTO_TEST_CASE(activity_accepts_integral_real_epoch)
{
    // epoch published as a real that happens to be integral (3.0) is accepted.
    Object inner;
    inner.push_back(Pair("node_address", std::string("AZ_1")));
    inner.push_back(Pair("tau", 4.0));
    inner.push_back(Pair("epoch", 3.0));
    std::string addr;
    uint32_t tau = 0, epoch = 0;
    BOOST_CHECK(mc_ParseActivityRecordJson(wrap_json(inner), addr, tau, epoch));
    BOOST_CHECK_EQUAL(tau, 4u);
    BOOST_CHECK_EQUAL(epoch, 3u);
}

BOOST_AUTO_TEST_CASE(activity_reject_bad_epoch_and_negative_tau)
{
    Object epoch0;
    epoch0.push_back(Pair("node_address", std::string("AZ_1")));
    epoch0.push_back(Pair("tau", (int64_t)5));
    epoch0.push_back(Pair("epoch", (int64_t)0)); // epoch must be >= 1
    std::string addr;
    uint32_t tau = 0, epoch = 0;
    BOOST_CHECK(!mc_ParseActivityRecordJson(wrap_json(epoch0), addr, tau, epoch));

    Object negtau;
    negtau.push_back(Pair("node_address", std::string("AZ_1")));
    negtau.push_back(Pair("tau", -1.0));
    negtau.push_back(Pair("epoch", (int64_t)2));
    BOOST_CHECK(!mc_ParseActivityRecordJson(wrap_json(negtau), addr, tau, epoch));
}

BOOST_AUTO_TEST_CASE(activity_reject_overflow_and_non_integral)
{
    std::string addr;
    uint32_t tau = 0, epoch = 0;

    // tau far beyond UINT32_MAX -> reject (do not truncate: UB territory).
    Object bigtau;
    bigtau.push_back(Pair("node_address", std::string("AZ_1")));
    bigtau.push_back(Pair("tau", 1e18));
    bigtau.push_back(Pair("epoch", (int64_t)1));
    BOOST_CHECK(!mc_ParseActivityRecordJson(wrap_json(bigtau), addr, tau, epoch));

    // epoch far beyond UINT32_MAX -> reject.
    Object bigepoch;
    bigepoch.push_back(Pair("node_address", std::string("AZ_1")));
    bigepoch.push_back(Pair("tau", (int64_t)1));
    bigepoch.push_back(Pair("epoch", 1e10));
    BOOST_CHECK(!mc_ParseActivityRecordJson(wrap_json(bigepoch), addr, tau, epoch));

    // non-integral tau -> reject (a counter must be exact).
    Object fractau;
    fractau.push_back(Pair("node_address", std::string("AZ_1")));
    fractau.push_back(Pair("tau", 3.5));
    fractau.push_back(Pair("epoch", (int64_t)1));
    BOOST_CHECK(!mc_ParseActivityRecordJson(wrap_json(fractau), addr, tau, epoch));
}

BOOST_AUTO_TEST_CASE(activity_aggregation_newest_wins)
{
    std::map<std::string, uint32_t> latest;
    mc_AccumulateLatestActivity(latest, "AZ_1", 5);
    mc_AccumulateLatestActivity(latest, "AZ_1", 9); // corrected within epoch
    mc_AccumulateLatestActivity(latest, "AZ_2", 2);
    BOOST_CHECK_EQUAL(latest.size(), 2u);
    BOOST_CHECK_EQUAL(latest["AZ_1"], 9u);
    BOOST_CHECK_EQUAL(latest["AZ_2"], 2u);
}

// ---- reconciliation ------------------------------------------------------

BOOST_AUTO_TEST_CASE(reconciliation_valid)
{
    Object inner;
    inner.push_back(Pair("node_address", std::string("MINER_A")));
    inner.push_back(Pair("reconciled", 42.5));
    inner.push_back(Pair("epoch", (int64_t)4));

    std::string miner;
    double r = 0.0;
    uint32_t epoch = 0;
    BOOST_CHECK(mc_ParseReconciliationRecordJson(wrap_json(inner), miner, r, epoch));
    BOOST_CHECK_EQUAL(miner, "MINER_A");
    BOOST_CHECK_CLOSE(r, 42.5, 1e-9);
    BOOST_CHECK_EQUAL(epoch, 4u);
}

BOOST_AUTO_TEST_CASE(reconciliation_wrapped_formatdata_shape)
{
    Object inner;
    inner.push_back(Pair("node_address", std::string("MINER_B")));
    inner.push_back(Pair("reconciled", (int64_t)10));
    inner.push_back(Pair("epoch", (int64_t)1));
    std::string miner;
    double r = 0.0;
    uint32_t epoch = 0;
    BOOST_CHECK(mc_ParseReconciliationRecordJson(wrap_formatdata(inner), miner, r, epoch));
    BOOST_CHECK_EQUAL(miner, "MINER_B");
    BOOST_CHECK_CLOSE(r, 10.0, 1e-9);
    BOOST_CHECK_EQUAL(epoch, 1u);
}

BOOST_AUTO_TEST_CASE(reconciliation_reject_negative_and_nan)
{
    std::string miner;
    double r = 1.0;
    uint32_t epoch = 0;

    Object neg;
    neg.push_back(Pair("node_address", std::string("MINER_A")));
    neg.push_back(Pair("reconciled", -0.01));
    neg.push_back(Pair("epoch", (int64_t)1));
    BOOST_CHECK(!mc_ParseReconciliationRecordJson(wrap_json(neg), miner, r, epoch));
    BOOST_CHECK_EQUAL(miner, "");

    Object nan_obj;
    nan_obj.push_back(Pair("node_address", std::string("MINER_A")));
    nan_obj.push_back(Pair("reconciled", std::numeric_limits<double>::quiet_NaN()));
    nan_obj.push_back(Pair("epoch", (int64_t)1));
    BOOST_CHECK(!mc_ParseReconciliationRecordJson(wrap_json(nan_obj), miner, r, epoch));
}

BOOST_AUTO_TEST_CASE(reconciliation_aggregation_newest_wins)
{
    std::map<std::string, double> latest;
    mc_AccumulateLatestReconciliation(latest, "MINER_A", 10.0);
    mc_AccumulateLatestReconciliation(latest, "MINER_A", 25.0); // corrected within epoch
    BOOST_CHECK_EQUAL(latest.size(), 1u);
    BOOST_CHECK_CLOSE(latest["MINER_A"], 25.0, 1e-9);
}

// ---- shared unwrap rejections -------------------------------------------

BOOST_AUTO_TEST_CASE(reject_non_object_and_missing_json_wrapper)
{
    std::string addr;
    double esg = 0.0;
    BOOST_CHECK(!mc_ParseEsgRecordJson(Value("just a string"), addr, esg));

    Object inner;
    inner.push_back(Pair("node_address", std::string("AZ_1")));
    inner.push_back(Pair("esg", (int64_t)10));
    // bare object, not wrapped in {"json": ...}
    BOOST_CHECK(!mc_ParseEsgRecordJson(Value(inner), addr, esg));
}
