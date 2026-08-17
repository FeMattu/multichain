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
 * The two classes of misbehaviour that a node can prove locally while validating a
 * block, and no others (Def. 5.17): a report whose proof would require another
 * validator's private state or secret key could not be decided locally, which
 * would break the local-decidability property the open stream relies on.
 */
enum MalusKind
{
    MALUS_NONE  = 0,   //!< unparsable / unknown kind — never scored
    MALUS_EQUIV = 1,   //!< equivocation: two distinct blocks at one height (Def. 5.18)
    MALUS_DELAY = 2    //!< scheduling-delay violation: block mined too early (Def. 5.19)
};

/** Stream field names — single source of truth for the writer and the reader. */
#define MC_WPOA_MALUS_FIELD_KIND     "kind"
#define MC_WPOA_MALUS_FIELD_ADDR     "node_address"
#define MC_WPOA_MALUS_FIELD_HEIGHT   "height"
#define MC_WPOA_MALUS_FIELD_BLOCKS   "blocks"

/** Wire spellings of MalusKind (what actually goes on-chain). */
#define MC_WPOA_MALUS_KIND_EQUIV     "equiv"
#define MC_WPOA_MALUS_KIND_DELAY     "delay"

/** Map a wire spelling to its enum; MALUS_NONE for anything unrecognised. */
inline MalusKind mc_MalusKindFromString(const std::string& s)
{
    if (s == MC_WPOA_MALUS_KIND_EQUIV) return MALUS_EQUIV;
    if (s == MC_WPOA_MALUS_KIND_DELAY) return MALUS_DELAY;
    return MALUS_NONE;
}

/** Map an enum to its wire spelling; "" for MALUS_NONE. */
inline const char* mc_MalusKindToString(MalusKind k)
{
    switch (k)
    {
        case MALUS_EQUIV: return MC_WPOA_MALUS_KIND_EQUIV;
        case MALUS_DELAY: return MC_WPOA_MALUS_KIND_DELAY;
        case MALUS_NONE:
        default:          return "";
    }
}

/**
 * Parse a wpoa-weights-malus item payload into its four fields.
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
                                    int& height, std::vector<std::string>& blocks)
{
    kind = MALUS_NONE;
    node_address = "";
    height = 0;
    blocks.clear();

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
    }

    if (k == MALUS_NONE || addr.empty() || h <= 0 || h > (int64_t)0x7fffffff)
    {
        return false;
    }
    // An equivocation names the two competing blocks; a delay violation names the
    // single block that was mined too early.
    const size_t expected = (k == MALUS_EQUIV) ? 2 : 1;
    if (refs.size() != expected)
    {
        return false;
    }

    kind = k;
    node_address = addr;
    height = (int)h;
    blocks = refs;
    return true;
}

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
     * p(Equiv) >> p(Delay) by protocol constraint: equivocation threatens the
     * chain's safety (competing blocks at one height), a delay violation only the
     * correctness of the temporal scheduling.
     *
     * @param kind     The violation kind; MALUS_NONE scores 0.
     * @param p_equiv  Score for an equivocation.
     * @param p_delay  Score for a delay violation.
     */
    static double Points(MalusKind kind, double p_equiv, double p_delay)
    {
        switch (kind)
        {
            case MALUS_EQUIV: return p_equiv;
            case MALUS_DELAY: return p_delay;
            case MALUS_NONE:
            default:          return 0.0;
        }
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
     * @return 0 when the validator is not excluded (M < M_max) and mu == 0
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
