// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W3: input-stream reader (node-coupled glue).
// ------------------------------------------------------------------------------
// WeightStreamReader owns the four public INPUT streams the WeightEngine consumes
// each epoch — membership, ESG, activity, reconciliation (names in
// weight_streams.h) — and turns their confirmed on-chain items into the in-memory
// structures the pure core (weight_engine.h) folds into w_k:
//
//   membership     -> C_k        : miner address -> set of company addresses
//   esg            -> ESG        : node address  -> latest certified score
//   activity       -> tau[e]     : epoch -> (node address -> tau)
//   reconciliation -> R[e]       : epoch -> (miner address -> reconciled amount)
//
// STREAM LIFECYCLE (automatic, no operator action). Like the wpoa-weights stream
// (StreamWeightRegistry), the reader CREATES the four streams when missing and
// SUBSCRIBES to them — so the first node with create permission (the genesis /
// admin node, on its first run) brings them into existence, and every other node
// simply finds them already present and subscribes. EnsureInputStreams() is the
// single "check + create + subscribe" entry point, called from ThreadWeightEngine
// before every read, mirroring RegisterLocalWeight's EnsureStreamExists path.
//
// THREADING. Every read uses the low-level, self-locking, NON-WRP wallet API
// (mc_WalletTxs FindEntity/GetListSize/GetList/GetWalletTx) — never the WRP* /
// getstreamkeysummary family, which would hand a background thread a stale (0-item)
// snapshot (see the long note in stream_weight_registry.cpp ReadAllRecords). Only
// CONFIRMED items are read, so every honest node observes the same input set.

#ifndef MC_WEIGHT_READER_H
#define MC_WEIGHT_READER_H

#include <map>
#include <set>
#include <string>
#include <vector>
#include <stdint.h>

#include "json/json_spirit_value.h"

struct mc_WalletTxs;
struct mc_EntityDetails;

/** One decoded confirmed stream item: its key(s) and its JSON payload value.
 *  A MultiChain item may carry several keys; the WeightEngine streams use a single
 *  key per item (the miner/node address), so keys[0] is the item key. */
struct WeightStreamItem
{
    std::vector<std::string> keys;
    json_spirit::Value       value;   // the {"json":{...}} payload (as OpReturnFormatEntry returns)
};

/**
 * WeightStreamReader — off-thread reader/creator for the four WeightEngine input
 * streams. Reads degrade gracefully: a missing or not-yet-subscribed stream, or a
 * stream with no confirmed items, yields an empty result rather than an error, so
 * the caller can simply retry on the next epoch tick.
 */
class WeightStreamReader
{
public:
    explicit WeightStreamReader(mc_WalletTxs* pwalletIn);

    /**
     * Ensure all four input streams exist (create the missing ones — one create tx
     * each, only on the node that has create permission) and that this node is
     * subscribed to them. Returns true only when all four are present AND subscribed
     * (i.e. reads can succeed); false while any create/subscribe is still pending.
     * Safe to call repeatedly from the retry loop.
     */
    bool EnsureInputStreams();

    /** membership -> C_k : miner address -> set of its company addresses. */
    bool ReadMembership(std::map<std::string, std::set<std::string> >& clusters);

    /** esg -> node address -> latest certified ESG score (newest confirmed wins). */
    bool ReadEsg(std::map<std::string, double>& esg);

    /** activity -> epoch -> (node address -> latest tau for that epoch). */
    bool ReadActivityByEpoch(std::map<uint32_t, std::map<std::string, uint32_t> >& tau_by_epoch);

    /** reconciliation -> epoch -> (miner address -> latest reconciled R for that epoch). */
    bool ReadReconciliationByEpoch(std::map<uint32_t, std::map<std::string, double> >& r_by_epoch);

private:
    mc_WalletTxs* m_pWalletTxs;   //!< borrowed pointer, not owned

    /** One managed input stream: its name and the once-only create/subscribe guards
     *  (mirrors StreamWeightRegistry::m_CreateAttempted / m_SubscribeAttempted). */
    struct InputStream
    {
        std::string name;
        bool        create_attempted;
        bool        subscribe_attempted;
        InputStream() : create_attempted(false), subscribe_attempted(false) {}
    };
    InputStream m_Streams[4];     //!< membership, esg, activity, reconciliation

    bool GetStreamEntity(const std::string& name, mc_EntityDetails* entity);
    bool EnsureOneStream(InputStream& s);   // create-if-missing + subscribe, one stream
    bool ReadStreamItems(const std::string& name, std::vector<WeightStreamItem>& out);
};

#endif // MC_WEIGHT_READER_H
