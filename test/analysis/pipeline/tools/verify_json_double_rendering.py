#!/usr/bin/env python3
"""Does the node's JSON writer reproduce the numbers the node computed?

A diagnostic, not a fix. It answers one question against runs that already exist on
disk, with no chain and no emulator: **is the delay-recompute disagreement a defect of
the sortition mechanism, or of the way the node renders a double into JSON?**

## The claim under test

``src/json/json_spirit_writer_template.h`` decides how many decimals a double needs by
*rounding* it, and then emits it by *truncating* it:

```c
int output_double_precision( const double& value, int max_p )      // :251
{
    sprintf(fp,"%%0.%df",p);
    sprintf(sp,fp,value);                       // rounds: 0.99999999999999944 -> "1.00000000000000"
    while( (tp>sp) && (p>=0) && *tp=='0') { p--; tp--; }        // strips the 14 zeros
    if( (tp == sp) || (*tp == '.') ) p=0;                       // only the point is left
    return p;
}
...
    if(p > 0) { os_ << ... << setprecision(p) << value; }
    else      { os_ << (int64_t)value; }                        // :349 truncates the ORIGINAL
```

So a value whose fractional part rounds up to ``1.000…0`` at fourteen decimals is
reported as its floor: ``0.99999999999999944`` is emitted as ``0``, and
``14.99999999999999467`` as ``14``. One whole unit, lost between the probe and the
emission.

## What this script does

For every ``(round, candidate)`` the harness recorded, it reconstructs the two values
the node must have held — ``score_norm = 1 - exp(-W_tot * score)`` and
``D = T + delta*T*(2*score_norm - 1) + lambda*Phi`` — pushes each through a faithful
Python transcription of that C++ writer, and compares the result with what the node
actually reported.

If the transcription reproduces the reported value **including every anomaly**, the
disagreement is a rendering defect and the sortition mechanism is exonerated. If it
reproduces the healthy rows but not the anomalies, the explanation is somewhere else and
this script has failed to find it — which is also an answer.

Reconstruction is sound to about 1e-27: ``score`` and ``total_effective_weight`` are
themselves rendered doubles, but their own fractional parts are nowhere near the
boundary that triggers the defect, so their fourteen-decimal rendering is exact enough
that the reconstructed ``score_norm`` is unaffected at double precision.

    python3 test/analysis/pipeline/tools/verify_json_double_rendering.py [--run-dir DIR ...]

With no argument it examines every run under ``test/results/`` that carries the table.
Exit status is 0 when the transcription explains every row it examined.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[4]
RESULTS = REPO_ROOT / "test" / "results"

#: ``max_p`` in ``output_double``. The node's default; ``-apidecimaldigits`` overrides it,
#: and no profile in this tree sets that flag.
DEFAULT_MAX_P = 14


# --------------------------------------------------------------------------------------
# A faithful transcription of src/json/json_spirit_writer_template.h
# --------------------------------------------------------------------------------------


def output_double_precision(value: float, max_p: int) -> int:
    """``output_double_precision`` at :251, character for character.

    The ``sprintf`` is what rounds. Everything after it counts how many decimals survive
    once the trailing zeros of that *rounded* rendering are stripped.
    """
    rendered = "%0.*f" % (max_p, value)
    p = max_p
    i = len(rendered) - 1
    while i > 0 and p >= 0 and rendered[i] == "0":
        p -= 1
        i -= 1
    if i == 0 or rendered[i] == ".":
        p = 0
    return p


def output_double(value: float, max_p: int = DEFAULT_MAX_P) -> str:
    """``output_double`` at :273, including the exponent branch and the ``(int64_t)`` cast.

    The last line is the defect: when the probe above concludes that no decimal survives,
    the value is emitted as ``(int64_t)value``, which truncates — while the probe reached
    that conclusion by rounding.
    """
    a = abs(value)
    e = math.log10(a) if a > 0 else 0.0
    z = 0
    if e < -4:
        f = a * 1e9
        j = int(f)
        if j and (f - j) < 0.0001:
            z = 1
    k = int(e)
    if e < k:
        k -= 1
    v = value / (10.0 ** k)
    p = output_double_precision(v, max_p)
    if p - k > max_p:
        z = 0
    if ((e < -4.0) or (e > 12.0)) and z == 0:
        head = ("%0.*f" % (p, v)) if p > 0 else str(int(v))
        return "%se%s%d" % (head, "+" if e >= 0 else "", k)
    pfull = output_double_precision(value, max_p)
    p = pfull if pfull + k <= max_p else p - k
    if p > 0:
        return "%0.*f" % (p, value)
    return str(int(value))          # (int64_t)value


# --------------------------------------------------------------------------------------
# The two quantities the node held
# --------------------------------------------------------------------------------------


def true_score_norm(score: float, total_eff_weight: float) -> float:
    """``PrivateSortition::NormalizedScore``: ``1 - e^{-W * score}``."""
    if total_eff_weight <= 0.0 or score < 0.0:
        return 1.0
    return 1.0 - math.exp(-min(total_eff_weight * score, 700.0))


def true_delay(norm: float, tbt: float, delta: float, lam: float, phi: float) -> float:
    """``PrivateSortition::MiningDelay``: ``T + delta*T*(2*norm - 1) + lambda*Phi``."""
    return tbt + delta * tbt * (2.0 * norm - 1.0) + lam * phi


# --------------------------------------------------------------------------------------
# Examining a run
# --------------------------------------------------------------------------------------


def _f(value: Optional[str]) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class Finding:
    """One field whose reported value is not what the node computed."""

    def __init__(self, height, address, field, held, reported, predicted):
        self.height = height
        self.address = address
        self.field = field
        self.held = held
        self.reported = reported
        self.predicted = predicted

    @property
    def explained(self) -> bool:
        return self.predicted is not None and _f(self.predicted) == self.reported

    def __str__(self) -> str:
        return (
            "h=%-7s %s.. %-11s held %-22.17g reported %-20s writer says %-20s %s"
            % (
                self.height, str(self.address)[:10], self.field, self.held,
                self.reported, self.predicted,
                "EXPLAINED" if self.explained else "NOT EXPLAINED",
            )
        )


def examine(run_dir: Path, max_p: int) -> Tuple[int, List[Finding], List[str]]:
    """Returns (rows examined, findings, notes)."""
    table = run_dir / "analysis" / "phase1" / "round_delays.csv"
    notes: List[str] = []
    if not table.is_file():
        return 0, [], ["no round_delays.csv"]

    rows = list(csv.DictReader(table.open(encoding="utf-8")))
    findings: List[Finding] = []
    examined = 0
    skipped = 0

    for row in rows:
        score = _f(row.get("score"))
        w_tot = _f(row.get("total_effective_weight"))
        tbt = _f(row.get("target_block_time"))
        delta = _f(row.get("delta"))
        lam = _f(row.get("lambda_s")) or 0.0
        phi = _f(row.get("feedback_phi")) or 0.0
        norm_reported = _f(row.get("score_norm"))
        delay_reported = _f(row.get("delay_s"))
        if None in (score, w_tot, tbt, delta, norm_reported, delay_reported) or not w_tot:
            skipped += 1
            continue
        examined += 1

        norm_held = true_score_norm(score, w_tot)
        delay_held = true_delay(norm_held, tbt, delta, lam, phi)

        for field, held, reported in (
            ("score_norm", norm_held, norm_reported),
            ("delay_s", delay_held, delay_reported),
        ):
            # A disagreement far larger than double precision is the thing to explain.
            # Anything at the 1e-13 level is the rendering's own truncation of a healthy
            # value and is not what this is about.
            if abs(held - reported) <= 1e-9:
                continue
            findings.append(
                Finding(row.get("round_height"), row.get("address"), field,
                        held, reported, output_double(held, max_p))
            )

    if skipped:
        notes.append("%d row(s) skipped for missing fields" % skipped)
    return examined, findings, notes


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--run-dir", action="append", default=None,
        help="a run directory; repeatable. Default: every run under test/results/.",
    )
    parser.add_argument(
        "--max-p", type=int, default=DEFAULT_MAX_P,
        help="the node's -apidecimaldigits. Default %d, which is the node's own."
             % DEFAULT_MAX_P,
    )
    args = parser.parse_args(argv)

    if args.run_dir:
        runs = [Path(d) for d in args.run_dir]
    else:
        runs = sorted(
            d for d in RESULTS.glob("run-*")
            if (d / "analysis" / "phase1" / "round_delays.csv").is_file()
        )
    if not runs:
        print("no run directory carries analysis/phase1/round_delays.csv", file=sys.stderr)
        return 2

    print("Transcription of json_spirit's double writer, checked against what the node "
          "reported.")
    print("max_p = %d\n" % args.max_p)

    total_rows = 0
    total_findings: List[Finding] = []
    unexplained: List[Finding] = []

    for run in runs:
        examined, findings, notes = examine(run, args.max_p)
        total_rows += examined
        total_findings.extend(findings)
        bad = [f for f in findings if not f.explained]
        unexplained.extend(bad)
        status = "clean" if not findings else (
            "%d anomaly(ies), all explained" % len(findings) if not bad
            else "%d anomaly(ies), %d NOT explained" % (len(findings), len(bad))
        )
        print("%-56s %7d rows  %s%s"
              % (run.name, examined, status, ("  [%s]" % "; ".join(notes)) if notes else ""))
        for finding in findings:
            print("    " + str(finding))

    print()
    print("rows examined ....... %d" % total_rows)
    print("anomalies found ..... %d" % len(total_findings))
    print("explained by the writer %d" % (len(total_findings) - len(unexplained)))
    print("unexplained ......... %d" % len(unexplained))
    print()
    if not total_findings:
        print("No anomaly in these runs. The transcription is untested by them: it says "
              "nothing either way.")
        return 0
    if unexplained:
        print("The rendering defect does NOT account for every anomaly. Something else is "
              "at work in the rows marked above, and the mechanism is not settled.")
        return 1
    print("Every anomaly is accounted for by the rendering, on values the node computed "
          "correctly. The sortition mechanism is not implicated: what is wrong is the "
          "number the node prints, not the number it used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
