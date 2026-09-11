"""Runtime subcommands: environment, topology, network, multichain, experiment.

Kept separate from :mod:`experiments.cli`, which only dispatches, so the
runtime can be driven from a script without importing the analysis stack —
which pulls in numpy, scipy and matplotlib and has no business being a
dependency of starting a network.
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..chain_params import ChainParams
from ..exit_codes import (
    SUCCESS,
    ConfigError,
    EnvironmentError_,
    ExperimentError,
    IncompleteData,
    RuntimeFailure,
)
from ..logging_setup import setup as setup_logging
from ..paths import ROLES_ROOT, results_root, run_dir
from ..plan import build_plan
from ..seeds import derive
from ..topology import exporters
from ..topology.generator import build_topology, load_profiles, profile_from_file
from ..topology.validator import format_matrix, rtt_between, validate_topology
from .collectors import logs as log_collector
from .collectors import system as system_collector
from .collectors.sampler import Sampler
from .fabric import available_backends, make_fabric
from .fabric.netns import NetnsFabric
from .multichain import install
from .multichain import treasury as treasury_mod
from .netem import apply as netem_apply
from .netem import clear as netem_clear
from .manifest import Manifest
from .session import Session
from .shell import Runner, which

LOG = logging.getLogger("experiments.cli")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _runner(args) -> Runner:
    return Runner(dry_run=getattr(args, "dry_run", False))


def _fabric_kwargs(args) -> dict:
    """Consent settings every fabric-building command shares."""
    return {"allow_fallback": getattr(args, "allow_fallback", False),
            "assume_yes": getattr(args, "assume_yes", False)}


def _default_run_id(name: str) -> str:
    """``run-<name>-<UTC timestamp>``: sortable, unique, self-describing."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "run-%s-%s" % (name, stamp)


def _resolve_run_root(run_id: str) -> Path:
    root = run_dir(run_id)
    if not root.is_dir():
        raise ConfigError(
            "no run directory for %r under %s" % (run_id, results_root()),
            hint="list the runs with 'experiments.cli results list'",
        )
    return root


def _print(payload, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    elif isinstance(payload, str):
        print(payload)
    else:
        print(json.dumps(payload, indent=2, default=str))


# ---------------------------------------------------------------------------
# env
# ---------------------------------------------------------------------------

def cmd_env_check(args) -> int:
    """Report everything the harness needs, and what is only optional."""
    runner = _runner(args)
    mandatory = {}
    for tool in ("ip", "tc"):
        mandatory[tool] = which(tool) or ""
    optional = {}
    for tool in ("nsenter", "curl", "sudo", "core-daemon", "docker", "python3"):
        optional[tool] = which(tool) or ""

    report = {
        "system": system_collector.snapshot(results_root()),
        "tools_mandatory": mandatory,
        "tools_optional": optional,
        "privileges": {
            "euid_is_root": runner.is_root,
            "sudo": runner.sudo or "",
        },
        "python_modules": _module_report(),
    }

    if getattr(args, "experiment", None):
        plan = build_plan(args.experiment)
        report["experiment"] = plan.summary()
        report["multichain"] = {
            name: info.as_dict() for name, info in install.resolve_all(plan.multichain).items()
        }
        report["backends"] = available_backends(plan, runner, run_root=results_root())
        report["host_headroom"] = system_collector.enough_headroom(
            len(plan.enabled_nodes), results_root()
        )

    _print(report, as_json=True)

    missing = [name for name, path in mandatory.items() if not path]
    if missing:
        LOG.error("missing mandatory tools: %s", ", ".join(missing))
        return EnvironmentError_.exit_code
    if getattr(args, "experiment", None):
        if any(not info["found"] for info in report["multichain"].values()):
            LOG.error("the MultiChain binaries were not found; see the report above")
            return EnvironmentError_.exit_code
        if all(problems for problems in report["backends"].values()):
            LOG.error("no fabric backend can run here; see the report above")
            return EnvironmentError_.exit_code
    return SUCCESS


def _module_report() -> dict:
    out = {}
    for module in ("yaml", "jsonschema", "numpy", "scipy", "pandas", "matplotlib",
                   "networkx", "openpyxl", "core"):
        try:
            imported = __import__(module)
            out[module] = getattr(imported, "__version__", "present")
        except ImportError:
            out[module] = ""
    return out


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def _validate_every_descriptor(args) -> int:
    """Every shipped descriptor, so one broken config fails the whole check.

    Validating them one at a time is how a descriptor that nobody runs drifts
    until the day somebody runs it.
    """
    from ..paths import CONFIG_ROOT

    descriptors = sorted((CONFIG_ROOT / "experiments").glob("*.yaml"))
    if not descriptors:
        LOG.error("no descriptor found under %s", CONFIG_ROOT / "experiments")
        return ConfigError.exit_code
    results, failed = [], 0
    for path in descriptors:
        try:
            plan = build_plan(path, seed_override=args.seed)
        except Exception as exc:  # noqa: BLE001 - the point is to report, not to stop
            failed += 1
            LOG.error("%s does not resolve: %s", path.name, exc)
            results.append({"descriptor": path.name, "ok": False, "error": str(exc)})
            continue
        report = validate_topology(plan.topology)
        warning = plan.duration_warning()
        if warning:
            LOG.warning("%s schedule: %s", path.name, warning)
        if report.errors:
            failed += 1
            for error in report.errors:
                LOG.error("%s topology: %s", path.name, error)
        results.append({
            "descriptor": path.name, "ok": not report.errors,
            "nodes": len(plan.enabled_nodes), "backend": plan.fabric.backend,
            "measurable_blocks": plan.measurable_blocks(),
            "warnings": report.warnings + ([warning] if warning else []),
        })
    _print({"descriptors": len(descriptors), "failed": failed,
            "results": results}, as_json=True)
    return ConfigError.exit_code if failed else 0


def cmd_validate(args) -> int:
    """Resolve a descriptor end to end without touching the system."""
    if getattr(args, "all", False):
        return _validate_every_descriptor(args)
    plan = build_plan(args.experiment, seed_override=args.seed)
    report = validate_topology(plan.topology)
    summary = plan.summary()
    summary["topology_max_rtt_ms"] = report.max_rtt_ms
    summary["topology_max_rtt_pair"] = report.max_rtt_pair
    summary["miner_worst_rtt_ms"] = rtt_between(
        plan.topology, [n.location for n in plan.miners if n.location]
    )
    summary["warnings"] = report.warnings
    summary["errors"] = report.errors
    summary["duration_is_explicit"] = plan.schedule.duration_is_explicit
    summary["auto_duration_s"] = plan.schedule.auto_duration_s
    _print(summary, as_json=True)
    too_short = plan.duration_warning()
    if too_short:
        LOG.warning("schedule: %s", too_short)
    for warning in report.warnings:
        LOG.warning("topology: %s", warning)
    if report.errors:
        for error in report.errors:
            LOG.error("topology: %s", error)
        return ConfigError.exit_code
    LOG.info("%s is valid", args.experiment)
    return SUCCESS


# ---------------------------------------------------------------------------
# topology
# ---------------------------------------------------------------------------

def cmd_topology_validate(args) -> int:
    topology = build_topology(args.topology)
    report = validate_topology(topology, require_connected=not args.allow_partitions)
    print("topology %s: %d locations, %d links (%d enabled)" % (
        topology.name, len(topology.locations), len(topology.links),
        sum(1 for _ in topology.enabled_links())))
    print("components: %d" % len(report.components))
    print("worst end-to-end RTT: %.3f ms%s" % (
        report.max_rtt_ms,
        " (%s)" % "-".join(report.max_rtt_pair) if report.max_rtt_pair else ""))
    for warning in report.warnings:
        print("warning: %s" % warning)
    for error in report.errors:
        print("error: %s" % error)
    if args.matrix:
        print()
        print(format_matrix(report, topology.location_ids))
    return SUCCESS if report.ok else ConfigError.exit_code


def cmd_topology_generate(args) -> int:
    topology = build_topology(args.topology)
    output = Path(args.output) if args.output else None
    if args.format == "gml":
        output = output or (Path("experiments/topology/generated") / (topology.name + ".gml"))
        exporters.write_gml(topology, output)
    elif args.format == "json":
        output = output or (Path("experiments/topology/generated") / (topology.name + ".json"))
        exporters.write_realized_json(topology, output)
    else:
        output = output or (Path("experiments/topology/generated") / (topology.name + "-edges.csv"))
        exporters.write_edges_csv(topology, output)
    print("wrote %s" % output)
    return SUCCESS


def cmd_topology_profiles(args) -> int:
    profiles = load_profiles(args.directory)
    rows = []
    for name, profile in sorted(profiles.items()):
        rows.append({
            "name": name, "direction": profile.direction,
            "forward_delay_ms": profile.forward.delay.mean_ms,
            "forward_jitter_ms": profile.forward.delay.jitter_ms,
            "forward_loss_percent": profile.forward.loss.percent,
            "forward_bandwidth_mbps": profile.forward.bandwidth.mbps,
            "reverse_delay_ms": profile.reverse.delay.mean_ms,
            "reverse_loss_percent": profile.reverse.loss.percent,
            "source": profile.source,
        })
    _print(rows, as_json=True)
    return SUCCESS


# ---------------------------------------------------------------------------
# network
# ---------------------------------------------------------------------------

def cmd_network_start(args) -> int:
    """Build the fabric and leave it up, without starting MultiChain."""
    plan = build_plan(args.experiment, backend_override=args.backend)
    run_id = args.run_id or _default_run_id(plan.name)
    root = run_dir(run_id)
    root.mkdir(parents=True, exist_ok=True)
    setup_logging(args.verbose, root / "run.log")
    runner = _runner(args)
    binaries = install.resolve_all(plan.multichain)
    manifest = Manifest.create(run_id, root, plan, backend=plan.fabric.backend,
                               binaries=binaries)
    fabric = make_fabric(plan, runner, run_root=root, backend=args.backend,
                         **_fabric_kwargs(args))
    fabric.build()
    report = fabric.verify_connectivity()
    if not report["ok"]:
        LOG.warning("%d of %d node pairs cannot reach each other",
                    len(report["failures"]), report["checked"])
    exporters.write_realized_json(
        plan.topology, root / "runtime" / "topology-realized.json",
        extra={"fabric": fabric.realized()},
    )
    manifest.set(fabric_backend=fabric.name, status="network-up",
                 connectivity=report)
    manifest.phase("network-start", "ok", nodes=len(fabric.nodes), links=len(fabric.links))
    print("run id: %s" % run_id)
    print("network up: %d nodes, %d links, backend %s" % (
        len(fabric.nodes), len(fabric.links), fabric.name))
    return SUCCESS


def cmd_network_stop(args) -> int:
    """Tear a fabric down by run id, from any process."""
    root = _resolve_run_root(args.run_id)
    setup_logging(args.verbose, root / "run.log")
    runner = _runner(args)
    manifest = Manifest.load(root)
    prefix = manifest.data.get("fabric_namespace_prefix") or _prefix_from_manifest(manifest)
    removed = NetnsFabric.destroy_session(runner, prefix)
    netem_clear.clear_stray_qdiscs(runner)
    manifest.phase("network-stop", "ok", objects_removed=removed)
    manifest.finish(manifest.data.get("status", "stopped"))
    print("removed %d objects for session prefix %r" % (removed, prefix))
    return SUCCESS


def _prefix_from_manifest(manifest: Manifest) -> str:
    descriptor = manifest.data.get("descriptor")
    if descriptor and Path(descriptor).is_file():
        try:
            return build_plan(descriptor).fabric.namespace_prefix
        except ExperimentError:
            pass
    return "poesia"


def cmd_network_apply_profile(args) -> int:
    """Change conditions on a live fabric."""
    root = _resolve_run_root(args.run_id)
    setup_logging(args.verbose, root / "run.log")
    plan = build_plan(root / "config" / "experiment.yaml")
    runner = _runner(args)
    fabric = make_fabric(plan, runner, run_root=root, backend=args.backend,
                         **_fabric_kwargs(args))
    realized = root / "runtime" / "topology-realized.json"
    if not realized.is_file():
        raise RuntimeFailure(
            "no realised topology for run %s: the fabric was never built" % args.run_id
        )
    _rehydrate(fabric, json.loads(realized.read_text(encoding="utf-8")), plan)
    links = _parse_links(args.link)
    if args.restore:
        event = netem_apply.restore(fabric, plan.topology, root)
    else:
        profile = profile_from_file(args.profile)
        event = netem_apply.apply_profile(fabric, profile, root, links=links)
    _print(event, as_json=True)
    return SUCCESS


def _parse_links(values) -> list[tuple[str, str]] | None:
    if not values:
        return None
    out = []
    for value in values:
        if "--" not in value:
            raise ConfigError("--link wants 'source--target', got %r" % value)
        source, target = value.split("--", 1)
        out.append((source.strip(), target.strip()))
    return out


def _rehydrate(fabric, realized: dict, plan) -> None:
    """Rebuild the fabric's in-memory link records from what it wrote to disk.

    Applying a profile to a running fabric happens from a different process
    than the one that built it, so the endpoint names have to come from the
    run directory rather than from memory.
    """
    from .fabric.base import LinkEndpoint, RealizedLink, RealizedNode

    payload = realized.get("fabric") or {}
    for entry in payload.get("nodes", []):
        fabric.nodes[entry["id"]] = RealizedNode(**entry)
    declared = {
        (link.source, link.target): (link.impairment_forward, link.impairment_reverse)
        for link in plan.topology.links
    }
    for entry in payload.get("links", []):
        forward, reverse = declared.get((entry["source"], entry["target"]), (None, None))
        fabric.links.append(RealizedLink(
            source=entry["source"], target=entry["target"], kind=entry["kind"],
            profile=entry.get("profile", ""), subnet=entry.get("subnet", ""),
            index=entry.get("index", 0),
            a=LinkEndpoint(entry["a"]["namespace"], entry["a"]["interface"],
                           entry["a"].get("address", ""), forward),
            b=LinkEndpoint(entry["b"]["namespace"], entry["b"]["interface"],
                           entry["b"].get("address", ""), reverse),
        ))


def cmd_network_status(args) -> int:
    root = _resolve_run_root(args.run_id)
    realized = root / "runtime" / "topology-realized.json"
    payload = json.loads(realized.read_text(encoding="utf-8")) if realized.is_file() else {}
    runner = _runner(args)
    live = NetnsFabric.existing_namespaces(runner, "poesia")
    _print({"run_id": args.run_id, "realized": payload.get("fabric", {}),
            "live_namespaces": live}, as_json=True)
    return SUCCESS


# ---------------------------------------------------------------------------
# multichain
# ---------------------------------------------------------------------------

def cmd_multichain_treasury(args) -> int:
    plan = build_plan(args.experiment) if args.experiment else None
    chain_params = (plan.chain_params if plan
                    else ChainParams.load(args.chain_params))
    binaries = install.require_all(plan.multichain) if plan else None
    if binaries is None:
        raise ConfigError("--experiment is required to locate the MultiChain binaries")
    out = Path(args.output) if args.output else plan.multichain.treasury_file
    treasury = treasury_mod.generate(
        binaries["multichain-util"].path, binaries["multichaind"].path,
        binaries["multichain-cli"].path, chain_params, out,
        with_key=args.with_key, force=args.force,
    )
    _print(treasury.as_dict(), as_json=True)
    return SUCCESS


def cmd_multichain_initialize(args) -> int:
    """Seal params.dat for an existing run directory."""
    root = _resolve_run_root(args.run_id)
    setup_logging(args.verbose, root / "run.log")
    plan = build_plan(root / "config" / "experiment.yaml")
    runner = _runner(args)
    binaries = install.require_all(plan.multichain)
    session = Session(plan=plan, run_id=args.run_id, run_root=root, runner=runner,
                      roles_dir=ROLES_ROOT, binaries=binaries)
    session.manifest = Manifest.load(root)
    session.initialize_chain()
    _print(session.init_result.as_dict(), as_json=True)
    return SUCCESS


# ---------------------------------------------------------------------------
# experiment
# ---------------------------------------------------------------------------

def cmd_experiment_dry_run(args) -> int:
    """Show everything a real run would do, without doing any of it."""
    plan = build_plan(args.experiment, seed_override=args.seed,
                      duration_override=args.duration, backend_override=args.backend)
    runner = Runner(dry_run=True)
    run_id = args.run_id or _default_run_id(plan.name)
    root = run_dir(run_id)
    binaries = install.resolve_all(plan.multichain)

    fabric = NetnsFabric(plan, runner, run_root=root)
    problems = fabric.preflight()
    if not problems or args.force:
        fabric.build()

    schedule = plan.schedule
    timeline = [
        ("%8.0fs" % 0, "admin", "multichaind: genesis, premine, input streams"),
        ("%8.0fs" % schedule.first_launch_s, "all but admin",
         "first launch: publish the wallet address, then exit"),
        ("%8.0fs" % schedule.grant_s, "admin",
         "grant permissions, create wpoa-weights (closed) and the application stream, "
         "delegate high1, distribute GAS"),
        ("%8.0fs" % schedule.join_s, "all but admin", "multichaind: join and sync"),
        ("%8.0fs" % schedule.register_s, "ca, miners, companies",
         "certified ESG scores; cluster membership"),
        ("%8.0fs" % schedule.traffic_s, "companies, miners, admin",
         "supply-chain traffic, reconciliation, GAS refill, epoch sampling"),
        ("  height=%d" % plan.setup_first_blocks, "all",
         "wPoA takes over from native PoA: the measurement window opens"),
        ("%8.0fs" % schedule.snapshot_s, "admin", "final chain snapshot"),
        ("%8.0fs" % schedule.duration_s, "harness", "stop, clean up, archive"),
    ]

    report = {
        "run_id": run_id,
        "run_root": str(root),
        "plan": plan.summary(),
        "fabric": {
            "backend_preflight": available_backends(plan, runner, run_root=root),
            "commands_that_would_run": len(runner.recorded),
            "namespaces": sorted({c[c.index("exec") + 1] for c in runner.recorded
                                  if "exec" in c}),
            "links": len(fabric.links),
        },
        "multichain": {name: info.as_dict() for name, info in binaries.items()},
        "timeline": [{"at": at, "who": who, "what": what} for at, who, what in timeline],
        "host_headroom": system_collector.enough_headroom(len(plan.enabled_nodes), root),
        "seeds": {purpose: derive(plan.seed, purpose)
                  for purpose in ("esg", "workload", "netem", "node_seed", "placement")},
    }
    if problems:
        report["fabric"]["preflight_problems"] = problems

    if args.show_commands:
        report["commands"] = [" ".join(c) for c in runner.recorded]

    _print(report, as_json=True)
    print("\nTimeline", file=sys.stderr)
    for at, who, what in timeline:
        print("  %-12s %-24s %s" % (at, who, what), file=sys.stderr)
    return SUCCESS


def cmd_experiment_run(args) -> int:
    """The real thing: build, bootstrap, measure, collect, tear down."""
    plan = build_plan(args.experiment, seed_override=args.seed,
                      duration_override=args.duration, backend_override=args.backend)
    run_id = args.run_id or _default_run_id(plan.name)
    root = run_dir(run_id)
    if root.exists() and args.force:
        LOG.warning("removing the previous attempt at %s", root)
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    setup_logging(args.verbose, root / "run.log")

    runner = _runner(args)
    binaries = install.require_all(plan.multichain)
    for warning in system_collector.enough_headroom(len(plan.enabled_nodes), root):
        LOG.warning("host: %s", warning)

    exit_code = SUCCESS
    sampler = None
    with Session(plan=plan, run_id=run_id, run_root=root, runner=runner,
                 roles_dir=ROLES_ROOT, binaries=binaries,
                 controller_tick_s=getattr(args, "controller_tick", 5.0)) as session:
        session.prepare_directories()
        session.snapshot_config()
        session.manifest = Manifest.create(
            run_id, root, plan, backend=plan.fabric.backend, binaries=binaries,
            extra={"system_at_start": system_collector.snapshot(root)},
        )
        try:
            session.validate()
            session.manifest.phase("validate", "ok")
            session.build_network(backend=args.backend, **_fabric_kwargs(args))
            session.manifest.set(fabric_backend=session.fabric.name)
            session.manifest.phase("network", "ok",
                                   nodes=len(session.fabric.nodes),
                                   links=len(session.fabric.links))
            session.initialize_chain()
            session.manifest.phase("initialize", "ok")

            sampler = Sampler(
                run_id=run_id, scenario=plan.scenario, seed=plan.seed,
                nodes=plan.enabled_nodes, clients=session.clients,
                registry=session.registry, out_dir=root / "raw" / "observations",
                interval_s=args.sample_interval,
                run_root=root, explorer_node=plan.admin.id,
                explorer_interval_s=args.explorer_interval,
                target_block_time_s=plan.target_block_time,
                explorer_mode=getattr(args, "explorer_mode", "backfill"),
            )
            sampler.start()
            session.sampler = sampler
            session.manifest.set(rpc_collector_mode=sampler.explorer_mode)

            health_report = session.run_schedule()
            session.manifest.set(health=health_report)
            session.manifest.phase("measure", "ok")
        except KeyboardInterrupt:
            session.interrupted = True
            LOG.warning("interrupted by the user")
            exit_code = RuntimeFailure.exit_code
        except ExperimentError as exc:
            LOG.error("%s", exc)
            if getattr(exc, "hint", ""):
                LOG.error("hint: %s", exc.hint)
            session.manifest.error(str(exc), phase="run")
            exit_code = exc.exit_code
        finally:
            if sampler is not None:
                sampler.stop()
                session.manifest.set(sampler=sampler.summary())
            _collect(session, plan, root, run_id)

    print("run id: %s" % run_id)
    print("results: %s" % root)
    return exit_code


def _collect(session: Session, plan, root: Path, run_id: str) -> None:
    """Archive logs and record what the run produced. Never raises."""
    try:
        found = log_collector.discover(
            root, [n.id for n in plan.enabled_nodes], plan.multichain.chain
        )
        archived = log_collector.archive(root, found)
        summary = log_collector.summarise(archived)
        if session.manifest:
            session.manifest.set(
                logs=summary,
                system_at_end=system_collector.snapshot(root),
            )
        LOG.info("archived %d log files (%.1f MiB)",
                 summary["files"], summary["total_bytes"] / 1024 ** 2)
    except Exception as exc:  # noqa: BLE001 - collection must not mask the run's own error
        LOG.error("log collection failed: %s", exc)
        if session.manifest:
            session.manifest.error("log collection failed: %s" % exc, phase="collect")
    del run_id


def cmd_metrics_collect(args) -> int:
    """Re-run collection over an existing run directory."""
    root = _resolve_run_root(args.run_id)
    setup_logging(args.verbose, root / "run.log")
    plan = build_plan(root / "config" / "experiment.yaml")
    found = log_collector.discover(root, [n.id for n in plan.enabled_nodes],
                                   plan.multichain.chain)
    archived = log_collector.archive(root, found)
    summary = log_collector.summarise(archived)
    from ..metrics.extractors import extract_all

    produced = extract_all(root, plan)
    manifest = Manifest.load(root)
    manifest.set(logs=summary, metrics=produced)
    _print({"logs": summary, "metrics": produced}, as_json=True)
    if not produced.get("tables"):
        raise IncompleteData("no metric table could be produced from %s" % root)
    return SUCCESS


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------

def cmd_results_list(args) -> int:
    root = results_root()
    rows = []
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            manifest = entry / "manifest.json"
            if not manifest.is_file():
                continue
            data = json.loads(manifest.read_text(encoding="utf-8"))
            rows.append({
                "run_id": data.get("run_id", entry.name),
                "scenario": data.get("scenario", ""),
                "status": data.get("status", ""),
                "backend": data.get("fabric_backend", ""),
                "nodes": data.get("node_count", ""),
                "started_at": data.get("started_at", ""),
                "duration_s": data.get("duration_wallclock_s", ""),
            })
    _print(rows, as_json=True)
    return SUCCESS


def cmd_results_clean(args) -> int:
    """Remove the fabric of a run, never its results."""
    runner = _runner(args)
    prefix = args.prefix
    removed = NetnsFabric.destroy_session(runner, prefix)
    stray = netem_clear.clear_stray_qdiscs(runner)
    print("removed %d namespaces/objects, cleared %d stray qdiscs" % (removed, stray))
    if args.run_id:
        root = _resolve_run_root(args.run_id)
        print("results left untouched at %s" % root)
    return SUCCESS
