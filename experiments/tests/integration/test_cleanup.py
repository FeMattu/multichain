"""Cleanup behaviour that can be exercised without privileges."""

from __future__ import annotations

import json

import pytest

from experiments.paths import CONFIG_ROOT
from experiments.plan import build_plan
from experiments.runtime.manifest import Manifest
from experiments.runtime.multichain.lifecycle import ManagedProcess, ProcessRegistry
from experiments.runtime.session import Session
from experiments.runtime.shell import Runner


def _session(tmp_path):
    plan = build_plan(CONFIG_ROOT / "experiments" / "smoke-3n.yaml")
    run_root = tmp_path / "run"
    run_root.mkdir(parents=True, exist_ok=True)
    return Session(plan=plan, run_id="run-x", run_root=run_root,
                   runner=Runner(dry_run=True), roles_dir=tmp_path)


def test_cleanup_never_raises_even_with_nothing_built(tmp_path):
    session = _session(tmp_path)
    summary = session.cleanup(status="failed", error="boom")
    assert summary["status"] == "failed"


def test_cleanup_writes_the_manifest_and_keeps_the_results(tmp_path):
    session = _session(tmp_path)
    session.prepare_directories()
    session.snapshot_config()
    session.manifest = Manifest.create("run-x", session.run_root, session.plan,
                                       backend="netns", binaries={})
    session.cleanup(status="interrupted", error="signal 2")
    manifest = json.loads((session.run_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "interrupted"
    assert any("signal 2" in e["message"] for e in manifest["errors"])
    assert (session.run_root / "config" / "experiment.yaml").is_file()
    assert (session.run_root / "logs").is_dir()


def test_context_manager_cleans_up_on_an_exception(tmp_path):
    session = _session(tmp_path)
    session.prepare_directories()
    session.manifest = Manifest.create("run-x", session.run_root, session.plan,
                                       backend="netns", binaries={})
    with pytest.raises(ValueError):
        with session:
            raise ValueError("boom")
    manifest = json.loads((session.run_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"


def test_processes_are_registered_before_they_start(tmp_path):
    """A process the registry never saw is a process cleanup cannot stop."""
    registry = ProcessRegistry()
    process = ManagedProcess(node_id="m1", kind="daemon", label="multichaind",
                             argv=["true"], handle=None,
                             log_path=tmp_path / "x.log")
    registry.add(process)
    assert registry.daemons() == [process]
    assert not process.alive()
    assert registry.as_dict()[0]["node_id"] == "m1"


def test_manifest_survives_being_written_repeatedly(tmp_path):
    session = _session(tmp_path)
    session.prepare_directories()
    manifest = Manifest.create("run-x", session.run_root, session.plan,
                               backend="netns", binaries={})
    for index in range(20):
        manifest.phase("phase-%d" % index, "ok")
    reloaded = Manifest.load(session.run_root)
    assert len(reloaded.data["phases"]) == 20
    # The temporary file must not be left behind.
    assert not (session.run_root / "manifest.json.tmp").exists()


def test_verify_artefacts_reports_incomplete_data(tmp_path):
    from experiments.exit_codes import IncompleteData

    session = _session(tmp_path)
    session.prepare_directories()
    with pytest.raises(IncompleteData) as caught:
        session.verify_artefacts()
    assert "blocks.json" in str(caught.value)


def test_stray_qdisc_pattern_matches_the_names_the_fabric_creates():
    from experiments.runtime.netem.clear import STRAY_PATTERN

    for name in ("pe1a", "pe42b", "mgp3"):
        assert STRAY_PATTERN.match(name), name
    for name in ("eth0", "lo", "docker0", "l1"):
        assert not STRAY_PATTERN.match(name), name
