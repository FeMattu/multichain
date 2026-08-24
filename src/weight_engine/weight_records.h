// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W1: pure, dependency-light helpers that parse
// the WeightEngine input-stream item payloads and fold them into the in-memory
// structures the pipeline consumes.
//
// There are TWO published input streams, membership and ESG, so there are two record
// parsers here. The pipeline's other two inputs — the activity counters tau and the
// reconciled amounts R — are DERIVED from the epoch's confirmed blocks rather than
// published, so they have no wire format and nothing to parse (weight_reader.h
// ComputeActivityAndReconciliationForEpoch; wpoa/docs/adr/reconciliation-onchain.md).
//
// Mirrors wpoa/weight_record.h: this header depends only on json_spirit (plus
// the C++ standard library), so the parsing/aggregation logic can be unit-tested
// in isolation, without linking the wallet / node runtime. See
// src/weight_engine/test/weight_records_tests.cpp. The node-coupled reader that
// pulls the raw item values off the streams lives in weight_reader.{h,cpp} (W3).
//
// CONSENSUS-CRITICAL. These parsers are the gate that decides which on-chain
// items are allowed to enter the weight math. Every honest node must accept or
// reject the same item bit-identically, or nodes derive different w_k and fork.
//
// THE MEMBERSHIP GATE IS SPLIT IN TWO. A membership record must additionally be
// SELF-ATTESTED: the transaction's signing address must equal the node_address in
// the payload (weight_streams.h). That half cannot be decided from the payload, so
// mc_ParseMembershipRecordJson only validates the shape and the W3 reader enforces
// the signer match. Both halves are consensus-critical; passing this parser is
// necessary but not sufficient for a record to enter C_k.
//
// Two further disciplines follow from determinism and are enforced here:
//   * numeric fields destined for a fixed-width integer (tau, epoch) are range-
//     and integrality-checked BEFORE the cast — an out-of-range double->uint32_t
//     conversion is undefined behavior in C++ and could differ across builds;
//   * non-finite doubles (NaN/Inf) are rejected centrally, since a NaN silently
//     passes ordinary `< 0` range guards.
// The parsers are kept explicit (one typed function per stream) rather than
// driven by a generic schema/factory: the typed out-params are the validated
// contract handed to the W3 reader, and each stream's accept/reject rule stays
// readable in one place for audit.

#ifndef MC_WEIGHT_RECORDS_H
#define MC_WEIGHT_RECORDS_H

#include <cmath>
#include <map>
#include <set>
#include <string>
#include <vector>
#include <stdint.h>

#include "weight_engine/weight_streams.h"
#include "wpoa/weight_record.h"   // mc_StreamItemIsSelfAttested (shared, one copy)
#include "json/json_spirit_value.h"
#include <boost/foreach.hpp>

// ---------------------------------------------------------------------------
// Shared unwrapping / field extraction
// ---------------------------------------------------------------------------

/**
 * Unwrap a decoded stream-item value into its inner record object.
 *
 * OpReturnFormatEntry produces two shapes for a UBJSON item, depending on the
 * overload used (see wpoa/weight_record.h for the same handling):
 *   * 6/7-arg overload (like StreamItemEntry): {"json": {...}}          <- direct
 *   * 3-arg  overload:  {"format":"json","formatdata":{"json":{...}}}   <- wrapped
 * Accept both: descend into "formatdata" when present, then into "json".
 *
 * @param data_value  The value produced by OpReturnFormatEntry.
 * @param out_inner   Out: a copy of the inner record object (cleared on failure).
 * @return true iff a "json" object was found; false otherwise.
 */
inline bool mc_WeightUnwrapItemJson(const json_spirit::Value& data_value,
                                    json_spirit::Object& out_inner)
{
    out_inner.clear();

    if (data_value.type() != json_spirit::obj_type)
    {
        return false;
    }

    const json_spirit::Object* obj = &data_value.get_obj();

    json_spirit::Value formatdata_val;
    bool have_formatdata = false;
    BOOST_FOREACH(const json_spirit::Pair& p, *obj)
    {
        if (p.name_ == "formatdata" && p.value_.type() == json_spirit::obj_type)
        {
            formatdata_val = p.value_;
            have_formatdata = true;
            break;
        }
    }
    if (have_formatdata)
    {
        obj = &formatdata_val.get_obj();
    }

    json_spirit::Value json_val;
    bool have_json = false;
    BOOST_FOREACH(const json_spirit::Pair& p, *obj)
    {
        if (p.name_ == "json")
        {
            json_val = p.value_;
            have_json = true;
            break;
        }
    }
    if (!have_json || json_val.type() != json_spirit::obj_type)
    {
        return false;
    }

    out_inner = json_val.get_obj();
    return true;
}

/** Read a string field from an inner record object; false if absent/wrong type.
 *  On a duplicate field name the first occurrence wins (BOOST_FOREACH order) —
 *  deterministic across nodes. */
inline bool mc_WeightGetStr(const json_spirit::Object& inner, const char* name,
                            std::string& out)
{
    BOOST_FOREACH(const json_spirit::Pair& p, inner)
    {
        if (p.name_ == name && p.value_.type() == json_spirit::str_type)
        {
            out = p.value_.get_str();
            return true;
        }
    }
    return false;
}

/** Read a numeric field (int or real) as a FINITE double; false if absent, of
 *  the wrong type, or non-finite (NaN/Inf). Rejecting non-finite values here is
 *  consensus-critical: a NaN would otherwise slip past callers' `< 0` guards and
 *  then be cast to an integer (undefined behavior). First occurrence wins. */
inline bool mc_WeightGetNum(const json_spirit::Object& inner, const char* name,
                            double& out)
{
    BOOST_FOREACH(const json_spirit::Pair& p, inner)
    {
        if (p.name_ == name)
        {
            double v;
            if (p.value_.type() == json_spirit::int_type)
            {
                v = (double)p.value_.get_int64();
            }
            else if (p.value_.type() == json_spirit::real_type)
            {
                v = p.value_.get_real();
            }
            else
            {
                return false; // present but not numeric
            }
            if (!std::isfinite(v))
            {
                return false; // NaN / +-Inf never enter the weight math
            }
            out = v;
            return true;
        }
    }
    return false;
}

/**
 * Read a numeric field as a uint32_t counter, safely.
 *
 * The value must be a finite number, an exact non-negative integer, and within
 * [0, UINT32_MAX]. Only then is the cast performed. This closes the
 * double->uint32_t undefined-behavior hole: a producer publishing e.g.
 * tau = 1e18 or epoch = 1e10 is rejected here rather than truncated to a
 * platform-dependent value that would fork the validator set.
 *
 * @return true iff the field is present and a representable non-negative integer.
 */
inline bool mc_WeightGetBoundedU32(const json_spirit::Object& inner, const char* name,
                                   uint32_t& out)
{
    double v;
    if (!mc_WeightGetNum(inner, name, v)) // also rejects NaN/Inf
    {
        return false;
    }
    if (v < 0.0 || v > (double)UINT32_MAX)
    {
        return false; // out of range for uint32_t
    }
    if (v != std::floor(v))
    {
        return false; // must be an exact integer, not a truncated fraction
    }
    out = (uint32_t)v;
    return true;
}

// ---------------------------------------------------------------------------
// Parsers — one per input stream
// ---------------------------------------------------------------------------

/**
 * Parse a self-attested membership item:
 *   {"json":{"node_address":"..","miner_address":"..","timestamp":n}}.
 *
 * `node_address` is the node DECLARING the membership (a company, or a miner
 * declaring itself the head of its own cluster); `miner_address` is the cluster it
 * joins. Both must be non-empty. `timestamp` is informational only — the ordering
 * that decides which declaration wins is the CHAIN order of the confirmed items,
 * never this field, which the publisher controls and could set arbitrarily. It is
 * still range-checked so a malformed record is rejected rather than silently
 * ignored.
 *
 * WHAT THIS PARSER DOES NOT CHECK. Self-attestation — that the transaction was
 * signed by `node_address` — is not verifiable from the payload alone: it needs the
 * publishing transaction's inputs. That check lives in the W3 reader
 * (WeightStreamReader::ReadMembership) and is the second half of the validity rule;
 * a record accepted here can still be discarded there.
 *
 * @param data_value     The value produced by OpReturnFormatEntry.
 * @param node_address   Out: the declaring node (cleared on failure).
 * @param miner_address  Out: the cluster joined (cleared on failure).
 * @param timestamp      Out: the declared timestamp (0 on failure).
 * @return true iff both addresses are present, non-empty, and the timestamp is a
 *         representable non-negative integer.
 */
inline bool mc_ParseMembershipRecordJson(const json_spirit::Value& data_value,
                                         std::string& node_address,
                                         std::string& miner_address,
                                         uint32_t& timestamp)
{
    node_address = "";
    miner_address = "";
    timestamp = 0;

    json_spirit::Object inner;
    if (!mc_WeightUnwrapItemJson(data_value, inner))
    {
        return false;
    }

    std::string node;
    std::string miner;
    uint32_t ts = 0;
    if (!mc_WeightGetStr(inner, MC_WEIGHT_FIELD_NODE_ADDR, node) ||
        !mc_WeightGetStr(inner, MC_WEIGHT_FIELD_MINER_ADDR, miner) ||
        !mc_WeightGetBoundedU32(inner, MC_WEIGHT_FIELD_TIMESTAMP, ts))
    {
        return false;
    }
    if (node.empty() || miner.empty())
    {
        return false;
    }

    node_address = node;
    miner_address = miner;
    timestamp = ts;
    return true;
}

/**
 * The SELF-ATTESTATION rule for a membership record (consensus-critical): valid iff
 * the address that SIGNED the publishing transaction is the `node_address` the
 * payload declares. A record failing it is DISCARDED by the reader.
 *
 * A named, membership-specific wrapper over the shared predicate
 * mc_StreamItemIsSelfAttested (wpoa/weight_record.h), which the wpoa-weights reader
 * applies to its own records under exactly the same rule. The rule has ONE
 * implementation on purpose: two copies of a consensus-critical predicate could drift
 * into a node discarding a record it does not accuse, or vice versa. The wrapper
 * exists so the call site reads as the membership rule it is, and so the rule's
 * meaning for this stream is documented where the stream's parsers live.
 *
 * `publishers` are the addresses recovered from the transaction's input scripts
 * (WeightStreamItem::publishers).
 *
 * @param node_address  The `node_address` from the parsed payload.
 * @param publishers    The signing addresses of the publishing transaction.
 * @return true iff the declaration is self-attested.
 */
inline bool mc_MembershipRecordIsSelfAttested(const std::string& node_address,
                                             const std::vector<std::string>& publishers)
{
    return mc_StreamItemIsSelfAttested(node_address, publishers);
}

/**
 * Parse a wpoa-esg item: {"json":{"node_address":"..","esg":n}}.
 * The ESG score must be strictly positive (Def. esg-score, ESG in R_{>0}); a
 * non-positive score is rejected so it can never enter the weight product.
 * @return true only for a non-empty address and esg > 0.
 */
inline bool mc_ParseEsgRecordJson(const json_spirit::Value& data_value,
                                  std::string& node_address, double& esg)
{
    node_address = "";
    esg = 0.0;

    json_spirit::Object inner;
    if (!mc_WeightUnwrapItemJson(data_value, inner))
    {
        return false;
    }

    std::string addr;
    double score = 0.0;
    if (!mc_WeightGetStr(inner, MC_WEIGHT_FIELD_NODE_ADDR, addr) ||
        !mc_WeightGetNum(inner, MC_WEIGHT_FIELD_ESG, score))
    {
        return false;
    }
    if (addr.empty() || score <= 0.0)
    {
        return false;
    }

    node_address = addr;
    esg = score;
    return true;
}

// ---------------------------------------------------------------------------
// Chain-derived reconciliation — the pure decision, one transaction at a time
// ---------------------------------------------------------------------------
//
// R_k^{(e)} (Def. riconciliazione) is no longer attested by anyone: it is derived from
// the confirmed transactions of a buried epoch (weight_reader.h
// ComputeActivityAndReconciliationForEpoch). The traversal needs the block/undo layer,
// but the RULE that decides what a single transaction contributes does not — so it
// lives here, pure and unit-tested, rather than buried inside the scan loop. See
// wpoa/docs/adr/reconciliation-onchain.md.

/**
 * Fold ONE transaction's reconciliation contribution into the running per-miner totals.
 *
 * @param r_raw            [in,out] miner -> reconciled value, in integer base units.
 *                         Accumulated across every transaction of the epoch, so calling
 *                         this repeatedly is how multi-transaction aggregation works.
 * @param signers          The addresses that SIGNED the transaction, resolved from undo
 *                         data — the same set that drives tau.
 * @param value_to_treasury The total value the transaction pays to the treasury address.
 * @param treasury         The treasury address ("" when none is configured).
 *
 * The rules, each with its reason:
 *
 *   * CREDITED TO THE SIGNERS, not to whoever appears in the transaction. This is what
 *     makes the DIRECTION unambiguous: a transfer TO a miner is never mistaken for one
 *     FROM it, and the treasury paying somebody creates no reconciliation for the
 *     recipient, because the recipient did not sign.
 *   * NOTHING WITHOUT A TREASURY. An unconfigured treasury yields no reconciliation at
 *     all, uniformly on every node — deterministic, and the same behaviour as the old
 *     model on a chain where nobody published reconciliation records.
 *   * NON-POSITIVE VALUE IGNORED. Covers a transaction paying the treasury nothing, and
 *     data-only outputs (OP_RETURN carries no value), so a stream item or a
 *     notarisation never registers as a reconciliation.
 *   * THE TREASURY PAYING ITSELF IS NOT A RECONCILIATION. Excluded explicitly, so a
 *     treasury-signed transaction — a refund, a rebalancing — cannot inflate any
 *     cluster's compliance, not even the treasury's own if it also happens to be a miner.
 *   * INTEGER ACCUMULATION. Base units are summed as int64 and converted to a real value
 *     once, after the whole epoch, so the total carries no floating-point rounding of
 *     its own — the sum must be bit-identical on every node.
 */
inline void mc_AccumulateReconciliation(std::map<std::string, int64_t>& r_raw,
                                        const std::set<std::string>& signers,
                                        int64_t value_to_treasury,
                                        const std::string& treasury)
{
    if (treasury.empty() || value_to_treasury <= 0 || signers.empty())
    {
        return;
    }
    for (std::set<std::string>::const_iterator it = signers.begin(); it != signers.end(); ++it)
    {
        if (*it == treasury)
        {
            continue;   // the treasury paying itself reconciles nothing
        }
        r_raw[*it] += value_to_treasury;
    }
}

/**
 * The value one transaction pays to the treasury: the sum of its outputs whose
 * destination IS the treasury address.
 *
 * Both sides of a transfer are resolved the same way — an output's destination through
 * the same address extraction the input side uses for signers — so "paid to the
 * treasury" means exactly what "signed by the miner" means, and the two halves of the
 * rule cannot drift apart.
 *
 * @param out_addresses  Per output, its destination address, or "" when the output has
 *                       no single extractable destination (OP_RETURN, bare multisig, a
 *                       non-standard script). Those never match a treasury address.
 * @param out_values     Per output, its value in integer base units. Must be the same
 *                       length as `out_addresses`; a mismatch yields 0 rather than
 *                       reading past either vector.
 * @param treasury       The treasury address ("" -> 0).
 */
inline int64_t mc_ValuePaidToTreasury(const std::vector<std::string>& out_addresses,
                                      const std::vector<int64_t>& out_values,
                                      const std::string& treasury)
{
    if (treasury.empty() || out_addresses.size() != out_values.size())
    {
        return 0;
    }
    int64_t total = 0;
    for (size_t i = 0; i < out_addresses.size(); i++)
    {
        if (out_values[i] > 0 && out_addresses[i] == treasury)
        {
            total += out_values[i];
        }
    }
    return total;
}

// ---------------------------------------------------------------------------
// Aggregation — fold parsed records into the pipeline's in-memory structures.
//
// Every accumulator here folds a chain-ordered (oldest -> newest) item list; the
// newest record for a key wins, mirroring mc_AccumulateLatestWeight in
// wpoa/weight_record.h. Membership included: since a node may change cluster at
// will, its latest confirmed declaration is the only one that counts.
// ---------------------------------------------------------------------------

/**
 * declaring node -> the cluster it currently belongs to. LAST CONFIRMED WINS: the
 * caller folds the chain-ordered item list (oldest -> newest), so a node that
 * republishes with a different miner_address simply overwrites its own entry and
 * its earlier cluster is forgotten.
 *
 * This replaces the old additive mc_AccumulateMembership: membership is no longer
 * a monotonically growing set per miner but a MUTABLE single-valued relation per
 * declaring node, which is what makes an autonomous cluster change expressible.
 */
inline void mc_AccumulateLatestMembership(std::map<std::string, std::string>& node_to_miner,
                                          const std::string& node_address,
                                          const std::string& miner_address)
{
    node_to_miner[node_address] = miner_address;
}

/**
 * Invert the node -> miner relation into the cluster sets C_k the pipeline consumes:
 * miner address -> the set of its member COMPANY addresses.
 *
 * Two rules, both deliberate:
 *
 *   1. A miner key exists in the output as soon as ANY node declares that miner,
 *      including the miner declaring itself. A miner's own self-declaration is
 *      therefore what registers it as a cluster head (which is what
 *      ComputeLocalWeightForEpoch tests before publishing a weight), even when no
 *      company has joined yet — in which case C_k is legitimately empty.
 *
 *   2. A miner is NEVER listed among its own companies. Its activity already enters
 *      the raw weight through the separate tau_Mk term of
 *      W_k = ESG_Mk * ( tau_Mk + sum_{i in C_k} c_i ), so also counting it as a
 *      company i would double-count it.
 *
 * @param node_to_miner  The folded latest declaration per node.
 * @param clusters       Out: miner -> C_k (cleared first).
 */
inline void mc_BuildClustersFromMembership(const std::map<std::string, std::string>& node_to_miner,
                                           std::map<std::string, std::set<std::string> >& clusters)
{
    clusters.clear();
    for (std::map<std::string, std::string>::const_iterator it = node_to_miner.begin();
         it != node_to_miner.end(); ++it)
    {
        const std::string& node  = it->first;
        const std::string& miner = it->second;

        std::set<std::string>& members = clusters[miner];   // registers the cluster head
        if (node != miner)                                  // rule 2: no self-membership
        {
            members.insert(node);
        }
    }
}

/** address -> latest certified ESG score. */
inline void mc_AccumulateLatestEsg(std::map<std::string, double>& latest,
                                   const std::string& node_address, double esg)
{
    latest[node_address] = esg;
}

#endif // MC_WEIGHT_RECORDS_H
