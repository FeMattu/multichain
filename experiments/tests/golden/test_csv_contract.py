"""The CSV column contract: what downstream readers are allowed to rely on.

Historical column names are frozen. New columns may be appended. Nothing may
be renamed or reordered — a reader that indexes by position must keep working
across a refactor, and there is no way to notice that it stopped except by
asserting it here.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from experiments.metrics import catalogue
from experiments.runtime.collectors.process import PROCESS_COLUMNS
from experiments.runtime.collectors.rpc import BLOCK_SIGHTING_COLUMNS, OBSERVATION_COLUMNS
from experiments.metrics.extractors import (
    FORK_COLUMNS,
    NETEM_COLUMNS,
    PROPAGATION_COLUMNS,
)
from experiments.topology.exporters import EDGE_COLUMNS

EXPECTED = Path(__file__).parent / "expected_columns.json"

CONTRACTS = {
    "node_observations": OBSERVATION_COLUMNS,
    "block_sightings": BLOCK_SIGHTING_COLUMNS,
    "process_samples": PROCESS_COLUMNS,
    "netem_conditions": NETEM_COLUMNS,
    "block_propagation": PROPAGATION_COLUMNS,
    "fork_events": FORK_COLUMNS,
    "topology_edges": EDGE_COLUMNS,
}


def test_columns_match_the_recorded_contract():
    """Fails on any rename, reorder or removal. Additions are allowed."""
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    problems = []
    for name, actual in sorted(CONTRACTS.items()):
        recorded = expected.get(name)
        if recorded is None:
            problems.append("%s: no recorded contract; add it to %s" % (name, EXPECTED.name))
            continue
        if actual[:len(recorded)] != recorded:
            problems.append(
                "%s: the recorded prefix changed.\n  was: %s\n  now: %s"
                % (name, recorded, actual[:len(recorded)]))
    assert not problems, "\n".join(problems)


def test_the_required_new_metrics_are_all_present():
    """Every column the brief asks for is produced somewhere."""
    required = {
        "node_id", "role", "organization", "geographic_scope", "region", "country",
        "continent", "run_id", "scenario", "seed", "timestamp_wallclock",
        "timestamp_monotonic", "block_height", "block_hash", "previous_block_hash",
        "block_time", "propagation_time", "peer_count", "peer_connectivity",
        "transaction_count", "confirmed_transaction_count", "fork_detected",
        "fork_depth", "sync_lag", "cpu_percent", "memory_bytes", "disk_read_bytes",
        "disk_write_bytes", "process_restarts", "rpc_errors", "p2p_errors",
        "netem_delay_ms", "netem_jitter_ms", "netem_loss_percent",
        "netem_bandwidth_mbps",
    }
    produced = set()
    for columns in CONTRACTS.values():
        produced |= set(columns)
    produced |= {"first_seen_time", "last_seen_time"}   # named below
    missing = required - produced
    # first_seen_/last_seen_ are carried under their monotonic and wallclock
    # names, which say which clock they use; the brief's generic names would not.
    aliases = {"first_seen_time": "first_seen_monotonic",
               "last_seen_time": "last_seen_monotonic"}
    for generic, actual in aliases.items():
        assert actual in produced, generic
        missing.discard(generic)
    assert not missing, "not produced anywhere: %s" % sorted(missing)


def test_every_catalogued_table_declares_columns_that_exist_somewhere():
    for table in catalogue.NATIVE_TABLES:
        contract = CONTRACTS.get(table.name)
        if contract is None:
            continue
        for column in table.columns:
            if column.status == catalogue.UNAVAILABLE:
                continue
            assert column.name in contract, "%s.%s" % (table.name, column.name)


def test_synthetic_run_passes_schema_validation(synthetic_run):
    from experiments.metrics.extractors import extract_all

    produced = extract_all(synthetic_run["run_root"], synthetic_run["plan"])
    assert produced["validation"]["problems"] == []


def test_historical_sheet_headers_are_unchanged():
    """The archived campaign sheets define the frozen historical headers."""
    archive = (Path(__file__).parents[2] / "analysis" / "historical" /
               "shadow-campaign" / "sheets")
    if not archive.is_dir():
        pytest.skip("the historical sheets are not present in this checkout")
    expected = json.loads(EXPECTED.read_text(encoding="utf-8")).get("historical_sheets", {})
    for name, header in sorted(expected.items()):
        path = archive / ("%s.csv" % name)
        assert path.is_file(), name
        with path.open(newline="", encoding="utf-8") as handle:
            actual = next(csv.reader(handle))
        assert actual == header, name
