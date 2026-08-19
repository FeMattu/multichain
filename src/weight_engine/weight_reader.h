// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W3: input-stream reader (node-coupled glue).
// ------------------------------------------------------------------------------
// WeightStreamReader owns the public INPUT streams the WeightEngine consumes each
// epoch and turns their confirmed on-chain items into the in-memory structures the
// pure core (weight_engine.h) folds into w_k:
//
//   membership     -> C_k : miner address -> set of company addresses   (admin)
//   esg            -> ESG : node address  -> latest certified score      (admin)
//   reconciliation -> R[e]: epoch -> (miner address -> reconciled R)      (admin)
//
// ACTIVITY IS NOT A STREAM. tau_i^{(e)} (the per-epoch activity counter) is derived
// DIRECTLY from the chain by ComputeActivityForEpoch() — it is a deterministic
// function of the confirmed blocks of the epoch, so every honest node recomputes
// the identical value with no publisher and no duplicate-write risk. See the long
// determinism contract on ComputeActivityForEpoch below.
//
// STREAM LIFECYCLE. Like wpoa-weights, the reader CREATES the (now CLOSED) input
// streams when missing and SUBSCRIBES to them — the first node with create
// permission (the genesis / admin node) brings them into existence, everyone else
// finds them present and subscribes. The streams are CLOSED (MC_PTP_WRITE required)
// so only write-permitted addresses can publish. The WeightPublisher admin RPCs are
// the sanctioned, schema-validating write path; operators must grant `.write` on
// these streams ONLY to admin/governance addresses (see the SECURITY MODEL note in
// weight_publisher.h). The reader accepts any schema-valid confirmed record.
//
// THREADING. Every read uses the low-level, self-locking, NON-WRP wallet API and
// only CONFIRMED items, never the WRP*/getstreamkeysummary family (stale off-thread;
// see stream_weight_registry.cpp ReadAllRecords). ComputeActivityForEpoch reads the
// block/undo files off-thread, taking cs_main only for a tiny chain snapshot.

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
 *  The WeightEngine streams use a single key per item (the miner/node address),
 *  so keys[0] is the item key. */
struct WeightStreamItem
{
    std::vector<std::string> keys;
    json_spirit::Value       value;   // the {"json":{...}} payload (as OpReturnFormatEntry returns)
};

/**
 * WeightStreamReader — off-thread reader/creator for the WeightEngine input
 * streams, plus the chain-derived activity metric. Reads degrade gracefully: a
 * missing / not-yet-subscribed stream, or a stream with no confirmed items, yields
 * an empty result rather than an error, so the caller can retry on the next tick.
 */
class WeightStreamReader
{
public:
    explicit WeightStreamReader(mc_WalletTxs* pwalletIn);

    /**
     * Ensure the three input streams exist (create the missing ones CLOSED — one
     * create tx each, only on a node with create permission) and that this node is
     * subscribed. Returns true only when all three are present AND subscribed.
     * Safe to call repeatedly from the retry loop.
     */
    bool EnsureInputStreams();

    /** membership -> C_k : miner address -> set of its company addresses. */
    bool ReadMembership(std::map<std::string, std::set<std::string> >& clusters);

    /** esg -> node address -> latest certified ESG score (newest confirmed wins). */
    bool ReadEsg(std::map<std::string, double>& esg);

    /** reconciliation -> epoch -> (miner address -> latest reconciled R for that epoch). */
    bool ReadReconciliationByEpoch(std::map<uint32_t, std::map<std::string, double> >& r_by_epoch);

    /**
     * CHAIN-DERIVED ACTIVITY (no stream, no publisher). Computes, for the given
     * 1-based epoch, tau(address) = the number of CONFIRMED transactions in the
     * epoch's block-height range whose inputs were signed by `address` (i.e. that
     * spent an output owned by `address`).
     *
     * CONSENSUS-CRITICAL DETERMINISM — this feeds w_k, so every honest node must
     * return the bit-identical map. Guarantees (verified against the block/undo
     * layer):
     *   * height range [ (epoch-1)*len , epoch*len - 1 ], len = g_weight_epoch_length;
     *     epoch < 1 or len < 1 -> return false (never a silent default).
     *   * ONLY computed for a BURIED epoch: returns false unless the range's last
     *     height is <= tip - MC_WEIGHT_DEFAULT_STABILITY_MARGIN, so a shallow reorg
     *     near the tip cannot change the answer. The range is snapshotted as one
     *     self-consistent pprev ancestor chain under a single short cs_main lock.
     *   * prevout owner resolved from block UNDO data (rev*.dat, present on every
     *     non-pruned node) -> NO dependence on -txindex.
     *   * coinbase tx skipped; a tx with several inputs from the same address counts
     *     once for it (set-dedup); a tx spanning several addresses counts once for
     *     each; non-standard / bare-multisig prevouts (address-extract yields 0)
     *     count for nobody. Address string is the canonical CBitcoinAddress form.
     *   * returns false (never a partial map) if any buried block lacks data/undo
     *     (e.g. a pruned node) — the caller then simply does not publish.
     */
    bool ComputeActivityForEpoch(uint32_t epoch, std::map<std::string, uint32_t>& tau);

private:
    mc_WalletTxs* m_pWalletTxs;   //!< borrowed pointer, not owned

    /** One managed input stream: its name and the once-only create/subscribe guards. */
    struct InputStream
    {
        std::string name;
        bool        create_attempted;
        bool        subscribe_attempted;
        InputStream() : create_attempted(false), subscribe_attempted(false) {}
    };
    InputStream m_Streams[3];     //!< membership, esg, reconciliation

    bool GetStreamEntity(const std::string& name, mc_EntityDetails* entity);
    bool EnsureOneStream(InputStream& s);   // create-if-missing (CLOSED) + subscribe, one stream
    bool ReadStreamItems(const std::string& name, std::vector<WeightStreamItem>& out);
};

#endif // MC_WEIGHT_READER_H
