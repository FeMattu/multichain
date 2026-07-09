// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA (Weighted Proof of Authority) — Phase 1: Weight Registry
// -------------------------------------------------------------
// Stores per-validator weights on an append-only MultiChain stream
// ("wpoa-weights") and exposes a small, opaque API to read the local
// and global weights. Nodes never touch the internal mechanism, only
// the public methods below.
//
// See src/wpoa/README.md for the design, data model and manual test steps.

#ifndef STREAM_WEIGHT_REGISTRY_H
#define STREAM_WEIGHT_REGISTRY_H

#include <map>
#include <string>
#include <stdint.h>

#include "json/json_spirit_value.h"

struct mc_WalletTxs;
struct mc_EntityDetails;

/** Name of the append-only stream that holds the weight records. */
#define MC_WPOA_WEIGHTS_STREAM_NAME     "wpoa-weights"
/** Default weight used when -weight is not supplied on the command line. */
#define MC_WPOA_DEFAULT_WEIGHT          100

/**
 * StreamWeightRegistry
 *
 * Thin, opaque facade over the "wpoa-weights" MultiChain stream.
 *
 * Reads are implemented with the low-level, self-locking wallet read API
 * (mc_WalletTxs GetListSize / GetList / GetWalletTx, which lock the wallet-txs DB
 * internally), so every read method is safe to call from ANY thread and always
 * observes the live confirmed state. We deliberately do NOT use the WRP* read
 * family: those return positions from a snapshot that is only valid inside the
 * RPC read-lock protocol, so an off-thread reader would see a stale (0-item) view.
 * Writes reuse MultiChain's in-process RPC handlers (create / subscribe / publish),
 * which build and broadcast real transactions.
 *
 * Because a published record is only visible once its transaction is mined and
 * imported into the local subscription, the read methods degrade gracefully:
 * they return 0 / an empty map until the data is confirmed, never throwing.
 */
class StreamWeightRegistry
{
public:
    /** Resolves the local node address and caches the stream name. */
    StreamWeightRegistry(mc_WalletTxs* pwalletIn);
    ~StreamWeightRegistry();

    /**
     * Registers the current node's weight on the stream.
     * Ensures the stream exists and that this node is subscribed, then, if the
     * weight is not already the latest confirmed value for this node, publishes
     * a new record. Returns true when the record is (or already was) in place,
     * false while prerequisites are still pending (e.g. the create tx has not
     * confirmed yet) or on error. Safe to call repeatedly / from a retry loop.
     */
    bool RegisterLocalWeight(uint32_t weight);

    /** Latest confirmed weight for this node, or 0 if not yet registered. */
    uint32_t GetLocalWeight();

    /** address -> latest confirmed weight, for every validator on the stream. */
    std::map<std::string, uint32_t> GetAllNodesWeights();

    /** Latest confirmed weight for a specific address, or 0 if not found. */
    uint32_t GetNodeWeight(const std::string& node_address);

    /** True if this node has at least one confirmed weight record. */
    bool IsLocalWeightRegistered();

    /** Logs the full registry state in the format documented in the spec. */
    void DebugPrintWeights();

    /**
     * Block until this node's confirmed weight equals `weight` (i.e. the publish
     * transaction has been mined and imported into the subscription), or until
     * `max_attempts` polls of `interval_ms` each have elapsed, or shutdown is
     * requested. Returns true if confirmed. Used by the deferred thread so the
     * debug dump reflects the committed state rather than the pending mempool tx.
     */
    bool WaitForLocalWeight(uint32_t weight, int max_attempts, int interval_ms);

    /** The resolved local node address (mine/connect/default key). */
    std::string GetLocalAddress() const { return m_LocalAddress; }

private:
    mc_WalletTxs* m_pWalletTxs;   //!< borrowed pointer, not owned
    std::string   m_StreamName;   //!< "wpoa-weights"
    std::string   m_LocalAddress; //!< cached node address

    bool m_CreateAttempted;       //!< guards against issuing >1 create tx
    bool m_SubscribeAttempted;    //!< guards against redundant subscribe calls

    void ResolveLocalAddress();
    bool GetStreamEntity(mc_EntityDetails* entity);
    bool EnsureStreamExists();
    bool EnsureSubscribed();
    bool PublishWeightRecord(uint32_t weight);
    bool ReadAllRecords(std::map<std::string, uint32_t>& out_latest);
};

/**
 * Deferred registration entry point. Launched as a background thread from
 * AppInit2. Waits until the node is ready (chain tip present and, unless
 * -offline, the initial block download finished) and then registers the node
 * weight, retrying until it succeeds or a bounded number of attempts elapse.
 */
void ThreadRegisterNodeWeight(uint32_t weight);

/** Node weight parsed from -weight in AppInit2 (defaults to MC_WPOA_DEFAULT_WEIGHT). */
extern uint32_t g_node_weight;

/* --- RPC commands (registered in src/rpc/rpclist.cpp) --- */
json_spirit::Value getlocalweight(const json_spirit::Array& params, bool fHelp);
json_spirit::Value getallweights(const json_spirit::Array& params, bool fHelp);
json_spirit::Value getnodeweight(const json_spirit::Array& params, bool fHelp);

#endif // STREAM_WEIGHT_REGISTRY_H
