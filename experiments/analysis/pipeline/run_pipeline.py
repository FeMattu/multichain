#!/usr/bin/env python3
"""Orchestrator of the three-phase analysis pipeline.

    python3 -m experiments.analysis.pipeline.run_pipeline --phase all
    python3 -m experiments.analysis.pipeline.run_pipeline --phase 2 --only regional
    python3 -m experiments.analysis.pipeline.run_pipeline --phase 3 --no-campaign

Every phase is re-runnable on its own: phase 2 reads phase1/, phase 3 reads
phase2/ (plus phase1/config.csv for the config tab).

Both run layouts are discovered, chosen by inspection rather than by a flag:
runs produced by this harness (`<root>/<run-id>/` with manifest.json and
raw/metrics/) and the archived Shadow campaign
(`<root>/runN-tbt-Ts/<level>/run/metrics/`). Defaults point at
experiments/results; --root, --out and --config move them, which is how the
archived campaign is re-analysed after shadow/ was removed - see
docs/migration-from-shadow.md.

Legacy directories whose name does not match runN-tbt-Ts are ignored by
discovery and listed in the log.
"""

import argparse
import logging
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
from . import common as C
from . import phase1_collect, phase2_aggregate, phase3_analyze

LOG = logging.getLogger("pipeline")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", default="all", choices=("1", "2", "3", "all"))
    ap.add_argument("--root", default=None,
                    help="runs to analyse (default: the experiments results root)")
    ap.add_argument("--out", default=None,
                    help="output root (default: <results>/_pipeline)")
    ap.add_argument("--config", default=None,
                    help="config root holding levels/*.json, for legacy archives only")
    ap.add_argument("--only", default="", help="substring filter on <run>/<area>")
    ap.add_argument("--no-campaign", action="store_true", help="skip the campaign-level files after phase 3")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    from ...paths import CONFIG_ROOT, results_root

    root = Path(args.root) if args.root else results_root()
    out = Path(args.out) if args.out else (results_root() / "_pipeline")
    cfg = Path(args.config) if args.config else CONFIG_ROOT
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s",
                        handlers=[logging.FileHandler(out / "pipeline.log", mode="a", encoding="utf-8"),
                                  logging.StreamHandler(sys.stdout)])
    LOG.info("pipeline phase=%s root=%s out=%s only=%r", args.phase, root, out, args.only)
    phases = ["1", "2", "3"] if args.phase == "all" else [args.phase]
    rc = 0
    if "1" in phases:
        # Only meaningful for the legacy archive: a native run directory is
        # named after its run id and is discovered by its manifest, so warning
        # that it does not match runN-tbt-Ts would be noise.
        from ..compatibility.run_adapter import is_native_run

        ignored = [p.name for p in sorted(root.iterdir())
                   if p.is_dir() and not C.RUN_DIR_RE.match(p.name) and not is_native_run(p)]
        if ignored:
            LOG.warning("directories ignored by discovery (name not runN-tbt-Ts): %s", ", ".join(ignored))
        rc |= phase1_collect.main(["--root", str(root), "--out", str(out), "--config-root", str(cfg), "--only", args.only])
    if "2" in phases:
        rc |= phase2_aggregate.main(["--out", str(out), "--only", args.only])
    if "3" in phases:
        a = ["--out", str(out), "--only", args.only]
        if not args.no_campaign and not args.only:
            a.append("--campaign")
        rc |= phase3_analyze.main(a)
    return rc


if __name__ == "__main__":
    sys.exit(main())
