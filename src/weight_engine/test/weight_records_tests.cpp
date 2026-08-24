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
#include <vector>
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

// A self-attested membership record: {node_address, miner_address, timestamp}.
static Object membership_obj(const std::string& node, const std::string& miner,
                             int64_t ts = 1700000000)
{
    Object o;
    o.push_back(Pair("node_address", node));
    o.push_back(Pair("miner_address", miner));
    o.push_back(Pair("timestamp", ts));
    return o;
}

// ---- membership: self-attested {node -> miner} record ---------------------

BOOST_AUTO_TEST_CASE(membership_record_parses_node_miner_timestamp)
{
    std::string node, miner;
    uint32_t ts = 0;
    BOOST_CHECK(mc_ParseMembershipRecordJson(
        wrap_json(membership_obj("AZ_1", "MINER_A", 1700000123)), node, miner, ts));
    BOOST_CHECK_EQUAL(node, "AZ_1");
    BOOST_CHECK_EQUAL(miner, "MINER_A");
    BOOST_CHECK_EQUAL(ts, 1700000123u);
}

BOOST_AUTO_TEST_CASE(membership_wrapped_formatdata_shape)
{
    std::string node, miner;
    uint32_t ts = 0;
    BOOST_CHECK(mc_ParseMembershipRecordJson(
        wrap_formatdata(membership_obj("AZ_9", "MINER_B")), node, miner, ts));
    BOOST_CHECK_EQUAL(node, "AZ_9");
    BOOST_CHECK_EQUAL(miner, "MINER_B");
}

// A miner declaring itself is legal and is what registers it as a cluster head.
BOOST_AUTO_TEST_CASE(membership_miner_may_declare_itself)
{
    std::string node, miner;
    uint32_t ts = 0;
    BOOST_CHECK(mc_ParseMembershipRecordJson(
        wrap_json(membership_obj("MINER_A", "MINER_A")), node, miner, ts));
    BOOST_CHECK_EQUAL(node, "MINER_A");
    BOOST_CHECK_EQUAL(miner, "MINER_A");
}

BOOST_AUTO_TEST_CASE(membership_reject_missing_or_empty_fields)
{
    std::string node = "stale", miner = "stale";
    uint32_t ts = 99;

    // miner_address missing entirely
    Object no_miner;
    no_miner.push_back(Pair("node_address", std::string("AZ_1")));
    no_miner.push_back(Pair("timestamp", (int64_t)1700000000));
    BOOST_CHECK(!mc_ParseMembershipRecordJson(wrap_json(no_miner), node, miner, ts));
    BOOST_CHECK(node.empty());
    BOOST_CHECK(miner.empty());
    BOOST_CHECK_EQUAL(ts, 0u);

    // node_address missing
    Object no_node;
    no_node.push_back(Pair("miner_address", std::string("MINER_A")));
    no_node.push_back(Pair("timestamp", (int64_t)1700000000));
    BOOST_CHECK(!mc_ParseMembershipRecordJson(wrap_json(no_node), node, miner, ts));

    // timestamp missing
    Object no_ts;
    no_ts.push_back(Pair("node_address", std::string("AZ_1")));
    no_ts.push_back(Pair("miner_address", std::string("MINER_A")));
    BOOST_CHECK(!mc_ParseMembershipRecordJson(wrap_json(no_ts), node, miner, ts));

    // empty address strings
    BOOST_CHECK(!mc_ParseMembershipRecordJson(wrap_json(membership_obj("", "MINER_A")),
                                              node, miner, ts));
    BOOST_CHECK(!mc_ParseMembershipRecordJson(wrap_json(membership_obj("AZ_1", "")),
                                              node, miner, ts));
}

BOOST_AUTO_TEST_CASE(membership_reject_non_integer_and_out_of_range_timestamp)
{
    std::string node, miner;
    uint32_t ts = 0;

    Object frac;
    frac.push_back(Pair("node_address", std::string("AZ_1")));
    frac.push_back(Pair("miner_address", std::string("MINER_A")));
    frac.push_back(Pair("timestamp", 1700000000.5));
    BOOST_CHECK(!mc_ParseMembershipRecordJson(wrap_json(frac), node, miner, ts));

    Object big;
    big.push_back(Pair("node_address", std::string("AZ_1")));
    big.push_back(Pair("miner_address", std::string("MINER_A")));
    big.push_back(Pair("timestamp", 1e18));
    BOOST_CHECK(!mc_ParseMembershipRecordJson(wrap_json(big), node, miner, ts));

    Object neg;
    neg.push_back(Pair("node_address", std::string("AZ_1")));
    neg.push_back(Pair("miner_address", std::string("MINER_A")));
    neg.push_back(Pair("timestamp", (int64_t)-1));
    BOOST_CHECK(!mc_ParseMembershipRecordJson(wrap_json(neg), node, miner, ts));
}

BOOST_AUTO_TEST_CASE(membership_reject_non_object_and_missing_wrapper)
{
    std::string node, miner;
    uint32_t ts = 0;
    BOOST_CHECK(!mc_ParseMembershipRecordJson(Value("just a string"), node, miner, ts));
    // bare object, not wrapped in {"json": ...}
    BOOST_CHECK(!mc_ParseMembershipRecordJson(Value(membership_obj("AZ_1", "MINER_A")),
                                              node, miner, ts));
}

// ---- membership self-attestation (the consensus-critical validity rule) --

// (a) A node declaring itself is accepted.
BOOST_AUTO_TEST_CASE(membership_self_declaration_is_accepted)
{
    std::vector<std::string> publishers;
    publishers.push_back("AZ_1");
    BOOST_CHECK(mc_MembershipRecordIsSelfAttested("AZ_1", publishers));
}

// (b) Node A trying to declare a record with node_address = B is rejected: the
// payload claims B, but only A signed. This is the forged-record case, and the
// reader must DISCARD it rather than fold it into C_k.
BOOST_AUTO_TEST_CASE(membership_foreign_declaration_is_rejected)
{
    std::vector<std::string> publishers;
    publishers.push_back("AZ_A");
    BOOST_CHECK(!mc_MembershipRecordIsSelfAttested("AZ_B", publishers));
}

// An admin signing on a company's behalf is rejected on exactly the same ground:
// privilege is irrelevant to the rule, only the signature counts.
BOOST_AUTO_TEST_CASE(membership_admin_proxy_declaration_is_rejected)
{
    std::vector<std::string> publishers;
    publishers.push_back("ADMIN");
    BOOST_CHECK(!mc_MembershipRecordIsSelfAttested("AZ_1", publishers));
}

// A multi-input transaction has several publishers; the declaration holds if the
// declared node is any of them, since each one authorized the transaction.
BOOST_AUTO_TEST_CASE(membership_multi_publisher_accepts_when_declarer_signed)
{
    std::vector<std::string> publishers;
    publishers.push_back("FUNDER");
    publishers.push_back("AZ_1");
    BOOST_CHECK(mc_MembershipRecordIsSelfAttested("AZ_1", publishers));
    BOOST_CHECK(!mc_MembershipRecordIsSelfAttested("AZ_2", publishers));
}

// Edge cases: fail closed. An item whose signer could not be recovered, or an empty
// declared address, is never self-attested.
BOOST_AUTO_TEST_CASE(membership_self_attestation_fails_closed)
{
    std::vector<std::string> none;
    BOOST_CHECK(!mc_MembershipRecordIsSelfAttested("AZ_1", none));

    std::vector<std::string> publishers;
    publishers.push_back("AZ_1");
    BOOST_CHECK(!mc_MembershipRecordIsSelfAttested("", publishers));

    std::vector<std::string> empty_pub;
    empty_pub.push_back("");
    BOOST_CHECK(!mc_MembershipRecordIsSelfAttested("", empty_pub));
}

// ---- membership aggregation: last confirmed wins, then invert to C_k -----

BOOST_AUTO_TEST_CASE(membership_latest_declaration_wins_per_node)
{
    std::map<std::string, std::string> node_to_miner;
    mc_AccumulateLatestMembership(node_to_miner, "AZ_1", "MINER_A");
    mc_AccumulateLatestMembership(node_to_miner, "AZ_1", "MINER_B"); // moved cluster
    BOOST_CHECK_EQUAL(node_to_miner.size(), 1u);
    BOOST_CHECK_EQUAL(node_to_miner["AZ_1"], "MINER_B");
}

// (c) A node that changes cluster twice: only the last declaration counts, and the
// superseded memberships leave no trace in any cluster.
BOOST_AUTO_TEST_CASE(membership_two_cluster_changes_only_last_counts)
{
    std::map<std::string, std::string> node_to_miner;
    mc_AccumulateLatestMembership(node_to_miner, "MINER_A", "MINER_A"); // heads register
    mc_AccumulateLatestMembership(node_to_miner, "MINER_B", "MINER_B");
    mc_AccumulateLatestMembership(node_to_miner, "MINER_C", "MINER_C");

    mc_AccumulateLatestMembership(node_to_miner, "AZ_1", "MINER_A");
    mc_AccumulateLatestMembership(node_to_miner, "AZ_1", "MINER_B");
    mc_AccumulateLatestMembership(node_to_miner, "AZ_1", "MINER_C");

    std::map<std::string, std::set<std::string> > clusters;
    mc_BuildClustersFromMembership(node_to_miner, clusters);

    BOOST_CHECK_EQUAL(clusters.size(), 3u);
    BOOST_CHECK(clusters["MINER_A"].empty());               // superseded, left empty
    BOOST_CHECK(clusters["MINER_B"].empty());               // superseded, left empty
    BOOST_CHECK_EQUAL(clusters["MINER_C"].size(), 1u);
    BOOST_CHECK(clusters["MINER_C"].count("AZ_1") == 1);
}

BOOST_AUTO_TEST_CASE(membership_build_clusters_inverts_relation)
{
    std::map<std::string, std::string> node_to_miner;
    node_to_miner["AZ_1"] = "MINER_A";
    node_to_miner["AZ_2"] = "MINER_A";
    node_to_miner["AZ_3"] = "MINER_B";

    std::map<std::string, std::set<std::string> > clusters;
    mc_BuildClustersFromMembership(node_to_miner, clusters);

    BOOST_CHECK_EQUAL(clusters.size(), 2u);
    BOOST_CHECK_EQUAL(clusters["MINER_A"].size(), 2u);
    BOOST_CHECK(clusters["MINER_A"].count("AZ_1") == 1);
    BOOST_CHECK(clusters["MINER_A"].count("AZ_2") == 1);
    BOOST_CHECK_EQUAL(clusters["MINER_B"].size(), 1u);
    BOOST_CHECK(clusters["MINER_B"].count("AZ_3") == 1);
}

// Rule 1: a self-declaration registers the cluster head even with no companies.
// Rule 2: the miner is never listed among its own companies — its activity already
// enters W_k through the separate tau_Mk term, so counting it as a company would
// double-count it.
BOOST_AUTO_TEST_CASE(membership_self_declaration_registers_head_without_self_membership)
{
    std::map<std::string, std::string> node_to_miner;
    node_to_miner["MINER_A"] = "MINER_A";     // head, no companies yet

    std::map<std::string, std::set<std::string> > clusters;
    mc_BuildClustersFromMembership(node_to_miner, clusters);

    BOOST_CHECK_EQUAL(clusters.size(), 1u);
    BOOST_CHECK(clusters.find("MINER_A") != clusters.end());
    BOOST_CHECK(clusters["MINER_A"].empty());

    node_to_miner["AZ_1"] = "MINER_A";
    mc_BuildClustersFromMembership(node_to_miner, clusters);
    BOOST_CHECK_EQUAL(clusters["MINER_A"].size(), 1u);
    BOOST_CHECK(clusters["MINER_A"].count("MINER_A") == 0);   // still not its own company
    BOOST_CHECK(clusters["MINER_A"].count("AZ_1") == 1);
}

// A company may join a cluster whose head never self-declared: the cluster key is
// created by the join itself, so C_k is never lost, but no weight is published for a
// miner that has not registered (ComputeLocalWeightForEpoch's own test).
BOOST_AUTO_TEST_CASE(membership_join_creates_cluster_key_without_head_declaration)
{
    std::map<std::string, std::string> node_to_miner;
    node_to_miner["AZ_1"] = "MINER_X";

    std::map<std::string, std::set<std::string> > clusters;
    mc_BuildClustersFromMembership(node_to_miner, clusters);

    BOOST_CHECK_EQUAL(clusters.size(), 1u);
    BOOST_CHECK_EQUAL(clusters["MINER_X"].size(), 1u);
}

BOOST_AUTO_TEST_CASE(membership_build_clusters_clears_stale_output)
{
    std::map<std::string, std::set<std::string> > clusters;
    clusters["STALE"].insert("garbage");

    std::map<std::string, std::string> empty;
    mc_BuildClustersFromMembership(empty, clusters);
    BOOST_CHECK(clusters.empty());
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
