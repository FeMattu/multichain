#!/usr/bin/env python3
"""Orchestrator of the three-phase Shadow pipeline.

    python3 tools/pipeline/run_pipeline.py --phase all              # 1 -> 2 -> 3 -> campaign
    python3 tools/pipeline/run_pipeline.py --phase 2 --only run6    # one phase, filtered
    python3 tools/pipeline/run_pipeline.py --phase 3 --no-campaign

Every phase is re-runnable on its own: phase 2 reads phase1/, phase 3 reads
phase2/ (plus phase1/config.csv for the config tab). Paths default to the
layout of the shadow/ tree: --root esperimenti, --out risultati, --config config.
Runs whose directory name does not match runN-tbt-Ts (e.g. the empty
run7-tbt7s) are ignored by discovery and listed in the log.
"""

import argparse
import logging
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from pipeline import common as C  # noqa: E402
from pipeline import phase1_collect, phase2_aggregate, phase3_analyze  # noqa: E402

LOG = logging.getLogger("pipeline")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", default="all", choices=("1", "2", "3", "all"))
    ap.add_argument("--root", default=None, help="archived campaign (default: <shadow>/esperimenti)")
    ap.add_argument("--out", default=None, help="output root (default: <shadow>/risultati)")
    ap.add_argument("--config", default=None, help="shadow/config (default: <shadow>/config)")
    ap.add_argument("--only", default="", help="substring filter on <run>/<area>")
    ap.add_argument("--no-campaign", action="store_true", help="skip the campaign-level files after phase 3")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    shadow = HERE.parent.parent
    root = Path(args.root) if args.root else shadow / "esperimenti"
    out = Path(args.out) if args.out else shadow / "risultati"
    cfg = Path(args.config) if args.config else shadow / "config"
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s",
                        handlers=[logging.FileHandler(out / "pipeline.log", mode="a", encoding="utf-8"),
                                  logging.StreamHandler(sys.stdout)])
    LOG.info("pipeline phase=%s root=%s out=%s only=%r", args.phase, root, out, args.only)
    phases = ["1", "2", "3"] if args.phase == "all" else [args.phase]
    rc = 0
    if "1" in phases:
        ignored = [p.name for p in sorted(root.iterdir()) if p.is_dir() and not C.RUN_DIR_RE.match(p.name)]
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
