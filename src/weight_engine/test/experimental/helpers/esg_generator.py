# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# esg_generator.py -- deterministic ESG-score generation. Scores are drawn from a
# single seeded RNG (config.SEED) so a run is fully reproducible; they are STATIC
# across epochs (per the experiment spec: ESG never changes). Both companies and
# miners are scored, because the WeightEngine's raw weight
#   W_k = ESG_{Mk} * ( tau_{Mk} + sum_i ESG_i * tau_i / kappa )
# depends on the miner's OWN ESG as well as its companies' -- an uncertified miner
# (ESG 0) collapses to weight 0 -> floored to 1, which would flatten the whole
# experiment. See weight_engine.h.

import random

import config


def generate_scores(seed=None):
    """Return a dict label -> esg_score (2 decimals, in [ESG_MIN, ESG_MAX]) for
    every miner (M1..) and company (COMPANY_Mx_Cy). Deterministic in `seed`.

    Iteration order is fixed (miners then companies, ascending index) so the same
    seed always yields the same assignment regardless of Python's dict ordering."""
    rng = random.Random(config.SEED if seed is None else seed)
    scores = {}
    for m in range(config.NUM_MINERS):
        scores[config.miner_id(m)] = round(
            rng.uniform(config.ESG_MIN, config.ESG_MAX), 2)
        for c in range(config.COMPANIES_PER_MINER):
            scores[config.company_id(m, c)] = round(
                rng.uniform(config.ESG_MIN, config.ESG_MAX), 2)
    return scores
