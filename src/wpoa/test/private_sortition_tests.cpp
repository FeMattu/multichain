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

BOOST_AUTO_TEST_CASE(normalized_score_is_scale_corrected_and_ordered)
{
    const double W = 600.0;   // a realistic total: 3 validators at 100/200/300

    // In (0,1), and strictly increasing in the raw score at fixed W: this is the
    // exact condition under which the delay preserves the argmin (Prop. 5.11).
    double prev = -1.0;
    for (int i = 1; i <= 200; i++)
    {
        double s = i / (20.0 * W);   // sweep the range the winner actually occupies
        double n = PrivateSortition::NormalizedScore(s, W);
        BOOST_CHECK(n > 0.0 && n < 1.0);
        BOOST_CHECK(n > prev);
        prev = n;
    }

    // The point of the W factor (Def. 5.10): without it the value collapses against
    // 0 for every candidate once weights reach the hundreds, so no candidate could be
    // told apart by its delay. With it, a typical winning score lands mid-band.
    const double typical = 1.0 / W;                       // E[min score] = 1/W
    BOOST_CHECK(PrivateSortition::NormalizedScore(typical, W) > 0.5);
    BOOST_CHECK(PrivateSortition::NormalizedScore(typical, 1.0) < 0.01);  // unscaled: collapsed

    // Degenerate input saturates to 1 (maximally delayed -> the node stands down).
    double nan = std::numeric_limits<double>::quiet_NaN();
    double inf = std::numeric_limits<double>::infinity();
    BOOST_CHECK_EQUAL(PrivateSortition::NormalizedScore(-1.0, W), 1.0);
    BOOST_CHECK_EQUAL(PrivateSortition::NormalizedScore(1.0, 0.0), 1.0);
    BOOST_CHECK_EQUAL(PrivateSortition::NormalizedScore(nan, W), 1.0);
    BOOST_CHECK_EQUAL(PrivateSortition::NormalizedScore(inf, W), 1.0);
}

BOOST_AUTO_TEST_CASE(mining_delay_is_a_band_around_the_target)
{
    const double W = 600.0, T = 15.0, delta = 0.5, lambda = 0.0, phi = 0.0;
    const double dmax = delta * T;

    // Every delay lies inside the symmetric band (T - dmax, T + dmax) — the property
    // the admissibility bound rests on (Prop. 5.13).
    for (int i = 1; i <= 400; i++)
    {
        double s = i / (20.0 * W);
        double d = PrivateSortition::MiningDelay(s, W, T, delta, lambda, phi);
        BOOST_CHECK(d >= T - dmax);
        BOOST_CHECK(d <= T + dmax);
    }

    // The band edges are attained in the limit: score -> 0 is the most favoured
    // candidate (earliest), a large score the least favoured (latest).
    BOOST_CHECK_CLOSE(PrivateSortition::MiningDelay(1e-12, W, T, delta, lambda, phi),
                      T - dmax, 1e-3);
    BOOST_CHECK_CLOSE(PrivateSortition::MiningDelay(10.0, W, T, delta, lambda, phi),
                      T + dmax, 1e-9);

    // Strictly increasing in the score, which is what makes argmin(score) propose
    // first and, dually, what the validator's time bar relies on.
    double prev = -1.0;
    for (int i = 1; i <= 400; i++)
    {
        double d = PrivateSortition::MiningDelay(i / (20.0 * W), W, T, delta, lambda, phi);
        BOOST_CHECK(d > prev);
        prev = d;
    }

    // delta -> 0 collapses the band onto the target (no separation, maximum forks);
    // the mid-band score sits exactly on the target for any delta.
    BOOST_CHECK_CLOSE(PrivateSortition::MiningDelay(1.0 / W, W, T, 1e-9, lambda, phi), T, 1e-4);
}

BOOST_AUTO_TEST_CASE(mining_delay_feedback_shifts_the_whole_band)
{
    const double W = 600.0, T = 15.0, delta = 0.5, lambda = 0.5;

    // Phi is common to every candidate, so it shifts all timers by the same amount
    // and cannot reorder them (Prop. 5.11). Verified as an exact identity.
    for (int i = 1; i <= 50; i++)
    {
        double s = i / (5.0 * W);
        double d0 = PrivateSortition::MiningDelay(s, W, T, delta, lambda,  0.0);
        double dp = PrivateSortition::MiningDelay(s, W, T, delta, lambda,  2.0);
        double dm = PrivateSortition::MiningDelay(s, W, T, delta, lambda, -2.0);
        BOOST_CHECK_CLOSE(dp - d0,  lambda * 2.0, 1e-9);
        BOOST_CHECK_CLOSE(d0 - dm,  lambda * 2.0, 1e-9);
    }

    // lambda = 0 disables the correction entirely (Cor. 5.14): Phi becomes inert.
    BOOST_CHECK_EQUAL(PrivateSortition::MiningDelay(1.0 / W, W, T, delta, 0.0, 7.0),
                      PrivateSortition::MiningDelay(1.0 / W, W, T, delta, 0.0, 0.0));
}

BOOST_AUTO_TEST_CASE(max_feedback_is_the_admissibility_ceiling)
{
    const double T = 15.0;

    // Cor. 5.15: M* = T(1-delta)/lambda, the largest |Phi| that still leaves D >= 0.
    BOOST_CHECK_CLOSE(PrivateSortition::MaxFeedback(T, 0.5, 0.5), T * 0.5 / 0.5, 1e-9);
    BOOST_CHECK_CLOSE(PrivateSortition::MaxFeedback(T, 0.8, 1.0), T * 0.2 / 1.0, 1e-9);

    // At exactly M* the most favoured candidate lands on 0 and never below it.
    for (double delta = 0.1; delta < 0.95; delta += 0.1)
    {
        for (double lambda = 0.1; lambda <= 1.0; lambda += 0.3)
        {
            double M = PrivateSortition::MaxFeedback(T, delta, lambda);
            double d = PrivateSortition::MiningDelay(1e-15, 600.0, T, delta, lambda, -M);
            BOOST_CHECK(d >= 0.0);
            BOOST_CHECK_SMALL(d, 1e-6);
        }
    }

    // lambda = 0 makes the bound vacuous (the lambda*Phi term vanishes anyway).
    BOOST_CHECK(std::isinf(PrivateSortition::MaxFeedback(T, 0.5, 0.0)));
}

BOOST_AUTO_TEST_CASE(mining_delay_never_negative_or_nan)
{
    const double W = 600.0, T = 15.0;
    double nan = std::numeric_limits<double>::quiet_NaN();
    double inf = std::numeric_limits<double>::infinity();

    // Degenerate parameters must never yield a negative or NaN delay (which would
    // make the time bar meaningless): they saturate to the maximum ("stand down").
    BOOST_CHECK_EQUAL(PrivateSortition::MiningDelay(1.0, W, 0.0, 0.5, 0.0, 0.0),
                      PrivateSortition::MaxDelaySeconds());
    BOOST_CHECK_EQUAL(PrivateSortition::MiningDelay(1.0, W, T, 1.0, 0.0, 0.0),
                      PrivateSortition::MaxDelaySeconds());   // delta must be < 1
    BOOST_CHECK_EQUAL(PrivateSortition::MiningDelay(1.0, W, T, 0.5, -1.0, 0.0),
                      PrivateSortition::MaxDelaySeconds());
    BOOST_CHECK_EQUAL(PrivateSortition::MiningDelay(1.0, W, T, 0.5, 0.5, nan),
                      PrivateSortition::MaxDelaySeconds());
    BOOST_CHECK_EQUAL(PrivateSortition::MiningDelay(1.0, W, nan, 0.5, 0.5, 0.0),
                      PrivateSortition::MaxDelaySeconds());

    // A degenerate SCORE saturates the normalized score to 1, i.e. the far edge of
    // the band — still a well-formed, non-negative delay.
    BOOST_CHECK_CLOSE(PrivateSortition::MiningDelay(nan, W, T, 0.5, 0.0, 0.0), T + 0.5 * T, 1e-9);
    BOOST_CHECK_CLOSE(PrivateSortition::MiningDelay(inf, W, T, 0.5, 0.0, 0.0), T + 0.5 * T, 1e-9);

    // An over-large feedback (caller failed to clip) is absorbed by the floor rather
    // than scheduling into the past.
    BOOST_CHECK(PrivateSortition::MiningDelay(1e-15, W, T, 0.5, 1.0, -1e6) >= 0.0);
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

// ---- the winner's delay: uniform over the band, mean on target ------------

// Prop. 5.10 with REAL VRF keys: whatever the weight distribution, the WINNER's
// normalized score is exactly U(0,1) — and therefore its delay is uniform over the
// band and the mean realized block time lands on target-block-time. This is the
// property the W factor of Def. 5.10 buys, and the reason the band form can replace
// an open-ended ramp; without W the value collapses against 0 and every candidate
// would be crammed against the early edge.
static void run_winner_uniformity(const std::vector<uint32_t>& weights,
                                  uint32_t trials, const char* label)
{
    const size_t m = weights.size();
    std::vector<std::vector<unsigned char> > sks(m);
    for (size_t i = 0; i < m; i++) sks[i] = make_secret_key((uint32_t)(4000 + i));

    double W = 0.0;
    for (size_t i = 0; i < m; i++) W += (double)weights[i];

    const double T = 15.0, delta = 0.5;
    const uint32_t height = 900;

    // 10 equal-width buckets over (0,1): a uniform winner-score fills them evenly.
    std::vector<uint64_t> hist(10, 0);
    double sum_norm = 0.0, sum_delay = 0.0;
    double dmin = 1e18, dmax = -1e18;

    for (uint32_t t = 0; t < trials; t++)
    {
        std::vector<unsigned char> seed = make_seed(90000 + t);
        double best_score = std::numeric_limits<double>::infinity();
        for (size_t i = 0; i < m; i++)
        {
            unsigned char y[32];
            vrf_output(sks[i], seed, height, y);
            double sc = PrivateSortition::ScoreFromVRFOutput(y, weights[i]);
            if (sc < best_score) best_score = sc;
        }
        double norm  = PrivateSortition::NormalizedScore(best_score, W);
        double delay = PrivateSortition::MiningDelay(best_score, W, T, delta, 0.0, 0.0);

        int b = (int)(norm * 10.0); if (b > 9) b = 9; if (b < 0) b = 0;
        hist[b]++;
        sum_norm  += norm;
        sum_delay += delay;
        if (delay < dmin) dmin = delay;
        if (delay > dmax) dmax = delay;
    }

    double mean_norm  = sum_norm  / trials;
    double mean_delay = sum_delay / trials;

    std::printf("\n  Winner's normalized score, %s (%zu validators, W=%.0f, %u trials):\n",
                label, m, W, trials);
    std::printf("    decile occupancy (expect ~%.3f each):", 1.0 / 10.0);
    for (size_t b = 0; b < hist.size(); b++)
        std::printf(" %.3f", (double)hist[b] / trials);
    std::printf("\n    mean score_norm = %.4f (expect 0.5000)\n", mean_norm);
    std::printf("    mean delay      = %.3fs (target T=%.1fs)   band [%.3f, %.3f] within [%.1f, %.1f]\n",
                mean_delay, T, dmin, dmax, T - delta * T, T + delta * T);

    // Uniform winner score (Prop. 5.10) — every decile within a sampling margin.
    BOOST_CHECK_CLOSE(mean_norm, 0.5, 4.0);
    for (size_t b = 0; b < hist.size(); b++)
    {
        double share = (double)hist[b] / trials;
        BOOST_CHECK_MESSAGE(share > 0.06 && share < 0.14,
                            "decile " << b << " occupancy " << share
                            << " is not consistent with a uniform winner score");
    }

    // Hence the mean realized delay sits on target-block-time, and the whole band is
    // respected — the two goals §5.10 states for the delay.
    BOOST_CHECK_CLOSE(mean_delay, T, 4.0);
    BOOST_CHECK(dmin >= T - delta * T);
    BOOST_CHECK(dmax <= T + delta * T);
}

BOOST_AUTO_TEST_CASE(winner_delay_uniform_equal_weights)
{
    std::vector<uint32_t> w;
    w.push_back(100); w.push_back(100); w.push_back(100);
    run_winner_uniformity(w, 8000, "equal weights 100x3");
}

BOOST_AUTO_TEST_CASE(winner_delay_uniform_skewed_weights)
{
    // The invariance that matters: a dominant holder does not shift the winner's
    // score distribution, so the band stays fully used and the cadence stays on target.
    std::vector<uint32_t> w;
    w.push_back(1000); w.push_back(10); w.push_back(10); w.push_back(10);
    run_winner_uniformity(w, 8000, "whale 1000 + 3x10");
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
