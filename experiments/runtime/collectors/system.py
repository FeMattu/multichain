"""Host-level facts, sampled once at the start and once at the end.

The host is shared by every emulated node, so its load is a confounder: a run
whose block times drifted because the machine was saturated should be
readable as such rather than as a protocol result. Load average and memory
pressure at both ends of the run are the cheapest way to make that visible.
"""

from __future__ import annotations

import os
import platform
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path


def snapshot(run_root: Path | None = None) -> dict:
    """Everything worth knowing about the host at this instant."""
    out = {
        "timestamp_wallclock": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "timestamp_monotonic": round(time.monotonic(), 6),
        "hostname": platform.node(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "loadavg_1m": None, "loadavg_5m": None, "loadavg_15m": None,
        "memory_total_bytes": None, "memory_available_bytes": None,
        "swap_total_bytes": None, "swap_free_bytes": None,
        "disk_total_bytes": None, "disk_free_bytes": None,
        "open_file_limit": None,
    }
    try:
        one, five, fifteen = os.getloadavg()
        out.update({"loadavg_1m": round(one, 2), "loadavg_5m": round(five, 2),
                    "loadavg_15m": round(fifteen, 2)})
    except (OSError, AttributeError):
        pass
    meminfo = _meminfo()
    out["memory_total_bytes"] = meminfo.get("MemTotal")
    out["memory_available_bytes"] = meminfo.get("MemAvailable")
    out["swap_total_bytes"] = meminfo.get("SwapTotal")
    out["swap_free_bytes"] = meminfo.get("SwapFree")
    if run_root is not None:
        try:
            usage = shutil.disk_usage(str(run_root))
            out["disk_total_bytes"] = usage.total
            out["disk_free_bytes"] = usage.free
        except OSError:
            pass
    try:
        import resource

        out["open_file_limit"] = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
    except (ImportError, ValueError):
        pass
    return out


def _meminfo() -> dict:
    path = Path("/proc/meminfo")
    if not path.is_file():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(":"):
            try:
                out[parts[0][:-1]] = int(parts[1]) * 1024
            except ValueError:
                continue
    return out


def enough_headroom(node_count: int, run_root: Path) -> list[str]:
    """Warnings about a host that will struggle with this many nodes.

    Advisory only. Twenty ``multichaind`` processes on two cores will produce
    block times that say more about the host than about the protocol, and the
    run should say so before it starts rather than after it is analysed.
    """
    warnings = []
    facts = snapshot(run_root)
    cpus = facts.get("cpu_count") or 1
    if node_count > cpus * 4:
        warnings.append(
            "%d nodes on %d CPUs: block times will reflect host contention as much as "
            "the protocol. Consider fewer nodes, a longer target-block-time, or a "
            "bigger machine." % (node_count, cpus)
        )
    available = facts.get("memory_available_bytes")
    if available is not None and available < node_count * 200 * 1024 * 1024:
        warnings.append(
            "%.1f GiB available for %d nodes: multichaind needs roughly 200 MiB each."
            % (available / 1024 ** 3, node_count)
        )
    free = facts.get("disk_free_bytes")
    if free is not None and free < 2 * 1024 ** 3:
        warnings.append(
            "%.1f GiB free under the results root: debug logs alone can exceed that."
            % (free / 1024 ** 3)
        )
    limit = facts.get("open_file_limit")
    if limit is not None and limit < 4096:
        warnings.append(
            "the open-file limit is %d; %d daemons with their peers need more. "
            "Raise it with 'ulimit -n 8192'." % (limit, node_count)
        )
    return warnings
