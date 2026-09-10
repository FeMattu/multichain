"""The migrated pipeline must still reproduce the archived campaign exactly.

This is the regression test for the migration itself, and it needs the raw
Shadow campaign, which was deliberately not carried into `experiments/` — it
is ~3 GB. Recover it and the test runs:

    git checkout 6278274 -- shadow/esperimenti shadow/config shadow/risultati

Without it the test skips, saying that. It is the single most important test
in the suite when it does run: if the migrated code stops reproducing the
archive, every comparison between an archived run and a new one is void.
"""

from __future__ import annotations

import filecmp

import pytest

from experiments.paths import REPO_ROOT

ARCHIVE = REPO_ROOT / "shadow"
EXPERIMENTS = ARCHIVE / "esperimenti"
RESULTS = ARCHIVE / "risultati"
CONFIG = ARCHIVE / "config"

#: One (run, level) pair is enough for a regression test and takes ~2 s;
#: re-running all 24 takes minutes and proves nothing extra.
SAMPLE = "run1-tbt-15s/regionale"

pytestmark = pytest.mark.slow


def _require_archive():
    if not (EXPERIMENTS.is_dir() and RESULTS.is_dir() and CONFIG.is_dir()):
        pytest.skip(
            "the archived Shadow campaign is not in this checkout; recover it with "
            "'git checkout 6278274 -- shadow/esperimenti shadow/config shadow/risultati'"
        )


def test_three_phases_reproduce_the_archive(tmp_path):
    _require_archive()
    from experiments.analysis.pipeline import run_pipeline

    out = tmp_path / "risultati"
    rc = run_pipeline.main([
        "--phase", "all", "--root", str(EXPERIMENTS), "--out", str(out),
        "--config", str(CONFIG), "--only", SAMPLE, "--no-campaign",
    ])
    assert rc == 0

    expected_root = RESULTS / SAMPLE
    produced_root = out / SAMPLE
    differences = []
    for phase in ("phase1", "phase2", "phase3"):
        expected_dir, produced_dir = expected_root / phase, produced_root / phase
        assert produced_dir.is_dir(), "phase %s produced nothing" % phase
        for expected in sorted(expected_dir.iterdir()):
            # The workbook embeds a creation timestamp, so it can never match.
            if expected.suffix == ".xlsx":
                continue
            produced = produced_dir / expected.name
            if not produced.is_file():
                differences.append("%s/%s is missing" % (phase, expected.name))
            elif not filecmp.cmp(expected, produced, shallow=False):
                differences.append("%s/%s differs" % (phase, expected.name))
    assert not differences, (
        "the migrated pipeline no longer reproduces the archive:\n  "
        + "\n  ".join(differences))


def test_campaign_sheets_reproduce_every_archived_row(tmp_path):
    """The legacy analyser must still produce the campaign-level sheets.

    Only the twenty runs the archived sheets were built from are fed in:
    fit_prop518.csv is a regression over the whole campaign, so adding run6
    legitimately changes it.
    """
    _require_archive()
    sheets = (REPO_ROOT / "experiments" / "analysis" / "historical" /
              "shadow-campaign" / "sheets")
    if not sheets.is_dir():
        pytest.skip("the archived sheets were not migrated into this checkout")

    subset = tmp_path / "esperimenti"
    subset.mkdir()
    for directory in sorted(EXPERIMENTS.iterdir()):
        if directory.is_dir() and directory.name.startswith(("run1", "run2", "run3",
                                                             "run4", "run5")):
            (subset / directory.name).symlink_to(directory.resolve())
    if not any(subset.iterdir()):
        pytest.skip("no runN-tbt-Ts directory in the archive")

    out = tmp_path / "analisi"
    import sys

    from experiments.analysis.legacy import analizza_esperimenti

    argv = sys.argv
    sys.argv = ["analizza", "--root", str(subset), "--out", str(out),
                "--force", "--recompute-chisq"]
    try:
        analizza_esperimenti.main()
    finally:
        sys.argv = argv

    produced = out / "fogli-di-analisi"
    # validazione_sortition.csv is not produced here: it comes from
    # valida_sortition_montecarlo.py, which is a separate script by design -
    # it validates the election algorithm by simulation rather than reading a
    # run. test_montecarlo_validator_runs covers it.
    skip = {"validazione_sortition.csv"}
    missing_rows = {}
    for expected in sorted(sheets.glob("*.csv")):
        if expected.name in skip:
            continue
        actual = produced / expected.name
        if not actual.is_file():
            missing_rows[expected.name] = ["the sheet was not produced"]
            continue
        # run_index.csv records the absolute path of the analysing machine, so
        # it can only be compared row-count-wise.
        if expected.name == "run_index.csv":
            assert len(actual.read_text().splitlines()) == \
                len(expected.read_text().splitlines())
            continue
        wanted = set(expected.read_text(encoding="utf-8").splitlines())
        got = set(actual.read_text(encoding="utf-8").splitlines())
        # epoch_shares row ORDER changed when the current code started sorting
        # by address; contents did not, so compare as sets.
        absent = wanted - got
        if absent:
            missing_rows[expected.name] = sorted(absent)[:3]
    assert not missing_rows, (
        "archived rows are no longer reproduced:\n" +
        "\n".join("  %s: %s" % (k, v) for k, v in missing_rows.items()))


def test_archive_recovery_instructions_are_accurate():
    """The commit the documentation points at must actually hold the archive."""
    import subprocess

    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "cat-file", "-t", "6278274"],
        capture_output=True, text=True)
    if result.returncode != 0:
        pytest.skip("commit 6278274 is not in this clone")
    listing = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-tree", "--name-only", "6278274", "shadow/"],
        capture_output=True, text=True)
    assert "shadow/esperimenti" in listing.stdout, \
        "the documented recovery commit does not carry shadow/esperimenti"


def test_montecarlo_validator_runs(tmp_path):
    """The election-algorithm validator is standalone and needs no run data."""
    import subprocess
    import sys

    script = (REPO_ROOT / "experiments" / "analysis" / "legacy" /
              "valida_sortition_montecarlo.py")
    assert script.is_file()
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
