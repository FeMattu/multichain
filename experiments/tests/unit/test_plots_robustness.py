"""Figures over partial data: skipped with a reason, never silently absent.

Two regressions are guarded here.

The first is the one that lost three figures. `reporting._plots` drew the
emulation's own three (height per node, propagation, link delays) until
commit f527222 pointed `generate_reports` at the new `plots` module and left
`_plots` in the file, uncalled. Nothing referenced it and nothing tested it,
so from then on those figures were simply never drawn - and because a figure
that is not attempted is not reported as skipped either, no run said so.
`test_every_catalogued_figure_has_a_drawer` is what makes that impossible to
repeat.

The second is the reporting of failure. A drawer that raises and a table that
is legitimately empty both used to land in `skipped`, at INFO level, which is
below the default threshold: a crash in a figure looked exactly like a run
with nothing to plot.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from experiments.analysis import plots

pytest.importorskip("matplotlib", reason="the figures need matplotlib")


class _Topology:
    name = "regional-20n"


class _Plan:
    scenario = "regional"
    target_block_time = 10
    topology = _Topology()


@pytest.fixture
def plan() -> _Plan:
    return _Plan()


def _run(tmp_path: Path, **tables) -> Path:
    """A run directory holding exactly the tables named, and nothing else."""
    metrics = tmp_path / "metrics"
    metrics.mkdir(parents=True, exist_ok=True)
    for name, text in tables.items():
        (metrics / ("%s.csv" % name)).write_text(text, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# the catalogue and the drawers must not drift
# ---------------------------------------------------------------------------

def test_every_catalogued_figure_has_a_drawer():
    """The check that would have caught the three lost figures."""
    drawn = {name for name, _ in plots.DRAWERS}
    assert drawn == set(plots.FIGURES), (
        "FIGURES and DRAWERS disagree; a figure named but never drawn is "
        "absent from every run with no explanation: %s"
        % (drawn.symmetric_difference(set(plots.FIGURES)),))


def test_every_drawer_exists_and_is_callable():
    for name, drawer_name in plots.DRAWERS:
        assert drawer_name in globals() or hasattr(plots, drawer_name), (
            "%s names a drawer %r that does not exist" % (name, drawer_name))
        assert callable(getattr(plots, drawer_name))


def test_the_emulation_figures_are_still_catalogued():
    """They are the only ones a run without a final snapshot can produce."""
    assert set(plots.EMULATION_FIGURES) == {
        "10_altezza_per_nodo.png",
        "11_propagazione_blocchi.png",
        "12_ritardi_link.png",
    }


def test_the_two_families_do_not_collide():
    historical = set(plots.HISTORICAL_FIGURES)
    emulation = set(plots.EMULATION_FIGURES)
    assert not historical & emulation
    prefixes = {name.split("_")[0] for name in historical}
    assert not prefixes & {name.split("_")[0] for name in emulation}, (
        "the two families share a number prefix; a reader cannot tell which "
        "'01_' a report means")


# ---------------------------------------------------------------------------
# partial data
# ---------------------------------------------------------------------------

def test_no_tables_at_all_skips_everything_with_a_reason(tmp_path, plan):
    result = plots.generate(_run(tmp_path), plan)
    assert result["produced"] == []
    assert result["failed"] == {}, "an absent table is not a drawer crash"
    assert set(result["skipped"]) == set(plots.FIGURES)
    for name, reason in result["skipped"].items():
        assert reason.strip(), "%s was skipped with an empty reason" % name


def test_a_header_only_table_is_skipped_not_crashed(tmp_path, plan):
    root = _run(
        tmp_path,
        weights_trajectory="epoca,host,peso\n",
        epoch_shares="epoca,host,quota_osservata_epoca,quota_peso_epoca\n",
        node_observations="node_id,block_height,timestamp_monotonic\n",
        block_propagation="propagation_time\n",
        netem_conditions="netem_delay_ms\n",
    )
    result = plots.generate(root, plan)
    assert result["failed"] == {}
    assert result["produced"] == []


def test_columns_of_the_wrong_type_do_not_crash(tmp_path, plan):
    """Real runs carry 'dato non disponibile' and '-' in numeric columns."""
    root = _run(
        tmp_path,
        weights_trajectory=(
            "epoca,host,peso\n1,m1,dato non disponibile\n2,m1,-\n"),
        node_observations=(
            "node_id,block_height,timestamp_monotonic\n"
            "m1,-,-\nm1,n/d,n/d\n"),
        block_propagation="propagation_time\n-\nn/d\n",
        netem_conditions="netem_delay_ms\n\n\n",
    )
    result = plots.generate(root, plan)
    assert result["failed"] == {}, result["failed"]


def test_a_missing_column_is_a_skip_with_the_column_named(tmp_path, plan):
    root = _run(tmp_path, node_observations="node_id,height,when\nm1,3,1.0\n")
    result = plots.generate(root, plan)
    assert "10_altezza_per_nodo.png" in result["skipped"]
    assert result["failed"] == {}


def test_partial_data_still_draws_what_it_can(tmp_path, plan):
    """The point of the emulation figures: a run whose snapshot failed has no
    campaign sheets at all, and must still get its observation figures."""
    root = _run(
        tmp_path,
        node_observations=(
            "node_id,block_height,timestamp_monotonic\n"
            "m1,1,100.0\nm1,2,110.0\nm2,1,100.5\nm2,2,111.0\n"),
        block_propagation="propagation_time\n0.5\n1.5\n2.0\n0.25\n1.0\n",
        netem_conditions="netem_delay_ms\n12.5\n30.0\n12.5\n45.0\n",
    )
    result = plots.generate(root, plan)
    drawn = {Path(p).name for p in result["produced"]}
    assert drawn == set(plots.EMULATION_FIGURES), (
        "an observation-only run must still get its three figures; got %s"
        % sorted(drawn))
    for name in drawn:
        assert (root / "plots" / name).stat().st_size > 0
    # and the campaign ones are skipped, with reasons, not crashed
    assert set(result["skipped"]) == set(plots.HISTORICAL_FIGURES)
    assert result["failed"] == {}


def test_the_plots_directory_is_created(tmp_path, plan):
    root = _run(tmp_path, netem_conditions="netem_delay_ms\n10.0\n20.0\n")
    assert not (root / "plots").exists()
    plots.generate(root, plan)
    assert (root / "plots").is_dir()


# ---------------------------------------------------------------------------
# a crash must look like a crash
# ---------------------------------------------------------------------------

def test_a_raising_drawer_is_reported_as_failed_not_skipped(
        tmp_path, plan, monkeypatch, caplog):
    def explode(*args, **kwargs):
        raise ZeroDivisionError("synthetic")

    monkeypatch.setattr(plots, "_link_delays", explode)
    with caplog.at_level(logging.WARNING, logger="experiments.analysis.plots"):
        result = plots.generate(_run(tmp_path), plan)

    assert "12_ritardi_link.png" in result["failed"]
    assert "ZeroDivisionError" in result["failed"]["12_ritardi_link.png"]
    assert "12_ritardi_link.png" not in result["skipped"], (
        "a drawer that raised was filed as 'no data', which is how a bug "
        "hides in a report")
    assert any(record.levelno >= logging.ERROR for record in caplog.records), (
        "a failed figure must be logged at ERROR: at INFO it is invisible at "
        "the default threshold")


def test_a_skip_is_logged_loudly_enough_to_be_seen(tmp_path, plan, caplog):
    with caplog.at_level(logging.WARNING, logger="experiments.analysis.plots"):
        plots.generate(_run(tmp_path), plan)
    assert caplog.records, (
        "every figure was skipped and nothing was logged at WARNING; the "
        "reasons existed but no operator would ever see them")


def test_one_failure_does_not_stop_the_others(tmp_path, plan, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(plots, "_height_per_node", explode)
    root = _run(tmp_path, netem_conditions="netem_delay_ms\n10.0\n20.0\n")
    result = plots.generate(root, plan)
    assert "10_altezza_per_nodo.png" in result["failed"]
    assert any(Path(p).name == "12_ritardi_link.png" for p in result["produced"])


def test_the_result_always_carries_all_three_keys(tmp_path, plan):
    """Callers index these unconditionally; a missing key is an AttributeError
    in the report writer, half an hour after the run."""
    result = plots.generate(_run(tmp_path), plan)
    assert set(result) >= {"produced", "skipped", "failed"}
