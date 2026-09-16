// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA — unit tests for the pure core behind the read-only ROUND AUDIT RPCs
// (wpoagetlocalscore / wpoagetnodedelay / wpoalistfinalweights and their siblings,
// implemented in src/rpc/rpcwpoa.cpp).
//
// The RPCs deliberately introduce NO new mathematics: every number they print comes
// from WPoASelector, PrivateSortition or MalusAccumulator, which the consensus path
// calls too. What IS new is one extracted helper —
// WPoASelector::TotalEffectiveWeight, the band normalizer W that the sortition
// context used to inline — so that is pinned here, together with the edge cases the
// audit surface must report rather than error on:
//
//   * a validator with weight 0 (never registered, or excluded by the malus);
//   * a validator at M >= M_max, where Psi = 0 and the effective weight vanishes;
//   * the composition ORDER g(w * Psi), which is what the election consumes;
//   * the degenerate delay inputs, which must yield a maximal delay, never NaN.
//
// Self-contained: links only HMAC-SHA256 / SHA256 and Boost.Test (header-only), NOT
// the wallet / node runtime. Build & run with
//   src/wpoa/test/run_unit_tests.sh audit

#define BOOST_TEST_MODULE wPoAAuditTests
#include <boost/test/included/unit_test.hpp>

#include <cmath>
#include <limits>
#include <map>
#include <string>

#include "wpoa/wpoa_selector.h"
#include "wpoa/private_sortition.h"
#include "wpoa/malus_record.h"

// A fixed, arbitrary 32-byte seed: these tests are about the weight algebra, not
// about the entropy, so one seed is enough and keeps every expectation reproducible.
static void FixedSeed(unsigned char out[32])
{
    for (int i = 0; i < 32; i++)
    {
        out[i] = (unsigned char)(0xA0 + i);
    }
}

// ---------------------------------------------------------------------------
// TotalEffectiveWeight — the band normalizer W
// ---------------------------------------------------------------------------

BOOST_AUTO_TEST_SUITE(wpoa_audit_total_effective_weight)

BOOST_AUTO_TEST_CASE(sums_dumped_weights_under_each_function)
{
    std::map<std::string, uint32_t> w;
    w["addr_a"] = 4;
    w["addr_b"] = 9;

    BOOST_CHECK_CLOSE(WPoASelector::TotalEffectiveWeight(w, DUMP_NONE), 13.0, 1e-9);
    BOOST_CHECK_CLOSE(WPoASelector::TotalEffectiveWeight(w, DUMP_SQRT), 2.0 + 3.0, 1e-9);
    BOOST_CHECK_CLOSE(WPoASelector::TotalEffectiveWeight(w, DUMP_LOG),
                      std::log(5.0) + std::log(10.0), 1e-9);
}

// An empty registry has no band at all. The callers treat a non-positive W as "round
// not evaluable" rather than dividing by it, which is what this pins.
BOOST_AUTO_TEST_CASE(empty_map_has_zero_total)
{
    std::map<std::string, uint32_t> w;
    BOOST_CHECK_EQUAL(WPoASelector::TotalEffectiveWeight(w, DUMP_NONE), 0.0);
    BOOST_CHECK_EQUAL(WPoASelector::TotalEffectiveWeight(w, DUMP_LOG), 0.0);
}

// EDGE CASE: zero weight. A validator outside V+ must contribute nothing to the band
// under every dumping function — including DUMP_LOG, where a naive ln(1+0) is also 0
// but only by accident of the "1 +" shift. Skipping it explicitly makes W the weight
// of the ELIGIBLE set by construction.
BOOST_AUTO_TEST_CASE(zero_weight_contributes_nothing)
{
    std::map<std::string, uint32_t> w;
    w["active"]   = 16;
    w["excluded"] = 0;

    BOOST_CHECK_CLOSE(WPoASelector::TotalEffectiveWeight(w, DUMP_NONE), 16.0, 1e-9);
    BOOST_CHECK_CLOSE(WPoASelector::TotalEffectiveWeight(w, DUMP_SQRT), 4.0, 1e-9);
    BOOST_CHECK_CLOSE(WPoASelector::TotalEffectiveWeight(w, DUMP_LOG), std::log(17.0), 1e-9);

    // ... and the excluded validator does not change W at all.
    std::map<std::string, uint32_t> only_active;
    only_active["active"] = 16;
    BOOST_CHECK_EQUAL(WPoASelector::TotalEffectiveWeight(w, DUMP_SQRT),
                      WPoASelector::TotalEffectiveWeight(only_active, DUMP_SQRT));
}

// The sum runs in the map's sorted-key order, so it cannot depend on insertion order —
// the property the consensus path relies on for bit-identical W across nodes.
BOOST_AUTO_TEST_CASE(insertion_order_does_not_change_the_sum)
{
    std::map<std::string, uint32_t> a, b;
    a["z"] = 7; a["m"] = 3; a["a"] = 11;
    b["a"] = 11; b["z"] = 7; b["m"] = 3;

    BOOST_CHECK_EQUAL(WPoASelector::TotalEffectiveWeight(a, DUMP_LOG),
                      WPoASelector::TotalEffectiveWeight(b, DUMP_LOG));
}

BOOST_AUTO_TEST_SUITE_END()

// ---------------------------------------------------------------------------
// Score reporting: what the audit RPCs must show for an ineligible validator
// ---------------------------------------------------------------------------

BOOST_AUTO_TEST_SUITE(wpoa_audit_score)

// EDGE CASE: weight 0 -> score +inf. The RPCs report this as `null` with
// eligible=false, which is only correct because the score is genuinely infinite and
// not merely large.
BOOST_AUTO_TEST_CASE(zero_weight_scores_infinite)
{
    unsigned char seed[32];
    FixedSeed(seed);

    double s = WPoASelector::ComputeScore(seed, sizeof(seed), "addr_a", 0, DUMP_NONE);
    BOOST_CHECK(std::isinf(s));
    BOOST_CHECK(!std::isfinite(s));

    // A positive weight, by contrast, always yields a finite score.
    double t = WPoASelector::ComputeScore(seed, sizeof(seed), "addr_a", 1, DUMP_NONE);
    BOOST_CHECK(std::isfinite(t));
    BOOST_CHECK(t >= 0.0);
}

// The audit prints the PUBLIC form; this pins that it is a pure function of
// (seed, address, effective weight, dumping) — so two nodes auditing the same round
// print the same number.
BOOST_AUTO_TEST_CASE(score_is_deterministic)
{
    unsigned char seed[32];
    FixedSeed(seed);

    double a = WPoASelector::ComputeScore(seed, sizeof(seed), "addr_a", 100, DUMP_SQRT);
    double b = WPoASelector::ComputeScore(seed, sizeof(seed), "addr_a", 100, DUMP_SQRT);
    BOOST_CHECK_EQUAL(a, b);

    // A different effective weight is a different score: this is what makes the malus
    // visible in the audit at all.
    double c = WPoASelector::ComputeScore(seed, sizeof(seed), "addr_a", 50, DUMP_SQRT);
    BOOST_CHECK(a != c);
}

BOOST_AUTO_TEST_SUITE_END()

// ---------------------------------------------------------------------------
// The two weight stages, and the order they compose in
// ---------------------------------------------------------------------------

BOOST_AUTO_TEST_SUITE(wpoa_audit_weight_stages)

// wpoagetnodeeffectiveweight reports g(w): the dumping stage alone.
BOOST_AUTO_TEST_CASE(effective_weight_is_dumping_only)
{
    BOOST_CHECK_CLOSE(WPoASelector::ApplyDumping(100, DUMP_NONE), 100.0, 1e-9);
    BOOST_CHECK_CLOSE(WPoASelector::ApplyDumping(100, DUMP_SQRT), 10.0, 1e-9);
    BOOST_CHECK_CLOSE(WPoASelector::ApplyDumping(100, DUMP_LOG), std::log(101.0), 1e-9);
}

// wpoagetnodefinalweight reports g(w * Psi) — malus FIRST, dumping SECOND. The two
// orders differ numerically under a non-trivial g, so getting this wrong would make
// the audit disagree with the election.
BOOST_AUTO_TEST_CASE(final_weight_applies_malus_before_dumping)
{
    const double m_max = 4.0;
    const uint32_t raw = 100;
    const double malus = 2.0;                       // half way to exclusion

    const double psi = MalusAccumulator::CorrectionFactor(malus, m_max);
    BOOST_CHECK_CLOSE(psi, 0.5, 1e-9);

    const uint32_t after_malus = MalusAccumulator::EffectiveWeight(raw, psi);
    BOOST_CHECK_EQUAL(after_malus, 50u);

    const double final_weight = WPoASelector::ApplyDumping(after_malus, DUMP_SQRT);
    BOOST_CHECK_CLOSE(final_weight, std::sqrt(50.0), 1e-9);

    // The other order — dump first, then scale by Psi — is a DIFFERENT number.
    const double wrong_order = WPoASelector::ApplyDumping(raw, DUMP_SQRT) * psi;
    BOOST_CHECK(std::fabs(final_weight - wrong_order) > 1e-6);
}

// EDGE CASE: M at M_max. Psi collapses to 0, the effective weight with it, and the
// score becomes infinite — the validator is simply outside V+ for the round. The RPCs
// must return 0 / null here, not an error.
BOOST_AUTO_TEST_CASE(malus_at_max_excludes_the_validator)
{
    const double m_max = 4.0;

    BOOST_CHECK_EQUAL(MalusAccumulator::CorrectionFactor(m_max, m_max), 0.0);
    BOOST_CHECK_EQUAL(MalusAccumulator::CorrectionFactor(2.0 * m_max, m_max), 0.0);

    const uint32_t eff = MalusAccumulator::EffectiveWeight(100, 0.0);
    BOOST_CHECK_EQUAL(eff, 0u);

    unsigned char seed[32];
    FixedSeed(seed);
    BOOST_CHECK(std::isinf(WPoASelector::ComputeScore(seed, sizeof(seed), "addr_a",
                                                      eff, DUMP_SQRT)));

    // And it adds nothing to the band, so the other candidates' delays are unaffected.
    std::map<std::string, uint32_t> w;
    w["addr_a"] = eff;
    w["addr_b"] = 100;
    BOOST_CHECK_CLOSE(WPoASelector::TotalEffectiveWeight(w, DUMP_NONE), 100.0, 1e-9);
}

// A clean validator is untouched: Psi = 1 and the final weight is exactly g(w).
BOOST_AUTO_TEST_CASE(no_malus_leaves_the_weight_alone)
{
    const double psi = MalusAccumulator::CorrectionFactor(0.0, 4.0);
    BOOST_CHECK_CLOSE(psi, 1.0, 1e-9);
    BOOST_CHECK_EQUAL(MalusAccumulator::EffectiveWeight(100, psi), 100u);
}

BOOST_AUTO_TEST_SUITE_END()

// ---------------------------------------------------------------------------
// Delay reporting
// ---------------------------------------------------------------------------

BOOST_AUTO_TEST_SUITE(wpoa_audit_delay)

// The delay the RPC prints is the band of Def. correzione-globale: centred on
// T_block, half-width delta*T_block, shifted by lambda*Phi.
BOOST_AUTO_TEST_CASE(delay_sits_in_the_band)
{
    const double T = 15.0, delta = 0.5, lambda = 0.0;
    const double W = 200.0;

    // A very small score -> normalized score near 0 -> the early edge of the band.
    double early = PrivateSortition::MiningDelay(1e-9, W, T, delta, lambda, 0.0);
    // A large score -> normalized score near 1 -> the late edge.
    double late  = PrivateSortition::MiningDelay(10.0, W, T, delta, lambda, 0.0);

    BOOST_CHECK(early < late);
    BOOST_CHECK(early >= T * (1.0 - delta) - 1e-9);
    BOOST_CHECK(late  <= T * (1.0 + delta) + 1e-9);
}

// The feedback term is common to every candidate, so it shifts the whole band and
// cannot reorder anyone — the property the audit output lets an operator check by
// printing Phi alongside each delay.
BOOST_AUTO_TEST_CASE(feedback_shifts_without_reordering)
{
    const double T = 15.0, delta = 0.4, lambda = 0.5, phi = 2.0;
    const double W = 300.0;

    double a0 = PrivateSortition::MiningDelay(0.001, W, T, delta, lambda, 0.0);
    double b0 = PrivateSortition::MiningDelay(0.010, W, T, delta, lambda, 0.0);
    double a1 = PrivateSortition::MiningDelay(0.001, W, T, delta, lambda, phi);
    double b1 = PrivateSortition::MiningDelay(0.010, W, T, delta, lambda, phi);

    BOOST_CHECK(a0 < b0);
    BOOST_CHECK(a1 < b1);
    BOOST_CHECK_CLOSE(a1 - a0, lambda * phi, 1e-9);
    BOOST_CHECK_CLOSE(b1 - b0, lambda * phi, 1e-9);
}

// EDGE CASE: an infinite score (weight 0) must not produce NaN. NormalizedScore
// saturates at 1, so the delay lands on the late edge of the band — the ineligible
// node stands down instead of scheduling into the past.
BOOST_AUTO_TEST_CASE(infinite_score_yields_the_latest_delay)
{
    const double T = 15.0, delta = 0.5, lambda = 0.0;
    const double inf = std::numeric_limits<double>::infinity();

    double norm = PrivateSortition::NormalizedScore(inf, 100.0);
    BOOST_CHECK_EQUAL(norm, 1.0);

    double d = PrivateSortition::MiningDelay(inf, 100.0, T, delta, lambda, 0.0);
    BOOST_CHECK(std::isfinite(d));
    BOOST_CHECK(d >= 0.0);
}

// EDGE CASE: a zero band normalizer (an empty or fully excluded registry). The RPCs
// refuse the round in that case, but the math must still degrade safely.
BOOST_AUTO_TEST_CASE(zero_total_weight_is_safe)
{
    BOOST_CHECK_EQUAL(PrivateSortition::NormalizedScore(1.0, 0.0), 1.0);

    double d = PrivateSortition::MiningDelay(1.0, 0.0, 15.0, 0.5, 0.0, 0.0);
    BOOST_CHECK(std::isfinite(d));
    BOOST_CHECK(d >= 0.0);
}

BOOST_AUTO_TEST_SUITE_END()
