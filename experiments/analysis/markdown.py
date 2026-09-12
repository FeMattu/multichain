"""Rendering the migrated analysers' fixed-width output as real Markdown.

`collect_metrics.py` and `legacy/summary_per_epoca.py` write the report the
Shadow campaign wrote: box-drawing rules, columns aligned with spaces, and -
in four sections - the source CSV pasted in verbatim. That text is a
contract: the campaign tools parse it, so it must keep being produced byte
for byte, and it is, as `summary.txt` and `summary_epoche.txt`.

What must *not* keep happening is publishing it under a `.md` name with the
whole body inside one ``` fence. A reader gets no headings, no navigable
structure, and four blocks of raw `a,b,c` where a table belongs - a Markdown
file in extension only. This module renders the same text properly:

* the ``══`` banner becomes the document title,
* every ``── Section ──`` rule becomes a ``##`` heading,
* an aligned column block becomes a pipe table,
* a pasted CSV block becomes a pipe table (and is offered as a real `.csv`),
* a ``key : value`` block becomes a two-column table,
* a JSON blob becomes a ```json fence.

Nothing is recomputed and nothing is dropped: anything that does not match a
known shape is emitted verbatim inside its own fence, so an unrecognised
block degrades to what the old renderer did for the whole file rather than
disappearing. `test_summary_format.py` asserts that every non-blank input
line survives into the output.
"""

from __future__ import annotations

import csv
import io
import re

#: The two rules the migrated analysers draw. The heavy one frames the
#: document title, the light one opens a section.
BANNER = re.compile(r"^\s*[═]{6,}\s*$")
SECTION = re.compile(r"^\s*──\s*(?P<name>.*?)\s*[─]{2,}\s*$")
#: A section rule with no trailing run of dashes, e.g. "── Adesioni (x.csv) ──".
SECTION_SHORT = re.compile(r"^\s*──\s*(?P<name>.+?)\s*──\s*$")
#: "  chiave              : valore"
KEY_VALUE = re.compile(r"^\s{1,6}(?P<key>[^:]{1,44}?)\s*:\s(?P<value>.*)$")
#: The analysers' own truncation marker, e.g. "... (176 righe totali)".
TRUNCATION = re.compile(r"^\s*\.\.\.\s*\((?P<rows>\d+)\s+righe totali\)\s*$")


def _escape(cell: str) -> str:
    """A cell may contain a pipe; a Markdown table row may not."""
    return cell.replace("|", r"\|").strip()


def _table(header: list, rows: list) -> list:
    """A pipe table. An empty header is rendered blank rather than dropped."""
    width = max([len(header)] + [len(r) for r in rows]) if rows else len(header)
    header = list(header) + [""] * (width - len(header))
    out = ["| " + " | ".join(_escape(c) for c in header) + " |",
           "|" + "|".join("---" for _ in header) + "|"]
    for row in rows:
        row = list(row) + [""] * (width - len(row))
        out.append("| " + " | ".join(_escape(c) for c in row) + " |")
    return out


def _fence(lines: list, language: str = "text") -> list:
    return ["```" + language] + [line.rstrip() for line in lines] + ["```"]


# ---------------------------------------------------------------------------
# block classification
# ---------------------------------------------------------------------------

def _csv_block(lines: list):
    """Rows of a pasted CSV block, or None.

    The analysers paste `esg_scores.csv`, `membership.csv`,
    `reconciliation.csv` and `gas_transfers.csv` straight into the text. They
    are recognisable: every line splits into the same number of
    comma-separated fields, and none of them uses column alignment.
    """
    body = [line for line in lines if not TRUNCATION.match(line)]
    if len(body) < 2:
        return None
    rows = []
    for line in body:
        stripped = line.strip()
        if "," not in stripped or re.search(r"\S {2,}\S", stripped):
            return None
        rows.append(next(csv.reader([stripped])))
    widths = {len(r) for r in rows}
    if len(widths) != 1 or widths.pop() < 2:
        return None
    return rows


def _fixed_width_columns(lines: list):
    """Split an aligned block into columns, or None.

    The split is on the character positions that are blank in *every* line of
    the block, which is the only rule that survives both right-aligned numbers
    and genuinely empty cells - the weight trajectory has both, and splitting
    on runs of whitespace per line silently shifts its columns left wherever a
    validator published nothing that epoch.
    """
    if len(lines) < 2:
        return None
    width = max(len(line) for line in lines)
    padded = [line.ljust(width) for line in lines]
    blank = [all(line[i] == " " for line in padded) for i in range(width)]

    gaps, start = [], None
    for i, is_blank in enumerate(blank):
        if is_blank and start is None:
            start = i
        elif not is_blank and start is not None:
            if i - start >= 2:
                gaps.append((start, i))
            start = None
    if start is not None and width - start >= 2:
        gaps.append((start, width))

    bounds, cursor = [], 0
    for gap_start, gap_end in gaps:
        if gap_start > cursor:
            bounds.append((cursor, gap_start))
        cursor = gap_end
    if cursor < width:
        bounds.append((cursor, width))
    if len(bounds) < 2:
        return None
    return [[line[a:b].strip() for a, b in bounds] for line in padded]


def _key_value_block(lines: list):
    """Pairs of a ``key : value`` block, or None.

    Requires every line to match, not a majority: a block where one line is
    prose and the rest are pairs reads better whole, as text.
    """
    pairs = []
    for line in lines:
        match = KEY_VALUE.match(line)
        if not match or line.strip().startswith(("->", "NB:", "ATTENZIONE")):
            return None
        pairs.append([match.group("key").strip(), match.group("value").strip()])
    return pairs if len(pairs) >= 2 else None


def _json_block(lines: list):
    text = " ".join(line.strip() for line in lines).strip()
    return text if text.startswith(("{", "[")) else None


def _peel(lines: list):
    """Split a block into (lead-in lines, table lines, trailing notes).

    An aligned table in this output is routinely bracketed by prose: a lead-in
    ending in a colon above it, a total or a caveat below it. Those lines run
    across the column gaps, so leaving them in destroys the very blankness the
    column detector reads - the weight trajectory loses its first column to
    the ``record totali: 139`` line underneath it. Dropping up to two lines
    from each end and keeping whichever split yields the most columns
    recovers the grid without a rule per section.
    """
    best = (0, 0, 0, None)          # columns, head dropped, tail dropped, grid
    for head in range(0, 3):
        for tail in range(0, 3):
            body = lines[head:len(lines) - tail if tail else None]
            if len(body) < 2:
                continue
            grid = _fixed_width_columns(body)
            if grid is None:
                continue
            columns = len(grid[0])
            better = columns > best[0] or (
                columns == best[0] and head + tail < best[1] + best[2])
            if better:
                best = (columns, head, tail, grid)
    if best[3] is None:
        return [], None, []
    _, head, tail, grid = best
    return (lines[:head], grid,
            lines[len(lines) - tail:] if tail else [])


def _looks_like_prose(lines: list) -> bool:
    """Sentences, not data: rendered as text rather than forced into a table."""
    joined = " ".join(line.strip() for line in lines)
    if not joined:
        return True
    if re.search(r"\S {2,}\S", joined) and len(lines) > 1:
        return False
    return bool(re.search(r"[a-z]{4,}\s+[a-z]{3,}", joined))


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def _render_block(lines: list, tables: dict, section: str) -> list:
    """One block of consecutive non-blank lines, as Markdown."""
    lines = [line.rstrip() for line in lines]
    if not lines:
        return []

    blob = _json_block(lines)
    if blob is not None:
        return _json_lines(blob)

    note = [line.strip() for line in lines if TRUNCATION.match(line)]
    rows = _csv_block(lines)
    if rows is not None:
        header, body = _csv_header_split(rows)
        out = _table(header, body)
        if note:
            out += ["", "*%s*" % note[0].lstrip(". ").strip()]
        tables.setdefault(section, []).append((header, body))
        return out

    pairs = _key_value_block(lines)
    if pairs is not None:
        return _table(["", ""], pairs)

    if not _looks_like_prose(lines):
        before, grid, after = _peel(lines)
        if grid is not None and len(grid[0]) >= 2:
            head, body = grid[0], grid[1:]
            # A first row that is all data (no word-like header) gets a blank
            # header rather than losing its first row to the header slot.
            if not any(re.search(r"[A-Za-z]", cell) for cell in head):
                head, body = [""] * len(grid[0]), grid
            out = [line.strip() for line in before]
            if before:
                out.append("")
            out += _table(head, body)
            if after:
                out.append("")
                out += [line.strip() for line in after]
            return out

    if len(lines) == 1 or _looks_like_prose(lines):
        return [line.strip() for line in lines]
    return _fence(lines)


def _json_lines(blob: str) -> list:
    """A JSON blob, pretty-printed when it parses and fenced when it does not.

    `collect_metrics` truncates it at 600 characters, so it usually does not
    parse. Saying so is the point: a reader must not mistake a cut-off object
    for the whole record.
    """
    import json

    try:
        return _fence(json.dumps(json.loads(blob), indent=2).splitlines(), "json")
    except ValueError:
        return (["> **Truncated by the analyser** - this is the first %d characters "
                 "of the record, not the whole of it. The complete object is in "
                 "`raw/metrics/verify.json`." % len(blob), ""]
                + _fence([blob], "text"))


def _csv_header_split(rows: list):
    """Header row and body, if the first row names columns rather than data."""
    first = rows[0]
    numeric = sum(1 for cell in first if re.fullmatch(r"-?\d+(\.\d+)?", cell.strip()))
    if numeric == 0 and all(len(cell) <= 24 for cell in first):
        return first, rows[1:]
    return [""] * len(first), rows


def render(text: str, *, source: str = "", intro: str = "") -> str:
    """The fixed-width report as Markdown. Content is preserved, not summarised."""
    lines = text.splitlines()
    out: list = []
    tables: dict = {}
    title = ""
    section = ""

    index = 0
    block: list = []

    def flush() -> None:
        nonlocal block
        if block:
            rendered = _render_block(block, tables, section)
            if rendered:
                out.extend(rendered)
                out.append("")
        block = []

    while index < len(lines):
        line = lines[index]
        if BANNER.match(line):
            flush()
            # The title is the line between two heavy rules.
            if index + 2 < len(lines) and BANNER.match(lines[index + 2]):
                title = lines[index + 1].strip()
                index += 3
                continue
            index += 1
            continue
        match = SECTION.match(line) or SECTION_SHORT.match(line)
        if match:
            flush()
            section = match.group("name").strip()
            out += ["## %s" % section, ""]
            index += 1
            continue
        if not line.strip():
            flush()
            index += 1
            continue
        block.append(line)
        index += 1
    flush()

    head = ["# %s" % (title or "Run summary"), ""]
    if intro:
        head += [intro.rstrip(), ""]
    if source:
        head += ["> Rendered from `%s`, which is the migrated Shadow analyser's "
                 "own fixed-width output and is kept beside this file "
                 "unchanged." % source, ""]
    body = "\n".join(head + out).rstrip("\n")
    return body + "\n"


def embedded_tables(text: str) -> dict:
    """The CSV blocks the analyser pasted into the text, section by section.

    The text truncates each at ten rows or so; this returns what is actually
    in the report, so a caller can write it out as a real `.csv` instead of
    leaving comma-separated lines inside a Markdown file.
    """
    tables: dict = {}
    section = ""
    block: list = []

    def flush() -> None:
        nonlocal block
        if block:
            rows = _csv_block(block)
            if rows is not None:
                header, body = _csv_header_split(rows)
                tables[section] = {"header": header, "rows": body}
        block = []

    for line in text.splitlines():
        match = SECTION.match(line) or SECTION_SHORT.match(line)
        if BANNER.match(line):
            flush()
            continue
        if match:
            flush()
            section = match.group("name").strip()
            continue
        if not line.strip():
            flush()
            continue
        block.append(line)
    flush()
    return tables


def as_csv(header: list, rows: list) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    if any(cell for cell in header):
        writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()
