"""Producing the Markdown reports and the plots of a single run.

The report file names are the historical ones — ``report_generale.md``,
``report_confronto.md``, ``report_asse_livello.md``, ``report_asse_tbt.md``,
``metrics_schema_report.md`` — because they are what the thesis and every
archived analysis refer to. What they contain has changed in one respect and
the reports say so at the top: the numbers now come from real MultiChain
processes on an emulated network, measured in wall-clock time, not from a
discrete-event simulation of one.

Each report declares, per section, whether the quantity is observed, derived
or unavailable, and every section that has no data says so rather than being
omitted — a missing section reads as an oversight, an explicit "no data" reads
as a fact.
"""

from __future__ import annotations

import csv
import json
import logging
import statistics
from datetime import datetime, timezone
from pathlib import Path

LOG = logging.getLogger("experiments.analysis.reporting")

REPORT_NAMES = [
    "report_generale.md",
    "report_confronto.md",
    "report_asse_livello.md",
    "report_asse_tbt.md",
    "metrics_schema_report.md",
]

PROVENANCE_BANNER = """\
> **Emulation, not simulation.** Every number below was produced by real
> `multichaind` processes running on an emulated network (backend `%(backend)s`),
> measured against the wall clock. The archived Shadow campaign measured
> *simulated* time. The two are not directly comparable — see
> [docs/metrics.md](../../../docs/metrics.md), "Three clocks".
"""


def _read_csv(path: Path) -> list:
    path = Path(path)
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _numbers(rows: list, column: str) -> list:
    out = []
    for row in rows:
        value = row.get(column, "")
        if value in ("", None):
            continue
        try:
            out.append(float(value))
        except (TypeError, ValueError):
            continue
    return out


def _stats(values: list) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 4),
        "median": round(statistics.median(values), 4),
        "sd": round(statistics.pstdev(values), 4) if len(values) > 1 else 0.0,
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def _table(headers: list, rows: list) -> list:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return out


def _no_data(what: str, why: str) -> list:
    return ["", "**No data.** %s %s" % (what, why), ""]


def generate_reports(run_root: Path, plan, *, with_plots: bool = True) -> dict:
    """Write every report for one run. Returns what was produced."""
    run_root = Path(run_root)
    reports_dir = run_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(run_root)

    produced: dict = {"reports": [], "plots": []}
    context = _gather(run_root, plan, manifest)

    for writer, name in (
        (_report_generale, "report_generale.md"),
        (_report_confronto, "report_confronto.md"),
        (_report_asse_livello, "report_asse_livello.md"),
        (_report_asse_tbt, "report_asse_tbt.md"),
    ):
        path = reports_dir / name
        path.write_text("\n".join(writer(context)) + "\n", encoding="utf-8")
        produced["reports"].append(str(path))

    from ..metrics.schema_report import write as write_schema

    produced["reports"].append(str(write_schema(
        reports_dir / "metrics_schema_report.md", metrics_dir=run_root / "metrics")))

    if with_plots:
        from .plots import generate as generate_plots

        figures = generate_plots(run_root, plan)
        produced["plots"] = figures["produced"]
        produced["plots_skipped"] = figures["skipped"]
        context["plots"] = figures
        # The figure inventory goes into the general report, so a reader sees
        # what was drawn AND what was not, with the reason.
        path = reports_dir / "report_generale.md"
        path.write_text(path.read_text(encoding="utf-8")
                        + "\n".join(_figures_section(figures)) + "\n",
                        encoding="utf-8")
    return produced


def _figures_section(figures: dict) -> list:
    from .plots import FIGURES

    lines = ["", "## Figures", ""]
    if figures["produced"]:
        lines += ["Written to `plots/`:", ""]
        for path in figures["produced"]:
            name = Path(path).name
            lines.append("* `%s` - %s" % (name, FIGURES.get(name, "")))
        lines.append("")
    if figures["skipped"]:
        lines += ["Not drawn, and why - a figure is never omitted silently:", "",
                  "| figure | shows | why not |", "|---|---|---|"]
        for name, reason in sorted(figures["skipped"].items()):
            lines.append("| `%s` | %s | %s |" % (name, FIGURES.get(name, ""), reason))
        lines.append("")
    return lines


def _load_manifest(run_root: Path) -> dict:
    path = run_root / "manifest.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _sheet(metrics: Path, name: str) -> list:
    """One historical table, or an empty list if it was not produced."""
    return _read_csv(metrics / ("%s.csv" % name))


def _gather(run_root: Path, plan, manifest: dict) -> dict:
    metrics = run_root / "metrics"
    observations = _read_csv(metrics / "node_observations.csv")
    propagation = _read_csv(metrics / "block_propagation.csv")
    forks = _read_csv(metrics / "fork_events.csv")
    netem = _read_csv(metrics / "netem_conditions.csv")
    processes = _read_csv(metrics / "process_samples.csv")
    return {
        "run_root": run_root,
        "metrics": metrics,
        "plan": plan,
        "manifest": manifest,
        "backend": manifest.get("fabric_backend", "unknown"),
        "observations": observations,
        "propagation": propagation,
        "forks": forks,
        "netem": netem,
        "processes": processes,
        # The historical tables. Each may legitimately be absent - a run that
        # never reached the wPoA window has no epoch_shares - and every
        # section that uses one says so rather than disappearing.
        "run_index": _sheet(metrics, "run_index"),
        "proposers": _sheet(metrics, "proposers"),
        "chisq": _sheet(metrics, "chisq"),
        "block_times": _sheet(metrics, "block_times"),
        "epoch_shares": _sheet(metrics, "epoch_shares"),
        "weights_trajectory": _sheet(metrics, "weights_trajectory"),
        "alternanze": _sheet(metrics, "alternanze"),
        "sortition_margins": _sheet(metrics, "sortition_margins"),
        "forks_sheet": _sheet(metrics, "forks"),
        "verify": _sheet(metrics, "verify"),
        "esg": _sheet(metrics, "esg"),
        "gas": _sheet(metrics, "gas"),
        "plots": {},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _header(context: dict, title: str) -> list:
    plan = context["plan"]
    manifest = context["manifest"]
    return [
        "# %s" % title,
        "",
        PROVENANCE_BANNER % {"backend": context["backend"]},
        "",
        "| | |",
        "|---|---|",
        "| run | `%s` |" % manifest.get("run_id", ""),
        "| scenario | `%s` |" % plan.scenario,
        "| topology | `%s` |" % plan.topology.name,
        "| nodes | %d (%d miner, %d company, %d administrative) |" % (
            len(plan.enabled_nodes), len(plan.miners), len(plan.companies),
            len(plan.by_role("admin")) + len(plan.cas)),
        "| chain parameters | `%s` |" % Path(plan.chain_params.path).name,
        "| target-block-time | %d s |" % plan.target_block_time,
        "| weight-epoch-length | %d blocks |" % plan.epoch_length,
        "| dump function | `%s` |" % plan.chain_params.dump_function,
        "| setup-first-blocks | %d |" % plan.setup_first_blocks,
        "| seed | %d |" % plan.seed,
        "| git commit | `%s` |" % manifest.get("git_commit_short", ""),
        "| multichaind | `%s` |" % manifest.get("multichain_version", ""),
        "| status | %s |" % manifest.get("status", ""),
        "| generated | %s |" % context["generated_at"],
        "",
    ]


def _report_generale(context: dict) -> list:
    plan = context["plan"]
    observations = context["observations"]
    lines = _header(context, "General report")

    lines += ["## Chain progress", ""]
    heights = _numbers(observations, "block_height")
    if heights:
        by_node: dict = {}
        for row in observations:
            value = row.get("block_height", "")
            if value:
                by_node.setdefault(row["node_id"], []).append(float(value))
        rows = [(node, int(min(values)), int(max(values)), len(values))
                for node, values in sorted(by_node.items())]
        lines += _table(["node", "first height", "last height", "samples"], rows)
        lines += ["", "Highest height observed: **%d**." % int(max(heights)), ""]
    else:
        lines += _no_data(
            "No node reported a block height.",
            "Either the sampler never ran, or no daemon answered RPC; see `run.log`.")

    lines += ["## Peer connectivity", ""]
    peers = _numbers(observations, "peer_count")
    if peers:
        stats = _stats(peers)
        lines += _table(["metric", "value"],
                        [(k, v) for k, v in stats.items()])
        isolated = sorted({row["node_id"] for row in observations
                           if row.get("peer_count") == "0"})
        lines += ["", "Nodes observed with zero peers at some point: %s." % (
            ", ".join("`%s`" % n for n in isolated) if isolated else "none"), ""]
    else:
        lines += _no_data("No peer count was recorded.", "")

    lines += ["## Inter-block interval (wPoA window)", ""]
    lines += _block_time_section(context)

    lines += ["## Independent verification of the weights", ""]
    lines += _verify_section(context)

    lines += ["## Block propagation", ""]
    times = _numbers(context["propagation"], "propagation_time")
    if times:
        stats = _stats(times)
        lines += _table(["metric", "value (s)"], [(k, v) for k, v in stats.items()])
        lines += [
            "",
            "*Derived.* Difference between the last and the first node to report a",
            "given block hash. Its resolution is the sampling interval, so it is an",
            "**upper bound** on the true propagation time, not a wire measurement.",
            "",
        ]
    else:
        lines += _no_data(
            "No block was seen by more than one node.",
            "With a single node, or a sampling interval longer than the block time, "
            "propagation is not observable.")

    lines += ["## Forks", ""]
    forks = context["forks"]
    detected = [row for row in forks if row.get("fork_detected") == "1"]
    if forks:
        depths = _numbers(detected, "fork_depth")
        lines += [
            "Samples examined: **%d**. Samples showing divergence: **%d**." % (
                len(forks), len(detected)),
            "",
        ]
        if depths:
            lines += ["Deepest divergence observed: **%d consecutive samples**." % int(max(depths)), ""]
            lines += [
                "*Derived, and bounded by the sampling interval:* a fork that heals",
                "between two ticks is invisible here. `raw/metrics/epochs/`",
                "`node_state_epochs.csv` covers the coarser, per-epoch case.",
                "",
            ]
        else:
            lines += ["Every sample showed a single hash at the common reference height.", ""]
    else:
        lines += _no_data("No fork observation was recorded.", "")

    lines += ["## Emulated network conditions", ""]
    netem = context["netem"]
    if netem:
        rows = []
        for row in netem[:40]:
            rows.append((
                "%s -> %s" % (row["link_source"], row["link_target"]),
                row["kind"], row["profile"],
                row["netem_delay_ms"], row["netem_jitter_ms"],
                row["netem_loss_percent"], row["netem_bandwidth_mbps"],
            ))
        lines += _table(
            ["link", "kind", "profile", "delay ms", "jitter ms", "loss %", "Mbit/s"], rows)
        if len(netem) > 40:
            lines += ["", "*(%d further directed links omitted; the full table is in "
                      "`metrics/netem_conditions.csv`.)*" % (len(netem) - 40)]
        lines += [
            "",
            "*Observed as configured, not as measured.* These are the values installed",
            "with `tc`; measuring them on the wire would need a probe per link whose own",
            "traffic would perturb the run.",
            "",
            "Jitter is **new**: the archived Shadow campaign carried jitter 0 on every",
            "edge, because the field was never implemented (shadow/shadow#3601).",
            "",
        ]
    else:
        lines += _no_data("No realised topology was recorded.", "The fabric never built.")

    lines += ["## Host resources", ""]
    cpu = _numbers(context["processes"], "cpu_percent")
    memory = _numbers(context["processes"], "memory_bytes")
    if cpu or memory:
        lines += _table(
            ["metric", "n", "mean", "median", "max"],
            [("cpu_percent per process", _stats(cpu).get("n", 0),
              _stats(cpu).get("mean", ""), _stats(cpu).get("median", ""),
              _stats(cpu).get("max", "")),
             ("memory MiB per process", _stats(memory).get("n", 0),
              round(_stats(memory).get("mean", 0) / 1048576, 1) if memory else "",
              round(_stats(memory).get("median", 0) / 1048576, 1) if memory else "",
              round(_stats(memory).get("max", 0) / 1048576, 1) if memory else "")])
        lines += [
            "",
            "The host is shared by every emulated node, so its load is a confounder:",
            "block times that drifted because the machine was saturated must be readable",
            "as such rather than as a protocol result.",
            "",
        ]
    else:
        lines += _no_data("No process sample was recorded.", "")

    lines += _footer(plan)
    return lines


def _block_time_section(context: dict) -> list:
    rows = context["block_times"]
    if not rows:
        return _no_data(
            "`block_times.csv` was not produced.",
            "It needs the admin's final snapshot; see the run log for whether the "
            "snapshot happened.")
    row = rows[0]
    out = _table(["quantity", "value"], [
        ("blocks measured (wPoA window)", row.get("blocchi_misurati", "")),
        ("setup blocks (native PoA, excluded)", row.get("setup_blocks", "")),
        ("mean", "%s s" % row.get("dt_medio_s", "")),
        ("median", "%s s" % row.get("dt_mediana_s", "")),
        ("standard deviation", "%s s" % row.get("dt_sd_s", "")),
        ("min / max", "%s / %s s" % (row.get("dt_min_s", ""), row.get("dt_max_s", ""))),
        ("target", "%s s" % row.get("target_s", "")),
        ("gap", "%s s (%s%%)" % (row.get("scarto_s", ""), row.get("scarto_pct", ""))),
    ])
    out += [
        "",
        "*Derived* from the block header timestamps of the measurement window only.",
        "Under real execution this figure carries no simulator artefact - unlike the",
        "archived Shadow runs, whose interval included the vDSO latency the simulator",
        "charged to every clock call. It does carry **host contention**: check the",
        "load figures below before attributing a gap to the protocol's own feedback.",
        "",
    ]
    return out


def _verify_section(context: dict) -> list:
    rows = context["verify"]
    if not rows:
        return _no_data(
            "`verify.csv` was not produced.",
            "It comes from weightverifyweights, which needs the admin to be "
            "subscribed to wpoa-weights.")
    row = rows[0]
    invalid = row.get("non_validi", "")
    out = _table(["quantity", "value"], [
        ("epoch verified", row.get("epoca", "")),
        ("verification ran", row.get("verificato", "")),
        ("records checked", row.get("record", "")),
        ("records INVALID", invalid),
        ("verdicts", row.get("verdetti", "")),
    ])
    out.append("")
    if str(invalid) not in ("", "0"):
        out += ["> **%s record(s) failed independent recomputation.** Every input of"
                % invalid,
                "> the weight pipeline is public, so any node can check any record; a",
                "> failure here means a published weight does not follow from its",
                "> inputs. This is the most serious finding a run can produce.", ""]
    else:
        out += ["Every published weight was independently recomputed and matched.", ""]
    return out


def _report_confronto(context: dict) -> list:
    lines = _header(context, "Comparison report")
    lines += [
        "## Scope",
        "",
        "This file is the **per-run** half of the comparison. The cross-run view -",
        "several scenarios side by side - is produced by",
        "`experiments.cli analysis campaign --run-id ... --run-id ...`, which writes it",
        "under the campaign output root.",
        "",
        "## Observed against expected",
        "",
    ]
    rows = context["proposers"]
    if rows:
        table_rows = [
            (r.get("host", ""), r.get("blocchi", ""), r.get("quota_osservata", ""),
             r.get("peso_ultimo", ""), r.get("quota_attesa", ""),
             _delta(r.get("quota_osservata"), r.get("quota_attesa")),
             _relative(r.get("quota_osservata"), r.get("quota_attesa")))
            for r in rows
        ]
        lines += _table(
            ["host", "blocks", "observed share", "last weight", "expected share",
             "abs. difference", "rel. difference"], table_rows)
        lines += ["", "*Derived.* The expected share is `w_i / W_tot` from the last",
                  "published weight. Where the weights moved between epochs, the",
                  "per-epoch comparison below is the one that counts.", ""]
    else:
        lines += _no_data(
            "The historical `proposers.csv` was not produced.",
            "It comes from the migrated campaign analyser, which needs the admin's "
            "final snapshot (`raw/metrics/blocks.json`).")

    lines += ["## The proportionality test", ""]
    lines += _chisq_section(context)

    lines += ["## Per epoch, against the weight in force then", ""]
    lines += _epoch_section(context)

    lines += ["## Alternation: is the native Spacing still binding?", ""]
    lines += _alternation_section(context)

    lines += _footer(context["plan"])
    return lines


def _relative(observed, expected) -> str:
    try:
        observed, expected = float(observed), float(expected)
    except (TypeError, ValueError):
        return ""
    if expected == 0:
        return "n/a (expected 0)"
    return "%+.1f%%" % (100.0 * (observed - expected) / expected)


def _chisq_section(context: dict) -> list:
    rows = context["chisq"]
    if not rows:
        return _no_data("`chisq.csv` was not produced.",
                        "It is written by the migrated campaign analyser.")
    row = rows[0]
    sufficient = row.get("campione_sufficiente") in ("1", 1, "True", True)
    compatible = row.get("compatibile_ricalcolato") in ("1", 1, "True", True)
    out = _table(["quantity", "value"], [
        ("chi-square (recomputed)", row.get("chi2_ricalcolato", "")),
        ("degrees of freedom", row.get("df", "")),
        ("critical value at 5%", row.get("critico_5pct", "")),
        ("p-value", row.get("p_value", "") or "not available: scipy was absent"),
        ("minimum expected count", row.get("min_attesa", "")),
        ("sample sufficient", "yes" if sufficient else "**no**"),
        ("compatible with the weights", "yes" if compatible else "no"),
    ])
    out.append("")
    if not sufficient:
        out += [
            "> **The test is not applicable to this run.** The chi-square needs at",
            "> least 5 expected blocks per validator; here the minimum expectation is",
            "> `%s`. The verdict above must not be read as evidence either way - a" % row.get("min_attesa", "?"),
            "> longer measurement window is what would settle it.",
            "",
        ]
    elif compatible:
        out += ["The observed distribution is compatible with the published weights "
                "at the 5% level.", ""]
    else:
        out += ["The observed distribution is **not** compatible with the published "
                "weights at the 5% level. Check the alternation section below "
                "before concluding: a residual Spacing constraint produces exactly "
                "this.", ""]
    return out


def _epoch_section(context: dict) -> list:
    rows = context["epoch_shares"]
    if not rows:
        return _no_data(
            "`epoch_shares.csv` is empty.",
            "No epoch closed inside the wPoA measurement window - the run ended "
            "before the weights had governed a full epoch.")
    by_epoch = {}
    for row in rows:
        by_epoch.setdefault(row.get("epoca", ""), []).append(row)
    shown = sorted(by_epoch)[-8:]
    table_rows = []
    for epoch in shown:
        for row in sorted(by_epoch[epoch], key=lambda r: r.get("host", "")):
            table_rows.append((
                epoch, row.get("host", ""), row.get("blocchi_epoca", ""),
                row.get("quota_osservata_epoca", ""), row.get("peso_epoca", ""),
                row.get("quota_peso_epoca", ""),
                _delta(row.get("quota_osservata_epoca"), row.get("quota_peso_epoca"))))
    out = _table(["epoch", "host", "blocks", "observed", "weight", "expected",
                  "difference"], table_rows)
    out += ["", "*This is the comparison that counts* when the weights move between",
            "epochs: each epoch's blocks are compared with the weight that was",
            "readable at the chain tip while they were proposed, not with the last",
            "weight of the run. Showing the last %d of %d epochs."
            % (len(shown), len(by_epoch)), ""]
    return out


def _alternation_section(context: dict) -> list:
    rows = context["alternanze"]
    if not rows:
        return _no_data("`alternanze.csv` was not produced.", "")
    row = rows[0]
    observed = _number(row.get("consecutivi_osservati"))
    expected = _number(row.get("consecutivi_attesi"))
    out = _table(["quantity", "value"], [
        ("blocks measured", row.get("blocchi_misurati", "")),
        ("consecutive same-proposer pairs, observed", row.get("consecutivi_osservati", "")),
        ("consecutive same-proposer pairs, expected", row.get("consecutivi_attesi", "")),
    ])
    out.append("")
    if observed == 0 and (expected or 0) > 1:
        out += [
            "> **Zero is not a statistical outcome.** Under weighted selection the",
            "> probability that two consecutive blocks share a proposer is the sum of",
            "> the squared shares, so %.1f pairs were expected. Observing none is the" % (expected or 0),
            "> signature of an active alternation constraint - the native Spacing of",
            "> `mining-diversity`, which is `ceil(d*(N-1))` blocks. With it in force",
            "> the observed distribution is a round robin and **says nothing about the",
            "> weights**. Check `mining_diversity` in `run_index.csv`: it must be 0.",
            "",
        ]
    else:
        out += ["Consistent with weighted selection: no residual alternation "
                "constraint is visible.", ""]
    return out


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta(observed, expected) -> str:
    try:
        return "%.5f" % abs(float(observed) - float(expected))
    except (TypeError, ValueError):
        return ""


def _report_asse_livello(context: dict) -> list:
    plan = context["plan"]
    lines = _header(context, "Geography axis report")
    lines += [
        "## The axis",
        "",
        "The four level descriptors differ in **geography and nothing else**: node",
        "list, roles, clusters, chain parameters, seed and schedule are identical by",
        "construction, so a difference in the results is a difference in the network.",
        "",
        "This run sits at one point on that axis. Comparing points is",
        "`analysis campaign`'s job.",
        "",
        "## This run's position",
        "",
    ]
    from ..topology.validator import rtt_between, validate_topology

    report = validate_topology(plan.topology)
    miner_locations = [n.location for n in plan.miners if n.location]
    lines += _table(
        ["quantity", "value"],
        [("scenario", plan.scenario),
         ("topology", plan.topology.name),
         ("locations", len(plan.topology.locations)),
         ("links", len(plan.topology.links)),
         ("worst end-to-end RTT (ms)", report.max_rtt_ms),
         ("worst pair", "-".join(report.max_rtt_pair or ())),
         ("worst RTT between miners (ms)", rtt_between(plan.topology, miner_locations)),
         ("sortition band Dmax (s)",
          round(plan.chain_params.sortition_delta * plan.target_block_time, 3))])
    lines += [
        "",
        "*Derived from the topology, not measured.* RTT is the minimum-delay path over",
        "the declared link delays, doubled.",
        "",
        "The band `Dmax = delta * target-block-time` is what the geography has to be",
        "compared against: while `Dmax` is orders of magnitude above the worst RTT the",
        "geography is expected to be nearly invisible, and that is a result, not a",
        "failure. Compressing `target-block-time` is what brings the two into the same",
        "range.",
        "",
    ]
    lines += _footer(plan)
    return lines


def _report_asse_tbt(context: dict) -> list:
    plan = context["plan"]
    lines = _header(context, "Target-block-time axis report")
    band = plan.chain_params.sortition_delta * plan.target_block_time
    lines += [
        "## The axis",
        "",
        "`target-block-time` is a chain parameter, so moving it means a different",
        "chain: the axis is explored by running the same descriptor against a different",
        "file in `configs/chain-params/`, which differ by that one line.",
        "",
        "## This run's position",
        "",
    ]
    lines += _table(
        ["quantity", "value"],
        [("target-block-time", "%d s" % plan.target_block_time),
         ("delta", plan.chain_params.sortition_delta),
         ("sortition band Dmax", "%.3f s" % band),
         ("weight-epoch-length", "%d blocks" % plan.epoch_length),
         ("epoch duration at target", "%.0f s" % (plan.epoch_length * plan.target_block_time)),
         ("measurement window", "%d blocks" % plan.measure_blocks())])

    lines += ["", "## The timer race (Prop. 5.18)", ""]
    lines += _margin_section(context)

    lines += ["", "## Observed inter-block interval", ""]
    if context["block_times"]:
        lines += _block_time_section(context)
        lines += _footer(plan)
        return lines
    intervals = _block_intervals(context["observations"])
    if intervals:
        stats = _stats(intervals)
        target = plan.target_block_time
        lines += _table(["metric", "value (s)"], [(k, v) for k, v in stats.items()])
        lines += [
            "",
            "Target %d s, observed mean %.3f s, gap %+.3f s (%+.1f%%)." % (
                target, stats["mean"], stats["mean"] - target,
                100.0 * (stats["mean"] - target) / target),
            "",
            "*Derived* from the block header timestamps seen by the sampler. Under real",
            "execution this figure has no simulator artefact in it - unlike the archived",
            "Shadow runs, whose interval carried the vDSO latency the simulator charged",
            "to every clock call. It does, however, include host contention: check the",
            "load figures in `report_generale.md` before attributing a gap to the",
            "protocol's own feedback.",
            "",
        ]
    else:
        lines += _no_data(
            "Fewer than two distinct block times were observed.",
            "The run may not have reached the wPoA window.")
    lines += _footer(plan)
    return lines


def _margin_section(context: dict) -> list:
    rows = context["sortition_margins"]
    if not rows:
        return _no_data(
            "`sortition_margins.csv` was not produced.",
            "The sortition delays are parsed from each node's debug.log, so the "
            "nodes must run with -debug=wpoa and the logs must have been archived.")
    row = rows[0]
    fraction = row.get("frazione_G_sotto_100ms", "")
    out = _table(["quantity", "value"], [
        ("rounds observed", row.get("round", "")),
        ("band Dmax = delta x tbt", "%s s" % row.get("banda_dmax_s", "")),
        ("worst RTT of the topology", "%s ms" % row.get("rtt_max_ms", "")),
        ("margin G, mean", "%s s" % row.get("G_medio_s", "")),
        ("margin G, median", "%s s" % row.get("G_mediano_s", "")),
        ("margin G, minimum", "%s s" % row.get("G_min_s", "")),
        ("rounds with G under 100 ms", "%s (%s of the total)"
         % (row.get("round_G_sotto_100ms", ""), fraction)),
    ])
    out += [
        "",
        "`G` is the distance between the two best delays of a round. When it falls",
        "below the network's own variance, the winner of the timer race is decided",
        "by latency rather than by score - the regime of Prop. 5.18. The fraction",
        "above is the direct measure of how often that happened.",
        "",
    ]
    return out


def _block_intervals(observations: list) -> list:
    """Successive block header timestamps, from whichever node saw them first."""
    by_height: dict = {}
    for row in observations:
        height, block_time = row.get("block_height"), row.get("block_time")
        if not height or not block_time:
            continue
        try:
            by_height.setdefault(int(height), float(block_time))
        except (TypeError, ValueError):
            continue
    heights = sorted(by_height)
    return [by_height[b] - by_height[a]
            for a, b in zip(heights, heights[1:]) if b == a + 1]


def _find_first(root: Path, name: str) -> Path | None:
    if not Path(root).is_dir():
        return None
    for path in sorted(Path(root).rglob(name)):
        return path
    return None


def _footer(plan) -> list:
    return [
        "---",
        "",
        "## How to read this",
        "",
        "* Every quantity is labelled *observed* (read from a node, the kernel or the",
        "  configuration), *derived* (computed by a stated formula) or **unavailable**",
        "  (declared absent, with the reason). `metrics_schema_report.md` carries the",
        "  full catalogue.",
        "* Timestamps are wall clock and monotonic. Neither is comparable with the",
        "  archived Shadow campaign's simulated time.",
        "* The run is reproducible from `config/` and the seed recorded above:",
        "  `experiments.cli experiment run --experiment <run>/config/experiment.yaml",
        "  --seed %d`." % plan.seed,
        "",
    ]


def _plots(run_root: Path, context: dict) -> list:
    """Plots, when matplotlib is present. Absence is reported, never fatal."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        LOG.warning("matplotlib is not installed: no plot was produced")
        return []

    plots_dir = Path(run_root) / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    produced = []

    by_node: dict = {}
    for row in context["observations"]:
        height, monotonic = row.get("block_height"), row.get("timestamp_monotonic")
        if not height or not monotonic:
            continue
        try:
            by_node.setdefault(row["node_id"], []).append((float(monotonic), float(height)))
        except (TypeError, ValueError):
            continue
    if by_node:
        figure, axes = plt.subplots(figsize=(10, 5))
        for node, series in sorted(by_node.items()):
            series.sort()
            axes.plot([p[0] for p in series], [p[1] for p in series], label=node, linewidth=1)
        axes.set_xlabel("monotonic time (s)")
        axes.set_ylabel("block height")
        axes.set_title("Chain height per node - %s" % context["plan"].scenario)
        if len(by_node) <= 12:
            axes.legend(fontsize=7, ncol=2)
        axes.grid(alpha=0.3)
        path = plots_dir / "01_height_per_node.png"
        figure.tight_layout()
        figure.savefig(path, dpi=120)
        plt.close(figure)
        produced.append(str(path))

    times = _numbers(context["propagation"], "propagation_time")
    if times:
        figure, axes = plt.subplots(figsize=(8, 4.5))
        axes.hist(times, bins=min(40, max(5, len(times) // 4)), color="#4477aa")
        axes.set_xlabel("propagation time (s, upper bound)")
        axes.set_ylabel("blocks")
        axes.set_title("Block propagation across nodes")
        axes.grid(alpha=0.3)
        path = plots_dir / "02_block_propagation.png"
        figure.tight_layout()
        figure.savefig(path, dpi=120)
        plt.close(figure)
        produced.append(str(path))

    delays = _numbers(context["netem"], "netem_delay_ms")
    if delays:
        figure, axes = plt.subplots(figsize=(8, 4.5))
        axes.hist(delays, bins=min(30, max(5, len(delays) // 2)), color="#aa7744")
        axes.set_xlabel("configured one-way delay (ms)")
        axes.set_ylabel("directed links")
        axes.set_title("Emulated link delays - %s" % context["plan"].topology.name)
        axes.grid(alpha=0.3)
        path = plots_dir / "03_link_delays.png"
        figure.tight_layout()
        figure.savefig(path, dpi=120)
        plt.close(figure)
        produced.append(str(path))

    LOG.info("wrote %d plots to %s", len(produced), plots_dir)
    return produced
