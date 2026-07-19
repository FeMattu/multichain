// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.
//
// Weight-management layer — node-coupled glue.
// ------------------------------------------------------------------------------
// Definitions of the WeightEngine runtime configuration globals declared in
// weight_engine.h. They are bound to the WeightEngine chain parameters / CLI
// flags (params.dat baseline + runtime override) in AppInit2 (src/core/init.cpp),
// exactly like the wPoA globals in stream_weight_registry.cpp / wpoa_selector.cpp.
//
// The initializers are the compile-time defaults from weight_streams.h; AppInit2
// overwrites them with the resolved chain-parameter / flag values at startup. The
// remaining node glue (the stream reader, the per-epoch trigger, the publish path
// and ThreadWeightEngine) is added to this file in a later stage — the pure math
// core lives header-only in weight_engine.h so it stays unit-testable in isolation.

#include "weight_engine/weight_engine.h"

/** -enableweightengine (default off): when set, the engine computes and publishes
 *  w_k each epoch instead of the static per-node -weight. */
bool g_weight_engine_enabled = false;

/** -weightepochlength: epoch length in blocks (epoch(height) = height / this). */
int g_weight_epoch_length = MC_WEIGHT_DEFAULT_EPOCH_LENGTH;

/** -weightkappa: normalization constant kappa > 0. */
double g_weight_kappa = MC_WEIGHT_DEFAULT_KAPPA;

/** -weightalpha: allocation constant alpha in [0,1]. */
double g_weight_alpha = MC_WEIGHT_DEFAULT_ALPHA;

/** -weightlambda: feedback damping lambda in [0,1). */
double g_weight_lambda = MC_WEIGHT_DEFAULT_LAMBDA;
