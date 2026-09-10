"""The CLI surface and its exit codes, which are part of the interface."""

from __future__ import annotations

import json

import pytest

from experiments.cli import main
from experiments.paths import CONFIG_ROOT


def test_help_lists_every_command(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
    out = capsys.readouterr().out
    for command in ("env", "validate", "topology", "network", "multichain",
                    "experiment", "metrics", "analysis", "report", "results"):
        assert command in out


def test_validate_returns_zero_on_a_good_descriptor(capsys):
    rc = main(["validate", "--experiment",
               str(CONFIG_ROOT / "experiments" / "regional.yaml")])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["node_count"] == 20
    assert payload["errors"] == []


def test_validate_returns_one_on_a_bad_descriptor(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: Bad Name\nnodes: []\n", encoding="utf-8")
    assert main(["validate", "--experiment", str(bad)]) == 1


def test_validate_on_a_missing_file_returns_one(tmp_path):
    assert main(["validate", "--experiment", str(tmp_path / "absent.yaml")]) == 1


def test_topology_validate_prints_the_matrix(capsys):
    rc = main(["topology", "validate", "--topology",
               str(CONFIG_ROOT / "topologies" / "smoke-3n.yaml"), "--matrix"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "worst end-to-end RTT" in out
    assert "firenze" in out


def test_topology_generate_writes_the_file(tmp_path, capsys):
    output = tmp_path / "out.gml"
    rc = main(["topology", "generate", "--topology",
               str(CONFIG_ROOT / "topologies" / "regional.yaml"),
               "--format", "gml", "--output", str(output)])
    assert rc == 0
    assert output.is_file()
    assert output.read_text(encoding="utf-8").startswith("graph [")
    assert str(output) in capsys.readouterr().out


def test_topology_profiles_lists_every_profile(capsys):
    assert main(["topology", "profiles"]) == 0
    payload = json.loads(capsys.readouterr().out)
    names = {row["name"] for row in payload}
    assert {"lan", "degraded", "partitioned"} <= names
    for row in payload:
        assert row["source"], row["name"]


def test_env_check_reports_without_an_experiment(capsys):
    rc = main(["env", "check"])
    payload = json.loads(capsys.readouterr().out)
    assert "tools_mandatory" in payload
    assert "python_modules" in payload
    assert rc in (0, 2)


def test_metrics_schema_renders_markdown(capsys):
    assert main(["metrics", "schema"]) == 0
    assert "# Metric schema" in capsys.readouterr().out


def test_metrics_schema_renders_json(capsys):
    assert main(["metrics", "schema", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tables"]
    assert payload["status_counts"]["unavailable"] > 0


def test_dry_run_touches_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("EXPERIMENT_ROOT", str(tmp_path / "results"))
    rc = main(["experiment", "dry-run", "--experiment",
               str(CONFIG_ROOT / "experiments" / "regional.yaml"), "--seed", "12345"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["plan"]["node_count"] == 20
    assert payload["fabric"]["commands_that_would_run"] > 100
    # Nothing was created on disk.
    assert not (tmp_path / "results").exists() or not any((tmp_path / "results").iterdir())


def test_dry_run_seeds_are_reproducible(capsys):
    seeds = []
    for _ in range(2):
        main(["experiment", "dry-run", "--experiment",
              str(CONFIG_ROOT / "experiments" / "regional.yaml"), "--seed", "777"])
        seeds.append(json.loads(capsys.readouterr().out)["seeds"])
    assert seeds[0] == seeds[1]


def test_analysis_on_an_unknown_run_returns_one(monkeypatch, tmp_path):
    monkeypatch.setenv("EXPERIMENT_ROOT", str(tmp_path))
    assert main(["analysis", "run", "--run-id", "no-such-run"]) == 1


def test_results_list_is_empty_on_a_fresh_root(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXPERIMENT_ROOT", str(tmp_path / "empty"))
    assert main(["results", "list"]) == 0
    assert json.loads(capsys.readouterr().out) == []
