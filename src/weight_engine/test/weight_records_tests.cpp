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

// ---- activity and reconciliation are NOT records ------------------------
//
// tau_i^{(e)} and R_k^{(e)} have no wire format and therefore no parser to test: both
// are DERIVED from the confirmed blocks of a buried epoch, in a single shared pass
// (WeightStreamReader::ComputeActivityAndReconciliationForEpoch). The parsers and
// accumulators that used to live here — mc_ParseActivityRecordJson,
// mc_ParseReconciliationRecordJson and their aggregators — were removed with the
// streams they served:
//
//   * weight-engine-activity was DEFINED but never created, written or read: a name,
//     not a mechanism.
//   * weight-engine-reconciliation carried an ADMIN ATTESTATION of a value the chain
//     already recorded. R is now read off the blocks instead, which is what closed the
//     asymmetry that treated one transaction fact as derived and the other as declared.
//
// What IS testable here is the RULE that decides a single transaction's contribution,
// which is deliberately kept in the pure layer rather than buried in the scan loop.
// Only the traversal itself — the buried-epoch guard and the undo-based signer
// attribution, both shared with tau — needs the block layer and is covered by
// functional_test_weight_engine.sh. Decision and rationale:
// wpoa/docs/adr/reconciliation-onchain.md.

// ---- reconciliation: which outputs count -------------------------------

static std::vector<std::string> addrs(const char* a = NULL, const char* b = NULL,
                                      const char* c = NULL)
{
    std::vector<std::string> v;
    if (a) v.push_back(a);
    if (b) v.push_back(b);
    if (c) v.push_back(c);
    return v;
}
static std::vector<int64_t> vals(int64_t a = -1, int64_t b = -1, int64_t c = -1)
{
    std::vector<int64_t> v;
    if (a >= 0) v.push_back(a);
    if (b >= 0) v.push_back(b);
    if (c >= 0) v.push_back(c);
    return v;
}
static std::set<std::string> signers(const char* a, const char* b = NULL)
{
    std::set<std::string> s;
    if (a) s.insert(a);
    if (b) s.insert(b);
    return s;
}

// A payment to the treasury counts; a miner's own change output alongside it does not.
BOOST_AUTO_TEST_CASE(reconciliation_counts_only_outputs_paying_the_treasury)
{
    BOOST_CHECK_EQUAL(mc_ValuePaidToTreasury(addrs("TREASURY"), vals(500), "TREASURY"), 500);

    // treasury 500 + change back to the miner 300 -> only the 500 counts
    BOOST_CHECK_EQUAL(
        mc_ValuePaidToTreasury(addrs("TREASURY", "MINER_A"), vals(500, 300), "TREASURY"), 500);
}

// A transfer to a third party is not a reconciliation, however large.
BOOST_AUTO_TEST_CASE(reconciliation_excludes_transfers_to_third_parties)
{
    BOOST_CHECK_EQUAL(
        mc_ValuePaidToTreasury(addrs("SOMEONE_ELSE"), vals(9999), "TREASURY"), 0);
}

// Non-monetary outputs never count. An OP_RETURN / bare-multisig / non-standard script
// has no single extractable destination, which the reader passes through as "", and a
// zero-value output carries nothing even if it is addressed to the treasury — so a
// stream item or a notarisation can never register as a reconciliation.
BOOST_AUTO_TEST_CASE(reconciliation_excludes_non_monetary_outputs)
{
    BOOST_CHECK_EQUAL(mc_ValuePaidToTreasury(addrs(""), vals(0), "TREASURY"), 0);
    BOOST_CHECK_EQUAL(mc_ValuePaidToTreasury(addrs("TREASURY"), vals(0), "TREASURY"), 0);

    // a data output next to a real payment leaves the real payment intact
    BOOST_CHECK_EQUAL(
        mc_ValuePaidToTreasury(addrs("", "TREASURY"), vals(0, 250), "TREASURY"), 250);
}

// Several outputs to the treasury in one transaction are summed.
BOOST_AUTO_TEST_CASE(reconciliation_sums_multiple_treasury_outputs)
{
    BOOST_CHECK_EQUAL(
        mc_ValuePaidToTreasury(addrs("TREASURY", "TREASURY", "MINER_A"),
                               vals(100, 250, 40), "TREASURY"), 350);
}

// Edge cases: no treasury configured, and a defensive length mismatch.
BOOST_AUTO_TEST_CASE(reconciliation_value_edge_cases)
{
    BOOST_CHECK_EQUAL(mc_ValuePaidToTreasury(addrs("TREASURY"), vals(500), ""), 0);
    std::vector<std::string> a = addrs("TREASURY", "TREASURY");
    std::vector<int64_t> v = vals(500);                     // deliberately shorter
    BOOST_CHECK_EQUAL(mc_ValuePaidToTreasury(a, v, "TREASURY"), 0);
}

// ---- reconciliation: who gets credited ---------------------------------

// The signer is credited — which is what makes the DIRECTION unambiguous.
BOOST_AUTO_TEST_CASE(reconciliation_credits_the_signing_miner)
{
    std::map<std::string, int64_t> r;
    mc_AccumulateReconciliation(r, signers("MINER_A"), 500, "TREASURY");
    BOOST_CHECK_EQUAL(r.size(), 1u);
    BOOST_CHECK_EQUAL(r["MINER_A"], 500);
}

// A transfer TO a miner is never mistaken for one FROM it: the treasury signed, so the
// recipient earns nothing. This is the case an "any address in the transaction" rule
// would have got wrong.
BOOST_AUTO_TEST_CASE(reconciliation_treasury_paying_a_miner_credits_nobody)
{
    std::map<std::string, int64_t> r;
    // The treasury pays MINER_A; the treasury is the signer, MINER_A is not.
    mc_AccumulateReconciliation(r, signers("TREASURY"), 0, "TREASURY");
    BOOST_CHECK(r.empty());

    // Even a treasury-signed transaction that does pay the treasury (a self-transfer or
    // a rebalancing) credits nobody, so it cannot inflate anyone's compliance.
    mc_AccumulateReconciliation(r, signers("TREASURY"), 500, "TREASURY");
    BOOST_CHECK(r.empty());
}

// (b) Multi-transaction aggregation within one epoch for the same miner: each call folds
// into the running total, which is how the scan loop accumulates across the epoch.
BOOST_AUTO_TEST_CASE(reconciliation_aggregates_across_transactions_in_the_epoch)
{
    std::map<std::string, int64_t> r;
    mc_AccumulateReconciliation(r, signers("MINER_A"), 100, "TREASURY");
    mc_AccumulateReconciliation(r, signers("MINER_A"), 250, "TREASURY");
    mc_AccumulateReconciliation(r, signers("MINER_A"),  50, "TREASURY");
    BOOST_CHECK_EQUAL(r.size(), 1u);
    BOOST_CHECK_EQUAL(r["MINER_A"], 400);
}

BOOST_AUTO_TEST_CASE(reconciliation_keeps_miners_separate)
{
    std::map<std::string, int64_t> r;
    mc_AccumulateReconciliation(r, signers("MINER_A"), 100, "TREASURY");
    mc_AccumulateReconciliation(r, signers("MINER_B"), 700, "TREASURY");
    BOOST_CHECK_EQUAL(r.size(), 2u);
    BOOST_CHECK_EQUAL(r["MINER_A"], 100);
    BOOST_CHECK_EQUAL(r["MINER_B"], 700);
}

// A transaction funded from several addresses has several signers, each of which
// authorized it, so each is credited — mirroring how tau counts such a transaction once
// for every distinct signing address.
BOOST_AUTO_TEST_CASE(reconciliation_credits_every_signer_of_a_multi_input_transaction)
{
    std::map<std::string, int64_t> r;
    mc_AccumulateReconciliation(r, signers("MINER_A", "MINER_B"), 500, "TREASURY");
    BOOST_CHECK_EQUAL(r["MINER_A"], 500);
    BOOST_CHECK_EQUAL(r["MINER_B"], 500);
}

// Nothing accumulates without a treasury: R is uniformly empty, deterministically and
// on every node — the same behaviour as the old model on a chain where nobody published
// a reconciliation record.
BOOST_AUTO_TEST_CASE(reconciliation_without_a_treasury_credits_nobody)
{
    std::map<std::string, int64_t> r;
    mc_AccumulateReconciliation(r, signers("MINER_A"), 500, "");
    BOOST_CHECK(r.empty());
}

BOOST_AUTO_TEST_CASE(reconciliation_ignores_non_positive_value_and_empty_signers)
{
    std::map<std::string, int64_t> r;
    mc_AccumulateReconciliation(r, signers("MINER_A"),  0, "TREASURY");
    mc_AccumulateReconciliation(r, signers("MINER_A"), -5, "TREASURY");
    mc_AccumulateReconciliation(r, std::set<std::string>(), 500, "TREASURY");
    BOOST_CHECK(r.empty());
}

// (e) DETERMINISM. Two nodes folding the same transactions of the same epoch reach the
// same totals whatever order they visit them in — the accumulation is integer addition
// into a sorted map, so there is no floating-point non-associativity to diverge on.
BOOST_AUTO_TEST_CASE(reconciliation_is_order_independent_across_nodes)
{
    std::map<std::string, int64_t> node1;
    mc_AccumulateReconciliation(node1, signers("MINER_A"), 100, "TREASURY");
    mc_AccumulateReconciliation(node1, signers("MINER_B"), 700, "TREASURY");
    mc_AccumulateReconciliation(node1, signers("MINER_A"), 250, "TREASURY");

    std::map<std::string, int64_t> node2;                    // same set, visited in reverse
    mc_AccumulateReconciliation(node2, signers("MINER_A"), 250, "TREASURY");
    mc_AccumulateReconciliation(node2, signers("MINER_B"), 700, "TREASURY");
    mc_AccumulateReconciliation(node2, signers("MINER_A"), 100, "TREASURY");

    BOOST_CHECK(node1 == node2);
    BOOST_CHECK_EQUAL(node1["MINER_A"], 350);
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
