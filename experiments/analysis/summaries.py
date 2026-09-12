"""The two textual summaries the Shadow suite produced, for a native run.

`summary.txt` and `summary_epoche.txt` were not decoration. The first is the
run's readable verdict — block times against the target, the proposer
distribution against the published weights, the chi-square, the sortition
delays, fork detection. The second is the same analysis **per epoch**, which
is the honest one whenever the weights move between epochs, because the
run-level test compares all the blocks against the *last* weight.

They were also load-bearing in a way that is easy to miss: the campaign-level
`chisq.csv` takes its authoritative chi-square by parsing `summary.txt`. A
run without one produces a `chisq.csv` whose `chi2_summary` column is empty —
which is exactly the "CSV parziali" symptom this module removes.

Nothing is reimplemented here. Both generators are the migrated Shadow code;
this only calls them with the paths and parameters a native run has.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from . import summary_per_epoca
from .layout import resolve as resolve_layout

LOG = logging.getLogger("experiments.analysis.summaries")

#: What the admin writes when its final snapshot could not be taken.
SNAPSHOT_FAILURE = "snapshot_failed.json"


def snapshot_verdict(run_root: Path) -> str:
    """Why the snapshot is missing, and whether re-analysis can recover it.

    "no blocks.json" on its own sends a reader looking for a bug in the
    analysis. The distinction that matters is whether the input was never
    produced - in which case no amount of re-running this code will help, and
    the run has to be repeated.
    """
    import json

    path = resolve_layout(run_root).metrics / SNAPSHOT_FAILURE
    if path.is_file():
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            record = {}
        return ("The admin's final snapshot was NOT taken (%s, at %s). This is "
                "UNRECOVERABLE by re-analysis: the data was never written. "
                "Re-run the experiment."
                % (record.get("reason", "reason not recorded"),
                   record.get("wallclock", "time not recorded")))
    return ("The admin's final snapshot did not happen and left no record of "
            "why. Check `logs/admin/` for the daemon's exit. If the daemon "
            "died before teardown this is UNRECOVERABLE by re-analysis.")


def write_run_summary(run_root: Path, plan, *, setup_blocks: int | None = None) -> Path | None:
    """Produce ``summary.txt`` — and therefore a complete ``chisq.csv``."""
    from .legacy import collect_metrics

    layout = resolve_layout(run_root)
    if not (layout.metrics / "blocks.json").is_file():
        LOG.warning("no blocks.json in %s: summary.txt cannot be written. %s",
                    layout.metrics, snapshot_verdict(run_root))
        return None
    argv = sys.argv
    sys.argv = [
        "collect_metrics",
        "--run", str(run_root),
        "--chain", plan.multichain.chain,
        "--level", plan.scenario,
        "--setup-blocks", str(setup_blocks if setup_blocks is not None
                              else plan.setup_first_blocks),
        "--epoch-len", str(plan.epoch_length),
        "--tbt", str(plan.target_block_time),
        "--delta", str(plan.chain_params.sortition_delta),
    ]
    try:
        collect_metrics.main()
    except SystemExit as exc:
        if exc.code not in (0, None):
            LOG.warning("collect_metrics exited with %s", exc.code)
    except Exception as exc:  # noqa: BLE001 - a summary must not sink a run
        LOG.error("summary.txt could not be written: %s", exc)
        return None
    finally:
        sys.argv = argv
    path = layout.metrics / "summary.txt"
    if path.is_file():
        LOG.info("summary.txt written (%d lines)",
                 len(path.read_text(encoding="utf-8").splitlines()))
        return path
    return None


def write_epoch_summary(run_root: Path, plan) -> Path | None:
    """Produce ``summary_epoche.txt``: the same analysis, epoch by epoch."""
    from .legacy import summary_per_epoca

    layout = resolve_layout(run_root)
    if not (layout.metrics / "blocks.json").is_file():
        LOG.warning("no blocks.json in %s: the per-epoch summary needs the "
                    "final snapshot. %s", layout.metrics, snapshot_verdict(run_root))
        return None
    argv = sys.argv
    sys.argv = [
        "summary_per_epoca",
        "--run", str(run_root),
        "--level", plan.scenario,
        "--tbt", str(plan.target_block_time),
    ]
    try:
        summary_per_epoca.main()
    except SystemExit as exc:
        if exc.code not in (0, None):
            LOG.warning("summary_per_epoca exited with %s", exc.code)
    except Exception as exc:  # noqa: BLE001
        LOG.error("summary_epoche.txt could not be written: %s", exc)
        return None
    finally:
        sys.argv = argv
    path = layout.metrics / "summary_epoche.txt"
    if path.is_file():
        LOG.info("summary_epoche.txt written (%d lines)",
                 len(path.read_text(encoding="utf-8").splitlines()))
        return path
    return None


#: `<source in metrics/>` -> `<Markdown in reports/>`, `<analyser>`.
#: `summary_per_epoca.md` keeps its name: docs/migration-from-shadow.md, the
#: analysis prompt and tests/golden/test_prompt_schema.py all key on it.
PUBLISHED = (
    ("summary.txt", "summary.md", "collect_metrics.py"),
    ("summary_epoche.txt", "summary_per_epoca.md", "summary_per_epoca.py"),
)


def publish_to_reports(run_root: Path) -> list:
    """Render both summaries into ``reports/`` as real Markdown.

    `metrics/` is where the analysers write and where the campaign tools look;
    `reports/` is where a reader looks. The `.txt` is copied over unchanged so
    the first contract survives, and the `.md` beside it is a *rendering*, not
    a wrapper: headings, pipe tables, and the four sections the analyser
    pastes in as raw CSV turned into tables and written out as `.csv` files of
    their own. Wrapping the whole fixed-width dump in one ``` fence - which is
    what this did - produced a file that was Markdown only in its extension.
    """
    import shutil

    from . import markdown as md

    layout = resolve_layout(run_root)
    reports = Path(run_root) / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    tables_dir = reports / "tables"
    written = []
    for source_name, target_name, analyser in PUBLISHED:
        source = layout.metrics / source_name
        if not source.is_file():
            LOG.warning("%s is absent from %s: %s was not published",
                        source_name, layout.metrics, target_name)
            continue
        body = source.read_text(encoding="utf-8")
        target = reports / target_name
        exported = _export_embedded_tables(body, tables_dir, md)
        target.write_text(
            md.render(
                body,
                source=source_name,
                intro=("> Produced by the migrated Shadow analyser "
                       "(`analysis/legacy/%s`) over a run of **real** "
                       "MultiChain processes on an emulated network, measured "
                       "against the wall clock.%s" % (analyser, exported.note)),
            ),
            encoding="utf-8")
        written.append(target)
        written.extend(exported.files)
        shutil.copy2(source, reports / source_name)
    return written


class _Exported:
    __slots__ = ("files", "note")

    def __init__(self, files: list, note: str):
        self.files = files
        self.note = note


def _export_embedded_tables(body: str, tables_dir: Path, md) -> _Exported:
    """Write the pasted-in CSV sections out as `.csv` files.

    The analyser truncates each block at about ten rows, so these are a
    convenience for reading the report, not the authoritative table - which is
    the file named in the section heading, under `raw/metrics/`. The note says
    so, because a truncated CSV that does not admit to being truncated is
    worse than no CSV.
    """
    import re

    embedded = md.embedded_tables(body)
    if not embedded:
        return _Exported([], "")
    tables_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for section, table in sorted(embedded.items()):
        stem = re.sub(r"[^a-z0-9]+", "_", section.lower()).strip("_")[:60] or "table"
        path = tables_dir / ("%s.csv" % stem)
        path.write_text(md.as_csv(table["header"], table["rows"]), encoding="utf-8")
        files.append(path)
    return _Exported(
        files,
        "\n> The CSV blocks the analyser pastes into the text are also written "
        "to `reports/tables/` as files. They carry only the rows the report "
        "shows; the complete tables are the ones named in each heading, under "
        "`raw/metrics/`.")


def write_all(run_root: Path, plan, *, setup_blocks: int | None = None) -> dict:
    """Both summaries, then their copies under ``reports/``."""
    produced = {
        "summary": str(write_run_summary(run_root, plan, setup_blocks=setup_blocks) or ""),
        "summary_per_epoch": str(write_epoch_summary(run_root, plan) or ""),
    }
    produced["reports"] = [str(p) for p in publish_to_reports(run_root)]
    # The emulation-native per-epoch view, alongside the migrated one. It is a
    # separate file on purpose: the historical sheet keeps the schema the
    # archived reports key on, this one carries wall-clock fields that did not
    # exist under a simulator.
    try:
        native = summary_per_epoca.write(run_root)
        produced["epoch_summary"] = str(native["files"]["epoch_summary"])
        produced["epoch_validators"] = str(native["files"]["epoch_validators"])
        produced["epoch_report"] = str(native["files"]["report"])
    except Exception as exc:  # noqa: BLE001 - one view failing must not lose the other
        LOG.warning("the emulation-native epoch summary failed: %s", exc)
        produced["epoch_summary_error"] = str(exc)
    return produced
