"""The analysis prompt and the real schemas must not drift apart.

The prompt is what an external agent is given instead of the code. If it
describes a column the harness no longer writes, the agent reports a gap that
does not exist; if it misses one, the agent never reads it. Neither failure is
visible from either file alone, so it is asserted here.

The schema section of the prompt is generated from the catalogue, and the
catalogue is checked against the columns the collectors actually write by
``test_csv_contract.py``. These two tests together are the chain
prompt -> catalogue -> produced CSV.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from experiments.metrics import catalogue
from experiments.metrics.prompt_schema import BEGIN, END, render_tables, splice
from experiments.paths import PACKAGE_ROOT

PROMPT = PACKAGE_ROOT / "docs" / "pipeline" / "PROMPT_ANALISI_ESPERIMENTO.md"


@pytest.fixture(scope="module")
def text() -> str:
    assert PROMPT.is_file(), "the merged analysis prompt is missing: %s" % PROMPT
    return PROMPT.read_text(encoding="utf-8")


def test_the_declared_schema_is_the_catalogue(text):
    """Regenerate and compare. Fails on any drift, in either direction.

    To fix a failure: `python3 -c "import pathlib;
    from experiments.metrics.prompt_schema import splice;
    p=pathlib.Path('experiments/docs/pipeline/PROMPT_ANALISI_ESPERIMENTO.md');
    p.write_text(splice(p.read_text()))"` — and say in the commit what changed.
    """
    assert BEGIN in text and END in text, "the generated-schema markers are gone"
    assert splice(text) == text, (
        "the prompt's schema section no longer matches experiments/metrics/catalogue.py")


def test_every_catalogued_column_is_described(text):
    """A column the harness writes and the prompt never mentions is invisible."""
    declared = set(re.findall(r"^\| `([A-Za-z0-9_]+)` \|", text, re.M))
    missing = []
    for table in catalogue.ALL_TABLES:
        for column in table.columns:
            if column.name not in declared:
                missing.append("%s.%s" % (table.name, column.name))
    assert not missing, "not described in the prompt: %s" % sorted(missing)


def test_every_file_the_brief_requires_is_listed(text):
    """The prompt must name exactly what the analyst is allowed to open."""
    required = [
        "manifest.json",
        "metrics/alternanze.csv", "metrics/block_times.csv", "metrics/chisq.csv",
        "metrics/epoch_shares.csv", "metrics/esg.csv", "metrics/forks.csv",
        "metrics/gas.csv", "metrics/proposers.csv", "metrics/run_index.csv",
        "metrics/sortition_margins.csv", "metrics/verify.csv",
        "metrics/weights_trajectory.csv",
        "reports/summary_per_epoca.md", "reports/report_generale.md",
        "reports/report_confronto.md", "reports/report_asse_livello.md",
        "reports/report_asse_tbt.md", "reports/metrics_schema_report.md",
        "raw/rpc/", "role_controller.log",
    ]
    missing = [name for name in required if name not in text]
    assert not missing, "the prompt does not list: %s" % missing


def test_the_temporal_rule_is_stated_before_anything_else(text):
    """A reader who assumes Shadow semantics misreads every duration."""
    assert "temporal_model: wall_clock_emulation" in text
    for name in ("wall_clock_time", "monotonic_time", "block_timestamp",
                 "first_seen_wallclock", "last_seen_wallclock", "elapsed_wallclock"):
        assert name in text, name
    # It must come early: the rule is useless in an appendix.
    assert text.index("There is no Shadow simulated time") < 3000


def test_the_prompt_forbids_inventing_data(text):
    assert "dato non disponibile" in text
    assert "Do not invent a missing value" in text


def test_the_output_format_is_the_twelve_sections(text):
    for section in ("Sintesi esecutiva", "Validazione della completezza dei dati",
                    "Tabella peso atteso vs blocchi osservati", "Analisi per epoca",
                    "Analisi geografica e di rete", "Transazioni e throughput",
                    "Fork, liveness e safety", "Anomalie nei log/RPC",
                    "Criticità ordinate per severità", "Raccomandazioni operative",
                    "Limiti e dati mancanti", "Verdetto finale prudente"):
        assert section in text, section


def test_both_sources_are_named_and_their_conflicts_resolved(text):
    """The merge has to be explicit about what wins, or it is not a merge."""
    assert "PROMPT_REPORT_ESPERIMENTI.md" in text
    assert "PROMPT_ANALISI.md" in text
    assert "Where they conflict" in text
