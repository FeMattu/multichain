// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W3: input-stream reader (node-coupled glue).
// ------------------------------------------------------------------------------
// WeightStreamReader owns the public INPUT streams the WeightEngine consumes each
// epoch and turns their confirmed on-chain items into the in-memory structures the
// pure core (weight_engine.h) folds into w_k.
//
// TWO PUBLISHED STREAMS, TWO CHAIN-DERIVED QUANTITIES:
//
//   membership -> C_k : miner address -> set of company addresses  (self-attested,
//                       published by each node about itself)
//   esg        -> ESG : node address  -> latest certified score     (published by a
//                       Certification Authority)
//   ---- derived, never published, no writer at all ----
//   tau[e]     -> address -> activity counter for the epoch          (Def. 6.3)
//   R[e]       -> miner   -> currency reconciled to the treasury     (Def. 6.7)
//
// tau AND R ARE BOTH DERIVED FROM THE BLOCKS, in a single shared pass
// (ComputeActivityAndReconciliationForEpoch). Both are facts about the confirmed
// transactions of one epoch, so neither needs a publisher and neither can be
// misstated: there is nothing to trust and no duplicate-write risk. R used to be an
// administrator attestation on a dedicated stream — the asymmetry that treated one
// transaction fact as derived and the other as declared. See
// wpoa/docs/adr/reconciliation-onchain.md for the decision and its consequences.
//
// (`weight-engine-activity` never existed as a mechanism either: the name was defined
// but no code ever created, wrote or read it. It has been removed.)
//
// STREAM LIFECYCLE. Like wpoa-weights, the reader CREATES the (CLOSED) input streams
// when missing and SUBSCRIBES to them — the first node with create permission (the
// genesis / admin node) brings them into existence, everyone else finds them present
// and subscribes. CLOSED means MC_PTP_WRITE is required to publish, but WHO holds it
// differs per stream: membership.write is meant for every node (its records are
// self-attested, so the permission grants nothing beyond speaking about oneself),
// esg.write only for delegated Certification Authorities. See the SECURITY MODEL note
// in weight_publisher.h. Membership records are additionally validated against the
// transaction signature; ESG records are accepted on any schema-valid confirmed item.
//
// THREADING. Every read uses the low-level, self-locking, NON-WRP wallet API and
// only CONFIRMED items, never the WRP*/getstreamkeysummary family (stale off-thread;
// see stream_weight_registry.cpp ReadAllRecords).
// ComputeActivityAndReconciliationForEpoch reads the block/undo files off-thread,
// taking cs_main only for a tiny chain snapshot.

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

/** One decoded confirmed stream item: its key(s), its publisher(s) and its JSON
 *  payload value. The WeightEngine streams use a single key per item (the
 *  miner/node address), so keys[0] is the item key.
 *
 *  `publishers` are the addresses that SIGNED the publishing transaction, decoded
 *  from its input scripts exactly as MultiChain's own StreamItemEntry does (see
 *  rpc/rpcwalletutils.cpp). They are the cryptographic identity of the writer — a
 *  payload field can claim anything, an input signature cannot — and are what the
 *  self-attestation rule of the membership stream is checked against. Normally a
 *  single address; a tx funded from several addresses yields several. */
struct WeightStreamItem
{
    std::vector<std::string> keys;
    std::vector<std::string> publishers;
    json_spirit::Value       value;   // the {"json":{...}} payload (as OpReturnFormatEntry returns)

    /** True iff `address` signed this item's transaction. */
    bool IsPublishedBy(const std::string& address) const
    {
        for (size_t i = 0; i < publishers.size(); i++)
        {
            if (publishers[i] == address)
            {
                return true;
            }
        }
        return false;
    }
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
     * Ensure the two published input streams exist (create the missing ones CLOSED —
     * one create tx each, only on a node with create permission) and that this node is
     * subscribed. Returns true only when both are present AND subscribed. Safe to call
     * repeatedly from the retry loop.
     */
    bool EnsureInputStreams();

    /**
     * membership -> C_k : miner address -> set of its member company addresses.
     *
     * SELF-ATTESTATION IS ENFORCED HERE (consensus-critical). For every confirmed
     * item, the payload's `node_address` is compared against the addresses that
     * actually SIGNED the publishing transaction. A mismatch means one node tried to
     * declare membership on another's behalf: the record is DISCARDED outright — it
     * does not enter C_k and produces no side effect of any kind. Only the signer's
     * own declaration counts, which is what makes it safe to grant
     * `weight-engine-membership.write` to every node on the network.
     *
     * Surviving records fold last-confirmed-wins per declaring node, then invert
     * into the cluster sets (mc_BuildClustersFromMembership): a node that
     * republishes with a different miner_address changes cluster autonomously, and
     * its previous membership disappears.
     */
    bool ReadMembership(std::map<std::string, std::set<std::string> >& clusters);

    /** esg -> node address -> latest certified ESG score (newest confirmed wins). */
    bool ReadEsg(std::map<std::string, double>& esg);

    /**
     * CHAIN-DERIVED ACTIVITY AND RECONCILIATION, in ONE pass (no stream, no publisher).
     *
     * Both quantities are facts about the confirmed transactions of a single epoch, and
     * both need the same traversal and the same per-transaction information — the set of
     * signing addresses, resolved from undo data. They are therefore computed together
     * rather than by two scans of the same blocks: the marginal cost of reconciliation is
     * a few comparisons per output. See
     * [docs/adr/reconciliation-onchain.md](../wpoa/docs/adr/reconciliation-onchain.md).
     *
     *   tau(address) = the number of CONFIRMED transactions in the epoch whose inputs
     *                  were signed by `address` (Def. 6.3).
     *   R(miner)     = the total native-currency value paid to the TREASURY address by
     *                  transactions `miner` signed, in the same epoch (Def. 6.7).
     *
     * R replaces an administrator attestation with a derivation: nobody declares how much
     * a miner reconciled, it is read off the blocks that recorded the transfers. When no
     * treasury address is configured (g_weight_treasury_address empty) R is uniformly
     * empty, which is deterministic and matches the old behaviour on a chain where nobody
     * published reconciliation records.
     *
     * CONSENSUS-CRITICAL DETERMINISM — these feed w_k, so every honest node must return
     * bit-identical maps. Guarantees (verified against the block/undo layer):
     *   * height range [ (epoch-1)*len , epoch*len - 1 ], len = g_weight_epoch_length;
     *     epoch < 1 or len < 1 -> return false (never a silent default).
     *   * ONLY computed for a BURIED epoch: returns false unless the range's last
     *     height is <= tip - MC_WEIGHT_DEFAULT_STABILITY_MARGIN, so a shallow reorg
     *     near the tip cannot change the answer — the same margin, for the same reason,
     *     for both quantities. The range is snapshotted as one self-consistent pprev
     *     ancestor chain under a single short cs_main lock.
     *   * prevout owner resolved from block UNDO data (rev*.dat, present on every
     *     non-pruned node) -> NO dependence on -txindex.
     *   * coinbase tx skipped; a tx with several inputs from the same address counts
     *     once for it (set-dedup); a tx spanning several addresses counts once for
     *     each; non-standard / bare-multisig prevouts (address-extract yields 0)
     *     count for nobody. Address string is the canonical CBitcoinAddress form.
     *   * for R: only outputs paying the treasury address count, and only in
     *     transactions the miner signed — so a transfer TO a miner is never mistaken
     *     for one FROM it, and a miner's own change output never counts. Fees are
     *     excluded (they go to the block's miner, not the treasury). Values are summed
     *     as int64 satoshi-equivalents and converted once at the end, so the sum
     *     itself carries no floating-point rounding.
     *   * returns false (never a partial map) if any buried block lacks data/undo
     *     (e.g. a pruned node) — the caller then simply does not publish.
     *
     * @param epoch  1-based epoch index.
     * @param tau    [out] address -> activity counter (cleared first).
     * @param r      [out] miner address -> reconciled amount (cleared first). A miner
     *               that reconciled nothing is simply absent, which the pipeline reads
     *               as R = 0.
     */
    bool ComputeActivityAndReconciliationForEpoch(uint32_t epoch,
                                                  std::map<std::string, uint32_t>& tau,
                                                  std::map<std::string, double>& r);

    /** Activity only, for callers that do not need R. Thin wrapper over the single-pass
     *  computation above — kept so the tau-only call sites stay readable, NOT a second
     *  scan. */
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
    /** The PUBLISHED input streams — two, not four. `weight-engine-activity` never
     *  existed as a mechanism (the name was defined but never created, written or read)
     *  and `weight-engine-reconciliation` was removed when R became chain-derived, so
     *  membership and ESG are the only streams this reader manages. */
    InputStream m_Streams[2];     //!< membership, esg

    bool GetStreamEntity(const std::string& name, mc_EntityDetails* entity);
    bool EnsureOneStream(InputStream& s);   // create-if-missing (CLOSED) + subscribe, one stream
    bool ReadStreamItems(const std::string& name, std::vector<WeightStreamItem>& out);
};

#endif // MC_WEIGHT_READER_H
