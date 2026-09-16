"""Load, validate and expand an experiment profile.

The profile is the harness's only input. Everything else — ports, datadirs, the
``params.dat`` body, the GAS budgets, the per-process RNG seeds — is *derived* here, so
that no network or node parameter is ever hardcoded in the code that uses it.

Validation is deliberately strict. MultiChain silently ignores an unknown key in
``params.dat``, so a typo would run the chain with the default and the mistake would
surface, if at all, as an inexplicable result three phases later. Every wPoA and
WeightEngine key is therefore checked against the catalogue below, which was taken from
``src/chainparams/paramlist.h`` and confirmed against a ``params.dat`` emitted by the
real ``multichain-util``.

See ``test/config/schema.md`` for the field reference and ``test/docs/architecture-notes.md``
for why the defaults are what they are.
"""

from __future__ import annotations

import hashlib
import math
import os
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# --------------------------------------------------------------------------------------
# Compile-time constants of the node. NOT configurable — they must match the binary.
# --------------------------------------------------------------------------------------

#: ``MC_WEIGHT_DEFAULT_STABILITY_MARGIN`` (src/weight_engine/weight_streams.h). An epoch
#: is only computed once its last block is this many blocks below the tip, so that a
#: shallow reorg near the tip cannot make two nodes read different blocks.
STABILITY_MARGIN = 6

#: ``MC_WEIGHT_SETUP_PUBLISH_MARGIN``. Slack the ``setup-first-blocks`` floor adds on top
#: of the epoch geometry, covering the engine tick, the confirming block and propagation.
SETUP_PUBLISH_MARGIN = 3

#: Raw units per display unit of native currency (``native-currency-multiple``).
COIN = 100_000_000

#: The Certification Authority role (``MC_WEIGHT_CA_PERMISSION_NAME``).
CA_PERMISSION = "high1"

#: Stream names owned by the protocol. Written by the harness, never by the profile.
STREAM_WEIGHTS = "wpoa-weights"
STREAM_MEMBERSHIP = "weight-engine-membership"
STREAM_ESG = "weight-engine-esg"
STREAM_MALUS = "wpoa-weights-malus"

#: The activation flags. Hardcoded on, and rejected if a profile mentions them.
ACTIVATION_KEYS = (
    "enable-wpoa",
    "enable-wpoa-weights",
    "enable-wpoa-selection",
    "enable-wpoa-vrf",
    "enable-wpoa-randao",
    "enable-wpoa-sortition",
    "enable-wpoa-malus",
    "enable-weight-engine",
)

# --------------------------------------------------------------------------------------
# Parameter catalogue
# --------------------------------------------------------------------------------------
# (default, kind, low, high, low_inclusive, high_inclusive). ``kind`` is one of
# "bool" | "int" | "float" | "enum". For "enum", ``low`` holds the allowed values.


class ConfigError(ValueError):
    """A profile that cannot be run. Raised with a message naming the offending field."""


_WPOA_PARAMS: Dict[str, tuple] = {
    "dump-function": (("none", "sqrt", "log"), "enum"),
    # Must be >= 1 because sortition is always on in this harness.
    "wpoa-randao-lookback": (None, "int", 1, 1_000_000, True, True),
    "wpoa-sortition-delta": (0.5, "float", 0.0, 1.0, False, False),
    "wpoa-sortition-lambda": (0.0, "float", 0.0, 1.0, True, True),
    "wpoa-malus-mu": (0.5, "float", 0.0, 1.0, True, False),
    "wpoa-malus-max": (4.0, "float", 0.0, 1e18, False, False),
    "wpoa-malus-equiv-points": (4.0, "float", 0.0, 1e18, False, False),
    "wpoa-malus-delay-points": (0.25, "float", 0.0, 1e18, False, False),
    "wpoa-malus-selfwrite-points": (1.0, "float", 0.0, 1e18, False, False),
    "wpoa-malus-badweight-points": (2.0, "float", 0.0, 1e18, False, False),
}

_WEIGHT_ENGINE_PARAMS: Dict[str, tuple] = {
    "weight-kappa": (100.0, "float", 0.0, 1e18, False, False),
    # Parsed and validated by the node, then never read. Kept because removing a
    # hash-enforced field would make existing chains unjoinable.
    "weight-alpha": (0.2, "float", 0.0, 1.0, True, True),
    # lambda < 1 is a correctness requirement (weight positivity), not a preference.
    "weight-lambda": (0.5, "float", 0.0, 1.0, True, False),
}

_CHAIN_PARAMS: Dict[str, tuple] = {
    "target-block-time": (2, "int", 2, 86_400, True, True),
    "mining-diversity": (0.0, "float", 0.0, 1.0, True, True),
    "mining-turnover": (0.5, "float", 0.0, 1.0, True, True),
    "mine-empty-rounds": (-1, "int", -1, 1000, True, True),
    "mining-requires-peers": (False, "bool"),
    "lock-admin-mine-rounds": (10, "int", 0, 10_000, True, True),
    "first-block-reward": (100_000_000_000_000, "int", -1, 10**18, True, True),
    "initial-block-reward": (0, "int", 0, 10**18, True, True),
    "minimum-relay-fee": (20_000_000, "int", 0, 1_000_000_000, True, True),
    "anyone-can-connect": (False, "bool"),
    # None means "derive"; see Profile.setup_first_blocks.
    "setup-first-blocks": (None, "int", 1, 31_536_000, True, True),
}

#: ``weight-epoch-length`` is spelled ``epochs.length_blocks`` and ``weight-treasury-address``
#: is created at runtime, so both are rejected with a message pointing at the real field.
_RELOCATED = {
    "weight-epoch-length": "epochs.length_blocks",
    "weight-treasury-address": "the harness (a dedicated address is created at bootstrap)",
}

_TOP_LEVEL = {
    "seed",
    "chain_name",
    "nodes",
    "network",
    "epochs",
    "chain",
    "wpoa",
    "weight_engine",
    "traffic",
    "runtime",
}

_TRAFFIC_DEFAULTS: Dict[str, Any] = {
    "event_stream": "supply-chain-events",
    "company_tx_per_epoch_range": [30, 60],
    "miner_gas_returns_per_epoch_range": [0, 5],
    "esg_score_range": [1, 100],
    "restitution_amount_range": [1.0, 9.0],
}

_RUNTIME_DEFAULTS: Dict[str, Any] = {
    "bindir": "src",
    "chain_home": None,          # default: <run_dir>/chains
    "results_root": "test/results",
    "rpc_timeout_s": 30,
    "startup_timeout_s": 120,
    "shutdown_grace_s": 30,
    "wpoa_debug": False,
}

_CHAIN_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


# --------------------------------------------------------------------------------------
# Node description
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Node:
    """One ``multichaind`` process.

    ``index`` fixes the port assignment, so a given profile always produces the same
    node-to-port map and two runs are comparable without a lookup table.
    """

    index: int
    role: str          # admin | ca | miner | company
    role_index: int    # 0-based within the role
    node_id: str       # e.g. "miner-2"; also the log directory name
    port: int
    rpc_port: int

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


# --------------------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------------------


@dataclass
class Profile:
    """A validated profile with every derived quantity the harness needs."""

    path: Path
    seed: int
    chain_name: str
    ca_count: int
    miner_count: int
    company_count: int
    host: str
    base_port: int
    base_rpc_port: int
    epoch_count: int
    epoch_length: int
    chain_params: Dict[str, Any]
    wpoa_params: Dict[str, Any]
    weight_engine_params: Dict[str, Any]
    traffic: Dict[str, Any]
    runtime: Dict[str, Any]
    nodes: List[Node] = field(default_factory=list)

    # -- topology ----------------------------------------------------------------------

    @property
    def node_count(self) -> int:
        return 1 + self.ca_count + self.miner_count + self.company_count

    @property
    def admin(self) -> Node:
        return self.nodes[0]

    def by_role(self, role: str) -> List[Node]:
        return [n for n in self.nodes if n.role == role]

    def node(self, node_id: str) -> Node:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        raise KeyError(node_id)

    @property
    def seed_node_address(self) -> str:
        """What a joining node dials.

        Loopback explicitly: ``getinfo``'s ``nodeaddress`` can report a NAT address when
        the host is containerised, and a joining node would then dial an unreachable one.
        """
        return "%s@%s:%d" % (self.chain_name, self.host, self.admin.port)

    # -- chain parameters --------------------------------------------------------------

    @property
    def target_block_time(self) -> int:
        return int(self.chain_params["target-block-time"])

    @property
    def min_relay_fee_raw(self) -> int:
        return int(self.chain_params["minimum-relay-fee"])

    @property
    def fee_per_kb(self) -> float:
        """Display units of native currency per 1000 bytes."""
        return self.min_relay_fee_raw / COIN

    @property
    def maxtxfee(self) -> float:
        """Wallet policy, ten times the relay fee of a 1 KB transaction.

        Not consensus: it belongs on the command line and may differ per node. Without
        it every publish above ~500 bytes fails with "Transaction too large for fee
        policy" while plain transfers keep working — the network looks healthy and no
        record is ever written. Derived from the configured fee so the two cannot drift.
        """
        return round(self.fee_per_kb * 10, 8)

    @property
    def protocol_setup_floor(self) -> int:
        """The floor the node itself applies at genesis (``AdjustSetupFirstBlocks``)."""
        return self.epoch_length + STABILITY_MARGIN - 1 + SETUP_PUBLISH_MARGIN + 1

    @property
    def setup_first_blocks(self) -> int:
        """Configured value, or a budget covering the wall-clock bootstrap.

        The protocol floor covers the epoch geometry only — when the first weight *can*
        confirm. It cannot know how long starting N daemons and confirming their grants
        takes, and past a handful of nodes that is the larger of the two: the chain
        reaches the floor with an empty registry, wPoA elects nobody and stops dead.
        """
        configured = self.chain_params.get("setup-first-blocks")
        if configured is not None:
            return max(int(configured), self.protocol_setup_floor)
        tbt = self.target_block_time
        boot_s = 6 * self.node_count // 2 + 60
        inputs_s = 12 * tbt + self.node_count
        need = (boot_s + inputs_s) // tbt
        need = (need + self.protocol_setup_floor) * 3 // 2
        return max(need, self.protocol_setup_floor)

    # -- epoch geometry ----------------------------------------------------------------

    def epoch_of_height(self, height: int) -> int:
        """1-based epoch containing ``height``."""
        return height // self.epoch_length

    def last_buried_epoch(self, tip: int) -> int:
        """Newest epoch the engine can have computed at this tip. 0 = nothing buried."""
        stable = tip - STABILITY_MARGIN
        if stable < 0:
            return 0
        return (stable + 1) // self.epoch_length

    def height_of_buried_epoch(self, epoch: int) -> int:
        """Tip height at which ``epoch`` first becomes buried."""
        return epoch * self.epoch_length + STABILITY_MARGIN - 1

    @property
    def target_height(self) -> int:
        """Where the run stops.

        One epoch beyond the last sampled one, so that the last one is itself buried and
        verifiable, plus the stability margin and the publication slack.
        """
        verify = self.height_of_buried_epoch(self.epoch_count + 1)
        return max(
            verify + STABILITY_MARGIN + SETUP_PUBLISH_MARGIN * 3,
            self.setup_first_blocks + self.epoch_length,
        )

    # -- GAS budgets -------------------------------------------------------------------

    @property
    def gas_per_tx(self) -> float:
        """One KB per transaction: a deliberate over-estimate.

        Over-funding costs nothing; under-funding voids the run, because a company that
        runs dry mid-epoch stops generating tau and that epoch's weight silently
        understates it.
        """
        return self.fee_per_kb

    @property
    def gas_floor(self) -> float:
        """Refuel trigger: enough for one further worst-case epoch."""
        tx_max = self.traffic["company_tx_per_epoch_range"][1]
        return round(tx_max * self.gas_per_tx * 2, 4)

    @property
    def gas_seed(self) -> float:
        tx_max = self.traffic["company_tx_per_epoch_range"][1]
        return round(tx_max * self.gas_per_tx * self.epoch_count * 1.5 + 50, 4)

    @property
    def gas_topup(self) -> float:
        return round(self.gas_seed / 2, 4)

    @property
    def miner_seed_gas(self) -> float:
        """Miners earn fees, but not before they have mined: epoch 1 would otherwise
        find them with nothing to return."""
        ret_max = self.traffic["miner_gas_returns_per_epoch_range"][1]
        hi = self.traffic["restitution_amount_range"][1]
        return round(ret_max * self.epoch_count * hi * 1.2 + 200, 4)

    # -- deterministic RNG -------------------------------------------------------------

    def rng(self, purpose: str, node_id: str = "") -> random.Random:
        """A ``random.Random`` derived from the master seed.

        The daemons are separate OS processes, so one shared generator is impossible.
        Deriving each stream from ``(seed, purpose, node_id)`` gives the same guarantee
        that a shared generator would: two runs of the same profile draw the same
        numbers in the same order in every process.
        """
        material = "%d:%s:%s" % (self.seed, purpose, node_id)
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
        return random.Random(int(digest, 16))

    # -- cluster assignment ------------------------------------------------------------

    def cluster_assignment(self) -> Dict[str, str]:
        """company node_id -> miner node_id, drawn once from the master seed.

        Every miner receives at least one company: a cluster with no members is not in
        the cluster map at all, so its head would never receive a published weight.
        """
        miners = self.by_role("miner")
        companies = self.by_role("company")
        rng = self.rng("cluster-assignment")
        order = list(companies)
        rng.shuffle(order)
        out: Dict[str, str] = {}
        for i, company in enumerate(order):
            out[company.node_id] = miners[i % len(miners)].node_id
        return out

    # -- params.dat --------------------------------------------------------------------

    def params_overrides(self, treasury_address: Optional[str] = None) -> Dict[str, str]:
        """Every key the harness writes into ``params.dat``, as strings.

        The eight activation keys are written explicitly and unconditionally: the
        ``enable-wpoa`` master is honoured only on the ``multichain-util create``
        command line and is inert when it merely sits in the file, so relying on it
        would leave wPoA off.
        """
        out: Dict[str, str] = {}
        for key in ACTIVATION_KEYS:
            out[key] = "true"
        out["weight-epoch-length"] = str(self.epoch_length)
        out["setup-first-blocks"] = str(self.setup_first_blocks)
        for key, value in self.chain_params.items():
            if key == "setup-first-blocks":
                continue
            out[key] = _as_param_string(value)
        for key, value in self.wpoa_params.items():
            out[key] = _as_param_string(value)
        for key, value in self.weight_engine_params.items():
            out[key] = _as_param_string(value)
        if treasury_address:
            out["weight-treasury-address"] = treasury_address
        return out

    # -- serialisation -----------------------------------------------------------------

    def manifest(self) -> Dict[str, Any]:
        """What the run records about its own configuration."""
        return {
            "profile_path": str(self.path),
            "seed": self.seed,
            "chain_name": self.chain_name,
            "nodes": {
                "admin": 1,
                "ca": self.ca_count,
                "miner": self.miner_count,
                "company": self.company_count,
                "total": self.node_count,
            },
            "network": {
                "host": self.host,
                "base_port": self.base_port,
                "base_rpc_port": self.base_rpc_port,
            },
            "epochs": {"count": self.epoch_count, "length_blocks": self.epoch_length},
            "derived": {
                "protocol_setup_floor": self.protocol_setup_floor,
                "setup_first_blocks_requested": self.setup_first_blocks,
                "target_height": self.target_height,
                "maxtxfee": self.maxtxfee,
                "fee_per_kb": self.fee_per_kb,
                "gas_seed": self.gas_seed,
                "gas_floor": self.gas_floor,
                "gas_topup": self.gas_topup,
                "miner_seed_gas": self.miner_seed_gas,
                "stability_margin": STABILITY_MARGIN,
                "setup_publish_margin": SETUP_PUBLISH_MARGIN,
            },
            "chain_params": dict(self.chain_params),
            "wpoa_params": dict(self.wpoa_params),
            "weight_engine_params": dict(self.weight_engine_params),
            "traffic": dict(self.traffic),
            "runtime": dict(self.runtime),
            "node_table": [
                {
                    "node_id": n.node_id,
                    "role": n.role,
                    "index": n.index,
                    "port": n.port,
                    "rpc_port": n.rpc_port,
                }
                for n in self.nodes
            ],
        }


# --------------------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------------------


def _as_param_string(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        # params.dat stores the decimal keys as text; %g would render 1e-05.
        return ("%.10f" % value).rstrip("0").rstrip(".") or "0"
    return str(value)


def _require_mapping(raw: Any, where: str) -> Dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError("%s must be a mapping, got %s" % (where, type(raw).__name__))
    return raw


def _check_number(key: str, value: Any, spec: tuple, where: str) -> Any:
    kind = spec[1]
    if kind == "bool":
        if not isinstance(value, bool):
            raise ConfigError("%s.%s must be true or false, got %r" % (where, key, value))
        return value
    if kind == "enum":
        allowed = spec[0]
        if value not in allowed:
            raise ConfigError(
                "%s.%s must be one of %s, got %r" % (where, key, ", ".join(allowed), value)
            )
        return value
    if isinstance(value, bool):
        raise ConfigError("%s.%s must be a number, got a boolean" % (where, key))
    if kind == "int":
        if not isinstance(value, int):
            raise ConfigError("%s.%s must be an integer, got %r" % (where, key, value))
        number: Any = value
    else:
        if not isinstance(value, (int, float)):
            raise ConfigError("%s.%s must be a number, got %r" % (where, key, value))
        if not math.isfinite(float(value)):
            raise ConfigError("%s.%s must be finite, got %r" % (where, key, value))
        number = float(value)

    _, _, low, high, low_incl, high_incl = spec
    if low is not None:
        if (number < low) or (number == low and not low_incl):
            raise ConfigError(
                "%s.%s = %r is out of range: must be %s %s"
                % (where, key, value, ">=" if low_incl else ">", low)
            )
    if high is not None:
        if (number > high) or (number == high and not high_incl):
            raise ConfigError(
                "%s.%s = %r is out of range: must be %s %s"
                % (where, key, value, "<=" if high_incl else "<", high)
            )
    return number


def _merge_section(
    raw: Any, catalogue: Dict[str, tuple], where: str, dynamic_defaults: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate one section against its catalogue and fill in the defaults."""
    given = _require_mapping(raw, where)
    out: Dict[str, Any] = {}

    for key, value in given.items():
        if key in ACTIVATION_KEYS:
            raise ConfigError(
                "%s.%s is not configurable: this harness always runs the complete wPoA "
                "stack with the weight engine on. Remove the key." % (where, key)
            )
        if key in _RELOCATED:
            raise ConfigError(
                "%s.%s is not set here — it is %s." % (where, key, _RELOCATED[key])
            )
        if key not in catalogue:
            near = _suggest(key, catalogue)
            raise ConfigError(
                "%s.%s is not a params.dat key this harness accepts.%s"
                % (where, key, (" Did you mean %s?" % near) if near else "")
            )
        out[key] = _check_number(key, value, catalogue[key], where)

    for key, spec in catalogue.items():
        if key in out:
            continue
        if key in dynamic_defaults:
            out[key] = dynamic_defaults[key]
        else:
            out[key] = spec[0]
    return out


def _suggest(key: str, catalogue: Dict[str, tuple]) -> str:
    """Cheap nearest-name hint: shared prefix length over a normalised spelling."""
    flat = key.replace("-", "").replace("_", "").lower()
    best, best_score = "", 0
    for candidate in catalogue:
        other = candidate.replace("-", "").lower()
        score = len(os.path.commonprefix([flat, other]))
        if score > best_score:
            best, best_score = candidate, score
    return best if best_score >= 4 else ""


def _check_range_pair(traffic: Dict[str, Any], key: str, numeric: str) -> None:
    value = traffic[key]
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ConfigError("traffic.%s must be a two-element [low, high] list" % key)
    low, high = value
    for item in (low, high):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ConfigError("traffic.%s entries must be numbers, got %r" % (key, value))
        if numeric == "int" and not isinstance(item, int):
            raise ConfigError("traffic.%s entries must be integers, got %r" % (key, value))
    if low > high:
        raise ConfigError("traffic.%s has low > high: %r" % (key, value))
    if numeric == "int" and low < 0:
        raise ConfigError("traffic.%s must not be negative: %r" % (key, value))
    traffic[key] = [low, high]


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------


def load_profile(path: str | os.PathLike) -> Profile:
    """Read a profile, validate it, and return it with every derived value filled in.

    Raises :class:`ConfigError` with a message naming the offending field.
    """
    profile_path = Path(path).expanduser()
    if not profile_path.is_file():
        raise ConfigError("no such profile: %s" % profile_path)
    try:
        raw = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError("%s is not valid YAML: %s" % (profile_path, exc)) from exc
    if not isinstance(raw, dict):
        raise ConfigError("%s must contain a YAML mapping at the top level" % profile_path)

    unknown = sorted(set(raw) - _TOP_LEVEL)
    if unknown:
        raise ConfigError(
            "unknown top-level key(s): %s. Allowed: %s"
            % (", ".join(unknown), ", ".join(sorted(_TOP_LEVEL)))
        )

    # -- seed --------------------------------------------------------------------------
    if "seed" not in raw:
        raise ConfigError("seed is required: it makes the whole run reproducible")
    seed = raw["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ConfigError("seed must be a non-negative integer, got %r" % (seed,))

    # -- chain name --------------------------------------------------------------------
    chain_name = raw.get("chain_name")
    if not isinstance(chain_name, str) or not _CHAIN_NAME_RE.match(chain_name):
        raise ConfigError(
            "chain_name must be 1-32 characters of [a-z0-9-] starting with a letter or "
            "digit, got %r" % (chain_name,)
        )

    # -- node counts -------------------------------------------------------------------
    nodes_raw = _require_mapping(raw.get("nodes"), "nodes")
    unknown = sorted(set(nodes_raw) - {"ca_count", "miner_count", "company_count"})
    if unknown:
        raise ConfigError(
            "unknown nodes key(s): %s. The admin node is always exactly 1 and is not "
            "configurable." % ", ".join(unknown)
        )
    counts = {}
    for key in ("ca_count", "miner_count", "company_count"):
        value = nodes_raw.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError("nodes.%s is required and must be an integer" % key)
        if value < 1:
            counts_reason = {
                "ca_count": "nobody could certify an ESG score, so every cluster would "
                            "compute W_k = 0 and publish the positivity floor of 1",
                "miner_count": "there would be no validator to elect",
                "company_count": "nothing would generate tau",
            }[key]
            raise ConfigError("nodes.%s must be >= 1: %s" % (key, counts_reason))
        counts[key] = value

    # -- epochs ------------------------------------------------------------------------
    epochs_raw = _require_mapping(raw.get("epochs"), "epochs")
    unknown = sorted(set(epochs_raw) - {"count", "length_blocks"})
    if unknown:
        raise ConfigError("unknown epochs key(s): %s" % ", ".join(unknown))
    epoch_count = epochs_raw.get("count")
    epoch_length = epochs_raw.get("length_blocks")
    if isinstance(epoch_count, bool) or not isinstance(epoch_count, int) or epoch_count < 1:
        raise ConfigError("epochs.count must be an integer >= 1")
    if (
        isinstance(epoch_length, bool)
        or not isinstance(epoch_length, int)
        or not (1 <= epoch_length <= 1_000_000)
    ):
        raise ConfigError("epochs.length_blocks must be an integer in [1, 1000000]")

    # -- network -----------------------------------------------------------------------
    net_raw = _require_mapping(raw.get("network"), "network")
    unknown = sorted(set(net_raw) - {"host", "base_port", "base_rpc_port"})
    if unknown:
        raise ConfigError("unknown network key(s): %s" % ", ".join(unknown))
    host = net_raw.get("host", "127.0.0.1")
    if not isinstance(host, str) or not host:
        raise ConfigError("network.host must be a non-empty string")
    base_port = net_raw.get("base_port")
    base_rpc_port = net_raw.get("base_rpc_port")
    node_count = 1 + counts["ca_count"] + counts["miner_count"] + counts["company_count"]
    for label, value in (("base_port", base_port), ("base_rpc_port", base_rpc_port)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError("network.%s is required and must be an integer" % label)
        if not (1024 <= value <= 65535):
            raise ConfigError("network.%s must be in [1024, 65535], got %d" % (label, value))
        if value + node_count - 1 > 65535:
            raise ConfigError(
                "network.%s = %d leaves no room for %d nodes (would reach %d)"
                % (label, value, node_count, value + node_count - 1)
            )
    p2p = range(base_port, base_port + node_count)
    rpc = range(base_rpc_port, base_rpc_port + node_count)
    if max(p2p.start, rpc.start) < min(p2p.stop, rpc.stop):
        raise ConfigError(
            "the P2P range [%d, %d] and the RPC range [%d, %d] overlap; a node would "
            "reuse a port and the daemon would half-start"
            % (p2p.start, p2p.stop - 1, rpc.start, rpc.stop - 1)
        )

    # -- parameter sections ------------------------------------------------------------
    chain_params = _merge_section(raw.get("chain"), _CHAIN_PARAMS, "chain", {})
    wpoa_params = _merge_section(
        raw.get("wpoa"),
        _WPOA_PARAMS,
        "wpoa",
        {"wpoa-randao-lookback": epoch_length + 1},
    )
    weight_engine_params = _merge_section(
        raw.get("weight_engine"), _WEIGHT_ENGINE_PARAMS, "weight_engine", {}
    )

    # Cross-parameter constraints the node would otherwise refuse at startup.
    if wpoa_params["wpoa-malus-equiv-points"] <= wpoa_params["wpoa-malus-delay-points"]:
        raise ConfigError(
            "wpoa.wpoa-malus-equiv-points (%r) must be strictly greater than "
            "wpoa-malus-delay-points (%r): an equivocation is a safety fault and must "
            "cost more than a scheduling one"
            % (
                wpoa_params["wpoa-malus-equiv-points"],
                wpoa_params["wpoa-malus-delay-points"],
            )
        )
    if wpoa_params["wpoa-malus-badweight-points"] <= wpoa_params["wpoa-malus-selfwrite-points"]:
        raise ConfigError(
            "wpoa.wpoa-malus-badweight-points (%r) must be strictly greater than "
            "wpoa-malus-selfwrite-points (%r): a false weight succeeds unless someone "
            "recomputes it, a self-write is discarded on sight"
            % (
                wpoa_params["wpoa-malus-badweight-points"],
                wpoa_params["wpoa-malus-selfwrite-points"],
            )
        )
    if int(chain_params["initial-block-reward"]) == 0 and int(
        chain_params["first-block-reward"]
    ) <= 0:
        raise ConfigError(
            "chain.first-block-reward must be > 0 when initial-block-reward is 0: with "
            "no native currency at all, R_k, the credits and the debits are all 0, rho "
            "is pinned and the WeightEngine's only endogenous feedback channel is inert"
        )

    # -- traffic -----------------------------------------------------------------------
    traffic_raw = _require_mapping(raw.get("traffic"), "traffic")
    unknown = sorted(set(traffic_raw) - set(_TRAFFIC_DEFAULTS))
    if unknown:
        raise ConfigError("unknown traffic key(s): %s" % ", ".join(unknown))
    traffic = dict(_TRAFFIC_DEFAULTS)
    traffic.update(traffic_raw)
    for key, numeric in (
        ("company_tx_per_epoch_range", "int"),
        ("miner_gas_returns_per_epoch_range", "int"),
        ("esg_score_range", "int"),
        ("restitution_amount_range", "float"),
    ):
        _check_range_pair(traffic, key, numeric)
    if traffic["esg_score_range"][0] < 1:
        raise ConfigError(
            "traffic.esg_score_range must start at 1 or above: the node rejects an ESG "
            "score of 0, and a cluster with no score computes W_k = 0"
        )
    if not isinstance(traffic["event_stream"], str) or not traffic["event_stream"]:
        raise ConfigError("traffic.event_stream must be a non-empty stream name")
    for reserved in (STREAM_WEIGHTS, STREAM_MEMBERSHIP, STREAM_ESG, STREAM_MALUS):
        if traffic["event_stream"] == reserved:
            raise ConfigError(
                "traffic.event_stream must not be %r: publishing test payloads onto a "
                "weight-engine stream would feed the engine's own input with noise and "
                "make tau indistinguishable from a malformed-record test" % reserved
            )

    # -- runtime -----------------------------------------------------------------------
    runtime_raw = _require_mapping(raw.get("runtime"), "runtime")
    unknown = sorted(set(runtime_raw) - set(_RUNTIME_DEFAULTS))
    if unknown:
        raise ConfigError("unknown runtime key(s): %s" % ", ".join(unknown))
    runtime = dict(_RUNTIME_DEFAULTS)
    runtime.update(runtime_raw)
    for key in ("rpc_timeout_s", "startup_timeout_s", "shutdown_grace_s"):
        value = runtime[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ConfigError("runtime.%s must be an integer >= 1" % key)
    if not isinstance(runtime["wpoa_debug"], bool):
        raise ConfigError("runtime.wpoa_debug must be true or false")

    profile = Profile(
        path=profile_path,
        seed=seed,
        chain_name=chain_name,
        ca_count=counts["ca_count"],
        miner_count=counts["miner_count"],
        company_count=counts["company_count"],
        host=host,
        base_port=base_port,
        base_rpc_port=base_rpc_port,
        epoch_count=epoch_count,
        epoch_length=epoch_length,
        chain_params=chain_params,
        wpoa_params=wpoa_params,
        weight_engine_params=weight_engine_params,
        traffic=traffic,
        runtime=runtime,
    )
    profile.nodes = _build_nodes(profile)
    return profile


def _build_nodes(profile: Profile) -> List[Node]:
    """admin, then CAs, then miners, then companies — a fixed order, so the port map is
    a property of the profile rather than of the run."""
    nodes: List[Node] = []
    index = 0

    def add(role: str, role_index: int) -> None:
        nonlocal index
        node_id = "admin" if role == "admin" else "%s-%d" % (role, role_index)
        nodes.append(
            Node(
                index=index,
                role=role,
                role_index=role_index,
                node_id=node_id,
                port=profile.base_port + index,
                rpc_port=profile.base_rpc_port + index,
            )
        )
        index += 1

    add("admin", 0)
    for i in range(profile.ca_count):
        add("ca", i)
    for i in range(profile.miner_count):
        add("miner", i)
    for i in range(profile.company_count):
        add("company", i)
    return nodes


__all__ = [
    "CA_PERMISSION",
    "COIN",
    "ConfigError",
    "Node",
    "Profile",
    "SETUP_PUBLISH_MARGIN",
    "STABILITY_MARGIN",
    "STREAM_ESG",
    "STREAM_MALUS",
    "STREAM_MEMBERSHIP",
    "STREAM_WEIGHTS",
    "load_profile",
]
