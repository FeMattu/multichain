// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA Phase 2 — unit tests for the pure Efraimidis–Spirakis proposer selector
// (src/wpoa/wpoa_selector.h, class WPoASelector).
//
// These tests are self-contained: they link only the HMAC-SHA256 / SHA256
// crypto primitives and Boost.Test (header-only), NOT the wallet / node
// runtime. Build & run with src/wpoa/test/run_selector_unit_tests.sh.
//
// They validate, node-free:
//   * determinism and iteration-order independence of the election;
//   * the degenerate cases (empty map, single validator, zero weights);
//   * probability preservation — Pr[i elected] = w_i / Σ w_j (thesis §7.4) —
//     empirically over many distinct seeds, with a chi-square goodness-of-fit
//     check whose observed-vs-expected table is printed as a thesis artifact.

#define BOOST_TEST_MODULE wPoASelectorTests
#include <boost/test/included/unit_test.hpp>

#include <cmath>
#include <cstdio>
#include <map>
#include <string>
#include <vector>

#include "wpoa/wpoa_selector.h"

// ---- helpers -------------------------------------------------------------

// A distinct 32-byte seed per trial index (big-endian index in the low bytes),
// standing in for the sequence of previous-block hashes a real chain produces.
static std::vector<unsigned char> make_seed(uint32_t i)
{
    std::vector<unsigned char> seed(32, 0);
    seed[28] = (unsigned char)((i >> 24) & 0xff);
    seed[29] = (unsigned char)((i >> 16) & 0xff);
    seed[30] = (unsigned char)((i >> 8) & 0xff);
    seed[31] = (unsigned char)(i & 0xff);
    return seed;
}

static std::string select(const std::vector<unsigned char>& seed,
                          const std::map<std::string, uint32_t>& w)
{
    return WPoASelector::SelectProposer(&seed[0], seed.size(), w);
}

// ---- determinism & degenerate cases -------------------------------------

BOOST_AUTO_TEST_CASE(empty_map_returns_empty)
{
    std::map<std::string, uint32_t> w;
    std::vector<unsigned char> seed = make_seed(1);
    BOOST_CHECK_EQUAL(select(seed, w), std::string(""));
}

BOOST_AUTO_TEST_CASE(single_validator_always_wins)
{
    std::map<std::string, uint32_t> w;
    w["1AaaValidatorAddressExample000000000"] = 100;
    for (uint32_t i = 0; i < 50; i++)
    {
        std::vector<unsigned char> seed = make_seed(i);
        BOOST_CHECK_EQUAL(select(seed, w), std::string("1AaaValidatorAddressExample000000000"));
    }
}

BOOST_AUTO_TEST_CASE(deterministic_same_inputs_same_winner)
{
    std::map<std::string, uint32_t> w;
    w["1Aaa"] = 10;
    w["1Bbb"] = 20;
    w["1Ccc"] = 30;

    std::vector<unsigned char> seed = make_seed(12345);
    std::string first = select(seed, w);
    BOOST_CHECK(!first.empty());
    for (int rep = 0; rep < 100; rep++)
    {
        BOOST_CHECK_EQUAL(select(seed, w), first);
    }
}

BOOST_AUTO_TEST_CASE(zero_weight_never_wins)
{
    // A zero-weight entry must be skipped entirely; the sole positive-weight
    // node always wins regardless of seed.
    std::map<std::string, uint32_t> w;
    w["1Zero"] = 0;
    w["1Real"] = 5;
    for (uint32_t i = 0; i < 100; i++)
    {
        std::vector<unsigned char> seed = make_seed(i * 7 + 3);
        BOOST_CHECK_EQUAL(select(seed, w), std::string("1Real"));
    }

    // All-zero map behaves like an empty map.
    std::map<std::string, uint32_t> all_zero;
    all_zero["1A"] = 0;
    all_zero["1B"] = 0;
    std::vector<unsigned char> seed = make_seed(9);
    BOOST_CHECK_EQUAL(select(seed, all_zero), std::string(""));
}

BOOST_AUTO_TEST_CASE(iteration_order_independence)
{
    // SelectProposer must be a function of the (address,weight) set only, not of
    // any container ordering. We recompute the winner with an independent manual
    // argmin over the reverse iteration order and require agreement. This guards
    // the ordering-independence property that motivated the argmin form (b).
    std::map<std::string, uint32_t> w;
    w["1alpha"] = 7;
    w["1bravo"] = 13;
    w["1charlie"] = 21;
    w["1delta"] = 3;

    for (uint32_t i = 0; i < 500; i++)
    {
        std::vector<unsigned char> seed = make_seed(i);

        std::string via_api = select(seed, w);

        // Manual argmin over reverse order with the same total-order rule.
        std::string best;
        double best_score = 0.0;
        bool have = false;
        for (std::map<std::string, uint32_t>::const_reverse_iterator it = w.rbegin();
             it != w.rend(); ++it)
        {
            double s = WPoASelector::ComputeScore(&seed[0], seed.size(), it->first, it->second);
            if (!have || s < best_score || (s == best_score && it->first < best))
            {
                best_score = s;
                best = it->first;
                have = true;
            }
        }
        BOOST_CHECK_EQUAL(via_api, best);
    }
}

// ---- probability preservation (thesis §7.4) ------------------------------

// Tally winners over `trials` distinct seeds and assert each validator's
// empirical share is within `tol` (relative) of its weight share. Prints the
// observed-vs-expected table and the chi-square statistic.
static void run_distribution(const std::map<std::string, uint32_t>& w,
                             uint32_t trials, double tol)
{
    std::map<std::string, uint64_t> wins;
    for (std::map<std::string, uint32_t>::const_iterator it = w.begin(); it != w.end(); ++it)
    {
        wins[it->first] = 0;
    }

    uint64_t total_weight = 0;
    for (std::map<std::string, uint32_t>::const_iterator it = w.begin(); it != w.end(); ++it)
    {
        total_weight += it->second;
    }

    for (uint32_t i = 0; i < trials; i++)
    {
        std::vector<unsigned char> seed = make_seed(i);
        std::string winner = select(seed, w);
        BOOST_REQUIRE(!winner.empty());
        wins[winner] += 1;
    }

    std::printf("\n  Distribution over %u trials (%zu validators, total weight %llu):\n",
                trials, w.size(), (unsigned long long)total_weight);
    std::printf("  %-40s %8s %10s %10s %8s\n", "address", "weight", "expected", "observed", "err%%");

    double chi2 = 0.0;
    for (std::map<std::string, uint32_t>::const_iterator it = w.begin(); it != w.end(); ++it)
    {
        double p_expected = (double)it->second / (double)total_weight;
        double expected_count = p_expected * trials;
        double observed_count = (double)wins[it->first];
        double p_observed = observed_count / (double)trials;
        double err = (p_observed - p_expected) / p_expected;

        std::printf("  %-40s %8u %10.4f %10.4f %+7.2f\n",
                    it->first.c_str(), it->second, p_expected, p_observed, err * 100.0);

        double diff = observed_count - expected_count;
        chi2 += (diff * diff) / expected_count;

        BOOST_CHECK_MESSAGE(std::fabs(err) < tol,
                            "validator " << it->first << " share " << p_observed
                            << " deviates from expected " << p_expected
                            << " by " << (err * 100.0) << "% (> " << (tol * 100.0) << "%)");
    }
    std::printf("  chi-square = %.3f (df = %zu)\n", chi2, w.size() - 1);
}

BOOST_AUTO_TEST_CASE(distribution_equal_weights)
{
    std::map<std::string, uint32_t> w;
    w["1AequalWeightNodeAAAAAAAAAAAAAAAAAAA"] = 100;
    w["1BequalWeightNodeBBBBBBBBBBBBBBBBBBB"] = 100;
    w["1CequalWeightNodeCCCCCCCCCCCCCCCCCCC"] = 100;
    w["1DequalWeightNodeDDDDDDDDDDDDDDDDDDD"] = 100;
    run_distribution(w, 200000, 0.05);
}

BOOST_AUTO_TEST_CASE(distribution_skewed_weights)
{
    // 1 : 2 : 3 : 4  ->  shares 0.1, 0.2, 0.3, 0.4
    std::map<std::string, uint32_t> w;
    w["1AskewNodeAAAAAAAAAAAAAAAAAAAAAAAAAA"] = 100;
    w["1BskewNodeBBBBBBBBBBBBBBBBBBBBBBBBBB"] = 200;
    w["1CskewNodeCCCCCCCCCCCCCCCCCCCCCCCCCC"] = 300;
    w["1DskewNodeDDDDDDDDDDDDDDDDDDDDDDDDDD"] = 400;
    run_distribution(w, 200000, 0.05);
}

BOOST_AUTO_TEST_CASE(distribution_monotonic_in_weight)
{
    // A strictly heavier validator must win strictly more often.
    std::map<std::string, uint32_t> w;
    w["1light"] = 50;
    w["1heavy"] = 500;

    std::map<std::string, uint64_t> wins;
    wins["1light"] = 0;
    wins["1heavy"] = 0;
    const uint32_t trials = 100000;
    for (uint32_t i = 0; i < trials; i++)
    {
        std::vector<unsigned char> seed = make_seed(i);
        wins[select(seed, w)] += 1;
    }
    BOOST_CHECK_MESSAGE(wins["1heavy"] > wins["1light"],
                        "heavy=" << wins["1heavy"] << " light=" << wins["1light"]);
    // ~10x weight -> ~10x wins (loose bound to stay non-flaky).
    double ratio = (double)wins["1heavy"] / (double)wins["1light"];
    BOOST_CHECK_MESSAGE(ratio > 8.0 && ratio < 12.0, "win ratio " << ratio << " (expected ~10)");
}
