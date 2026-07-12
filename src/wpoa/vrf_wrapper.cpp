// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA Phase 3a — ECVRF / Chaum–Pedersen DLEQ implementation over secp256k1.
// See vrf_wrapper.h for the full construction and the security properties it
// provides to the wPoA randomness beacon.
//
// Implementation notes
// --------------------
// * Only the *core* secp256k1 API is used (pubkey create/parse/serialize/
//   tweak_mul/combine, seckey_verify, privkey_tweak_add/mul). None of these live
//   behind an optional module, so they are present in MultiChain's build (which
//   enables only the recovery module). No internal secp256k1 headers are needed.
// * secp256k1 has cofactor 1, so H (a curve point) has prime order and there is
//   no small-subgroup / cofactor-clearing step: the plain Chaum–Pedersen DLEQ
//   proof of equal discrete logs is a sound ECVRF here.
// * Scalars derived from hashes (the nonce k and challenge c) use a rejection
//   loop against secp256k1_ec_seckey_verify, which accepts exactly the valid
//   scalars in [1, n-1]. Because n is within ~2^-128 of 2^256, rejection is
//   astronomically rare and the tiny modular bias it removes is irrelevant.
// * Point negation: this secp256k1 vintage exposes no pubkey_negate, so −P is
//   computed as (n-1)·P via pubkey_tweak_mul with the constant NEG_ONE = n-1
//   (since (n-1) ≡ -1 mod n).

#include "wpoa/vrf_wrapper.h"

#include "crypto/sha256.h"

#include <cstring>

#include <secp256k1.h>

// Out-of-line definitions for the in-class static constants, required whenever
// they are odr-used (e.g. bound to a const reference by Boost.Test macros).
const size_t WPoAVRF::OUTPUT_SIZE;
const size_t WPoAVRF::GAMMA_SIZE;
const size_t WPoAVRF::SCALAR_SIZE;
const size_t WPoAVRF::PROOF_SIZE;

namespace
{

// Domain-separation: a suite/version tag plus a one-byte role separator keep the
// three hash usages (curve, challenge, output) and any future VRF variant from
// ever colliding on inputs.
const char        VRF_SUITE_TAG[]   = "MC-wPoA-VRF-secp256k1-v1";
const size_t      VRF_SUITE_TAG_LEN = sizeof(VRF_SUITE_TAG) - 1; // drop the NUL
const unsigned char ROLE_NONCE      = 0x01;
const unsigned char ROLE_CHALLENGE  = 0x02;
const unsigned char ROLE_OUTPUT     = 0x03;
const unsigned char ROLE_H2C        = 0x04;

// n - 1 for the secp256k1 group order n. Multiplying a point by this negates it
// ((n-1)·P = -P), the workaround for the missing pubkey_negate in this vintage.
const unsigned char NEG_ONE[32] = {
    0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,
    0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFE,
    0xBA,0xAE,0xDC,0xE6,0xAF,0x48,0xA0,0x3B,
    0xBF,0xD2,0x5E,0x8C,0xD0,0x36,0x41,0x40
};

// A single process-wide context with sign+verify capability. C++11 guarantees
// the static local is initialized exactly once, thread-safely.
secp256k1_context* VRFContext()
{
    static secp256k1_context* ctx =
        secp256k1_context_create(SECP256K1_CONTEXT_SIGN | SECP256K1_CONTEXT_VERIFY);
    return ctx;
}

// Serialize a point to its 33-byte compressed form. Returns false only on an
// internal secp256k1 error (never expected for a valid in-memory point).
bool SerializePoint(const secp256k1_pubkey* p, unsigned char out33[33])
{
    size_t len = 33;
    if (!secp256k1_ec_pubkey_serialize(VRFContext(), out33, &len, p, SECP256K1_EC_COMPRESSED))
    {
        return false;
    }
    return len == 33;
}

// Deterministically map arbitrary input bytes to a curve point by
// try-and-increment: hash (suite ‖ role ‖ counter ‖ input) to 32 bytes, treat
// them as a compressed x-coordinate with an even-Y prefix (0x02), and parse;
// bump the counter until a valid point is found. About half of all 32-byte
// strings are valid x-coordinates, so this terminates after ~2 tries on average.
bool HashToCurve(const unsigned char* input, size_t input_len, secp256k1_pubkey* out)
{
    unsigned char candidate[33];
    candidate[0] = 0x02; // even Y; the specific branch is irrelevant to soundness
    for (uint32_t counter = 0; counter < 256; counter++)
    {
        unsigned char ctr = (unsigned char)counter;
        CSHA256 h;
        h.Write((const unsigned char*)VRF_SUITE_TAG, VRF_SUITE_TAG_LEN);
        h.Write(&ROLE_H2C, 1);
        h.Write(&ctr, 1);
        h.Write(input, input_len);
        h.Finalize(candidate + 1);
        if (secp256k1_ec_pubkey_parse(VRFContext(), out, candidate, 33))
        {
            return true;
        }
    }
    return false; // unreachable in practice
}

// Hash a sequence of byte-chunks to a scalar in [1, n-1]. A one-byte counter is
// mixed in and incremented until the digest is a valid secp256k1 scalar, which
// removes both the ==0 and the >=n cases. Both prover and verifier run the
// identical deterministic loop, so they derive the identical scalar.
bool HashToScalar(unsigned char role,
                  const unsigned char* const* chunks, const size_t* chunk_lens,
                  size_t n_chunks, unsigned char out32[32])
{
    for (uint32_t counter = 0; counter < 256; counter++)
    {
        unsigned char ctr = (unsigned char)counter;
        CSHA256 h;
        h.Write((const unsigned char*)VRF_SUITE_TAG, VRF_SUITE_TAG_LEN);
        h.Write(&role, 1);
        h.Write(&ctr, 1);
        for (size_t i = 0; i < n_chunks; i++)
        {
            h.Write(chunks[i], chunk_lens[i]);
        }
        h.Finalize(out32);
        if (secp256k1_ec_seckey_verify(VRFContext(), out32))
        {
            return true;
        }
    }
    return false; // unreachable in practice
}

// output = SHA256(suite ‖ ROLE_OUTPUT ‖ compressed(Gamma))
void ComputeOutput(const unsigned char gamma33[33], unsigned char out32[32])
{
    CSHA256 h;
    h.Write((const unsigned char*)VRF_SUITE_TAG, VRF_SUITE_TAG_LEN);
    h.Write(&ROLE_OUTPUT, 1);
    h.Write(gamma33, 33);
    h.Finalize(out32);
}

// c = HashToScalar(ROLE_CHALLENGE, H ‖ PK ‖ Gamma ‖ U ‖ V), each point
// compressed. Binds the DLEQ proof to both statement points (PK=sk·G,
// Gamma=sk·H) and both commitments (U=k·G, V=k·H).
bool ComputeChallenge(const unsigned char H33[33], const unsigned char PK33[33],
                      const unsigned char Gamma33[33], const unsigned char U33[33],
                      const unsigned char V33[33], unsigned char out_c[32])
{
    const unsigned char* chunks[5] = { H33, PK33, Gamma33, U33, V33 };
    const size_t lens[5]           = { 33, 33, 33, 33, 33 };
    return HashToScalar(ROLE_CHALLENGE, chunks, lens, 5, out_c);
}

} // anonymous namespace

bool WPoAVRF::Prove(const unsigned char* sk32,
                    const unsigned char* input, size_t input_len,
                    unsigned char* output32, unsigned char* proof)
{
    secp256k1_context* ctx = VRFContext();

    if (!secp256k1_ec_seckey_verify(ctx, sk32))
    {
        return false;
    }

    // PK = sk·G
    secp256k1_pubkey PK;
    if (!secp256k1_ec_pubkey_create(ctx, &PK, sk32))
    {
        return false;
    }

    // H = HashToCurve(input);  Gamma = sk·H
    secp256k1_pubkey H;
    if (!HashToCurve(input, input_len, &H))
    {
        return false;
    }
    secp256k1_pubkey Gamma = H;
    if (!secp256k1_ec_pubkey_tweak_mul(ctx, &Gamma, sk32))
    {
        return false;
    }

    unsigned char H33[33], PK33[33], Gamma33[33];
    if (!SerializePoint(&H, H33) || !SerializePoint(&PK, PK33) ||
        !SerializePoint(&Gamma, Gamma33))
    {
        return false;
    }

    // Deterministic nonce k = HashToScalar(ROLE_NONCE, sk ‖ compressed(H)).
    unsigned char k[32];
    {
        const unsigned char* chunks[2] = { sk32, H33 };
        const size_t lens[2]           = { 32, 33 };
        if (!HashToScalar(ROLE_NONCE, chunks, lens, 2, k))
        {
            return false;
        }
    }

    // U = k·G,  V = k·H
    secp256k1_pubkey U;
    if (!secp256k1_ec_pubkey_create(ctx, &U, k))
    {
        return false;
    }
    secp256k1_pubkey V = H;
    if (!secp256k1_ec_pubkey_tweak_mul(ctx, &V, k))
    {
        return false;
    }

    unsigned char U33[33], V33[33];
    if (!SerializePoint(&U, U33) || !SerializePoint(&V, V33))
    {
        return false;
    }

    // c = challenge;  s = k + c·sk (mod n)
    unsigned char c[32];
    if (!ComputeChallenge(H33, PK33, Gamma33, U33, V33, c))
    {
        return false;
    }

    unsigned char s[32];
    memcpy(s, sk32, 32);
    if (!secp256k1_ec_privkey_tweak_mul(ctx, s, c))    // s = sk·c
    {
        return false;
    }
    if (!secp256k1_ec_privkey_tweak_add(ctx, s, k))    // s = sk·c + k
    {
        return false;
    }

    // Assemble outputs: output = SHA256(...Gamma), proof = Gamma ‖ c ‖ s.
    ComputeOutput(Gamma33, output32);
    memcpy(proof,               Gamma33, 33);
    memcpy(proof + 33,          c,       32);
    memcpy(proof + 33 + 32,     s,       32);
    return true;
}

bool WPoAVRF::Verify(const unsigned char* pubkey, size_t pubkey_len,
                     const unsigned char* input, size_t input_len,
                     const unsigned char* output32, const unsigned char* proof)
{
    secp256k1_context* ctx = VRFContext();

    // Parse the proposer public key.
    secp256k1_pubkey PK;
    if (!secp256k1_ec_pubkey_parse(ctx, &PK, pubkey, pubkey_len))
    {
        return false;
    }

    // Split the proof into Gamma ‖ c ‖ s and range-check the scalars.
    const unsigned char* Gamma_bytes = proof;
    const unsigned char* c           = proof + 33;
    const unsigned char* s           = proof + 33 + 32;

    secp256k1_pubkey Gamma;
    if (!secp256k1_ec_pubkey_parse(ctx, &Gamma, Gamma_bytes, 33))
    {
        return false;
    }
    if (!secp256k1_ec_seckey_verify(ctx, c) || !secp256k1_ec_seckey_verify(ctx, s))
    {
        return false;
    }

    // The reveal must be the one this proof commits to.
    unsigned char expected_output[32];
    ComputeOutput(Gamma_bytes, expected_output);
    if (memcmp(expected_output, output32, 32) != 0)
    {
        return false;
    }

    // Recompute H from the public input.
    secp256k1_pubkey H;
    if (!HashToCurve(input, input_len, &H))
    {
        return false;
    }

    // U' = s·G − c·PK
    secp256k1_pubkey sG;
    if (!secp256k1_ec_pubkey_create(ctx, &sG, s))
    {
        return false;
    }
    secp256k1_pubkey negcPK = PK;
    if (!secp256k1_ec_pubkey_tweak_mul(ctx, &negcPK, c) ||        // c·PK
        !secp256k1_ec_pubkey_tweak_mul(ctx, &negcPK, NEG_ONE))    // −(c·PK)
    {
        return false;
    }
    secp256k1_pubkey Uprime;
    {
        const secp256k1_pubkey* ins[2] = { &sG, &negcPK };
        if (!secp256k1_ec_pubkey_combine(ctx, &Uprime, ins, 2))
        {
            // Point at infinity (s·G == c·PK) — an honest proof never produces
            // this (it would require k == 0); reject.
            return false;
        }
    }

    // V' = s·H − c·Gamma
    secp256k1_pubkey sH = H;
    if (!secp256k1_ec_pubkey_tweak_mul(ctx, &sH, s))
    {
        return false;
    }
    secp256k1_pubkey negcGamma = Gamma;
    if (!secp256k1_ec_pubkey_tweak_mul(ctx, &negcGamma, c) ||       // c·Gamma
        !secp256k1_ec_pubkey_tweak_mul(ctx, &negcGamma, NEG_ONE))   // −(c·Gamma)
    {
        return false;
    }
    secp256k1_pubkey Vprime;
    {
        const secp256k1_pubkey* ins[2] = { &sH, &negcGamma };
        if (!secp256k1_ec_pubkey_combine(ctx, &Vprime, ins, 2))
        {
            return false;
        }
    }

    // c' = challenge(H, PK, Gamma, U', V');  accept iff c' == c.
    unsigned char H33[33], PK33[33], Gamma33[33], Up33[33], Vp33[33];
    if (!SerializePoint(&H, H33) || !SerializePoint(&PK, PK33) ||
        !SerializePoint(&Gamma, Gamma33) || !SerializePoint(&Uprime, Up33) ||
        !SerializePoint(&Vprime, Vp33))
    {
        return false;
    }

    unsigned char cprime[32];
    if (!ComputeChallenge(H33, PK33, Gamma33, Up33, Vp33, cprime))
    {
        return false;
    }

    return memcmp(cprime, c, 32) == 0;
}

bool WPoAVRF::Prove(const std::vector<unsigned char>& sk,
                    const std::vector<unsigned char>& input,
                    std::vector<unsigned char>& output,
                    std::vector<unsigned char>& proof)
{
    output.clear();
    proof.clear();
    if (sk.size() != 32)
    {
        return false;
    }
    unsigned char out_buf[OUTPUT_SIZE];
    unsigned char proof_buf[PROOF_SIZE];
    if (!Prove(sk.data(), input.data(), input.size(), out_buf, proof_buf))
    {
        return false;
    }
    output.assign(out_buf, out_buf + OUTPUT_SIZE);
    proof.assign(proof_buf, proof_buf + PROOF_SIZE);
    return true;
}

bool WPoAVRF::Verify(const std::vector<unsigned char>& pubkey,
                     const std::vector<unsigned char>& input,
                     const std::vector<unsigned char>& output,
                     const std::vector<unsigned char>& proof)
{
    if (output.size() != OUTPUT_SIZE || proof.size() != PROOF_SIZE)
    {
        return false;
    }
    return Verify(pubkey.data(), pubkey.size(), input.data(), input.size(),
                  output.data(), proof.data());
}
