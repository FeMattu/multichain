"""Per-epoch summary, computed from what the emulation actually observed.

The migrated `legacy/summary_per_epoca.py` reproduces the Shadow campaign's
own per-epoch sheet and must keep doing so byte for byte, so it is left
untouched and its schema stays as the archive wrote it, in Italian. This
module is the emulation-native view the brief asks for: English field names,
wall-clock timestamps, and every number taken from the explorer's record of
the run rather than from a simulator's event log.

Two files, because they answer two questions:

* `epoch_summary.csv`    one row per epoch - how the chain behaved
* `epoch_validators.csv` one row per (epoch, validator) - who proposed what

Both are additions. `epoch_shares.csv` keeps the historical schema every
archived report keys on; see docs/migration-from-shadow.md for why the two
coexist instead of one being rewritten into the other.
"""

from __future__ import annotations

import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

try:  # scipy is optional everywhere else in this package
    from scipy import stats as _scipy_stats
except ImportError:  # pragma: no cover - exercised by the fallback branch
    _scipy_stats = None

EPOCH_COLUMNS = [
    "epoch_id", "run_id", "scenario",
    "start_wallclock", "end_wallclock", "duration_wallclock_seconds",
    "start_height", "end_height", "block_count", "transaction_count",
    "fork_count", "average_block_time_seconds",
    "chi_square_statistic", "chi_square_p_value", "chi_square_note",
    "sortition_margin_mean", "sortition_margin_std", "sortition_margin_note",
]

VALIDATOR_COLUMNS = [
    "epoch_id", "run_id", "scenario", "node_id",
    "expected_weight_share", "observed_block_share", "blocks_proposed",
    "deviation_absolute", "deviation_relative",
]

#: What a field says when it has no value. Written out rather than left blank
#: so a reader never has to decide whether an empty cell means zero.
UNAVAILABLE = "dato non disponibile"


def _rows(path: Path) -> list:
    if not path.is_file() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _chi_square(observed: dict, expected: dict) -> tuple:
    """Statistic, p-value and the honest note about whether it may be read.

    Pearson's approximation needs every expected count at 5 or above. Below
    that the number is still computed - it is the one the historical sheets
    carry - but the note says it must not be interpreted, which is the part a
    reader skips if it is not written down.
    """
    hosts = sorted(set(observed) | set(expected))
    obs = [observed.get(h, 0) for h in hosts]
    exp = [expected.get(h, 0.0) for h in hosts]
    if len(hosts) < 2 or sum(exp) <= 0:
        return "", "", "%s: fewer than two validators with weight" % UNAVAILABLE
    statistic = sum((o - e) ** 2 / e for o, e in zip(obs, exp) if e > 0)
    degrees = max(1, len(hosts) - 1)
    if _scipy_stats is not None:
        p_value = float(_scipy_stats.chi2.sf(statistic, degrees))
    else:
        p_value = ""
    smallest = min(exp)
    note = ("" if smallest >= 5 else
            "sample too small to interpret: smallest expected count %.2f < 5" % smallest)
    return round(statistic, 6), (round(p_value, 6) if p_value != "" else ""), note


def _epoch_of(height: int, epoch_length: int) -> int:
    return height // max(1, epoch_length) + 1


def build(run_root, *, epoch_length: int = 0) -> dict:
    """Compute both tables. Returns them plus the reasons for what is absent."""
    run_root = Path(run_root)
    observations = run_root / "raw" / "observations"

    blocks = _rows(observations / "explorer_blocks.csv")
    transactions = _rows(observations / "explorer_transactions.csv")
    forks = _rows(observations / "fork_events.csv")
    # The campaign sheets sit in <run>/metrics; layout.metrics is the raw
    # per-node capture, which is a different tree.
    margins = _rows(run_root / "metrics" / "sortition_margins.csv")

    if not epoch_length:
        epoch_length = _epoch_length_from_manifest(run_root) or 12

    per_epoch = defaultdict(list)
    for row in blocks:
        height = int(_float(row.get("height"), -1) or -1)
        if height < 0:
            continue
        per_epoch[_epoch_of(height, epoch_length)].append(row)

    transactions_by_epoch = defaultdict(int)
    for row in transactions:
        height = int(_float(row.get("height"), -1) or -1)
        if height >= 0:
            transactions_by_epoch[_epoch_of(height, epoch_length)] += 1

    forks_by_epoch = defaultdict(int)
    for row in forks:
        height = int(_float(row.get("height"), -1) or -1)
        if height >= 0:
            forks_by_epoch[_epoch_of(height, epoch_length)] += 1

    margin_values = [_float(r.get("margine_s") or r.get("margin_s"))
                     for r in margins]
    margin_values = [v for v in margin_values if v is not None]

    epoch_rows, validator_rows = [], []
    for epoch in sorted(per_epoch):
        rows = sorted(per_epoch[epoch], key=lambda r: _float(r.get("height"), 0))
        run_id = rows[0].get("run_id", "")
        scenario = rows[0].get("scenario", "")
        starts = [r.get("observed_wallclock", "") for r in rows if r.get("observed_wallclock")]
        block_times = [_float(r.get("block_time")) for r in rows]
        block_times = [t for t in block_times if t is not None]
        deltas = [b - a for a, b in zip(block_times, block_times[1:]) if b >= a]

        observed, expected_weight = defaultdict(int), {}
        for row in rows:
            host = row.get("miner_host") or row.get("miner") or ""
            if host:
                observed[host] += 1
            weight = _float(row.get("proposer_weight"))
            if host and weight is not None and weight > 0:
                expected_weight[host] = weight

        total_weight = sum(expected_weight.values())
        block_count = len(rows)
        expected_counts = {h: block_count * w / total_weight
                           for h, w in expected_weight.items()} if total_weight else {}
        statistic, p_value, chi_note = _chi_square(observed, expected_counts)

        epoch_rows.append({
            "epoch_id": epoch, "run_id": run_id, "scenario": scenario,
            "start_wallclock": starts[0] if starts else UNAVAILABLE,
            "end_wallclock": starts[-1] if starts else UNAVAILABLE,
            "duration_wallclock_seconds": (
                round(block_times[-1] - block_times[0], 3)
                if len(block_times) > 1 else UNAVAILABLE),
            "start_height": int(_float(rows[0].get("height"), 0)),
            "end_height": int(_float(rows[-1].get("height"), 0)),
            "block_count": block_count,
            "transaction_count": transactions_by_epoch.get(epoch, 0),
            "fork_count": forks_by_epoch.get(epoch, 0),
            "average_block_time_seconds": (
                round(statistics.mean(deltas), 3) if deltas else UNAVAILABLE),
            "chi_square_statistic": statistic if statistic != "" else UNAVAILABLE,
            "chi_square_p_value": p_value if p_value != "" else UNAVAILABLE,
            "chi_square_note": chi_note or "",
            "sortition_margin_mean": (round(statistics.mean(margin_values), 4)
                                      if margin_values else UNAVAILABLE),
            "sortition_margin_std": (round(statistics.pstdev(margin_values), 4)
                                     if len(margin_values) > 1 else UNAVAILABLE),
            "sortition_margin_note": (
                "" if margin_values else
                "%s: the sortition delays are only written to debug.log when "
                "the nodes run with -debug=wpoa" % UNAVAILABLE),
        })

        for host in sorted(set(observed) | set(expected_weight)):
            share_expected = (expected_weight.get(host, 0.0) / total_weight
                              if total_weight else None)
            share_observed = observed.get(host, 0) / block_count if block_count else 0.0
            deviation = (share_observed - share_expected
                         if share_expected is not None else None)
            validator_rows.append({
                "epoch_id": epoch, "run_id": run_id, "scenario": scenario,
                "node_id": host,
                "expected_weight_share": (round(share_expected, 6)
                                          if share_expected is not None else UNAVAILABLE),
                "observed_block_share": round(share_observed, 6),
                "blocks_proposed": observed.get(host, 0),
                "deviation_absolute": (round(deviation, 6)
                                       if deviation is not None else UNAVAILABLE),
                "deviation_relative": (
                    round(deviation / share_expected, 6)
                    if deviation is not None and share_expected else UNAVAILABLE),
            })

    return {"epochs": epoch_rows, "validators": validator_rows,
            "epoch_length": epoch_length, "blocks_read": len(blocks)}


def _epoch_length_from_manifest(run_root: Path) -> int:
    import json
    try:
        data = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    return int(data.get("epoch_length_blocks") or 0)


def _write_csv(path: Path, columns: list, rows: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
    return path


def render(result: dict) -> str:
    """The per-epoch report, in the order a reader needs it."""
    epochs = result["epochs"]
    lines = ["# Summary per epoch", "",
             "Epoch length: %d blocks. Every timestamp is wall-clock: these runs"
             % result["epoch_length"],
             "are an emulation with real MultiChain processes and have no simulated",
             "clock. Durations come from the block header timestamps; a field with",
             "`%s` says why it is absent rather than showing a blank." % UNAVAILABLE,
             ""]
    if not epochs:
        lines += ["No epoch closed inside the observed range.", "",
                  "%s: the collector saw %d blocks." % (UNAVAILABLE, result["blocks_read"]),
                  ""]
        return "\n".join(lines)

    lines += ["| epoch | blocks | heights | txs | forks | mean block time (s) | chi2 | p |",
              "|---|---|---|---|---|---|---|---|"]
    for row in epochs:
        lines.append("| %s | %s | %s-%s | %s | %s | %s | %s | %s |" % (
            row["epoch_id"], row["block_count"], row["start_height"],
            row["end_height"], row["transaction_count"], row["fork_count"],
            row["average_block_time_seconds"], row["chi_square_statistic"],
            row["chi_square_p_value"]))
    lines.append("")

    notes = {row["chi_square_note"] for row in epochs if row["chi_square_note"]}
    if notes:
        lines += ["## Reading the chi-square", ""]
        lines += ["- %s" % note for note in sorted(notes)]
        lines.append("")

    margin_notes = {row["sortition_margin_note"] for row in epochs
                    if row["sortition_margin_note"]}
    if margin_notes:
        lines += ["## Sortition margin", ""]
        lines += ["- %s" % note for note in sorted(margin_notes)]
        lines.append("")

    lines += ["## Per validator", "",
              "| epoch | node | expected share | observed share | blocks | deviation |",
              "|---|---|---|---|---|---|"]
    for row in result["validators"]:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            row["epoch_id"], row["node_id"], row["expected_weight_share"],
            row["observed_block_share"], row["blocks_proposed"],
            row["deviation_absolute"]))
    lines.append("")
    return "\n".join(lines)


def write(run_root) -> dict:
    """Compute and write both tables and the report."""
    run_root = Path(run_root)
    result = build(run_root)
    metrics = run_root / "metrics"
    reports = run_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    written = {
        "epoch_summary": _write_csv(metrics / "epoch_summary.csv",
                                    EPOCH_COLUMNS, result["epochs"]),
        "epoch_validators": _write_csv(metrics / "epoch_validators.csv",
                                       VALIDATOR_COLUMNS, result["validators"]),
    }
    report_path = reports / "summary_per_epoca_emulation.md"
    report_path.write_text(render(result), encoding="utf-8")
    written["report"] = report_path
    return {"files": written, "epochs": len(result["epochs"]),
            "validators": len(result["validators"])}


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_root")
    args = parser.parse_args(argv)
    result = write(args.run_root)
    for name, path in result["files"].items():
        print("%-18s %s" % (name, path))
    print("epochs: %d, validator rows: %d" % (result["epochs"], result["validators"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
