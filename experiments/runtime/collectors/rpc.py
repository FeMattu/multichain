"""Per-node RPC sampling: the time series a wall-clock run makes possible.

The Shadow suite could only reconstruct most of this after the fact, from a
single final snapshot, because sampling inside the simulation cost simulated
time. Running natively there is no such tax, so the harness samples every node
on a fixed interval and the result is a genuine time series: propagation of a
given height across nodes, sync lag, peer churn, transient forks.

Both clocks are recorded on every row and they are never mixed.
``timestamp_wallclock`` is comparable across machines and with external
events; ``timestamp_monotonic`` is the only one safe for differences, because
it does not jump when the host's clock is adjusted. Neither is comparable with
the Shadow campaign's simulated time — see docs/metrics.md.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..multichain.rpc import RpcClient

LOG = logging.getLogger("experiments.runtime.collectors.rpc")

OBSERVATION_COLUMNS = [
    "run_id", "scenario", "seed", "node_id", "role", "organization",
    "geographic_scope", "region", "country", "continent",
    "timestamp_wallclock", "timestamp_monotonic", "sample_index",
    "block_height", "block_hash", "previous_block_hash", "block_time",
    "peer_count", "peer_connectivity", "transaction_count",
    "confirmed_transaction_count", "mempool_size", "sync_lag",
    "rpc_errors", "p2p_errors", "reachable",
    # Appended, never inserted: a reader that indexes by position must keep
    # working across a change. tests/golden/test_csv_contract.py enforces it.
    "pending_transaction_count", "process_alive", "controller_alive",
]

BLOCK_SIGHTING_COLUMNS = [
    "run_id", "scenario", "node_id", "block_height", "block_hash",
    "first_seen_wallclock", "first_seen_monotonic", "sample_index",
]


@dataclass
class NodeCounters:
    """Errors accumulate over the run; they are reported, never reset."""

    rpc_errors: int = 0
    p2p_errors: int = 0


@dataclass
class RpcCollector:
    """Samples every node and accumulates rows in memory.

    Memory is bounded by the run: twenty nodes at one sample every ten seconds
    for an hour is 7200 rows, which is nothing. Rows are flushed to disk by the
    sampler, so a killed run still keeps what it had collected.
    """

    run_id: str
    scenario: str
    seed: int
    nodes: list          # list[NodePlan]
    clients: dict        # dict[str, RpcClient]
    observations: list = field(default_factory=list)
    sightings: list = field(default_factory=list)
    counters: dict = field(default_factory=dict)
    _seen: dict = field(default_factory=dict)   # (node, height) -> hash
    _index: int = 0

    def __post_init__(self) -> None:
        for node in self.nodes:
            self.counters.setdefault(node.id, NodeCounters())

    def sample(self) -> int:
        """Take one sample of every node. Returns the number of rows added."""
        self._index += 1
        wallclock = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        monotonic = round(time.monotonic(), 6)
        heights: dict[str, int] = {}
        rows = []
        for node in self.nodes:
            client: RpcClient | None = self.clients.get(node.id)
            counters = self.counters[node.id]
            row = _empty_row(self, node, wallclock, monotonic)
            if client is None:
                row["reachable"] = 0
                rows.append(row)
                continue
            info, error = client.try_call("getinfo")
            if error is not None:
                counters.rpc_errors += 1
                row["reachable"] = 0
                row["rpc_errors"] = counters.rpc_errors
                row["p2p_errors"] = counters.p2p_errors
                rows.append(row)
                continue
            row["reachable"] = 1
            height = int(info.get("blocks", 0) or 0)
            heights[node.id] = height
            row["block_height"] = height
            row["peer_count"] = int(info.get("connections", 0) or 0)
            row["peer_connectivity"] = 1 if row["peer_count"] > 0 else 0

            best, best_error = client.try_call("getbestblockhash")
            if best_error is None and best:
                row["block_hash"] = str(best)
                block, block_error = client.try_call("getblock", [str(best)])
                if block_error is None and isinstance(block, dict):
                    row["previous_block_hash"] = block.get("previousblockhash", "")
                    row["block_time"] = block.get("time", "")
                    row["transaction_count"] = len(block.get("tx", []) or [])
                else:
                    counters.rpc_errors += 1
                self._note_sighting(node, height, str(best), wallclock, monotonic)
            elif best_error is not None:
                counters.rpc_errors += 1

            mempool, mempool_error = client.try_call("getmempoolinfo")
            if mempool_error is None and isinstance(mempool, dict):
                row["mempool_size"] = mempool.get("size", "")
                # The same quantity under the name the analysis asks for: the
                # transactions this node is holding but has not yet seen mined.
                row["pending_transaction_count"] = mempool.get("size", "")
            row["confirmed_transaction_count"] = _total_confirmed(info)
            row["rpc_errors"] = counters.rpc_errors
            row["p2p_errors"] = counters.p2p_errors
            rows.append(row)

        if heights:
            tip = max(heights.values())
            for row in rows:
                node_height = heights.get(row["node_id"])
                row["sync_lag"] = "" if node_height is None else tip - node_height
        self.observations.extend(rows)
        return len(rows)

    def _note_sighting(self, node, height: int, block_hash: str,
                       wallclock: str, monotonic: float) -> None:
        """First time this node reported this hash.

        Differences of these timestamps across nodes are the propagation time
        of a block, which the final snapshot cannot recover at all.
        """
        key = (node.id, block_hash)
        if key in self._seen:
            return
        self._seen[key] = height
        self.sightings.append({
            "run_id": self.run_id, "scenario": self.scenario, "node_id": node.id,
            "block_height": height, "block_hash": block_hash,
            "first_seen_wallclock": wallclock, "first_seen_monotonic": monotonic,
            "sample_index": self._index,
        })


def _empty_row(collector: "RpcCollector", node, wallclock: str, monotonic: float) -> dict:
    return {
        "run_id": collector.run_id, "scenario": collector.scenario, "seed": collector.seed,
        "node_id": node.id, "role": node.role, "organization": node.organization,
        "geographic_scope": node.scope, "region": node.region, "country": node.country,
        "continent": node.continent,
        "timestamp_wallclock": wallclock, "timestamp_monotonic": monotonic,
        "sample_index": collector._index,
        "block_height": "", "block_hash": "", "previous_block_hash": "", "block_time": "",
        "peer_count": "", "peer_connectivity": "", "transaction_count": "",
        "confirmed_transaction_count": "", "mempool_size": "",
        "pending_transaction_count": "", "sync_lag": "",
        "process_alive": "", "controller_alive": "",
        "rpc_errors": collector.counters[node.id].rpc_errors,
        "p2p_errors": collector.counters[node.id].p2p_errors,
        "reachable": 0,
    }


def _total_confirmed(info: dict) -> str:
    """MultiChain's getinfo does not carry a confirmed-tx total; declare it absent."""
    del info
    return ""
