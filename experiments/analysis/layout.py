"""Where a run keeps its files, in whichever layout it uses.

Two layouts exist and both must keep working: the archived Shadow campaign
(``<run>/metrics``, ``<run>/shared``, ``<run>/data``) and the one this harness
writes (``<run>/raw/metrics``, ``<run>/runtime/shared``, ``<run>/runtime/data``).

Rather than fork the migrated analysers - which would mean two copies of every
metric definition, and eventually two answers - they ask here. The resolution
is by inspection, never by a flag, so a directory can be handed to any of them
without being told what it is.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunLayout:
    root: Path
    metrics: Path
    shared: Path
    data: Path
    style: str          # "native" | "legacy"

    @property
    def epochs(self) -> Path:
        """The per-epoch samples, under whichever name this run used."""
        for name in ("epochs", "epoche"):
            candidate = self.metrics / name
            if candidate.is_dir():
                return candidate
        return self.metrics / "epochs"

    def epoch_file(self, native: str, legacy: str) -> Path:
        """One per-epoch file, preferring the current name over the archive's."""
        directory = self.epochs
        for name in (native, legacy):
            candidate = directory / name
            if candidate.is_file():
                return candidate
        return directory / native


def resolve(run_root: Path | str) -> RunLayout:
    """Work out which layout ``run_root`` uses."""
    root = Path(run_root)
    native_metrics = root / "raw" / "metrics"
    if native_metrics.is_dir() or (root / "manifest.json").is_file():
        return RunLayout(root=root, metrics=native_metrics,
                         shared=root / "runtime" / "shared",
                         data=root / "runtime" / "data", style="native")
    return RunLayout(root=root, metrics=root / "metrics",
                     shared=root / "shared", data=root / "data", style="legacy")
