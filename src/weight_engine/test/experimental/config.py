# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# config.py -- single source of truth for the WeightEngine experimental
# simulation. Everything tunable (topology, epoch geometry, RNG seed, transaction
# volumes, timeouts) lives here so a run is fully reproducible from this file plus
# the --mode flag. Values can be overridden from the environment (WE_* variables)
# so the harness mirrors the env-parameterised style of src/wpoa/test.
#
# ---------------------------------------------------------------------------
# MYLEDGER TOPOLOGY (this revision). The simulated network models MyLedger, not
# the original 4-miner/5-company sketch:
#
#   * 5 cluster miners      ClusterMinerA .. ClusterMinerE
#   * 10 companies each     Azienda_A1 .. Azienda_A10, Azienda_B1 .. etc (50 total)
#   * 1 ADMIN node          the Apuana SB stand-in: global admin, writer of the
#                           governance streams, reconciliation counterparty. NOT a
#                           miner (its mine permission is revoked once the miner
#                           set is live), so it never proposes a block.
#   * 1 FEE POOL address    the aggregate counterparty that settles transaction
#                           fees to the miners (see ECONOMICS below).
#
# ---------------------------------------------------------------------------
# ECONOMICS (GAS). 1 GAS == 1 EUR, and every network transaction costs
# ALPHA = 0.2 GAS, paid to the miner that validated it:
#
#   Guadagno_k^{(e)} = TxMiner_k^{(e)} * ALPHA        (earnings, EUR == GAS)
#   Resi_k^{(e)}     = Guadagno_k^{(e)} * RESO_RATE_k (returned to ADMIN)
#   %Reso_k^{(e)}    = Resi_k / Guadagno_k * 100      (conformity rate)
#   Giacenza_k^{(e)} = on-chain GAS balance of miner k AFTER reconciliation
#   TotalGAIN_k^{(e)}= sum of Guadagno_k over epochs 1..e
#
# A default MultiChain has no spendable native currency (initial-block-reward = 0),
# so GAS is modelled as a purpose-issued DIVISIBLE asset named GAS_ASSET_NAME with
# 1 unit == 1 EUR. This keeps the proven `sendassetfrom` activity path (which is
# also what the engine's undo-data tau metric counts) while giving exact 0.2-GAS
# granularity. Nothing else about the model depends on the asset-vs-native choice.
#
# ALPHA IS NOT A DIRECT WEIGHT INPUT. The engine's weight is
#   W_k = ESG_Mk * (tau_Mk + sum_i ESG_i*tau_i/kappa)   -- ESG + activity only
#   w_k = W_k * [rho_k^{(e-1)}*lambda + (1-lambda)]     -- feedback via compliance
# so ALPHA reaches the weight only through the allocation -> compliance -> feedback
# chain, never as a term of W_k. See docs/experiment.md.
#
# ---------------------------------------------------------------------------
# NOTE ON EPOCH GEOMETRY. The WeightEngine publishes a cluster's weight only for
# the newest *buried* epoch, i.e. epoch e is computable once the tip is at least
# STABILITY_MARGIN blocks past e's last block (weight_engine.cpp). The simulation
# therefore drives the chain a full epoch + margin ahead before it reads epoch e's
# weights. EPOCH_LENGTH must additionally be long enough to absorb one epoch's
# transaction volume (50 companies x TX_PER_COMPANY_MAX transfers).

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


def _env_float_list(name, default):
    """Parse WE_X="1.0,0.9,0.75" into a list of floats; fall back to `default`."""
    raw = os.environ.get(name)
    if not raw:
        return list(default)
    try:
        vals = [float(x) for x in raw.replace(";", ",").split(",") if x.strip() != ""]
    except ValueError:
        return list(default)
    return vals if vals else list(default)


def _env_str_list(name, default):
    raw = os.environ.get(name)
    if not raw:
        return list(default)
    vals = [x.strip() for x in raw.split(";") if x.strip() != ""]
    return vals if vals else list(default)


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
SEED = _env_int("WE_SEED", 42)          # drives ESG scores AND transaction picks

# ---------------------------------------------------------------------------
# Topology -- MyLedger: 5 cluster miners x 10 companies + 1 ADMIN (Apuana SB)
# ---------------------------------------------------------------------------
NUM_MINERS = _env_int("WE_MINERS", 5)                 # ClusterMinerA..E
COMPANIES_PER_MINER = _env_int("WE_COMPANIES", 10)     # 10 aziende per cluster -> 50
NUM_CLUSTERS = NUM_MINERS                              # alias used by the reporters

# Cluster naming. Letters run out at 26 clusters; beyond that fall back to indices.
CLUSTER_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Labels for the two non-cluster actors.
ADMIN_LABEL = "ADMIN"        # Apuana SB stand-in (reconciliation counterparty)
FEEPOOL_LABEL = "FEEPOOL"    # aggregate payer of the per-transaction ALPHA fees

# ---------------------------------------------------------------------------
# Epoch geometry / consensus timing
# ---------------------------------------------------------------------------
NUM_EPOCHS = _env_int("WE_EPOCHS", 30)               # >= 30 epochs, per the spec
EPOCH_LENGTH = _env_int("WE_EPOCH_LENGTH", 10)        # blocks per epoch (weightepochlength)
STABILITY_MARGIN = _env_int("WE_STABILITY_MARGIN", 6)  # MC_WEIGHT_DEFAULT_STABILITY_MARGIN
TARGET_BLOCK_TIME = _env_int("WE_BLOCK_TIME", 2)     # seconds (param minimum is 2)
# The native setup phase must be LONG in wpoa mode: while it lasts, mining is native
# (round-robin), which is what lets the admin publish the inputs and the miners
# establish their first weight. Once it ends, weighted selection governs -- and if no
# weight exists yet, NO miner qualifies and the chain deadlocks. So setup must comfortably
# outlast bootstrap + publish + first-weight; sampling then begins strictly AFTER it, so
# the sampled epochs are genuinely wPoA-governed. (Native mode is indifferent to this;
# the extra pre-sampling blocks are harmless.)
SETUP_FIRST_BLOCKS = _env_int("WE_SETUP_BLOCKS", 60)

# WeightEngine numeric parameters (must match on every node; passed as flags).
KAPPA = _env_float("WE_KAPPA", 100.0)
# ALPHA is BOTH the engine's allocation constant AND the MyLedger per-transaction
# cost in GAS (= EUR). One symbol, one value, so the two views stay reconcilable:
# sum_k Guadagno_k = ALPHA * Theta = sum_k A_k.
ALPHA = _env_float("WE_ALPHA", 0.2)
LAMBDA = _env_float("WE_LAMBDA", 0.5)

# ---------------------------------------------------------------------------
# GAS / currency model -- 1 GAS = 1 EUR
# ---------------------------------------------------------------------------
GAS_PER_EURO = 1.0                                   # direct 1:1 correspondence
GAS_ASSET_NAME = _env_str("WE_ASSET", "GAS")         # the simulated native currency
GAS_ASSET_UNITS = _env_float("WE_ASSET_UNITS", 0.0001)  # divisibility (>= ALPHA's precision)
GAS_TOTAL_SUPPLY = _env_int("WE_ASSET_TOTAL", 2000000)  # issued once, to the admin
GAS_DECIMALS = 4                                     # display / comparison precision
GAS_EPS = 1e-6                                       # tolerance for conservation checks

# Backwards-compatible aliases (older code / docs refer to these names).
ASSET_NAME = GAS_ASSET_NAME
ASSET_TOTAL = GAS_TOTAL_SUPPLY

FUND_PER_ADDR = _env_float("WE_FUND", 1000.0)        # GAS seeded to each participant
# The fee pool must cover every epoch's fee settlement:
#   NUM_EPOCHS * ALPHA * Theta_max, Theta_max = 50 companies * TX_PER_COMPANY_MAX.
FEEPOOL_FUND = _env_float("WE_FEEPOOL_FUND", 0.0)    # 0 -> derived (see below)

# ---------------------------------------------------------------------------
# ESG scores -- integers in [10, 20] per the MyLedger configuration sheet
# ---------------------------------------------------------------------------
ESG_MIN = _env_int("WE_ESG_MIN", 10)
ESG_MAX = _env_int("WE_ESG_MAX", 20)
# "ESG normalized" in the impact formula is ESG/KAPPA, exactly as the engine's
# c_i = ESG_i * tau_i / kappa (weight_engine.h). With ESG in [10,20] and
# kappa = 100 the per-transaction impact of a company lies in [0.10, 0.20].

# ISO certificate shown per cluster on the configuration sheet. Display-only: it
# never enters the weight (the certified ESG score is what the engine reads).
ISO_CERTIFICATES = _env_str_list(
    "WE_ISO_CERTS",
    ["ISO 14001", "ISO 14001 + ISO 50001", "ISO 9001", "ISO 14001", "non certificato"])

# ---------------------------------------------------------------------------
# Reconciliation -- per-cluster nominal conformity ("Reso" column of the config
# sheet). Resi_k = Guadagno_k * RESO_RATES[k], so %Reso is deterministic, in
# [0,1] by construction, and spread across clusters so the lambda-feedback on
# w_k is visible in the output. Extra clusters beyond the list reuse the last rate.
# ---------------------------------------------------------------------------
RESO_RATES = _env_float_list("WE_RESO_RATES", [1.00, 0.90, 0.75, 0.60, 0.40])
# Small deterministic jitter (fraction of the nominal rate) so %Reso is not a flat
# line across epochs; 0 disables it. Seeded from SEED -> reproducible.
RESO_JITTER = _env_float("WE_RESO_JITTER", 0.05)

# ---------------------------------------------------------------------------
# Transaction simulation (per epoch)
# ---------------------------------------------------------------------------
# Every company sends TX_PER_COMPANY_MIN..MAX transfers per epoch (the config
# sheet's "Numero minimo/massimo Tx"). This is the activity that produces both the
# engine's tau_i and the network's Theta.
TX_PER_COMPANY_MIN = _env_int("WE_TX_MIN", 10)
TX_PER_COMPANY_MAX = _env_int("WE_TX_MAX", 20)
# Miner<->miner transfers keep tau_{Mk} non-degenerate (the miner's own activity
# term of W_k). Small on purpose: the cluster's weight should be driven by its
# companies, not by the miner trading with itself.
TX_MINER_MIN = _env_int("WE_TX_MINER_MIN", 2)
TX_MINER_MAX = _env_int("WE_TX_MINER_MAX", 4)

# Per-transfer GAS amount (micro-payments; small so nobody runs dry over 30 epochs).
TX_AMOUNT_MIN = _env_float("WE_AMOUNT_MIN", 0.01)
TX_AMOUNT_MAX = _env_float("WE_AMOUNT_MAX", 0.10)

# Number of WAVES an epoch's transactions are submitted in, spread one block apart.
#
# This is not a performance knob, it is a CORRECTNESS one. Submitting a whole epoch's
# traffic in a single burst (which takes well under a second over JSON-RPC) puts every
# transaction in the ONE block that follows, so TxMiner -- and with it Guadagno, Resi and
# Giacenza -- becomes a lottery on who happened to mine that block, instead of tracking
# validation work: one cluster collects the epoch's entire fee income and the others get
# zero. Spreading the submissions across the epoch's blocks makes TxMiner proportional to
# blocks proposed, which is what the MyLedger fee model means. 0 or 1 restores the old
# single-burst behaviour.
TX_WAVES = _env_int("WE_TX_WAVES", 0)   # 0 -> derived, see tx_waves()

# Legacy aliases kept so older invocations of the env knobs still do something
# sensible (company-to-company volume is now per-company, see TX_PER_COMPANY_*).
TX_COMPANY_MIN = TX_PER_COMPANY_MIN
TX_COMPANY_MAX = TX_PER_COMPANY_MAX

# ---------------------------------------------------------------------------
# Timeouts / pacing (seconds)
# ---------------------------------------------------------------------------
RPC_TIMEOUT = _env_int("WE_RPC_TIMEOUT", 60)         # wait for a node's RPC to come up
CONNECT_TIMEOUT = _env_int("WE_CONNECT_TIMEOUT", 40)  # wait for a node to (re)join
WEIGHT_TIMEOUT = _env_int("WE_WEIGHT_TIMEOUT", 300)  # wait for all miners to publish a weight
DRIVE_TIMEOUT = _env_int("WE_DRIVE_TIMEOUT", 600)    # wait to reach a target height
CONFIRM_TIMEOUT = _env_int("WE_CONFIRM_TIMEOUT", 60)  # wait for a tx to confirm

# ---------------------------------------------------------------------------
# Invariant thresholds (see experimental_test.py _verify)
# ---------------------------------------------------------------------------
# Minimum fraction of cluster PAIRS whose engine-weight ordering must agree with the
# ESG+activity composite ordering. Below 1.0 on purpose: the final weight applies a
# per-cluster feedback factor rho*lambda + (1-lambda) in [1-lambda, 1], which can
# legitimately reorder clusters whose raw weights are close together.
RANK_CONCORDANCE_MIN = _env_float("WE_RANK_MIN", 0.80)

# ---------------------------------------------------------------------------
# Derived helpers
# ---------------------------------------------------------------------------
VALID_MODES = ("wpoa", "native")


def num_companies():
    """Total companies on the network (50 in the MyLedger default)."""
    return NUM_MINERS * COMPANIES_PER_MINER


def theta_max():
    """Upper bound on one epoch's company activity Theta (all companies at TX max)."""
    return num_companies() * TX_PER_COMPANY_MAX


def feepool_fund():
    """GAS the fee pool needs to settle every epoch's fees, with 50% head-room.

    Guadagno totals ALPHA * Theta per epoch, so the pool must hold
    NUM_EPOCHS * ALPHA * theta_max; the margin covers the extra epochs the harness
    drives through during setup/burial."""
    if FEEPOOL_FUND > 0:
        return FEEPOOL_FUND
    return round(1.5 * (NUM_EPOCHS + 4) * ALPHA * theta_max(), GAS_DECIMALS)


def tx_waves():
    """How many waves to spread an epoch's submissions over (>= 1).

    Defaults to EPOCH_LENGTH - 2, leaving two blocks of slack at the end of the epoch so
    the final wave still confirms inside it."""
    if TX_WAVES > 0:
        return TX_WAVES
    return max(1, EPOCH_LENGTH - 2)


def reso_rate(miner_idx):
    """Nominal conformity rate of cluster `miner_idx` (clamped to [0,1])."""
    if not RESO_RATES:
        return 0.0
    r = RESO_RATES[miner_idx] if miner_idx < len(RESO_RATES) else RESO_RATES[-1]
    return max(0.0, min(1.0, r))


def iso_certificate(miner_idx):
    """Display-only ISO certificate of cluster `miner_idx`."""
    if not ISO_CERTIFICATES:
        return ""
    return (ISO_CERTIFICATES[miner_idx] if miner_idx < len(ISO_CERTIFICATES)
            else ISO_CERTIFICATES[-1])


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


def cluster_letter(miner_idx):
    """'A'..'Z' for the first 26 clusters, then a bare index."""
    if 0 <= miner_idx < len(CLUSTER_LETTERS):
        return CLUSTER_LETTERS[miner_idx]
    return str(miner_idx + 1)


def miner_id(miner_idx):
    """Canonical cluster-miner label ClusterMiner{A..E} (MyLedger naming)."""
    return "ClusterMiner%s" % cluster_letter(miner_idx)


def company_id(miner_idx, company_idx):
    """Canonical company label Azienda_{A..E}{1..10} (MyLedger naming)."""
    return "Azienda_%s%d" % (cluster_letter(miner_idx), company_idx + 1)


def company_display(company_idx):
    """The name shown in the 'Nome utente' column of a report sheet."""
    return "Azienda %d" % (company_idx + 1)
