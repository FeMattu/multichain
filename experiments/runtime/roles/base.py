"""What every node controller is, and the machinery all four share.

The Shadow suite drove each node with a bash script (`role_admin.sh`,
`role_miner.sh`, `role_company.sh`, `role_ca.sh` over `sim_common.sh`). These
controllers are those scripts, ported: the same on-chain sequence, the same
output files, the same hard-won details — the CLOSED `wpoa-weights` stream the
admin must create by hand, the one-stream-per-call grants, the admin's
explicit `subscribe`, the epoch sampler's burial margin.

Three things are new, and they are the point of the port:

* a **life cycle** — ``setup`` / ``loop`` / ``teardown`` — so a node is driven
  for the whole experiment instead of being started and abandoned;
* a **supervisor** that restarts a controller that dies, and records that it
  did (`runtime.collectors.process` reports the count as `process_restarts`);
* **configuration instead of constants** — the workload of a company, the
  reconciliation rate of a miner and the admin's GAS thresholds come from the
  descriptor.

The bash originals spoke JSON-RPC over curl to avoid `multichain-cli`'s
100 ms `Strengthen()` cost per invocation. These use the same JSON-RPC over
HTTP from a single long-lived process, which pays that cost zero times.

Every controller writes `logs/<node>/role_controller.log`. A controller that
did its work silently would be indistinguishable from one that never ran.
"""

from __future__ import annotations

import abc
import csv
import json
import logging
import os
import random
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..multichain.rpc import RpcClient, RpcError

LOG = logging.getLogger("experiments.roles")


@dataclass
class RoleContext:
    """Everything a controller needs, read from the environment once.

    The controller runs in its own process inside the node's namespace, so the
    environment is the only channel. :func:`context_from_env` is the single
    place that parses it.
    """

    node_id: str
    role: str
    ip: str
    run_root: Path
    chain: str
    rpc_port: int
    p2p_port: int
    rpc_user: str
    rpc_password: str
    admin_id: str
    admin_ip: str
    miners: list = field(default_factory=list)
    companies: list = field(default_factory=list)
    cas: list = field(default_factory=list)
    ip_by_node: dict = field(default_factory=dict)
    cluster: str = ""
    treasury: str = ""
    stream: str = "poesia-supplychain"
    epoch_length: int = 12
    setup_blocks: int = 60
    seed: int = 0
    duration_s: float = 0.0
    tick_s: float = 5.0
    workload: dict = field(default_factory=dict)

    @property
    def metrics_dir(self) -> Path:
        return self.run_root / "raw" / "metrics"

    @property
    def shared_dir(self) -> Path:
        return self.run_root / "runtime" / "shared"

    @property
    def log_path(self) -> Path:
        return self.run_root / "logs" / self.node_id / "role_controller.log"

    def all_nodes(self) -> list:
        return [self.admin_id] + list(self.miners) + list(self.companies) + list(self.cas)


def _env_list(name: str) -> list:
    return [part for part in os.environ.get(name, "").split() if part]


def context_from_env() -> RoleContext:
    """Build the context from POESIA_* variables. Fails loudly if one is missing."""
    def need(key: str) -> str:
        value = os.environ.get(key)
        if not value:
            raise SystemExit("role controller: %s is not set" % key)
        return value

    node_id = need("POESIA_HOST")
    ip_by_node = {
        key[len("POESIA_IP_"):]: value
        for key, value in os.environ.items() if key.startswith("POESIA_IP_")
    }
    workload = json.loads(os.environ.get("POESIA_WORKLOAD_JSON", "{}"))
    return RoleContext(
        node_id=node_id,
        role=need("POESIA_ROLE"),
        ip=need("POESIA_IP"),
        run_root=Path(need("POESIA_RUN")),
        chain=need("POESIA_CHAIN"),
        rpc_port=int(os.environ.get("POESIA_RPCPORT", "27000")),
        p2p_port=int(os.environ.get("POESIA_P2PPORT", "27001")),
        rpc_user=os.environ.get("POESIA_RPCUSER", "poesia"),
        rpc_password=os.environ.get("POESIA_RPCPASS", "poesiarpc"),
        admin_id=os.environ.get("POESIA_ADMIN", "admin"),
        admin_ip=need("POESIA_ADMIN_IP"),
        miners=_env_list("POESIA_MINERS"),
        companies=_env_list("POESIA_COMPANIES"),
        cas=_env_list("POESIA_CAS"),
        ip_by_node=ip_by_node,
        cluster=os.environ.get("POESIA_CLUSTER", ""),
        treasury=os.environ.get("POESIA_TREASURY", ""),
        stream=os.environ.get("POESIA_STREAM", "poesia-supplychain"),
        epoch_length=int(os.environ.get("POESIA_EPOCHLEN", "12")),
        setup_blocks=int(os.environ.get("POESIA_SETUPBLOCKS", "60")),
        seed=int(os.environ.get("POESIA_RNG_SEED", "0")),
        duration_s=float(os.environ.get("POESIA_DURATION", "0") or 0),
        tick_s=float(os.environ.get("POESIA_TICK", "5")),
        workload=workload,
    )


class RoleController(abc.ABC):
    """One node, driven for the whole experiment.

    ``run()`` is the life cycle: ``setup`` once, then ``loop(tick)`` every
    ``tick_s`` until the deadline or a signal, then ``teardown`` — which runs
    even when the loop raised, because the final snapshot is the run's primary
    data source and losing it loses the run.
    """

    role = "base"

    def __init__(self, context: RoleContext) -> None:
        self.ctx = context
        self.log = self._make_logger()
        self.rng = random.Random(context.seed ^ hash(context.node_id) & 0x7FFFFFFF)
        self._stop = threading.Event()
        self.started_monotonic = time.monotonic()
        self.tick_count = 0
        self.errors = 0
        self._clients: dict = {}

    # -- logging ------------------------------------------------------------
    def _make_logger(self) -> logging.Logger:
        path = self.ctx.log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger("role.%s" % self.ctx.node_id)
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%dT%H:%M:%S%z"))
        logger.addHandler(handler)
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
        logger.addHandler(stream)
        return logger

    # -- RPC ----------------------------------------------------------------
    def client(self, node_id: str | None = None) -> RpcClient:
        """RPC client for a node, by its EMULATED address.

        Node-to-node RPC is part of the experiment's traffic and travels the
        impaired paths on purpose. Only the harness's own collectors, which
        run on the host, use the management plane.
        """
        node_id = node_id or self.ctx.node_id
        if node_id not in self._clients:
            address = (self.ctx.ip if node_id == self.ctx.node_id
                       else self.ctx.ip_by_node.get(node_id, ""))
            if not address:
                raise KeyError("no address for node %r" % node_id)
            self._clients[node_id] = RpcClient(
                "http://%s:%d/" % (address, self.ctx.rpc_port),
                self.ctx.rpc_user, self.ctx.rpc_password, node_id=self.ctx.node_id)
        return self._clients[node_id]

    def call(self, method: str, params: list | None = None, *,
             node_id: str | None = None, quiet: bool = False):
        """One RPC. Returns None on failure and counts it, never raises."""
        try:
            return self.client(node_id).call(method, params)
        except (RpcError, KeyError) as exc:
            self.errors += 1
            if not quiet:
                self.log.warning("%s failed: %s", method, exc)
            return None

    def wait_rpc(self, timeout_s: float = 600.0, node_id: str | None = None) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline and not self._stop.is_set():
            if self.call("getblockcount", node_id=node_id, quiet=True) is not None:
                return True
            self._sleep(2.0)
        self.log.error("no RPC answer within %gs", timeout_s)
        return False

    def wait_stream(self, name: str, timeout_s: float = 600.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline and not self._stop.is_set():
            if self.call("liststreams", [name], quiet=True) is not None:
                return True
            self._sleep(5.0)
        self.log.warning("stream %s not confirmed within %gs", name, timeout_s)
        return False

    def block_count(self) -> int:
        value = self.call("getblockcount", quiet=True)
        try:
            return int(value)
        except (TypeError, ValueError):
            return -1

    # -- output -------------------------------------------------------------
    def csv_append(self, name: str, row: list, header: list | None = None) -> None:
        """Append one row, writing the header once.

        Several controllers share some of these files (traffic, membership,
        reconciliation), exactly as the bash originals did — hence the
        header-if-absent dance rather than a plain writer.
        """
        path = self.ctx.metrics_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        exists = path.exists() and path.stat().st_size > 0
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if header and not exists:
                writer.writerow(header)
            writer.writerow(row)

    def write_json(self, name: str, payload) -> None:
        """Store an RPC answer in the shape the analysis expects.

        The analysis reads `{"result": ...}` because that is what the bash
        originals saved — the raw JSON-RPC envelope, straight from curl.
        """
        path = self.ctx.metrics_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"result": payload, "error": None,
                                    "id": self.ctx.node_id}), encoding="utf-8")

    def address_of(self, node_id: str) -> str:
        path = self.ctx.shared_dir / ("%s.addr" % node_id)
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def publish_own_address(self) -> str:
        """Record this node's wallet address where the admin will look for it."""
        addresses = self.call("getaddresses")
        if not addresses:
            return ""
        address = addresses[0] if isinstance(addresses, list) else str(addresses)
        self.ctx.shared_dir.mkdir(parents=True, exist_ok=True)
        (self.ctx.shared_dir / ("%s.addr" % self.ctx.node_id)).write_text(
            address + "\n", encoding="utf-8")
        return address

    # -- life cycle ---------------------------------------------------------
    @abc.abstractmethod
    def setup(self) -> None:
        """Once, before the loop. Role-specific initialisation."""

    @abc.abstractmethod
    def loop(self, tick: int) -> None:
        """Every tick_s until the deadline. Must return promptly."""

    def teardown(self) -> None:
        """Once, at the end. Runs even if the loop raised."""

    def run(self) -> int:
        self._install_signals()
        self.log.info("controller start: role=%s node=%s ip=%s duration=%gs tick=%gs",
                      self.role, self.ctx.node_id, self.ctx.ip,
                      self.ctx.duration_s, self.ctx.tick_s)
        status = 0
        try:
            self.setup()
            self.log.info("setup complete")
            deadline = (self.started_monotonic + self.ctx.duration_s
                        if self.ctx.duration_s > 0 else float("inf"))
            while not self._stop.is_set() and time.monotonic() < deadline:
                self.tick_count += 1
                started = time.monotonic()
                try:
                    self.loop(self.tick_count)
                except Exception as exc:  # noqa: BLE001 - one bad tick is not the run
                    self.errors += 1
                    self.log.warning("tick %d failed: %s", self.tick_count, exc)
                # A heartbeat every tenth tick: a log that only shows start-up
                # cannot be distinguished from a controller that died silently.
                if self.tick_count % 10 == 0:
                    self.log.info("heartbeat tick=%d height=%d errors=%d",
                                  self.tick_count, self.block_count(), self.errors)
                self._sleep(max(0.0, self.ctx.tick_s - (time.monotonic() - started)))
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            self.log.exception("controller failed: %s", exc)
            status = 3
        finally:
            try:
                self.teardown()
                self.log.info("teardown complete")
            except Exception as exc:  # noqa: BLE001
                self.log.warning("teardown failed: %s", exc)
            self.log.info("controller stop: ticks=%d errors=%d elapsed=%.0fs",
                          self.tick_count, self.errors,
                          time.monotonic() - self.started_monotonic)
            logging.shutdown()
        return status

    def _install_signals(self) -> None:
        def handler(signum, frame):
            del frame
            self.log.info("signal %d: stopping", signum)
            self._stop.set()

        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(signum, handler)
            except ValueError:
                pass

    def _sleep(self, seconds: float) -> None:
        """Interruptible: a signal must not wait out a whole tick."""
        if seconds > 0:
            self._stop.wait(seconds)

    # -- helpers shared by more than one role -------------------------------
    def epoch_of(self, height: int) -> int:
        return height // self.ctx.epoch_length + 1

    def hexlify(self, payload: dict) -> str:
        return json.dumps(payload, separators=(",", ":")).encode().hex()
