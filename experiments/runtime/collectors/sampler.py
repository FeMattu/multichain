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
                 registry, out_dir: Path, interval_s: float = 10.0) -> None:
        self.interval_s = max(1.0, float(interval_s))
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
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.ticks = 0
        self.errors = 0

    # -- control ------------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="sampler", daemon=True)
        self._thread.start()
        LOG.info("sampler started: every %.0fs into %s", self.interval_s, self.out_dir)

    def stop(self, *, timeout_s: float = 30.0) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=timeout_s)
        if self._thread.is_alive():
            LOG.warning("the sampler did not stop within %gs; its last tick may be partial",
                        timeout_s)
        self._thread = None
        self.tick()          # one final observation, after everything settled
        LOG.info("sampler stopped: %d ticks, %d observation rows, %d sightings",
                 self.ticks, self._observations.written, self._sightings.written)

    # -- work ---------------------------------------------------------------
    def tick(self) -> None:
        """One round of sampling and flushing. Never raises."""
        try:
            before_obs = len(self.rpc.observations)
            before_sight = len(self.rpc.sightings)
            self.rpc.sample()
            self._observations.extend(self.rpc.observations[before_obs:])
            self._sightings.extend(self.rpc.sightings[before_sight:])
            before_proc = len(self.process.rows)
            self.process.sample()
            self._processes.extend(self.process.rows[before_proc:])
            self.ticks += 1
        except Exception as exc:  # noqa: BLE001 - a collector must not kill a run
            self.errors += 1
            LOG.warning("sampler tick failed (%d so far): %s", self.errors, exc)

    def _loop(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            self.tick()
            elapsed = time.monotonic() - started
            self._stop.wait(max(0.5, self.interval_s - elapsed))

    def summary(self) -> dict:
        return {
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
