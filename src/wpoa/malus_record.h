// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// wPoA — behavioural malus: pure, dependency-light record helpers and accumulator.
// -----------------------------------------------------------------------------
// The weight registry (wpoa-weights, stream_weight_registry.h) carries the weight
// w_i produced by the weight-management layer — ESG score and participation —
// which knows nothing about how validator i behaves on the wPoA protocol itself.
// A validator that equivocates, or that tries to jump its scheduling delay, keeps
// exactly the same w_i as an honest one.
//
// The malus registry (malus_registry.h) closes that gap with a SECOND, separate
// append-only stream, and this header holds its pure half:
//
//   M_i^(e)   = mu * M_i^(e-1) + sum over the epoch's VALID records of p(kind)
//                                                          (Def. 5.21, accumulator)
//   Psi_i^(e) = max( 0, 1 - M_i^(e) / M_max )   in [0,1]   (Def. 5.22, correction)
//   w_eff_i   = w_i * Psi_i                                 (Def. 5.22, effective weight)
//
// M is an exponential moving average, not an unbounded counter: with mu < 1 the
// memory of past violations decays, so an exclusion caused by M >= M_max always
// clears after a finite, computable number of clean epochs (Prop. 5.16 / Cor. 5.17
// — no permanent ban). EpochsToClear() below is that bound.
//
// WHAT THIS DOES NOT TOUCH. The malus is a multiplicative factor applied
// DOWNSTREAM of the raw weight: it never modifies the weight-management layer that
// produces w_i, nor the wpoa-weights stream, nor the Efraimidis-Spirakis selection
// math. Only the number handed to the sortition changes.
//
// CONSENSUS-CRITICAL. w_eff gates proposer election, so mu, M_max and the two
// per-kind scores must be identical on every honest node. As with the selector's
// dumping function, they are threaded explicitly into this otherwise-pure core
// (which never reads a global) and bound to their runtime flags in exactly one
// place (AppInit2).
//
// This header depends only on json_spirit and the C++ standard library, so the
// parsing/accumulator logic is unit-tested in isolation, without linking the
// wallet / node runtime. See src/wpoa/test/wpoa_malus_tests.cpp.

#ifndef MC_WPOA_MALUS_RECORD_H
#define MC_WPOA_MALUS_RECORD_H

#include <cmath>
#include <map>
#include <string>
#include <vector>
#include <stdint.h>

#include "json/json_spirit_value.h"
#include <boost/foreach.hpp>

/**
 * The classes of misbehaviour a node can prove locally, and no others (Def. 5.17): a
 * report whose proof would require another validator's private state or secret key
 * could not be decided locally, which would break the local-decidability property the
 * open stream relies on.
 *
 * They fall into TWO FAMILIES, which share that principle but differ in what the
 * evidence is and what the offence damages:
 *
 *   CONSENSUS-BEHAVIOURAL (equiv, delay) — how a validator behaved while PRODUCING a
 *     block. The evidence is the block itself, and the proof rests on the VRF reveal it
 *     carries. equiv threatens safety (competing blocks at one height); delay threatens
 *     only the correctness of temporal scheduling.
 *
 *   PUBLISHED-DATA INTEGRITY (selfwrite, badweight) — what a node WROTE to a stream the
 *     weight pipeline reads. The evidence is the publishing transaction, and the proof
 *     rests on its signature and payload. These offences do not touch block production
 *     at all; they attack the INPUTS of the election instead of its execution.
 *
 * Both families are verified the same way — re-derived from public chain data, never
 * judged — which is why they can share one open stream and one accumulator.
 */
enum MalusKind
{
    MALUS_NONE  = 0,   //!< unparsable / unknown kind — never scored
    MALUS_EQUIV = 1,   //!< equivocation: two distinct blocks at one height (Def. 5.18)
    MALUS_DELAY = 2,   //!< scheduling-delay violation: block mined too early (Def. 5.19)

    /**
     * Publishing a record on a SELF-ATTESTED stream on another address's behalf: the
     * transaction's signer is not the node_address the payload declares.
     *
     * The reader already discards such a record, so the attempt gains nothing — and
     * that is exactly why it needs a price. Without one, a node could forge records
     * indefinitely at the cost of transaction fees alone, and every peer would have to
     * keep decoding and discarding them. Same reasoning as `delay`: the ATTEMPT is the
     * offence, whether or not it succeeded.
     */
    MALUS_SELF_WRITE = 3,

    /**
     * Publishing on wpoa-weights a value that does not survive independent
     * recomputation from the public pipeline inputs.
     *
     * Unlike selfwrite, this one CAN succeed: a record from the right signer is
     * accepted on the self-publication rule, so a false value would flow into the
     * election unless somebody recomputes it. It is the offence with the most direct
     * effect on proposer probability, since a single inflated weight distorts every
     * round of the epoch.
     */
    MALUS_INVALID_WEIGHT = 4
};

/** Stream field names — single source of truth for the writer and the reader. */
#define MC_WPOA_MALUS_FIELD_KIND     "kind"
#define MC_WPOA_MALUS_FIELD_ADDR     "node_address"
#define MC_WPOA_MALUS_FIELD_HEIGHT   "height"
/** Evidence references. Block hashes for the consensus-behavioural kinds; the single
 *  publishing TRANSACTION id for the data-integrity kinds. One list, because in both
 *  families it answers the same question: which on-chain object proves this? */
#define MC_WPOA_MALUS_FIELD_BLOCKS   "blocks"
/** Data-integrity kinds only — the fields that let a third party re-derive the finding
 *  without re-running any search of its own. */
#define MC_WPOA_MALUS_FIELD_STREAM   "stream"
#define MC_WPOA_MALUS_FIELD_DECLARED_ADDR "declared_address"
#define MC_WPOA_MALUS_FIELD_EPOCH    "epoch"
#define MC_WPOA_MALUS_FIELD_DECLARED "declared"
#define MC_WPOA_MALUS_FIELD_RECOMPUTED "recomputed"

/** Wire spellings of MalusKind (what actually goes on-chain). */
#define MC_WPOA_MALUS_KIND_EQUIV     "equiv"
#define MC_WPOA_MALUS_KIND_DELAY     "delay"
#define MC_WPOA_MALUS_KIND_SELFWRITE "selfwrite"
#define MC_WPOA_MALUS_KIND_BADWEIGHT "badweight"

/** Map a wire spelling to its enum; MALUS_NONE for anything unrecognised. */
inline MalusKind mc_MalusKindFromString(const std::string& s)
{
    if (s == MC_WPOA_MALUS_KIND_EQUIV)     return MALUS_EQUIV;
    if (s == MC_WPOA_MALUS_KIND_DELAY)     return MALUS_DELAY;
    if (s == MC_WPOA_MALUS_KIND_SELFWRITE) return MALUS_SELF_WRITE;
    if (s == MC_WPOA_MALUS_KIND_BADWEIGHT) return MALUS_INVALID_WEIGHT;
    return MALUS_NONE;
}

/** Map an enum to its wire spelling; "" for MALUS_NONE. */
inline const char* mc_MalusKindToString(MalusKind k)
{
    switch (k)
    {
        case MALUS_EQUIV:         return MC_WPOA_MALUS_KIND_EQUIV;
        case MALUS_DELAY:         return MC_WPOA_MALUS_KIND_DELAY;
        case MALUS_SELF_WRITE:    return MC_WPOA_MALUS_KIND_SELFWRITE;
        case MALUS_INVALID_WEIGHT: return MC_WPOA_MALUS_KIND_BADWEIGHT;
        case MALUS_NONE:
        default:                  return "";
    }
}

/** True for the kinds whose evidence is a PUBLISHING TRANSACTION rather than a block.
 *  Used to pick the right validation branch and the right expected reference count. */
inline bool mc_MalusKindIsDataIntegrity(MalusKind k)
{
    return k == MALUS_SELF_WRITE || k == MALUS_INVALID_WEIGHT;
}

/** How many evidence references a kind must name. Two competing blocks for an
 *  equivocation; one block for a delay violation; one transaction for either
 *  data-integrity kind. Single-sourced so the parser, the writer and the RPC help
 *  cannot disagree. */
inline size_t mc_MalusKindRefCount(MalusKind k)
{
    return (k == MALUS_EQUIV) ? 2 : 1;
}

/**
 * The extra payload fields the data-integrity kinds carry, so a third party can
 * re-derive the finding by reading ONE transaction rather than searching for it.
 *
 * They are claims, not evidence: every one is re-checked against the referenced
 * transaction, and a mismatch invalidates the report. Their purpose is to make the
 * accusation self-describing and auditable — a reader can see what was alleged without
 * running the pipeline — not to be believed.
 */
struct MalusDataDetail
{
    std::string stream;            //!< selfwrite: the stream written
    std::string declared_address;  //!< selfwrite: the node_address the payload claimed
    uint32_t    epoch;             //!< badweight: the epoch the record was published for
    uint32_t    declared;          //!< badweight: the value found on chain
    uint32_t    recomputed;        //!< badweight: the accuser's recomputation

    MalusDataDetail() : epoch(0), declared(0), recomputed(0) {}
};

/** Read a JSON number as a bounded uint32_t; 0 for anything absent, non-numeric,
 *  negative or out of range. A malformed number reads as "unstated" rather than
 *  wrapping, so it can never make a report look like it is about something else. */
inline uint32_t mc_MalusU32(const json_spirit::Value& v)
{
    int64_t n = -1;
    if (v.type() == json_spirit::int_type)
    {
        n = v.get_int64();
    }
    else if (v.type() == json_spirit::real_type)
    {
        double d = v.get_real();
        if (d >= 0.0 && d <= 4294967295.0)
        {
            n = (int64_t)d;
        }
    }
    if (n < 0 || n > (int64_t)0xffffffff)
    {
        return 0;
    }
    return (uint32_t)n;
}

/**
 * Parse a wpoa-weights-malus item payload into its fields.
 *
 * Wire shape (mirroring the weight record, weight_record.h):
 *
 *   { "json": { "kind": "equiv"|"delay",
 *               "node_address": "<accused validator>",
 *               "height": n,
 *               "blocks": [ "<block hash>", ... ] } }
 *
 * The accompanying evidence is the referenced block(s): the verifier resolves them
 * from its own block index and re-runs the checks of Def. 5.18 / Def. 5.19. Nothing
 * in the record is trusted — this parser only establishes that the item is
 * well-formed and carries the number of block references its kind requires
 * (two for an equivocation, one for a delay violation).
 *
 * @param data_value  The value produced by OpReturnFormatEntry for a JSON item.
 * @param kind        Out: the violation kind (MALUS_NONE on failure).
 * @param node_address Out: the accused validator (cleared on failure).
 * @param height      Out: the height the accusation refers to (0 on failure).
 * @param blocks      Out: the referenced block hashes (cleared on failure).
 * @return true only for a well-formed record of a known kind, with a non-empty
 *         address, a positive height and the expected number of block references.
 */
inline bool mc_ParseMalusRecordJson(const json_spirit::Value& data_value,
                                    MalusKind& kind, std::string& node_address,
                                    int& height, std::vector<std::string>& blocks,
                                    MalusDataDetail* detail = NULL)
{
    kind = MALUS_NONE;
    node_address = "";
    height = 0;
    blocks.clear();
    if (detail != NULL)
    {
        *detail = MalusDataDetail();
    }

    if (data_value.type() != json_spirit::obj_type)
    {
        return false;
    }

    // OpReturnFormatEntry has two output shapes for a UBJSON item, depending on the
    // overload used (see mc_ParseWeightRecordJson): accept both by descending into
    // "formatdata" when present, then unwrapping "json".
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

    MalusKind k = MALUS_NONE;
    std::string addr;
    int64_t h = 0;
    std::vector<std::string> refs;
    MalusDataDetail d;

    BOOST_FOREACH(const json_spirit::Pair& p, json_val.get_obj())
    {
        if (p.name_ == MC_WPOA_MALUS_FIELD_KIND && p.value_.type() == json_spirit::str_type)
        {
            k = mc_MalusKindFromString(p.value_.get_str());
        }
        else if (p.name_ == MC_WPOA_MALUS_FIELD_ADDR && p.value_.type() == json_spirit::str_type)
        {
            addr = p.value_.get_str();
        }
        else if (p.name_ == MC_WPOA_MALUS_FIELD_HEIGHT)
        {
            if (p.value_.type() == json_spirit::int_type)
            {
                h = p.value_.get_int64();
            }
            else if (p.value_.type() == json_spirit::real_type)
            {
                h = (int64_t)p.value_.get_real();
            }
        }
        else if (p.name_ == MC_WPOA_MALUS_FIELD_BLOCKS && p.value_.type() == json_spirit::array_type)
        {
            const json_spirit::Array& arr = p.value_.get_array();
            for (size_t i = 0; i < arr.size(); i++)
            {
                if (arr[i].type() == json_spirit::str_type)
                {
                    refs.push_back(arr[i].get_str());
                }
            }
        }
        else if (p.name_ == MC_WPOA_MALUS_FIELD_STREAM && p.value_.type() == json_spirit::str_type)
        {
            d.stream = p.value_.get_str();
        }
        else if (p.name_ == MC_WPOA_MALUS_FIELD_DECLARED_ADDR &&
                 p.value_.type() == json_spirit::str_type)
        {
            d.declared_address = p.value_.get_str();
        }
        else if (p.name_ == MC_WPOA_MALUS_FIELD_EPOCH)
        {
            d.epoch = mc_MalusU32(p.value_);
        }
        else if (p.name_ == MC_WPOA_MALUS_FIELD_DECLARED)
        {
            d.declared = mc_MalusU32(p.value_);
        }
        else if (p.name_ == MC_WPOA_MALUS_FIELD_RECOMPUTED)
        {
            d.recomputed = mc_MalusU32(p.value_);
        }
    }

    if (k == MALUS_NONE || addr.empty() || h <= 0 || h > (int64_t)0x7fffffff)
    {
        return false;
    }
    // An equivocation names the two competing blocks; a delay violation names the single
    // block that was mined too early; a data-integrity report names the single publishing
    // TRANSACTION that carries the offending record.
    if (refs.size() != mc_MalusKindRefCount(k))
    {
        return false;
    }

    // The data-integrity kinds must carry the fields that make them self-describing.
    // Rejecting an incomplete one here rather than mid-validation keeps "well-formed"
    // and "true" cleanly separated: this checks the SHAPE, the registry re-derives the
    // CLAIM from the referenced transaction.
    if (k == MALUS_SELF_WRITE)
    {
        if (d.stream.empty() || d.declared_address.empty())
        {
            return false;
        }
        // A record declaring the accused's OWN address is not a forgery at all — it is
        // the honest case — so such a report is malformed rather than merely false.
        if (d.declared_address == addr)
        {
            return false;
        }
    }
    if (k == MALUS_INVALID_WEIGHT)
    {
        // epoch >= 1 (epochs are 1-based) and a positive declared value, since the
        // weight stream only carries strictly positive weights. `recomputed` may
        // legitimately be 0: that is what an address heading no cluster recomputes to.
        if (d.epoch < 1 || d.declared == 0)
        {
            return false;
        }
        // Equal values would be an accusation that nothing is wrong.
        if (d.declared == d.recomputed)
        {
            return false;
        }
    }

    kind = k;
    node_address = addr;
    height = (int)h;
    blocks = refs;
    if (detail != NULL)
    {
        *detail = d;
    }
    return true;
}

/**
 * The per-kind severity scores, all consensus-critical and all resolved from chain
 * parameters in exactly one place (AppInit2). Grouped in a struct rather than passed as
 * a growing argument list so adding a kind cannot silently shift an existing caller's
 * arguments.
 */
struct MalusScores
{
    double equiv;       //!< p(Equiv) — a safety fault
    double delay;       //!< p(Delay) — a scheduling fault
    double self_write;  //!< p(SelfWrite) — a discarded forgery attempt
    double bad_weight;  //!< p(BadWeight) — a false weight that would have taken effect

    MalusScores() : equiv(0.0), delay(0.0), self_write(0.0), bad_weight(0.0) {}
    MalusScores(double e, double d, double sw, double bw)
        : equiv(e), delay(d), self_write(sw), bad_weight(bw) {}
};

/**
 * MalusAccumulator — pure, deterministic, node-free malus math.
 *
 * All methods are static and depend only on the C++ standard library, so the
 * Boost.Test suite can exercise them without linking the wallet / node runtime,
 * exactly like the Phase 2/3a/3b/4 cores.
 */
class MalusAccumulator
{
public:

    /**
     * The per-kind score p(kind) added to the accumulator by one valid record
     * (Def. 5.21).
     *
     * WHAT NEEDED EXTENDING, AND WHAT DID NOT. Adding a violation kind touches exactly
     * this dispatch. Everything downstream is already generic over the kind, because it
     * operates on the ACCUMULATED SEVERITY rather than on what produced it:
     *   Fold        works on a double;
     *   Psi         = max(0, 1 - M/M_max), a function of M alone;
     *   w_eff       = w * Psi;
     *   EpochsToClear, ApplyToWeights — likewise.
     * So the two data-integrity kinds needed a score each and nothing else: no new
     * correction law, no second accumulator, no change to the consensus path. That is
     * the property that makes one severity scale able to carry two different families
     * of offence.
     *
     * THE SEVERITY ORDERING, and the reasoning behind it:
     *
     *   equiv      threatens SAFETY — two competing blocks at one height. The heaviest
     *              by a wide margin, and the protocol enforces p(equiv) > p(delay).
     *   badweight  a false weight that SUCCEEDS unless somebody recomputes it, and then
     *              distorts proposer probability for every round of the epoch. The
     *              heaviest of the data-integrity pair.
     *   selfwrite  a forgery that is ALWAYS discarded, so it damages nothing directly;
     *              it is scored to price the attempt, exactly as `delay` prices an
     *              attempt that block validation already rejects. Hence
     *              p(badweight) > p(selfwrite), enforced at startup.
     *   delay      threatens only the correctness of temporal scheduling: the lightest.
     */
    static double Points(MalusKind kind, const MalusScores& s)
    {
        switch (kind)
        {
            case MALUS_EQUIV:          return s.equiv;
            case MALUS_DELAY:          return s.delay;
            case MALUS_SELF_WRITE:     return s.self_write;
            case MALUS_INVALID_WEIGHT: return s.bad_weight;
            case MALUS_NONE:
            default:                   return 0.0;
        }
    }

    /** Two-score form, for callers that only deal with the consensus-behavioural kinds.
     *  The data-integrity kinds score 0 through it, which is the correct reading of "no
     *  score configured for them". */
    static double Points(MalusKind kind, double p_equiv, double p_delay)
    {
        return Points(kind, MalusScores(p_equiv, p_delay, 0.0, 0.0));
    }

    /**
     * One epoch step of the accumulator (Def. 5.21):
     *
     *   M^(e) = mu * M^(e-1) + sum of p(kind) over this epoch's valid records
     *
     * The mu factor carries the validator's history forward attenuated, so M is an
     * exponential moving average of recent severity rather than a cumulative
     * counter — which is precisely what makes an exclusion reversible
     * (EpochsToClear / Prop. 5.16).
     *
     * @param prev          M^(e-1) (0 for the first epoch, M^(0) = 0).
     * @param epoch_points  Sum of p(kind) over the epoch's valid records.
     * @param mu            Persistence in [0,1).
     * @return M^(e), never negative and never NaN.
     */
    static double Fold(double prev, double epoch_points, double mu)
    {
        if (!(prev > 0.0))          prev = 0.0;          // also maps NaN to 0
        if (!(epoch_points > 0.0))  epoch_points = 0.0;
        if (!(mu >= 0.0))           mu = 0.0;
        if (mu > 1.0)               mu = 1.0;
        return mu * prev + epoch_points;
    }

    /**
     * The behavioural correction factor (Def. 5.22):
     *
     *   Psi = max( 0, 1 - M / M_max )   in [0,1]
     *
     * Psi = 1 for a validator with no accumulated valid violations, so the
     * mechanism is a no-op on honest behaviour; it then decreases linearly with M
     * and reaches exactly 0 at M >= M_max.
     *
     * @param M     The accumulator value M^(e).
     * @param Mmax  The exclusion threshold, > 0. A non-positive or non-finite
     *              threshold disables the correction (returns 1) rather than
     *              dividing by zero.
     */
    static double CorrectionFactor(double M, double Mmax)
    {
        if (!(Mmax > 0.0))                    return 1.0;
        if (!(M > 0.0))                       return 1.0;   // also maps NaN to 1
        double psi = 1.0 - M / Mmax;
        if (!(psi > 0.0))                     return 0.0;
        if (psi > 1.0)                        return 1.0;
        return psi;
    }

    /**
     * The effective weight fed to the sortition (Def. 5.22):
     *
     *   w_eff = w * Psi
     *
     * Unlike the raw weight — for which the weight-management layer guarantees
     * strict positivity — w_eff MAY be zero, when M >= M_max. That case needs no
     * special handling downstream: the score transform already returns +inf for a
     * zero weight (wpoa_selector.h ScoreFromEntropy64), which makes the validator
     * structurally ineligible without any explicit exclusion branch.
     *
     * Rounds half away from zero, and floors to 1 for any Psi that leaves a
     * fraction of the weight intact, so a small-but-nonzero correction can never
     * silently exclude a validator that Psi did not actually zero out.
     *
     * @param weight  The raw registry weight w.
     * @param psi     The correction factor in [0,1].
     */
    static uint32_t EffectiveWeight(uint32_t weight, double psi)
    {
        if (weight == 0)          return 0;
        if (!(psi > 0.0))         return 0;      // excluded (also maps NaN)
        if (psi >= 1.0)           return weight;

        double w = (double)weight * psi;
        if (w >= (double)weight)  return weight;
        uint32_t r = (uint32_t)std::floor(w + 0.5);
        return (r == 0) ? 1 : r;                 // Psi > 0 must not zero the weight
    }

    /**
     * The number of consecutive clean epochs after which an excluded validator
     * becomes eligible again (Prop. 5.16):
     *
     *   k* = ceil( ln(M / M_max) / ln(1 / mu) )
     *
     * With no new valid records the accumulator decays as M^(e0+k) = mu^k * M^(e0),
     * so k* is the first k with mu^k * M < M_max. Finite for every mu in (0,1),
     * which is what Cor. 5.17 means by "no permanent ban".
     *
     * The closed form above solves the NON-strict mu^k * M <= M_max, but Psi only
     * becomes positive again on the strict inequality: when M / M_max is an exact
     * power of 1/mu (e.g. M = 8, M_max = 4, mu = 0.5) the formula returns the epoch
     * at which M lands exactly ON the threshold, one short. The closed form is
     * therefore used as the starting point and settled by direct evaluation, which
     * also absorbs any floating-point rounding at the boundary.
     *
     * @return 0 when the validator is not excluded (M < M_max); 1 when mu == 0
     *         (a single clean epoch wipes M entirely); -1 when the exclusion can
     *         never clear, which happens only for the degenerate mu >= 1 the
     *         protocol constraint forbids.
     */
    static int EpochsToClear(double M, double Mmax, double mu)
    {
        if (!(Mmax > 0.0))  return 0;
        if (!(M >= Mmax))   return 0;            // not excluded
        if (mu <= 0.0)      return 1;            // one clean epoch drops M to 0
        if (mu >= 1.0)      return -1;           // no decay: forbidden by constraint

        double k = std::log(M / Mmax) / std::log(1.0 / mu);
        int ki = (int)std::ceil(k);
        if (ki < 1) ki = 1;

        // Settle on the strict inequality. Bounded so a pathological input can
        // never spin: mu < 1, so the decay always gets there.
        const int kMaxEpochs = 1000000;
        while (ki < kMaxEpochs && !(std::pow(mu, (double)ki) * M < Mmax))
        {
            ki++;
        }
        return ki;
    }

    /**
     * Apply the correction to a whole weight map: w -> w * Psi, entry by entry.
     *
     * Addresses absent from `accumulators` carry no malus and keep their weight
     * unchanged, so an empty malus map leaves `weights` untouched — the mechanism
     * is inert until the first valid record is recorded.
     *
     * @param weights       address -> raw registry weight.
     * @param accumulators  address -> M (only the accused addresses need appear).
     * @param Mmax          The exclusion threshold.
     * @param out           [out] address -> effective weight (cleared first).
     */
    static void ApplyToWeights(const std::map<std::string, uint32_t>& weights,
                               const std::map<std::string, double>& accumulators,
                               double Mmax,
                               std::map<std::string, uint32_t>& out)
    {
        out.clear();
        for (std::map<std::string, uint32_t>::const_iterator it = weights.begin();
             it != weights.end(); ++it)
        {
            std::map<std::string, double>::const_iterator mi = accumulators.find(it->first);
            double psi = (mi == accumulators.end())
                             ? 1.0
                             : CorrectionFactor(mi->second, Mmax);
            out[it->first] = EffectiveWeight(it->second, psi);
        }
    }
};

#endif // MC_WPOA_MALUS_RECORD_H
