"""``python -m experiments.cli`` — the single entry point.

Exit codes are part of the interface, so a shell script can branch on them:

    0  success
    1  configuration error       a descriptor, schema or topology is wrong
    2  environment unavailable   CORE, MultiChain, tc or privileges are missing
    3  runtime error             the network or a node failed while running
    4  incomplete data           the run produced too little to analyse
    5  analysis failed           the statistical pipeline could not complete

The parser is built here and nowhere else; the subcommand bodies live in
:mod:`experiments.runtime.cli` and :mod:`experiments.analysis.cli`, and the
analysis half is imported lazily so that starting a network does not pull in
numpy, scipy and matplotlib.
"""

from __future__ import annotations

import argparse
import logging
import sys

from .exit_codes import SUCCESS, ExperimentError
from .logging_setup import setup as setup_logging

LOG = logging.getLogger("experiments.cli")

EPILOG = """\
examples:
  # check the machine before anything else
  python3 -m experiments.cli env check --experiment experiments/configs/experiments/regional.yaml

  # resolve a descriptor without touching the system
  python3 -m experiments.cli validate --experiment experiments/configs/experiments/regional.yaml

  # see exactly what a run would do
  python3 -m experiments.cli experiment dry-run \\
      --experiment experiments/configs/experiments/regional.yaml --seed 12345

  # the real thing (needs root or passwordless sudo, and the MultiChain binaries)
  sudo -E python3 -m experiments.cli experiment run \\
      --experiment experiments/configs/experiments/intercontinental.yaml --seed 12345

  # analyse and report
  python3 -m experiments.cli analysis run --run-id run-regional-20260910T101500Z
  python3 -m experiments.cli report generate --run-id run-regional-20260910T101500Z
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="experiments.cli",
        description="Real-network emulation harness for the POESIA / wPoA MultiChain fork.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("--dry-run", action="store_true",
                        help="print privileged commands instead of running them")
    parser.add_argument(
        "--allow-fallback-without-core", dest="allow_fallback", action="store_true",
        help="authorise the netns fabric when CORE is unavailable. Without it, "
             "an 'auto' backend asks interactively and refuses to start when "
             "nobody can answer - a run must never change backend on its own.")
    parser.add_argument(
        "--yes", dest="assume_yes", action="store_true",
        help="answer yes to every question, the CORE fallback included. The "
             "blanket form of --allow-fallback-without-core, for scripts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- env ---------------------------------------------------------------
    env = subparsers.add_parser("env", help="inspect the machine")
    env_sub = env.add_subparsers(dest="subcommand", required=True)
    check = env_sub.add_parser("check", help="report tools, privileges and backends")
    check.add_argument("--experiment", help="also check this descriptor's requirements")
    check.set_defaults(handler="runtime:cmd_env_check")

    # -- validate ----------------------------------------------------------
    validate = subparsers.add_parser("validate", help="validate an experiment descriptor")
    validate.add_argument("--experiment", required=True)
    validate.add_argument("--seed", type=int)
    validate.set_defaults(handler="runtime:cmd_validate")

    # -- topology ----------------------------------------------------------
    topology = subparsers.add_parser("topology", help="topologies and network profiles")
    topology_sub = topology.add_subparsers(dest="subcommand", required=True)

    tvalidate = topology_sub.add_parser("validate", help="check a topology and its RTT matrix")
    tvalidate.add_argument("--topology", required=True)
    tvalidate.add_argument("--matrix", action="store_true", help="print the RTT matrix")
    tvalidate.add_argument("--allow-partitions", action="store_true",
                           help="do not treat a disconnected graph as an error")
    tvalidate.set_defaults(handler="runtime:cmd_topology_validate")

    tgenerate = topology_sub.add_parser("generate", help="export a topology")
    tgenerate.add_argument("--topology", required=True)
    tgenerate.add_argument("--format", choices=("gml", "json", "csv"), default="gml")
    tgenerate.add_argument("--output")
    tgenerate.set_defaults(handler="runtime:cmd_topology_generate")

    tprofiles = topology_sub.add_parser("profiles", help="list the network profiles")
    tprofiles.add_argument("--directory")
    tprofiles.set_defaults(handler="runtime:cmd_topology_profiles")

    # -- network -----------------------------------------------------------
    network = subparsers.add_parser("network", help="the emulated fabric")
    network_sub = network.add_subparsers(dest="subcommand", required=True)

    nstart = network_sub.add_parser("start", help="build the fabric and leave it up")
    nstart.add_argument("--experiment", required=True)
    nstart.add_argument("--run-id")
    nstart.add_argument("--backend", choices=("core", "netns", "docker", "auto"))
    nstart.set_defaults(handler="runtime:cmd_network_start")

    nstop = network_sub.add_parser("stop", help="tear the fabric down")
    nstop.add_argument("--run-id", required=True)
    nstop.set_defaults(handler="runtime:cmd_network_stop")

    napply = network_sub.add_parser("apply-profile", help="change conditions on a live fabric")
    napply.add_argument("--run-id", required=True)
    napply.add_argument("--profile", help="a configs/network-profiles/*.yaml file")
    napply.add_argument("--link", action="append",
                        help="restrict to 'source--target'; repeatable")
    napply.add_argument("--restore", action="store_true",
                        help="put every link back to the impairment its topology declares")
    napply.add_argument("--backend", choices=("core", "netns", "docker", "auto"))
    napply.set_defaults(handler="runtime:cmd_network_apply_profile")

    nstatus = network_sub.add_parser("status", help="what is currently built")
    nstatus.add_argument("--run-id", required=True)
    nstatus.set_defaults(handler="runtime:cmd_network_status")

    # -- multichain --------------------------------------------------------
    multichain = subparsers.add_parser("multichain", help="the chain itself")
    mc_sub = multichain.add_subparsers(dest="subcommand", required=True)

    minit = mc_sub.add_parser("initialize", help="seal params.dat for a run")
    minit.add_argument("--run-id", required=True)
    minit.set_defaults(handler="runtime:cmd_multichain_initialize")

    mtreasury = mc_sub.add_parser("treasury", help="generate the treasury address")
    mtreasury.add_argument("--experiment", required=True)
    mtreasury.add_argument("--chain-params")
    mtreasury.add_argument("--output")
    mtreasury.add_argument("--force", action="store_true")
    mtreasury.add_argument("--with-key", action="store_true",
                           help="also write the private key to an unversioned file")
    mtreasury.set_defaults(handler="runtime:cmd_multichain_treasury")

    # -- experiment --------------------------------------------------------
    experiment = subparsers.add_parser("experiment", help="run one")
    exp_sub = experiment.add_subparsers(dest="subcommand", required=True)

    for name, handler in (("run", "runtime:cmd_experiment_run"),
                          ("dry-run", "runtime:cmd_experiment_dry_run")):
        sub = exp_sub.add_parser(name)
        sub.add_argument("--experiment", required=True)
        sub.add_argument("--run-id")
        sub.add_argument("--seed", type=int)
        sub.add_argument("--duration", type=float, help="override the run length, in seconds")
        sub.add_argument("--backend", choices=("core", "netns", "docker", "auto"))
        if name == "run":
            sub.add_argument("--sample-interval", type=float, default=10.0,
                             help="seconds between two per-node collector samples")
            sub.add_argument("--explorer-interval", type=float, default=2.0,
                             help="seconds between two explorer polls of the admin "
                                  "node. Keep it well below target-block-time: the "
                                  "explorer walks every intermediate height, but a "
                                  "long interval makes every batch a gap fill.")
            sub.add_argument("--controller-tick", type=float, default=5.0,
                             help="seconds between two node-controller ticks")
            sub.add_argument("--force", action="store_true",
                             help="delete a previous attempt with the same run id")
        else:
            sub.add_argument("--show-commands", action="store_true",
                             help="include every privileged command in the output")
            sub.add_argument("--force", action="store_true",
                             help="plan the fabric even when preflight objects")
        sub.set_defaults(handler=handler)

    # -- metrics -----------------------------------------------------------
    metrics = subparsers.add_parser("metrics", help="extract metrics from a run")
    metrics_sub = metrics.add_subparsers(dest="subcommand", required=True)
    mcollect = metrics_sub.add_parser("collect")
    mcollect.add_argument("--run-id", required=True)
    mcollect.set_defaults(handler="runtime:cmd_metrics_collect")

    mschema = metrics_sub.add_parser("schema", help="print the metric catalogue")
    mschema.add_argument("--format", choices=("json", "markdown"), default="markdown")
    mschema.set_defaults(handler="analysis:cmd_metrics_schema")

    # -- analysis ----------------------------------------------------------
    analysis = subparsers.add_parser("analysis", help="statistics over a run")
    analysis_sub = analysis.add_subparsers(dest="subcommand", required=True)
    arun = analysis_sub.add_parser("run")
    arun.add_argument("--run-id", required=True)
    arun.add_argument("--results-root", help="analyse a tree outside experiments/results")
    arun.set_defaults(handler="analysis:cmd_analysis_run")

    acampaign = analysis_sub.add_parser("campaign", help="compare several runs")
    acampaign.add_argument("--run-id", action="append", required=True)
    acampaign.add_argument("--output")
    acampaign.set_defaults(handler="analysis:cmd_analysis_campaign")

    # -- report ------------------------------------------------------------
    report = subparsers.add_parser("report", help="generate the Markdown reports")
    report_sub = report.add_subparsers(dest="subcommand", required=True)
    rgen = report_sub.add_parser("generate")
    rgen.add_argument("--run-id", required=True)
    rgen.add_argument("--plots", action="store_true", default=True,
                      help="also produce the plots (default)")
    rgen.add_argument("--no-plots", dest="plots", action="store_false")
    rgen.set_defaults(handler="analysis:cmd_report_generate")

    # -- results -----------------------------------------------------------
    results = subparsers.add_parser("results", help="the results tree")
    results_sub = results.add_subparsers(dest="subcommand", required=True)
    rlist = results_sub.add_parser("list")
    rlist.set_defaults(handler="runtime:cmd_results_list")
    rclean = results_sub.add_parser("clean", help="remove leftover namespaces, never results")
    rclean.add_argument("--run-id")
    rclean.add_argument("--prefix", default="poesia")
    rclean.set_defaults(handler="runtime:cmd_results_clean")

    return parser


def _resolve(handler: str):
    module_name, function_name = handler.split(":")
    if module_name == "runtime":
        from .runtime import cli as module
    else:
        from .analysis import cli as module
    return getattr(module, function_name)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    try:
        return _resolve(args.handler)(args)
    except ExperimentError as exc:
        LOG.error("%s", exc)
        if getattr(exc, "hint", ""):
            LOG.error("hint: %s", exc.hint)
        return exc.exit_code
    except KeyboardInterrupt:
        LOG.warning("interrupted")
        return 3
    except BrokenPipeError:  # pragma: no cover - `| head` on a long report
        return SUCCESS


if __name__ == "__main__":
    sys.exit(main())
