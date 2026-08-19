// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — Stage W1: stream identifiers, JSON field names and
// pipeline parameter defaults.
// ------------------------------------------------------------------------------
// The weight-calculation layer sits ABOVE the wPoA consensus (src/wpoa). Each
// epoch it reads a set of public on-chain INPUT streams — membership (which
// company belongs to which miner/cluster), ESG (the static certified scores),
// activity (the per-epoch transaction counters tau) and reconciliation (the
// per-epoch reconciled allocation R) — computes the per-cluster weight
// w_k^{(e)} following the "Gestione del peso" thesis chapter, and publishes the
// result to the SAME "wpoa-weights" stream the consensus already consumes
// (wpoa/stream_weight_registry.h). The consensus never learns HOW w_k is
// produced: the two layers are coupled only through the wpoa-weights stream.
//
// The four input streams are deliberately named "weight-engine-*", NOT "wpoa-*":
// they are owned and fed by the weight layer and its external actors (the
// certifier, the activity aggregator, the reconciliation process), not by the
// consensus. Only the OUTPUT stream "wpoa-weights" belongs to wPoA. This mirrors
// the folder split (src/weight_engine vs src/wpoa) at the on-chain contract level.
//
// This header holds only names and #define defaults (no logic), so it can be
// included by both the pure record helpers (weight_records.h) and the node glue
// (weight_engine.cpp) without dragging in any dependency.

#ifndef MC_WEIGHT_STREAMS_H
#define MC_WEIGHT_STREAMS_H

// ---------------------------------------------------------------------------
// Input streams read by the WeightEngine each epoch
// ---------------------------------------------------------------------------

/** company -> miner association (static, updated only on cluster change).
 *  Item key = miner address; payload {"json":{"<azienda_addr>": <ts>, ...}}.
 *  Native jsonobjectmerge (getstreamkeysummary / mc_MergeValues) folds every
 *  item published under a miner key into a single object whose FIELD NAMES are
 *  the associated company addresses — reconstructing the cluster set C_k
 *  (Def. peso-grezzo). See mc_ParseMembershipClusterJson in weight_records.h. */
#define MC_WEIGHT_MEMBERSHIP_STREAM_NAME     "weight-engine-membership"

/** Certified ESG scores (static between epochs, Def. esg-static). Item key =
 *  node address (company or miner); payload {"json":{"node_address":..,"esg":..}}. */
#define MC_WEIGHT_ESG_STREAM_NAME            "weight-engine-esg"

/** Per-epoch activity counters tau_i^{(e)} (Def. attivita-partecipazione).
 *  Item key = node address;
 *  payload {"json":{"node_address":..,"tau":..,"epoch":..}}. */
#define MC_WEIGHT_ACTIVITY_STREAM_NAME       "weight-engine-activity"

/** Per-epoch reconciled allocation R_k^{(e)} (Def. riconciliazione). Item key =
 *  miner address; payload {"json":{"node_address":..,"reconciled":..,"epoch":..}}. */
#define MC_WEIGHT_RECONCILIATION_STREAM_NAME "weight-engine-reconciliation"

// ---------------------------------------------------------------------------
// Output stream (owned by src/wpoa; reused as the publication port)
// ---------------------------------------------------------------------------
// The final weight w_k^{(e)} is written to MC_WPOA_WEIGHTS_STREAM_NAME
// ("wpoa-weights") via StreamWeightRegistry, exactly like the static -weight
// value it replaces. See wpoa/stream_weight_registry.h.

// ---------------------------------------------------------------------------
// JSON field names (single source of truth)
// ---------------------------------------------------------------------------
// Shared by this reader and the Phase-W3 writer, so a producer and consumer can
// never drift on a field name. The parsers in weight_records.h use these.

#define MC_WEIGHT_FIELD_NODE_ADDR   "node_address"
#define MC_WEIGHT_FIELD_ESG         "esg"
#define MC_WEIGHT_FIELD_TAU         "tau"
#define MC_WEIGHT_FIELD_EPOCH       "epoch"
#define MC_WEIGHT_FIELD_RECONCILED  "reconciled"

// ---------------------------------------------------------------------------
// Weight-pipeline configuration parameters (DEFAULTS ONLY)
// ---------------------------------------------------------------------------
// CONSENSUS-CRITICAL: every honest node MUST use identical values, or nodes
// compute different w_k and disagree on the elected proposer (the chain forks).
// Like g_dumping_function in the selector, each parameter will be bound to its
// runtime flag in exactly one place (AppInit2, Phase W3) and threaded explicitly
// into the otherwise-pure WeightEngine core (Phase W2) — the core never reads a
// global. This header carries only the DEFAULT values; the constraint
// ENFORCEMENT (0<=lambda<1, alpha in (0,1], kappa>0, epochlen>=1) lives at
// flag-parse time in W3, not here.
//
// The math is carried in double precision, matching the existing selector core
// (wpoa_selector.h ScoreFromEntropy64), which already treats IEEE-754 double as
// deterministic across the (identical-binary) validator set.

/** kappa > 0: normalization constant for the weighted company contribution
 *  c_i = ESG_i * tau_i / kappa (Def. contributo-pesato). */
#define MC_WEIGHT_DEFAULT_KAPPA          100.0

/** alpha in (0,1]: protocol constant scaling the epoch allocation
 *  A_k = alpha * Theta * W_k / W_tot (Def. allocazione). 0.2 mirrors the 20%
 *  reward share of the reference Vers_2 simulation. */
#define MC_WEIGHT_DEFAULT_ALPHA          0.2

/** lambda in [0,1): behavioral-feedback damping in
 *  w_k = W_k * [ rho_{k,e-1} * lambda + (1 - lambda) ] (Def. peso-finale). The
 *  strict lambda < 1 is a CORRECTNESS requirement (Prop. positivita-peso),
 *  enforced when the flag is parsed. 0.5 mirrors "Peso %Reso" = 50 in Vers_2. */
#define MC_WEIGHT_DEFAULT_LAMBDA         0.5

/** Epoch length in blocks: epoch(height) = height / MC_WEIGHT_DEFAULT_EPOCH_LENGTH.
 *  Read from the chain param "weightepochlength" when present so the miner and
 *  every validator derive the same epoch from the height alone (Section
 *  epochs_slots). Must be >= 1. */
#define MC_WEIGHT_DEFAULT_EPOCH_LENGTH   100

/** Stability margin in blocks. The activity counter tau is derived from the
 *  confirmed blocks of an epoch (weight_reader.cpp ComputeActivityForEpoch); to
 *  keep that derivation identical on every node, an epoch is only computed once it
 *  is BURIED — its last block is at least this many blocks below the chain tip —
 *  so a shallow reorg near the tip can never make two nodes read different blocks.
 *  MUST be >= the deepest reorg the chain can undergo and identical on every node.
 *  Held as a compile-time constant (identical across the single binary version);
 *  promote to a params.dat-hashed chain parameter before production, alongside
 *  weightepochlength. */
#define MC_WEIGHT_DEFAULT_STABILITY_MARGIN   6

#endif // MC_WEIGHT_STREAMS_H
