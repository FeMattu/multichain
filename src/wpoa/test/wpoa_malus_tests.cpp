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

// A selfwrite report: evidence is the offending TRANSACTION, plus the stream it was
// written to and the node_address its payload claimed.
static Object make_selfwrite(const std::string& accused, int64_t height,
                             const std::string& txid, const std::string& stream,
                             const std::string& declared)
{
    std::vector<std::string> refs;
    refs.push_back(txid);
    Object inner = make_inner(MC_WPOA_MALUS_KIND_SELFWRITE, accused, height, refs);
    inner.push_back(Pair(MC_WPOA_MALUS_FIELD_STREAM, stream));
    inner.push_back(Pair(MC_WPOA_MALUS_FIELD_DECLARED_ADDR, declared));
    return inner;
}

// A badweight report: evidence is the offending TRANSACTION, plus the epoch it claimed
// and the two values that disagree.
static Object make_badweight(const std::string& accused, int64_t height,
                             const std::string& txid, int64_t epoch,
                             int64_t declared, int64_t recomputed)
{
    std::vector<std::string> refs;
    refs.push_back(txid);
    Object inner = make_inner(MC_WPOA_MALUS_KIND_BADWEIGHT, accused, height, refs);
    inner.push_back(Pair(MC_WPOA_MALUS_FIELD_EPOCH, epoch));
    inner.push_back(Pair(MC_WPOA_MALUS_FIELD_DECLARED, declared));
    inner.push_back(Pair(MC_WPOA_MALUS_FIELD_RECOMPUTED, recomputed));
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

// ---- the published-data integrity kinds ----------------------------------
//
// The second family of violations: what a node WROTE to a stream the weight pipeline
// reads, rather than how it behaved while producing a block. The evidence is the
// publishing transaction; these cases cover the SHAPE of such a report, which is what
// the pure layer can decide. Whether the accusation is TRUE is re-derived from the
// referenced transaction by MalusRegistry::ValidDataIntegrityReport, which needs the
// chain and is exercised by the functional suite.

BOOST_AUTO_TEST_CASE(parse_selfwrite_record)
{
    MalusKind kind; std::string addr; int height; std::vector<std::string> refs;
    MalusDataDetail d;
    BOOST_REQUIRE(mc_ParseMalusRecordJson(
        wrap_json(make_selfwrite("SIGNER_A", 120, "tx1", "weight-engine-membership",
                                 "VICTIM_B")),
        kind, addr, height, refs, &d));
    BOOST_CHECK_EQUAL(kind, MALUS_SELF_WRITE);
    BOOST_CHECK_EQUAL(addr, "SIGNER_A");          // the accused is the SIGNER
    BOOST_CHECK_EQUAL(height, 120);
    BOOST_CHECK_EQUAL(refs.size(), 1u);           // one TRANSACTION, not two blocks
    BOOST_CHECK_EQUAL(refs[0], "tx1");
    BOOST_CHECK_EQUAL(d.stream, "weight-engine-membership");
    BOOST_CHECK_EQUAL(d.declared_address, "VICTIM_B");
}

BOOST_AUTO_TEST_CASE(parse_badweight_record)
{
    MalusKind kind; std::string addr; int height; std::vector<std::string> refs;
    MalusDataDetail d;
    BOOST_REQUIRE(mc_ParseMalusRecordJson(
        wrap_json(make_badweight("MINER_A", 200, "tx2", 5, 99999, 300)),
        kind, addr, height, refs, &d));
    BOOST_CHECK_EQUAL(kind, MALUS_INVALID_WEIGHT);
    BOOST_CHECK_EQUAL(addr, "MINER_A");
    BOOST_CHECK_EQUAL(d.epoch, 5u);
    BOOST_CHECK_EQUAL(d.declared, 99999u);
    BOOST_CHECK_EQUAL(d.recomputed, 300u);
}

// A selfwrite report must name the stream and the impersonated address: without them the
// accusation is not self-describing, so a third party could not audit it without
// searching. Incompleteness is a SHAPE failure, decided here.
BOOST_AUTO_TEST_CASE(parse_rejects_selfwrite_without_its_fields)
{
    MalusKind kind; std::string addr; int height; std::vector<std::string> refs;

    std::vector<std::string> one; one.push_back("tx1");
    BOOST_CHECK(!mc_ParseMalusRecordJson(
        wrap_json(make_inner(MC_WPOA_MALUS_KIND_SELFWRITE, "SIGNER_A", 120, one)),
        kind, addr, height, refs));                       // no stream, no declared_address

    Object no_declared = make_inner(MC_WPOA_MALUS_KIND_SELFWRITE, "SIGNER_A", 120, one);
    no_declared.push_back(Pair(MC_WPOA_MALUS_FIELD_STREAM, std::string("wpoa-weights")));
    BOOST_CHECK(!mc_ParseMalusRecordJson(wrap_json(no_declared), kind, addr, height, refs));
}

// A record declaring the accused's OWN address is the HONEST case — the reader accepts
// it — so accusing it is malformed rather than merely false. Rejecting it in the parser
// stops such a report from ever reaching the accumulator.
BOOST_AUTO_TEST_CASE(parse_rejects_selfwrite_accusing_an_honest_record)
{
    MalusKind kind; std::string addr; int height; std::vector<std::string> refs;
    BOOST_CHECK(!mc_ParseMalusRecordJson(
        wrap_json(make_selfwrite("SIGNER_A", 120, "tx1", "wpoa-weights", "SIGNER_A")),
        kind, addr, height, refs));
}

// A badweight report needs a real epoch (epochs are 1-based) and a positive declared
// value, since the weight stream only carries strictly positive weights.
BOOST_AUTO_TEST_CASE(parse_rejects_badweight_without_epoch_or_value)
{
    MalusKind kind; std::string addr; int height; std::vector<std::string> refs;
    BOOST_CHECK(!mc_ParseMalusRecordJson(
        wrap_json(make_badweight("MINER_A", 200, "tx2", 0, 99999, 300)),
        kind, addr, height, refs));                       // epoch 0
    BOOST_CHECK(!mc_ParseMalusRecordJson(
        wrap_json(make_badweight("MINER_A", 200, "tx2", 5, 0, 300)),
        kind, addr, height, refs));                       // declared 0
}

// NO FALSE POSITIVE ON A CORRECT WEIGHT. Equal values are an accusation that nothing is
// wrong, and it is rejected before it can score anything.
BOOST_AUTO_TEST_CASE(parse_rejects_badweight_where_the_values_agree)
{
    MalusKind kind; std::string addr; int height; std::vector<std::string> refs;
    BOOST_CHECK(!mc_ParseMalusRecordJson(
        wrap_json(make_badweight("MINER_A", 200, "tx2", 5, 750, 750)),
        kind, addr, height, refs));
}

// recomputed == 0 IS legitimate: that is what an address heading no cluster recomputes
// to, so "published 5000, recomputes to nothing" must be reportable.
BOOST_AUTO_TEST_CASE(parse_accepts_badweight_against_a_non_cluster)
{
    MalusKind kind; std::string addr; int height; std::vector<std::string> refs;
    MalusDataDetail d;
    BOOST_REQUIRE(mc_ParseMalusRecordJson(
        wrap_json(make_badweight("NOT_A_MINER", 200, "tx2", 5, 5000, 0)),
        kind, addr, height, refs, &d));
    BOOST_CHECK_EQUAL(d.recomputed, 0u);
}

// One transaction, never two: the reference count is per kind and single-sourced.
BOOST_AUTO_TEST_CASE(parse_rejects_data_integrity_with_two_references)
{
    MalusKind kind; std::string addr; int height; std::vector<std::string> refs;
    std::vector<std::string> two;
    two.push_back("tx1");
    two.push_back("tx2");
    Object o = make_inner(MC_WPOA_MALUS_KIND_SELFWRITE, "SIGNER_A", 120, two);
    o.push_back(Pair(MC_WPOA_MALUS_FIELD_STREAM, std::string("wpoa-weights")));
    o.push_back(Pair(MC_WPOA_MALUS_FIELD_DECLARED_ADDR, std::string("VICTIM_B")));
    BOOST_CHECK(!mc_ParseMalusRecordJson(wrap_json(o), kind, addr, height, refs));

    BOOST_CHECK_EQUAL(mc_MalusKindRefCount(MALUS_EQUIV), 2u);
    BOOST_CHECK_EQUAL(mc_MalusKindRefCount(MALUS_DELAY), 1u);
    BOOST_CHECK_EQUAL(mc_MalusKindRefCount(MALUS_SELF_WRITE), 1u);
    BOOST_CHECK_EQUAL(mc_MalusKindRefCount(MALUS_INVALID_WEIGHT), 1u);
}

BOOST_AUTO_TEST_CASE(kind_families_are_classified)
{
    BOOST_CHECK(!mc_MalusKindIsDataIntegrity(MALUS_EQUIV));
    BOOST_CHECK(!mc_MalusKindIsDataIntegrity(MALUS_DELAY));
    BOOST_CHECK(!mc_MalusKindIsDataIntegrity(MALUS_NONE));
    BOOST_CHECK(mc_MalusKindIsDataIntegrity(MALUS_SELF_WRITE));
    BOOST_CHECK(mc_MalusKindIsDataIntegrity(MALUS_INVALID_WEIGHT));
}

// ---- Points --------------------------------------------------------------

BOOST_AUTO_TEST_CASE(points_per_kind)
{
    BOOST_CHECK_CLOSE(MalusAccumulator::Points(MALUS_EQUIV, 4.0, 0.25), 4.0, 1e-9);
    BOOST_CHECK_CLOSE(MalusAccumulator::Points(MALUS_DELAY, 4.0, 0.25), 0.25, 1e-9);
    BOOST_CHECK_SMALL(MalusAccumulator::Points(MALUS_NONE, 4.0, 0.25), EPS);
}

// The four-score dispatch. Adding a kind touches ONLY this function: Fold, Psi, w_eff,
// EpochsToClear and ApplyToWeights all operate on the accumulated severity M rather than
// on what produced it, so they were already generic. This case pins that the new kinds
// are scored and that the ordering argument holds.
BOOST_AUTO_TEST_CASE(points_covers_the_data_integrity_kinds)
{
    const MalusScores s(4.0, 0.25, 1.0, 2.0);
    BOOST_CHECK_CLOSE(MalusAccumulator::Points(MALUS_EQUIV, s), 4.0, 1e-9);
    BOOST_CHECK_CLOSE(MalusAccumulator::Points(MALUS_DELAY, s), 0.25, 1e-9);
    BOOST_CHECK_CLOSE(MalusAccumulator::Points(MALUS_SELF_WRITE, s), 1.0, 1e-9);
    BOOST_CHECK_CLOSE(MalusAccumulator::Points(MALUS_INVALID_WEIGHT, s), 2.0, 1e-9);
    BOOST_CHECK_SMALL(MalusAccumulator::Points(MALUS_NONE, s), EPS);

    // The severity ordering the protocol enforces at startup: equivocation threatens
    // safety; a false weight succeeds unless recomputed; a forged record is always
    // discarded, so its score prices the attempt; a delay violation is the lightest.
    BOOST_CHECK(MalusAccumulator::Points(MALUS_EQUIV, s) >
                MalusAccumulator::Points(MALUS_INVALID_WEIGHT, s));
    BOOST_CHECK(MalusAccumulator::Points(MALUS_INVALID_WEIGHT, s) >
                MalusAccumulator::Points(MALUS_SELF_WRITE, s));
    BOOST_CHECK(MalusAccumulator::Points(MALUS_SELF_WRITE, s) >
                MalusAccumulator::Points(MALUS_DELAY, s));
}

// The two-score form must keep working for callers that only handle the behavioural
// kinds — it scores the data-integrity kinds 0, which is the correct reading of "no
// score configured for them" rather than a silent misattribution.
BOOST_AUTO_TEST_CASE(points_two_score_form_stays_backward_compatible)
{
    BOOST_CHECK_CLOSE(MalusAccumulator::Points(MALUS_EQUIV, 4.0, 0.25), 4.0, 1e-9);
    BOOST_CHECK_SMALL(MalusAccumulator::Points(MALUS_SELF_WRITE, 4.0, 0.25), EPS);
    BOOST_CHECK_SMALL(MalusAccumulator::Points(MALUS_INVALID_WEIGHT, 4.0, 0.25), EPS);
}

// END TO END THROUGH THE CORRECTION, for a data-integrity violation: one proved
// badweight report reduces Psi, hence w_eff, from the NEXT epoch — and the reduction
// then decays away over clean epochs exactly as it does for a behavioural violation.
// This is what "the same severity scale carries both families" means concretely.
BOOST_AUTO_TEST_CASE(a_proved_badweight_reduces_effective_weight_then_decays)
{
    const MalusScores sc(4.0, 0.25, 1.0, 2.0);
    const double Mmax = 4.0, mu = 0.5;
    const uint32_t raw = 1000;

    // Epoch e: clean. Psi = 1, so the mechanism is inert.
    double M0 = 0.0;
    BOOST_CHECK_CLOSE(MalusAccumulator::CorrectionFactor(M0, Mmax), 1.0, 1e-9);
    BOOST_CHECK_EQUAL(MalusAccumulator::EffectiveWeight(raw, 1.0), raw);

    // Epoch e+1: one proved badweight. M = 2, Psi = 1 - 2/4 = 0.5, w_eff halves.
    double M1 = MalusAccumulator::Fold(M0, MalusAccumulator::Points(MALUS_INVALID_WEIGHT, sc), mu);
    BOOST_CHECK_CLOSE(M1, 2.0, 1e-9);
    double psi1 = MalusAccumulator::CorrectionFactor(M1, Mmax);
    BOOST_CHECK_CLOSE(psi1, 0.5, 1e-9);
    BOOST_CHECK_EQUAL(MalusAccumulator::EffectiveWeight(raw, psi1), 500u);

    // A second one in the following epoch reaches the threshold: M = 0.5*2 + 2 = 3.
    double M2 = MalusAccumulator::Fold(M1, MalusAccumulator::Points(MALUS_INVALID_WEIGHT, sc), mu);
    BOOST_CHECK_CLOSE(M2, 3.0, 1e-9);
    BOOST_CHECK_CLOSE(MalusAccumulator::CorrectionFactor(M2, Mmax), 0.25, 1e-9);

    // Clean epochs afterwards: the memory decays and the weight comes back. No
    // permanent ban for a data-integrity violation either.
    double M3 = MalusAccumulator::Fold(M2, 0.0, mu);
    BOOST_CHECK_CLOSE(M3, 1.5, 1e-9);
    BOOST_CHECK(MalusAccumulator::CorrectionFactor(M3, Mmax) >
                MalusAccumulator::CorrectionFactor(M2, Mmax));
}

// A selfwrite and a badweight in the same epoch accumulate together: one accumulator
// carries both families, so a node cannot spread misbehaviour across kinds to stay under
// the threshold.
BOOST_AUTO_TEST_CASE(the_two_families_accumulate_into_one_severity)
{
    const MalusScores sc(4.0, 0.25, 1.0, 2.0);
    double epoch_points = MalusAccumulator::Points(MALUS_SELF_WRITE, sc)
                        + MalusAccumulator::Points(MALUS_INVALID_WEIGHT, sc)
                        + MalusAccumulator::Points(MALUS_DELAY, sc);
    double M = MalusAccumulator::Fold(0.0, epoch_points, 0.5);
    BOOST_CHECK_CLOSE(M, 3.25, 1e-9);

    // And a node with only data-integrity violations is excluded exactly as one with
    // only behavioural violations would be, once M reaches M_max.
    double heavy = MalusAccumulator::Fold(0.0, 2.0 * MalusAccumulator::Points(MALUS_INVALID_WEIGHT, sc), 0.5);
    BOOST_CHECK_CLOSE(heavy, 4.0, 1e-9);
    BOOST_CHECK_SMALL(MalusAccumulator::CorrectionFactor(heavy, 4.0), EPS);
    BOOST_CHECK_EQUAL(MalusAccumulator::EffectiveWeight(1000, 0.0), 0u);
    BOOST_CHECK(MalusAccumulator::EpochsToClear(heavy, 4.0, 0.5) >= 1);
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
