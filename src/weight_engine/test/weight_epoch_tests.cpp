// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — unit tests for the pure core behind the read-only EPOCH
// AUDIT RPCs (weightgetnodecontribution / weightlistclusterweights /
// weightgetnodeearnings / weightgetnodebalance and their siblings, implemented in
// src/rpc/rpcweightengine.cpp).
//
// The RPCs add NO new mathematics: each family prints one step of the pipeline
// WeightEngine already computes. What IS new is the finality bound they share with
// the publishing thread — WeightEngine::LastBuriedEpoch, extracted here from the
// thread's inline arithmetic — so that is pinned first, followed by the edge cases
// the audit surface must report as values rather than as errors:
//
//   * an inactive cluster (W_k = 0), and an inactive company (c_i = 0);
//   * epoch 1 (no previous rate to feed back) versus epoch 2;
//   * no treasury address configured, i.e. R_k = 0 and phi_k = 0 everywhere;
//   * a non-positive saldo, which must yield phi_k = 0 rather than a division by zero.
//
// Self-contained: depends only on the WeightEngine header and Boost.Test
// (header-only), NOT on the wallet / node runtime. Build & run with
//   src/weight_engine/test/run_unit_tests.sh epoch

#define BOOST_TEST_MODULE WeightEpochAuditTests
#include <boost/test/included/unit_test.hpp>

#include <cmath>
#include <map>
#include <string>
#include <vector>

#include "weight_engine/weight_engine.h"

static const int MARGIN = MC_WEIGHT_DEFAULT_STABILITY_MARGIN;   // 6

// ---------------------------------------------------------------------------
// LastBuriedEpoch — the finality bound the audit RPCs refuse past
// ---------------------------------------------------------------------------

BOOST_AUTO_TEST_SUITE(weight_epoch_finality)

// Epoch e spans heights [(e-1)*len, e*len - 1], so it is buried once its last height
// sits `margin` below the tip. With len = 10 and margin = 6, epoch 1 ends at height 9
// and becomes buried exactly at tip 15.
BOOST_AUTO_TEST_CASE(boundary_is_exact)
{
    const int len = 10;

    BOOST_CHECK_EQUAL(WeightEngine::LastBuriedEpoch(14, len, MARGIN), 0u);  // 9 > 14-6=8
    BOOST_CHECK_EQUAL(WeightEngine::LastBuriedEpoch(15, len, MARGIN), 1u);  // 9 <= 15-6=9
    BOOST_CHECK_EQUAL(WeightEngine::LastBuriedEpoch(24, len, MARGIN), 1u);
    BOOST_CHECK_EQUAL(WeightEngine::LastBuriedEpoch(25, len, MARGIN), 2u);  // 19 <= 19
}

// EDGE CASE: a chain too young for anything to be final. The RPCs turn a 0 here into
// "epoch not yet finalized" rather than computing over blocks a reorg can replace.
BOOST_AUTO_TEST_CASE(young_chain_has_nothing_buried)
{
    const int len = 10;
    for (int tip = 0; tip < 15; tip++)
    {
        BOOST_CHECK_EQUAL(WeightEngine::LastBuriedEpoch(tip, len, MARGIN), 0u);
    }
}

// The bound is monotone in the tip: burying never un-buries an epoch.
BOOST_AUTO_TEST_CASE(monotone_in_tip_height)
{
    const int len = 7;
    uint32_t prev = 0;
    for (int tip = 0; tip < 200; tip++)
    {
        uint32_t e = WeightEngine::LastBuriedEpoch(tip, len, MARGIN);
        BOOST_CHECK(e >= prev);
        prev = e;
    }
}

// Degenerate configuration must fail closed, never wrap or divide by zero.
BOOST_AUTO_TEST_CASE(invalid_configuration_buries_nothing)
{
    BOOST_CHECK_EQUAL(WeightEngine::LastBuriedEpoch(1000, 0, MARGIN), 0u);
    BOOST_CHECK_EQUAL(WeightEngine::LastBuriedEpoch(1000, -5, MARGIN), 0u);
    BOOST_CHECK_EQUAL(WeightEngine::LastBuriedEpoch(-1, 10, MARGIN), 0u);
    BOOST_CHECK_EQUAL(WeightEngine::LastBuriedEpoch(1000, 10, -1), 0u);
}

// A zero margin means "buried as soon as the epoch closes" — the arithmetic still has
// to land on the right epoch.
BOOST_AUTO_TEST_CASE(zero_margin_buries_on_close)
{
    const int len = 10;
    BOOST_CHECK_EQUAL(WeightEngine::LastBuriedEpoch(8, len, 0), 0u);
    BOOST_CHECK_EQUAL(WeightEngine::LastBuriedEpoch(9, len, 0), 1u);
}

BOOST_AUTO_TEST_SUITE_END()

// ---------------------------------------------------------------------------
// The quantities each RPC family prints
// ---------------------------------------------------------------------------

BOOST_AUTO_TEST_SUITE(weight_epoch_quantities)

// weightgetnodecontribution: c_i = ESG_i * tau_i / kappa.
BOOST_AUTO_TEST_CASE(contribution_matches_the_definition)
{
    BOOST_CHECK_CLOSE(WeightEngine::CompanyContribution(2.0, 30, 10.0), 6.0, 1e-9);
}

// EDGE CASE: an inactive company contributes exactly nothing, whatever its ESG score.
// The RPC prints 0, not an error — inactivity is a legitimate state.
BOOST_AUTO_TEST_CASE(inactive_company_contributes_zero)
{
    BOOST_CHECK_EQUAL(WeightEngine::CompanyContribution(9.9, 0, 10.0), 0.0);
}

// weightgetnodeclusterweight: W_k = ESG_Mk * (tau_Mk + sum_i c_i).
BOOST_AUTO_TEST_CASE(raw_cluster_weight_matches_the_definition)
{
    WeightEngine::ClusterInput in;
    in.miner     = "miner_a";
    in.esg_miner = 3.0;
    in.tau_miner = 4;
    in.companies.push_back(WeightEngine::Company("c_b", 2.0, 30));   // c = 6
    in.companies.push_back(WeightEngine::Company("c_a", 1.0, 10));   // c = 1

    // 3 * (4 + 6 + 1) = 33
    BOOST_CHECK_CLOSE(WeightEngine::RawWeight(in, 10.0), 33.0, 1e-9);
}

// EDGE CASE: a totally inactive cluster. W_k = 0 exactly when the miner and every
// member are inactive, which the RPC reports as a raw weight of 0 (and the published
// weight then floors at 1, which weightlistclusterweights shows separately).
BOOST_AUTO_TEST_CASE(inactive_cluster_has_zero_raw_weight)
{
    WeightEngine::ClusterInput in;
    in.miner     = "miner_a";
    in.esg_miner = 5.0;
    in.tau_miner = 0;
    in.companies.push_back(WeightEngine::Company("c_a", 4.0, 0));

    BOOST_CHECK_EQUAL(WeightEngine::RawWeight(in, 10.0), 0.0);
    BOOST_CHECK_EQUAL(WeightEngine::ToIntegerWeight(0.0, 10.0), 1u);   // stream floor
}

// weightgetnodeearnings: g_k = Entrate - Uscite, with this epoch's own R added back
// because the reader hands over GROSS debits.
BOOST_AUTO_TEST_CASE(gain_excludes_this_epochs_restitution)
{
    // credits 100, gross debits 40 of which 15 was the restitution.
    BOOST_CHECK_CLOSE(WeightEngine::Gain(100.0, 40.0, 15.0), 75.0, 1e-9);

    // Without the exclusion it would be 60 — the difference is exactly R.
    BOOST_CHECK_CLOSE(WeightEngine::Gain(100.0, 40.0, 0.0), 60.0, 1e-9);
}

// A cluster may legitimately spend more than it received in an epoch; the audit prints
// the negative gain rather than clamping it.
BOOST_AUTO_TEST_CASE(gain_may_be_negative)
{
    BOOST_CHECK_CLOSE(WeightEngine::Gain(10.0, 50.0, 0.0), -40.0, 1e-9);
}

// weightgetnodebalance: saldo_k = saldo_k(e-1) + g_k, from saldo_k(0) = 0.
BOOST_AUTO_TEST_CASE(balance_is_the_running_total)
{
    double saldo = 0.0;
    saldo = WeightEngine::Saldo(saldo, 30.0);
    BOOST_CHECK_CLOSE(saldo, 30.0, 1e-9);
    saldo = WeightEngine::Saldo(saldo, -10.0);
    BOOST_CHECK_CLOSE(saldo, 20.0, 1e-9);
    saldo = WeightEngine::Saldo(saldo, 5.0);
    BOOST_CHECK_CLOSE(saldo, 25.0, 1e-9);
}

// weightgetnodeearnings, return_rate: phi_k = R_k / saldo_k in [0,1].
BOOST_AUTO_TEST_CASE(return_rate_matches_the_definition)
{
    BOOST_CHECK_CLOSE(WeightEngine::RestitutionRate(25.0, 100.0), 0.25, 1e-9);
    BOOST_CHECK_CLOSE(WeightEngine::RestitutionRate(100.0, 100.0), 1.0, 1e-9);
}

// EDGE CASE: no treasury address configured. R is uniformly 0, so phi is 0 for every
// cluster — a legitimate, deterministic configuration, and a uniform scaling of w_k
// that leaves the relative weights (and so the election) untouched.
BOOST_AUTO_TEST_CASE(no_treasury_means_zero_rate_everywhere)
{
    BOOST_CHECK_EQUAL(WeightEngine::RestitutionRate(0.0, 500.0), 0.0);
    BOOST_CHECK_EQUAL(WeightEngine::RestitutionRate(0.0, 1.0), 0.0);
}

// EDGE CASE: a non-positive saldo. The defined value is 0, never NaN or infinity —
// this is the degeneration that turned the reference simulation into #DIV/0!.
BOOST_AUTO_TEST_CASE(non_positive_balance_yields_zero_rate)
{
    BOOST_CHECK_EQUAL(WeightEngine::RestitutionRate(10.0, 0.0), 0.0);
    BOOST_CHECK_EQUAL(WeightEngine::RestitutionRate(10.0, -50.0), 0.0);
}

BOOST_AUTO_TEST_SUITE_END()

// ---------------------------------------------------------------------------
// The inter-epoch feedback the cluster-weight RPC exposes on its own
// ---------------------------------------------------------------------------

BOOST_AUTO_TEST_SUITE(weight_epoch_feedback)

// EDGE CASE: epoch 1. w_k = W_k by construction and there is no previous rate, which
// weightgetnodeclusterweight reports as previous_epoch_return_rate = null.
BOOST_AUTO_TEST_CASE(epoch_one_has_no_feedback)
{
    BOOST_CHECK_CLOSE(WeightEngine::FinalWeight(80.0, 0.0, 0.5, 1), 80.0, 1e-9);
    // Even a rate that would damp heavily is ignored at epoch 1.
    BOOST_CHECK_CLOSE(WeightEngine::FinalWeight(80.0, 0.0, 0.9, 1), 80.0, 1e-9);
}

// From epoch 2 the bracket is a convex combination of phi and 1.
BOOST_AUTO_TEST_CASE(epoch_two_applies_the_previous_rate)
{
    // 80 * (0.25*0.5 + 0.5) = 80 * 0.625 = 50
    BOOST_CHECK_CLOSE(WeightEngine::FinalWeight(80.0, 0.25, 0.5, 2), 50.0, 1e-9);
}

// lambda_w < 1 is a CORRECTNESS requirement, not a tuning choice: it keeps the bracket
// in [1-lambda_w, 1] and therefore w_k > 0 whenever W_k > 0, for every history of phi.
BOOST_AUTO_TEST_CASE(positive_raw_weight_stays_positive)
{
    const double lambda = 0.9;
    for (int i = 0; i <= 10; i++)
    {
        double phi = i / 10.0;
        double w = WeightEngine::FinalWeight(80.0, phi, lambda, 2);
        BOOST_CHECK(w > 0.0);
        BOOST_CHECK(w <= 80.0 + 1e-9);
        BOOST_CHECK(w >= 80.0 * (1.0 - lambda) - 1e-9);
    }
}

// EDGE CASE: W_k = 0 propagates to w_k = 0 whatever the feedback — the inactive
// cluster of Oss. cluster-inattivo, excluded from the round but not penalised.
BOOST_AUTO_TEST_CASE(zero_raw_weight_stays_zero)
{
    BOOST_CHECK_EQUAL(WeightEngine::FinalWeight(0.0, 1.0, 0.5, 2), 0.0);
    BOOST_CHECK_EQUAL(WeightEngine::FinalWeight(0.0, 0.0, 0.5, 5), 0.0);
}

// The whole chain, as weightlistclusterweights prints it for one cluster over two
// epochs: the epoch-1 weight feeds nothing back, the epoch-2 weight consumes phi^(1).
BOOST_AUTO_TEST_CASE(two_epoch_fold_matches_the_pipeline)
{
    WeightEngine::Params params(10.0, 1.0, 0.5);   // kappa, alpha (unused), lambda_w

    std::vector<WeightEngine::ClusterInput> inputs(1);
    inputs[0].miner      = "miner_a";
    inputs[0].esg_miner  = 2.0;
    inputs[0].tau_miner  = 5;
    inputs[0].companies.push_back(WeightEngine::Company("c_a", 4.0, 25));  // c = 10
    inputs[0].credits    = 100.0;
    inputs[0].debits     = 40.0;    // gross, restitution inside
    inputs[0].restituted = 20.0;

    std::map<std::string, WeightEngine::ClusterState> state, next;
    std::map<std::string, WeightEngine::ClusterResult> results;

    WeightEngine::ComputeEpoch(inputs, state, params, 1, results, next);

    const WeightEngine::ClusterResult& r1 = results["miner_a"];
    BOOST_CHECK_CLOSE(r1.raw_weight, 2.0 * (5.0 + 10.0), 1e-9);      // W = 30
    BOOST_CHECK_CLOSE(r1.gain, 100.0 - 40.0 + 20.0, 1e-9);           // g = 80
    BOOST_CHECK_CLOSE(r1.saldo, 80.0, 1e-9);                         // saldo(0)=0
    BOOST_CHECK_CLOSE(r1.restitution, 20.0 / 80.0, 1e-9);            // phi = 0.25
    BOOST_CHECK_CLOSE(r1.weight, 30.0, 1e-9);                        // e = 1 -> w = W

    // Epoch 2 with the same inputs: saldo accumulates, and w now consumes phi^(1).
    state = next;
    WeightEngine::ComputeEpoch(inputs, state, params, 2, results, next);

    const WeightEngine::ClusterResult& r2 = results["miner_a"];
    BOOST_CHECK_CLOSE(r2.saldo, 160.0, 1e-9);                        // 80 + 80
    BOOST_CHECK_CLOSE(r2.restitution, 20.0 / 160.0, 1e-9);           // phi^(2) = 0.125
    BOOST_CHECK_CLOSE(r2.weight, 30.0 * (0.25 * 0.5 + 0.5), 1e-9);   // uses phi^(1)
}

BOOST_AUTO_TEST_SUITE_END()
