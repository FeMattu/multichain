# The node's JSON writer loses a whole unit — evidence

> **Type:** historical record (evidence) · **Date:** 2026-09-18 · **Status:** mechanism confirmed, mitigated harness-side
>
> Kept as written: it records the work as it was done and is **not** updated when the
> code changes, so paths, identifiers and line numbers may no longer match the tree.
>
> **Design record:** [`../adr/core-emulation-2026.md`](../adr/core-emulation-2026.md) §9.3.
> **Reproducer:** [`test/analysis/pipeline/tools/verify_json_double_rendering.py`](../../test/analysis/pipeline/tools/verify_json_double_rendering.py).
>
> **For the system as it is now:** [`test/README.md`](../../test/README.md).

This exists so the two diagnostics below stay citable without keeping their raw scratch
files in the tree. Every figure here is a measurement, not a summary of one.

## The defect

`src/json/json_spirit_writer_template.h` decides how many decimals a double needs by
**rounding** it, and then emits it by **truncating** it:

```c
int output_double_precision( const double& value, int max_p )       // :251
{
    sprintf(fp,"%%0.%df",p);
    sprintf(sp,fp,value);                     // rounds: 0.99999999999999944 -> "1.00000000000000"
    while( (tp>sp) && (p>=0) && *tp=='0') { p--; tp--; }     // strips the fourteen zeros
    if( (tp == sp) || (*tp == '.') ) p=0;                    // only the point is left
    return p;
}
...
    if(p > 0) { os_ << ... << setprecision(p) << value; }
    else      { os_ << (int64_t)value; }                     // :349 truncates the ORIGINAL
```

A value whose fractional part rounds up to `1.000…0` at fourteen decimals is reported as
its floor. The error is always exactly one unit of the value's own scale.

## Diagnostic (a) — the writer, transcribed and checked offline

A faithful Python transcription of that writer, applied to the two quantities the node
must have held for every `(round, candidate)` in nine archived runs, and compared against
what the node actually reported.

| run | rows | anomalies | explained by the writer |
|---|---:|---:|---:|
| `smoke-large` (native, pre-workaround) | 12 150 | 227 | 227 |
| `smoke-malicious` (native) | 1 650 | 26 | 26 |
| `core-intercontinental` | 1 778 | 18 | 18 |
| `core-national` | 1 778 | 17 | 17 |
| `core-regional` | 1 785 | 13 | 13 |
| `core-smoke`, three `smoke-small` runs | 3 846 | 0 | — |
| **total** | **22 987** | **301** | **301** |

Of the 301: **298 are `score_norm` reported as 0 instead of ~1**, and **3 are a delay of
`14.99999999999999x` reported as `14`**.

The healthy rows reproduce too, including those where `score_norm` is *exactly* 1.0 in
double precision and the writer prints `1` correctly. Both kinds occur in the same round,
under the same configuration, which is what rules out any per-chain explanation.

`long10h-medium-sqrt` is deliberately excluded: its analysis directory is internally
inconsistent (`round_level.csv` predates `round_delays.csv` by 24 minutes and covers
heights the latter does not), and the operator is re-supplying the data.

## Diagnostic (b) — the same profile, on the live node, with the boundary moved

`-apidecimaldigits=17` raises the writer's `max_p`, so the probe never concludes that no
decimal survives and the truncating branch is never reached. Same profile, same seed, same
28 nodes; the only difference is the flag.

| | reference (2026-09-17) | diagnostic (2026-09-18) |
|---|---|---|
| `-apidecimaldigits` | unset (node default, 14) | **17**, verified on all 28 nodes |
| rows examined | 1 650 | 1 630 |
| corrupted values | **26** | **0** |
| `delay_recompute_mismatch_rounds` | — | **0** |
| `max abs delay mismatch` | ~1 s | 8.88e-16 |
| consistency checks | — | 14/15 (only `phi_consistent`) |

The prediction set before the run was "zero anomalies". That is what happened.

## Blast radius, measured rather than assumed

**Currency amounts are not affected and never were.** `ValueFromAmount`
(`src/rpc/rpcserver.cpp:451`) returns `amount / COIN`, an exact multiple of 1e-8, so its
fraction has at most eight decimals and cannot round up at the fourteenth. 300 005 amounts
were pushed through the transcribed writer and **none** was corrupted.

Only computed, unquantised doubles are exposed — the wPoA audit values, which is where
this was found.

## What was done, and what was not

**Done:** every shipped profile sets `runtime.api_decimal_digits: 17`. Scope: `test/`
only. It is a mitigation — the defect remains in `src/json/` for every other consumer of
this fork.

**Not done:** the repair itself, at
`src/json/json_spirit_writer_template.h:349`, which would emit the rounded integer rather
than the truncated one. It is the correct fix and it touches every JSON number this
Bitcoin-Core-derived fork emits, so it is a deliberate, separate intervention and not
something to do in the middle of a campaign.
