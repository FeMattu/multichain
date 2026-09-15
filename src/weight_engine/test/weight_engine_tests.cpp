// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W2: unit tests for the pure weight-computation
// core (src/weight_engine/weight_engine.h).
//
// Self-contained: depend only on the WeightEngine header and Boost.Test
// (header-only "included" variant), NOT on the wallet / node runtime. Build & run
// with src/weight_engine/test/run_unit_tests.sh.
//
// The expected numbers are hand-computed from the "Gestione del peso" thesis
// definitions (restitution-rate formulation: g_k -> saldo_k -> rho_k -> w_k).

#define BOOST_TEST_MODULE WeightEngineTests
#include <boost/test/included/unit_test.hpp>

#include <cmath>
#include <limits>
#include <map>
#include <string>
#include <vector>

#include "weight_engine/weight_engine.h"

typedef WeightEngine::Company       Company;
typedef WeightEngine::ClusterInput  ClusterInput;
typedef WeightEngine::ClusterState  ClusterState;
typedef WeightEngine::ClusterResult ClusterResult;
typedef WeightEngine::Params        Params;

// A canonical single cluster used across several tests:
//   miner ESG = 10, tau_M = 20; companies AZ_1{esg 10, tau 50}, AZ_2{esg 20, tau 10}
//   -> c1 = 5, c2 = 2, sum c = 7, W_k = 10 * (20 + 7) = 270
static ClusterInput canonical_cluster(double restituted, double credits, double debits)
{
    ClusterInput in;
    in.miner = "MINER_M";
    in.esg_miner = 10.0;
    in.tau_miner = 20;
    in.companies.push_back(Company("AZ_1", 10.0, 50));
    in.companies.push_back(Company("AZ_2", 20.0, 10));
    in.restituted = restituted;
    in.credits = credits;
    in.debits = debits;
    return in;
}

// ---- scalar: contribution and raw weight ---------------------------------

BOOST_AUTO_TEST_CASE(company_contribution)
{
    BOOST_CHECK_CLOSE(WeightEngine::CompanyContribution(10.0, 50, 100.0), 5.0, 1e-9);
    BOOST_CHECK_CLOSE(WeightEngine::CompanyContribution(20.0, 10, 100.0), 2.0, 1e-9);
    // tau = 0 (inactive company) contributes nothing (Def. contributo-pesato).
    BOOST_CHECK_CLOSE(WeightEngine::CompanyContribution(20.0, 0, 100.0), 0.0, 1e-9);
}

BOOST_AUTO_TEST_CASE(raw_weight_matches_thesis)
{
    ClusterInput in = canonical_cluster(0.0, 0.0, 0.0);
    BOOST_CHECK_CLOSE(WeightEngine::RawWeight(in, 100.0), 270.0, 1e-9);
}

BOOST_AUTO_TEST_CASE(raw_weight_is_company_order_independent)
{
    // Same companies supplied in the opposite order must give the identical
    // floating-point W_k (deterministic ascending-address summation).
    ClusterInput a = canonical_cluster(0.0, 0.0, 0.0);

    ClusterInput b;
    b.miner = "MINER_M";
    b.esg_miner = 10.0;
    b.tau_miner = 20;
    b.companies.push_back(Company("AZ_2", 20.0, 10));
    b.companies.push_back(Company("AZ_1", 10.0, 50));

    BOOST_CHECK_EQUAL(WeightEngine::RawWeight(a, 100.0), WeightEngine::RawWeight(b, 100.0));
}

// ---- scalar: gain, saldo and restitution rate (the feedback recursion) ----

BOOST_AUTO_TEST_CASE(gain_excludes_the_epochs_own_restitution)
{
    // g_k = credits - debits_gross + R. The reader hands over GROSS debits (the
    // restitution still inside), so adding R back is what "Uscite ESCLUSA la
    // restituzione dell'epoca stessa" means in code.
    BOOST_CHECK_CLOSE(WeightEngine::Gain(100.0, 30.0, 0.0), 70.0, 1e-9);
    BOOST_CHECK_CLOSE(WeightEngine::Gain(100.0, 100.0, 100.0), 100.0, 1e-9);
    BOOST_CHECK_CLOSE(WeightEngine::Gain(100.0, 40.0, 25.0), 85.0, 1e-9);
    // Spending more than received is representable: g may be negative.
    BOOST_CHECK_CLOSE(WeightEngine::Gain(10.0, 50.0, 0.0), -40.0, 1e-9);
    // A negative R cannot inflate the gain (clamped at 0 before being added back).
    BOOST_CHECK_CLOSE(WeightEngine::Gain(100.0, 30.0, -50.0), 70.0, 1e-9);
}

BOOST_AUTO_TEST_CASE(saldo_is_the_cumulative_recursion)
{
    // saldo^(0) = 0; saldo^(e) = saldo^(e-1) + g^(e).
    double saldo = 0.0;
    saldo = WeightEngine::Saldo(saldo, 100.0);
    BOOST_CHECK_CLOSE(saldo, 100.0, 1e-9);
    saldo = WeightEngine::Saldo(saldo, 50.0);
    BOOST_CHECK_CLOSE(saldo, 150.0, 1e-9);
    // A negative gain draws the running total down rather than being floored.
    saldo = WeightEngine::Saldo(saldo, -200.0);
    BOOST_CHECK_CLOSE(saldo, -50.0, 1e-9);
}

BOOST_AUTO_TEST_CASE(restitution_rate_basic_and_bounds)
{
    BOOST_CHECK_CLOSE(WeightEngine::RestitutionRate(6.0, 12.0), 0.5, 1e-9);
    BOOST_CHECK_CLOSE(WeightEngine::RestitutionRate(3.0, 18.0), 1.0 / 6.0, 1e-6);
    // Returning the whole saldo is the maximum: rho == 1.
    BOOST_CHECK_CLOSE(WeightEngine::RestitutionRate(12.0, 12.0), 1.0, 1e-9);
    // R above the saldo is clamped -> rho == 1, never > 1 (Oss. limite-restituzione).
    BOOST_CHECK_CLOSE(WeightEngine::RestitutionRate(1000.0, 12.0), 1.0, 1e-9);
    // Negative R -> 0, never a negative rate.
    BOOST_CHECK_EQUAL(WeightEngine::RestitutionRate(-5.0, 12.0), 0.0);
    // Non-positive saldo -> 0 (the #DIV/0! avoidance), not NaN/Inf.
    BOOST_CHECK_EQUAL(WeightEngine::RestitutionRate(5.0, 0.0), 0.0);
    BOOST_CHECK_EQUAL(WeightEngine::RestitutionRate(5.0, -30.0), 0.0);
}

BOOST_AUTO_TEST_CASE(restitution_rate_stays_in_unit_interval_for_arbitrary_inputs)
{
    // The positivity proof of w_k consumes rho in [0,1] and nothing else, so pin it
    // across the whole input grid rather than at the handful of points above.
    const double rs[] = {-100.0, -1.0, 0.0, 0.5, 7.0, 12.0, 13.0, 1e9};
    const double ss[] = {-50.0, -1.0, 0.0, 1e-9, 1.0, 12.0, 1e9};
    for (int i = 0; i < 8; i++)
    {
        for (int j = 0; j < 7; j++)
        {
            double rho = WeightEngine::RestitutionRate(rs[i], ss[j]);
            BOOST_CHECK(rho >= 0.0);
            BOOST_CHECK(rho <= 1.0);
            BOOST_CHECK(rho == rho);            // not NaN
        }
    }
}

BOOST_AUTO_TEST_CASE(full_restitution_scores_one_not_zero)
{
    // THE regression that fixes the design of the denominator. A cluster that earns 100
    // and returns all of it ends the epoch with a ledger balance of ZERO. Had saldo been
    // read from the UTXO set, rho would divide by that zero and the guard would report
    // rho = 0 — scoring maximal non-compliance for maximal compliance. The recursive
    // saldo of Def. saldo keeps the restitution in the denominator and yields rho = 1.
    double gain  = WeightEngine::Gain(/*credits*/100.0, /*debits_gross*/100.0, /*R*/100.0);
    double saldo = WeightEngine::Saldo(0.0, gain);
    BOOST_CHECK_CLOSE(saldo, 100.0, 1e-9);      // NOT the 0 a balance lookup would see
    BOOST_CHECK_CLOSE(WeightEngine::RestitutionRate(100.0, saldo), 1.0, 1e-9);
}

// ---- scalar: final weight (Def. peso-finale, Prop. positivita) -----------

BOOST_AUTO_TEST_CASE(final_weight_epoch1_is_raw)
{
    // e == 1: w_k = W_k, independent of any (nonexistent) prior restitution rate.
    BOOST_CHECK_CLOSE(WeightEngine::FinalWeight(270.0, 0.0, 0.5, 1), 270.0, 1e-9);
    BOOST_CHECK_CLOSE(WeightEngine::FinalWeight(270.0, 0.9, 0.5, 1), 270.0, 1e-9);
}

BOOST_AUTO_TEST_CASE(final_weight_epoch2_convex_mix)
{
    // factor = rho*lambda + (1-lambda) = 0.5*0.5 + 0.5 = 0.75
    BOOST_CHECK_CLOSE(WeightEngine::FinalWeight(270.0, 0.5, 0.5, 2), 202.5, 1e-9);
}

BOOST_AUTO_TEST_CASE(final_weight_positive_even_at_rho_zero)
{
    // Prop. positivita-peso: with lambda < 1, rho == 0 still gives w_k = W_k*(1-lambda) > 0.
    double w = WeightEngine::FinalWeight(270.0, 0.0, 0.9, 2);
    BOOST_CHECK_CLOSE(w, 27.0, 1e-9); // 270 * 0.1
    BOOST_CHECK(w > 0.0);
}

BOOST_AUTO_TEST_CASE(final_weight_bounded_between_1minus_lambda_and_1)
{
    // For any rho in [0,1] the factor lies in [1-lambda, 1] -> w_k in [W_k(1-lambda), W_k].
    const double Wk = 500.0, lambda = 0.3;
    double rhos[] = {0.0, 0.25, 0.75, 1.0};
    for (int i = 0; i < 4; i++)
    {
        double w = WeightEngine::FinalWeight(Wk, rhos[i], lambda, 2);
        BOOST_CHECK(w >= Wk * (1.0 - lambda) - 1e-9);
        BOOST_CHECK(w <= Wk + 1e-9);
    }
}

// ---- scalar: integer conversion ------------------------------------------

BOOST_AUTO_TEST_CASE(to_integer_weight_scale_round_clamp)
{
    // uniform scale by kappa, round half away from zero.
    BOOST_CHECK_EQUAL(WeightEngine::ToIntegerWeight(270.0, 100.0), 27000u);
    BOOST_CHECK_EQUAL(WeightEngine::ToIntegerWeight(202.5, 100.0), 20250u);
    BOOST_CHECK_EQUAL(WeightEngine::ToIntegerWeight(1.5, 1.0), 2u);

    // positivity floor: a zero-activity (w == 0) cluster still publishes >= 1.
    BOOST_CHECK_EQUAL(WeightEngine::ToIntegerWeight(0.0, 100.0), 1u);
    // sub-1 scaled value also floors to 1.
    BOOST_CHECK_EQUAL(WeightEngine::ToIntegerWeight(0.005, 100.0), 1u);

    // uint32_t ceiling guard against extreme inputs.
    BOOST_CHECK_EQUAL(WeightEngine::ToIntegerWeight(1e10, 100.0), UINT32_MAX);

    // NaN maps to the safe floor.
    BOOST_CHECK_EQUAL(
        WeightEngine::ToIntegerWeight(std::numeric_limits<double>::quiet_NaN(), 100.0), 1u);
}

// ---- epoch driver: single cluster, epoch 1 -------------------------------

BOOST_AUTO_TEST_CASE(compute_epoch1_single_cluster)
{
    std::vector<ClusterInput> inputs;
    // Earned 20, spent 8 of which 6 was the restitution -> g = 20 - 8 + 6 = 18.
    inputs.push_back(canonical_cluster(/*R*/6.0, /*credits*/20.0, /*debits*/8.0));

    std::map<std::string, ClusterState> prior; // empty -> saldo_0 = 0
    std::map<std::string, ClusterResult> results;
    std::map<std::string, ClusterState> state;

    WeightEngine::ComputeEpoch(inputs, prior, Params(100.0, 0.2, 0.5), 1, results, state);

    const ClusterResult& r = results["MINER_M"];
    BOOST_CHECK_CLOSE(r.raw_weight, 270.0, 1e-9);
    BOOST_CHECK_CLOSE(r.gain, 18.0, 1e-9);          // 20 - 8 + 6
    BOOST_CHECK_CLOSE(r.saldo, 18.0, 1e-9);         // 0 + 18
    BOOST_CHECK_CLOSE(r.restitution, 1.0 / 3.0, 1e-6); // 6 / 18
    BOOST_CHECK_CLOSE(r.weight, 270.0, 1e-9);       // epoch 1: w = W_k
    BOOST_CHECK_EQUAL(r.integer_weight, 27000u);

    // state carried into epoch 2
    BOOST_CHECK_CLOSE(state["MINER_M"].saldo, 18.0, 1e-9);
    BOOST_CHECK_CLOSE(state["MINER_M"].restitution, 1.0 / 3.0, 1e-6);
}

// ---- epoch driver: fold forward into epoch 2 -----------------------------

BOOST_AUTO_TEST_CASE(compute_epoch2_uses_prior_restitution_and_accumulates_saldo)
{
    Params params(100.0, 0.2, 0.5);

    // Epoch 1: g = 20 - 8 + 6 = 18, saldo_1 = 18, rho_1 = 6/18 = 1/3.
    std::vector<ClusterInput> e1;
    e1.push_back(canonical_cluster(6.0, 20.0, 8.0));
    std::map<std::string, ClusterState> prior;
    std::map<std::string, ClusterResult> r1;
    std::map<std::string, ClusterState> s1;
    WeightEngine::ComputeEpoch(e1, prior, params, 1, r1, s1);
    BOOST_CHECK_CLOSE(s1["MINER_M"].saldo, 18.0, 1e-9);

    // Epoch 2: earned 10, spent 3 all of which was the restitution -> g = 10 - 3 + 3 = 10.
    std::vector<ClusterInput> e2;
    e2.push_back(canonical_cluster(3.0, 10.0, 3.0));
    std::map<std::string, ClusterResult> r2;
    std::map<std::string, ClusterState> s2;
    WeightEngine::ComputeEpoch(e2, s1, params, 2, r2, s2);

    const ClusterResult& r = r2["MINER_M"];
    BOOST_CHECK_CLOSE(r.raw_weight, 270.0, 1e-9);
    // The feedback is one epoch LATE: w_2 uses rho_1, not rho_2.
    // w_2 = W_k * [rho_1*lambda + (1-lambda)] = 270 * (1/3*0.5 + 0.5) = 180
    BOOST_CHECK_CLOSE(r.weight, 180.0, 1e-9);
    BOOST_CHECK_EQUAL(r.integer_weight, 18000u);
    // saldo_2 = saldo_1 + g_2 = 18 + 10 = 28 ; rho_2 = 3 / 28
    BOOST_CHECK_CLOSE(r.gain, 10.0, 1e-9);
    BOOST_CHECK_CLOSE(r.saldo, 28.0, 1e-9);
    BOOST_CHECK_CLOSE(r.restitution, 3.0 / 28.0, 1e-6);
}

// ---- epoch driver: the saldo really is cumulative across many epochs ------

BOOST_AUTO_TEST_CASE(saldo_accumulates_across_epochs_and_drives_rho)
{
    // Four epochs of identical flows: the saldo grows linearly, so an unchanged
    // restitution is a shrinking FRACTION of it. This is the property a per-epoch
    // (non-cumulative) denominator would silently lose.
    Params params(100.0, 0.2, 0.5);
    std::map<std::string, ClusterState> state;
    std::map<std::string, ClusterResult> results;

    const double expected_saldo[] = {10.0, 20.0, 30.0, 40.0};
    for (uint32_t e = 1; e <= 4; e++)
    {
        std::vector<ClusterInput> in;
        in.push_back(canonical_cluster(/*R*/2.0, /*credits*/10.0, /*debits*/2.0)); // g = 10
        std::map<std::string, ClusterState> next;
        WeightEngine::ComputeEpoch(in, state, params, e, results, next);

        BOOST_CHECK_CLOSE(results["MINER_M"].saldo, expected_saldo[e - 1], 1e-9);
        BOOST_CHECK_CLOSE(results["MINER_M"].restitution, 2.0 / expected_saldo[e - 1], 1e-6);
        state = next;
    }
}

// ---- epoch driver: restituting the whole saldo ---------------------------

BOOST_AUTO_TEST_CASE(cluster_restituting_everything_reaches_rho_one_and_full_weight)
{
    // End-to-end form of full_restitution_scores_one_not_zero: a cluster that returns
    // its entire saldo scores rho = 1 and therefore carries NO damping into the next
    // epoch (factor = 1*lambda + (1-lambda) = 1), i.e. w_2 == W_k.
    Params params(100.0, 0.2, 0.5);
    std::vector<ClusterInput> e1;
    e1.push_back(canonical_cluster(/*R*/50.0, /*credits*/50.0, /*debits*/50.0)); // g = 50
    std::map<std::string, ClusterState> prior, s1, s2;
    std::map<std::string, ClusterResult> r1, r2;
    WeightEngine::ComputeEpoch(e1, prior, params, 1, r1, s1);

    BOOST_CHECK_CLOSE(r1["MINER_M"].saldo, 50.0, 1e-9);
    BOOST_CHECK_CLOSE(r1["MINER_M"].restitution, 1.0, 1e-9);

    std::vector<ClusterInput> e2;
    e2.push_back(canonical_cluster(0.0, 0.0, 0.0));
    WeightEngine::ComputeEpoch(e2, s1, params, 2, r2, s2);
    BOOST_CHECK_CLOSE(r2["MINER_M"].weight, 270.0, 1e-9);   // undamped
    BOOST_CHECK_EQUAL(r2["MINER_M"].integer_weight, 27000u);
}

// ---- epoch driver: a cluster with no movement at all ---------------------

BOOST_AUTO_TEST_CASE(zero_saldo_cluster_gets_rho_zero_and_max_damping)
{
    // No credits, no debits, nothing restituted: saldo = 0 -> rho = 0 by the guard (no
    // NaN), and the next epoch is damped to the floor W_k*(1-lambda), never to zero.
    Params params(100.0, 0.2, 0.5);
    std::vector<ClusterInput> e1;
    e1.push_back(canonical_cluster(0.0, 0.0, 0.0));
    std::map<std::string, ClusterState> prior, s1, s2;
    std::map<std::string, ClusterResult> r1, r2;
    WeightEngine::ComputeEpoch(e1, prior, params, 1, r1, s1);

    BOOST_CHECK_EQUAL(r1["MINER_M"].saldo, 0.0);
    BOOST_CHECK_EQUAL(r1["MINER_M"].restitution, 0.0);
    BOOST_CHECK(r1["MINER_M"].restitution == r1["MINER_M"].restitution); // not NaN

    std::vector<ClusterInput> e2;
    e2.push_back(canonical_cluster(0.0, 0.0, 0.0));
    WeightEngine::ComputeEpoch(e2, s1, params, 2, r2, s2);
    BOOST_CHECK_CLOSE(r2["MINER_M"].weight, 135.0, 1e-9);   // 270 * (1 - 0.5)
    BOOST_CHECK(r2["MINER_M"].weight > 0.0);                // Prop. positivita-peso
}

// ---- epoch driver: 5 clusters (Vers_2 A-E), independent per cluster ------

BOOST_AUTO_TEST_CASE(compute_epoch_five_clusters_raw_weights_and_independence)
{
    // Mirrors the reference simulation's 5-cluster layout (A..E). All miners ESG 10,
    // kappa 100, lambda 0.5.
    //   W_A = 10*(20 + (5+5))  = 300   company tau 100
    //   W_B = 10*(10 + 10)     = 200   company tau 100
    //   W_C = 10*(10 + 0)      = 100   company tau   0
    //   W_D = 10*(30 + 20)     = 500   company tau 200
    //   W_E = 10*( 0 + (10+10))= 200   company tau 200
    //
    // With the allocation gone there is no cross-cluster term left (no W_tot, no Theta),
    // so each cluster's whole result depends on its OWN inputs only — asserted below by
    // giving every cluster a different flow profile and checking each in isolation.
    ClusterInput A;
    A.miner = "A"; A.esg_miner = 10.0; A.tau_miner = 20;
    A.restituted = 0.0;  A.credits = 40.0; A.debits = 10.0;   // g = 30, rho = 0
    A.companies.push_back(Company("a1", 10.0, 50));
    A.companies.push_back(Company("a2", 10.0, 50));
    ClusterInput B;
    B.miner = "B"; B.esg_miner = 10.0; B.tau_miner = 10;
    B.restituted = 25.0; B.credits = 50.0; B.debits = 25.0;   // g = 50, rho = 0.5
    B.companies.push_back(Company("b1", 10.0, 100));
    ClusterInput C;
    C.miner = "C"; C.esg_miner = 10.0; C.tau_miner = 10;
    C.restituted = 0.0;  C.credits = 0.0;  C.debits = 0.0;    // g = 0, rho = 0 (guard)
    C.companies.push_back(Company("c1", 10.0, 0));
    ClusterInput D;
    D.miner = "D"; D.esg_miner = 10.0; D.tau_miner = 30;
    D.restituted = 80.0; D.credits = 80.0; D.debits = 80.0;   // g = 80, rho = 1
    D.companies.push_back(Company("d1", 10.0, 200));
    ClusterInput E;
    E.miner = "E"; E.esg_miner = 10.0; E.tau_miner = 0;
    E.restituted = 0.0;  E.credits = 10.0; E.debits = 60.0;   // g = -50 (overspent)
    E.companies.push_back(Company("e1", 10.0, 100));
    E.companies.push_back(Company("e2", 10.0, 100));

    std::vector<ClusterInput> inputs;
    inputs.push_back(A); inputs.push_back(B); inputs.push_back(C);
    inputs.push_back(D); inputs.push_back(E);

    std::map<std::string, ClusterState> prior;
    std::map<std::string, ClusterResult> results;
    std::map<std::string, ClusterState> state;
    WeightEngine::ComputeEpoch(inputs, prior, Params(100.0, 0.2, 0.5), 1, results, state);

    const char*  names[5] = {"A", "B", "C", "D", "E"};
    const double W[5]     = {300.0, 200.0, 100.0, 500.0, 200.0};
    const double G[5]     = {30.0, 50.0, 0.0, 80.0, -50.0};
    const double RHO[5]   = {0.0, 0.5, 0.0, 1.0, 0.0};

    for (int i = 0; i < 5; i++)
    {
        const ClusterResult& r = results[names[i]];
        BOOST_CHECK_CLOSE(r.raw_weight, W[i], 1e-9);
        BOOST_CHECK_CLOSE(r.gain, G[i], 1e-9);
        BOOST_CHECK_CLOSE(r.saldo, G[i], 1e-9);        // saldo_0 = 0
        BOOST_CHECK_EQUAL(r.restitution, RHO[i]);
        // epoch 1: w_k = W_k, and the integer weight is strictly positive
        BOOST_CHECK_CLOSE(r.weight, W[i], 1e-9);
        BOOST_CHECK(r.integer_weight >= 1u);
    }

    // E overspent: a negative saldo must yield rho = 0 rather than a negative rate.
    BOOST_CHECK(results["E"].saldo < 0.0);
    BOOST_CHECK_EQUAL(results["E"].restitution, 0.0);

    // No cross-cluster coupling: recomputing D alone gives bit-identical numbers.
    std::vector<ClusterInput> onlyD;
    onlyD.push_back(D);
    std::map<std::string, ClusterResult> rD;
    std::map<std::string, ClusterState> sD;
    WeightEngine::ComputeEpoch(onlyD, prior, Params(100.0, 0.2, 0.5), 1, rD, sD);
    BOOST_CHECK_EQUAL(rD["D"].raw_weight,     results["D"].raw_weight);
    BOOST_CHECK_EQUAL(rD["D"].saldo,          results["D"].saldo);
    BOOST_CHECK_EQUAL(rD["D"].restitution,    results["D"].restitution);
    BOOST_CHECK_EQUAL(rD["D"].integer_weight, results["D"].integer_weight);
}

// ---- degeneration guard: inactive cluster stays finite, weight >= 1 ------

BOOST_AUTO_TEST_CASE(inactive_cluster_no_div0_and_min_weight)
{
    // A cluster with no activity and no movement at all: W_k = 0, saldo = 0.
    ClusterInput dead;
    dead.miner = "DEAD"; dead.esg_miner = 10.0; dead.tau_miner = 0;
    dead.restituted = 0.0; dead.credits = 0.0; dead.debits = 0.0;

    std::vector<ClusterInput> inputs;
    inputs.push_back(dead);

    std::map<std::string, ClusterState> prior;
    std::map<std::string, ClusterResult> results;
    std::map<std::string, ClusterState> state;
    WeightEngine::ComputeEpoch(inputs, prior, Params(100.0, 0.2, 0.5), 1, results, state);

    const ClusterResult& r = results["DEAD"];
    BOOST_CHECK_EQUAL(r.raw_weight, 0.0);
    BOOST_CHECK_EQUAL(r.gain, 0.0);
    BOOST_CHECK_EQUAL(r.restitution, 0.0);         // 0, not NaN
    BOOST_CHECK(std::isfinite(r.saldo));
    BOOST_CHECK_EQUAL(r.integer_weight, 1u);       // positivity floor

    // And it must not degenerate across a second epoch either.
    std::map<std::string, ClusterResult> r2;
    std::map<std::string, ClusterState> s2;
    WeightEngine::ComputeEpoch(inputs, state, Params(100.0, 0.2, 0.5), 2, r2, s2);
    BOOST_CHECK(std::isfinite(r2["DEAD"].weight));
    BOOST_CHECK(std::isfinite(r2["DEAD"].restitution));
    BOOST_CHECK(std::isfinite(r2["DEAD"].saldo));
    BOOST_CHECK_EQUAL(r2["DEAD"].integer_weight, 1u);
}

// ---- cluster-order independence of the epoch driver ----------------------

BOOST_AUTO_TEST_CASE(compute_epoch_is_cluster_order_independent)
{
    ClusterInput A;
    A.miner = "A"; A.esg_miner = 12.0; A.tau_miner = 7;
    A.restituted = 4.0; A.credits = 31.0; A.debits = 9.0;
    A.companies.push_back(Company("a1", 11.0, 33));
    ClusterInput B;
    B.miner = "B"; B.esg_miner = 9.0; B.tau_miner = 3;
    B.restituted = 1.0; B.credits = 17.0; B.debits = 5.0;
    B.companies.push_back(Company("b1", 14.0, 21));

    std::vector<ClusterInput> forward;  forward.push_back(A);  forward.push_back(B);
    std::vector<ClusterInput> reversed; reversed.push_back(B); reversed.push_back(A);

    Params params(100.0, 0.2, 0.5);
    std::map<std::string, ClusterState> prior;

    std::map<std::string, ClusterResult> rf, rr;
    std::map<std::string, ClusterState> sf, sr;
    WeightEngine::ComputeEpoch(forward,  prior, params, 1, rf, sf);
    WeightEngine::ComputeEpoch(reversed, prior, params, 1, rr, sr);

    // Identical results per miner regardless of input ordering.
    BOOST_CHECK_EQUAL(rf["A"].integer_weight, rr["A"].integer_weight);
    BOOST_CHECK_EQUAL(rf["B"].integer_weight, rr["B"].integer_weight);
    BOOST_CHECK_EQUAL(rf["A"].raw_weight, rr["A"].raw_weight);
    BOOST_CHECK_EQUAL(rf["B"].saldo, rr["B"].saldo);
    BOOST_CHECK_EQUAL(rf["B"].restitution, rr["B"].restitution);
}
