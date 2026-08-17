// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA — unit tests for the pure behavioural-malus core (src/wpoa/malus_record.h):
// record parsing, the accumulator fold, the correction factor Psi, the effective
// weight w_eff = w * Psi, and the reversibility bound.
//
// These tests are self-contained: they depend only on json_spirit headers and
// Boost.Test (header-only "included" variant), NOT on the wallet / node runtime.
// Build & run with src/wpoa/test/run_unit_tests.sh.

#define BOOST_TEST_MODULE wPoAMalusTests
#include <boost/test/included/unit_test.hpp>

#include <cmath>
#include <map>
#include <string>
#include <vector>

#include "wpoa/malus_record.h"

using namespace json_spirit;

static const double EPS = 1e-12;

// ---- helpers -------------------------------------------------------------

// Build the inner record object a reporter publishes.
static Object make_inner(const std::string& kind, const std::string& addr,
                         int64_t height, const std::vector<std::string>& blocks)
{
    Array arr;
    for (size_t i = 0; i < blocks.size(); i++)
    {
        arr.push_back(blocks[i]);
    }
    Object inner;
    inner.push_back(Pair(MC_WPOA_MALUS_FIELD_KIND, kind));
    inner.push_back(Pair(MC_WPOA_MALUS_FIELD_ADDR, addr));
    inner.push_back(Pair(MC_WPOA_MALUS_FIELD_HEIGHT, height));
    inner.push_back(Pair(MC_WPOA_MALUS_FIELD_BLOCKS, arr));
    return inner;
}

// Wrap as the value returned by OpReturnFormatEntry's 6-argument overload.
static Value wrap_json(const Value& inner)
{
    Object outer;
    outer.push_back(Pair("json", inner));
    return Value(outer);
}

// The 3-argument overload wraps one level deeper; the parser must accept both.
static Value wrap_formatdata(const Value& inner)
{
    Object outer;
    outer.push_back(Pair("format", std::string("json")));
    outer.push_back(Pair("formatdata", wrap_json(inner)));
    return Value(outer);
}

static std::vector<std::string> two_blocks()
{
    std::vector<std::string> b;
    b.push_back("aa11");
    b.push_back("bb22");
    return b;
}

static std::vector<std::string> one_block()
{
    std::vector<std::string> b;
    b.push_back("cc33");
    return b;
}

// ---- parsing: happy paths ------------------------------------------------

BOOST_AUTO_TEST_CASE(parse_equivocation_record)
{
    Value data = wrap_json(make_inner("equiv", "1Accused", 120, two_blocks()));

    MalusKind kind; std::string addr; int height; std::vector<std::string> blocks;
    BOOST_CHECK(mc_ParseMalusRecordJson(data, kind, addr, height, blocks));
    BOOST_CHECK_EQUAL((int)kind, (int)MALUS_EQUIV);
    BOOST_CHECK_EQUAL(addr, "1Accused");
    BOOST_CHECK_EQUAL(height, 120);
    BOOST_CHECK_EQUAL(blocks.size(), 2u);
    BOOST_CHECK_EQUAL(blocks[0], "aa11");
    BOOST_CHECK_EQUAL(blocks[1], "bb22");
}

BOOST_AUTO_TEST_CASE(parse_delay_record)
{
    Value data = wrap_json(make_inner("delay", "1Accused", 7, one_block()));

    MalusKind kind; std::string addr; int height; std::vector<std::string> blocks;
    BOOST_CHECK(mc_ParseMalusRecordJson(data, kind, addr, height, blocks));
    BOOST_CHECK_EQUAL((int)kind, (int)MALUS_DELAY);
    BOOST_CHECK_EQUAL(blocks.size(), 1u);
}

// The wrapped shape must decode identically — the same regression guard the
// weight-record suite carries, for the bug where every on-chain item silently
// failed to decode.
BOOST_AUTO_TEST_CASE(parse_accepts_formatdata_wrapping)
{
    Value data = wrap_formatdata(make_inner("equiv", "1Accused", 9, two_blocks()));

    MalusKind kind; std::string addr; int height; std::vector<std::string> blocks;
    BOOST_CHECK(mc_ParseMalusRecordJson(data, kind, addr, height, blocks));
    BOOST_CHECK_EQUAL((int)kind, (int)MALUS_EQUIV);
    BOOST_CHECK_EQUAL(addr, "1Accused");
}

BOOST_AUTO_TEST_CASE(kind_string_roundtrip)
{
    BOOST_CHECK_EQUAL((int)mc_MalusKindFromString("equiv"), (int)MALUS_EQUIV);
    BOOST_CHECK_EQUAL((int)mc_MalusKindFromString("delay"), (int)MALUS_DELAY);
    BOOST_CHECK_EQUAL((int)mc_MalusKindFromString("nonsense"), (int)MALUS_NONE);
    BOOST_CHECK_EQUAL(std::string(mc_MalusKindToString(MALUS_EQUIV)), "equiv");
    BOOST_CHECK_EQUAL(std::string(mc_MalusKindToString(MALUS_DELAY)), "delay");
}

// ---- parsing: malformed records are rejected ------------------------------
//
// The stream is open to everyone, so the parser is the first line of defence:
// anything it accepts goes on to the (much more expensive) evidence check.

BOOST_AUTO_TEST_CASE(parse_rejects_unknown_kind)
{
    Value data = wrap_json(make_inner("slashing", "1Accused", 5, one_block()));

    MalusKind kind; std::string addr; int height; std::vector<std::string> blocks;
    BOOST_CHECK(!mc_ParseMalusRecordJson(data, kind, addr, height, blocks));
    BOOST_CHECK_EQUAL((int)kind, (int)MALUS_NONE);
}

BOOST_AUTO_TEST_CASE(parse_rejects_empty_address)
{
    Value data = wrap_json(make_inner("delay", "", 5, one_block()));

    MalusKind kind; std::string addr; int height; std::vector<std::string> blocks;
    BOOST_CHECK(!mc_ParseMalusRecordJson(data, kind, addr, height, blocks));
}

BOOST_AUTO_TEST_CASE(parse_rejects_non_positive_height)
{
    MalusKind kind; std::string addr; int height; std::vector<std::string> blocks;
    BOOST_CHECK(!mc_ParseMalusRecordJson(wrap_json(make_inner("delay", "1A", 0, one_block())),
                                         kind, addr, height, blocks));
    BOOST_CHECK(!mc_ParseMalusRecordJson(wrap_json(make_inner("delay", "1A", -3, one_block())),
                                         kind, addr, height, blocks));
}

// An equivocation names two blocks and a delay violation exactly one: a record
// carrying the wrong count cannot describe the violation it claims.
BOOST_AUTO_TEST_CASE(parse_rejects_wrong_block_count)
{
    MalusKind kind; std::string addr; int height; std::vector<std::string> blocks;
    BOOST_CHECK(!mc_ParseMalusRecordJson(wrap_json(make_inner("equiv", "1A", 5, one_block())),
                                         kind, addr, height, blocks));
    BOOST_CHECK(!mc_ParseMalusRecordJson(wrap_json(make_inner("delay", "1A", 5, two_blocks())),
                                         kind, addr, height, blocks));
    BOOST_CHECK(!mc_ParseMalusRecordJson(wrap_json(make_inner("equiv", "1A", 5,
                                                              std::vector<std::string>())),
                                         kind, addr, height, blocks));
}

BOOST_AUTO_TEST_CASE(parse_rejects_non_object_and_missing_json)
{
    MalusKind kind; std::string addr; int height; std::vector<std::string> blocks;
    BOOST_CHECK(!mc_ParseMalusRecordJson(Value("not an object"), kind, addr, height, blocks));

    Object bare;
    bare.push_back(Pair("kind", std::string("delay")));
    BOOST_CHECK(!mc_ParseMalusRecordJson(Value(bare), kind, addr, height, blocks));
}

// ---- Points --------------------------------------------------------------

BOOST_AUTO_TEST_CASE(points_per_kind)
{
    BOOST_CHECK_CLOSE(MalusAccumulator::Points(MALUS_EQUIV, 4.0, 0.25), 4.0, 1e-9);
    BOOST_CHECK_CLOSE(MalusAccumulator::Points(MALUS_DELAY, 4.0, 0.25), 0.25, 1e-9);
    BOOST_CHECK_SMALL(MalusAccumulator::Points(MALUS_NONE, 4.0, 0.25), EPS);
}

// ---- Fold: the exponential moving average --------------------------------

BOOST_AUTO_TEST_CASE(fold_matches_definition)
{
    // M^(e) = mu * M^(e-1) + points
    BOOST_CHECK_CLOSE(MalusAccumulator::Fold(0.0, 4.0, 0.5), 4.0, 1e-9);
    BOOST_CHECK_CLOSE(MalusAccumulator::Fold(4.0, 0.0, 0.5), 2.0, 1e-9);
    BOOST_CHECK_CLOSE(MalusAccumulator::Fold(4.0, 1.0, 0.5), 3.0, 1e-9);
    BOOST_CHECK_CLOSE(MalusAccumulator::Fold(3.0, 0.0, 0.25), 0.75, 1e-9);
}

// The whole point of an EMA rather than a counter: with no new reports the
// accumulator decays monotonically towards zero.
BOOST_AUTO_TEST_CASE(fold_decays_without_new_reports)
{
    double M = 8.0;
    double prev = M;
    for (int i = 0; i < 20; i++)
    {
        M = MalusAccumulator::Fold(M, 0.0, 0.5);
        BOOST_CHECK(M < prev);
        prev = M;
    }
    BOOST_CHECK(M < 1e-5);
}

BOOST_AUTO_TEST_CASE(fold_is_defensive_on_degenerate_input)
{
    BOOST_CHECK_SMALL(MalusAccumulator::Fold(-5.0, 0.0, 0.5), EPS);   // negative prev
    BOOST_CHECK_CLOSE(MalusAccumulator::Fold(2.0, -1.0, 0.5), 1.0, 1e-9); // negative points
    BOOST_CHECK_CLOSE(MalusAccumulator::Fold(2.0, 0.0, -1.0), 0.0, 1e-9); // negative mu -> 0
}

// ---- Psi: the correction factor ------------------------------------------

BOOST_AUTO_TEST_CASE(psi_is_identity_for_clean_validators)
{
    // The mechanism must be a no-op on honest behaviour.
    BOOST_CHECK_CLOSE(MalusAccumulator::CorrectionFactor(0.0, 4.0), 1.0, 1e-9);
}

BOOST_AUTO_TEST_CASE(psi_decreases_linearly_to_zero_at_the_threshold)
{
    BOOST_CHECK_CLOSE(MalusAccumulator::CorrectionFactor(1.0, 4.0), 0.75, 1e-9);
    BOOST_CHECK_CLOSE(MalusAccumulator::CorrectionFactor(2.0, 4.0), 0.50, 1e-9);
    BOOST_CHECK_CLOSE(MalusAccumulator::CorrectionFactor(3.0, 4.0), 0.25, 1e-9);
    BOOST_CHECK_SMALL(MalusAccumulator::CorrectionFactor(4.0, 4.0), EPS);
    BOOST_CHECK_SMALL(MalusAccumulator::CorrectionFactor(9.0, 4.0), EPS);  // clamped at 0
}

BOOST_AUTO_TEST_CASE(psi_stays_within_unit_interval)
{
    for (double M = 0.0; M <= 10.0; M += 0.13)
    {
        double psi = MalusAccumulator::CorrectionFactor(M, 4.0);
        BOOST_CHECK(psi >= 0.0 && psi <= 1.0);
    }
    // A degenerate threshold disables the correction rather than dividing by zero.
    BOOST_CHECK_CLOSE(MalusAccumulator::CorrectionFactor(5.0, 0.0), 1.0, 1e-9);
}

// ---- w_eff ---------------------------------------------------------------

BOOST_AUTO_TEST_CASE(effective_weight_applies_psi)
{
    BOOST_CHECK_EQUAL(MalusAccumulator::EffectiveWeight(100, 1.0), 100u);
    BOOST_CHECK_EQUAL(MalusAccumulator::EffectiveWeight(100, 0.5), 50u);
    BOOST_CHECK_EQUAL(MalusAccumulator::EffectiveWeight(100, 0.25), 25u);
    BOOST_CHECK_EQUAL(MalusAccumulator::EffectiveWeight(100, 0.0), 0u);   // excluded
}

// Psi > 0 must never silently exclude: a validator keeping a fraction of its
// weight keeps at least 1, so only Psi == 0 makes it ineligible.
BOOST_AUTO_TEST_CASE(effective_weight_floors_at_one_while_psi_is_positive)
{
    BOOST_CHECK_EQUAL(MalusAccumulator::EffectiveWeight(1, 0.001), 1u);
    BOOST_CHECK_EQUAL(MalusAccumulator::EffectiveWeight(3, 0.01), 1u);
    BOOST_CHECK_EQUAL(MalusAccumulator::EffectiveWeight(0, 1.0), 0u);    // no raw weight
}

BOOST_AUTO_TEST_CASE(effective_weight_is_monotone_in_psi)
{
    // Step over integers, so psi hits exactly 0.0 and exactly 1.0 (a `psi += 0.05`
    // loop accumulates rounding and stops short of the endpoint).
    uint32_t prev = 0;
    for (int i = 0; i <= 20; i++)
    {
        uint32_t w = MalusAccumulator::EffectiveWeight(1000, i / 20.0);
        BOOST_CHECK(w >= prev);
        prev = w;
    }
    BOOST_CHECK_EQUAL(prev, 1000u);
}

// ---- ApplyToWeights: the map-level transform -----------------------------

BOOST_AUTO_TEST_CASE(apply_leaves_unaccused_validators_untouched)
{
    std::map<std::string, uint32_t> weights;
    weights["a"] = 100; weights["b"] = 200; weights["c"] = 300;

    std::map<std::string, double> none;   // nobody carries any malus
    std::map<std::string, uint32_t> out;
    MalusAccumulator::ApplyToWeights(weights, none, 4.0, out);

    BOOST_CHECK(out == weights);          // enabling the registry on a clean chain is a no-op
}

BOOST_AUTO_TEST_CASE(apply_corrects_only_the_accused)
{
    std::map<std::string, uint32_t> weights;
    weights["a"] = 100; weights["b"] = 200; weights["c"] = 300;

    std::map<std::string, double> M;
    M["b"] = 2.0;                          // Psi = 0.5
    M["c"] = 4.0;                          // Psi = 0   -> excluded

    std::map<std::string, uint32_t> out;
    MalusAccumulator::ApplyToWeights(weights, M, 4.0, out);

    BOOST_CHECK_EQUAL(out["a"], 100u);
    BOOST_CHECK_EQUAL(out["b"], 100u);
    BOOST_CHECK_EQUAL(out["c"], 0u);
}

// ---- Reversibility: no permanent ban -------------------------------------

BOOST_AUTO_TEST_CASE(exclusion_clears_after_the_computed_number_of_clean_epochs)
{
    const double Mmax = 4.0, mu = 0.5;

    // One proved equivocation at p = 8 puts the validator over the threshold.
    double M = MalusAccumulator::Fold(0.0, 8.0, mu);
    BOOST_CHECK(M >= Mmax);
    BOOST_CHECK_SMALL(MalusAccumulator::CorrectionFactor(M, Mmax), EPS);

    int k = MalusAccumulator::EpochsToClear(M, Mmax, mu);
    BOOST_CHECK(k > 0);

    // Not eligible before k clean epochs...
    double Mk = M;
    for (int i = 0; i < k - 1; i++)
    {
        Mk = MalusAccumulator::Fold(Mk, 0.0, mu);
    }
    BOOST_CHECK(Mk >= Mmax);

    // ...and eligible exactly at k.
    Mk = MalusAccumulator::Fold(Mk, 0.0, mu);
    BOOST_CHECK(Mk < Mmax);
    BOOST_CHECK(MalusAccumulator::CorrectionFactor(Mk, Mmax) > 0.0);
    BOOST_CHECK(MalusAccumulator::EffectiveWeight(100, MalusAccumulator::CorrectionFactor(Mk, Mmax)) > 0u);
}

BOOST_AUTO_TEST_CASE(epochs_to_clear_edge_cases)
{
    BOOST_CHECK_EQUAL(MalusAccumulator::EpochsToClear(1.0, 4.0, 0.5), 0);   // not excluded
    BOOST_CHECK_EQUAL(MalusAccumulator::EpochsToClear(8.0, 4.0, 0.0), 1);   // mu = 0 wipes M
    BOOST_CHECK_EQUAL(MalusAccumulator::EpochsToClear(8.0, 4.0, 1.0), -1);  // no decay (forbidden)
}

// A validator excluded for any finite accumulator always recovers: this is the
// property that distinguishes the malus from a permanent ban.
BOOST_AUTO_TEST_CASE(every_exclusion_is_reversible)
{
    const double Mmax = 4.0;
    const double mus[] = { 0.1, 0.25, 0.5, 0.75, 0.9, 0.99 };

    for (size_t i = 0; i < sizeof(mus) / sizeof(mus[0]); i++)
    {
        double M = 1000.0;   // an extreme accumulated severity
        int k = MalusAccumulator::EpochsToClear(M, Mmax, mus[i]);
        BOOST_CHECK(k > 0);

        for (int e = 0; e < k; e++)
        {
            M = MalusAccumulator::Fold(M, 0.0, mus[i]);
        }
        BOOST_CHECK(M < Mmax);
    }
}
