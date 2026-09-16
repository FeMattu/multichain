// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W2: the pure weight-computation core.
// ------------------------------------------------------------------------------
// WeightEngine turns the pipeline's four inputs — two PUBLISHED streams (membership,
// ESG; parsed by the W1 helpers in weight_records.h) and two quantities DERIVED from
// the epoch's confirmed blocks (activity tau and reconciliation R; see
// weight_reader.h) — into the per-cluster weight w_k^{(e)} published to
// "wpoa-weights". It implements, VERBATIM, the "Gestione del peso" thesis chapter:
//
//   c_i^{(e)}   = ESG_i * tau_i^{(e)} / kappa                       (Def. contributo-pesato)
//   W_k^{(e)}   = ESG_{Mk} * ( tau_{Mk}^{(e)} + sum_{i in C_k} c_i^{(e)} )   (Def. peso-grezzo)
//   g_k^{(e)}   = Entrate_k^{(e)} - Uscite_k^{(e)}                   (Def. guadagno)
//   saldo_k^{(e)} = saldo_k^{(e-1)} + g_k^{(e)},  saldo_k^{(0)} = 0  (Def. saldo)
//   rho_k^{(e)} = R_k^{(e)} / saldo_k^{(e)}   in [0,1]               (Def. tasso-restituzione)
//   w_k^{(1)}   = W_k^{(1)}                                          (Def. peso-finale, e = 1)
//   w_k^{(e)}   = W_k^{(e)} * [ rho_k^{(e-1)} * lambda + (1-lambda) ]         (e >= 2)
//
// with Uscite EXCLUDING the epoch's own restitution R_k^{(e)} — accounted separately so
// saldo_k^{(e)} does not depend on R_k^{(e)}, which would make rho_k^{(e)} = R/saldo
// self-referential (Def. guadagno states the exclusion and its reason). Operationally the
// reader hands over GROSS flows, restitution still inside the debits, and Gain() adds it
// back: one subtraction in one place, rather than a special case threaded through the scan.
//
// SUPERSEDES ALLOCATION / COMPLIANCE. Until this change the engine implemented the earlier
// formulation of the same feedback slot — an allocation A_k = alpha*Theta*W_k/W_tot, a
// residual carry B_k, and a compliance rate rho_k = R_k/(A_k + B_k^{(e-1)}). The thesis
// chapter replaced that trio with the three lines above: the denominator is no longer an
// amount the protocol notionally ASSIGNS to a cluster, but the amount the cluster actually
// HAS, derived from the epoch's confirmed transfers like R_k itself. A_k, B_k, Theta and the
// alpha parameter are therefore gone from the pipeline (alpha survives only as a parsed,
// hash-enforced chain parameter — see g_weight_alpha below — because dropping a params.dat
// field would change its hash and break every existing chain). The recursion shape of
// w_k, the positivity argument (lambda < 1) and the wpoa-weights contract are unchanged.
//
// The final integer weight fed to the stream is ToIntegerWeight(w_k), always >= 1
// (Prop. positivita-peso; also the Efraimidis-Spirakis requirement, wpoa_selector.h).
//
// RELATION TO THE SELECTOR. WeightEngine produces the RAW weight w_k (the exact
// analogue of the static -weight it replaces). The consensus selector
// (WPoASelector::ApplyDumping) still applies its whale-compression f(w_k) at
// election time; the two are complementary and the wpoa-weights contract
// ({address, integer weight > 0}) is unchanged.
//
// RELATION TO THE Vers_2 SIMULATION. The reference Vers_2 spreadsheet derived its
// "GuadagnoEx" from the feedback-adjusted, normalized weight (ImpCluster/Delay) — a
// notional assignment. This core no longer models an assignment at all: g_k is the
// cluster's OBSERVED native-currency flow over the epoch's confirmed blocks. The two
// still coincide for W_k in every epoch and for w_k at epoch 1; from epoch 2 on the
// feedback term differs, deliberately, because it now measures what the cluster
// actually earned and returned rather than what it was notionally due.
//
// CONSENSUS-CRITICAL DETERMINISM. w_k gates proposer election, so every honest
// node must compute the SAME integer w_k:
//   * double precision throughout, matching the selector core
//     (wpoa_selector.h ScoreFromEntropy64) — reproducible across the
//     identical-binary validator set;
//   * sum_{i} c_i is taken in ascending-ADDRESS order and clusters are processed in
//     ascending-MINER order, so the (non-associative) floating-point result never
//     depends on input order;
//   * a zero/negative saldo in rho yields 0 (never NaN/Inf) — this is the degeneration
//     that turned the "con delega" simulation into propagating #DIV/0!; the thesis form
//     with lambda < 1 provably avoids it propagating into w_k;
//   * ToIntegerWeight rounds half-away-from-zero and clamps to [1, UINT32_MAX].
//
// The core is header-only and depends ONLY on the C++ standard library, so it is
// unit-tested in isolation (test/weight_engine_tests.cpp); the node-coupled
// reader/publisher/thread live in weight_reader.{h,cpp} and weight_engine.cpp (W3).

#ifndef MC_WEIGHT_ENGINE_H
#define MC_WEIGHT_ENGINE_H

#include <algorithm>
#include <cmath>
#include <map>
#include <string>
#include <vector>
#include <stdint.h>

#include "weight_engine/weight_streams.h"

/**
 * WeightEngine — pure, deterministic, node-free weight computation.
 *
 * All methods are static and depend only on the C++ standard library, so the
 * Boost.Test suite can exercise them without linking the wallet / node runtime.
 * The scalar helpers expose each thesis definition on its own (for direct
 * verification); ComputeEpoch drives a whole epoch across every cluster, and is
 * what the W3 reader calls once per epoch while folding state forward.
 */
class WeightEngine
{
public:

    // -----------------------------------------------------------------------
    // Data types
    // -----------------------------------------------------------------------

    /** One company's per-epoch activity within a cluster. */
    struct Company
    {
        std::string address;  // company node address (drives deterministic order)
        double      esg;      // ESG_i > 0 (certified, static across epochs)
        uint32_t    tau;      // tau_i^{(e)} (this epoch; 0 = inactive)

        Company() : esg(0.0), tau(0) {}
        Company(const std::string& a, double e, uint32_t t)
            : address(a), esg(e), tau(t) {}
    };

    /** One cluster's inputs for a single epoch. All four chain-derived quantities come
     *  from one pass over the epoch's confirmed blocks
     *  (WeightStreamReader::ComputeEpochFacts); none is declared by anybody. */
    struct ClusterInput
    {
        std::string          miner;       // miner / cluster address (C_k key)
        double               esg_miner;   // ESG_{Mk} > 0
        uint32_t             tau_miner;   // tau_{Mk}^{(e)}
        std::vector<Company> companies;   // the cluster members C_k
        double               restituted;  // R_k^{(e)}        (Def. restituzione)
        double               credits;     // Entrate_k^{(e)}  (gross, coinbase included)
        double               debits;      // Uscite_k^{(e)}   (GROSS: R_k still inside)

        ClusterInput()
            : esg_miner(0.0), tau_miner(0), restituted(0.0), credits(0.0), debits(0.0) {}
    };

    /** Inter-epoch state carried per cluster: (saldo_k^{(e-1)}, rho_k^{(e-1)}).
     *
     *  This IS the engine's memo of the recursive saldo: ComputeEpoch folds it forward
     *  one buried epoch at a time, so no separate balance cache is needed and none may
     *  be introduced — see the NOT AN AVAILABLE-BALANCE READING note on Saldo() for why
     *  the running total and a UTXO balance are different quantities. */
    struct ClusterState
    {
        double saldo;        // saldo_k^{(e-1)} (cumulative net; saldo_k^{(0)} = 0)
        double restitution;  // rho_k^{(e-1)}   (previous-epoch restitution rate)

        ClusterState() : saldo(0.0), restitution(0.0) {}
        ClusterState(double s, double r) : saldo(s), restitution(r) {}
    };

    /** Full per-cluster result of one epoch. */
    struct ClusterResult
    {
        double   raw_weight;      // W_k^{(e)}
        double   gain;            // g_k^{(e)}     (Def. guadagno; may be negative)
        double   restitution;     // rho_k^{(e)}   (becomes next epoch's prev)
        double   saldo;           // saldo_k^{(e)} (carried forward)
        double   weight;          // w_k^{(e)}     (real-valued final weight)
        uint32_t integer_weight;  // published weight, always >= 1

        ClusterResult()
            : raw_weight(0.0), gain(0.0), restitution(0.0),
              saldo(0.0), weight(0.0), integer_weight(1) {}
    };

    /** Protocol parameters (defaults from weight_streams.h). CONSENSUS-CRITICAL:
     *  identical on every node. Constraints (kappa>0, 0<=lambda<1) are enforced where
     *  the flags are parsed (W3), not here.
     *
     *  `alpha` is RETAINED BUT UNUSED. It parameterised the allocation A_k that the
     *  restitution-rate formulation replaced; nothing reads it any more. It is kept as a
     *  field — and as a parsed chain parameter — only because `weightalpha` is part of
     *  params.dat, which is hash-enforced: removing it would change the hash and reject
     *  every existing chain. Do not reintroduce a consumer without reopening the
     *  Def. tasso-restituzione decision. */
    struct Params
    {
        double kappa;   // kappa > 0
        double alpha;   // DEPRECATED: parsed for params.dat compatibility, never read
        double lambda;  // lambda in [0,1)

        Params()
            : kappa(MC_WEIGHT_DEFAULT_KAPPA), alpha(MC_WEIGHT_DEFAULT_ALPHA),
              lambda(MC_WEIGHT_DEFAULT_LAMBDA) {}
        Params(double k, double a, double l) : kappa(k), alpha(a), lambda(l) {}
    };

    // -----------------------------------------------------------------------
    // Scalar pipeline pieces (each a single thesis definition)
    // -----------------------------------------------------------------------

    /** c_i = ESG_i * tau_i / kappa   (Def. contributo-pesato). */
    static double CompanyContribution(double esg_i, uint32_t tau_i, double kappa)
    {
        return esg_i * (double)tau_i / kappa;
    }

    /**
     * W_k = ESG_{Mk} * ( tau_{Mk} + sum_{i in C_k} c_i )   (Def. peso-grezzo).
     *
     * The company contributions are summed in ascending-address order so the
     * (non-associative) floating-point total is identical on every node
     * regardless of how the caller ordered `companies`.
     */
    static double RawWeight(const ClusterInput& in, double kappa)
    {
        std::vector<const Company*> ordered;
        ordered.reserve(in.companies.size());
        for (size_t i = 0; i < in.companies.size(); i++)
        {
            ordered.push_back(&in.companies[i]);
        }
        std::sort(ordered.begin(), ordered.end(), CompanyAddressLess);

        double sum_c = 0.0;
        for (size_t i = 0; i < ordered.size(); i++)
        {
            sum_c += CompanyContribution(ordered[i]->esg, ordered[i]->tau, kappa);
        }

        return in.esg_miner * ((double)in.tau_miner + sum_c);
    }

    /**
     * g_k = Entrate_k - Uscite_k   (Def. guadagno), where Uscite EXCLUDES the epoch's
     * own restitution R_k.
     *
     * The reader supplies GROSS flows — `debits_gross` still contains R_k, because a
     * restitution is an ordinary outgoing transfer and the block scan has no reason to
     * treat it specially — so the exclusion is performed here, once, by adding R_k back:
     *
     *     g_k = credits - (debits_gross - R_k) = credits - debits_gross + R_k
     *
     * Why exclude it at all: saldo_k feeds rho_k = R_k / saldo_k. Were R_k also
     * subtracted inside saldo_k, the ratio would be self-referential — a cluster that
     * returned everything would divide by the very zero its own restitution created, and
     * score 0 for the behaviour the mechanism exists to reward. The thesis states this
     * exclusion and its reason directly (Def. guadagno).
     *
     * R_k is clamped at 0 first, so a negative input can never inflate the gain.
     * The result MAY be negative (a cluster that spent more than it received); the saldo
     * recursion carries that through honestly and RestitutionRate's guard handles the
     * degenerate non-positive case.
     */
    static double Gain(double credits, double debits_gross, double restituted)
    {
        double r = (restituted > 0.0) ? restituted : 0.0;
        return credits - debits_gross + r;
    }

    /**
     * saldo_k^{(e)} = saldo_k^{(e-1)} + g_k^{(e)},  saldo_k^{(0)} = 0   (Def. saldo).
     *
     * NOT AN AVAILABLE-BALANCE READING. It is tempting to replace this recursion with a
     * direct read of the address' UTXO balance — MultiChain is UTXO-based and the ledger
     * already tracks exactly that. It would be wrong, for three independent reasons:
     *
     *   1. DIFFERENT QUANTITY. Because every epoch's Uscite excludes that epoch's own
     *      restitution, the recursion adds every past R back: saldo_k^{(e)} equals the
     *      real balance PLUS sum_{j<=e} R_k^{(j)}. The two coincide only for a cluster
     *      that never restituted. Reading the ledger would shrink the denominator by the
     *      cluster's own good behaviour — in the limit, a cluster that returns everything
     *      reads a balance of 0 and scores rho = 0 (the guard's value) instead of rho = 1,
     *      exactly inverting the incentive.
     *   2. WRONG TIME. w_k for a buried epoch must be a function of THAT epoch's confirmed
     *      blocks alone. A UTXO balance is current state at the local tip, so two nodes at
     *      different heights — or one re-syncing — would attribute a historical epoch
     *      differently than the network did when it happened. This is the same failure
     *      that ruled out deriving the treasury address from the mutable admin set
     *      (wpoa/docs/adr/reconciliation-onchain.md).
     *   3. NOT AVAILABLE ANYWAY. Balance lookups here are wallet-scoped
     *      (ISMINE_SPENDABLE | ISMINE_WATCH_ONLY: see getaddressbalances,
     *      CWallet::GetAddressBalances) and MultiChain keeps no address index, so a node
     *      simply cannot read another cluster's balance — yet every node must recompute
     *      EVERY cluster's weight to verify the published ones (weight_verifier.h).
     *
     * The flows themselves come from the block scan every node already runs once per
     * buried epoch, and ClusterState carries the running total forward, so the recursion
     * costs nothing beyond the pass already being made and needs no cache of its own.
     */
    static double Saldo(double saldo_prev, double gain)
    {
        return saldo_prev + gain;
    }

    /**
     * rho_k = clamp(R_k, [0, saldo_k]) / saldo_k   in [0,1]   (Def. tasso-restituzione).
     *
     * A non-positive saldo (a cluster that received nothing this epoch and carried
     * nothing in, or spent more than it ever took) yields 0 — the defined value that
     * keeps the pipeline finite where the "con delega" simulation produced a propagating
     * #DIV/0!. Note this is the SAFE direction: rho only ever damps w_k, so an
     * indeterminate ratio costs a cluster feedback, it never grants any.
     *
     * The clamp is belt-and-braces. The ledger already enforces R_k <= saldo_k: a
     * restitution is an ordinary transfer, so it cannot exceed the balance actually
     * available, and the available balance never exceeds saldo_k by reason 1 above
     * (Oss. limite-restituzione argues the bound from exactly this ledger semantics).
     * Clamping anyway keeps rho in [0,1] by construction rather than by argument, which
     * is what the positivity proof of w_k consumes.
     */
    static double RestitutionRate(double restituted, double saldo)
    {
        if (saldo <= 0.0)
        {
            return 0.0;
        }
        double r = ClampRestituted(restituted, saldo);
        return r / saldo;
    }

    /**
     * w_k = W_k                                   (e = 1)
     * w_k = W_k * [ rho_{k,e-1} * lambda + (1-lambda) ]   (e >= 2)   (Def. peso-finale).
     *
     * `restitution_prev` is rho_k^{(e-1)}, the PREVIOUS epoch's restitution rate: the
     * feedback is deliberately one epoch late, so the weight of epoch e never depends on
     * a quantity of epoch e that it would in turn influence.
     *
     * For e >= 2 the bracket is a convex combination of rho_{k,e-1} in [0,1] and 1
     * with weight lambda in [0,1), hence in [1-lambda, 1] and strictly positive, so
     * w_k > 0 whenever W_k > 0 (Prop. positivita-peso) — the reason lambda < 1 is a
     * correctness requirement, not just a tuning choice. Swapping the compliance rate
     * for the restitution rate leaves this argument untouched: it needs only rho in
     * [0,1], which RestitutionRate guarantees by construction.
     */
    static double FinalWeight(double raw_weight, double restitution_prev,
                              double lambda, uint32_t epoch)
    {
        if (epoch <= 1)
        {
            return raw_weight;
        }
        double factor = restitution_prev * lambda + (1.0 - lambda);
        return raw_weight * factor;
    }

    /**
     * Convert a real weight to the positive integer published on wpoa-weights.
     *
     * `scale` uniformly magnifies w_k before rounding to preserve the precision
     * that kappa divided out of c_i (ComputeEpoch passes kappa). Because the
     * selector normalizes weights, any positive uniform scale leaves the election
     * distribution unchanged; it only sets the rounding granularity. The result is
     * rounded half-away-from-zero and clamped to [1, UINT32_MAX]:
     *   * the floor of 1 enforces the positivity invariant of the stream and of
     *     Efraimidis-Spirakis even for a degenerate zero-activity cluster (W_k = 0);
     *   * the ceiling guards the uint32_t range against extreme inputs.
     * The `!(s >= 1.0)` test also maps NaN to the safe floor of 1.
     */
    static uint32_t ToIntegerWeight(double weight, double scale)
    {
        double s = weight * scale;
        if (!(s >= 1.0))                       // catches NaN, negatives and s < 1
        {
            return 1;
        }
        if (s >= (double)UINT32_MAX)
        {
            return UINT32_MAX;
        }
        return (uint32_t)std::floor(s + 0.5);  // round half away from zero (s >= 1)
    }

    // -----------------------------------------------------------------------
    // Epoch driver
    // -----------------------------------------------------------------------

    /**
     * Compute one epoch's weights for every cluster.
     *
     * One pass over clusters in ascending-miner-address order, so every floating-point
     * accumulation is order-independent. For each cluster: W_k, then g_k from the
     * epoch's flows, then saldo_k folded onto the carried saldo_k^{(e-1)}, then
     * rho_k^{(e)}, then w_k^{(e)} from the carried rho_k^{(e-1)}, then the integer weight.
     *
     * NOTE the two different vintages in play: w_k^{(e)} consumes the PREVIOUS epoch's
     * rho (one-epoch-late feedback), while rho_k^{(e)} computed here is what the NEXT
     * epoch will consume. The single pass is safe precisely because of that separation —
     * no cluster's result depends on another cluster's result within the epoch, which is
     * what the removed allocation term (via W_tot) used to require a second pass for.
     *
     * @param inputs      per-cluster inputs for THIS epoch.
     * @param prior       miner -> {saldo^{(e-1)}, rho^{(e-1)}}. A miner absent here starts
     *                    from zero state. Consulted for the saldo at EVERY epoch (the
     *                    recursion is cumulative, and saldo^{(0)} = 0 makes epoch 1 fall
     *                    out of the general case) but for rho only from epoch 2, since
     *                    there is no rho^{(0)}.
     * @param params      kappa / lambda. (alpha is no longer consumed; see the header.)
     * @param epoch       1-based epoch index.
     * @param out_results miner -> ClusterResult (cleared first).
     * @param out_state   miner -> {saldo^{(e)}, rho^{(e)}} to carry into epoch e+1
     *                    (cleared first).
     */
    static void ComputeEpoch(const std::vector<ClusterInput>& inputs,
                             const std::map<std::string, ClusterState>& prior,
                             const Params& params,
                             uint32_t epoch,
                             std::map<std::string, ClusterResult>& out_results,
                             std::map<std::string, ClusterState>& out_state)
    {
        out_results.clear();
        out_state.clear();

        // Deterministic cluster order (by miner address).
        std::vector<const ClusterInput*> ordered;
        ordered.reserve(inputs.size());
        for (size_t i = 0; i < inputs.size(); i++)
        {
            ordered.push_back(&inputs[i]);
        }
        std::sort(ordered.begin(), ordered.end(), ClusterMinerLess);

        for (size_t i = 0; i < ordered.size(); i++)
        {
            const ClusterInput& in = *ordered[i];

            // Prior state. The saldo recursion runs from epoch 1 (where the absent entry
            // correctly yields saldo^{(0)} = 0); rho^{(e-1)} only exists from epoch 2.
            double saldo_prev = 0.0;
            double restitution_prev = 0.0;
            {
                std::map<std::string, ClusterState>::const_iterator it = prior.find(in.miner);
                if (it != prior.end())
                {
                    saldo_prev = it->second.saldo;
                    if (epoch >= 2)
                    {
                        restitution_prev = it->second.restitution;
                    }
                }
            }

            double Wk    = RawWeight(in, params.kappa);
            double gk    = Gain(in.credits, in.debits, in.restituted);
            double saldo = Saldo(saldo_prev, gk);
            double rho   = RestitutionRate(in.restituted, saldo);
            double wk    = FinalWeight(Wk, restitution_prev, params.lambda, epoch);

            ClusterResult r;
            r.raw_weight     = Wk;
            r.gain           = gk;
            r.restitution    = rho;
            r.saldo          = saldo;
            r.weight         = wk;
            r.integer_weight = ToIntegerWeight(wk, params.kappa);

            out_results[in.miner] = r;
            out_state[in.miner] = ClusterState(saldo, rho);
        }
    }

    /**
     * The newest epoch whose blocks are all buried, i.e. the newest epoch whose last
     * height sits at least `margin` below `tip_height`. 0 when nothing is buried yet.
     *
     * Epoch e spans heights [(e-1)*len, e*len - 1], so the largest buried e is the one
     * with e*len - 1 <= tip_height - margin, i.e. e = (tip_height - margin + 1) / len.
     *
     * This is the ONE definition of "how far back the pipeline may be trusted": the
     * publishing thread uses it to pick the epoch to compute, and the audit RPCs use it
     * both as their default epoch and as the admissibility bound they refuse past. Kept
     * pure so the node-free unit test can pin the boundary arithmetic.
     */
    static uint32_t LastBuriedEpoch(int tip_height, int epoch_length, int margin)
    {
        if (epoch_length < 1 || tip_height < 0 || margin < 0)
        {
            return 0;
        }
        int stable = tip_height - margin;
        if (stable < 0)
        {
            return 0;
        }
        return (uint32_t)((stable + 1) / epoch_length);
    }

private:

    /** Restituted amount clamped to its legal domain [0, saldo] (Oss. limite-restituzione). */
    static double ClampRestituted(double restituted, double saldo)
    {
        if (restituted < 0.0)   return 0.0;
        if (restituted > saldo) return saldo;
        return restituted;
    }

    /** Strict weak ordering on company address (for deterministic summation). */
    static bool CompanyAddressLess(const Company* a, const Company* b)
    {
        return a->address < b->address;
    }

    /** Strict weak ordering on miner address (for deterministic cluster order). */
    static bool ClusterMinerLess(const ClusterInput* a, const ClusterInput* b)
    {
        return a->miner < b->miner;
    }
};

// ---------------------------------------------------------------------------
// Node-coupled configuration (defined in weight_engine.cpp; bound to the chain
// parameters / runtime flags in AppInit2, exactly like the wPoA globals). NOT
// used by the node-free unit test, which exercises only the pure core above.
//
// Each is a params.dat chain parameter inherited on join, which a matching
// runtime flag can override locally (see src/core/init.cpp). CONSENSUS-CRITICAL:
// every honest node MUST hold identical values, or they compute different w_k and
// disagree on the elected proposer (the chain forks). They are threaded
// explicitly into WeightEngine::Params by the caller; the pure core never reads
// a global.
// ---------------------------------------------------------------------------

/** -enableweightengine: compute+publish w_k each epoch instead of a static
 *  -weight. Default false. Requires the wPoA weights stream. */
extern bool g_weight_engine_enabled;

/** -weightepochlength: epoch length in blocks, epoch(height) = height / this (>= 1). */
extern int g_weight_epoch_length;

/** -weightkappa: normalization constant kappa > 0 (Def. contributo-pesato). */
extern double g_weight_kappa;

/** -weightalpha: DEPRECATED. It scaled the allocation A_k = alpha*Theta*W_k/W_tot in the
 *  superseded compliance-rate formulation; the restitution-rate pipeline has no allocation
 *  and reads it nowhere. Still parsed and still hash-enforced, because `weightalpha` is a
 *  params.dat field (protocol 20014) and dropping it would change the file's hash and make
 *  every existing chain unjoinable. Validation of its range is likewise retained, so a
 *  chain created before or after this change is configured identically. */
extern double g_weight_alpha;

/** -weightlambda: feedback damping lambda in [0,1) (Def. peso-finale). */
extern double g_weight_lambda;

/** -weighttreasuryaddress: the recipient that defines a reconciliation transfer.
 *
 *  R_k^{(e)} (Def. restituzione) is the native-currency value paid to THIS address by
 *  transactions the miner signed, among the confirmed transactions of epoch e — derived
 *  from the blocks by WeightStreamReader::ComputeEpochFacts, never declared by anyone. It
 *  replaced an administrator attestation on a dedicated stream; see
 *  wpoa/docs/adr/reconciliation-onchain.md.
 *
 *  CONSENSUS-CRITICAL, and necessarily a chain parameter rather than a derived value: the
 *  value of R_k depends on it, so two nodes disagreeing about the treasury address compute
 *  different w_k and fork. Deriving it implicitly from "who holds admin" was rejected
 *  because the admin set is MUTABLE, which would make a re-syncing node attribute a
 *  historical epoch differently than the network did at the time.
 *
 *  EMPTY IS LEGAL and means R_k = 0 for every cluster, uniformly and on every node — the
 *  same behaviour as the old model on a chain where nobody published reconciliation
 *  records. A uniform R = 0 gives rho_k = 0 and hence w_k = W_k * (1 - lambda), a uniform
 *  scaling that leaves the relative weights, and so the election, unchanged — note this
 *  holds under the restitution-rate formulation too, and for the same reason: rho enters
 *  w_k only through a factor that is identical across clusters when R is. */
extern std::string g_weight_treasury_address;

// --- epoch mapping / activation / background thread (defined in weight_engine.cpp) ---

/** epoch(height) = height / g_weight_epoch_length + 1 (1-based). Every node derives
 *  the same epoch from the height alone (thesis §epochs_slots). */
uint32_t HeightToEpoch(int height);

class WeightStreamReader;   // forward-declared: the epoch driver reads through it

/**
 * WeightEpochCluster — one cluster's complete, audited epoch: what went in, what came
 * out, and the one carried quantity that links it to the epoch before.
 *
 * The pipeline already derives all of this to produce a single integer weight, and
 * WeightEngineComputeAllWeightsForEpoch then discards everything but that integer.
 * Keeping the intermediate values is what lets a third party check each step of
 * Def. contributo-pesato -> peso-grezzo -> guadagno -> saldo -> tasso-restituzione ->
 * peso-finale separately, instead of being handed the end of the chain and asked to
 * trust it.
 */
struct WeightEpochCluster
{
    WeightEngine::ClusterInput  input;   //!< ESG, tau, members, R_k, gross flows
    WeightEngine::ClusterResult result;  //!< W_k, g_k, saldo_k, rho_k, w_k, integer w_k

    /** rho_k^{(e-1)}, the restitution rate the FINAL weight of this epoch consumed.
     *  Undefined at epoch 1 — there is no previous epoch — which `has_restitution_prev`
     *  distinguishes from a genuine rate of 0. */
    double restitution_prev;
    bool   has_restitution_prev;

    WeightEpochCluster() : restitution_prev(0.0), has_restitution_prev(false) {}
};

/**
 * Every cluster's FULL epoch detail for `target_epoch`, folded forward from epoch 1
 * over purely public on-chain inputs.
 *
 * This is the primitive; WeightEngineComputeAllWeightsForEpoch is a projection of it
 * that keeps only the integer weights. Both therefore walk exactly the same pipeline,
 * so an audit RPC cannot report a number the consensus path would not have derived.
 *
 * @return false when the inputs are not yet readable or the epoch's blocks cannot be
 *         scanned identically across nodes (not buried, pruned) — never a partial map.
 */
bool WeightEngineComputeEpochDetail(WeightStreamReader& reader, uint32_t target_epoch,
                                    std::map<std::string, WeightEpochCluster>& out);

/**
 * The newest fully buried epoch at the local tip, or 0 when nothing is buried yet.
 *
 * WeightEngine::LastBuriedEpoch applied to the current chain height, the configured
 * epoch length and MC_WEIGHT_DEFAULT_STABILITY_MARGIN. Shared by the publishing thread
 * (which epoch to compute) and the audit RPCs (their default epoch, and the bound past
 * which they refuse), so the two can never disagree about what is final.
 */
uint32_t WeightEngineLastBuriedEpoch();

/** True when the weight engine governs the weights at `height` (i.e. it is enabled).
 *  Pure predicate, in the style of WPoAActiveAtHeight (wpoa_selector.h). */
bool WeightEngineActiveAtHeight(int height);

/**
 * Background entry point launched from AppInit2 (in place of ThreadRegisterNodeWeight)
 * when -enableweightengine is set. Ensures the two published input streams exist and are
 * subscribed — creating them on the first node that has create permission (the
 * genesis / admin node) and merely subscribing on every other node — then, at each
 * epoch boundary on the chain tip, recomputes this node's own w_k from the public
 * inputs and publishes it to wpoa-weights via StreamWeightRegistry.
 */
void ThreadWeightEngine();

#endif // MC_WEIGHT_ENGINE_H
