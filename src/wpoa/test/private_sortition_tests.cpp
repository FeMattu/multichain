// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA Phase 4 — unit tests for the pure private-sortition core
// (src/wpoa/private_sortition.h, class PrivateSortition) plus its end-to-end
// coupling with the real VRF (src/wpoa/vrf_wrapper.h).
//
// These tests are self-contained: they link only the SHA256 / HMAC-SHA256 crypto
// primitives, the VRF wrapper (secp256k1) and Boost.Test (header-only), NOT the
// wallet / node runtime. Build & run with
// src/wpoa/test/run_unit_tests.sh sortition (needs a one-time secp256k1 build).
//
// They validate, node-free:
//   * the consensus-critical VRF-input encoding  seed ‖ "PROPOSER" ‖ height_be;
//   * that the private score reuses the SAME transform as the Phase 2 public
//     selector (single source of truth) — bit-identical given the same entropy;
//   * the score-timing / time-bar delay map: monotone, linear, clamped, robust;
//   * PROBABILITY PRESERVATION (thesis §7.4) end-to-end with REAL per-validator
//     VRF keys — argmin over private VRF scores elects i with Pr = w_i / Σ w_j —
//     the property that makes the private redesign a security fix, not a change
//     in consensus semantics;
//   * that a validator's score is unknowable without its secret key (the privacy
//     the whole phase rests on): the same input under different keys yields
//     different, independent scores.

#define BOOST_TEST_MODULE wPoAPrivateSortitionTests
#include <boost/test/included/unit_test.hpp>

#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>
#include <map>
#include <string>
#include <vector>

#include "wpoa/private_sortition.h"
#include "wpoa/wpoa_selector.h"
#include "wpoa/vrf_wrapper.h"
#include "crypto/sha256.h"

// ---- helpers -------------------------------------------------------------

// A distinct 32-byte beacon seed per trial index (big-endian index in the low
// bytes), standing in for the sequence of RANDAO beacon seeds a real chain feeds
// the sortition.
static std::vector<unsigned char> make_seed(uint32_t i)
{
    std::vector<unsigned char> seed(32, 0);
    seed[28] = (unsigned char)((i >> 24) & 0xff);
    seed[29] = (unsigned char)((i >> 16) & 0xff);
    seed[30] = (unsigned char)((i >> 8) & 0xff);
    seed[31] = (unsigned char)(i & 0xff);
    return seed;
}

// Deterministically derive a VALID secp256k1 secret key for validator `idx`:
// sk = SHA256("wpoa-phase4-sk" ‖ idx ‖ counter), bumping the counter on the
// astronomically rare event that the digest is not a valid scalar (WPoAVRF::Prove
// rejects it). Keeps the test reproducible without any RNG.
static std::vector<unsigned char> make_secret_key(uint32_t idx)
{
    const char* tag = "wpoa-phase4-sk";
    for (uint32_t counter = 0; counter < 256; counter++)
    {
        unsigned char sk[32];
        CSHA256 h;
        h.Write((const unsigned char*)tag, std::strlen(tag));
        unsigned char ib[4] = {
            (unsigned char)((idx >> 24) & 0xff), (unsigned char)((idx >> 16) & 0xff),
            (unsigned char)((idx >> 8) & 0xff),  (unsigned char)(idx & 0xff) };
        unsigned char cb = (unsigned char)counter;
        h.Write(ib, 4);
        h.Write(&cb, 1);
        h.Finalize(sk);

        // Probe validity by attempting a Prove over a trivial input.
        unsigned char out[WPoAVRF::OUTPUT_SIZE], proof[WPoAVRF::PROOF_SIZE];
        unsigned char probe[1] = { 0x00 };
        if (WPoAVRF::Prove(sk, probe, 1, out, proof))
        {
            return std::vector<unsigned char>(sk, sk + 32);
        }
    }
    BOOST_FAIL("could not derive a valid secp256k1 secret key");
    return std::vector<unsigned char>();
}

// The real per-validator VRF output over the sortition input for a given seed.
static void vrf_output(const std::vector<unsigned char>& sk,
                       const std::vector<unsigned char>& seed, uint32_t height,
                       unsigned char out[WPoAVRF::OUTPUT_SIZE])
{
    std::vector<unsigned char> input;
    PrivateSortition::VRFInput(&seed[0], height, input);
    unsigned char proof[WPoAVRF::PROOF_SIZE];
    BOOST_REQUIRE(WPoAVRF::Prove(&sk[0], input.data(), input.size(), out, proof));
}

// ---- VRF-input encoding (consensus-critical wire contract) ---------------

BOOST_AUTO_TEST_CASE(vrf_input_encoding)
{
    std::vector<unsigned char> seed = make_seed(0xA1B2C3D4);
    std::vector<unsigned char> in;
    PrivateSortition::VRFInput(&seed[0], 0x01020304u, in);

    // Layout: 32-byte seed ‖ "PROPOSER" (8) ‖ height big-endian (4) = 44 bytes.
    BOOST_REQUIRE_EQUAL(in.size(), (size_t)44);
    BOOST_CHECK(std::memcmp(&in[0], &seed[0], 32) == 0);
    BOOST_CHECK(std::memcmp(&in[32], "PROPOSER", 8) == 0);
    BOOST_CHECK_EQUAL(in[40], 0x01);
    BOOST_CHECK_EQUAL(in[41], 0x02);
    BOOST_CHECK_EQUAL(in[42], 0x03);
    BOOST_CHECK_EQUAL(in[43], 0x04);

    // Deterministic, and sensitive to BOTH the seed and the height.
    std::vector<unsigned char> in2;
    PrivateSortition::VRFInput(&seed[0], 0x01020304u, in2);
    BOOST_CHECK(in == in2);

    std::vector<unsigned char> in_h;
    PrivateSortition::VRFInput(&seed[0], 0x01020305u, in_h);
    BOOST_CHECK(in != in_h);

    std::vector<unsigned char> seed2 = make_seed(0xA1B2C3D5);
    std::vector<unsigned char> in_s;
    PrivateSortition::VRFInput(&seed2[0], 0x01020304u, in_s);
    BOOST_CHECK(in != in_s);
}

// ---- score reuses the single source of truth -----------------------------

BOOST_AUTO_TEST_CASE(score_matches_shared_transform)
{
    // ScoreFromVRFOutput must be byte-identical to running the Phase-2 transform
    // on the folded output — same math, only the entropy source differs. This is
    // what lets the thesis prove the distribution is unchanged.
    const DumpingFunction modes[3] = { DUMP_NONE, DUMP_SQRT, DUMP_LOG };
    for (uint32_t t = 0; t < 64; t++)
    {
        unsigned char y[32];
        CSHA256 h;
        unsigned char tb[4] = { (unsigned char)(t >> 24), (unsigned char)(t >> 16),
                                (unsigned char)(t >> 8), (unsigned char)t };
        h.Write((const unsigned char*)"y", 1);
        h.Write(tb, 4);
        h.Finalize(y);

        uint32_t weights[4] = { 1u, 7u, 100u, 4000u };
        for (int wi = 0; wi < 4; wi++)
        {
            for (int mi = 0; mi < 3; mi++)
            {
                double a = PrivateSortition::ScoreFromVRFOutput(y, weights[wi], modes[mi]);
                double b = WPoASelector::ScoreFromEntropy64(
                               WPoASelector::FoldTop64(y), weights[wi], modes[mi]);
                BOOST_CHECK(a == b);
            }
        }
    }

    // Weight 0 => +inf, so a zero-weight node can never be the argmin.
    unsigned char y0[32];
    std::memset(y0, 0x5a, sizeof(y0));
    BOOST_CHECK(std::isinf(PrivateSortition::ScoreFromVRFOutput(y0, 0)));
}

// ---- delay map (score-timing + validator time bar) -----------------------

BOOST_AUTO_TEST_CASE(mining_delay_monotone_linear_clamped)
{
    const double W = 10.0, scale = 2.0;

    // A zero score maps to zero delay (the argmin can, in the limit, mine at once).
    BOOST_CHECK_EQUAL(PrivateSortition::MiningDelay(0.0, W, scale), 0.0);

    // Linear in score, in W and in scale (below the clamp).
    BOOST_CHECK_CLOSE(PrivateSortition::MiningDelay(0.5, W, scale), 0.5 * W * scale, 1e-9);
    BOOST_CHECK_CLOSE(PrivateSortition::MiningDelay(0.3, 20.0, 1.5), 0.3 * 20.0 * 1.5, 1e-9);

    // Strictly increasing in score (this is what makes argmin(score) propose first).
    double prev = -1.0;
    for (int i = 0; i <= 50; i++)
    {
        double s = 0.01 * i;
        double d = PrivateSortition::MiningDelay(s, W, scale);
        BOOST_CHECK(d > prev);
        prev = d;
    }

    // Clamped to MaxDelaySeconds for an enormous score (never overflows nTime).
    double huge = PrivateSortition::MiningDelay(1e18, W, scale);
    BOOST_CHECK_EQUAL(huge, PrivateSortition::MaxDelaySeconds());

    // Degenerate inputs must never yield a negative/NaN delay (which would make
    // the time bar meaningless): they saturate to the maximum ("stand down").
    double nan = std::numeric_limits<double>::quiet_NaN();
    double inf = std::numeric_limits<double>::infinity();
    BOOST_CHECK_EQUAL(PrivateSortition::MiningDelay(-1.0, W, scale), PrivateSortition::MaxDelaySeconds());
    BOOST_CHECK_EQUAL(PrivateSortition::MiningDelay(1.0, 0.0, scale), PrivateSortition::MaxDelaySeconds());
    BOOST_CHECK_EQUAL(PrivateSortition::MiningDelay(nan, W, scale), PrivateSortition::MaxDelaySeconds());
    BOOST_CHECK_EQUAL(PrivateSortition::MiningDelay(inf, W, scale), PrivateSortition::MaxDelaySeconds());
    BOOST_CHECK_EQUAL(PrivateSortition::MiningDelay(1.0, inf, scale), PrivateSortition::MaxDelaySeconds());

    // scale = 0 (all delays collapse to 0) is a legal, if degenerate, setting.
    BOOST_CHECK_EQUAL(PrivateSortition::MiningDelay(1.0, W, 0.0), 0.0);
}

// ---- privacy: score is unknowable without the secret key -----------------

BOOST_AUTO_TEST_CASE(score_depends_on_secret_key)
{
    // The security property Phase 4 rests on: a validator's score is derived under
    // its OWN secret key, so a peer holding a different key cannot reproduce it.
    // Same public input, different keys -> different outputs -> different scores.
    std::vector<unsigned char> seed = make_seed(42);
    std::vector<unsigned char> skA = make_secret_key(1);
    std::vector<unsigned char> skB = make_secret_key(2);

    unsigned char yA[32], yB[32];
    vrf_output(skA, seed, 100, yA);
    vrf_output(skB, seed, 100, yB);
    BOOST_CHECK(std::memcmp(yA, yB, 32) != 0);

    double sA = PrivateSortition::ScoreFromVRFOutput(yA, 100);
    double sB = PrivateSortition::ScoreFromVRFOutput(yB, 100);
    BOOST_CHECK(sA != sB);
}

// ---- probability preservation (thesis §7.4), real VRF keys ---------------

// m validators, each with a real secp256k1 key and a weight; over `trials` beacon
// seeds, the winner is argmin_i(score_i) with score from the validator's real VRF
// output. Tally winners and assert each empirical share is within `tol` of its
// weight share; print the observed-vs-expected table + chi-square as a thesis
// artifact. Trial counts are modest relative to the Phase-2 pure-HMAC test because
// each trial now runs m real VRF evaluations.
static void run_vrf_distribution(const std::vector<uint32_t>& weights,
                                 uint32_t trials, double tol)
{
    const size_t m = weights.size();
    std::vector<std::vector<unsigned char> > sks(m);
    for (size_t i = 0; i < m; i++)
    {
        sks[i] = make_secret_key((uint32_t)(1000 + i));
    }

    uint64_t total_weight = 0;
    for (size_t i = 0; i < m; i++) total_weight += weights[i];

    std::vector<uint64_t> wins(m, 0);
    const uint32_t height = 500;
    for (uint32_t t = 0; t < trials; t++)
    {
        std::vector<unsigned char> seed = make_seed(t);
        size_t best = 0;
        double best_score = std::numeric_limits<double>::infinity();
        for (size_t i = 0; i < m; i++)
        {
            unsigned char y[32];
            vrf_output(sks[i], seed, height, y);
            double s = PrivateSortition::ScoreFromVRFOutput(y, weights[i]);
            // Total order with a deterministic index tie-break (bit-exact ties are
            // cryptographically negligible; the tie-break just keeps the test total).
            if (s < best_score || (s == best_score && i < best))
            {
                best_score = s;
                best = i;
            }
        }
        wins[best] += 1;
    }

    std::printf("\n  Private-sortition distribution over %u trials (%zu validators, total weight %llu):\n",
                trials, m, (unsigned long long)total_weight);
    std::printf("  %-10s %8s %10s %10s %8s\n", "validator", "weight", "expected", "observed", "err%%");

    double chi2 = 0.0;
    for (size_t i = 0; i < m; i++)
    {
        double p_expected = (double)weights[i] / (double)total_weight;
        double expected_count = p_expected * trials;
        double observed_count = (double)wins[i];
        double p_observed = observed_count / (double)trials;
        double err = (p_observed - p_expected) / p_expected;

        std::printf("  v%-9zu %8u %10.4f %10.4f %+7.2f\n",
                    i, weights[i], p_expected, p_observed, err * 100.0);

        double diff = observed_count - expected_count;
        chi2 += (diff * diff) / expected_count;

        BOOST_CHECK_MESSAGE(std::fabs(err) < tol,
                            "validator " << i << " share " << p_observed
                            << " deviates from expected " << p_expected
                            << " by " << (err * 100.0) << "% (> " << (tol * 100.0) << "%)");
    }
    std::printf("  chi-square = %.3f (df = %zu)\n", chi2, m - 1);
}

BOOST_AUTO_TEST_CASE(distribution_equal_weights)
{
    std::vector<uint32_t> w;
    w.push_back(100); w.push_back(100); w.push_back(100); w.push_back(100);
    run_vrf_distribution(w, 20000, 0.05);
}

BOOST_AUTO_TEST_CASE(distribution_skewed_weights)
{
    // 1 : 2 : 3 : 4  ->  shares 0.1, 0.2, 0.3, 0.4
    std::vector<uint32_t> w;
    w.push_back(100); w.push_back(200); w.push_back(300); w.push_back(400);
    run_vrf_distribution(w, 20000, 0.06);
}

BOOST_AUTO_TEST_CASE(distribution_monotonic_in_weight)
{
    // A strictly heavier validator wins strictly more often under the private
    // argmin, exactly as under the public selector.
    std::vector<unsigned char> skLight = make_secret_key(7001);
    std::vector<unsigned char> skHeavy = make_secret_key(7002);
    const uint32_t wLight = 50, wHeavy = 500;

    uint64_t heavy = 0, light = 0;
    const uint32_t trials = 20000;
    for (uint32_t t = 0; t < trials; t++)
    {
        std::vector<unsigned char> seed = make_seed(t * 3 + 1);
        unsigned char yL[32], yH[32];
        vrf_output(skLight, seed, 500, yL);
        vrf_output(skHeavy, seed, 500, yH);
        double sL = PrivateSortition::ScoreFromVRFOutput(yL, wLight);
        double sH = PrivateSortition::ScoreFromVRFOutput(yH, wHeavy);
        if (sH < sL) heavy++; else light++;
    }
    BOOST_CHECK_MESSAGE(heavy > light, "heavy=" << heavy << " light=" << light);
    double ratio = (double)heavy / (double)light;
    BOOST_CHECK_MESSAGE(ratio > 8.0 && ratio < 12.0, "win ratio " << ratio << " (expected ~10)");
}
