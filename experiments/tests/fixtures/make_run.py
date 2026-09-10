"""Build a synthetic run directory, without root and without MultiChain.

It is the fixture the golden and integration tests use, and it exists for one
reason: the metric extractors, the schema validators, the report writers and
the CSV column contract must be testable on a machine that cannot create a
network namespace. What it does NOT do is pretend to be an end-to-end test —
no block here was mined by anything. ``tests/integration/test_smoke_real.py``
is the one that needs real binaries, and it skips loudly when they are absent.

Everything is generated from a fixed seed, so two builds are byte-identical
and a golden test can compare against a stored expectation.
"""

from __future__ import annotations

import csv
import json
import random
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ...paths import CONFIG_ROOT, REPO_ROOT
from ...plan import build_plan
from ...runtime.collectors.process import PROCESS_COLUMNS
from ...runtime.collectors.rpc import BLOCK_SIGHTING_COLUMNS, OBSERVATION_COLUMNS
from ...topology import exporters

DEFAULT_DESCRIPTOR = CONFIG_ROOT / "experiments" / "smoke-3n.yaml"

#: Fixed epoch for the synthetic wall clock, so two builds agree to the second.
EPOCH = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)


def build_synthetic_run(destination: Path, *, descriptor: Path | None = None,
                        run_id: str = "run-fixture", ticks: int = 40,
                        interval_s: float = 2.0, seed: int = 20260910,
                        with_fork: bool = True) -> dict:
    """Write a complete run directory and return its plan and paths."""
    descriptor = Path(descriptor or DEFAULT_DESCRIPTOR)
    plan = build_plan(descriptor, seed_override=seed)
    root = Path(destination)
    if root.exists():
        shutil.rmtree(root)
    for relative in ("config", "runtime", "logs", "raw/metrics", "raw/observations",
                     "metrics", "plots", "reports"):
        (root / relative).mkdir(parents=True, exist_ok=True)

    shutil.copy2(descriptor, root / "config" / "experiment.yaml")
    shutil.copy2(plan.topology_path, root / "config" / "topology.yaml")
    shutil.copy2(plan.chain_params.path, root / "config" / "chain-params.dat")
    exporters.write_gml(plan.topology, root / "config" / "topology.gml")
    exporters.write_realized_json(
        plan.topology, root / "runtime" / "topology-realized.json",
        extra={"fabric": {"backend": "netns", "session": "fixture",
                          "nodes": [{"id": n.id, "namespace": "fixture-h-%s" % n.id,
                                     "ip": n.ip, "mgmt_ip": "", "location": n.location,
                                     "interfaces": ["lo", "eth0"]}
                                    for n in plan.enabled_nodes],
                          "links": []}},
    )

    rng = random.Random(seed)
    nodes = plan.enabled_nodes
    observations, sightings, processes = _series(
        plan, nodes, rng, ticks=ticks, interval_s=interval_s, with_fork=with_fork
    )
    _write(root / "raw" / "observations" / "node_observations.csv",
           OBSERVATION_COLUMNS, observations)
    _write(root / "raw" / "observations" / "block_sightings.csv",
           BLOCK_SIGHTING_COLUMNS, sightings)
    _write(root / "raw" / "observations" / "process_samples.csv",
           PROCESS_COLUMNS, processes)

    _chain_snapshot(root, plan, observations)
    _manifest(root, plan, run_id, ticks, interval_s)
    return {"run_root": root, "plan": plan, "run_id": run_id,
            "observations": len(observations), "sightings": len(sightings)}


def _series(plan, nodes, rng, *, ticks: int, interval_s: float, with_fork: bool):
    """A plausible height series with one transient fork in the middle."""
    observations, sightings, processes = [], [], []
    target = plan.target_block_time
    height = 0
    hashes: dict = {}
    for tick in range(1, ticks + 1):
        monotonic = round(tick * interval_s, 6)
        wallclock = (EPOCH + timedelta(seconds=monotonic)).isoformat(timespec="milliseconds")
        if tick * interval_s >= (height + 1) * target:
            height += 1
            hashes[height] = "%064x" % rng.getrandbits(256)
        # A transient disagreement: half the nodes hold a different hash for two
        # ticks. It has to be at the SAME height on every node, because that is
        # what a fork is - two hashes at one height. Injecting it at different
        # heights would only be propagation lag, and the extractor would be
        # right to ignore it, so the lag is suppressed for those ticks.
        forking = with_fork and 12 <= tick <= 13 and len(nodes) > 2
        alternative = "%064x" % rng.getrandbits(256) if forking else ""
        top_height = max(1, height)
        for index, node in enumerate(nodes):
            # Later nodes lag by a tick now and then; that is what makes
            # propagation and sync_lag non-degenerate. The sampling interval is
            # deliberately shorter than the target block time, or a lagging node
            # would skip a height entirely instead of seeing it late.
            lag = 0 if forking else (1 if (tick + index) % 3 == 0 and top_height > 1 else 0)
            node_height = max(0, top_height - lag)
            block_hash = hashes.get(node_height, "")
            if forking and index % 2 == 1:
                block_hash = alternative
            observations.append({
                "run_id": plan.name, "scenario": plan.scenario, "seed": plan.seed,
                "node_id": node.id, "role": node.role, "organization": node.organization,
                "geographic_scope": node.scope, "region": node.region,
                "country": node.country, "continent": node.continent,
                "timestamp_wallclock": wallclock, "timestamp_monotonic": monotonic,
                "sample_index": tick,
                "block_height": node_height, "block_hash": block_hash,
                "previous_block_hash": hashes.get(node_height - 1, ""),
                "block_time": int(EPOCH.timestamp()) + node_height * target,
                "peer_count": max(0, len(nodes) - 1 - (1 if tick % 11 == 0 else 0)),
                "peer_connectivity": 1,
                "transaction_count": (node_height % 4),
                "confirmed_transaction_count": "",
                "mempool_size": rng.randint(0, 3),
                "sync_lag": top_height - node_height,
                "rpc_errors": 0, "p2p_errors": "", "reachable": 1,
            })
            if block_hash:
                key = (node.id, block_hash)
                if key not in _SEEN:
                    _SEEN.add(key)
                    sightings.append({
                        "run_id": plan.name, "scenario": plan.scenario,
                        "node_id": node.id, "block_height": node_height,
                        "block_hash": block_hash,
                        "first_seen_wallclock": wallclock,
                        "first_seen_monotonic": monotonic, "sample_index": tick,
                    })
            processes.append({
                "run_id": plan.name, "node_id": node.id, "process_kind": "daemon",
                "process_label": "multichaind", "pid": 10000 + index,
                "timestamp_wallclock": wallclock, "timestamp_monotonic": monotonic,
                "sample_index": tick, "alive": 1,
                "cpu_seconds_total": round(tick * 0.35 + index * 0.1, 3),
                "cpu_percent": round(6.0 + rng.random() * 4.0, 2),
                "memory_bytes": 180 * 1024 * 1024 + index * 1024 * 1024,
                "memory_peak_bytes": 200 * 1024 * 1024, "threads": 12,
                "disk_read_bytes": "", "disk_write_bytes": "", "process_restarts": 0,
            })
    _SEEN.clear()
    return observations, sightings, processes


#: Module-level so ``_series`` can stay a plain function; cleared on every build.
_SEEN: set = set()


def _write(path: Path, columns: list, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _chain_snapshot(root: Path, plan, observations: list) -> None:
    """The admin's final snapshot, in the shape the role script writes it."""
    metrics = root / "raw" / "metrics"
    heights = sorted({int(row["block_height"]) for row in observations
                      if row["block_height"] not in ("", None) and int(row["block_height"]) > 0})
    miners = plan.miners or plan.enabled_nodes[:1]
    blocks = []
    for height in heights:
        row = next(r for r in observations
                   if str(r["block_height"]) == str(height) and r["block_hash"])
        blocks.append({
            "height": height, "hash": row["block_hash"],
            "miner": "1FIXTURE%s" % miners[height % len(miners)].id,
            "time": int(row["block_time"]), "txcount": int(row["transaction_count"]),
            "confirmations": len(heights) - height + 1,
        })
    (metrics / "blocks.json").write_text(
        json.dumps({"result": blocks, "error": None, "id": "fixture"}), encoding="utf-8")
    (metrics / "final_height.txt").write_text("%d\n" % (heights[-1] if heights else 0),
                                              encoding="utf-8")
    for name, payload in (
        ("weights.json", []), ("esg.json", []), ("membership.json", []),
        ("malus.json", []),
    ):
        (metrics / name).write_text(
            json.dumps({"result": payload, "error": None, "id": "fixture"}), encoding="utf-8")
    (metrics / "verify.json").write_text(
        json.dumps({"result": {"epoch": 1, "verified": True, "records": 0, "invalid": 0,
                               "entries": []}, "error": None, "id": "fixture"}),
        encoding="utf-8")
    (metrics / "admin_getinfo.json").write_text(
        json.dumps({"result": {"chainname": plan.multichain.chain,
                               "setupblocks": plan.setup_first_blocks,
                               "blocks": heights[-1] if heights else 0,
                               "protocolversion": 20014},
                    "error": None, "id": "fixture"}), encoding="utf-8")
    (metrics / "permissions_mine.json").write_text(
        json.dumps({"result": [], "error": None, "id": "fixture"}), encoding="utf-8")
    header = "host,height,besthash,hash_a_1,peers,balance\n"
    rows = "".join(
        "%s,%d,%s,%s,%d,%s\n" % (n.id, heights[-1] if heights else 0,
                                 "f" * 64, "f" * 64, max(0, len(plan.enabled_nodes) - 1), "100.0")
        for n in plan.enabled_nodes)
    (metrics / "node_state.csv").write_text(header + rows, encoding="utf-8")


def _manifest(root: Path, plan, run_id: str, ticks: int, interval_s: float) -> None:
    summary = plan.summary()
    document = {
        "schema_version": 1, "run_id": run_id, "status": "completed",
        "scenario": plan.scenario, "experiment": plan.name,
        "description": plan.description, "topology": plan.topology.name,
        "topology_file": str(plan.topology_path),
        "chain_params_file": str(plan.chain_params.path),
        "descriptor": str(root / "config" / "experiment.yaml"),
        "seed": plan.seed, "mode": plan.mode, "fabric_backend": "netns",
        "git_commit": "0" * 40, "git_commit_short": "0000000",
        "branch": "fixture", "git_dirty": False,
        "multichain_binary": "(fixture: no binary was run)",
        "multichain_version": "(fixture: synthetic data, nothing was mined)",
        "chain": plan.multichain.chain,
        "os": "fixture", "kernel": "fixture", "python": "fixture",
        "core_version": "", "hostname": "fixture", "cpu_count": 1,
        "started_at": EPOCH.isoformat(timespec="seconds"),
        "ended_at": (EPOCH + timedelta(seconds=ticks * interval_s)).isoformat(timespec="seconds"),
        "duration_wallclock_s": ticks * interval_s,
        "node_count": summary["node_count"], "miner_count": summary["miner_count"],
        "company_count": summary["company_count"], "admin_count": summary["admin_count"],
        "target_block_time_s": summary["target_block_time_s"],
        "epoch_length_blocks": summary["epoch_length_blocks"],
        "dump_function": summary["dump_function"],
        "setup_first_blocks": summary["setup_first_blocks"],
        "measure_blocks": summary["measure_blocks"],
        "planned_duration_s": summary["duration_s"],
        "schedule": plan.schedule.as_dict(),
        "nodes": [n.as_dict() for n in plan.nodes],
        "phases": [{"name": "fixture", "status": "ok", "at": EPOCH.isoformat()}],
        "synthetic": True,
        "synthetic_note": (
            "Generated by experiments.tests.fixtures.make_run. No MultiChain process "
            "produced these numbers; they exist to exercise the extractors, the schema "
            "validators and the report writers without root or binaries."
        ),
        "errors": [],
    }
    (root / "manifest.json").write_text(json.dumps(document, indent=2) + "\n",
                                        encoding="utf-8")


def _repo_relative(path: Path) -> str:
    try:
        return str(Path(path).relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
