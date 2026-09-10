"""The resolved experiment: what will actually be built and run.

An :class:`ExperimentPlan` is produced once, from the descriptor plus the files
it references, and everything downstream reads it instead of re-deriving
values. That is the whole point: the topology exporter, the fabric, the
MultiChain initialiser, the collectors and the manifest must agree on the
node's IP, its ports and the resolved ``setup-first-blocks``, and the only way
to guarantee that is to compute each of them exactly once.

Building a plan performs no I/O beyond reading the referenced files and never
touches the network, so ``validate`` and ``dry-run`` exercise the same code
path a real run does.
"""

from __future__ import annotations

import ipaddress
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from .chain_params import ChainParams
from .config import load_document, resolve_path, validate
from .exit_codes import ConfigError
from .paths import CONFIG_ROOT, REPO_ROOT
from .seeds import derive, derive_node
from .topology.generator import build_topology
from .topology.models import Topology

DEFAULT_SCHEDULE = {
    "first_launch_s": 30.0,
    "grant_s": 60.0,
    "join_s": 150.0,
    "register_s": 260.0,
    "traffic_s": 340.0,
    "snapshot_before_stop_s": 120.0,
    "measure_epochs": 16,
}

DEFAULT_WORKLOAD = {
    "gas_company": 100.0,
    "gas_miner": 50.0,
    "gas_threshold": 20.0,
    "gas_topup": 100.0,
    "refill_every_s": 30.0,
    "epoch_poll_s": 10.0,
    "epoch_margin_blocks": 8,
    "default_tx_interval_s": 15.0,
    "default_reconcile_rate": 0.6,
    "reconcile_reserve_gas": 2.0,
}

ADMINISTRATIVE_ROLES = ("admin", "ca")


@dataclass
class NodePlan:
    """One MultiChain node, fully addressed."""

    id: str
    role: str
    hostname: str
    organization: str
    location: str
    region: str
    country: str
    continent: str
    scope: str
    ip: str
    p2p_port: int
    rpc_port: int
    cluster: str = ""
    weight: float = 0.0
    seed: int = 0
    miner: bool = False
    expected_state: str = "running"
    peers: list[str] = field(default_factory=list)
    tx_interval_s: float | None = None
    reconcile_rate: float | None = None
    enabled: bool = True

    @property
    def administrative(self) -> bool:
        return self.role in ADMINISTRATIVE_ROLES

    def datadir(self, run_root: Path) -> Path:
        return run_root / "runtime" / "data" / self.id

    def logdir(self, run_root: Path) -> Path:
        return run_root / "logs" / self.id

    def rpc_url(self) -> str:
        return "http://%s:%d/" % (self.ip, self.rpc_port)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "role": self.role, "hostname": self.hostname,
            "organization": self.organization, "location": self.location,
            "region": self.region, "country": self.country, "continent": self.continent,
            "geographic_scope": self.scope, "ip": self.ip, "p2p_port": self.p2p_port,
            "rpc_port": self.rpc_port, "cluster": self.cluster, "weight": self.weight,
            "seed": self.seed, "miner": self.miner, "expected_state": self.expected_state,
            "peers": list(self.peers), "tx_interval_s": self.tx_interval_s,
            "reconcile_rate": self.reconcile_rate, "enabled": self.enabled,
        }


@dataclass
class Schedule:
    """Bootstrap timeline, in wall-clock seconds from the start of the run."""

    first_launch_s: float
    grant_s: float
    join_s: float
    register_s: float
    traffic_s: float
    snapshot_before_stop_s: float
    duration_s: float
    measure_epochs: int
    duration_is_explicit: bool
    auto_duration_s: float

    @property
    def snapshot_s(self) -> float:
        return max(self.traffic_s, self.duration_s - self.snapshot_before_stop_s)

    def as_dict(self) -> dict:
        return {
            "first_launch_s": self.first_launch_s, "grant_s": self.grant_s,
            "join_s": self.join_s, "register_s": self.register_s,
            "traffic_s": self.traffic_s, "snapshot_s": self.snapshot_s,
            "duration_s": self.duration_s, "measure_epochs": self.measure_epochs,
            "duration_is_explicit": self.duration_is_explicit,
            "auto_duration_s": self.auto_duration_s,
        }


@dataclass
class MultiChainSettings:
    chain: str
    bindir: Path | None
    daemon: str
    cli: str
    util: str
    rpc_user: str
    rpc_password: str
    rpc_port: int
    p2p_port: int
    max_tx_fee: float
    debug: str
    stream: str
    treasury_file: Path


@dataclass
class FabricSettings:
    backend: str
    core_address: str
    session_name: str
    subnet: str
    link_subnet: str
    mgmt_subnet: str
    namespace_prefix: str
    host_uplink: bool


@dataclass
class ExperimentPlan:
    """Everything a run needs, resolved once."""

    name: str
    scenario: str
    description: str
    seed: int
    mode: str
    descriptor_path: Path
    topology: Topology
    topology_path: Path
    chain_params: ChainParams
    nodes: list[NodePlan]
    schedule: Schedule
    multichain: MultiChainSettings
    fabric: FabricSettings
    workload: dict
    expected: dict
    setup_first_blocks: int

    # -- node views ---------------------------------------------------------
    @property
    def enabled_nodes(self) -> list[NodePlan]:
        return [n for n in self.nodes if n.enabled]

    def by_role(self, role: str) -> list[NodePlan]:
        return [n for n in self.enabled_nodes if n.role == role]

    @property
    def miners(self) -> list[NodePlan]:
        return self.by_role("miner")

    @property
    def companies(self) -> list[NodePlan]:
        return self.by_role("company")

    @property
    def cas(self) -> list[NodePlan]:
        return self.by_role("ca")

    @property
    def admin(self) -> NodePlan:
        admins = self.by_role("admin")
        if not admins:
            raise ConfigError("%s declares no admin node" % self.descriptor_path)
        return admins[0]

    def node(self, node_id: str) -> NodePlan:
        for candidate in self.nodes:
            if candidate.id == node_id:
                return candidate
        raise KeyError(node_id)

    @property
    def target_block_time(self) -> int:
        return self.chain_params.target_block_time

    @property
    def epoch_length(self) -> int:
        return self.chain_params.epoch_length

    def measure_blocks(self) -> int:
        return self.schedule.measure_epochs * self.epoch_length

    def summary(self) -> dict:
        return {
            "name": self.name,
            "scenario": self.scenario,
            "seed": self.seed,
            "mode": self.mode,
            "backend": self.fabric.backend,
            "topology": self.topology.name,
            "chain": self.multichain.chain,
            "node_count": len(self.enabled_nodes),
            "miner_count": len(self.miners),
            "company_count": len(self.companies),
            "admin_count": len(self.by_role("admin")) + len(self.cas),
            "target_block_time_s": self.target_block_time,
            "epoch_length_blocks": self.epoch_length,
            "dump_function": self.chain_params.dump_function,
            "setup_first_blocks": self.setup_first_blocks,
            "measure_blocks": self.measure_blocks(),
            "duration_s": self.schedule.duration_s,
        }


# ---------------------------------------------------------------------------
# building
# ---------------------------------------------------------------------------


def _env_binary(name: str, env_var: str, bindir: Path | None, explicit: str | None) -> str:
    """Resolve one binary. Order documented in configs/multichain.yaml."""
    if explicit:
        return str(Path(explicit).expanduser())
    from_env = os.environ.get(env_var)
    if from_env:
        return str(Path(from_env).expanduser())
    base = os.environ.get("MULTICHAIN_BASE_DIR")
    if base:
        return str(Path(base).expanduser() / name)
    if bindir is not None:
        return str(bindir / name)
    return name


def _allocate_ips(nodes: list[dict], subnet: str, roles_config: dict) -> dict[str, str]:
    """Give every node an address, honouring explicit ones.

    Offsets come from configs/node-roles.yaml so the historical layout is
    preserved: admin .10, ca .11+, miners .21+, companies .31+. When a role has
    more members than its offset window allows, allocation falls back to the
    first free address above the highest offset, which is reported rather than
    silently overlapping.
    """
    network = ipaddress.ip_network(subnet, strict=False)
    hosts = list(network.hosts())
    if not hosts:
        raise ConfigError("subnet %s has no usable address" % subnet)
    base = int(hosts[0]) - 1  # x.x.x.0, so offset N lands on x.x.x.N
    composition = roles_config.get("composition", {})

    taken: dict[str, str] = {}
    used: set[str] = set()
    for node in nodes:
        if node.get("ip"):
            taken[node["id"]] = node["ip"]
            used.add(node["ip"])

    counters: dict[str, int] = {}
    for node in nodes:
        if node["id"] in taken:
            continue
        role = node["role"]
        offset = composition.get(role, {}).get("ip_offset")
        if offset is None:
            offset = 100
        index = counters.get(role, 0)
        counters[role] = index + 1
        candidate = base + offset + index
        address = str(ipaddress.ip_address(candidate))
        while address in used or ipaddress.ip_address(candidate) not in network:
            candidate += 1
            if ipaddress.ip_address(candidate) not in network:
                raise ConfigError(
                    "subnet %s is too small for %d nodes" % (subnet, len(nodes))
                )
            address = str(ipaddress.ip_address(candidate))
        taken[node["id"]] = address
        used.add(address)
    return taken


def _roles_config() -> dict:
    path = CONFIG_ROOT / "node-roles.yaml"
    return load_document(path) if path.is_file() else {}


def build_plan(descriptor_path: Path | str, *, seed_override: int | None = None,
               duration_override: float | None = None,
               backend_override: str | None = None) -> ExperimentPlan:
    """Read a descriptor and resolve it into an :class:`ExperimentPlan`."""
    descriptor_path = Path(descriptor_path).resolve()
    document = load_document(descriptor_path)
    validate(document, "experiment.schema.json", origin=str(descriptor_path))
    base = descriptor_path.parent
    roles_config = _roles_config()

    name = document["name"]
    seed = int(seed_override if seed_override is not None else document.get("seed", 20260910))

    topology_path = resolve_path(document["topology"], base=base)
    profile_dir = document.get("network_profile_dir")
    topology = build_topology(
        topology_path,
        profile_dir=resolve_path(profile_dir, base=base) if profile_dir else None,
    )

    chain_params_ref = document.get("chain_params") or "experiments/configs/chain-params/tbt10s-sqrt.dat"
    chain_params = ChainParams.load(resolve_path(chain_params_ref, base=base))

    # -- schedule ----------------------------------------------------------
    sched_doc = {**DEFAULT_SCHEDULE, **(document.get("schedule") or {})}
    setup_first_blocks = chain_params.setup_first_blocks(traffic_start_s=sched_doc["traffic_s"])
    measure_epochs = int(sched_doc.get("measure_epochs") or chain_params.measure_epochs)
    measure_blocks = measure_epochs * chain_params.epoch_length
    auto_duration = float(
        sched_doc["traffic_s"]
        + (setup_first_blocks + measure_blocks) * chain_params.target_block_time
        + 600
    )
    raw_duration = sched_doc.get("duration_s", "auto")
    if duration_override is not None:
        duration, explicit = float(duration_override), True
    elif raw_duration in (None, "auto"):
        duration, explicit = auto_duration, False
    else:
        duration, explicit = float(raw_duration), True
    schedule = Schedule(
        first_launch_s=float(sched_doc["first_launch_s"]),
        grant_s=float(sched_doc["grant_s"]),
        join_s=float(sched_doc["join_s"]),
        register_s=float(sched_doc["register_s"]),
        traffic_s=float(sched_doc["traffic_s"]),
        snapshot_before_stop_s=float(sched_doc["snapshot_before_stop_s"]),
        duration_s=duration,
        measure_epochs=measure_epochs,
        duration_is_explicit=explicit,
        auto_duration_s=auto_duration,
    )
    _check_schedule(schedule, descriptor_path)

    # -- multichain --------------------------------------------------------
    mc_doc = document.get("multichain") or {}
    bindir_ref = mc_doc.get("bindir")
    bindir = resolve_path(bindir_ref, base=base) if bindir_ref else (REPO_ROOT / "src")
    chain = (
        os.environ.get("MULTICHAIN_CHAIN")
        or mc_doc.get("chain")
        or "poesia" + name.replace("-", "")
    )
    multichain = MultiChainSettings(
        chain=chain,
        bindir=bindir,
        daemon=_env_binary("multichaind", "MULTICHAIN_BIN", bindir, mc_doc.get("executable")),
        cli=_env_binary("multichain-cli", "MULTICHAIN_CLI", bindir, mc_doc.get("cli")),
        util=_env_binary("multichain-util", "MULTICHAIN_UTIL", bindir, mc_doc.get("util")),
        rpc_user=mc_doc.get("rpc_user", "poesia"),
        rpc_password=mc_doc.get("rpc_password", "poesiarpc"),
        rpc_port=int(mc_doc.get("rpc_port", 27000)),
        p2p_port=int(mc_doc.get("p2p_port", 27001)),
        max_tx_fee=float(mc_doc.get("max_tx_fee", 10.0)),
        debug=mc_doc.get("debug", "wpoa"),
        stream=mc_doc.get("stream", "poesia-supplychain"),
        treasury_file=resolve_path(mc_doc["treasury_file"], base=base)
        if mc_doc.get("treasury_file") else CONFIG_ROOT / "treasury.json",
    )

    # -- fabric ------------------------------------------------------------
    fab_doc = document.get("fabric") or {}
    fabric = FabricSettings(
        backend=backend_override or fab_doc.get("backend", "auto"),
        core_address=fab_doc.get("core_address", "127.0.0.1:50051"),
        session_name=fab_doc.get("session_name") or "poesia-%s" % name,
        subnet=fab_doc.get("subnet", "11.0.0.0/24"),
        link_subnet=fab_doc.get("link_subnet", "10.99.0.0/16"),
        mgmt_subnet=fab_doc.get("mgmt_subnet", "172.30.0.0/24"),
        namespace_prefix=fab_doc.get("namespace_prefix", "poesia"),
        host_uplink=bool(fab_doc.get("host_uplink", True)),
    )

    workload = {**DEFAULT_WORKLOAD, **(document.get("workload") or {})}

    # -- nodes -------------------------------------------------------------
    raw_nodes = [dict(n) for n in document["nodes"] if n.get("enabled", True) is not False
                 or True]  # keep disabled ones in the plan, marked
    ips = _allocate_ips(
        [n for n in raw_nodes], fabric.subnet, roles_config
    )
    nodes = [
        _build_node(raw, plan_seed=seed, ip=ips[raw["id"]], topology=topology,
                    multichain=multichain, workload=workload,
                    descriptor_path=descriptor_path)
        for raw in raw_nodes
    ]
    _check_nodes(nodes, topology, descriptor_path)
    _assign_peers(nodes)

    return ExperimentPlan(
        name=name,
        scenario=document.get("scenario") or name,
        description=document.get("description", ""),
        seed=seed,
        mode=document.get("mode", "native"),
        descriptor_path=descriptor_path,
        topology=topology,
        topology_path=topology_path,
        chain_params=chain_params,
        nodes=nodes,
        schedule=schedule,
        multichain=multichain,
        fabric=fabric,
        workload=workload,
        expected=document.get("expected") or {},
        setup_first_blocks=setup_first_blocks,
    )


def _build_node(raw: dict, *, plan_seed: int, ip: str, topology: Topology,
                multichain: MultiChainSettings, workload: dict,
                descriptor_path: Path) -> NodePlan:
    node_id = raw["id"]
    role = raw["role"]
    geography = raw.get("geography") or {}
    location = raw.get("location") or ""
    if location:
        try:
            loc = topology.location(location)
        except KeyError:
            raise ConfigError(
                "node %r in %s is placed at unknown location %r; the topology %r offers: %s"
                % (node_id, descriptor_path, location, topology.name,
                   ", ".join(topology.location_ids))
            ) from None
        region = geography.get("region") or loc.region
        country = geography.get("country") or loc.country
        continent = geography.get("continent") or loc.continent
        scope = geography.get("scope") or loc.scope
    else:
        region = geography.get("region", "")
        country = geography.get("country", "")
        continent = geography.get("continent", "")
        scope = geography.get("scope", "regional")

    tx_interval = raw.get("tx_interval_s")
    if role == "company" and tx_interval is None:
        tx_interval = workload["default_tx_interval_s"]
    reconcile = raw.get("reconcile_rate")
    if role == "miner" and reconcile is None:
        reconcile = workload["default_reconcile_rate"]

    return NodePlan(
        id=node_id,
        role=role,
        hostname=raw.get("hostname") or node_id,
        organization=raw.get("organization", ""),
        location=location,
        region=region, country=country, continent=continent, scope=scope,
        ip=ip,
        p2p_port=int(raw.get("p2p_port") or multichain.p2p_port),
        rpc_port=int(raw.get("rpc_port") or multichain.rpc_port),
        cluster=raw.get("cluster", ""),
        weight=float(raw.get("weight", 0.0)),
        seed=int(raw["seed"]) if raw.get("seed") is not None
        else derive_node(plan_seed, "node_seed", node_id),
        miner=bool(raw.get("miner", role in ("miner", "admin"))),
        expected_state=raw.get("expected_state", "running"),
        peers=list(raw.get("peers") or []),
        tx_interval_s=tx_interval,
        reconcile_rate=reconcile,
        enabled=bool(raw.get("enabled", True)),
    )


def _check_nodes(nodes: list[NodePlan], topology: Topology, descriptor_path: Path) -> None:
    seen: set[str] = set()
    for node in nodes:
        if node.id in seen:
            raise ConfigError("duplicate node id %r in %s" % (node.id, descriptor_path))
        seen.add(node.id)

    enabled = [n for n in nodes if n.enabled]
    admins = [n for n in enabled if n.role == "admin"]
    if len(admins) != 1:
        raise ConfigError(
            "%s declares %d admin nodes; exactly one seals the genesis and grants permissions"
            % (descriptor_path, len(admins))
        )
    if not [n for n in enabled if n.role == "miner"]:
        raise ConfigError("%s declares no miner" % descriptor_path)
    cas = [n for n in enabled if n.role == "ca"]
    if not cas:
        raise ConfigError(
            "%s declares no Certification Authority; nothing would publish ESG scores and "
            "every weight would stay zero" % descriptor_path
        )

    miner_ids = {n.id for n in enabled if n.role == "miner"}
    for node in enabled:
        if node.role == "company":
            if not node.cluster:
                raise ConfigError(
                    "company %r in %s declares no cluster; its activity would contribute to no "
                    "miner's weight" % (node.id, descriptor_path)
                )
            if node.cluster not in miner_ids:
                raise ConfigError(
                    "company %r joins cluster %r, which is not an enabled miner (%s)"
                    % (node.id, node.cluster, ", ".join(sorted(miner_ids)))
                )

    addresses = {}
    for node in enabled:
        endpoint = (node.ip, node.rpc_port)
        if endpoint in addresses:
            raise ConfigError(
                "nodes %r and %r share the RPC endpoint %s:%d"
                % (addresses[endpoint], node.id, node.ip, node.rpc_port)
            )
        addresses[endpoint] = node.id

    placed = [n for n in enabled if n.location]
    if placed and len(placed) != len(enabled):
        missing = [n.id for n in enabled if not n.location]
        raise ConfigError(
            "%s places some nodes on the topology but not %s"
            % (descriptor_path, ", ".join(missing))
        )


def _assign_peers(nodes: list[NodePlan]) -> None:
    """Derive ``-addnode`` lists where the descriptor gave none.

    Default policy, the historical one: everybody connects to every miner and
    to the admin. It keeps the P2P graph connected even when the emulated
    topology is sparse, which is what the experiment wants — the network delay
    is the variable, not the peer discovery.
    """
    enabled = [n for n in nodes if n.enabled and n.expected_state != "absent"]
    miners = [n for n in enabled if n.role == "miner"]
    admins = [n for n in enabled if n.role == "admin"]
    for node in nodes:
        if node.peers:
            continue
        targets = [m.id for m in miners if m.id != node.id]
        targets += [a.id for a in admins if a.id != node.id]
        node.peers = targets


def _check_schedule(schedule: Schedule, descriptor_path: Path) -> None:
    ordered = [
        ("first_launch_s", schedule.first_launch_s),
        ("grant_s", schedule.grant_s),
        ("join_s", schedule.join_s),
        ("register_s", schedule.register_s),
        ("traffic_s", schedule.traffic_s),
    ]
    for (name_a, a), (name_b, b) in zip(ordered, ordered[1:]):
        if not a < b:
            raise ConfigError(
                "%s: schedule.%s (%g) must come before schedule.%s (%g)"
                % (descriptor_path, name_a, a, name_b, b),
                hint="the bootstrap order is not arbitrary: permissions before join, "
                     "membership and ESG before traffic",
            )
    if schedule.duration_s <= schedule.traffic_s:
        raise ConfigError(
            "%s: the run lasts %gs but traffic only starts at %gs"
            % (descriptor_path, schedule.duration_s, schedule.traffic_s)
        )
