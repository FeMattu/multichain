"""Finding, indexing and archiving the nodes' own logs.

``debug.log`` is where everything the RPC cannot show lives: the sortition
scores, the Phi feedback, the rejected blocks, the weight-engine folds. The
analysis pipeline parses it, so the harness's job is to make sure every one of
them is present, complete and locatable, and to say plainly when one is not.

The location moved between generations — the archived Shadow runs keep the
file at ``data/<host>/debug.log``, a freshly run node at
``data/<host>/<chain>/debug.log`` — so both are searched, which is also what
the pipeline does.
"""

from __future__ import annotations

import gzip
import hashlib
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

LOG = logging.getLogger("experiments.runtime.collectors.logs")

LOG_INDEX_COLUMNS = [
    "run_id", "node_id", "kind", "path", "size_bytes", "lines", "sha256", "compressed",
]

#: Compress anything larger than this when archiving. A twenty-node run with
#: -debug=wpoa produces hundreds of megabytes of debug.log.
COMPRESS_ABOVE_BYTES = 8 * 1024 * 1024


@dataclass
class LogFile:
    node_id: str
    kind: str
    path: Path
    size_bytes: int
    lines: int
    sha256: str
    compressed: bool = False

    def as_row(self, run_id: str) -> dict:
        return {
            "run_id": run_id, "node_id": self.node_id, "kind": self.kind,
            "path": str(self.path), "size_bytes": self.size_bytes,
            "lines": self.lines, "sha256": self.sha256,
            "compressed": int(self.compressed),
        }


def debug_log_path(run_root: Path, node_id: str, chain: str) -> Path | None:
    """Where this node's ``debug.log`` actually is, both layouts searched."""
    data = run_root / "runtime" / "data" / node_id
    for candidate in (data / chain / "debug.log", data / "debug.log"):
        if candidate.is_file():
            return candidate
    return None


def discover(run_root: Path, node_ids: list[str], chain: str) -> list[LogFile]:
    """Every log the run produced, per node."""
    found: list[LogFile] = []
    for node_id in node_ids:
        debug = debug_log_path(run_root, node_id, chain)
        if debug is not None:
            found.append(_describe(node_id, "debug.log", debug))
        else:
            LOG.warning("no debug.log for node %s: its diagnostics are unavailable", node_id)
        node_logs = run_root / "logs" / node_id
        if node_logs.is_dir():
            for path in sorted(node_logs.glob("*.log")):
                found.append(_describe(node_id, path.name, path))
    return found


def _describe(node_id: str, kind: str, path: Path) -> LogFile:
    size = path.stat().st_size
    digest = hashlib.sha256()
    lines = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            lines += chunk.count(b"\n")
    return LogFile(node_id=node_id, kind=kind, path=path, size_bytes=size,
                   lines=lines, sha256=digest.hexdigest())


def archive(run_root: Path, logs: list[LogFile], *,
            compress_above: int = COMPRESS_ABOVE_BYTES) -> list[LogFile]:
    """Copy the nodes' own logs under ``logs/<node>/``, compressing big ones.

    Copies rather than moves: the data directory stays intact, so a run can be
    re-collected without having been damaged by the first attempt.
    """
    archived = []
    for entry in logs:
        target_dir = run_root / "logs" / entry.node_id
        target_dir.mkdir(parents=True, exist_ok=True)
        if entry.path.parent == target_dir:
            archived.append(entry)
            continue
        if entry.size_bytes > compress_above:
            target = target_dir / (entry.kind + ".gz")
            with entry.path.open("rb") as source, gzip.open(target, "wb") as sink:
                shutil.copyfileobj(source, sink, length=1 << 20)
            archived.append(LogFile(entry.node_id, entry.kind, target,
                                    target.stat().st_size, entry.lines,
                                    entry.sha256, compressed=True))
        else:
            target = target_dir / entry.kind
            shutil.copy2(entry.path, target)
            archived.append(LogFile(entry.node_id, entry.kind, target,
                                    entry.size_bytes, entry.lines, entry.sha256))
    return archived


def summarise(logs: list[LogFile]) -> dict:
    return {
        "files": len(logs),
        "total_bytes": sum(entry.size_bytes for entry in logs),
        "total_lines": sum(entry.lines for entry in logs),
        "nodes_with_debug_log": sorted({e.node_id for e in logs if e.kind.startswith("debug.log")}),
    }
