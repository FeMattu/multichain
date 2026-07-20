# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# config.py -- single source of truth for the WeightEngine experimental
# simulation. Everything tunable (topology, epoch geometry, RNG seed, transaction
# volumes, timeouts) lives here so a run is fully reproducible from this file plus
# the --mode flag. Values can be overridden from the environment (WE_* variables)
# so the harness mirrors the env-parameterised style of src/wpoa/test.
#
# NOTE ON EPOCH GEOMETRY. The WeightEngine publishes a cluster's weight only for
# the newest *buried* epoch, i.e. epoch e is computable once the tip is at least
# STABILITY_MARGIN blocks past e's last block (weight_engine.cpp). The simulation
# therefore drives the chain a full epoch + margin ahead before it reads epoch e's
# weights. Keep EPOCH_LENGTH small so 12 epochs stay quick, but >= a couple of
# blocks so each epoch contains room for the simulated transactions.

import os


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_str(name, default):
    v = os.environ.get(name)
    return v if v else default


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
SEED = _env_int("WE_SEED", 42)          # drives ESG scores AND transaction picks

# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------
NUM_MINERS = _env_int("WE_MINERS", 4)               # M1..M4 (mining nodes)
COMPANIES_PER_MINER = _env_int("WE_COMPANIES", 5)    # 5 companies per miner -> 20
# The admin is node 0: the genesis node, a global administrator, and the ONLY
# writer of the esg/membership/reconciliation streams. It is NOT a miner: its mine
# permission is revoked once the miner set is live, so it never proposes a block.

# ---------------------------------------------------------------------------
# Epoch geometry / consensus timing
# ---------------------------------------------------------------------------
NUM_EPOCHS = _env_int("WE_EPOCHS", 12)              # epochs to simulate + report
EPOCH_LENGTH = _env_int("WE_EPOCH_LENGTH", 6)        # blocks per epoch (weightepochlength)
STABILITY_MARGIN = _env_int("WE_STABILITY_MARGIN", 6)  # MC_WEIGHT_DEFAULT_STABILITY_MARGIN
TARGET_BLOCK_TIME = _env_int("WE_BLOCK_TIME", 2)     # seconds (param minimum is 2)
# The native setup phase must be LONG in wpoa mode: while it lasts, mining is native
# (round-robin), which is what lets the admin publish the inputs and the miners
# establish their first weight. Once it ends, weighted selection governs -- and if no
# weight exists yet, NO miner qualifies and the chain deadlocks. So setup must comfortably
# outlast bootstrap + publish + first-weight (~25-30 blocks here); sampling then begins
# strictly AFTER it, so the sampled epochs are genuinely wPoA-governed. (Native mode is
# indifferent to this; the extra pre-sampling blocks are harmless.)
SETUP_FIRST_BLOCKS = _env_int("WE_SETUP_BLOCKS", 40)

# WeightEngine numeric parameters (must match on every node; passed as flags).
KAPPA = _env_float("WE_KAPPA", 100.0)
ALPHA = _env_float("WE_ALPHA", 0.2)
LAMBDA = _env_float("WE_LAMBDA", 0.5)

# ---------------------------------------------------------------------------
# ESG scores
# ---------------------------------------------------------------------------
ESG_MIN = _env_float("WE_ESG_MIN", 1.0)     # strictly > 0 (engine rejects <= 0)
ESG_MAX = _env_float("WE_ESG_MAX", 100.0)

# ---------------------------------------------------------------------------
# Transaction simulation (per epoch)
# ---------------------------------------------------------------------------
TX_COMPANY_MIN = _env_int("WE_TX_COMPANY_MIN", 3)   # 3-7 company<->company transfers
TX_COMPANY_MAX = _env_int("WE_TX_COMPANY_MAX", 7)
TX_MINER_MIN = _env_int("WE_TX_MINER_MIN", 3)       # 3-7 miner<->miner transfers
TX_MINER_MAX = _env_int("WE_TX_MINER_MAX", 7)
TX_ASSET_MIN = _env_int("WE_TX_ASSET_MIN", 1)       # 1-2 symbolic asset transfers
TX_ASSET_MAX = _env_int("WE_TX_ASSET_MAX", 2)

ASSET_NAME = _env_str("WE_ASSET", "weasset")        # asset issued to move value around
ASSET_TOTAL = _env_int("WE_ASSET_TOTAL", 1000000)   # total units issued to admin
FUND_PER_ADDR = _env_int("WE_FUND", 1000)           # asset units seeded to each participant
TX_AMOUNT_MIN = _env_int("WE_AMOUNT_MIN", 1)        # per-transfer asset amount range
TX_AMOUNT_MAX = _env_int("WE_AMOUNT_MAX", 10)

# ---------------------------------------------------------------------------
# Timeouts / pacing (seconds)
# ---------------------------------------------------------------------------
RPC_TIMEOUT = _env_int("WE_RPC_TIMEOUT", 60)         # wait for a node's RPC to come up
CONNECT_TIMEOUT = _env_int("WE_CONNECT_TIMEOUT", 40)  # wait for a node to (re)join
WEIGHT_TIMEOUT = _env_int("WE_WEIGHT_TIMEOUT", 240)  # wait for all miners to publish a weight
DRIVE_TIMEOUT = _env_int("WE_DRIVE_TIMEOUT", 400)    # wait to reach a target height
CONFIRM_TIMEOUT = _env_int("WE_CONFIRM_TIMEOUT", 60)  # wait for a tx to confirm

# ---------------------------------------------------------------------------
# Derived helpers
# ---------------------------------------------------------------------------
VALID_MODES = ("wpoa", "native")


def epoch_range(epoch):
    """Block-height range [start, end] of a 1-based epoch, matching the engine's
    epoch(height) = height / EPOCH_LENGTH + 1 mapping."""
    start = (epoch - 1) * EPOCH_LENGTH
    end = epoch * EPOCH_LENGTH - 1
    return start, end


def height_to_epoch(height):
    """epoch(height) = height / EPOCH_LENGTH + 1  (mirror of HeightToEpoch)."""
    if height < 0:
        height = 0
    return height // EPOCH_LENGTH + 1


def buried_epoch(tip_height):
    """Largest epoch fully buried under STABILITY_MARGIN at the given tip, i.e. the
    epoch the engine would currently publish. 0 if none buried yet."""
    stable = tip_height - STABILITY_MARGIN
    if stable < 0:
        return 0
    return (stable + 1) // EPOCH_LENGTH


def node_args(mode):
    """The wPoA / WeightEngine flags a node is launched with, per mode.

    wpoa   : master switch on  -> weights drive weighted proposer selection.
    native : master off, weights stream + engine on -> native round-robin mining
             while the engine still computes and publishes w_k to wpoa-weights.
    """
    common = [
        "-enableweightengine=1",
        "-weightepochlength=%d" % EPOCH_LENGTH,
        "-weightkappa=%g" % KAPPA,
        "-weightalpha=%g" % ALPHA,
        "-weightlambda=%g" % LAMBDA,
        "-debug=wpoa",
    ]
    if mode == "wpoa":
        return ["-enablewpoa=1"] + common
    # native: weights stream explicitly on (engine requires it), master off.
    return ["-enablewpoaweights=1"] + common


def company_id(miner_idx, company_idx):
    """Canonical company label COMPANY_M{miner}_C{company} (1-based)."""
    return "COMPANY_M%d_C%d" % (miner_idx + 1, company_idx + 1)


def miner_id(miner_idx):
    """Canonical miner label M{n} (1-based)."""
    return "M%d" % (miner_idx + 1)
