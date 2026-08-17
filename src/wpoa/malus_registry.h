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
// Two report kinds are recognised, and only two, because they are exactly the
// misbehaviours a node can already prove while validating a block:
//
//   equiv  the accused signed two DISTINCT blocks at one height over the same
//          beacon seed. VRF uniqueness makes that impossible by accident, so the
//          mere coexistence of the two blocks is proof (Def. 5.18).
//   delay  the accused published a block whose VRF proof is valid but whose
//          timestamp precedes the delay its own sortition score entitled it to
//          (Def. 5.19). The attempt is the violation, whether or not it was
//          accepted anywhere.
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
                              int height, const std::vector<std::string>& blocks);

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
    };

    /** Every confirmed, well-formed report, oldest first. */
    bool ReadAllReports(std::vector<Report>& out);
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
