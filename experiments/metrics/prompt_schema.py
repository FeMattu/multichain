"""The schema section of the analysis prompt, generated from the catalogue.

The prompt tells an external agent what every column means. Hand-written, it
drifts: a column is added to the harness, the prompt keeps describing the old
shape, and the agent reports a gap that does not exist — or worse, quietly
reads a column that no longer means what the prompt says.

So the catalogue is the single declaration and this renders it. The prompt
file carries the output between two markers, and
``tests/golden/test_prompt_schema.py`` regenerates it and fails when the file
and the catalogue disagree.
"""

from __future__ import annotations

from .catalogue import ALL_TABLES, DERIVED, OBSERVED, UNAVAILABLE

BEGIN = "<!-- BEGIN GENERATED SCHEMA -->"
END = "<!-- END GENERATED SCHEMA -->"

#: The four statuses the brief asks every metric to declare itself as.
STATUS = {
    OBSERVED: "observed",
    DERIVED: "derived",
    UNAVAILABLE: "not applicable",
}

#: Where each table is written, relative to the run directory.
LOCATION = {True: "metrics/", False: "raw/observations/"}


def _row(column) -> str:
    missing = column.note or ("empty when not applicable" if
                              column.status == UNAVAILABLE else "empty")
    return "| `%s` | %s | %s | %s | %s | %s |" % (
        column.name,
        STATUS.get(column.status, column.status),
        column.unit or "—",
        column.description.replace("\n", " "),
        column.source or "—",
        missing.replace("\n", " "),
    )


def render_tables() -> str:
    """Every catalogued table, with the six facts the brief requires."""
    lines = []
    for table in ALL_TABLES:
        location = LOCATION[table.historical]
        lines += ["### `%s%s.csv`" % (location, table.name), "",
                  table.description, ""]
        if not table.columns:
            lines += ["Columns are those of the archived Shadow campaign and are",
                      "reproduced verbatim by the migrated analyser; see",
                      "`experiments/analysis/legacy/` and the golden byte comparison",
                      "in `tests/golden/`.", ""]
            continue
        lines += ["| column | status | unit | meaning | source | when missing |",
                  "|---|---|---|---|---|---|"]
        lines += [_row(column) for column in table.columns]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def splice(text: str) -> str:
    """Replace whatever sits between the markers with the current schema."""
    if BEGIN not in text or END not in text:
        raise ValueError("the prompt has no generated-schema markers")
    head = text[:text.index(BEGIN) + len(BEGIN)]
    tail = text[text.index(END):]
    return "%s\n\n%s\n%s" % (head, render_tables(), tail)
