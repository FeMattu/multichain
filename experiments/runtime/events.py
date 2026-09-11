"""The harness's own event stream, as JSON lines.

The manifest records phases, which is the shape of the run. This records what
happened *inside* them and in what order: a controller that crashed and was
restarted, a health check that came back degraded, a signal that arrived
mid-schedule. None of that fits a phase list, and all of it is what you want
when a run produced less than it should have.

One file per source under ``raw/events/``, append-only. Every record carries
both clocks — wall clock so it joins with the chain's timestamps, monotonic so
durations survive a clock step. There is no simulated time in these runs and
therefore none in this file.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


class EventLog:
    """Append-only JSONL, safe to share between threads."""

    def __init__(self, run_root, source: str, *, run_id: str = "") -> None:
        self.path = Path(run_root) / "raw" / "events" / ("%s.jsonl" % source)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.source = source
        self.run_id = run_id or Path(run_root).name
        self._lock = threading.Lock()
        self._started = time.monotonic()

    def emit(self, kind: str, **fields) -> dict:
        record = {
            "wall_clock_time": datetime.now(timezone.utc).isoformat(),
            "monotonic_time": round(time.monotonic(), 6),
            "elapsed_wallclock": round(time.monotonic() - self._started, 3),
            "run_id": self.run_id,
            "source": self.source,
            "event": kind,
        }
        record.update(fields)
        line = json.dumps(record, default=str)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return record
