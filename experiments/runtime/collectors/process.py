"""Per-process resource sampling, read straight from ``/proc``.

No psutil: the harness must run on a bare Ubuntu 20.04 with nothing installed
beyond the standard library, and everything needed is two files.

``/proc/<pid>/stat`` gives cumulative CPU jiffies, ``/proc/<pid>/status`` the
resident set, ``/proc/<pid>/io`` the byte counters. CPU is reported both as
the cumulative seconds and as a percentage over the interval since the last
sample, because the cumulative figure is the one that survives a missed
sample and the percentage is the one a reader wants.

``/proc/<pid>/io`` is unreadable for a process owned by another user, which is
exactly the case when the daemons run under sudo. That is recorded as an empty
value, never as a zero: zero disk I/O and unknown disk I/O are different
claims.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

LOG = logging.getLogger("experiments.runtime.collectors.process")

PROCESS_COLUMNS = [
    "run_id", "node_id", "process_kind", "process_label", "pid",
    "timestamp_wallclock", "timestamp_monotonic", "sample_index",
    "alive", "cpu_seconds_total", "cpu_percent", "memory_bytes",
    "memory_peak_bytes", "threads", "disk_read_bytes", "disk_write_bytes",
    "process_restarts",
]

CLOCK_TICKS = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


@dataclass
class _Previous:
    cpu_seconds: float
    monotonic: float


@dataclass
class ProcessCollector:
    """Samples the processes a :class:`ProcessRegistry` owns."""

    run_id: str
    registry: object                    # ProcessRegistry
    rows: list = field(default_factory=list)
    _previous: dict = field(default_factory=dict)
    _index: int = 0

    def sample(self) -> int:
        self._index += 1
        wallclock = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        monotonic = time.monotonic()
        added = 0
        for process in getattr(self.registry, "processes", []):
            pid = process.pid
            row = {
                "run_id": self.run_id, "node_id": process.node_id,
                "process_kind": process.kind, "process_label": process.label,
                "pid": pid or "", "timestamp_wallclock": wallclock,
                "timestamp_monotonic": round(monotonic, 6), "sample_index": self._index,
                "alive": int(process.alive()), "cpu_seconds_total": "", "cpu_percent": "",
                "memory_bytes": "", "memory_peak_bytes": "", "threads": "",
                "disk_read_bytes": "", "disk_write_bytes": "",
                "process_restarts": process.restarts,
            }
            if pid and process.alive():
                stat = read_stat(pid)
                if stat is not None:
                    row["cpu_seconds_total"] = round(stat["cpu_seconds"], 3)
                    row["threads"] = stat["threads"]
                    previous = self._previous.get(pid)
                    if previous is not None:
                        elapsed = monotonic - previous.monotonic
                        if elapsed > 0:
                            delta = stat["cpu_seconds"] - previous.cpu_seconds
                            row["cpu_percent"] = round(100.0 * delta / elapsed, 2)
                    self._previous[pid] = _Previous(stat["cpu_seconds"], monotonic)
                memory = read_memory(pid)
                if memory is not None:
                    row["memory_bytes"] = memory["rss_bytes"]
                    row["memory_peak_bytes"] = memory["peak_bytes"]
                io_counters = read_io(pid)
                if io_counters is not None:
                    row["disk_read_bytes"] = io_counters["read_bytes"]
                    row["disk_write_bytes"] = io_counters["write_bytes"]
            self.rows.append(row)
            added += 1
        return added


def read_stat(pid: int) -> dict | None:
    """Cumulative CPU time and thread count of a pid."""
    path = Path("/proc/%d/stat" % pid)
    try:
        text = path.read_text()
    except OSError:
        return None
    # The comm field may contain spaces and parentheses; everything after the
    # last ')' is positional, and field 14 of that remainder is utime.
    try:
        tail = text[text.rindex(")") + 2:].split()
        utime, stime = int(tail[11]), int(tail[12])
        threads = int(tail[17])
    except (ValueError, IndexError):
        return None
    return {"cpu_seconds": (utime + stime) / float(CLOCK_TICKS), "threads": threads}


def read_memory(pid: int) -> dict | None:
    path = Path("/proc/%d/status" % pid)
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return None
    out = {"rss_bytes": "", "peak_bytes": ""}
    for line in lines:
        if line.startswith("VmRSS:"):
            out["rss_bytes"] = int(line.split()[1]) * 1024
        elif line.startswith("VmHWM:"):
            out["peak_bytes"] = int(line.split()[1]) * 1024
    return out


def read_io(pid: int) -> dict | None:
    """Disk byte counters, or None when they are not readable.

    Unreadable is the normal case for a process started through sudo, and it
    must stay distinguishable from zero.
    """
    path = Path("/proc/%d/io" % pid)
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return None
    out = {"read_bytes": "", "write_bytes": ""}
    for line in lines:
        if line.startswith("read_bytes:"):
            out["read_bytes"] = int(line.split()[1])
        elif line.startswith("write_bytes:"):
            out["write_bytes"] = int(line.split()[1])
    return out
