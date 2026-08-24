// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA — behavioural malus registry (node glue).
// -----------------------------------------------------------------------------
// The second of the two registries the protocol maintains, and the deliberate
// mirror image of the first (Def. 5.17):
//
//   wpoa-weights        CLOSED  — only authorized publishers may write a weight
//   wpoa-weights-malus  OPEN    — ANYONE may publish a misbehaviour report
//
// The asymmetry is the point. Trust is not placed in the reporter's identity but
// in the cryptographic verifiability of what is reported: every node re-derives
// the predicate Valid(e) (Def. 5.20) from public chain data alone, so a false,
// malformed or duplicated report is discarded identically everywhere and cannot
// move any validator's weight (Prop. 5.15, local decidability). Opening the
// stream therefore costs nothing in safety while removing the need for a
// privileged accuser — the control stays decentralized.
//
// FOUR report kinds, in TWO families. Both families satisfy the same requirement — the
// proof must be re-derivable from public chain data — and differ only in what the
// evidence is and what the offence damages.
//
// CONSENSUS-BEHAVIOURAL: how a validator behaved while PRODUCING a block. Evidence: the
// block, and the VRF reveal it carries.
//   equiv      the accused signed two DISTINCT blocks at one height over the same
//              beacon seed. VRF uniqueness makes that impossible by accident, so the
//              mere coexistence of the two blocks is proof (Def. 5.18).
//   delay      the accused published a block whose VRF proof is valid but whose
//              timestamp precedes the delay its own sortition score entitled it to
//              (Def. 5.19). The attempt is the violation, whether or not it was
//              accepted anywhere.
//
// PUBLISHED-DATA INTEGRITY: what a node WROTE to a stream the weight pipeline reads.
// Evidence: the publishing transaction, its signature and its payload. These attack the
// INPUTS of the election rather than its execution.
//   selfwrite  the accused published a record on a SELF-ATTESTED stream naming a
//              node_address other than its own signing address. Readers already discard
//              such a record, so it gains nothing — which is precisely why the attempt
//              needs a price, as with `delay`.
//   badweight  the accused published on wpoa-weights a value that does not survive
//              independent recomputation from the public pipeline inputs. Unlike
//              selfwrite this one SUCCEEDS unless somebody recomputes it, so it is the
//              offence with the most direct effect on proposer probability.
//
// The second family exists because the weight inputs became self-verifiable: a forged
// membership record or a false weight is now PROVABLY wrong, and anything provable can
// carry a malus on exactly the same terms as an equivocation.
//
// The accumulated, decayed severity M_i is turned into the correction factor
// Psi_i and applied DOWNSTREAM of the raw weight, w_eff = w * Psi (Def. 5.22).
// Neither the weight-management layer nor the wpoa-weights stream is touched.
//
// EPOCH ALIGNMENT. M and Psi are per-epoch quantities on the same height->epoch
// map the weight layer uses (Def. 5.21 refers to it explicitly). Heights in epoch
// e are governed by Psi^(e-1), i.e. a malus takes effect from the epoch AFTER the
// one in which it was proved — the same inter-epoch feedback shape the weight
// recursion uses (Def. 6.9, where rho^(e-1) drives w^(e)). Besides matching the
// weight layer, this keeps the definition acyclic: validating a delay report from
// epoch e needs the delay the block validator actually enforced, which is derived
// from Psi^(e-1); resolving it against Psi^(e) would make the epoch's own reports
// depend on themselves.
//
// The pure half — record parsing, the accumulator fold, Psi, w_eff, the
// clearing-time bound — lives in malus_record.h and is unit-tested node-free.
// This header holds only what needs the running node.

#ifndef MC_WPOA_MALUS_REGISTRY_H
#define MC_WPOA_MALUS_REGISTRY_H

#include <map>
#include <string>
#include <vector>
#include <stdint.h>

#include "json/json_spirit_value.h"
#include "wpoa/malus_record.h"

struct mc_WalletTxs;
struct mc_EntityDetails;

/** Name of the open, append-only stream that holds the misbehaviour reports. */
#define MC_WPOA_MALUS_STREAM_NAME        "wpoa-weights-malus"

/** mu in [0,1): how much of M^(e-1) is carried into M^(e) (Def. 5.21). */
#define MC_WPOA_DEFAULT_MALUS_MU         0.5

/** M_max > 0: the accumulator value at which Psi reaches 0 (Def. 5.22). */
#define MC_WPOA_DEFAULT_MALUS_MAX        4.0

/** p(Equiv): score of one proved equivocation — a safety fault. */
#define MC_WPOA_DEFAULT_MALUS_P_EQUIV    4.0

/** p(Delay): score of one proved delay violation — a scheduling fault only.
 *  Kept far below p(Equiv) by the protocol constraint p(Equiv) >> p(Delay). */
#define MC_WPOA_DEFAULT_MALUS_P_DELAY    0.25

/** p(SelfWrite): score of one proved attempt to publish a self-attested record on
 *  another address's behalf. The record is always discarded, so the offence damages
 *  nothing directly — the score prices the ATTEMPT, exactly as p(Delay) prices an
 *  attempt block validation already rejects. Set above p(Delay) because a forged
 *  signature claim is unambiguous intent, where an early timestamp can be a clock. */
#define MC_WPOA_DEFAULT_MALUS_P_SELFWRITE 1.0

/** p(BadWeight): score of one weight published on wpoa-weights that fails independent
 *  recomputation. The heaviest of the data-integrity pair, and the constraint
 *  p(BadWeight) > p(SelfWrite) is enforced at startup: unlike a forgery, a false weight
 *  SUCCEEDS unless somebody recomputes it, and then distorts proposer probability for
 *  every round of the epoch. Still below p(Equiv), which threatens safety itself. */
#define MC_WPOA_DEFAULT_MALUS_P_BADWEIGHT 2.0

/**
 * MalusRegistry
 *
 * Opaque facade over the "wpoa-weights-malus" stream, built to the same shape as
 * StreamWeightRegistry: reads go through the low-level, self-locking wallet API
 * (so they are safe from any thread and always observe the live CONFIRMED state),
 * writes reuse MultiChain's in-process RPC handlers.
 *
 * Reads degrade gracefully — an absent stream, an unsubscribed node or a
 * not-yet-confirmed report yields an empty map rather than an exception — so a
 * chain that never enables the mechanism behaves exactly as before.
 */
class MalusRegistry
{
public:
    /** Caches the stream name; borrows (does not own) the wallet-tx store. */
    MalusRegistry(mc_WalletTxs* pwalletIn);
    ~MalusRegistry();

    /**
     * Ensures the stream exists (creating it OPEN on the first node with create
     * permission) and that this node is subscribed. Returns true once both hold;
     * false while a create/subscribe transaction is still confirming.
     */
    bool EnsureStream();

    /**
     * address -> M^(epoch) for every validator carrying accumulated malus at
     * `epoch`, folding forward from epoch 1 over the CONFIRMED reports that pass
     * Valid(e). Addresses with no valid report are simply absent.
     *
     * Returns false when the stream is unavailable (not created / not subscribed),
     * leaving `out` empty — callers then apply no correction at all.
     */
    bool GetAccumulators(uint32_t epoch, std::map<std::string, double>& out);

    /** Convenience: M^(epoch) for one address (0 when absent or unavailable). */
    double GetAccumulator(const std::string& address, uint32_t epoch);

    /**
     * Publishes a misbehaviour report. The record is verified locally BEFORE it is
     * broadcast, so this node never spends a transaction on evidence its own peers
     * would discard.
     *
     * @return the publish txid; throws a JSONRPCError on a failed local check.
     */
    std::string PublishReport(MalusKind kind, const std::string& node_address,
                              int height, const std::vector<std::string>& blocks,
                              const MalusDataDetail& detail = MalusDataDetail());

    /**
     * The Valid(e) predicate of Def. 5.20, exposed for the report RPC and the
     * unit-testable verification path: re-derives the accusation from public chain
     * data and returns true only if it holds.
     *
     * @param psi_prev  Psi^(e-1) for the accused, i.e. the correction that was in
     *                  force at `height` — needed to reproduce the delay the block
     *                  validator actually enforced (MALUS_DELAY only).
     * @param reason_out [out, optional] why the record was rejected.
     */
    bool ValidReport(MalusKind kind, const std::string& node_address, int height,
                     const std::vector<std::string>& blocks, double psi_prev,
                     std::string* reason_out)
    {
        return ValidReport(kind, node_address, height, blocks, MalusDataDetail(),
                           psi_prev, reason_out);
    }

    /**
     * Full form, carrying the extra payload the data-integrity kinds need.
     *
     * `detail` is treated as a CLAIM, never as evidence: every field is re-checked
     * against the referenced transaction, and a mismatch invalidates the report. It
     * exists so a third party can audit an accusation by reading one transaction rather
     * than searching for it.
     */
    bool ValidReport(MalusKind kind, const std::string& node_address, int height,
                     const std::vector<std::string>& blocks,
                     const MalusDataDetail& detail, double psi_prev,
                     std::string* reason_out);

private:
    mc_WalletTxs* m_pWalletTxs;   //!< borrowed pointer, not owned
    std::string   m_StreamName;   //!< "wpoa-weights-malus"

    bool m_CreateAttempted;       //!< guards against issuing >1 create tx
    bool m_SubscribeAttempted;    //!< guards against redundant subscribe calls

    bool GetStreamEntity(mc_EntityDetails* entity);
    bool EnsureStreamExists();
    bool EnsureSubscribed();

    /** One parsed, chain-ordered report as read off the stream. */
    struct Report
    {
        MalusKind                kind;
        std::string              address;
        int                      height;
        std::vector<std::string> blocks;
        MalusDataDetail          detail;   //!< data-integrity kinds only
    };

    /** Every confirmed, well-formed report, oldest first. */
    bool ReadAllReports(std::vector<Report>& out);

    /**
     * Valid(e) for the PUBLISHED-DATA INTEGRITY kinds, whose evidence is a publishing
     * transaction rather than a block.
     *
     * Verification is deliberately mechanical, with no judgement anywhere in it: read
     * the referenced transaction, decode its signer and its payload, and confirm the
     * discrepancy the report alleges. For `badweight` it additionally re-runs the weight
     * pipeline over the epoch's public inputs — the same computation the accuser ran, and
     * the same one every other node can run.
     */
    bool ValidDataIntegrityReport(MalusKind kind, const std::string& node_address,
                                  int height, const std::vector<std::string>& blocks,
                                  const MalusDataDetail& detail,
                                  std::string* reason_out);
};

// ---------------------------------------------------------------------------
// Runtime configuration (defined in malus_registry.cpp; bound to the chain
// parameters / runtime flags in AppInit2, exactly like the other wPoA globals).
// CONSENSUS-CRITICAL: every honest node MUST hold identical values, or they
// compute different effective weights and disagree on the elected proposer.
// ---------------------------------------------------------------------------

/** -enablewpoamalus: run the malus registry and apply w_eff = w * Psi. Default
 *  off, in which case the sortition consumes the raw registry weight unchanged. */
extern bool g_wpoa_malus_enabled;

/** -wpoamalusmu: accumulator persistence mu in [0,1) (Def. 5.21). */
extern double g_wpoa_malus_mu;

/** -wpoamalusmax: exclusion threshold M_max > 0 (Def. 5.22). */
extern double g_wpoa_malus_max;

/** -wpoamalusequivpoints: p(Equiv) > 0 (Def. 5.21). */
extern double g_wpoa_malus_p_equiv;

/** -wpoamalusdelaypoints: p(Delay) > 0, with p(Equiv) >> p(Delay). */
extern double g_wpoa_malus_p_delay;

/** -wpoamalusselfwritepoints: p(SelfWrite) > 0 — a discarded forgery attempt. */
extern double g_wpoa_malus_p_selfwrite;

/** -wpoamalusbadweightpoints: p(BadWeight) > 0, with p(BadWeight) > p(SelfWrite). */
extern double g_wpoa_malus_p_badweight;

/** The four scores as one struct, for MalusAccumulator::Points. */
MalusScores WPoAMalusScores();

/**
 * True when the malus correction governs the weights at `height`: the mechanism
 * is enabled and wPoA already governs the height. A pure function of shared data
 * (flags + chain params + height), in the style of WPoAActiveAtHeight, so the
 * miner and every validator agree from the height alone.
 */
bool WPoAMalusActiveAtHeight(int height);

/**
 * Apply the behavioural correction to a raw weight map: w -> w * Psi^(e-1), where
 * e is the epoch of `height` (Def. 5.22).
 *
 * This is the ONE place the malus enters the consensus path; both the public
 * selector and the private sortition call it on the map they read from
 * wpoa-weights, so miner and validator always score the same numbers. Returns
 * `weights` unchanged when the mechanism is inactive, the stream is unavailable
 * or no validator carries any malus — so enabling the registry on a clean chain
 * is a no-op.
 */
std::map<std::string, uint32_t> WPoAApplyMalus(const std::map<std::string, uint32_t>& weights,
                                               int height);

/**
 * Background entry point launched from AppInit2 when the malus registry is
 * enabled: ensures the stream exists (creating it OPEN on the first node with
 * create permission) and that this node is subscribed, then exits.
 */
void ThreadMalusRegistry();

/* --- RPC commands (registered in src/rpc/rpclist.cpp) --- */
json_spirit::Value getallmalus(const json_spirit::Array& params, bool fHelp);
json_spirit::Value getnodemalus(const json_spirit::Array& params, bool fHelp);
json_spirit::Value reportmalus(const json_spirit::Array& params, bool fHelp);

#endif // MC_WPOA_MALUS_REGISTRY_H
