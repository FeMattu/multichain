// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA (Weighted Proof of Authority) — Phase 3a: VRF wrapper
// -----------------------------------------------------------------------
// A publicly-verifiable Verifiable Random Function (VRF) over the secp256k1
// curve already bundled with MultiChain (the same curve as the validator
// signing keys). This is the *randomness-generation* primitive of the wPoA
// beacon (Layer 2 in docs/implementation-roadmap.md §1): the proposer elected
// for a block produces a verifiable pseudorandom reveal bound to its key and to
// the round's public input, embeds it in the block, and every peer verifies it.
//
// Construction — ECVRF / Chaum–Pedersen DLEQ (secp256k1 has cofactor 1, which
// removes the cofactor-clearing steps of the full RFC 9381 suites):
//
//   H       = HashToCurve(input)                         (try-and-increment)
//   Gamma   = sk · H                                      (the VRF pre-output)
//   output  = SHA256(SUITE ‖ 0x03 ‖ compressed(Gamma))    (the reveal R[n])
//   proof   = compressed(Gamma) ‖ c ‖ s                    (π[n], 33+32+32 = 97 B)
//     with a Fiat–Shamir DLEQ proof that log_G(PK) = log_H(Gamma):
//       k = HashToScalar(SUITE ‖ 0x01 ‖ sk ‖ compressed(H))   (deterministic nonce)
//       U = k · G,   V = k · H
//       c = HashToScalar(SUITE ‖ 0x02 ‖ H ‖ PK ‖ Gamma ‖ U ‖ V)
//       s = k + c · sk   (mod n)
//
// Verification recomputes U' = s·G − c·PK and V' = s·H − c·Gamma and accepts iff
// c == HashToScalar(SUITE ‖ 0x02 ‖ H ‖ PK ‖ Gamma ‖ U' ‖ V') and
// output == SHA256(SUITE ‖ 0x03 ‖ compressed(Gamma)).
//
// Security properties this gives the beacon (docs/thesis-project-overview.md
// §7.1–§7.2):
//   * Uniqueness  — exactly one valid (output, proof) per (sk, input): a
//                   proposer cannot grind alternative reveals (grinding
//                   resistance).
//   * Pseudorandomness — output is indistinguishable from random without sk.
//   * Public verifiability — any peer checks the reveal from PK alone.
//
// This wrapper is PURE and node-free (it depends only on secp256k1 + SHA256), so
// it is unit-tested in isolation (test/vrf_wrapper_tests.cpp) exactly like the
// Phase 2 selector core. The node-coupled activation flag/predicate
// (g_wpoa_vrf_enabled, WPoAVRFActiveAtHeight) live with the rest of the wPoA
// node glue in wpoa_selector.{h,cpp}, not here.

#ifndef WPOA_VRF_WRAPPER_H
#define WPOA_VRF_WRAPPER_H

#include <stddef.h>
#include <stdint.h>
#include <vector>

/**
 * WPoAVRF — pure, deterministic, node-free VRF over secp256k1.
 *
 * All methods are static and depend only on secp256k1 + SHA256, so they can be
 * exercised by the Boost.Test unit suite without linking the wallet / node
 * runtime (see test/vrf_wrapper_tests.cpp). Keys are the ordinary secp256k1
 * validator keys: a 32-byte secret and a 33-byte compressed public key — no
 * separate VRF key material is introduced.
 */
class WPoAVRF
{
public:
    /** Byte lengths of the VRF outputs, part of the on-chain wire format. */
    static const size_t OUTPUT_SIZE = 32;        // reveal R[n] = SHA256(...)
    static const size_t GAMMA_SIZE  = 33;        // compressed pre-output point
    static const size_t SCALAR_SIZE = 32;        // c and s
    static const size_t PROOF_SIZE  = GAMMA_SIZE + SCALAR_SIZE + SCALAR_SIZE; // 97

    /**
     * Evaluate the VRF: produce the reveal and its proof.
     *
     * Deterministic in (sk, input): the same key and input always yield the same
     * (output, proof), and — by VRF uniqueness — no other (output, proof) will
     * verify. Uses a hash-derived deterministic nonce, so it needs no external
     * randomness and never leaks the key through a bad nonce.
     *
     * @param sk32       32-byte secret key (a valid secp256k1 scalar in [1,n-1]).
     * @param input      Public VRF input bytes (Phase 3a: the previous block hash).
     * @param input_len  Length of `input`.
     * @param output32   [out] OUTPUT_SIZE bytes — the reveal R[n].
     * @param proof      [out] PROOF_SIZE bytes — the proof π[n].
     * @return true on success; false if the key is invalid or a (negligible)
     *         degenerate scalar is hit — callers treat false as "cannot reveal".
     */
    static bool Prove(const unsigned char* sk32,
                      const unsigned char* input, size_t input_len,
                      unsigned char* output32, unsigned char* proof);

    /**
     * Verify a VRF reveal against a public key and input.
     *
     * Returns true iff `proof` is a valid DLEQ proof for `pubkey` over `input`
     * AND `output32` is the reveal that `proof` commits to. A validator MUST
     * reject a wPoA-VRF block whose reveal does not verify (a forged or absent
     * reveal), and MAY then trust the reveal as an unbiased, unpredictable
     * contribution bound to the proposer's identity.
     *
     * @param pubkey      Serialized secp256k1 public key (33-byte compressed or
     *                    65-byte uncompressed — the validator's signer key).
     * @param pubkey_len  Length of `pubkey`.
     * @param input       Public VRF input bytes (must match Prove()).
     * @param input_len   Length of `input`.
     * @param output32    OUTPUT_SIZE bytes claimed as the reveal.
     * @param proof       PROOF_SIZE bytes claimed as the proof.
     * @return true iff the reveal and proof are valid and consistent.
     */
    static bool Verify(const unsigned char* pubkey, size_t pubkey_len,
                       const unsigned char* input, size_t input_len,
                       const unsigned char* output32, const unsigned char* proof);

    /**
     * Convenience wrapper over Prove() using std::vector outputs.
     * @return true on success; on failure the output vectors are left empty.
     */
    static bool Prove(const std::vector<unsigned char>& sk,
                      const std::vector<unsigned char>& input,
                      std::vector<unsigned char>& output,
                      std::vector<unsigned char>& proof);

    /** Convenience wrapper over Verify() using std::vector inputs. */
    static bool Verify(const std::vector<unsigned char>& pubkey,
                       const std::vector<unsigned char>& input,
                       const std::vector<unsigned char>& output,
                       const std::vector<unsigned char>& proof);
};

#endif // WPOA_VRF_WRAPPER_H
