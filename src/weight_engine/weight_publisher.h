// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W3: the single validated write path for the
// admin-attested WeightEngine streams.
// ------------------------------------------------------------------------------
// Three inputs of the weight pipeline are external ATTESTATIONS that cannot be
// derived on-chain, so they are published by governance through admin-only RPCs,
// each routed through WeightPublisher — the ONE choke point for these writes:
//
//   weight-engine-esg            <- weightsetesg            (certified ESG score)
//   weight-engine-membership     <- weightsetmembership     (azienda -> miner map)
//   weight-engine-reconciliation <- weightsetreconciliation (Apuana SB R_k per epoch)
//
// (activity is chain-derived, not published — weight_reader.h; wpoa-weights keeps
// its own port, StreamWeightRegistry.)
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
//     arbitrary/raw writes;
//   * application policy (this RPC only): weightset* additionally requires the
//     acting address to be a GLOBAL admin (CanAdmin) and validates the schema.
// Because write permission is an INDEPENDENT grant from admin, the "admin-only"
// guarantee holds ONLY if operators grant `<stream>.write` exclusively to admin /
// governance addresses. A non-admin that has been granted write could still publish
// a schema-VALID (but forged) record directly via the generic `publishfrom`, and
// the reader currently trusts any schema-valid confirmed record regardless of its
// publisher. Recommended hardening (future): have the reader additionally require
// CanAdmin(publisher) before folding a record into the weight math.

#ifndef MC_WEIGHT_PUBLISHER_H
#define MC_WEIGHT_PUBLISHER_H

#include <string>
#include <stdint.h>

#include "json/json_spirit_value.h"

/**
 * WeightPublisher — validated, admin-gated publication of the three attestation
 * streams. Static methods; each returns the publish txid or throws JSONRPCError.
 * `from_address` is the acting address the caller has already verified is a global
 * admin; it is also the tx publisher, so its write permission is what gates the tx.
 */
class WeightPublisher
{
public:
    /** esg: {node_address, esg}; esg must be > 0 (W1 parser). Key = node_address. */
    static std::string PublishEsg(const std::string& from_address,
                                  const std::string& node_address, double esg);

    /** membership: item key = miner, payload {<azienda>: ts}; merge rebuilds C_k. */
    static std::string PublishMembership(const std::string& from_address,
                                         const std::string& miner, const std::string& azienda);

    /** reconciliation: {node_address=miner, reconciled, epoch}; R>=0, epoch>=1
     *  (the RPC additionally bounds epoch <= current epoch). Key = miner. */
    static std::string PublishReconciliation(const std::string& from_address,
                                             const std::string& miner, double reconciled,
                                             uint32_t epoch);
};

// Admin RPCs (registered in src/rpc/rpclist.cpp, category "weight").
json_spirit::Value weightsetesg(const json_spirit::Array& params, bool fHelp);
json_spirit::Value weightsetmembership(const json_spirit::Array& params, bool fHelp);
json_spirit::Value weightsetreconciliation(const json_spirit::Array& params, bool fHelp);

#endif // MC_WEIGHT_PUBLISHER_H
