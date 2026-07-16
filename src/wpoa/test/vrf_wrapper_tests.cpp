// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA Phase 3a — unit tests for the pure VRF wrapper
// (src/wpoa/vrf_wrapper.h, class WPoAVRF).
//
// These tests are self-contained: they link only secp256k1 + SHA256 and
// Boost.Test (header-only), NOT the wallet / node runtime. Build & run with
// src/wpoa/test/run_unit_tests.sh vrf.
//
// They validate, node-free, every property the beacon relies on:
//   * correctness  — an honestly produced (output, proof) verifies;
//   * determinism  — the same (sk, input) always yields the same reveal;
//   * uniqueness / soundness — tampering with the reveal, the proof, the key or
//     the input makes verification fail (grinding is infeasible);
//   * pseudorandomness sanity — distinct inputs give distinct, well-spread
//     outputs;
//   * key-format tolerance — both compressed and uncompressed public keys verify.

#define BOOST_TEST_MODULE wPoAVRFTests
#include <boost/test/included/unit_test.hpp>

#include <cstring>
#include <set>
#include <string>
#include <vector>

#include <secp256k1.h>

#include "wpoa/vrf_wrapper.h"

// ---- helpers -------------------------------------------------------------

static secp256k1_context* g_ctx = NULL;

// A deterministic, valid secp256k1 secret key derived from a small index. Byte
// layout keeps every value well inside [1, n-1].
static std::vector<unsigned char> make_seckey(unsigned char idx)
{
    std::vector<unsigned char> sk(32, 0);
    sk[31] = 0x01;   // ensure non-zero / valid even when idx == 0
    sk[0]  = idx;
    sk[15] = (unsigned char)(idx * 7 + 1);
    BOOST_REQUIRE(secp256k1_ec_seckey_verify(g_ctx, sk.data()));
    return sk;
}

// Compressed (33-byte) public key for a secret key.
static std::vector<unsigned char> pubkey_of(const std::vector<unsigned char>& sk,
                                            bool compressed = true)
{
    secp256k1_pubkey pk;
    BOOST_REQUIRE(secp256k1_ec_pubkey_create(g_ctx, &pk, sk.data()));
    std::vector<unsigned char> out(compressed ? 33 : 65);
    size_t len = out.size();
    BOOST_REQUIRE(secp256k1_ec_pubkey_serialize(
        g_ctx, out.data(), &len, &pk,
        compressed ? SECP256K1_EC_COMPRESSED : SECP256K1_EC_UNCOMPRESSED));
    out.resize(len);
    return out;
}

static std::vector<unsigned char> make_input(const std::string& s)
{
    return std::vector<unsigned char>(s.begin(), s.end());
}

struct VRFFixture
{
    VRFFixture()
    {
        if (g_ctx == NULL)
        {
            g_ctx = secp256k1_context_create(SECP256K1_CONTEXT_SIGN |
                                             SECP256K1_CONTEXT_VERIFY);
        }
    }
};

BOOST_GLOBAL_FIXTURE(VRFFixture);

// ---- correctness ---------------------------------------------------------

BOOST_AUTO_TEST_CASE(prove_then_verify_roundtrips)
{
    std::vector<unsigned char> sk = make_seckey(3);
    std::vector<unsigned char> pk = pubkey_of(sk);
    std::vector<unsigned char> input = make_input("prev-block-hash-abc");

    unsigned char output[WPoAVRF::OUTPUT_SIZE];
    unsigned char proof[WPoAVRF::PROOF_SIZE];
    BOOST_REQUIRE(WPoAVRF::Prove(sk.data(), input.data(), input.size(), output, proof));

    BOOST_CHECK(WPoAVRF::Verify(pk.data(), pk.size(), input.data(), input.size(),
                                output, proof));
}

BOOST_AUTO_TEST_CASE(uncompressed_pubkey_also_verifies)
{
    std::vector<unsigned char> sk = make_seckey(9);
    std::vector<unsigned char> pk_u = pubkey_of(sk, /*compressed=*/false);
    BOOST_REQUIRE_EQUAL(pk_u.size(), 65u);
    std::vector<unsigned char> input = make_input("round-42");

    unsigned char output[WPoAVRF::OUTPUT_SIZE];
    unsigned char proof[WPoAVRF::PROOF_SIZE];
    BOOST_REQUIRE(WPoAVRF::Prove(sk.data(), input.data(), input.size(), output, proof));

    BOOST_CHECK(WPoAVRF::Verify(pk_u.data(), pk_u.size(), input.data(), input.size(),
                                output, proof));
}

// ---- determinism ---------------------------------------------------------

BOOST_AUTO_TEST_CASE(prove_is_deterministic)
{
    std::vector<unsigned char> sk = make_seckey(5);
    std::vector<unsigned char> input = make_input("same-input");

    unsigned char out1[WPoAVRF::OUTPUT_SIZE], out2[WPoAVRF::OUTPUT_SIZE];
    unsigned char pr1[WPoAVRF::PROOF_SIZE],  pr2[WPoAVRF::PROOF_SIZE];
    BOOST_REQUIRE(WPoAVRF::Prove(sk.data(), input.data(), input.size(), out1, pr1));
    BOOST_REQUIRE(WPoAVRF::Prove(sk.data(), input.data(), input.size(), out2, pr2));

    BOOST_CHECK_EQUAL(memcmp(out1, out2, WPoAVRF::OUTPUT_SIZE), 0);
    BOOST_CHECK_EQUAL(memcmp(pr1, pr2, WPoAVRF::PROOF_SIZE), 0);
}

// ---- soundness / uniqueness (tamper rejection) ---------------------------

BOOST_AUTO_TEST_CASE(wrong_pubkey_is_rejected)
{
    std::vector<unsigned char> sk = make_seckey(2);
    std::vector<unsigned char> other_pk = pubkey_of(make_seckey(7));
    std::vector<unsigned char> input = make_input("height-100");

    unsigned char output[WPoAVRF::OUTPUT_SIZE];
    unsigned char proof[WPoAVRF::PROOF_SIZE];
    BOOST_REQUIRE(WPoAVRF::Prove(sk.data(), input.data(), input.size(), output, proof));

    BOOST_CHECK(!WPoAVRF::Verify(other_pk.data(), other_pk.size(),
                                 input.data(), input.size(), output, proof));
}

BOOST_AUTO_TEST_CASE(wrong_input_is_rejected)
{
    std::vector<unsigned char> sk = make_seckey(4);
    std::vector<unsigned char> pk = pubkey_of(sk);
    std::vector<unsigned char> input = make_input("input-A");
    std::vector<unsigned char> other = make_input("input-B");

    unsigned char output[WPoAVRF::OUTPUT_SIZE];
    unsigned char proof[WPoAVRF::PROOF_SIZE];
    BOOST_REQUIRE(WPoAVRF::Prove(sk.data(), input.data(), input.size(), output, proof));

    BOOST_CHECK(!WPoAVRF::Verify(pk.data(), pk.size(), other.data(), other.size(),
                                 output, proof));
}

BOOST_AUTO_TEST_CASE(tampered_output_is_rejected)
{
    std::vector<unsigned char> sk = make_seckey(6);
    std::vector<unsigned char> pk = pubkey_of(sk);
    std::vector<unsigned char> input = make_input("seed-xyz");

    unsigned char output[WPoAVRF::OUTPUT_SIZE];
    unsigned char proof[WPoAVRF::PROOF_SIZE];
    BOOST_REQUIRE(WPoAVRF::Prove(sk.data(), input.data(), input.size(), output, proof));

    output[0] ^= 0x01; // flip one bit of the reveal
    BOOST_CHECK(!WPoAVRF::Verify(pk.data(), pk.size(), input.data(), input.size(),
                                 output, proof));
}

BOOST_AUTO_TEST_CASE(tampered_proof_each_field_is_rejected)
{
    std::vector<unsigned char> sk = make_seckey(8);
    std::vector<unsigned char> pk = pubkey_of(sk);
    std::vector<unsigned char> input = make_input("seed-tamper");

    unsigned char output[WPoAVRF::OUTPUT_SIZE];
    unsigned char proof_orig[WPoAVRF::PROOF_SIZE];
    BOOST_REQUIRE(WPoAVRF::Prove(sk.data(), input.data(), input.size(), output, proof_orig));

    // Flip a bit in Gamma (offset 0), in c (offset 33), and in s (offset 65).
    const size_t offsets[3] = { 0, 33, 65 };
    for (int i = 0; i < 3; i++)
    {
        unsigned char proof[WPoAVRF::PROOF_SIZE];
        memcpy(proof, proof_orig, WPoAVRF::PROOF_SIZE);
        proof[offsets[i]] ^= 0x01;
        BOOST_CHECK_MESSAGE(
            !WPoAVRF::Verify(pk.data(), pk.size(), input.data(), input.size(), output, proof),
            "tampering at proof offset " << offsets[i] << " should be rejected");
    }
}

// A valid proof from key A must not verify a reveal claimed for key B even if
// the attacker recomputes a self-consistent output — this is the grinding /
// impersonation guard.
BOOST_AUTO_TEST_CASE(cross_key_proof_is_rejected)
{
    std::vector<unsigned char> skA = make_seckey(11);
    std::vector<unsigned char> skB = make_seckey(12);
    std::vector<unsigned char> pkB = pubkey_of(skB);
    std::vector<unsigned char> input = make_input("contested-round");

    unsigned char outA[WPoAVRF::OUTPUT_SIZE];
    unsigned char proofA[WPoAVRF::PROOF_SIZE];
    BOOST_REQUIRE(WPoAVRF::Prove(skA.data(), input.data(), input.size(), outA, proofA));

    // A's reveal/proof presented as if it were B's — must fail.
    BOOST_CHECK(!WPoAVRF::Verify(pkB.data(), pkB.size(), input.data(), input.size(),
                                 outA, proofA));
}

// ---- pseudorandomness sanity --------------------------------------------

BOOST_AUTO_TEST_CASE(distinct_inputs_give_distinct_outputs)
{
    std::vector<unsigned char> sk = make_seckey(1);
    std::set<std::string> outputs;

    const int N = 500;
    for (int i = 0; i < N; i++)
    {
        std::vector<unsigned char> input(4);
        input[0] = (unsigned char)(i & 0xff);
        input[1] = (unsigned char)((i >> 8) & 0xff);
        input[2] = 0xAB;
        input[3] = 0xCD;

        unsigned char output[WPoAVRF::OUTPUT_SIZE];
        unsigned char proof[WPoAVRF::PROOF_SIZE];
        BOOST_REQUIRE(WPoAVRF::Prove(sk.data(), input.data(), input.size(), output, proof));
        outputs.insert(std::string((const char*)output, WPoAVRF::OUTPUT_SIZE));
    }
    // No collisions expected among 500 distinct inputs.
    BOOST_CHECK_EQUAL((int)outputs.size(), N);
}

// ---- convenience vector API ---------------------------------------------

BOOST_AUTO_TEST_CASE(vector_api_roundtrips)
{
    std::vector<unsigned char> sk = make_seckey(13);
    std::vector<unsigned char> pk = pubkey_of(sk);
    std::vector<unsigned char> input = make_input("vector-api");

    std::vector<unsigned char> output, proof;
    BOOST_REQUIRE(WPoAVRF::Prove(sk, input, output, proof));
    BOOST_CHECK_EQUAL(output.size(), WPoAVRF::OUTPUT_SIZE);
    BOOST_CHECK_EQUAL(proof.size(), WPoAVRF::PROOF_SIZE);
    BOOST_CHECK(WPoAVRF::Verify(pk, input, output, proof));

    // A too-short secret key is rejected cleanly.
    std::vector<unsigned char> bad_sk(16, 0x01);
    std::vector<unsigned char> o2, p2;
    BOOST_CHECK(!WPoAVRF::Prove(bad_sk, input, o2, p2));
}
