"""Block-explorer-style collection: poll the chain, miss nothing, keep the raw.

The admin is the explorer. It is subscribed to every stream and its
``listblocks`` reports the proposer of each height directly, which is why the
Shadow suite used its snapshot as the primary source. What that snapshot could
not give was *time*: one reading at the end of the run. This collector polls,
so the same facts arrive as a series.

Three properties matter more than the polling itself.

**No gaps.** Comparing ``getblockcount`` with the last height seen and
fetching only the tip would lose every block produced between two polls - and
at a 5 s target block time with a 2 s interval that is most of them under any
load. Every intermediate height is walked with ``getblockhash`` +
``getblock``, and a gap that cannot be closed is recorded as a gap rather than
skipped.

**The raw answer is kept.** Every call is written under
``raw/rpc/``, so a metric that looks wrong can be traced to the bytes the node
actually returned. Without that, a disagreement between the analysis and
reality is unfalsifiable.

**One node cannot see everything.** Height, hash, proposer and transactions
come from the explorer. Fork detection, sync lag and propagation are
*comparisons between nodes* and are collected from all of them; deriving them
from a single node would be inventing them. ``docs/metrics.md`` says which is
which, and so does every column's ``source`` in the catalogue.

Every RPC used here was checked against ``src/rpc/rpclist.cpp``. In
particular ``getvalidatorinfo`` and ``getweight`` do **not** exist in this
fork; the weight registry is ``getallweights`` / ``getnodeweight`` /
``getlocalweight``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..multichain.rpc import RpcClient, RpcError

#: Collector modes. `live` starts at the tip and follows it; `backfill` walks
#: the chain from `from_height`, which is what you want when a collector is
#: started against a chain that is already running. The mode is recorded in
#: the manifest, because it decides what "no blocks before height N" means.
LIVE = "live"
BACKFILL = "backfill"

LOG = logging.getLogger("experiments.runtime.collectors.explorer")

BLOCK_COLUMNS = [
    "run_id", "scenario", "height", "hash", "previous_block_hash", "block_time",
    "observed_wallclock", "observed_monotonic", "miner", "miner_host",
    "proposer_weight", "total_weight", "validators", "size_bytes",
    "transaction_count", "confirmations", "source_node", "gap_filled",
]

TRANSACTION_COLUMNS = [
    "run_id", "scenario", "height", "block_hash", "txid", "index_in_block",
    "size_bytes", "fee", "kind", "from_address", "observed_wallclock",
    "first_seen_mempool_wallclock", "included_wallclock", "inclusion_latency_s",
    "status",
]

CHAIN_STATE_COLUMNS = [
    "run_id", "scenario", "node_id", "observed_wallclock", "observed_monotonic",
    "sample_index", "block_height", "best_hash", "peer_count", "mempool_size",
    "difficulty", "chain_name", "reachable", "rpc_errors",
]

GAP_COLUMNS = ["run_id", "height_from", "height_to", "reason", "observed_wallclock"]

#: Read-only calls taken once per sample from the explorer node. Each is
#: present in src/rpc/rpclist.cpp - verified, not assumed.
EXPLORER_SNAPSHOT_CALLS = [
    ("getinfo", []),
    ("getblockchaininfo", []),
    ("getmininginfo", []),
    ("getrawmempool", []),
    ("getallweights", []),
    ("listpermissions", ["mine"]),
    ("getpeerinfo", []),
]

#: Taken once, at the end: expensive or only meaningful complete.
EXPLORER_FINAL_CALLS = [
    ("gettxoutsetinfo", []),
    ("listminers", []),
    ("liststreams", []),
    ("getnetworkinfo", []),
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class ExplorerState:
    last_height: int = 0
    blocks_seen: int = 0
    transactions_seen: int = 0
    gaps: list = field(default_factory=list)
    rpc_errors: int = 0
    samples: int = 0
    #: Every height actually collected. Kept here, not derived from the row
    #: list, because the sampler drains that list to disk on every tick - so
    #: reading it at the end reported "0 blocks" for a run that had collected
    #: forty.
    heights: set = field(default_factory=set)
    #: txid -> (wall clock, monotonic) of the first time it was seen waiting
    #: in the mempool. Without it a transaction can only be reported as
    #: confirmed, never as "confirmed after N seconds", and the inclusion
    #: latency is the quantity the emulated network actually changes.
    mempool_first_seen: dict = field(default_factory=dict)
    #: When the tip last moved, and the longest it ever stood still. A chain
    #: that stops advancing produces artefacts that are complete and empty;
    #: without this the only evidence is "blocchi insufficienti" in
    #: run_index.csv, days later.
    tip_moved_monotonic: float = 0.0
    longest_stall_s: float = 0.0
    stalled_at_height: int = 0


class RpcExplorer:
    """Polls one node as a block explorer, and the others for comparison."""

    def __init__(self, *, run_id: str, scenario: str, run_root: Path,
                 explorer_node: str, clients: dict, host_by_address: dict | None = None,
                 keep_raw: bool = True, raw_every: int = 1,
                 mode: str = BACKFILL, from_height: int = 1) -> None:
        self.run_id = run_id
        self.scenario = scenario
        self.run_root = Path(run_root)
        self.explorer_node = explorer_node
        self.clients = dict(clients)
        self.host_by_address = dict(host_by_address or {})
        self._addresses_loaded = 0
        self.keep_raw = keep_raw
        self.raw_every = max(1, raw_every)
        if mode not in (LIVE, BACKFILL):
            raise ValueError("explorer mode must be %r or %r, not %r"
                             % (LIVE, BACKFILL, mode))
        self.mode = mode
        self.from_height = max(0, int(from_height) - 1)
        self.state = ExplorerState()
        #: Survives a restart, so a resumed collector neither re-walks the
        #: chain nor leaves a hole where it stopped.
        self.index_path = self.run_root / "runtime" / "explorer-state.json"
        self._resume()
        self.blocks: list = []
        self.transactions: list = []
        self.chain_state: list = []
        self._raw_dir = self.run_root / "raw" / "rpc"
        self._raw_dir.mkdir(parents=True, exist_ok=True)

    # -- restartability -----------------------------------------------------
    def _resume(self) -> None:
        """Pick up where a previous collector stopped, if there was one."""
        try:
            saved = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # No index: a live collector starts at the tip and a backfill one
            # at the height it was told, which is the first poll's job.
            self.state.last_height = self.from_height if self.mode == BACKFILL else 0
            self.resumed_from = None
            return
        self.state.last_height = int(saved.get("last_height", 0))
        self.resumed_from = self.state.last_height
        LOG.info("explorer resuming after height %d (%s)",
                 self.state.last_height, self.index_path)

    def _persist_index(self) -> None:
        """Write the index atomically: a torn index would replay or skip."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({
            "run_id": self.run_id,
            "mode": self.mode,
            "last_height": self.state.last_height,
            "blocks_seen": self.state.blocks_seen,
            "updated_at": _utc(),
        }, indent=2), encoding="utf-8")
        os.replace(temporary, self.index_path)

    # -- who is who ---------------------------------------------------------
    def refresh_addresses(self) -> int:
        """Map wallet addresses to host names, from runtime/shared/*.addr.

        Re-read rather than read once: the files appear during the bootstrap
        as each node publishes its address, so a single read at start-up
        leaves every proposer unnamed - which is what made `miner_host` empty
        for a whole run. The analysis keys on host names, never on addresses,
        so this is not cosmetic.
        """
        shared = self.run_root / "runtime" / "shared"
        if not shared.is_dir():
            return len(self.host_by_address)
        for path in sorted(shared.glob("*.addr")):
            try:
                address = path.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if address:
                self.host_by_address[address] = path.stem
        if len(self.host_by_address) != self._addresses_loaded:
            self._addresses_loaded = len(self.host_by_address)
            LOG.debug("explorer knows %d node addresses", self._addresses_loaded)
        return len(self.host_by_address)

    # -- raw persistence ----------------------------------------------------
    def _store_raw(self, method: str, payload, *, suffix: str = "") -> None:
        if not self.keep_raw:
            return
        name = "%s%s.jsonl" % (method, ("-" + suffix) if suffix else "")
        body = json.dumps(payload, default=str, sort_keys=True)
        record = {"at": _utc(), "method": method, "node": self.explorer_node,
                  # A stable identifier for the payload: two runs that saw the
                  # same answer produce the same digest, and a truncated line
                  # is detectable without re-reading the chain.
                  "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                  "bytes": len(body),
                  "result": payload}
        line = json.dumps(record, default=str) + "\n"
        path = self._raw_dir / name
        # One write per line, flushed and fsynced: a killed run leaves whole
        # lines, never half a JSON object for the analysis to trip over.
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    # -- RPC with retry -----------------------------------------------------
    def _call(self, method: str, params: list | None = None, *,
              node_id: str | None = None, attempts: int = 3,
              backoff_s: float = 0.5, store: bool = False):
        """One call, retried with backoff. Returns None once it gives up.

        A node restarting, or busy writing a block, refuses a connection for a
        moment; treating that as data loss would put holes in the series for
        no reason.
        """
        client: RpcClient | None = self.clients.get(node_id or self.explorer_node)
        if client is None:
            return None
        delay = backoff_s
        for attempt in range(1, attempts + 1):
            try:
                result = client.call(method, params)
                if store:
                    self._store_raw(method, result)
                return result
            except RpcError as exc:
                self.state.rpc_errors += 1
                if attempt == attempts:
                    LOG.debug("%s on %s gave up after %d attempts: %s",
                              method, node_id or self.explorer_node, attempts, exc)
                    return None
                time.sleep(delay)
                delay *= 2
        return None

    # -- the explorer -------------------------------------------------------
    def poll(self) -> dict:
        """One pass: new blocks first, then the comparative state."""
        self.state.samples += 1
        self.refresh_addresses()
        produced = {"blocks": 0, "transactions": 0, "gaps": 0}
        self._watch_mempool()
        tip = self._call("getblockcount")
        if tip is None:
            LOG.debug("the explorer node did not answer this tick")
            self._collect_chain_state()
            return produced

        tip = int(tip)
        # A live collector joins at the tip: the blocks before it belong to a
        # history it did not observe, and claiming a first_seen for them would
        # be a measurement of nothing. A backfill collector walks them on
        # purpose. Either way this happens once.
        if self.mode == LIVE and self.state.samples == 1 and self.resumed_from is None:
            self.state.last_height = tip
            self.state.tip_moved_monotonic = time.monotonic()
            LOG.info("explorer joined live at height %d", tip)
            self._persist_index()
            self._collect_chain_state()
            return produced

        if tip > self.state.last_height:
            first = self.state.last_height + 1
            weights = self._weight_snapshot()
            for height in range(first, tip + 1):
                row = self._collect_block(height, weights,
                                          gap_filled=height < tip)
                if row is None:
                    self.state.gaps.append({"height_from": height, "height_to": height})
                    produced["gaps"] += 1
                    continue
                produced["blocks"] += 1
                produced["transactions"] += row.pop("_transactions", 0)
            self.state.last_height = tip
            self.state.tip_moved_monotonic = time.monotonic()
        elif self.state.tip_moved_monotonic:
            stalled = time.monotonic() - self.state.tip_moved_monotonic
            if stalled > self.state.longest_stall_s:
                self.state.longest_stall_s = stalled
                self.state.stalled_at_height = self.state.last_height

        if self.state.samples % self.raw_every == 0:
            for method, params in EXPLORER_SNAPSHOT_CALLS:
                self._call(method, params, store=True, attempts=1)

        self._collect_chain_state()
        self._persist_index()
        return produced

    def _watch_mempool(self) -> None:
        """Record the first sighting of every pending transaction.

        Cheap and unmissable only up to the poll interval: a transaction that
        is mined between two polls is never seen waiting, and its latency is
        reported as unavailable rather than guessed at zero.
        """
        pending = self._call("getrawmempool", attempts=1)
        if not isinstance(pending, (list, dict)):
            return
        now, monotonic = _utc(), time.monotonic()
        for txid in (pending.keys() if isinstance(pending, dict) else pending):
            self.state.mempool_first_seen.setdefault(str(txid), (now, monotonic))

    def _weight_snapshot(self) -> dict:
        """The live weight map, so a block records the weight AT proposal.

        Read once per batch of new blocks rather than per block: it is the
        registry's current view either way, and asking per block would make
        the collector's own load scale with the block rate.
        """
        result = self._call("getallweights", attempts=1)
        if not isinstance(result, dict):
            return {"weights": {}, "total": 0, "validators": 0}
        return result

    def _collect_block(self, height: int, weights: dict, *,
                       gap_filled: bool) -> dict | None:
        block_hash = self._call("getblockhash", [height])
        if not block_hash:
            return None
        block = self._call("getblock", [block_hash, 4])
        if not isinstance(block, dict):
            # verbose=4 is not accepted by every build; fall back to the
            # boolean form rather than losing the block.
            block = self._call("getblock", [block_hash, True])
        if not isinstance(block, dict):
            return None
        self._store_raw("getblock", block, suffix="h%d" % height)

        miner = block.get("miner", "")
        weight_map = weights.get("weights") or {}
        transactions = block.get("tx") or []
        row = {
            "run_id": self.run_id, "scenario": self.scenario,
            "height": height, "hash": block_hash,
            "previous_block_hash": block.get("previousblockhash", ""),
            "block_time": block.get("time", ""),
            "observed_wallclock": _utc(),
            "observed_monotonic": round(time.monotonic(), 6),
            "miner": miner,
            "miner_host": self.host_by_address.get(miner, ""),
            "proposer_weight": weight_map.get(miner, ""),
            "total_weight": weights.get("total", ""),
            "validators": weights.get("validators", ""),
            "size_bytes": block.get("size", ""),
            "transaction_count": len(transactions),
            "confirmations": block.get("confirmations", ""),
            "source_node": self.explorer_node,
            "gap_filled": int(gap_filled),
        }
        self.blocks.append(row)
        self.state.blocks_seen += 1
        self.state.heights.add(height)
        row["_transactions"] = self._collect_transactions(height, block_hash, transactions)
        return row

    def _collect_transactions(self, height: int, block_hash: str,
                              transactions: list) -> int:
        """One row per transaction in the block.

        ``tx`` is a list of txids with verbose=1 and a list of objects with
        the higher verbosity; both shapes are handled, because which one a
        build returns is not something to assume.
        """
        count = 0
        for index, entry in enumerate(transactions):
            if isinstance(entry, str):
                txid, size, fee, kind = entry, "", "", ""
            elif isinstance(entry, dict):
                txid = entry.get("txid", "")
                size = entry.get("size", "")
                fee = entry.get("fee", "")
                kind = "coinbase" if entry.get("vin") and any(
                    "coinbase" in v for v in entry.get("vin", [])) else "tx"
            else:
                continue
            seen = self.state.mempool_first_seen.pop(txid, None)
            included_wallclock, included_monotonic = _utc(), time.monotonic()
            latency = (round(included_monotonic - seen[1], 3)
                       if seen is not None else "")
            self.transactions.append({
                "run_id": self.run_id, "scenario": self.scenario,
                "height": height, "block_hash": block_hash, "txid": txid,
                "index_in_block": index, "size_bytes": size, "fee": fee,
                "kind": kind or ("coinbase" if index == 0 else "tx"),
                "from_address": "", "observed_wallclock": included_wallclock,
                "first_seen_mempool_wallclock": seen[0] if seen else "",
                "included_wallclock": included_wallclock,
                # Empty, not zero: a transaction mined between two polls was
                # never observed waiting, and zero would read as instant.
                "inclusion_latency_s": latency,
                "status": "confirmed",
            })
            count += 1
        return count

    # -- the comparative part ----------------------------------------------
    def _collect_chain_state(self) -> None:
        """Every node's own view.

        This is the half a single explorer cannot provide: sync lag, peer
        counts and disagreement at a common height are relations between
        nodes, not properties of one.
        """
        wallclock, monotonic = _utc(), round(time.monotonic(), 6)
        for node_id in sorted(self.clients):
            info = self._call("getinfo", node_id=node_id, attempts=1)
            reachable = isinstance(info, dict)
            best = self._call("getbestblockhash", node_id=node_id, attempts=1) \
                if reachable else None
            mempool = self._call("getmempoolinfo", node_id=node_id, attempts=1) \
                if reachable else None
            self.chain_state.append({
                "run_id": self.run_id, "scenario": self.scenario, "node_id": node_id,
                "observed_wallclock": wallclock, "observed_monotonic": monotonic,
                "sample_index": self.state.samples,
                "block_height": (info or {}).get("blocks", "") if reachable else "",
                "best_hash": best or "",
                "peer_count": (info or {}).get("connections", "") if reachable else "",
                "mempool_size": (mempool or {}).get("size", "")
                if isinstance(mempool, dict) else "",
                "difficulty": (info or {}).get("difficulty", "") if reachable else "",
                "chain_name": (info or {}).get("chainname", "") if reachable else "",
                "reachable": int(reachable),
                "rpc_errors": self.state.rpc_errors,
            })

    # -- end of run ---------------------------------------------------------
    def final_snapshot(self) -> None:
        """The calls worth taking once, complete, at the end."""
        for method, params in EXPLORER_FINAL_CALLS:
            self._call(method, params, store=True, attempts=2)
        # A last poll, so a block produced after the previous tick is not lost.
        self.poll()

    def summary(self) -> dict:
        return {
            "explorer_node": self.explorer_node,
            "samples": self.state.samples,
            "blocks_collected": self.state.blocks_seen,
            "transactions_collected": self.state.transactions_seen
            or len(self.transactions),
            "highest_height": self.state.last_height,
            "gaps": self.state.gaps,
            "gap_count": len(self.state.gaps),
            "rpc_errors": self.state.rpc_errors,
            "raw_dir": str(self._raw_dir),
            "contiguous": self.contiguity(),
        }

    def contiguity(self) -> dict:
        """Are the collected heights actually contiguous?

        The claim "no gaps" has to be checkable, not asserted. This is what
        the end-to-end test asserts on.
        """
        heights = sorted(self.state.heights)
        if not heights:
            return {"ok": True, "checked": 0, "missing": []}
        expected = set(range(heights[0], heights[-1] + 1))
        missing = sorted(expected - set(heights))
        return {"ok": not missing, "checked": len(heights),
                "from": heights[0], "to": heights[-1], "missing": missing[:50],
                "missing_count": len(missing)}

    def longest_stall(self) -> dict:
        """The longest the tip stood still, and where.

        Gap-free heights say the explorer missed nothing; they say nothing
        about whether the chain kept moving. A run whose tip froze at the
        setup boundary collects every block up to that height, contiguously,
        and measures none of them.
        """
        return {"seconds": round(self.state.longest_stall_s, 1),
                "height": self.state.stalled_at_height,
                "tip": self.state.last_height}
