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

from fabric.addressing import AddressPlan  # noqa: E402
from fabric.topology import (  # noqa: E402
    LinkProfile,
    RealisedLink,
    Topology,
    TopologyError,
    load_link_profile,
    load_topology,
)
from malicious import (  # noqa: E402
    MaliciousConfigError,
    disabled_plan as _disabled_malicious_plan,
    resolve_plan as _resolve_malicious_plan,
    select_miners as _select_malicious,
    validate as _validate_malicious,
)

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

#: Everything a profile names by relative path -- a topology, a link profile -- is
#: relative to this directory, not to the profile's own location. A profile is a
#: statement about a run; where the shared configuration lives is a property of the
#: tree, and resolving against the profile would make a profile unmovable.
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

#: The roles a node may have. `admin` is special only in being unique.
ROLES = ("admin", "ca", "miner", "company")

#: A node id is a directory name (``chains/<id>/``, ``logs/<id>/``) and a column value in
#: every analysis table, so it is restricted to what is safe in both.
_NODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

#: The regimes. `native` is the default, which is what makes every profile written
#: before the fabric existed keep working untouched.
FABRIC_BACKENDS = ("native", "core")

#: How many times the bootstrap waits for something to cross the whole network before
#: the next step may depend on it: the join, the two grant passes, the stream creation,
#: the stream grants, the funding, the membership registration and the ESG certification.
#: Counted from ``bootstrap_network.py``'s own sequence rather than guessed.
BOOTSTRAP_SYNC_POINTS = 16

#: The largest share of the sortition window that propagation may take up.
#:
#: The sortition delay is drawn inside ``Delta_max = wpoa-sortition-delta *
#: target-block-time``. If a block's worst round trip were a large fraction of that
#: window, the order in which validators *appear* to act would be set by the network
#: rather than by the draw, and the election's timing would measure the emulator's
#: queueing instead of the protocol. A quarter leaves the draw dominant by a factor of
#: four, which is what the shipped maps run at.
MAX_PROPAGATION_SHARE_OF_SORTITION_WINDOW = 0.25

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
    "malicious",
    "fabric",
    "topology",
    "network_profile",
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
    #: The topology site this node runs at. Empty in the native regime, where there is
    #: one place and every node is at it.
    location: str = ""
    #: For a company, the miner whose cluster it joins, when the profile declares it
    #: rather than leaving it to the seed.
    cluster: str = ""

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
    #: The validated ``malicious`` section, with every default filled in. A profile
    #: without the section gets the disabled form, so every consumer reads the same shape
    #: and none of them has to test for the key.
    malicious: Dict[str, Any] = field(default_factory=dict)
    nodes: List[Node] = field(default_factory=list)
    #: Which regime this profile runs in. A profile written before the fabric existed
    #: carries no ``fabric`` section, so the default is the one that changes nothing.
    fabric: Dict[str, Any] = field(default_factory=lambda: {"backend": "native"})
    #: The map, in the CORE regime. ``None`` in the native one, where there is one place
    #: and every node is at it.
    topology: Optional[Topology] = None
    #: A named override of the map's own delay model, and which links it applies to.
    network_profile: Optional[LinkProfile] = None
    network_profile_apply_to: str = "all"
    #: Derived from the topology alone, which is what lets a traffic daemon resolve an
    #: RPC endpoint without an emulator, and ``--dry-run`` print one without a daemon.
    address_plan: Optional[AddressPlan] = None
    #: company node_id -> miner node_id, when the profile states it instead of leaving
    #: it to the seed.
    declared_clusters: Dict[str, str] = field(default_factory=dict)

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

    # -- the regime, and where a node is -----------------------------------------------

    @property
    def fabric_backend(self) -> str:
        return str(self.fabric.get("backend", "native"))

    def site_of(self, node_id: str) -> str:
        """The topology site this node runs at. Empty in the native regime."""
        return self.node(node_id).location

    def rpc_host(self, node_id: str) -> str:
        """Where this node's RPC port is, seen from the harness.

        In the native regime, the one host every node shares. Under CORE, the node's site
        on the **control** plane, which carries no impairment: the instrument must not sit
        inside the thing it measures.

        Derived rather than looked up, because the traffic daemons are separate processes
        that re-load the profile from YAML and must resolve a node without constructing an
        emulator client or being able to.
        """
        if self.address_plan is None:
            return self.host
        return self.address_plan.control(self.site_of(node_id))

    def data_host(self, node_id: str) -> str:
        """Where this node's peer-to-peer port is: the **emulated** plane under CORE.

        Everything the chain does between nodes goes here, and everything here is subject
        to the map's delay, jitter and loss. Confusing this with :meth:`rpc_host` would
        build the peer mesh on an unimpaired network and the run would measure nothing —
        which is why the bootstrap asserts, afterwards, that no peer address is off it.
        """
        if self.address_plan is None:
            return self.host
        return self.address_plan.identity(self.site_of(node_id))

    def realised_links(self) -> List[RealisedLink]:
        """Every cable with its impairment resolved. Empty in the native regime."""
        if self.topology is None:
            return []
        return self.topology.realise(self.network_profile, self.network_profile_apply_to)

    @property
    def network_profile_description(self) -> Optional[Dict[str, Any]]:
        if self.network_profile is None:
            return None
        return {"name": self.network_profile.name, "apply_to": self.network_profile_apply_to}

    @property
    def seed_node_address(self) -> str:
        """What a joining node dials.

        The admin's **data** address, always. In the native regime that is loopback,
        stated explicitly because ``getinfo``'s ``nodeaddress`` can report a NAT address
        when the host is containerised and a joining node would then dial an unreachable
        one. Under CORE it is the admin's site on the emulated plane: a seed dialled over
        the control network would build the entire mesh there.
        """
        return "%s@%s:%d" % (
            self.chain_name, self.data_host(self.admin.node_id), self.admin.port
        )

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
    def worst_path_delay_ms(self) -> float:
        """One-way delay of the slowest path on the map. 0 in the native regime."""
        return self.topology.worst_path_delay_ms if self.topology is not None else 0.0

    @property
    def worst_round_trip_s(self) -> float:
        return 2.0 * self.worst_path_delay_ms / 1000.0

    @property
    def sortition_window_s(self) -> float:
        """``Delta_max``: the width of the window a sortition delay is drawn in."""
        return float(self.wpoa_params["wpoa-sortition-delta"]) * self.target_block_time

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
        # Every step of the bootstrap is a transaction that has to reach every node
        # before the next step may depend on it. On loopback that costs nothing; across
        # an emulated map it is one worst-case round trip per sync point. Measured, this
        # is small -- 16 * 363 ms is about 6 s against a 120 s budget on the harshest
        # map shipped -- but it is the term that grows if a harsher one is ever written,
        # and a budget that ignores it would fail with no indication why.
        propagation_s = BOOTSTRAP_SYNC_POINTS * self.worst_round_trip_s
        need = int(boot_s + inputs_s + propagation_s) // tbt
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

    # -- the malicious-miner experiment --------------------------------------------------

    @property
    def malicious_enabled(self) -> bool:
        return bool(self.malicious.get("enabled"))

    @property
    def malicious_miner_ids(self) -> List[str]:
        """Which miners misbehave, decided from the plan seed alone.

        A property rather than a stored field: the selection is a pure function of the
        seed and the miner list, so every process that loads the profile derives the same
        set without reading anything the orchestrator wrote. The run manifest still
        records it, because a *derivation* that is not written down is not evidence.
        """
        if not self.malicious_enabled:
            return []
        return _select_malicious(
            int(self.malicious["seed"]),
            [n.node_id for n in self.by_role("miner")],
            int(self.malicious["miner_count"]),
        )

    def malicious_plan(
        self,
        addresses: Optional[Dict[str, str]] = None,
        initial_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """The immutable plan for this run, ready to be written to the run directory.

        ``addresses`` and ``initial_weights`` are only known once the network is up, so
        they are passed in rather than read: the profile stays loadable with no chain.
        """
        miner_ids = [n.node_id for n in self.by_role("miner")]
        if not self.malicious_enabled:
            return _disabled_malicious_plan(miner_ids)
        return _resolve_malicious_plan(self.malicious, miner_ids, addresses, initial_weights)

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
        """company node_id -> miner node_id.

        **Declared** when the profile states a ``cluster`` for its companies, **drawn**
        from the master seed when it does not. The two forms differ in what they fix,
        never in what they produce: either way the result is one company-to-miner map,
        recorded in ``clusters.json``, and either way every miner receives at least one
        company — a cluster with no members is not in the map at all, so its head would
        never receive a published weight.
        """
        if self.declared_clusters:
            return dict(self.declared_clusters)
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
            # The regime is recorded, not inferred: a result whose network has to be
            # guessed from the profile's name is not evidence.
            "fabric": {
                "backend": self.fabric_backend,
                "topology": self.topology.as_dict() if self.topology else None,
                "network_profile": self.network_profile_description,
            },
            "derived": {
                "protocol_setup_floor": self.protocol_setup_floor,
                "worst_path_delay_ms": round(self.worst_path_delay_ms, 3),
                "worst_round_trip_s": round(self.worst_round_trip_s, 4),
                "sortition_window_s": round(self.sortition_window_s, 4),
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
            "malicious": dict(self.malicious),
            "malicious_plan": self.malicious_plan(),
            "node_table": [
                {
                    "node_id": n.node_id,
                    "role": n.role,
                    "index": n.index,
                    "port": n.port,
                    "rpc_port": n.rpc_port,
                    "location": n.location,
                    "rpc_host": self.rpc_host(n.node_id),
                    "data_host": self.data_host(n.node_id),
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
# The regime, the map, and where each node sits on it
# --------------------------------------------------------------------------------------


def _parse_fabric(raw: Any) -> Dict[str, Any]:
    """``fabric: {backend: native|core}``. Absent means native."""
    given = _require_mapping(raw, "fabric")
    unknown = sorted(set(given) - {"backend"})
    if unknown:
        raise ConfigError("unknown fabric key(s): %s. Only `backend`." % ", ".join(unknown))
    backend = given.get("backend", "native")
    if backend not in FABRIC_BACKENDS:
        raise ConfigError(
            "fabric.backend must be one of %s, got %r"
            % (", ".join(FABRIC_BACKENDS), backend)
        )
    return {"backend": backend}


def _resolve_config_path(value: str, what: str) -> Path:
    """A path a profile names, resolved against ``test/config/``.

    Against the config directory rather than against the profile's own location: a
    profile is a statement about a run, and where the shared maps live is a property of
    the tree. Resolving relative to the profile would make a profile unmovable.
    """
    if not isinstance(value, str) or not value:
        raise ConfigError("%s must be a non-empty path relative to test/config/" % what)
    candidate = (CONFIG_DIR / value).resolve()
    if candidate.is_file():
        return candidate
    raise ConfigError(
        "%s names %r, which is not a file under %s" % (what, value, CONFIG_DIR)
    )


def _parse_network_profile(raw: Any) -> Tuple[Optional[LinkProfile], str]:
    """``network_profile: <name>`` or ``{name: <name>, apply_to: all|backbone|access}``."""
    if raw is None:
        return None, "all"
    if isinstance(raw, str):
        name, apply_to = raw, "all"
    else:
        given = _require_mapping(raw, "network_profile")
        unknown = sorted(set(given) - {"name", "apply_to"})
        if unknown:
            raise ConfigError(
                "unknown network_profile key(s): %s. Only `name` and `apply_to`."
                % ", ".join(unknown)
            )
        name = given.get("name")
        apply_to = given.get("apply_to", "all")
    if not isinstance(name, str) or not name:
        raise ConfigError("network_profile.name is required and must be a string")
    if apply_to not in ("all", "backbone", "access"):
        raise ConfigError(
            "network_profile.apply_to must be all, backbone or access, got %r" % (apply_to,)
        )
    path = _resolve_config_path("network-profiles/%s.yaml" % name, "network_profile")
    try:
        return load_link_profile(path), apply_to
    except TopologyError as exc:
        raise ConfigError(str(exc)) from exc


def _parse_node_list(
    raw: List[Any], topology: Optional[Topology], backend: str
) -> Tuple[List[Dict[str, Any]], Dict[str, int], Dict[str, str]]:
    """The list form of ``nodes``: one entry per node, in the order that fixes the ports.

    Returns the enabled entries, the per-role counts derived from them, and the declared
    company-to-miner map. Every rejection names the offending id, because a list of twenty
    nodes is not something to re-read looking for which one was wrong.
    """
    specs: List[Dict[str, Any]] = []
    seen: set = set()
    for position, entry in enumerate(raw):
        entry = _require_mapping(entry, "nodes[%d]" % position)
        unknown = sorted(set(entry) - {"id", "role", "location", "cluster", "enabled"})
        if unknown:
            raise ConfigError(
                "nodes[%d] has unknown key(s): %s. Allowed: id, role, location, cluster, "
                "enabled." % (position, ", ".join(unknown))
            )
        node_id = entry.get("id")
        if not isinstance(node_id, str) or not _NODE_ID_RE.match(node_id):
            raise ConfigError(
                "nodes[%d].id must be 1-64 characters of [a-z0-9._-] starting with a "
                "letter or digit, got %r. It is a directory name and a column value."
                % (position, node_id)
            )
        if node_id in seen:
            raise ConfigError(
                "duplicate node id %r: two nodes would share a data directory and a log"
                % node_id
            )
        seen.add(node_id)
        role = entry.get("role")
        if role not in ROLES:
            raise ConfigError(
                "nodes[%d] (%s) has role %r, must be one of %s"
                % (position, node_id, role, ", ".join(ROLES))
            )
        enabled = entry.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ConfigError("nodes[%d] (%s).enabled must be true or false" % (position, node_id))

        location = entry.get("location", "")
        if backend == "core":
            if not isinstance(location, str) or not location:
                raise ConfigError(
                    "%s has no location. Under the CORE fabric every node names a site of "
                    "the topology: there is no single place for it to be." % node_id
                )
            if topology is not None and location not in topology.sites:
                raise ConfigError(
                    "%s is placed at %r, which is not a site of %s. Known sites: %s"
                    % (node_id, location, topology.path.name, ", ".join(sorted(topology.sites)))
                )
        elif location:
            raise ConfigError(
                "%s names a location (%r), but this profile has no topology. A location "
                "without a map is a claim nothing checks." % (node_id, location)
            )

        cluster = entry.get("cluster", "")
        if cluster and role != "company":
            raise ConfigError(
                "%s is a %s and names a cluster. Only a company joins one: a miner heads "
                "its own, and the admin and the CAs belong to none." % (node_id, role)
            )
        if cluster and not isinstance(cluster, str):
            raise ConfigError("%s.cluster must be the id of a miner" % node_id)

        if not enabled:
            continue
        specs.append(
            {
                "id": node_id,
                "role": role,
                "location": location or "",
                "cluster": cluster or "",
            }
        )

    if not specs:
        raise ConfigError("nodes is empty: every entry is disabled, so there is no network")

    by_role: Dict[str, List[str]] = {role: [] for role in ROLES}
    for spec in specs:
        by_role[spec["role"]].append(spec["id"])

    if len(by_role["admin"]) != 1:
        raise ConfigError(
            "exactly one enabled node must have role `admin`, found %d (%s). The admin "
            "seals the genesis, holds the premine and funds everyone; two would race and "
            "none would leave the chain unable to start."
            % (len(by_role["admin"]), ", ".join(by_role["admin"]) or "none")
        )
    reasons = {
        "ca": "nobody could certify an ESG score, so every cluster would compute W_k = 0 "
              "and publish the positivity floor of 1, which makes the sortition uniform",
        "miner": "there would be no validator to elect",
        "company": "nothing would generate tau",
    }
    for role, reason in reasons.items():
        if not by_role[role]:
            raise ConfigError("at least one enabled node must have role %r: %s" % (role, reason))

    miners = set(by_role["miner"])
    declared: Dict[str, str] = {}
    for spec in specs:
        if spec["role"] != "company" or not spec["cluster"]:
            continue
        if spec["cluster"] not in miners:
            raise ConfigError(
                "%s joins cluster %r, which is not an enabled miner. Enabled miners: %s"
                % (spec["id"], spec["cluster"], ", ".join(sorted(miners)))
            )
        declared[spec["id"]] = spec["cluster"]

    if declared:
        if len(declared) != len(by_role["company"]):
            silent = sorted(set(by_role["company"]) - set(declared))
            raise ConfigError(
                "these companies declare no cluster while others do: %s. Either every "
                "company states one, or none does and the seed draws them all — a mixture "
                "would be half a decision." % ", ".join(silent)
            )
        headless = sorted(miners - set(declared.values()))
        if headless:
            raise ConfigError(
                "these miners head no cluster: %s. The cluster map is built only from "
                "confirmed membership records, so a miner nobody joined is never computed "
                "and never published — silently." % ", ".join(headless)
            )

    counts = {
        "ca_count": len(by_role["ca"]),
        "miner_count": len(by_role["miner"]),
        "company_count": len(by_role["company"]),
    }
    return specs, counts, declared


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

    # -- the regime, and the map it runs on --------------------------------------------
    # Parsed before the nodes, because what a node entry is allowed to say depends on it.
    fabric = _parse_fabric(raw.get("fabric"))
    backend = fabric["backend"]

    topology: Optional[Topology] = None
    address_plan: Optional[AddressPlan] = None
    if "topology" in raw and raw["topology"] is not None:
        if backend != "core":
            raise ConfigError(
                "topology is set, but fabric.backend is %r. A map with no emulator to "
                "build it is a description of a network the run would not have." % backend
            )
        try:
            topology = load_topology(_resolve_config_path(raw["topology"], "topology"))
            address_plan = AddressPlan(topology)
        except (TopologyError, ValueError) as exc:
            raise ConfigError(str(exc)) from exc
    elif backend == "core":
        raise ConfigError(
            "fabric.backend is core, so the profile must name a map with "
            "`topology: topologies/<name>.yaml`: the emulator has to be told what to build."
        )

    network_profile, network_profile_apply_to = _parse_network_profile(
        raw.get("network_profile")
    )
    if network_profile is not None and backend != "core":
        raise ConfigError(
            "network_profile is set, but fabric.backend is %r. There is no link to apply "
            "it to: the native regime has one host and no cables." % backend
        )

    # -- the nodes ---------------------------------------------------------------------
    # Two forms. A mapping of counts, which is what a native profile has always used, or
    # an explicit list, which is the only form that can say where a node is.
    nodes_given = raw.get("nodes")
    node_specs: Optional[List[Dict[str, Any]]] = None
    declared_clusters: Dict[str, str] = {}
    if isinstance(nodes_given, list):
        node_specs, counts, declared_clusters = _parse_node_list(
            nodes_given, topology, backend
        )
    elif backend == "core":
        raise ConfigError(
            "under the CORE fabric, nodes must be a list of entries naming each node's "
            "location: a count cannot say where a node is."
        )
    else:
        nodes_raw = _require_mapping(nodes_given, "nodes")
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
    if "host" in net_raw and backend == "core":
        raise ConfigError(
            "network.host is not set under the CORE fabric: a node's address belongs to "
            "the site it is placed at and is derived from the map. Remove the key."
        )
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

    # -- the malicious-miner experiment (optional) -------------------------------------
    # Validated in malicious.py, which knows nothing about this loader, and its error is
    # re-raised as a ConfigError so a profile author only ever sees one error type. An
    # ABSENT section is not an error: it yields the disabled plan, and a profile without
    # the section must behave exactly as it did before the feature existed.
    try:
        malicious = _validate_malicious(
            raw.get("malicious"), counts["miner_count"], epoch_count, seed
        )
    except MaliciousConfigError as exc:
        raise ConfigError(str(exc)) from exc

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
        malicious=malicious,
        fabric=fabric,
        topology=topology,
        network_profile=network_profile,
        network_profile_apply_to=network_profile_apply_to,
        address_plan=address_plan,
        declared_clusters=declared_clusters,
    )
    profile.nodes = _build_nodes(profile, node_specs)

    # The block time has to clear the network, and by a margin. Checked here rather than
    # left to the results, because a chain whose propagation is comparable with its own
    # sortition window produces a perfectly well-formed report of the wrong thing.
    if topology is not None:
        window = profile.sortition_window_s
        worst = profile.worst_round_trip_s
        if worst > window * MAX_PROPAGATION_SHARE_OF_SORTITION_WINDOW:
            raise ConfigError(
                "the worst round trip on %s is %.3f s, and the sortition window "
                "(wpoa-sortition-delta %.2f x target-block-time %d s) is only %.3f s. "
                "Propagation must stay under %.0f%% of that window, or the order in which "
                "validators appear to act is set by the network rather than by the draw "
                "and the election measures the emulator. Raise chain.target-block-time to "
                "at least %d s, or raise wpoa.wpoa-sortition-delta."
                % (
                    topology.name, worst,
                    float(profile.wpoa_params["wpoa-sortition-delta"]),
                    profile.target_block_time, window,
                    MAX_PROPAGATION_SHARE_OF_SORTITION_WINDOW * 100,
                    math.ceil(
                        worst
                        / (MAX_PROPAGATION_SHARE_OF_SORTITION_WINDOW
                           * float(profile.wpoa_params["wpoa-sortition-delta"]))
                    ),
                )
            )
    return profile


def _build_nodes(
    profile: Profile, specs: Optional[List[Dict[str, Any]]] = None
) -> List[Node]:
    """The node table, in the order that fixes the port map.

    From counts: admin, then CAs, then miners, then companies — a fixed order, so the port
    map is a property of the profile rather than of the run. From a list: the order the
    list is written in, which is the same property stated explicitly. The shipped CORE
    profiles write them in the same order the counted form would produce, so a profile of
    either kind puts the same node on the same port.
    """
    nodes: List[Node] = []
    index = 0
    role_counter: Dict[str, int] = {role: 0 for role in ROLES}

    def add(role: str, node_id: str, location: str = "", cluster: str = "") -> None:
        nonlocal index
        role_index = role_counter[role]
        role_counter[role] += 1
        nodes.append(
            Node(
                index=index,
                role=role,
                role_index=role_index,
                node_id=node_id,
                port=profile.base_port + index,
                rpc_port=profile.base_rpc_port + index,
                location=location,
                cluster=cluster,
            )
        )
        index += 1

    if specs is not None:
        for spec in specs:
            add(spec["role"], spec["id"], spec["location"], spec["cluster"])
        return nodes

    add("admin", "admin")
    for i in range(profile.ca_count):
        add("ca", "ca-%d" % i)
    for i in range(profile.miner_count):
        add("miner", "miner-%d" % i)
    for i in range(profile.company_count):
        add("company", "company-%d" % i)
    return nodes


__all__ = [
    "CA_PERMISSION",
    "COIN",
    "ConfigError",
    "MaliciousConfigError",
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
