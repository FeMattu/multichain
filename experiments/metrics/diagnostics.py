"""What a run actually produced, against what it was supposed to produce.

Two jobs, one inventory. Before a fix it is the baseline: which files exist,
how many rows each table carries, what is missing and why. After a fix it is
the acceptance check, and the two are comparable because they are the same
code.

The point is the *absences*. A run directory that looks full is not evidence:
a table can exist with a header and no rows, a report can be generated from
nothing, and a node can have a controller log that stops after `setup`. Each
of those reads as success from a file listing, so this module counts rows,
not files, and names every expectation it fails to find.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from .catalogue import ALL_TABLES, HISTORICAL_TABLES
from .validators import check_run

#: Keys the manifest must carry for a run to be interpretable on its own.
#: `temporal_model` is the one that stops a reader assuming Shadow semantics.
REQUIRED_MANIFEST_KEYS = [
    "run_id", "scenario", "topology", "seed", "git_commit", "branch",
    "network_backend_requested", "network_backend_used", "fallback_confirmed",
    "temporal_model", "node_count", "miner_count",
    "started_at_wallclock", "ended_at_wallclock", "duration_wallclock_seconds",
    "rpc_collector_mode", "multichain_binary_hash", "core_version", "kernel",
]

#: One controller's worth of evidence, per node.
REQUIRED_NODE_LOGS = ["role_controller.log", "rpc.log", "process.log", "events.jsonl"]

REQUIRED_REPORTS = [
    "summary_per_epoca.md", "summary_per_epoca_emulation.md",
    "report_generale.md", "report_confronto.md",
    "report_asse_livello.md", "report_asse_tbt.md", "metrics_schema_report.md",
]

REQUIRED_PLOTS = [
    "01_traiettoria_pesi.png", "02_quota_per_epoca.png", "03_chi2_vs_tbt.png",
    "04_margine_prop518.png", "05_block_time.png", "06_eccesso_miner_pesante.png",
]


@dataclass
class TableState:
    name: str
    path: Path
    exists: bool
    rows: int
    columns: list = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if not self.exists:
            return "absent"
        if not self.columns:
            return "empty (no header)"
        if self.rows == 0:
            return "header only, no rows"
        return "%d rows" % self.rows


def _count_rows(path: Path) -> tuple:
    """Rows and columns of a CSV, without loading it all."""
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration:
                return 0, []
            return sum(1 for _ in reader), header
    except OSError:
        return 0, []


def _table_state(directory: Path, name: str) -> TableState:
    path = directory / ("%s.csv" % name)
    if not path.is_file():
        return TableState(name, path, False, 0, [])
    rows, header = _count_rows(path)
    return TableState(name, path, True, rows, header)


def inventory(run_root) -> dict:
    """Everything the run produced, keyed by what was expected of it."""
    run_root = Path(run_root)
    report = {"run_root": str(run_root), "exists": run_root.is_dir()}
    if not report["exists"]:
        return report

    # -- manifest ----------------------------------------------------------
    manifest_path = run_root / "manifest.json"
    manifest = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            report["manifest_error"] = str(exc)
    report["manifest_present"] = bool(manifest)
    report["manifest_missing_keys"] = [k for k in REQUIRED_MANIFEST_KEYS
                                       if k not in manifest]
    report["temporal_model"] = manifest.get("temporal_model", "")
    report["backend_used"] = manifest.get("network_backend_used",
                                          manifest.get("fabric_backend", ""))

    # -- tables ------------------------------------------------------------
    metrics_dir = run_root / "metrics"
    observations = run_root / "raw" / "observations"
    historical = [_table_state(metrics_dir, t.name) for t in HISTORICAL_TABLES]
    native_names = [t.name for t in ALL_TABLES if t not in HISTORICAL_TABLES]
    native = [_table_state(observations, name) for name in native_names]
    # A native table may live in either tree depending on the writer.
    for state in native:
        if not state.exists:
            alternative = _table_state(metrics_dir, state.name)
            if alternative.exists:
                state.exists, state.rows, state.columns, state.path = (
                    True, alternative.rows, alternative.columns, alternative.path)
    report["historical_tables"] = historical
    report["native_tables"] = native
    report["schema"] = check_run(metrics_dir)

    # -- per node ----------------------------------------------------------
    logs_dir = run_root / "logs"
    nodes = {}
    if logs_dir.is_dir():
        for node_dir in sorted(p for p in logs_dir.iterdir() if p.is_dir()):
            present, missing, lines = [], [], {}
            for name in REQUIRED_NODE_LOGS:
                path = node_dir / name
                if path.is_file() and path.stat().st_size > 0:
                    present.append(name)
                    lines[name] = sum(1 for _ in path.open(
                        encoding="utf-8", errors="replace"))
                else:
                    missing.append(name)
            controller = node_dir / "role_controller.log"
            text = (controller.read_text(encoding="utf-8", errors="replace")
                    if controller.is_file() else "")
            nodes[node_dir.name] = {
                "present": present, "missing": missing, "lines": lines,
                "setup": "setup complete" in text,
                "teardown": "teardown complete" in text,
                "heartbeats": text.count("heartbeat"),
            }
    report["nodes"] = nodes

    # -- raw, reports, plots ----------------------------------------------
    raw_rpc = run_root / "raw" / "rpc"
    report["raw_rpc_files"] = len(list(raw_rpc.glob("*"))) if raw_rpc.is_dir() else 0
    raw_events = run_root / "raw" / "events"
    report["raw_events_files"] = (len(list(raw_events.glob("*")))
                                  if raw_events.is_dir() else 0)
    runtime_dir = run_root / "runtime"
    report["runtime_artefacts"] = {
        name: (runtime_dir / name).is_file() for name in
        ("topology-realized.json", "node-status.json", "role-controllers.json",
         "explorer-state.json")
    }
    reports_dir = run_root / "reports"
    report["reports"] = {name: (reports_dir / name).is_file()
                         for name in REQUIRED_REPORTS}
    plots_dir = run_root / "plots"
    report["plots"] = {name: (plots_dir / name).is_file()
                       for name in REQUIRED_PLOTS}
    return report


def render(report: dict) -> str:
    """The inventory as Markdown, absences first."""
    if not report.get("exists"):
        return "# Diagnostic\n\nRun directory not found: %s\n" % report["run_root"]

    lines = ["# Diagnostic report", "",
             "Run: `%s`" % report["run_root"],
             "", "Generated by `experiments.metrics.diagnostics`. Row counts exclude",
             "the header, so `0 rows` means a table that exists and says nothing.", ""]

    lines += ["## Manifest", ""]
    if not report["manifest_present"]:
        lines += ["**manifest.json is absent or unreadable.**", ""]
    else:
        missing = report["manifest_missing_keys"]
        lines += ["- temporal model: `%s`" % (report["temporal_model"] or "NOT DECLARED"),
                  "- network backend used: `%s`" % (report["backend_used"] or "unknown"),
                  "- required keys missing: %s" % (
                      ", ".join("`%s`" % k for k in missing) if missing else "none"),
                  ""]

    lines += ["## Historical tables (the Shadow campaign schema)", "",
              "| table | state |", "|---|---|"]
    for state in report["historical_tables"]:
        lines.append("| `%s.csv` | %s |" % (state.name, state.verdict))
    lines.append("")

    lines += ["## Native tables (this harness)", "",
              "| table | state |", "|---|---|"]
    for state in report["native_tables"]:
        lines.append("| `%s.csv` | %s |" % (state.name, state.verdict))
    lines.append("")

    lines += ["## Per-node evidence", "",
              "| node | controller log | setup | teardown | heartbeats | missing files |",
              "|---|---|---|---|---|---|"]
    for node, state in report["nodes"].items():
        lines.append("| `%s` | %s lines | %s | %s | %d | %s |" % (
            node, state["lines"].get("role_controller.log", 0),
            "yes" if state["setup"] else "**no**",
            "yes" if state["teardown"] else "**no**",
            state["heartbeats"],
            ", ".join("`%s`" % m for m in state["missing"]) or "none"))
    lines.append("")

    lines += ["## Raw capture", "",
              "- `raw/rpc/`: %d files" % report["raw_rpc_files"],
              "- `raw/events/`: %d files" % report["raw_events_files"], ""]

    lines += ["## Runtime artefacts", "", "| file | present |", "|---|---|"]
    for name, present in report.get("runtime_artefacts", {}).items():
        lines.append("| `runtime/%s` | %s |" % (name, "yes" if present else "**no**"))
    lines.append("")

    lines += ["## Reports", "", "| report | present |", "|---|---|"]
    for name, present in report["reports"].items():
        lines.append("| `%s` | %s |" % (name, "yes" if present else "**no**"))
    lines.append("")

    lines += ["## Figures", "", "| figure | drawn |", "|---|---|"]
    for name, present in report["plots"].items():
        lines.append("| `%s` | %s |" % (name, "yes" if present else "**no**"))
    lines.append("")

    schema = report.get("schema") or {}
    lines += ["## Schema check", "",
              "- problems: %s" % (", ".join(schema.get("problems", [])) or "none"),
              "- absent: %s" % (", ".join(schema.get("absent", [])) or "none"),
              "- empty: %s" % (", ".join(schema.get("empty", [])) or "none"), ""]
    return "\n".join(lines)


def write(run_root, out_dir) -> Path:
    """Render the inventory of ``run_root`` into ``out_dir/report.md``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = inventory(run_root)
    path = out_dir / "report.md"
    path.write_text(render(report), encoding="utf-8")
    (out_dir / "inventory.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return path
