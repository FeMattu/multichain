"""The whole analysis path over a synthetic run: no root, no binaries.

This is a pipeline test, not an end-to-end test, and the fixture's own
manifest says so. What it proves is that extractors, schema validation,
the migrated three-phase pipeline and the report writers all work together
on a well-formed run directory.
"""

from __future__ import annotations

import csv
import json

from experiments.analysis.reporting import REPORT_NAMES, generate_reports
from experiments.metrics.extractors import extract_all


def _rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_extractors_produce_every_table(synthetic_run):
    root, plan = synthetic_run["run_root"], synthetic_run["plan"]
    produced = extract_all(root, plan)
    for name in ("node_observations.csv", "block_sightings.csv", "process_samples.csv",
                 "netem_conditions.csv", "block_propagation.csv", "fork_events.csv"):
        assert (root / "metrics" / name).is_file(), name
    assert produced["validation"]["problems"] == []


def test_raw_observations_survive_extraction(synthetic_run):
    """Extraction copies; a bug in an extractor must be fixable and re-runnable."""
    root, plan = synthetic_run["run_root"], synthetic_run["plan"]
    before = (root / "raw" / "observations" / "node_observations.csv").read_bytes()
    extract_all(root, plan)
    after = (root / "raw" / "observations" / "node_observations.csv").read_bytes()
    assert before == after


def test_extraction_is_idempotent(synthetic_run):
    root, plan = synthetic_run["run_root"], synthetic_run["plan"]
    extract_all(root, plan)
    first = (root / "metrics" / "block_propagation.csv").read_text(encoding="utf-8")
    extract_all(root, plan)
    second = (root / "metrics" / "block_propagation.csv").read_text(encoding="utf-8")
    assert first == second


def test_propagation_is_non_degenerate(synthetic_run):
    """A run where every node sees every block at the same tick would say
    nothing; the fixture is built so it does not."""
    root, plan = synthetic_run["run_root"], synthetic_run["plan"]
    extract_all(root, plan)
    rows = _rows(root / "metrics" / "block_propagation.csv")
    assert rows
    values = [float(r["propagation_time"]) for r in rows]
    assert max(values) > 0, "no block was seen at different times by different nodes"


def test_the_injected_fork_is_detected(synthetic_run):
    """The fixture injects a two-tick disagreement; the extractor must find it."""
    root, plan = synthetic_run["run_root"], synthetic_run["plan"]
    extract_all(root, plan)
    rows = _rows(root / "metrics" / "fork_events.csv")
    detected = [r for r in rows if r["fork_detected"] == "1"]
    assert len(detected) == 2, "expected the two injected fork ticks"
    assert max(int(r["fork_depth"]) for r in detected) == 2
    assert all(int(r["distinct_hashes"]) > 1 for r in detected)


def test_netem_conditions_carry_both_directions(synthetic_run):
    root, plan = synthetic_run["run_root"], synthetic_run["plan"]
    extract_all(root, plan)
    rows = _rows(root / "metrics" / "netem_conditions.csv")
    assert rows
    assert {r["direction"] for r in rows} == {"forward", "reverse"}


def test_the_historical_pipeline_runs_over_a_native_run(synthetic_run):
    root, plan = synthetic_run["run_root"], synthetic_run["plan"]
    produced = extract_all(root, plan)
    assert produced["historical"].get("pipeline_exit_code") == 0
    # The adapter's compatibility inputs live inside the run, not globally.
    assert (root / "analysis-compat" / "levels").is_dir()
    assert (root / "analysis-compat" / "topology.gml").is_file()
    phase1 = list((root / "analysis").rglob("phase1/blocks.csv"))
    assert phase1, "phase 1 produced no blocks table"
    assert _rows(phase1[0]), "the blocks table is empty"


def test_reports_are_written_with_the_historical_names(synthetic_run):
    root, plan = synthetic_run["run_root"], synthetic_run["plan"]
    extract_all(root, plan)
    produced = generate_reports(root, plan, with_plots=False)
    written = {p.split("/")[-1] for p in produced["reports"]}
    assert set(REPORT_NAMES) <= written


def test_every_report_declares_its_provenance(synthetic_run):
    root, plan = synthetic_run["run_root"], synthetic_run["plan"]
    extract_all(root, plan)
    generate_reports(root, plan, with_plots=False)
    for name in ("report_generale.md", "report_confronto.md",
                 "report_asse_livello.md", "report_asse_tbt.md"):
        text = (root / "reports" / name).read_text(encoding="utf-8")
        assert "Emulation, not simulation" in text, name
        assert "not directly comparable" in text, name


def test_reports_state_the_mandatory_facts(synthetic_run):
    root, plan = synthetic_run["run_root"], synthetic_run["plan"]
    extract_all(root, plan)
    generate_reports(root, plan, with_plots=False)
    text = (root / "reports" / "report_generale.md").read_text(encoding="utf-8")
    for required in ("seed", "target-block-time", "dump function",
                     "setup-first-blocks", "git commit"):
        assert required in text, required


def test_plots_are_produced_when_matplotlib_is_present(synthetic_run):
    import importlib.util

    if importlib.util.find_spec("matplotlib") is None:
        import pytest

        pytest.skip("matplotlib is not installed")
    root, plan = synthetic_run["run_root"], synthetic_run["plan"]
    extract_all(root, plan)
    produced = generate_reports(root, plan, with_plots=True)
    assert produced["plots"]
    for path in produced["plots"]:
        assert path.endswith(".png")


def test_the_fixture_declares_that_it_is_synthetic(synthetic_run):
    """A fixture that could be mistaken for a real run would be worse than none."""
    manifest = json.loads(
        (synthetic_run["run_root"] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["synthetic"] is True
    assert "No MultiChain process" in manifest["synthetic_note"]
