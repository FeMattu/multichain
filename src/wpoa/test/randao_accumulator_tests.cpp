// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA Phase 3b — unit tests for the pure RANDAO accumulator + seed core
// (src/wpoa/randao_accumulator.h, class RandaoAccumulator).
//
// These tests are self-contained: they link only SHA256 and Boost.Test
// (header-only), NOT the wallet / node runtime. Build & run with
// src/wpoa/test/run_unit_tests.sh randao.
//
// They validate, node-free, every property the beacon relies on:
//   * spec conformance — Fold == R_tot_prev ⊕ reveal (thesis Def. 5.3, §5.4) and
//     DeriveSeed == H(R_tot ‖ h_prev ‖ height_be) exactly (§5.5), checked against an
//     INDEPENDENT re-implementation of the formulas;
//   * determinism — identical inputs always yield identical outputs;
//   * the algebra of a bare XOR — commutativity and self-inverse are real properties
//     of Def. 5.3, pinned here as KNOWN so nobody mistakes them for a bug, together
//     with the reason they are unreachable: the seed re-binds position via h[n]/n+1;
//   * avalanche/sensitivity — a one-bit change in any input changes the output;
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

// Independent reference implementation of the thesis Def. 5.3 fold,
// R_tot[n] = R_tot[n-1] XOR R[n], written straight from the formula (not sharing code
// with RandaoAccumulator), so a bug in the header cannot hide behind a shared helper.
// Takes 32-byte operands, which is what consensus ever folds.
static bytes ref_fold(const bytes& prev, const bytes& reveal)
{
    bytes out(32);
    for (size_t i = 0; i < 32; i++) out[i] = (unsigned char)(prev[i] ^ reveal[i]);
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

// The hardened variant this module used to fold, H(R_tot XOR H(R)). Kept only so the
// realignment to Def. 5.3 can be pinned as a REGRESSION GUARD (see
// fold_is_the_bare_xor_of_definition_5_3): this is the formula the implementation no
// longer computes.
static bytes ref_hardened_fold(const bytes& prev, const bytes& reveal)
{
    bytes t(32);
    CSHA256().Write(&reveal[0], reveal.size()).Finalize(&t[0]);
    bytes x(32);
    for (size_t i = 0; i < 32; i++) x[i] = (unsigned char)(prev[i] ^ t[i]);
    bytes out(32);
    CSHA256().Write(&x[0], 32).Finalize(&out[0]);
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

BOOST_AUTO_TEST_CASE(fold_is_the_bare_xor_of_definition_5_3)
{
    // REGRESSION GUARD ON THE REALIGNMENT.
    //
    // Def. 5.3 states the accumulator as a bare XOR, R_tot[n] = R_tot[n-1] XOR R[n], and
    // that is now exactly what Fold computes. An earlier revision folded the hardened
    // variant H(R_tot[n-1] XOR H(R[n])); this pins the difference, so a future edit that
    // reintroduces the hardening fails the build instead of silently changing every seed.
    for (uint32_t i = 0; i < 16; i++)
    {
        bytes prev = make_val(2000 + i);
        bytes reveal = make_val(i);
        BOOST_CHECK(core_fold(prev, reveal) == ref_fold(prev, reveal));           // the definition
        BOOST_CHECK(core_fold(prev, reveal) != ref_hardened_fold(prev, reveal));  // not the old form
    }

    // Against hand-written bytes, with no helper in the way: the fold is XOR, position by
    // position, and nothing else (no hashing, no permutation, no truncation).
    bytes prev(32), reveal(32), expect(32);
    for (size_t i = 0; i < 32; i++)
    {
        prev[i]   = (unsigned char)(0xA5 ^ i);
        reveal[i] = (unsigned char)(0x3C + i);
        expect[i] = (unsigned char)(prev[i] ^ reveal[i]);
    }
    BOOST_CHECK(core_fold(prev, reveal) == expect);

    // Folding the genesis value with an all-zero reveal must leave it untouched: zero is
    // the identity of XOR, which a hashing fold would not respect.
    bytes g = H32(); RandaoAccumulator::Genesis(&g[0]);
    BOOST_CHECK(core_fold(g, H32()) == g);
}

BOOST_AUTO_TEST_CASE(accumulator_algebra_is_known_and_bounded)
{
    // XOR IS COMMUTATIVE AND SELF-INVERSE. Both are properties of Def. 5.3 itself, not
    // defects: this case states them explicitly so they are read as accepted, and pins the
    // two facts that keep them harmless.
    bytes g = H32(); RandaoAccumulator::Genesis(&g[0]);
    bytes A = make_val(100), B = make_val(200);

    // (1) Order does not reach R_tot: A then B folds to the same value as B then A.
    BOOST_CHECK(core_fold(core_fold(g, A), B) == core_fold(core_fold(g, B), A));

    // (2) The same reveal folded twice cancels itself. Unreachable on a chain — the
    // Phase-3a VRF input is the parent hash, distinct at every height, so no two governed
    // blocks of one branch can carry the same reveal — but true of the algebra.
    BOOST_CHECK(core_fold(core_fold(g, A), A) == g);

    // (3) What keeps the SEED position-dependent regardless: it commits to the tip hash
    // and to the height being elected, so two histories that collide in R_tot still elect
    // from different seeds.
    bytes rtot = core_fold(core_fold(g, A), B);
    BOOST_CHECK(core_seed(rtot, make_val(1), 500) != core_seed(rtot, make_val(2), 500));
    BOOST_CHECK(core_seed(rtot, make_val(1), 500) != core_seed(rtot, make_val(1), 501));
}

BOOST_AUTO_TEST_CASE(fold_of_an_off_size_reveal_is_deterministic)
{
    // A governed block's reveal is always 32 bytes (WPoAVRF::Verify rejects anything else),
    // so this is not a consensus path — but Fold takes a length and must stay total and
    // deterministic for it. A short reveal touches only its own prefix; a long one folds
    // cyclically rather than being truncated, so no input byte is ignored.
    bytes prev = make_val(5);

    bytes short_reveal(8);
    for (size_t i = 0; i < short_reveal.size(); i++) short_reveal[i] = (unsigned char)(i + 1);
    bytes got_short = core_fold(prev, short_reveal);
    for (size_t i = 0; i < 32; i++)
    {
        const unsigned char x = (i < 8) ? short_reveal[i] : 0;
        BOOST_CHECK_EQUAL((int)got_short[i], (int)(unsigned char)(prev[i] ^ x));
    }

    bytes long_reveal(40);
    for (size_t i = 0; i < long_reveal.size(); i++) long_reveal[i] = (unsigned char)(0x11 * (i + 1));
    bytes got_long = core_fold(prev, long_reveal);
    for (size_t i = 0; i < 32; i++)
    {
        unsigned char x = 0;
        for (size_t j = i; j < long_reveal.size(); j += 32) x = (unsigned char)(x ^ long_reveal[j]);
        BOOST_CHECK_EQUAL((int)got_long[i], (int)(unsigned char)(prev[i] ^ x));
    }

    BOOST_CHECK(core_fold(prev, short_reveal) == got_short);   // repeatable
    BOOST_CHECK(core_fold(prev, long_reveal) == got_long);
}

BOOST_AUTO_TEST_CASE(seed_height_is_serialized_big_endian)
{
    // CONSENSUS-CRITICAL ENCODING. DeriveSeed serializes the height byte-by-byte as
    // big-endian rather than memcpy-ing the uint32_t, so two architectures hash the same
    // bytes for the same height. ref_seed shares that construction, so seed_matches_spec
    // alone could not catch a switch to host order — this pins the byte layout against a
    // literal, hand-written buffer that has no endianness at all.
    bytes rtot = make_val(1), hprev = make_val(2);
    const uint32_t height = 0x01020304u;

    unsigned char literal_be[4] = {0x01, 0x02, 0x03, 0x04};
    bytes expect(32);
    CSHA256().Write(&rtot[0], 32).Write(&hprev[0], 32)
             .Write(literal_be, 4).Finalize(&expect[0]);

    BOOST_CHECK(core_seed(rtot, hprev, height) == expect);

    // And the byte-swapped height must give a different seed, i.e. the order is load-bearing.
    BOOST_CHECK(core_seed(rtot, hprev, 0x04030201u) != expect);
}

BOOST_AUTO_TEST_CASE(seed_depends_on_the_lookback_distance)
{
    // The glue picks R_tot[n-k] and feeds it here as the first argument; k itself never
    // reaches the core. What the core must guarantee is that DIFFERENT lookback depths —
    // i.e. different accumulator values along one chain — really do give different seeds,
    // so that the choice of k is not silently inert.
    bytes g = H32(); RandaoAccumulator::Genesis(&g[0]);
    bytes hn = make_val(77);
    const uint32_t height = 101;

    // R_tot at successive depths of one 8-block chain.
    std::vector<bytes> rtot_at_depth;
    bytes rtot = g;
    rtot_at_depth.push_back(rtot);
    for (uint32_t i = 1; i <= 8; i++)
    {
        rtot = core_fold(rtot, make_val(i));
        rtot_at_depth.push_back(rtot);
    }

    std::set<bytes> seeds;
    for (size_t d = 0; d < rtot_at_depth.size(); d++)
    {
        seeds.insert(core_seed(rtot_at_depth[d], hn, height));
    }
    // Same tip hash and same height throughout: any collision would mean the looked-back
    // accumulator had stopped mattering.
    BOOST_CHECK_EQUAL(seeds.size(), rtot_at_depth.size());
}

BOOST_AUTO_TEST_CASE(fold_accepts_a_block_hash_as_the_fallback_contribution)
{
    // The glue folds the BLOCK HASH in place of the reveal when a governed block's data
    // is unavailable (a deterministic fallback, so nodes still agree rather than
    // diverge). That path must be an ordinary fold — same 32-byte contract, no special
    // case — and must not coincide with the fold of the real reveal.
    bytes g = H32(); RandaoAccumulator::Genesis(&g[0]);
    bytes reveal = make_val(900);
    bytes blockhash = make_val(901);

    BOOST_CHECK(core_fold(g, blockhash) == ref_fold(g, blockhash));  // plain Def. 5.3 fold
    BOOST_CHECK(core_fold(g, blockhash) != core_fold(g, reveal));    // distinguishable
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
    // Every input bit reaches the output. Under a bare XOR it reaches exactly one output
    // bit (no avalanche — that is DeriveSeed's job, and seed_is_sensitive_to_every_input
    // checks it there); what matters here is that no input bit is dropped.
    bytes prev = make_val(3), reveal = make_val(4);
    bytes base = core_fold(prev, reveal);

    bytes prev2 = prev; prev2[0] ^= 0x01;      // flip one bit of the accumulator
    BOOST_CHECK(core_fold(prev2, reveal) != base);

    bytes reveal2 = reveal; reveal2[31] ^= 0x80; // flip one bit of the reveal
    BOOST_CHECK(core_fold(prev, reveal2) != base);
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
