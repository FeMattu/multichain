// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W1: the pure authorization policy for the
// weight-engine input streams.
// ------------------------------------------------------------------------------
// The three published input streams do NOT share one authorization model. The split
// follows a single criterion — can a third party VERIFY the claim? — and this header
// holds the resulting decision tables as pure functions, so they are unit-testable
// without a running node (test/weight_authorization_tests.cpp) and stated in exactly
// one place instead of being scattered through RPC bodies.
//
//   weight-engine-membership     SELF-ATTESTED. A node declares its own cluster; the
//                                reader checks the transaction's signer against the
//                                payload (weight_records.h
//                                mc_MembershipRecordIsSelfAttested). No privilege is
//                                involved at all, so no policy is needed here.
//   weight-engine-esg            CERTIFICATION AUTHORITY only. See below.
//   weight-engine-reconciliation ADMIN only (unchanged).
//
// WHY ESG NEEDS A ROLE OF ITS OWN. An ESG score is an attestation of TRUST: it is
// produced by an external certification process — documentary review, compliance
// questionnaires, audit by a third-party body — and nothing about it can be checked
// cryptographically by a peer. Unlike the recomputable inputs, there is no assertion
// to validate; the only available defence is to restrict rigidly WHO may assert it.
//
// That is a different question from "who runs the network". Signing an ESG
// certification and administering the chain are separate competences, and conflating
// them forces every certifier to hold full chain-administration power. So the writer
// is a CERTIFICATION AUTHORITY (CA): a role the global administrator delegates
// explicitly, per address, and can revoke.
//
// HOW THE CA ROLE IS CARRIED ON CHAIN. MultiChain has no arbitrary named custom
// permission — there is no `grant <addr> custom.certauth`. It offers exactly six
// FIXED slots (permission.h): low1..low3 (MC_PTP_CUSTOM1..3) and high1..high3
// (MC_PTP_CUSTOM4..6). The CA role therefore occupies one of them, and it must be a
// HIGH slot: mc_Permissions::IsActivateEnough returns 0 for the high slots, so
// granting one requires `admin` and not merely `activate` — which is precisely the
// requirement that only the administrator may confer CA status. The low slots are
// grantable by an `activate` holder and would weaken that.
//
// NOT CONSENSUS-CRITICAL, deliberately. This policy gates LOCAL PUBLICATION only:
// the reader still accepts any schema-valid confirmed ESG record regardless of its
// publisher, exactly as before. Two nodes disagreeing about who is a CA therefore
// disagree about whether their own RPC will publish — they do not compute different
// weights and cannot fork. That is why the CA slot is a compile-time constant here
// rather than a params.dat chain parameter: making it inheritable would imply a
// consensus role it does not have. The consequence is the known limit that survives
// from before, recorded on WeightEsgWriteDecision below.

#ifndef MC_WEIGHT_AUTHORIZATION_H
#define MC_WEIGHT_AUTHORIZATION_H

// ---------------------------------------------------------------------------
// The on-chain marker of the Certification Authority role
// ---------------------------------------------------------------------------
// Wire name, for operator-facing messages and documentation:
//     multichain-cli <chain> grant <address> high1     # confer CA status
//     multichain-cli <chain> revoke <address> high1    # withdraw it
//
// OPERATIONAL NOTE. Because the slot is one of MultiChain's six fixed custom
// permissions, a deployment that already uses `high1` for an application-level RBAC
// role must pick a different slot for that role, or it would be indistinguishable
// from CA status. The name is defined once, here, so moving the role to another slot
// is a one-line change plus a documentation update.
#define MC_WEIGHT_CA_PERMISSION_NAME   "high1"

/** Outcome of the ESG write-authorization decision. Distinct values rather than a
 *  bool so the caller can return an accurate error: an address refused for lacking
 *  the CA role needs a different message from one refused for lacking `.write`. */
enum WeightEsgWriteDecision
{
    MC_WEIGHT_ESG_WRITE_OK = 0,        //!< authorized: CA role held and stream writable
    MC_WEIGHT_ESG_WRITE_NOT_CA,        //!< not a Certification Authority
    MC_WEIGHT_ESG_WRITE_NO_STREAM_PERM,//!< CA, but lacks MC_PTP_WRITE on the stream
    MC_WEIGHT_ESG_WRITE_NO_CA_SUPPORT  //!< the chain's protocol predates custom permissions
};

/**
 * Decide whether an address may publish an ESG attestation.
 *
 * The two conditions are INDEPENDENT and both required, in this order:
 *
 *   1. the CA role (application policy, this layer);
 *   2. `weight-engine-esg.write` (the on-chain gate, enforced by MultiChain).
 *
 * The order matters for the error message, not for the outcome. It is checked
 * CA-first so an operator who granted `.write` to a non-certifier is told the real
 * problem — that the address is not a certification authority — rather than being led
 * to believe more permissions are needed.
 *
 * BEING A GLOBAL ADMINISTRATOR IS NOT SUFFICIENT, and that is the point of the role:
 * the administrator *confers* CA status, it does not automatically hold it. An admin
 * that wants to certify grants itself `high1` explicitly, which keeps the two
 * competences distinguishable on chain — `listpermissions` shows who certifies
 * separately from who administers.
 *
 * REVOCATION takes effect immediately and independently of `.write`: an address whose
 * `high1` was revoked is refused here even though it still holds stream write
 * permission. Revoking `.write` as well is still recommended — it closes the raw
 * `publishfrom` route described below — but the CA check does not depend on it.
 *
 * KNOWN LIMIT (unchanged by this policy, and narrowed no further). The reader accepts
 * any schema-valid confirmed ESG record regardless of who published it, so an address
 * holding `.write` but not the CA role can still land a forged record through the
 * generic `publishfrom`, bypassing this decision entirely. This gate raises the bar
 * for the sanctioned path and separates the two roles; it does not make ESG
 * self-verifiable, because nothing can. Closing it would require the reader to
 * enforce the CA role too, which is deliberately NOT done here: permissions are
 * mutable, so a later revocation would retroactively invalidate historical records
 * and change already-computed epoch weights — a determinism hazard worse than the
 * limit it removes. See docs/weight-engine.md.
 *
 * @param is_certification_authority  Whether the address holds the CA permission.
 * @param has_stream_write            Whether it holds MC_PTP_WRITE on the ESG stream.
 * @param chain_supports_custom_perms Whether the chain's protocol version provides
 *                                    custom permissions at all (>= 20004). When it
 *                                    does not, the CA role cannot be expressed and
 *                                    the decision FAILS CLOSED rather than silently
 *                                    falling back to an admin check — a silent
 *                                    fallback would reopen exactly the conflation
 *                                    the role exists to prevent.
 */
inline WeightEsgWriteDecision mc_WeightEsgWriteDecision(bool is_certification_authority,
                                                        bool has_stream_write,
                                                        bool chain_supports_custom_perms)
{
    if (!chain_supports_custom_perms)
    {
        return MC_WEIGHT_ESG_WRITE_NO_CA_SUPPORT;
    }
    if (!is_certification_authority)
    {
        return MC_WEIGHT_ESG_WRITE_NOT_CA;
    }
    if (!has_stream_write)
    {
        return MC_WEIGHT_ESG_WRITE_NO_STREAM_PERM;
    }
    return MC_WEIGHT_ESG_WRITE_OK;
}

/** A stable operator-facing explanation of a refusal; "" for the authorized case.
 *  Kept beside the decision so a new outcome cannot be added without a message. */
inline const char* mc_WeightEsgWriteDecisionText(WeightEsgWriteDecision d)
{
    switch (d)
    {
        case MC_WEIGHT_ESG_WRITE_OK:
            return "";
        case MC_WEIGHT_ESG_WRITE_NOT_CA:
            return "this node's address is not a Certification Authority. An ESG score is "
                   "an attestation of trust that no peer can verify, so only a delegated "
                   "certifier may publish one. Being a global administrator is not "
                   "sufficient: the administrator confers the role, it does not hold it "
                   "automatically. Grant it with:  grant <address> " MC_WEIGHT_CA_PERMISSION_NAME;
        case MC_WEIGHT_ESG_WRITE_NO_STREAM_PERM:
            return "this node's address is a Certification Authority but lacks write "
                   "permission on the ESG stream. Grant it with:  "
                   "grant <address> weight-engine-esg.write";
        case MC_WEIGHT_ESG_WRITE_NO_CA_SUPPORT:
            return "this chain's protocol version predates MultiChain custom permissions "
                   "(>= 20004 required), so the Certification Authority role cannot be "
                   "expressed on chain. ESG publication is refused rather than falling "
                   "back to an admin-only check, which would silently re-conflate "
                   "administering the network with certifying ESG scores.";
        default:
            return "ESG publication refused";
    }
}

#endif // MC_WEIGHT_AUTHORIZATION_H
