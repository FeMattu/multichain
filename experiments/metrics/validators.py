"""Checking that a produced table still matches its declared schema.

The point is regression, not correctness of the numbers: a refactor that
renames a column or reorders the header breaks every downstream report and
every comparison with the archive, and it does so silently. These checks turn
that into a failed test.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .catalogue import ALL_TABLES, UNAVAILABLE, table


def read_header(path: Path) -> list:
    path = Path(path)
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle), [])


def check_table(path: Path, table_name: str) -> list:
    """Problems with one produced table. Empty means it matches."""
    problems = []
    try:
        declared = table(table_name)
    except KeyError:
        return ["%s is not in the catalogue" % table_name]
    header = read_header(path)
    if not header:
        return ["%s is missing or empty" % path]
    declared_names = declared.column_names
    # A column declared UNAVAILABLE may legitimately be absent: "declared
    # absent, with the reason" is the whole point of that status. Requiring it
    # to exist as an empty column would defeat it.
    required = [c.name for c in declared.columns if c.status != UNAVAILABLE]
    missing = [name for name in required if name not in header]
    if missing:
        problems.append(
            "%s: declared columns absent from the file: %s" % (path.name, ", ".join(missing))
        )
    # Extra columns are fine - the compatibility rule is additive - but a
    # REORDERED prefix is not, because readers index by position.
    common = [name for name in header if name in declared_names]
    expected_order = [name for name in declared_names if name in header]
    if common != expected_order:
        problems.append(
            "%s: declared columns are reordered (%s vs %s)"
            % (path.name, ", ".join(common), ", ".join(expected_order))
        )
    return problems


def check_run(metrics_dir: Path) -> dict:
    """Check every catalogued table a run directory contains.

    ``problems`` fails a run; ``empty`` and ``absent`` do not. An empty table
    with a correct header is a fact about the run ("nothing happened"), not a
    schema violation, and a historical table's header is data-dependent by
    construction - see Table.enforced.
    """
    metrics_dir = Path(metrics_dir)
    # The collectors write into raw/observations and the analysers into
    # metrics; looking in one tree only reported healthy tables as absent.
    observations = metrics_dir.parent / "raw" / "observations"
    report = {"checked": [], "problems": [], "absent": [], "empty": [],
              "reported_only": []}
    for entry in ALL_TABLES:
        path = metrics_dir / ("%s.csv" % entry.name)
        if not path.is_file():
            alternative = observations / ("%s.csv" % entry.name)
            if alternative.is_file():
                path = alternative
            else:
                report["absent"].append(entry.name)
                continue
        if path.stat().st_size == 0:
            report["empty"].append(entry.name)
            continue
        if not entry.enforced:
            report["reported_only"].append(entry.name)
            continue
        report["checked"].append(entry.name)
        report["problems"].extend(check_table(path, entry.name))
    return report


def unavailable_columns() -> list:
    """Every column the catalogue declares absent, with its reason.

    Reported by ``metrics schema`` so the gaps are visible without reading
    the whole catalogue.
    """
    out = []
    for entry in ALL_TABLES:
        for column in entry.columns:
            if column.status == UNAVAILABLE:
                out.append({"table": entry.name, "column": column.name,
                            "reason": column.note or column.description})
    return out
