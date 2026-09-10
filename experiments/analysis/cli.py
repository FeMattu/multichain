"""Analysis subcommands: metrics schema, analysis, campaign, reports.

Imported lazily by :mod:`experiments.cli`, because everything below pulls in
numpy, scipy, pandas and matplotlib, and none of those has any business being
a dependency of starting a network.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ..exit_codes import SUCCESS, AnalysisFailed, ConfigError, IncompleteData
from ..logging_setup import setup as setup_logging
from ..paths import results_root, run_dir
from ..plan import build_plan

LOG = logging.getLogger("experiments.analysis.cli")


def _run_root(run_id: str) -> Path:
    root = run_dir(run_id)
    if not root.is_dir():
        raise ConfigError(
            "no run directory for %r under %s" % (run_id, results_root()),
            hint="list them with 'experiments.cli results list'",
        )
    return root


def _plan_of(root: Path):
    descriptor = root / "config" / "experiment.yaml"
    if not descriptor.is_file():
        raise IncompleteData(
            "%s holds no config/experiment.yaml, so the run cannot be described"
            % root,
            hint="only runs produced by 'experiment run' carry their own configuration",
        )
    return build_plan(descriptor)


# ---------------------------------------------------------------------------
# metrics schema
# ---------------------------------------------------------------------------

def cmd_metrics_schema(args) -> int:
    from ..metrics import catalogue, schema_report

    if args.format == "json":
        print(json.dumps(catalogue.as_dict(), indent=2))
    else:
        print(schema_report.render())
    return SUCCESS


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------

def cmd_analysis_run(args) -> int:
    """Extract the metrics of one run and analyse them."""
    root = Path(args.results_root) if args.results_root else _run_root(args.run_id)
    setup_logging(args.verbose, root / "run.log")
    plan = _plan_of(root)

    from ..metrics.extractors import extract_all

    produced = extract_all(root, plan)
    problems = produced.get("validation", {}).get("problems", [])
    for problem in problems:
        LOG.error("schema: %s", problem)

    summary = {
        "run_id": args.run_id,
        "tables": produced.get("tables", {}),
        "historical": produced.get("historical", {}),
        "schema_report": produced.get("schema_report", ""),
        "schema_problems": problems,
    }
    print(json.dumps(summary, indent=2, default=str))

    if problems:
        return AnalysisFailed.exit_code
    if not produced.get("tables"):
        raise IncompleteData("no metric table could be produced from %s" % root)
    return SUCCESS


def cmd_analysis_campaign(args) -> int:
    """Compare several runs in one campaign view."""
    roots = [_run_root(run_id) for run_id in args.run_id]
    output = Path(args.output) if args.output else results_root() / "_campaign"
    output.mkdir(parents=True, exist_ok=True)
    setup_logging(args.verbose, output / "campaign.log")

    from ..analysis.compatibility.run_adapter import write_compat_inputs
    from ..analysis.pipeline import run_pipeline

    for root in roots:
        write_compat_inputs(root, _plan_of(root))

    parents = {root.parent for root in roots}
    if len(parents) != 1:
        raise ConfigError(
            "the runs live under different roots (%s); the campaign view needs one"
            % ", ".join(str(p) for p in sorted(parents))
        )
    rc = run_pipeline.main([
        "--phase", "all", "--root", str(parents.pop()), "--out", str(output),
    ])
    print(json.dumps({"runs": [r.name for r in roots], "output": str(output),
                      "pipeline_exit_code": rc}, indent=2))
    return SUCCESS if rc == 0 else AnalysisFailed.exit_code


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------

def cmd_report_generate(args) -> int:
    root = _run_root(args.run_id)
    setup_logging(args.verbose, root / "run.log")
    plan = _plan_of(root)

    from .reporting import generate_reports

    produced = generate_reports(root, plan, with_plots=args.plots)
    print(json.dumps(produced, indent=2, default=str))
    if not produced.get("reports"):
        return AnalysisFailed.exit_code
    return SUCCESS
