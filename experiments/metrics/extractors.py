"""Turning a finished run's raw artefacts into the catalogued metric tables.

Three sources feed in and none of them is re-derived:

* ``raw/observations/`` — the sampler's time series, normalised into
  ``metrics/`` and extended with the quantities that need the whole series
  (propagation time, fork depth);
* ``runtime/topology-realized.json`` — the impairment actually installed,
  which becomes ``netem_conditions.csv``;
* the three-phase pipeline — the historical tables, computed by the migrated
  code so their definitions cannot drift from the archived campaign's.

Everything is written under ``metrics/`` with a header even when empty: an
empty table with the right header is a fact ("nothing happened"), an absent
file is an ambiguity ("nothing happened, or the step never ran").
"""

from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict
from pathlib import Path

LOG = logging.getLogger("experiments.metrics.extractors")

NETEM_COLUMNS = [
    "run_id", "scenario", "link_source", "link_target", "kind", "profile",
    "direction", "enabled", "distance_km", "netem_delay_ms", "netem_jitter_ms",
    "netem_distribution", "netem_loss_percent", "netem_bandwidth_mbps",
    "netem_queue_limit_packets", "partition", "profile_source",
]

PROPAGATION_COLUMNS = [
    "run_id", "scenario", "block_height", "block_hash", "nodes_seen",
    "first_seen_monotonic", "last_seen_monotonic", "propagation_time",
    "first_seen_node", "last_seen_node",
]

FORK_COLUMNS = [
    "run_id", "scenario", "sample_index", "timestamp_wallclock", "reference_height",
    "distinct_hashes", "fork_detected", "fork_depth", "nodes_reporting", "hashes",
]


def _write_csv(path: Path, columns: list, rows: list) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _read_csv(path: Path) -> list:
    path = Path(path)
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def extract_netem(run_root: Path, plan) -> int:
    """``netem_conditions.csv`` from what the fabric actually installed."""
    realized_path = Path(run_root) / "runtime" / "topology-realized.json"
    rows = []
    if realized_path.is_file():
        document = json.loads(realized_path.read_text(encoding="utf-8"))
        for link in document.get("links", []):
            for direction in ("forward", "reverse"):
                impairment = link.get(direction) or {}
                delay = impairment.get("delay") or {}
                loss = impairment.get("loss") or {}
                bandwidth = impairment.get("bandwidth") or {}
                queue = impairment.get("queue") or {}
                rows.append({
                    "run_id": plan.name, "scenario": plan.scenario,
                    "link_source": link.get("source", ""), "link_target": link.get("target", ""),
                    "kind": link.get("kind", ""), "profile": link.get("profile", ""),
                    "direction": direction, "enabled": int(bool(link.get("enabled", True))),
                    "distance_km": link.get("distance_km", ""),
                    "netem_delay_ms": delay.get("mean_ms", ""),
                    "netem_jitter_ms": delay.get("jitter_ms", ""),
                    "netem_distribution": delay.get("distribution", ""),
                    "netem_loss_percent": loss.get("percent", ""),
                    "netem_bandwidth_mbps": bandwidth.get("mbps", ""),
                    "netem_queue_limit_packets": queue.get("limit_packets", ""),
                    "partition": int(bool(impairment.get("partition", False))),
                    "profile_source": document.get("source", ""),
                })
    else:
        LOG.warning("no topology-realized.json in %s: netem_conditions will be empty",
                    run_root)
    return _write_csv(Path(run_root) / "metrics" / "netem_conditions.csv",
                      NETEM_COLUMNS, rows)


def extract_propagation(run_root: Path, plan) -> int:
    """Per-block propagation, from the sightings the sampler recorded.

    The value is bounded below by the sampling interval, so it is an upper
    bound on the true propagation time rather than a wire measurement. The
    catalogue says so, and so does the report.
    """
    sightings = _read_csv(Path(run_root) / "raw" / "observations" / "block_sightings.csv")
    by_hash: dict = defaultdict(list)
    for row in sightings:
        try:
            monotonic = float(row["first_seen_monotonic"])
        except (KeyError, TypeError, ValueError):
            continue
        by_hash[(row.get("block_height", ""), row.get("block_hash", ""))].append(
            (monotonic, row.get("node_id", ""))
        )
    rows = []
    for (height, block_hash), seen in sorted(by_hash.items(), key=_height_key):
        seen.sort()
        first_time, first_node = seen[0]
        last_time, last_node = seen[-1]
        rows.append({
            "run_id": plan.name, "scenario": plan.scenario,
            "block_height": height, "block_hash": block_hash,
            "nodes_seen": len(seen),
            "first_seen_monotonic": round(first_time, 6),
            "last_seen_monotonic": round(last_time, 6),
            "propagation_time": round(last_time - first_time, 6),
            "first_seen_node": first_node, "last_seen_node": last_node,
        })
    return _write_csv(Path(run_root) / "metrics" / "block_propagation.csv",
                      PROPAGATION_COLUMNS, rows)


def _height_key(item):
    (height, block_hash), _ = item
    try:
        return (0, int(height), block_hash)
    except (TypeError, ValueError):
        return (1, 0, str(block_hash))


def extract_forks(run_root: Path, plan) -> int:
    """Divergence over time, from the per-tick observations.

    A tick where two nodes report different hashes at the same height is a
    fork in progress. Depth is counted in consecutive ticks rather than in
    blocks, because between two samples the chain may have moved by several
    heights and claiming a block count would overstate what was observed.
    """
    observations = _read_csv(Path(run_root) / "raw" / "observations" / "node_observations.csv")
    by_tick: dict = defaultdict(list)
    for row in observations:
        if row.get("reachable") != "1" or not row.get("block_hash"):
            continue
        by_tick[row.get("sample_index", "")].append(row)

    rows = []
    depth = 0
    for index in sorted(by_tick, key=lambda v: int(v) if str(v).isdigit() else 0):
        sample = by_tick[index]
        heights = [int(r["block_height"]) for r in sample if str(r.get("block_height", "")).isdigit()]
        if not heights:
            continue
        reference = min(heights)
        at_reference = {r["node_id"]: r["block_hash"] for r in sample
                        if str(r.get("block_height", "")).isdigit()
                        and int(r["block_height"]) == reference}
        distinct = sorted(set(at_reference.values()))
        detected = len(distinct) > 1
        depth = depth + 1 if detected else 0
        rows.append({
            "run_id": plan.name, "scenario": plan.scenario, "sample_index": index,
            "timestamp_wallclock": sample[0].get("timestamp_wallclock", ""),
            "reference_height": reference, "distinct_hashes": len(distinct),
            "fork_detected": int(detected), "fork_depth": depth,
            "nodes_reporting": len(at_reference),
            "hashes": " ".join(h[:12] for h in distinct),
        })
    return _write_csv(Path(run_root) / "metrics" / "fork_events.csv", FORK_COLUMNS, rows)


def copy_observations(run_root: Path) -> dict:
    """Normalise the sampler's raw series into ``metrics/``.

    A copy rather than a move: ``raw/`` stays exactly as the run produced it,
    so a bug in an extractor can be fixed and re-run without having destroyed
    its own input.
    """
    import shutil

    produced = {}
    raw = Path(run_root) / "raw" / "observations"
    target = Path(run_root) / "metrics"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("node_observations.csv", "block_sightings.csv", "process_samples.csv"):
        source = raw / name
        if source.is_file():
            shutil.copy2(source, target / name)
            produced[name] = sum(1 for _ in source.open(encoding="utf-8")) - 1
        else:
            LOG.warning("no %s: the sampler produced nothing for this run", name)
    return produced


def run_historical_pipeline(run_root: Path, plan) -> dict:
    """Produce the historical tables through the migrated pipeline.

    The definitions come from the migrated code rather than being restated
    here, which is the whole point: an archived campaign and a new run must be
    computed by the same lines.
    """
    from ..analysis.compatibility.run_adapter import write_compat_inputs
    from ..analysis.pipeline import run_pipeline

    write_compat_inputs(run_root, plan)
    out = Path(run_root) / "analysis"
    rc = run_pipeline.main([
        "--phase", "all", "--root", str(Path(run_root).parent), "--out", str(out),
        "--only", Path(run_root).name, "--no-campaign",
    ])
    return {"pipeline_exit_code": rc, "output": str(out)}


def extract_all(run_root: Path, plan) -> dict:
    """Every extractor, in order. Returns what was produced."""
    run_root = Path(run_root)
    produced: dict = {"tables": {}}
    produced["tables"].update(copy_observations(run_root))
    produced["tables"]["netem_conditions.csv"] = extract_netem(run_root, plan)
    produced["tables"]["block_propagation.csv"] = extract_propagation(run_root, plan)
    produced["tables"]["fork_events.csv"] = extract_forks(run_root, plan)
    try:
        produced["historical"] = run_historical_pipeline(run_root, plan)
    except Exception as exc:  # noqa: BLE001 - a run with no snapshot still has observations
        LOG.error("the historical pipeline could not run: %s", exc)
        produced["historical"] = {"error": str(exc)}

    from .schema_report import write as write_schema

    report = write_schema(run_root / "reports" / "metrics_schema_report.md",
                          metrics_dir=run_root / "metrics")
    produced["schema_report"] = str(report)

    from .validators import check_run

    produced["validation"] = check_run(run_root / "metrics")
    for problem in produced["validation"]["problems"]:
        LOG.warning("schema: %s", problem)
    return produced
