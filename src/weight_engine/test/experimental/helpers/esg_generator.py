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
#
# CHANGED FROM THE ORIGINAL (Apuana SB) SETUP. Scores are now INTEGERS in
# [ESG_MIN, ESG_MAX] = [10, 20], matching the MyLedger configuration sheet's
# "Score minimo/massimo ESG" instead of the previous 2-decimal draw over [1, 100].
# The engine only requires ESG > 0, so the narrower integer band changes the scale
# of W_k but not the algebra; with kappa = 100 a company's per-transaction impact
# ESG_i/kappa lands in [0.10, 0.20].

import random

import config


def generate_scores(seed=None):
    """Return a dict label -> esg_score (integer in [ESG_MIN, ESG_MAX]) for every
    cluster miner (ClusterMinerA..) and company (Azienda_X1..). Deterministic in
    `seed`.

    Iteration order is fixed (miner then its companies, ascending index) so the same
    seed always yields the same assignment regardless of Python's dict ordering.
    ADMIN and FEEPOOL are deliberately absent: they are not cluster members, hold no
    certified score, and must never enter a weight."""
    rng = random.Random(config.SEED if seed is None else seed)
    lo, hi = int(config.ESG_MIN), int(config.ESG_MAX)
    if hi < lo:
        lo, hi = hi, lo
    scores = {}
    for m in range(config.NUM_MINERS):
        scores[config.miner_id(m)] = rng.randint(lo, hi)
        for c in range(config.COMPANIES_PER_MINER):
            scores[config.company_id(m, c)] = rng.randint(lo, hi)
    return scores


def normalized_esg(score):
    """"ESG normalized" as the impact formula uses it: ESG / kappa, i.e. exactly the
    per-transaction factor of the engine's c_i = ESG_i * tau_i / kappa. Keeping this
    in one place stops the report and the harness drifting apart."""
    return (score / config.KAPPA) if config.KAPPA else 0.0


def cluster_config_rows(scores):
    """The configuration-sheet view of the static inputs: one row per cluster with
    its ESG score, ISO certificate, nominal Reso rate and its 10 companies.

    Returns a list of dicts (ordered A..E) -- consumed by the CSV reporter and by
    make_report.py's "Foglio di configurazione"."""
    rows = []
    for m in range(config.NUM_MINERS):
        mlabel = config.miner_id(m)
        companies = []
        for c in range(config.COMPANIES_PER_MINER):
            clabel = config.company_id(m, c)
            companies.append({
                "label": clabel,
                # Derived from the LABEL, not from the loop index. It is the same value
                # here (this loop walks the canonical topology in order), but keeping one
                # rule everywhere means a future reordering cannot relabel Azienda_A10
                # as "Azienda 3" -- which is exactly what happened once the cluster sets
                # started arriving from the membership stream in address order.
                "display": config.company_display_for(clabel),
                "esg": scores.get(clabel, 0),
            })
        rows.append({
            "miner": mlabel,
            "letter": config.cluster_letter(m),
            "esg": scores.get(mlabel, 0),
            "iso": config.iso_certificate(m),
            "reso_rate": config.reso_rate(m),
            "companies": companies,
        })
    return rows
