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
// definitions; the multi-cluster case also checks the reference-simulation
// control identity sum_k A_k = alpha * Theta.

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
static ClusterInput canonical_cluster(double reconciled)
{
    ClusterInput in;
    in.miner = "MINER_M";
    in.esg_miner = 10.0;
    in.tau_miner = 20;
    in.companies.push_back(Company("AZ_1", 10.0, 50));
    in.companies.push_back(Company("AZ_2", 20.0, 10));
    in.reconciled = reconciled;
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
    ClusterInput in = canonical_cluster(0.0);
    BOOST_CHECK_CLOSE(WeightEngine::RawWeight(in, 100.0), 270.0, 1e-9);
}

BOOST_AUTO_TEST_CASE(raw_weight_is_company_order_independent)
{
    // Same companies supplied in the opposite order must give the identical
    // floating-point W_k (deterministic ascending-address summation).
    ClusterInput a = canonical_cluster(0.0);

    ClusterInput b;
    b.miner = "MINER_M";
    b.esg_miner = 10.0;
    b.tau_miner = 20;
    b.companies.push_back(Company("AZ_2", 20.0, 10));
    b.companies.push_back(Company("AZ_1", 10.0, 50));

    BOOST_CHECK_EQUAL(WeightEngine::RawWeight(a, 100.0), WeightEngine::RawWeight(b, 100.0));
}

// ---- scalar: allocation --------------------------------------------------

BOOST_AUTO_TEST_CASE(allocation_and_zero_total_guard)
{
    // A_k = alpha * Theta * W_k / W_tot ; single cluster W_tot == W_k -> alpha*Theta.
    BOOST_CHECK_CLOSE(WeightEngine::Allocation(0.2, 60.0, 270.0, 270.0), 12.0, 1e-9);
    // W_tot <= 0 -> 0 (never a division by zero).
    BOOST_CHECK_EQUAL(WeightEngine::Allocation(0.2, 60.0, 0.0, 0.0), 0.0);
}

// ---- scalar: compliance and balance (feedback recursion) -----------------

BOOST_AUTO_TEST_CASE(compliance_rate_basic_and_bounds)
{
    BOOST_CHECK_CLOSE(WeightEngine::ComplianceRate(6.0, 12.0, 0.0), 0.5, 1e-9);
    BOOST_CHECK_CLOSE(WeightEngine::ComplianceRate(3.0, 12.0, 6.0), 1.0 / 6.0, 1e-6);
    // R above the legal domain is clamped -> rho == 1, never > 1.
    BOOST_CHECK_CLOSE(WeightEngine::ComplianceRate(1000.0, 12.0, 0.0), 1.0, 1e-9);
    // zero denominator -> 0 (the #DIV/0! avoidance), not NaN.
    BOOST_CHECK_EQUAL(WeightEngine::ComplianceRate(5.0, 0.0, 0.0), 0.0);
}

BOOST_AUTO_TEST_CASE(balance_recursion_and_nonnegativity)
{
    BOOST_CHECK_CLOSE(WeightEngine::Balance(6.0, 12.0, 0.0), 6.0, 1e-9);
    BOOST_CHECK_CLOSE(WeightEngine::Balance(3.0, 12.0, 6.0), 15.0, 1e-9);
    // R clamped to the domain keeps B >= 0.
    BOOST_CHECK_CLOSE(WeightEngine::Balance(1000.0, 12.0, 0.0), 0.0, 1e-9);
    BOOST_CHECK_EQUAL(WeightEngine::Balance(5.0, 0.0, 0.0), 0.0);
}

// ---- scalar: final weight (Def. peso-finale, Prop. positivita) -----------

BOOST_AUTO_TEST_CASE(final_weight_epoch1_is_raw)
{
    // e == 1: w_k = W_k, independent of any (nonexistent) prior compliance.
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
    inputs.push_back(canonical_cluster(6.0)); // R_1 = 6

    double theta = WeightEngine::NetworkActivity(inputs); // 50 + 10 = 60
    BOOST_CHECK_CLOSE(theta, 60.0, 1e-9);

    std::map<std::string, ClusterState> prior; // empty -> B_0 = 0
    std::map<std::string, ClusterResult> results;
    std::map<std::string, ClusterState> state;

    WeightEngine::ComputeEpoch(inputs, theta, prior, Params(100.0, 0.2, 0.5), 1,
                               results, state);

    const ClusterResult& r = results["MINER_M"];
    BOOST_CHECK_CLOSE(r.raw_weight, 270.0, 1e-9);
    BOOST_CHECK_CLOSE(r.allocation, 12.0, 1e-9);   // 0.2 * 60 * 270/270
    BOOST_CHECK_CLOSE(r.compliance, 0.5, 1e-9);    // 6 / (12 + 0)
    BOOST_CHECK_CLOSE(r.balance, 6.0, 1e-9);       // 12 - 6 + 0
    BOOST_CHECK_CLOSE(r.weight, 270.0, 1e-9);      // epoch 1: w = W_k
    BOOST_CHECK_EQUAL(r.integer_weight, 27000u);

    // state carried into epoch 2
    BOOST_CHECK_CLOSE(state["MINER_M"].balance, 6.0, 1e-9);
    BOOST_CHECK_CLOSE(state["MINER_M"].compliance, 0.5, 1e-9);
}

// ---- epoch driver: fold forward into epoch 2 -----------------------------

BOOST_AUTO_TEST_CASE(compute_epoch2_uses_prior_compliance)
{
    Params params(100.0, 0.2, 0.5);

    // Epoch 1 (R_1 = 6) -> rho_1 = 0.5, B_1 = 6.
    std::vector<ClusterInput> e1;
    e1.push_back(canonical_cluster(6.0));
    std::map<std::string, ClusterState> prior;
    std::map<std::string, ClusterResult> r1;
    std::map<std::string, ClusterState> s1;
    WeightEngine::ComputeEpoch(e1, WeightEngine::NetworkActivity(e1), prior, params, 1, r1, s1);

    // Epoch 2 (R_2 = 3), carrying s1.
    std::vector<ClusterInput> e2;
    e2.push_back(canonical_cluster(3.0));
    std::map<std::string, ClusterResult> r2;
    std::map<std::string, ClusterState> s2;
    WeightEngine::ComputeEpoch(e2, WeightEngine::NetworkActivity(e2), s1, params, 2, r2, s2);

    const ClusterResult& r = r2["MINER_M"];
    BOOST_CHECK_CLOSE(r.raw_weight, 270.0, 1e-9);
    BOOST_CHECK_CLOSE(r.allocation, 12.0, 1e-9);
    // w_2 = W_k * [rho_1 * lambda + (1-lambda)] = 270 * (0.5*0.5 + 0.5) = 202.5
    BOOST_CHECK_CLOSE(r.weight, 202.5, 1e-9);
    BOOST_CHECK_EQUAL(r.integer_weight, 20250u);
    // rho_2 = 3 / (12 + 6) = 1/6 ; B_2 = 12 - 3 + 6 = 15
    BOOST_CHECK_CLOSE(r.compliance, 1.0 / 6.0, 1e-6);
    BOOST_CHECK_CLOSE(r.balance, 15.0, 1e-9);
}

// ---- epoch driver: 5 clusters (Vers_2 A-E) + control identity sum A_k = alpha*Theta -

BOOST_AUTO_TEST_CASE(compute_epoch_five_clusters_allocation_identity)
{
    // Mirrors the reference simulation's 5-cluster layout (A..E). All miners ESG 10,
    // kappa 100, alpha 0.2, lambda 0.5.
    //   W_A = 10*(20 + (5+5))  = 300   company tau 100
    //   W_B = 10*(10 + 10)     = 200   company tau 100
    //   W_C = 10*(10 + 0)      = 100   company tau   0
    //   W_D = 10*(30 + 20)     = 500   company tau 200
    //   W_E = 10*( 0 + (10+10))= 200   company tau 200
    //   W_tot = 1300 ; Theta = 600
    ClusterInput A;
    A.miner = "A"; A.esg_miner = 10.0; A.tau_miner = 20; A.reconciled = 0.0;
    A.companies.push_back(Company("a1", 10.0, 50));
    A.companies.push_back(Company("a2", 10.0, 50));
    ClusterInput B;
    B.miner = "B"; B.esg_miner = 10.0; B.tau_miner = 10; B.reconciled = 0.0;
    B.companies.push_back(Company("b1", 10.0, 100));
    ClusterInput C;
    C.miner = "C"; C.esg_miner = 10.0; C.tau_miner = 10; C.reconciled = 0.0;
    C.companies.push_back(Company("c1", 10.0, 0));
    ClusterInput D;
    D.miner = "D"; D.esg_miner = 10.0; D.tau_miner = 30; D.reconciled = 0.0;
    D.companies.push_back(Company("d1", 10.0, 200));
    ClusterInput E;
    E.miner = "E"; E.esg_miner = 10.0; E.tau_miner = 0; E.reconciled = 0.0;
    E.companies.push_back(Company("e1", 10.0, 100));
    E.companies.push_back(Company("e2", 10.0, 100));

    std::vector<ClusterInput> inputs;
    inputs.push_back(A); inputs.push_back(B); inputs.push_back(C);
    inputs.push_back(D); inputs.push_back(E);

    double theta = WeightEngine::NetworkActivity(inputs); // 100+100+0+200+200 = 600
    BOOST_CHECK_CLOSE(theta, 600.0, 1e-9);

    std::map<std::string, ClusterState> prior;
    std::map<std::string, ClusterResult> results;
    std::map<std::string, ClusterState> state;
    WeightEngine::ComputeEpoch(inputs, theta, prior, Params(100.0, 0.2, 0.5), 1,
                               results, state);

    const double W[5] = {300.0, 200.0, 100.0, 500.0, 200.0};
    const char* names[5] = {"A", "B", "C", "D", "E"};
    const double W_tot = 1300.0;

    double sumA = 0.0;
    for (int i = 0; i < 5; i++)
    {
        const ClusterResult& r = results[names[i]];
        BOOST_CHECK_CLOSE(r.raw_weight, W[i], 1e-9);
        // A_k = alpha * Theta * W_k / W_tot
        BOOST_CHECK_CLOSE(r.allocation, 0.2 * 600.0 * W[i] / W_tot, 1e-9);
        // epoch 1: w_k = W_k, and the integer weight is strictly positive
        BOOST_CHECK_CLOSE(r.weight, W[i], 1e-9);
        BOOST_CHECK(r.integer_weight >= 1u);
        sumA += r.allocation;
    }

    // Control identity (report §4.5): the allocations sum to alpha*Theta.
    BOOST_CHECK_CLOSE(sumA, 0.2 * 600.0, 1e-9); // = 120
}

// ---- degeneration guard: inactive cluster stays finite, weight >= 1 ------

BOOST_AUTO_TEST_CASE(inactive_cluster_no_div0_and_min_weight)
{
    // A cluster with no activity at all: W_k = 0, A_k = 0, denom = 0.
    ClusterInput dead;
    dead.miner = "DEAD"; dead.esg_miner = 10.0; dead.tau_miner = 0; dead.reconciled = 0.0;

    std::vector<ClusterInput> inputs;
    inputs.push_back(dead);

    std::map<std::string, ClusterState> prior;
    std::map<std::string, ClusterResult> results;
    std::map<std::string, ClusterState> state;
    WeightEngine::ComputeEpoch(inputs, WeightEngine::NetworkActivity(inputs), prior,
                               Params(100.0, 0.2, 0.5), 1, results, state);

    const ClusterResult& r = results["DEAD"];
    BOOST_CHECK_EQUAL(r.raw_weight, 0.0);
    BOOST_CHECK_EQUAL(r.allocation, 0.0);
    BOOST_CHECK_EQUAL(r.compliance, 0.0);          // 0, not NaN
    BOOST_CHECK(std::isfinite(r.balance));
    BOOST_CHECK_EQUAL(r.integer_weight, 1u);       // positivity floor

    // And it must not degenerate across a second epoch either.
    std::map<std::string, ClusterResult> r2;
    std::map<std::string, ClusterState> s2;
    WeightEngine::ComputeEpoch(inputs, WeightEngine::NetworkActivity(inputs), state,
                               Params(100.0, 0.2, 0.5), 2, r2, s2);
    BOOST_CHECK(std::isfinite(r2["DEAD"].weight));
    BOOST_CHECK(std::isfinite(r2["DEAD"].compliance));
    BOOST_CHECK_EQUAL(r2["DEAD"].integer_weight, 1u);
}

// ---- cluster-order independence of the epoch driver ----------------------

BOOST_AUTO_TEST_CASE(compute_epoch_is_cluster_order_independent)
{
    ClusterInput A;
    A.miner = "A"; A.esg_miner = 12.0; A.tau_miner = 7; A.reconciled = 4.0;
    A.companies.push_back(Company("a1", 11.0, 33));
    ClusterInput B;
    B.miner = "B"; B.esg_miner = 9.0; B.tau_miner = 3; B.reconciled = 1.0;
    B.companies.push_back(Company("b1", 14.0, 21));

    std::vector<ClusterInput> forward;  forward.push_back(A);  forward.push_back(B);
    std::vector<ClusterInput> reversed; reversed.push_back(B); reversed.push_back(A);

    Params params(100.0, 0.2, 0.5);
    std::map<std::string, ClusterState> prior;

    std::map<std::string, ClusterResult> rf, rr;
    std::map<std::string, ClusterState> sf, sr;
    WeightEngine::ComputeEpoch(forward,  WeightEngine::NetworkActivity(forward),  prior, params, 1, rf, sf);
    WeightEngine::ComputeEpoch(reversed, WeightEngine::NetworkActivity(reversed), prior, params, 1, rr, sr);

    // Identical results per miner regardless of input ordering.
    BOOST_CHECK_EQUAL(rf["A"].integer_weight, rr["A"].integer_weight);
    BOOST_CHECK_EQUAL(rf["B"].integer_weight, rr["B"].integer_weight);
    BOOST_CHECK_EQUAL(rf["A"].raw_weight, rr["A"].raw_weight);
    BOOST_CHECK_EQUAL(rf["B"].allocation, rr["B"].allocation);
}
