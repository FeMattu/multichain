// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — unit tests for the pure comparison and filter that
// implement universal verification of the published weights
// (src/weight_engine/weight_verifier.h).
//
// Self-contained: depends only on Boost.Test (header-only "included" variant), NOT on
// the wallet / node runtime. Build & run with
// src/weight_engine/test/run_unit_tests.sh.
//
// WHAT THE NODE-COUPLED HALF STILL OWNS, and is therefore not covered here: running
// the recomputation itself (WeightEngineComputeAllWeightsForEpoch, which needs the
// input streams and the epoch's blocks) and the verdict cache. What is tested here is
// the decision the recomputation feeds — given a published map and a recomputed map,
// which records stand and which are dropped — plus the fail-open behaviour when no
// recomputation was possible, which is the property that keeps the mechanism from
// stalling a syncing node.
//
// Determinism between two honest nodes is tested as an equality of the two maps they
// would produce: the pipeline's own determinism is exercised by the `engine` suite
// (order independence, clamps, positivity), and what matters here is that identical
// recomputations produce identical verdicts.

#define BOOST_TEST_MODULE WeightVerifierTests
#include <boost/test/included/unit_test.hpp>

#include <map>
#include <string>

#include "weight_engine/weight_verifier.h"

typedef std::map<std::string, uint32_t> WMap;
typedef std::map<std::string, WeightVerificationEntry> VMap;

// ---- the honest case ----------------------------------------------------

BOOST_AUTO_TEST_CASE(matching_values_verify_ok_and_survive_the_filter)
{
    WMap published, recomputed;
    published["MINER_A"] = 250;  recomputed["MINER_A"] = 250;
    published["MINER_B"] = 700;  recomputed["MINER_B"] = 700;

    VMap v;
    mc_VerifyPublishedWeights(published, recomputed, true, v);

    BOOST_CHECK_EQUAL(v.size(), 2u);
    BOOST_CHECK_EQUAL(v["MINER_A"].verdict, MC_WEIGHT_VERDICT_OK);
    BOOST_CHECK_EQUAL(v["MINER_B"].verdict, MC_WEIGHT_VERDICT_OK);
    BOOST_CHECK_EQUAL(mc_CountInvalidVerdicts(v), 0u);

    WMap filtered;
    mc_FilterVerifiedWeights(published, v, filtered);
    BOOST_CHECK_EQUAL(filtered.size(), 2u);
    BOOST_CHECK_EQUAL(filtered["MINER_A"], 250u);
    BOOST_CHECK_EQUAL(filtered["MINER_B"], 700u);
}

// ---- a value that does not match the recomputation ---------------------

// The core of the mechanism: a publisher inflating its own weight is caught, its
// record is dropped from the map the election consumes, and both values are retained
// so the finding can be audited (and carried in an accusation).
BOOST_AUTO_TEST_CASE(mismatching_value_is_rejected_and_dropped)
{
    WMap published, recomputed;
    published["HONEST"] = 250;    recomputed["HONEST"] = 250;
    published["CHEATER"] = 99999; recomputed["CHEATER"] = 300;   // inflated its own weight

    VMap v;
    mc_VerifyPublishedWeights(published, recomputed, true, v);

    BOOST_CHECK_EQUAL(v["CHEATER"].verdict, MC_WEIGHT_VERDICT_MISMATCH);
    BOOST_CHECK_EQUAL(v["CHEATER"].published, 99999u);
    BOOST_CHECK_EQUAL(v["CHEATER"].recomputed, 300u);            // evidence kept
    BOOST_CHECK(mc_WeightVerdictIsInvalid(v["CHEATER"].verdict));
    BOOST_CHECK_EQUAL(mc_CountInvalidVerdicts(v), 1u);

    WMap filtered;
    mc_FilterVerifiedWeights(published, v, filtered);
    BOOST_CHECK_EQUAL(filtered.size(), 1u);
    BOOST_CHECK(filtered.find("CHEATER") == filtered.end());     // never reaches the election
    BOOST_CHECK_EQUAL(filtered["HONEST"], 250u);
}

// Understating is caught by the identical rule: the check is equality, not an upper
// bound, so a publisher cannot deviate in either direction.
BOOST_AUTO_TEST_CASE(understated_value_is_also_a_mismatch)
{
    WMap published, recomputed;
    published["MINER_A"] = 10;  recomputed["MINER_A"] = 300;

    VMap v;
    mc_VerifyPublishedWeights(published, recomputed, true, v);
    BOOST_CHECK_EQUAL(v["MINER_A"].verdict, MC_WEIGHT_VERDICT_MISMATCH);
}

// Exact integer equality, with no tolerance band: off by one is a mismatch. A
// tolerance would only create a margin for a dishonest publisher to hide in, and the
// pipeline's determinism disciplines make it unnecessary.
BOOST_AUTO_TEST_CASE(off_by_one_is_a_mismatch_no_tolerance_band)
{
    WMap published, recomputed;
    published["MINER_A"] = 251;  recomputed["MINER_A"] = 250;

    VMap v;
    mc_VerifyPublishedWeights(published, recomputed, true, v);
    BOOST_CHECK_EQUAL(v["MINER_A"].verdict, MC_WEIGHT_VERDICT_MISMATCH);
}

// ---- a weight published for something that is not a cluster ------------

BOOST_AUTO_TEST_CASE(weight_for_a_non_cluster_is_rejected_with_its_own_reason)
{
    WMap published, recomputed;
    published["MINER_A"]  = 250;  recomputed["MINER_A"] = 250;
    published["NOT_A_MINER"] = 5000;                 // heads no cluster at all

    VMap v;
    mc_VerifyPublishedWeights(published, recomputed, true, v);

    // Distinguished from MISMATCH: the fault differs, and an accurate reason makes the
    // log and any accusation auditable.
    BOOST_CHECK_EQUAL(v["NOT_A_MINER"].verdict, MC_WEIGHT_VERDICT_NOT_A_CLUSTER);
    BOOST_CHECK_EQUAL(v["NOT_A_MINER"].published, 5000u);
    BOOST_CHECK(mc_WeightVerdictIsInvalid(v["NOT_A_MINER"].verdict));

    WMap filtered;
    mc_FilterVerifiedWeights(published, v, filtered);
    BOOST_CHECK(filtered.find("NOT_A_MINER") == filtered.end());
    BOOST_CHECK_EQUAL(filtered.size(), 1u);
}

// ---- fail open when nothing could be recomputed ------------------------

// THE LIVENESS PROPERTY. A node that cannot recompute — still syncing, inputs not yet
// readable, epoch not buried — must not conclude that everybody is wrong. If it did,
// it would zero every weight and stall the chain. Every verdict is UNVERIFIED and the
// filter is a no-op.
BOOST_AUTO_TEST_CASE(failed_recomputation_leaves_every_record_untouched)
{
    WMap published;
    published["MINER_A"] = 250;
    published["MINER_B"] = 700;

    WMap empty_recomputed;                              // nothing recomputed
    VMap v;
    mc_VerifyPublishedWeights(published, empty_recomputed, false, v);

    BOOST_CHECK_EQUAL(v.size(), 2u);
    BOOST_CHECK_EQUAL(v["MINER_A"].verdict, MC_WEIGHT_VERDICT_UNVERIFIED);
    BOOST_CHECK_EQUAL(v["MINER_B"].verdict, MC_WEIGHT_VERDICT_UNVERIFIED);
    BOOST_CHECK_EQUAL(mc_CountInvalidVerdicts(v), 0u);

    WMap filtered;
    mc_FilterVerifiedWeights(published, v, filtered);
    BOOST_CHECK_EQUAL(filtered.size(), 2u);             // unchanged
    BOOST_CHECK_EQUAL(filtered["MINER_A"], 250u);
    BOOST_CHECK_EQUAL(filtered["MINER_B"], 700u);
}

// recompute_ok = false must dominate even a populated recomputed map: a partial map
// from an aborted fold must never be read as authoritative.
BOOST_AUTO_TEST_CASE(recompute_not_ok_dominates_a_populated_map)
{
    WMap published, partial;
    published["MINER_A"] = 250;
    partial["MINER_A"]   = 1;        // would be a mismatch if trusted

    VMap v;
    mc_VerifyPublishedWeights(published, partial, false, v);
    BOOST_CHECK_EQUAL(v["MINER_A"].verdict, MC_WEIGHT_VERDICT_UNVERIFIED);
    BOOST_CHECK_EQUAL(mc_CountInvalidVerdicts(v), 0u);
}

// An empty verdict map — a node that has never verified — leaves the weights alone,
// so enabling verification on a running chain is a no-op until it has run once.
BOOST_AUTO_TEST_CASE(empty_verdicts_leave_the_map_unchanged)
{
    WMap published;
    published["MINER_A"] = 250;

    VMap none;
    WMap filtered;
    mc_FilterVerifiedWeights(published, none, filtered);
    BOOST_CHECK_EQUAL(filtered.size(), 1u);
    BOOST_CHECK_EQUAL(filtered["MINER_A"], 250u);
}

// ---- determinism between two honest nodes ------------------------------

// Two honest nodes with the same chain state recompute the same map, so they reach
// the same verdicts and the same filtered weights — which is what makes a rejection
// safe: it cannot make one node drop a record its peers keep.
BOOST_AUTO_TEST_CASE(two_honest_nodes_reach_identical_verdicts)
{
    WMap published;
    published["MINER_A"] = 250;
    published["MINER_B"] = 700;
    published["CHEATER"] = 99999;

    // Same chain state -> same recomputation on both nodes.
    WMap node1, node2;
    node1["MINER_A"] = 250;  node2["MINER_A"] = 250;
    node1["MINER_B"] = 700;  node2["MINER_B"] = 700;
    node1["CHEATER"] = 300;  node2["CHEATER"] = 300;

    VMap v1, v2;
    mc_VerifyPublishedWeights(published, node1, true, v1);
    mc_VerifyPublishedWeights(published, node2, true, v2);

    BOOST_CHECK_EQUAL(v1.size(), v2.size());
    for (VMap::const_iterator it = v1.begin(); it != v1.end(); ++it)
    {
        VMap::const_iterator o = v2.find(it->first);
        BOOST_REQUIRE(o != v2.end());
        BOOST_CHECK_EQUAL(it->second.verdict, o->second.verdict);
        BOOST_CHECK_EQUAL(it->second.recomputed, o->second.recomputed);
    }

    WMap f1, f2;
    mc_FilterVerifiedWeights(published, v1, f1);
    mc_FilterVerifiedWeights(published, v2, f2);
    BOOST_CHECK(f1 == f2);
    BOOST_CHECK_EQUAL(f1.size(), 2u);
    BOOST_CHECK(f1.find("CHEATER") == f1.end());
}

// ---- edge cases --------------------------------------------------------

// A cluster that exists but has published nothing gets no entry: there is no record to
// accept or reject, and inventing one would turn "silent" into "guilty".
BOOST_AUTO_TEST_CASE(recomputed_but_unpublished_cluster_has_no_entry)
{
    WMap published, recomputed;
    published["MINER_A"] = 250;
    recomputed["MINER_A"] = 250;
    recomputed["MINER_SILENT"] = 400;      // a real cluster that published nothing

    VMap v;
    mc_VerifyPublishedWeights(published, recomputed, true, v);
    BOOST_CHECK_EQUAL(v.size(), 1u);
    BOOST_CHECK(v.find("MINER_SILENT") == v.end());
}

BOOST_AUTO_TEST_CASE(empty_published_map_yields_no_verdicts)
{
    WMap published, recomputed;
    recomputed["MINER_A"] = 250;

    VMap v;
    mc_VerifyPublishedWeights(published, recomputed, true, v);
    BOOST_CHECK(v.empty());
    BOOST_CHECK_EQUAL(mc_CountInvalidVerdicts(v), 0u);
}

BOOST_AUTO_TEST_CASE(verify_clears_stale_output)
{
    VMap v;
    v["STALE"] = WeightVerificationEntry(1, 1, MC_WEIGHT_VERDICT_OK);

    WMap published, recomputed;
    mc_VerifyPublishedWeights(published, recomputed, true, v);
    BOOST_CHECK(v.empty());
}

BOOST_AUTO_TEST_CASE(filter_clears_stale_output)
{
    WMap filtered;
    filtered["STALE"] = 7;

    WMap published;
    VMap v;
    mc_FilterVerifiedWeights(published, v, filtered);
    BOOST_CHECK(filtered.empty());
}

// Every verdict has a stable spelling, and only the two invalidating ones are treated
// as invalid — the classification is single-sourced so the filter, the logs and any
// accusation cannot disagree about what "invalid" means.
BOOST_AUTO_TEST_CASE(verdict_names_and_invalid_classification_are_stable)
{
    BOOST_CHECK_EQUAL(std::string(mc_WeightVerdictToString(MC_WEIGHT_VERDICT_OK)), "ok");
    BOOST_CHECK_EQUAL(std::string(mc_WeightVerdictToString(MC_WEIGHT_VERDICT_MISMATCH)),
                      "mismatch");
    BOOST_CHECK_EQUAL(std::string(mc_WeightVerdictToString(MC_WEIGHT_VERDICT_NOT_A_CLUSTER)),
                      "not-a-cluster");
    BOOST_CHECK_EQUAL(std::string(mc_WeightVerdictToString(MC_WEIGHT_VERDICT_UNVERIFIED)),
                      "unverified");

    BOOST_CHECK(!mc_WeightVerdictIsInvalid(MC_WEIGHT_VERDICT_OK));
    BOOST_CHECK(!mc_WeightVerdictIsInvalid(MC_WEIGHT_VERDICT_UNVERIFIED));
    BOOST_CHECK(mc_WeightVerdictIsInvalid(MC_WEIGHT_VERDICT_MISMATCH));
    BOOST_CHECK(mc_WeightVerdictIsInvalid(MC_WEIGHT_VERDICT_NOT_A_CLUSTER));
}
