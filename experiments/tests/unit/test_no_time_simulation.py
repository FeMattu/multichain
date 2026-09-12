"""The harness must measure time, never simulate it.

This is the constraint that separates this branch from the Shadow lineage it
replaced. Shadow ran a discrete-event scheduler on a virtual clock: a run
could be faster or slower than the wall clock, and every duration in its
output was simulated. Here the processes are real `multichaind` binaries on
a real (emulated) network, and every duration must come from the machine's
own clock.

These tests are a static guard over the source. They cannot prove the numbers
are honest - only a run can - but they make the specific ways the old model
could creep back detectable at commit time:

* a scale or speed-up factor anywhere;
* a duration taken from `time.time()`, which jumps when NTP steps the clock;
* an epoch's end synthesised as `start + configured_duration` rather than
  observed;
* the archived simulator's own modules being imported by the live harness.

`analysis/legacy/` is exempt from the wall-clock rules and only from those:
it is the migrated Shadow analyser, kept byte-compatible on purpose, and it
reads timestamps out of archived files rather than taking any of its own.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

EXPERIMENTS = Path(__file__).resolve().parents[2]

#: Directories excluded, and why. Nothing here runs during an emulation.
EXCLUDED = {
    "legacy": "the migrated Shadow analyser, kept byte-compatible",
    "historical": "archived campaign data, not code",
    "__pycache__": "build output",
    "results": "run output",
    "tests": "this file names the forbidden words in order to forbid them",
    ".pytest_cache": "build output",
}


def _sources() -> list:
    out = []
    for path in sorted(EXPERIMENTS.rglob("*.py")):
        if any(part in EXCLUDED for part in path.relative_to(EXPERIMENTS).parts):
            continue
        out.append(path)
    return out


def _shell_sources() -> list:
    return sorted((EXPERIMENTS / "scripts").rglob("*.sh")) + \
        sorted((EXPERIMENTS / "runtime" / "roles").rglob("*.sh"))


@pytest.fixture(scope="module")
def sources() -> list:
    found = _sources()
    assert found, "no source files were collected: the walk is wrong"
    return [(path, path.read_text(encoding="utf-8")) for path in found]


def _relative(path: Path) -> str:
    return str(path.relative_to(EXPERIMENTS))


# ---------------------------------------------------------------------------
# no virtual clock, no scale factor
# ---------------------------------------------------------------------------

#: Every name the Shadow lineage used for "time that is not the machine's".
FORBIDDEN_NAMES = [
    "time_scale", "timescale", "time_factor", "clock_scale", "scale_factor",
    "speedup", "speed_up", "speedup_factor", "acceleration_factor",
    "virtual_time", "virtualtime", "sim_clock", "simclock", "simulated_time",
    "simulated_clock", "tick_rate", "ticks_per_second", "time_dilation",
]

FORBIDDEN = re.compile(
    r"\b(" + "|".join(re.escape(name) for name in FORBIDDEN_NAMES) + r")\b",
    re.IGNORECASE)


def test_no_time_scaling_identifier_in_python(sources):
    offenders = []
    for path, text in sources:
        for number, line in enumerate(text.splitlines(), 1):
            match = FORBIDDEN.search(line)
            if match:
                offenders.append("%s:%d uses %r" % (_relative(path), number,
                                                    match.group(1)))
    assert not offenders, (
        "a time-scaling factor is a simulated clock by another name:\n  "
        + "\n  ".join(offenders))


def test_no_time_scaling_identifier_in_shell():
    offenders = []
    for path in _shell_sources():
        for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            match = FORBIDDEN.search(line)
            if match:
                offenders.append("%s:%d uses %r" % (_relative(path), number,
                                                    match.group(1)))
    assert not offenders, "\n  ".join(offenders)


def test_no_configuration_key_declares_a_time_scale():
    """A scale factor in YAML is as bad as one in code, and easier to miss."""
    offenders = []
    for path in sorted((EXPERIMENTS / "configs").rglob("*.yaml")):
        for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            match = FORBIDDEN.search(line)
            if match:
                offenders.append("%s:%d uses %r" % (_relative(path), number,
                                                    match.group(1)))
    assert not offenders, "\n  ".join(offenders)


# ---------------------------------------------------------------------------
# the live harness must not import the simulator
# ---------------------------------------------------------------------------

def test_the_runtime_does_not_import_the_migrated_analyser(sources):
    """`runtime/` drives real processes; it has no business in Shadow's code."""
    offenders = []
    for path, text in sources:
        if not _relative(path).startswith("runtime/"):
            continue
        if re.search(r"\b(from|import)\b.*\blegacy\b", text):
            offenders.append(_relative(path))
    assert not offenders, (
        "the live harness imports the migrated Shadow analyser: %s" % offenders)


def test_nothing_imports_a_shadow_module(sources):
    offenders = []
    for path, text in sources:
        for number, line in enumerate(text.splitlines(), 1):
            if re.match(r"\s*(import|from)\s+(shadow|shadow\.)", line):
                offenders.append("%s:%d" % (_relative(path), number))
    assert not offenders, "shadow/ is imported by %s" % offenders


# ---------------------------------------------------------------------------
# durations come from the monotonic clock
# ---------------------------------------------------------------------------

class _DurationVisitor(ast.NodeVisitor):
    """Finds `time.time() - x` and `x - time.time()`.

    A duration measured with the wall clock is wrong whenever NTP steps or
    slews it mid-run, which on a run of an hour is not hypothetical.
    `time.monotonic()` is the one that cannot go backwards.
    """

    def __init__(self):
        self.found = []

    @staticmethod
    def _is_time_time(node) -> bool:
        return (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "time"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "time")

    def visit_BinOp(self, node):
        if isinstance(node.op, ast.Sub) and (
                self._is_time_time(node.left) or self._is_time_time(node.right)):
            self.found.append(node.lineno)
        self.generic_visit(node)


def test_durations_are_measured_with_a_monotonic_clock(sources):
    offenders = []
    for path, text in sources:
        try:
            tree = ast.parse(text)
        except SyntaxError:                       # pragma: no cover
            continue
        visitor = _DurationVisitor()
        visitor.visit(tree)
        offenders += ["%s:%d" % (_relative(path), line) for line in visitor.found]
    assert not offenders, (
        "a duration is computed from time.time(); use time.monotonic(), which "
        "an NTP step cannot move: %s" % offenders)


def test_absolute_timestamps_are_timezone_aware(sources):
    """`datetime.now()` with no tz writes a local time no reader can place."""
    offenders = []
    for path, text in sources:
        for number, line in enumerate(text.splitlines(), 1):
            if re.search(r"datetime\.now\(\s*\)", line):
                offenders.append("%s:%d" % (_relative(path), number))
            if re.search(r"datetime\.utcnow\(", line):
                offenders.append("%s:%d (utcnow is naive and deprecated)"
                                 % (_relative(path), number))
    assert not offenders, (
        "use datetime.now(timezone.utc): %s" % offenders)


def test_the_monotonic_clock_is_actually_used():
    """A guard on the guard: if the harness stopped measuring time at all,
    every test above would pass vacuously."""
    session = (EXPERIMENTS / "runtime" / "session.py").read_text(encoding="utf-8")
    assert "time.monotonic()" in session
    events = (EXPERIMENTS / "runtime" / "events.py").read_text(encoding="utf-8")
    assert "time.monotonic()" in events
    assert "datetime.now(timezone.utc)" in events


# ---------------------------------------------------------------------------
# epoch boundaries are observed, not synthesised
# ---------------------------------------------------------------------------

def test_no_epoch_end_is_synthesised_from_a_configured_duration():
    """`end = start + epoch_length * target_block_time` is a simulator's
    timeline: it states when the epoch *should* have ended. What the run did
    is in the block timestamps, and that is what must be reported."""
    pattern = re.compile(
        r"(epoch|epoca)\w*_?(start|inizio)\w*\s*\+\s*\w*(duration|durata|"
        r"length|target_block_time|tbt)", re.IGNORECASE)
    offenders = []
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                offenders.append("%s:%d: %s" % (_relative(path), number,
                                                line.strip()))
    assert not offenders, "\n  ".join(offenders)


def test_the_epoch_summary_reads_its_timestamps_from_observations():
    """The per-epoch table's wall-clock fields must come from the collector's
    record of the blocks, not from arithmetic over the plan."""
    from experiments.analysis import summary_per_epoca as native

    source = Path(native.__file__).read_text(encoding="utf-8")
    assert "observed_wallclock" in source, (
        "the epoch summary no longer reads the observed wall-clock field")
    assert not FORBIDDEN.search(source)


def test_the_manifest_declares_the_temporal_model():
    """Every run must say, in its own manifest, that its clock was real -
    otherwise a reader has to infer it from the branch name."""
    manifest = (EXPERIMENTS / "runtime" / "manifest.py").read_text(encoding="utf-8")
    assert "temporal_model" in manifest
    assert "wall_clock" in manifest, (
        "temporal_model must be set to a wall-clock value, not left free")


# ---------------------------------------------------------------------------
# sleeps are polling intervals, not time travel
# ---------------------------------------------------------------------------

def test_no_sleep_stands_in_for_a_whole_measurement_window(sources):
    """A bounded poll is fine. A sleep long enough to *be* the run is the
    discrete-event step in disguise: it asserts what happened over a window
    nobody watched."""
    offenders = []
    literal = re.compile(r"time\.sleep\(\s*([0-9]+(?:\.[0-9]+)?)\s*\)")
    for path, text in sources:
        for number, line in enumerate(text.splitlines(), 1):
            match = literal.search(line)
            if match and float(match.group(1)) > 60:
                offenders.append("%s:%d sleeps %ss"
                                 % (_relative(path), number, match.group(1)))
    assert not offenders, (
        "a sleep longer than a minute is not a polling interval: %s" % offenders)


def test_the_session_waits_against_the_monotonic_clock():
    """`_sleep` must be a loop against a real deadline, so an interrupt is
    noticed and a slow machine is not silently 'caught up' with."""
    source = (EXPERIMENTS / "runtime" / "session.py").read_text(encoding="utf-8")
    assert "deadline = time.monotonic()" in source
    assert "while time.monotonic() < deadline" in source
