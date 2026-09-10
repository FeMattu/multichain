"""The metric catalogue and its validators."""

from __future__ import annotations

from experiments.metrics import catalogue, schema_report, validators


def test_every_column_has_a_status_and_a_description():
    for table in catalogue.ALL_TABLES:
        assert table.columns, table.name
        for column in table.columns:
            assert column.status in (catalogue.OBSERVED, catalogue.DERIVED,
                                     catalogue.UNAVAILABLE)
            assert column.description.strip(), "%s.%s" % (table.name, column.name)


def test_observed_and_derived_columns_name_their_source():
    for table in catalogue.ALL_TABLES:
        for column in table.columns:
            if column.status in (catalogue.OBSERVED, catalogue.DERIVED):
                assert column.source.strip(), "%s.%s" % (table.name, column.name)


def test_unavailable_columns_explain_themselves():
    absent = validators.unavailable_columns()
    assert absent, "the catalogue should name what it cannot measure"
    for entry in absent:
        assert len(entry["reason"]) > 30, entry


def test_the_twelve_historical_tables_are_all_declared():
    names = {t.name for t in catalogue.HISTORICAL_TABLES}
    assert names == {
        "run_index", "block_times", "proposers", "chisq", "epoch_shares",
        "weights_trajectory", "sortition_margins", "alternanze", "forks",
        "verify", "esg", "gas",
    }


def test_table_names_are_unique():
    names = [t.name for t in catalogue.ALL_TABLES]
    assert len(names) == len(set(names))


def test_catalogue_matches_the_collectors_column_order():
    """The catalogue tracks the writer, because readers index by position."""
    from experiments.runtime.collectors.process import PROCESS_COLUMNS
    from experiments.runtime.collectors.rpc import OBSERVATION_COLUMNS

    declared = catalogue.table("node_observations").column_names
    common = [c for c in OBSERVATION_COLUMNS if c in declared]
    assert common == [c for c in declared if c in OBSERVATION_COLUMNS]

    declared = catalogue.table("process_samples").column_names
    common = [c for c in PROCESS_COLUMNS if c in declared]
    assert common == [c for c in declared if c in PROCESS_COLUMNS]


def test_schema_report_renders_and_mentions_the_three_statuses():
    text = schema_report.render()
    assert "# Metric schema" in text
    for status in ("observed", "derived", "unavailable"):
        assert status in text
    for table in catalogue.ALL_TABLES:
        assert "`%s.csv`" % table.name in text


def test_validator_accepts_extra_columns_but_not_reordering(tmp_path):
    declared = catalogue.table("netem_conditions").column_names
    good = tmp_path / "netem_conditions.csv"
    good.write_text(",".join(declared + ["something_new"]) + "\n", encoding="utf-8")
    assert validators.check_table(good, "netem_conditions") == []

    swapped = declared[:]
    swapped[0], swapped[1] = swapped[1], swapped[0]
    bad = tmp_path / "bad.csv"
    bad.write_text(",".join(swapped) + "\n", encoding="utf-8")
    problems = validators.check_table(bad, "netem_conditions")
    assert any("reordered" in p for p in problems)


def test_validator_tolerates_an_absent_unavailable_column(tmp_path):
    table = catalogue.table("netem_conditions")
    present = [c.name for c in table.columns if c.status != catalogue.UNAVAILABLE]
    path = tmp_path / "netem_conditions.csv"
    path.write_text(",".join(present) + "\n", encoding="utf-8")
    assert validators.check_table(path, "netem_conditions") == []


def test_validator_reports_a_missing_required_column(tmp_path):
    table = catalogue.table("netem_conditions")
    present = [c.name for c in table.columns
               if c.status != catalogue.UNAVAILABLE][1:]
    path = tmp_path / "netem_conditions.csv"
    path.write_text(",".join(present) + "\n", encoding="utf-8")
    problems = validators.check_table(path, "netem_conditions")
    assert any("absent from the file" in p for p in problems)
