// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W2: the pure weight-computation core.
// ------------------------------------------------------------------------------
// WeightEngine turns the four public input streams (membership, ESG, activity,
// reconciliation — read by the W1 helpers in weight_records.h) into the
// per-cluster weight w_k^{(e)} published to "wpoa-weights". It implements, VERBATIM,
// the "Gestione del peso" thesis chapter:
//
//   c_i^{(e)}   = ESG_i * tau_i^{(e)} / kappa                       (Def. contributo-pesato)
//   W_k^{(e)}   = ESG_{Mk} * ( tau_{Mk}^{(e)} + sum_{i in C_k} c_i^{(e)} )   (Def. peso-grezzo)
//   A_k^{(e)}   = alpha * Theta^{(e)} * W_k^{(e)} / W_tot^{(e)}      (Def. allocazione)
//   rho_k^{(e)} = R_k^{(e)} / ( A_k^{(e)} + B_k^{(e-1)} )  in [0,1]  (Def. tasso-conformita)
//   B_k^{(e)}   = A_k^{(e)} - R_k^{(e)} + B_k^{(e-1)},  B_k^{(0)} = 0 (Def. riconciliazione)
//   w_k^{(1)}   = W_k^{(1)}                                          (Def. peso-finale, e = 1)
//   w_k^{(e)}   = W_k^{(e)} * [ rho_k^{(e-1)} * lambda + (1-lambda) ]         (e >= 2)
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
// RELATION TO THE Vers_2 SIMULATION. This core follows the THESIS, which defines
// the allocation A_k on the RAW weight W_k (A_k = alpha*Theta*W_k/W_tot). The
// reference Vers_2 spreadsheet instead derives its "GuadagnoEx" from the
// feedback-adjusted, normalized weight (ImpCluster/Delay). The two therefore
// coincide for epoch 1 and for W_k in every epoch, but the allocation-derived
// quantities (A_k, rho_k, B_k) can differ from epoch 2 on. The thesis form is
// used deliberately: allocation tracks certified+current merit (W_k), avoiding a
// feedback-of-feedback loop. See docs and the Phase-2 plan.
//
// CONSENSUS-CRITICAL DETERMINISM. w_k gates proposer election, so every honest
// node must compute the SAME integer w_k:
//   * double precision throughout, matching the selector core
//     (wpoa_selector.h ScoreFromEntropy64) — reproducible across the
//     identical-binary validator set;
//   * sum_{i} c_i and the W_tot sum are taken in ascending-ADDRESS order, so the
//     (non-associative) floating-point result never depends on input order;
//   * a zero/negative denominator in rho yields 0 (never NaN/Inf) — this is the
//     degeneration that turned the "con delega" simulation into propagating
//     #DIV/0!; the thesis form with lambda < 1 provably avoids it;
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

    /** One cluster's inputs for a single epoch. */
    struct ClusterInput
    {
        std::string          miner;       // miner / cluster address (C_k key)
        double               esg_miner;   // ESG_{Mk} > 0
        uint32_t             tau_miner;   // tau_{Mk}^{(e)}
        std::vector<Company> companies;   // the cluster members C_k
        double               reconciled;  // R_k^{(e)} (from the reconciliation stream)

        ClusterInput() : esg_miner(0.0), tau_miner(0), reconciled(0.0) {}
    };

    /** Inter-epoch state carried per cluster: (B_k^{(e-1)}, rho_k^{(e-1)}). */
    struct ClusterState
    {
        double balance;      // B_k^{(e-1)}  (residual carry; B_k^{(0)} = 0)
        double compliance;   // rho_k^{(e-1)} (previous-epoch compliance rate)

        ClusterState() : balance(0.0), compliance(0.0) {}
        ClusterState(double b, double r) : balance(b), compliance(r) {}
    };

    /** Full per-cluster result of one epoch. */
    struct ClusterResult
    {
        double   raw_weight;      // W_k^{(e)}
        double   allocation;      // A_k^{(e)}
        double   compliance;      // rho_k^{(e)}   (becomes next epoch's prev)
        double   balance;         // B_k^{(e)}     (carried forward)
        double   weight;          // w_k^{(e)}     (real-valued final weight)
        uint32_t integer_weight;  // published weight, always >= 1

        ClusterResult()
            : raw_weight(0.0), allocation(0.0), compliance(0.0),
              balance(0.0), weight(0.0), integer_weight(1) {}
    };

    /** Protocol parameters (defaults from weight_streams.h). CONSENSUS-CRITICAL:
     *  identical on every node. Constraints (kappa>0, alpha in (0,1], 0<=lambda<1)
     *  are enforced where the flags are parsed (W3), not here. */
    struct Params
    {
        double kappa;   // kappa > 0
        double alpha;   // alpha in (0,1]
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
     * A_k = alpha * Theta * W_k / W_tot   (Def. allocazione).
     * Returns 0 when W_tot <= 0 (no active cluster in the epoch) — deterministic,
     * never a division by zero.
     */
    static double Allocation(double alpha, double theta, double raw_weight,
                             double total_raw_weight)
    {
        if (total_raw_weight <= 0.0)
        {
            return 0.0;
        }
        return alpha * theta * raw_weight / total_raw_weight;
    }

    /**
     * rho_k = clamp(R_k, [0, A_k + B_{k-1}]) / (A_k + B_{k-1})   (Def. tasso-conformita).
     *
     * Always in [0, 1]. R_k is an external input (reconciliation stream), so it is
     * clamped to its legal domain [0, A_k + B_{k-1}] (Def. riconciliazione) before
     * the ratio. A non-positive denominator (nothing was allocated and no residual
     * carried) yields 0 — the defined value that keeps the pipeline finite where
     * the "con delega" simulation produced a propagating #DIV/0!.
     */
    static double ComplianceRate(double reconciled, double allocation,
                                 double balance_prev)
    {
        double denom = allocation + balance_prev;
        if (denom <= 0.0)
        {
            return 0.0;
        }
        double r = ClampReconciled(reconciled, denom);
        return r / denom;
    }

    /**
     * B_k = A_k - clamp(R_k, [0, A_k + B_{k-1}]) + B_{k-1}   (Def. riconciliazione).
     * Uses the same R_k clamp as ComplianceRate, so B_k >= 0 and the two stay
     * mutually consistent.
     */
    static double Balance(double reconciled, double allocation, double balance_prev)
    {
        double denom = allocation + balance_prev;
        double r = (denom <= 0.0) ? 0.0 : ClampReconciled(reconciled, denom);
        return allocation - r + balance_prev;
    }

    /**
     * w_k = W_k                                   (e = 1)
     * w_k = W_k * [ rho_{k,e-1} * lambda + (1-lambda) ]   (e >= 2)   (Def. peso-finale).
     *
     * For e >= 2 the bracket is a convex combination of rho_{k,e-1} in [0,1] and 1
     * with weight lambda in [0,1), hence in [1-lambda, 1] and strictly positive, so
     * w_k > 0 whenever W_k > 0 (Prop. positivita-peso) — the reason lambda < 1 is a
     * correctness requirement, not just a tuning choice.
     */
    static double FinalWeight(double raw_weight, double compliance_prev,
                              double lambda, uint32_t epoch)
    {
        if (epoch <= 1)
        {
            return raw_weight;
        }
        double factor = compliance_prev * lambda + (1.0 - lambda);
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
    // Convenience: network activity Theta
    // -----------------------------------------------------------------------

    /**
     * Theta^{(e)} = sum over all clusters of sum_{i in C_k} tau_i   — the network's
     * total COMPANY activity this epoch (the reference simulation's "TotTx"; the
     * thesis' "somma di tutti i contatori tau_i"). Miner counters tau_{Mk} are part
     * of W_k but not of Theta. Supplied as the `theta` argument to ComputeEpoch;
     * callers may substitute any deterministic network-activity measure.
     */
    static double NetworkActivity(const std::vector<ClusterInput>& inputs)
    {
        double theta = 0.0;
        for (size_t k = 0; k < inputs.size(); k++)
        {
            for (size_t i = 0; i < inputs[k].companies.size(); i++)
            {
                theta += (double)inputs[k].companies[i].tau;
            }
        }
        return theta;
    }

    // -----------------------------------------------------------------------
    // Epoch driver
    // -----------------------------------------------------------------------

    /**
     * Compute one epoch's weights for every cluster.
     *
     * Two passes, both over clusters in ascending-miner-address order so W_tot and
     * every derived quantity are order-independent:
     *   1. W_k for each cluster and their sum W_tot;
     *   2. per cluster: A_k, rho_k^{(e)}, B_k^{(e)}, w_k^{(e)} (using the carried
     *      rho_k^{(e-1)}) and the integer weight.
     *
     * @param inputs      per-cluster inputs for THIS epoch.
     * @param theta       Theta^{(e)} (e.g. NetworkActivity(inputs)).
     * @param prior       miner -> {B^{(e-1)}, rho^{(e-1)}}; ignored for epoch 1
     *                    (B^{(0)} = 0). A miner absent here starts from zero state.
     * @param params      kappa / alpha / lambda.
     * @param epoch       1-based epoch index.
     * @param out_results miner -> ClusterResult (cleared first).
     * @param out_state   miner -> {B^{(e)}, rho^{(e)}} to carry into epoch e+1
     *                    (cleared first).
     */
    static void ComputeEpoch(const std::vector<ClusterInput>& inputs,
                             double theta,
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

        // Pass 1 — raw weights and their total.
        std::vector<double> raw(ordered.size(), 0.0);
        double total_raw = 0.0;
        for (size_t i = 0; i < ordered.size(); i++)
        {
            raw[i] = RawWeight(*ordered[i], params.kappa);
            total_raw += raw[i];
        }

        // Pass 2 — allocation, feedback, final weight, carried state.
        for (size_t i = 0; i < ordered.size(); i++)
        {
            const ClusterInput& in = *ordered[i];
            double Wk = raw[i];

            // Prior state: for epoch 1, B^{(0)} = 0 and there is no rho^{(0)}.
            double balance_prev = 0.0;
            double compliance_prev = 0.0;
            if (epoch >= 2)
            {
                std::map<std::string, ClusterState>::const_iterator it = prior.find(in.miner);
                if (it != prior.end())
                {
                    balance_prev = it->second.balance;
                    compliance_prev = it->second.compliance;
                }
            }

            double Ak = Allocation(params.alpha, theta, Wk, total_raw);
            double rho = ComplianceRate(in.reconciled, Ak, balance_prev);
            double Bk = Balance(in.reconciled, Ak, balance_prev);
            double wk = FinalWeight(Wk, compliance_prev, params.lambda, epoch);

            ClusterResult r;
            r.raw_weight = Wk;
            r.allocation = Ak;
            r.compliance = rho;
            r.balance = Bk;
            r.weight = wk;
            r.integer_weight = ToIntegerWeight(wk, params.kappa);

            out_results[in.miner] = r;
            out_state[in.miner] = ClusterState(Bk, rho);
        }
    }

private:

    /** Reconciled amount clamped to its legal domain [0, denom]. */
    static double ClampReconciled(double reconciled, double denom)
    {
        if (reconciled < 0.0)   return 0.0;
        if (reconciled > denom) return denom;
        return reconciled;
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

/** -weightalpha: allocation constant alpha in [0,1] (Def. allocazione). */
extern double g_weight_alpha;

/** -weightlambda: feedback damping lambda in [0,1) (Def. peso-finale). */
extern double g_weight_lambda;

#endif // MC_WEIGHT_ENGINE_H
