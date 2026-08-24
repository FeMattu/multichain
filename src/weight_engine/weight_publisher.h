// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W3: the single validated write path for the two
// PUBLISHED WeightEngine input streams.
// ------------------------------------------------------------------------------
// TWO inputs of the weight pipeline are published rather than derived, and they do NOT
// share one authorization model — the split follows what a third party can verify:
//
//   weight-engine-esg            <- weightsetesg              CERTIFICATION AUTHORITY
//         An external attestation about a third party. Nobody can check an ESG
//         score cryptographically, so restricting WHO may assert it is the only
//         available defence — and the writer is a role the administrator delegates
//         per address and can revoke, NOT the administrator itself. See
//         weight_authorization.h.
//   weight-engine-membership     <- weightregistermembership  PUBLIC (self-write)
//         A node declaring its OWN cluster. The claim is self-verifiable: the
//         reader compares the payload's node_address against the transaction's
//         signer and discards any mismatch, so opening the write to every node
//         costs nothing — nobody can declare membership for somebody else.
// (tau AND R are chain-derived, not published — weight_reader.h
// ComputeActivityAndReconciliationForEpoch. R used to be a third stream carrying an
// ADMIN ATTESTATION of a value the chain already recorded; it was removed, together
// with the weightsetreconciliation RPC and PublishReconciliation, when R became a
// derivation. See wpoa/docs/adr/reconciliation-onchain.md. wpoa-weights keeps its own
// port, StreamWeightRegistry.)
//
// Every WeightPublisher method, before it publishes, ROUND-TRIP validates the
// record with the SAME W1 parser the reader uses (mc_Parse*RecordJson) — so it
// cannot emit a MALFORMED record the reader would reject — then verifies the acting
// address has write permission on the (CLOSED) stream, then publishes FROM that
// address. Any failure throws JSONRPCError so the calling RPC returns a precise
// error. The streams are created/subscribed by the reader
// (WeightStreamReader::EnsureInputStreams); the publisher requires them to exist.
//
// SECURITY MODEL (read carefully). There are TWO gates and they are distinct:
//   * on-chain (consensus-enforced): the streams are CLOSED, so only an address
//     holding MC_PTP_WRITE on the stream can publish at all — this is what stops
//     arbitrary/raw writes. For membership, `.write` is now meant to be granted to
//     EVERY node on the network (network admission itself stays gated upstream by
//     the KYC-backed `connect` permission);
//   * application policy (these RPCs only): weightsetesg additionally requires the
//     acting address to hold the Certification Authority role
//     (IsCertificationAuthority, NOT CanAdmin); weightregistermembership requires
//     nothing, because it structurally cannot write about anyone but the caller.
//
// KNOWN LIMIT, and where it no longer applies. Write permission is an INDEPENDENT
// grant from the role, so for ESG the guarantee holds only if operators grant
// `weight-engine-esg.write` exclusively to the intended certifiers: an address holding
// `.write` without the role could publish a schema-VALID but forged record through the
// generic `publishfrom`, and the reader accepts any schema-valid confirmed record.
// MEMBERSHIP IS NOT EXPOSED TO THIS. Its validity rule is
// enforced by the reader against the transaction's signature rather than against the
// writer's privileges, so a forged record — one naming a node_address other than the
// signer — is discarded by every honest node no matter which RPC produced it.

#ifndef MC_WEIGHT_PUBLISHER_H
#define MC_WEIGHT_PUBLISHER_H

#include <string>
#include <stdint.h>

#include "json/json_spirit_value.h"

/**
 * WeightPublisher — validated publication of the two published input streams. Static
 * methods; each returns the publish txid or throws JSONRPCError. `from_address` is the
 * acting address the caller has already authorized (a Certification Authority for ESG,
 * the caller itself for membership); it is also the tx publisher, so its write
 * permission is what gates the tx.
 */
class WeightPublisher
{
public:
    /** esg: {node_address, esg}; esg must be > 0 (W1 parser). Key = node_address. */
    static std::string PublishEsg(const std::string& from_address,
                                  const std::string& node_address, double esg);

    /** membership: SELF-WRITE. Item key = node_address, payload
     *  {node_address, miner_address, timestamp}. `node_address` must equal
     *  `from_address` — a node may only declare its own cluster — otherwise this
     *  throws, mirroring the reader's discard rule. */
    static std::string PublishMembership(const std::string& from_address,
                                        const std::string& node_address,
                                        const std::string& miner_address);

};

// RPCs (registered in src/rpc/rpclist.cpp, category "weight").
//
// weightsetesg is CERTIFICATION-AUTHORITY-only: it carries an external attestation
// about a third party that no peer can verify, so restricting the writer is the only
// defence. weightregistermembership is PUBLIC: it can only ever write a record about
// the calling node itself, which the reader verifies cryptographically.
json_spirit::Value weightsetesg(const json_spirit::Array& params, bool fHelp);
json_spirit::Value weightregistermembership(const json_spirit::Array& params, bool fHelp);

#endif // MC_WEIGHT_PUBLISHER_H
