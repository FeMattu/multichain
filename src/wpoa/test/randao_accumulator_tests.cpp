// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA Phase 3b — unit tests for the pure RANDAO accumulator + seed core
// (src/wpoa/randao_accumulator.h, class RandaoAccumulator).
//
// These tests are self-contained: they link only SHA256 and Boost.Test
// (header-only), NOT the wallet / node runtime. Build & run with
// src/wpoa/test/run_randao_unit_tests.sh.
//
// They validate, node-free, every property the beacon relies on:
//   * spec conformance — Fold == H(R_tot_prev ⊕ H(reveal)) and
//     DeriveSeed == H(R_tot ‖ h_prev ‖ height_be) exactly (thesis §5.4–§5.5),
//     checked against an INDEPENDENT re-implementation of the formulas;
//   * determinism — identical inputs always yield identical outputs;
//   * order sensitivity — the accumulator is history-dependent (folding the same
//     reveals in a different order gives a different R_tot);
//   * avalanche/sensitivity — a one-bit change in any input flips the output;
//   * chain consistency — folding a sequence step-by-step matches the recurrence
//     and distinct heights give distinct, well-spread seeds.

#define BOOST_TEST_MODULE wPoARandaoTests
#include <boost/test/included/unit_test.hpp>

#include <cstring>
#include <set>
#include <string>
#include <vector>

#include "wpoa/randao_accumulator.h"
#include "crypto/sha256.h"

// ---- helpers -------------------------------------------------------------

typedef std::vector<unsigned char> bytes;

static bytes H32() { return bytes(RandaoAccumulator::HASH_SIZE, 0); }

// A distinct, well-mixed 32-byte value per index (SHA256 of the index), standing
// in for a VRF reveal / block hash.
static bytes make_val(uint32_t i)
{
    unsigned char in[4];
    in[0] = (unsigned char)((i >> 24) & 0xff);
    in[1] = (unsigned char)((i >> 16) & 0xff);
    in[2] = (unsigned char)((i >> 8) & 0xff);
    in[3] = (unsigned char)(i & 0xff);
    bytes out(32);
    CSHA256().Write(in, 4).Finalize(&out[0]);
    return out;
}

// Independent reference implementation of the thesis §5.4 fold, written straight
// from the formula (not sharing code with RandaoAccumulator), so a bug in the
// header cannot hide behind a shared helper.
static bytes ref_fold(const bytes& prev, const bytes& reveal)
{
    bytes t(32);
    CSHA256().Write(&reveal[0], reveal.size()).Finalize(&t[0]);
    bytes x(32);
    for (size_t i = 0; i < 32; i++) x[i] = (unsigned char)(prev[i] ^ t[i]);
    bytes out(32);
    CSHA256().Write(&x[0], 32).Finalize(&out[0]);
    return out;
}

// Independent reference implementation of the thesis §5.5 seed derivation.
static bytes ref_seed(const bytes& rtot, const bytes& hprev, uint32_t height)
{
    unsigned char hb[4];
    hb[0] = (unsigned char)((height >> 24) & 0xff);
    hb[1] = (unsigned char)((height >> 16) & 0xff);
    hb[2] = (unsigned char)((height >> 8) & 0xff);
    hb[3] = (unsigned char)(height & 0xff);
    bytes out(32);
    CSHA256().Write(&rtot[0], 32).Write(&hprev[0], 32).Write(hb, 4).Finalize(&out[0]);
    return out;
}

static bytes core_fold(const bytes& prev, const bytes& reveal)
{
    bytes out(32);
    RandaoAccumulator::Fold(&prev[0], &reveal[0], reveal.size(), &out[0]);
    return out;
}

static bytes core_seed(const bytes& rtot, const bytes& hprev, uint32_t height)
{
    bytes out(32);
    RandaoAccumulator::DeriveSeed(&rtot[0], &hprev[0], height, &out[0]);
    return out;
}

static bool is_zero(const bytes& b)
{
    for (size_t i = 0; i < b.size(); i++) if (b[i] != 0) return false;
    return true;
}

BOOST_AUTO_TEST_SUITE(wpoa_randao_tests)

// ---- Genesis -------------------------------------------------------------

BOOST_AUTO_TEST_CASE(genesis_is_deterministic_and_nonzero)
{
    bytes g1 = H32(), g2 = H32();
    RandaoAccumulator::Genesis(&g1[0]);
    RandaoAccumulator::Genesis(&g2[0]);
    BOOST_CHECK(g1 == g2);            // deterministic
    BOOST_CHECK(!is_zero(g1));        // domain-separated, not all-zero

    // Independently: genesis == SHA256("wPoA-RANDAO-accumulator-genesis-v1").
    const char* tag = "wPoA-RANDAO-accumulator-genesis-v1";
    bytes ref(32);
    CSHA256().Write((const unsigned char*)tag, strlen(tag)).Finalize(&ref[0]);
    BOOST_CHECK(g1 == ref);
}

// ---- Fold (thesis §5.4) --------------------------------------------------

BOOST_AUTO_TEST_CASE(fold_matches_spec)
{
    for (uint32_t i = 0; i < 64; i++)
    {
        bytes prev = make_val(1000 + i);
        bytes reveal = make_val(i);
        BOOST_CHECK(core_fold(prev, reveal) == ref_fold(prev, reveal));
    }
}

BOOST_AUTO_TEST_CASE(fold_is_deterministic)
{
    bytes prev = make_val(7), reveal = make_val(42);
    BOOST_CHECK(core_fold(prev, reveal) == core_fold(prev, reveal));
}

BOOST_AUTO_TEST_CASE(fold_supports_in_out_aliasing)
{
    bytes prev = make_val(11), reveal = make_val(22);
    bytes expected = core_fold(prev, reveal);

    // Fold in place: rtot_out == rtot_prev buffer.
    bytes inplace = prev;
    RandaoAccumulator::Fold(&inplace[0], &reveal[0], reveal.size(), &inplace[0]);
    BOOST_CHECK(inplace == expected);
}

BOOST_AUTO_TEST_CASE(fold_is_sensitive_to_prev_and_reveal)
{
    bytes prev = make_val(3), reveal = make_val(4);
    bytes base = core_fold(prev, reveal);

    bytes prev2 = prev; prev2[0] ^= 0x01;      // flip one bit of the accumulator
    BOOST_CHECK(core_fold(prev2, reveal) != base);

    bytes reveal2 = reveal; reveal2[31] ^= 0x80; // flip one bit of the reveal
    BOOST_CHECK(core_fold(prev, reveal2) != base);
}

BOOST_AUTO_TEST_CASE(accumulator_is_history_order_dependent)
{
    // Folding reveals A then B differs from B then A: the accumulator captures the
    // ORDER of the reveal history, not just the set — as required for a chain.
    bytes g = H32(); RandaoAccumulator::Genesis(&g[0]);
    bytes A = make_val(100), B = make_val(200);

    bytes ab = core_fold(core_fold(g, A), B);
    bytes ba = core_fold(core_fold(g, B), A);
    BOOST_CHECK(ab != ba);
}

BOOST_AUTO_TEST_CASE(accumulator_chain_matches_recurrence)
{
    // Build R_tot over a 50-reveal chain from genesis and confirm each prefix
    // matches an independent step-by-step fold; a longer chain never collides with
    // a shorter one.
    bytes g = H32(); RandaoAccumulator::Genesis(&g[0]);

    std::set<bytes> seen;
    bytes rtot = g;
    seen.insert(rtot);
    for (uint32_t i = 1; i <= 50; i++)
    {
        bytes reveal = make_val(i);
        bytes expect = ref_fold(rtot, reveal);
        rtot = core_fold(rtot, reveal);
        BOOST_CHECK(rtot == expect);
        BOOST_CHECK(seen.find(rtot) == seen.end()); // no collision along the chain
        seen.insert(rtot);
    }
}

// ---- DeriveSeed (thesis §5.5) --------------------------------------------

BOOST_AUTO_TEST_CASE(seed_matches_spec)
{
    bytes rtot = make_val(500), hprev = make_val(600);
    for (uint32_t hgt = 0; hgt < 128; hgt++)
    {
        BOOST_CHECK(core_seed(rtot, hprev, hgt) == ref_seed(rtot, hprev, hgt));
    }
}

BOOST_AUTO_TEST_CASE(seed_is_deterministic)
{
    bytes rtot = make_val(1), hprev = make_val(2);
    BOOST_CHECK(core_seed(rtot, hprev, 12345) == core_seed(rtot, hprev, 12345));
}

BOOST_AUTO_TEST_CASE(seed_is_sensitive_to_every_input)
{
    bytes rtot = make_val(8), hprev = make_val(9);
    bytes base = core_seed(rtot, hprev, 77);

    BOOST_CHECK(core_seed(rtot, hprev, 78) != base);        // height matters

    bytes rtot2 = rtot; rtot2[15] ^= 0x01;
    BOOST_CHECK(core_seed(rtot2, hprev, 77) != base);       // accumulator matters

    bytes hprev2 = hprev; hprev2[0] ^= 0x40;
    BOOST_CHECK(core_seed(rtot, hprev2, 77) != base);       // prev-hash matters
}

BOOST_AUTO_TEST_CASE(seeds_are_distinct_across_heights)
{
    // Even with a fixed accumulator and prev-hash (a slowly-changing beacon), the
    // per-round height keeps the seed fresh: 4096 consecutive heights give 4096
    // distinct seeds.
    bytes rtot = make_val(31337), hprev = make_val(42);
    std::set<bytes> seeds;
    for (uint32_t hgt = 0; hgt < 4096; hgt++)
    {
        seeds.insert(core_seed(rtot, hprev, hgt));
    }
    BOOST_CHECK_EQUAL(seeds.size(), (size_t)4096);
}

BOOST_AUTO_TEST_SUITE_END()
