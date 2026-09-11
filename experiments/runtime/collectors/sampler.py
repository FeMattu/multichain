"""The background thread that drives the collectors during a run.

It runs beside the schedule, not inside it, so a slow RPC never delays the
bootstrap. Rows are flushed to disk on every tick rather than held until the
end: a run that is killed at minute forty must still leave forty minutes of
observations, and that is exactly the run whose observations matter most.

Writing is append-only CSV with the header written once, so a partially
written file is still a valid one.
"""

from __future__ import annotations

import csv
import logging
import threading
import time
from pathlib import Path

from .process import PROCESS_COLUMNS, ProcessCollector
from .rpc import BLOCK_SIGHTING_COLUMNS, OBSERVATION_COLUMNS, RpcCollector
from .rpc_explorer import (
    BLOCK_COLUMNS,
    CHAIN_STATE_COLUMNS,
    GAP_COLUMNS,
    TRANSACTION_COLUMNS,
    RpcExplorer,
)

LOG = logging.getLogger("experiments.runtime.collectors.sampler")


class _AppendCsv:
    """Append rows to a CSV, writing the header exactly once."""

    def __init__(self, path: Path, columns: list[str]) -> None:
        self.path = path
        self.columns = columns
        self._written = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open("w", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=columns).writeheader()

    def extend(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        with self.path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.columns, extrasaction="ignore")
            for row in rows:
                writer.writerow(row)
        self._written += len(rows)
        return len(rows)

    @property
    def written(self) -> int:
        return self._written


class Sampler:
    """Periodic observation of a live run."""

    def __init__(self, *, run_id: str, scenario: str, seed: int, nodes, clients,
                 registry, out_dir: Path, interval_s: float = 10.0,
                 run_root: Path | None = None, explorer_node: str = "",
                 explorer_interval_s: float = 2.0,
                 target_block_time_s: float = 0.0,
                 explorer_mode: str = "backfill") -> None:
        self.interval_s = max(1.0, float(interval_s))
        self.target_block_time_s = float(target_block_time_s)
        self.explorer_mode = explorer_mode
        self.registry = registry
        #: Set by the session once the controllers exist; until then the
        #: column is empty, which is the truth - there is no controller yet.
        self.controller_probe = None
        self.out_dir = Path(out_dir)
        self.rpc = RpcCollector(run_id=run_id, scenario=scenario, seed=seed,
                                nodes=list(nodes), clients=dict(clients))
        self.process = ProcessCollector(run_id=run_id, registry=registry)
        self._observations = _AppendCsv(self.out_dir / "node_observations.csv",
                                        OBSERVATION_COLUMNS)
        self._sightings = _AppendCsv(self.out_dir / "block_sightings.csv",
                                     BLOCK_SIGHTING_COLUMNS)
        self._processes = _AppendCsv(self.out_dir / "process_samples.csv",
                                     PROCESS_COLUMNS)
        # The explorer polls faster than the per-node sampler, because its job
        # is to miss no block: at a 5 s target block time a 10 s sample would
        # walk gaps constantly. It runs on its own thread for the same reason.
        self.explorer = None
        self._explorer_thread: threading.Thread | None = None
        self.explorer_interval_s = max(0.5, float(explorer_interval_s))
        if explorer_node and run_root is not None:
            self.explorer = RpcExplorer(
                run_id=run_id, scenario=scenario, run_root=Path(run_root),
                explorer_node=explorer_node, clients=dict(clients),
                mode=explorer_mode,
            )
            self._blocks = _AppendCsv(self.out_dir / "explorer_blocks.csv", BLOCK_COLUMNS)
            self._transactions = _AppendCsv(self.out_dir / "explorer_transactions.csv",
                                            TRANSACTION_COLUMNS)
            self._chain_state = _AppendCsv(self.out_dir / "explorer_chain_state.csv",
                                           CHAIN_STATE_COLUMNS)
            self._gaps = _AppendCsv(self.out_dir / "explorer_gaps.csv", GAP_COLUMNS)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.ticks = 0
        self.explorer_ticks = 0
        self.errors = 0

    # -- control ------------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="sampler", daemon=True)
        self._thread.start()
        LOG.info("sampler started: every %.0fs into %s", self.interval_s, self.out_dir)
        if self.explorer is not None:
            self._explorer_thread = threading.Thread(
                target=self._explorer_loop, name="explorer", daemon=True)
            self._explorer_thread.start()
            LOG.info("rpc explorer started on %s: every %.1fs",
                     self.explorer.explorer_node, self.explorer_interval_s)

    def stop(self, *, timeout_s: float = 30.0) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=timeout_s)
        if self._thread.is_alive():
            LOG.warning("the sampler did not stop within %gs; its last tick may be partial",
                        timeout_s)
        self._thread = None
        if self._explorer_thread is not None:
            self._explorer_thread.join(timeout=timeout_s)
            self._explorer_thread = None
        self.tick()          # one final observation, after everything settled
        if self.explorer is not None:
            # One last walk plus the end-of-run calls, while the daemons are
            # still up: a block produced after the previous tick would
            # otherwise never be recorded.
            try:
                self.explorer.final_snapshot()
            except Exception as exc:  # noqa: BLE001
                LOG.warning("the explorer's final snapshot failed: %s", exc)
            self._flush_explorer()
            contiguity = self.explorer.contiguity()
            if not contiguity["ok"]:
                LOG.warning("the explorer missed %d height(s): %s",
                            contiguity["missing_count"], contiguity["missing"][:10])
            else:
                LOG.info("explorer: %d blocks, heights %s-%s, no gaps",
                         contiguity["checked"], contiguity.get("from"),
                         contiguity.get("to"))
            stall = self.explorer.longest_stall()
            # Ten target block times without a block is not jitter. Saying so
            # here is the difference between an empty metric and a known
            # cause: the chain stopped, and this is the height it stopped at.
            if stall["seconds"] > 10 * max(1, self.target_block_time_s):
                LOG.warning(
                    "the chain stopped advancing: tip stood at height %d for "
                    "%gs (target block time %gs). Every metric that needs "
                    "measured blocks will be empty; check the miner's "
                    "debug.log around that height.",
                    stall["height"], stall["seconds"], self.target_block_time_s)
        LOG.info("sampler stopped: %d ticks, %d observation rows, %d sightings",
                 self.ticks, self._observations.written, self._sightings.written)

    # -- work ---------------------------------------------------------------
    def tick(self) -> None:
        """One round of sampling and flushing. Never raises."""
        try:
            before_obs = len(self.rpc.observations)
            before_sight = len(self.rpc.sightings)
            self.rpc.sample()
            self._annotate_liveness(self.rpc.observations[before_obs:])
            self._observations.extend(self.rpc.observations[before_obs:])
            self._sightings.extend(self.rpc.sightings[before_sight:])
            before_proc = len(self.process.rows)
            self.process.sample()
            self._processes.extend(self.process.rows[before_proc:])
            self.ticks += 1
        except Exception as exc:  # noqa: BLE001 - a collector must not kill a run
            self.errors += 1
            LOG.warning("sampler tick failed (%d so far): %s", self.errors, exc)

    def explorer_tick(self) -> None:
        """One explorer pass. Never raises: it must not kill the run."""
        if self.explorer is None:
            return
        try:
            self.explorer.poll()
            self._flush_explorer()
            self.explorer_ticks += 1
        except Exception as exc:  # noqa: BLE001
            self.errors += 1
            LOG.warning("explorer tick failed: %s", exc)

    def _annotate_liveness(self, rows) -> None:
        """Whether each node's daemon and controller were alive at this sample.

        A node can answer RPC while its controller is dead: the chain keeps
        moving and that node simply stops doing anything. Recorded per sample
        so the moment it happened is in the data, not only in a log.
        """
        for row in rows:
            node_id = row.get("node_id", "")
            daemons = [p for p in self.registry.for_node(node_id)
                       if p.kind == "daemon"] if self.registry else []
            row["process_alive"] = (1 if any(p.alive() for p in daemons)
                                    else (0 if daemons else ""))
            if self.controller_probe is not None:
                row["controller_alive"] = self.controller_probe(node_id)

    def _flush_explorer(self) -> None:
        """Move whatever the explorer accumulated onto disk.

        Flushing every tick rather than at the end is the difference between
        a killed run that keeps its blocks and one that keeps nothing.
        """
        explorer = self.explorer
        if explorer is None:
            return
        if explorer.blocks:
            self._blocks.extend(explorer.blocks)
            explorer.blocks = []
        if explorer.transactions:
            explorer.state.transactions_seen += len(explorer.transactions)
            self._transactions.extend(explorer.transactions)
            explorer.transactions = []
        if explorer.chain_state:
            self._chain_state.extend(explorer.chain_state)
            explorer.chain_state = []
        if explorer.state.gaps:
            self._gaps.extend([
                {"run_id": explorer.run_id, "height_from": g["height_from"],
                 "height_to": g["height_to"], "reason": "block not retrievable",
                 "observed_wallclock": ""}
                for g in explorer.state.gaps])
            explorer.state.gaps = []

    def _loop(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            self.tick()
            elapsed = time.monotonic() - started
            self._stop.wait(max(0.5, self.interval_s - elapsed))

    def _explorer_loop(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            self.explorer_tick()
            elapsed = time.monotonic() - started
            self._stop.wait(max(0.2, self.explorer_interval_s - elapsed))

    def summary(self) -> dict:
        out = {
            "ticks": self.ticks,
            "errors": self.errors,
            "interval_s": self.interval_s,
            "observation_rows": self._observations.written,
            "block_sighting_rows": self._sightings.written,
            "process_rows": self._processes.written,
            "files": {
                "node_observations": str(self._observations.path),
                "block_sightings": str(self._sightings.path),
                "process_samples": str(self._processes.path),
            },
        }
        if self.explorer is not None:
            out["explorer"] = {
                **self.explorer.summary(),
                "ticks": self.explorer_ticks,
                "interval_s": self.explorer_interval_s,
                "block_rows": self._blocks.written,
                "transaction_rows": self._transactions.written,
                "chain_state_rows": self._chain_state.written,
            }
        return out
