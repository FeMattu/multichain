"""`summary.md` and `summary_per_epoca.md` must be Markdown, not a CSV dump.

The regression these guard against was real and shipped: the two summaries
were published with a `.md` extension and the migrated analyser's whole
fixed-width body inside a single ``` fence. Four of its sections are the
source CSV pasted in verbatim, so the file a reader opened was Markdown in
extension only, with `m1,13DWP2...,53.52` where a table belonged.

The assertions are deliberately about *shape*, not wording: a heading, real
pipe tables, no bare comma-separated data rows outside a fence, and - the one
that matters most - no content lost in the conversion.
"""

from __future__ import annotations

import re

import pytest

from experiments.analysis import markdown as md

# A faithful miniature of what `analysis/legacy/collect_metrics.py` writes:
# heavy-rule banner, section rules, key/value block, an aligned table with an
# empty cell, a pasted CSV block with the analyser's truncation marker, and a
# JSON blob it cut at 600 characters.
SAMPLE = """
══════════════════════════════════════════════════════════════════
  POESIA / wPoA — riepilogo run: livello regional
══════════════════════════════════════════════════════════════════

── Blocchi ────────────────────────────────────────────────────
  totale prodotti      : 304
  fase di setup (PoA)  : 152 blocchi (height 1..152)

── Traiettoria dei pesi (stream wpoa-weights) ─────────────────
  epoca             m1        m2        m3
  e1                 1         1         1
  e6             59082               29768
  record totali: 139

── Distribuzione dei proposer vs peso pubblicato ──────────────
  host   indirizzo                blocchi     quota
  m2     14rwLucpPvo77JKatEnZgR        35    23.0%
  m5     1JiDczyAZBt1uZVRSCT5gA        32    21.1%

── ESG certificati dal CA (esg_scores.csv) ──
  host,address,esg
  m1,13DWP2zKBTDGazKQLbKux3BGtvDoQ98DucGphs,53.52
  m2,14rwLucpPvo77JKatEnZgRaX1dTw2J44VpENff,89.57
  ... (18 righe totali)

── weightverifyweights (ricomputazione indipendente) ──────────
  {"epoch": 23, "verified": true, "records": 7, "invalid": 0, "entries": [{"addr
"""


@pytest.fixture(scope="module")
def rendered() -> str:
    return md.render(SAMPLE, source="summary.txt")


def _fenced_spans(text: str) -> list:
    """(start, end) line indices of every ``` fence, so tests can exclude them."""
    spans, opened = [], None
    for index, line in enumerate(text.splitlines()):
        if line.startswith("```"):
            if opened is None:
                opened = index
            else:
                spans.append((opened, index))
                opened = None
    if opened is not None:
        spans.append((opened, len(text.splitlines())))
    return spans


def _outside_fences(text: str) -> list:
    spans = _fenced_spans(text)
    return [line for index, line in enumerate(text.splitlines())
            if not any(a <= index <= b for a, b in spans)]


# ---------------------------------------------------------------------------
# the shape of the file
# ---------------------------------------------------------------------------

def test_starts_with_a_markdown_heading(rendered):
    first = rendered.lstrip().splitlines()[0]
    assert first.startswith("# "), (
        "the summary must open with a Markdown H1, not with fixed-width text; "
        "got %r" % first)


def test_carries_markdown_table_syntax(rendered):
    assert re.search(r"^\|[-: |]*-{3}[-: |]*\|$", rendered, re.MULTILINE), (
        "no Markdown table separator row (|---|---|) anywhere in the summary")


def test_every_section_rule_became_a_heading(rendered):
    expected = ["Blocchi", "Traiettoria dei pesi", "Distribuzione dei proposer",
                "ESG certificati dal CA", "weightverifyweights"]
    for name in expected:
        assert re.search(r"^## .*%s" % re.escape(name), rendered, re.MULTILINE), (
            "section %r did not become a '##' heading" % name)


def test_no_box_drawing_rules_survive(rendered):
    for line in _outside_fences(rendered):
        assert "══" not in line and "──" not in line, (
            "a fixed-width rule leaked into the Markdown: %r" % line)


def test_whole_body_is_not_one_code_fence(rendered):
    """The exact regression: everything wrapped, nothing rendered."""
    body = rendered.splitlines()
    fenced = sum(b - a + 1 for a, b in _fenced_spans(rendered))
    assert fenced < len(body) / 2, (
        "more than half the file is inside a code fence (%d of %d lines): "
        "this is the 'wrap it all and call it Markdown' regression"
        % (fenced, len(body)))


# ---------------------------------------------------------------------------
# the CSV blocks, which are the reported bug
# ---------------------------------------------------------------------------

def test_pasted_csv_becomes_a_table(rendered):
    assert "| m1 | 13DWP2zKBTDGazKQLbKux3BGtvDoQ98DucGphs | 53.52 |" in rendered, (
        "the pasted esg_scores.csv block was not turned into a Markdown table")


def test_no_raw_csv_rows_outside_a_fence(rendered):
    """A `.md` must not carry `a,b,c` data rows as body text."""
    offenders = [
        line for line in _outside_fences(rendered)
        if line.count(",") >= 2 and "|" not in line and not line.startswith(">")
        and re.match(r"^\s*\S+,\S+", line)
    ]
    assert not offenders, (
        "raw CSV rows are still in the Markdown body: %r" % offenders[:3])


def test_embedded_tables_are_offered_as_csv():
    tables = md.embedded_tables(SAMPLE)
    assert "ESG certificati dal CA (esg_scores.csv)" in tables
    table = tables["ESG certificati dal CA (esg_scores.csv)"]
    assert table["header"] == ["host", "address", "esg"]
    assert len(table["rows"]) == 2
    text = md.as_csv(table["header"], table["rows"])
    assert text.splitlines()[0] == "host,address,esg"


def test_truncation_marker_is_kept_as_a_note(rendered):
    assert "18 righe totali" in rendered, (
        "the analyser's truncation marker was dropped: a reader would take "
        "the two shown rows for the whole table")


# ---------------------------------------------------------------------------
# aligned tables, including the empty-cell case that broke naive splitting
# ---------------------------------------------------------------------------

def test_aligned_table_keeps_its_columns(rendered):
    assert "| epoca | m1 | m2 | m3 |" in rendered, (
        "the weight trajectory header did not split into one column per "
        "validator")


def test_empty_cell_stays_in_its_own_column(rendered):
    """`e6` published nothing for m2. Splitting on runs of whitespace would
    shift 29768 left into m2's column and silently misreport the run."""
    row = [line for line in rendered.splitlines() if line.startswith("| e6 ")]
    assert row, "the e6 row is missing from the trajectory table"
    cells = [c.strip() for c in row[0].strip("|").split("|")]
    assert cells == ["e6", "59082", "", "29768"], (
        "the empty cell was not preserved: %r" % cells)


def test_footer_line_does_not_destroy_the_table(rendered):
    assert "record totali: 139" in rendered


# ---------------------------------------------------------------------------
# nothing may be lost
# ---------------------------------------------------------------------------

def test_no_content_is_dropped(rendered):
    """Every token of the source must appear in the rendering.

    Commas are split on, because turning `a,b,c` into three cells is the
    point; box-drawing runs are dropped, because they became headings.
    """
    def tokens(text: str) -> list:
        out = []
        for token in re.findall(r"[^\s|,]+", text):
            # Markdown adds emphasis and backticks around what it keeps, and
            # the key/value split consumes the ':' separator itself.
            token = token.strip("*`_")
            if not token or token in (":", "...") or set(token) <= set("─═-.:"):
                continue
            out.append(token)
        return out

    produced = set(tokens(rendered))
    missing = [t for t in tokens(SAMPLE) if t not in produced]
    assert not missing, "content lost in rendering: %r" % missing[:10]


def test_truncated_json_is_flagged_not_silently_shown(rendered):
    assert "Truncated by the analyser" in rendered, (
        "the 600-character cut of verify.json must be labelled: a reader must "
        "not mistake it for the whole record")


# ---------------------------------------------------------------------------
# degradation
# ---------------------------------------------------------------------------

def test_unrecognised_block_is_fenced_not_dropped():
    odd = "── Strana ──\n  ▲▼▲▼  ▲▼▲▼  ▲▼\n  ▼▲▼▲\n"
    out = md.render(odd)
    assert "▲▼▲▼" in out, "an unrecognised block was dropped instead of fenced"


def test_empty_input_still_produces_a_heading():
    out = md.render("")
    assert out.startswith("# "), "an empty summary must still be valid Markdown"
