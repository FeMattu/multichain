"""The run wrapper and the CLI duplicate an interface; prove they agree.

``run_experiment.sh`` is how every document tells you to start a run, so an
option the CLI understands and the wrapper rejects is an option that, in
practice, does not exist. That is how ``--allow-fallback-without-core``
shipped unusable: it was added to the parser and not to the wrapper.

These tests drive the real script with a stub interpreter in place of
``python3``, so they check what the wrapper actually sends rather than what
its source looks like.
"""

from __future__ import annotations

import os
import subprocess

import pytest

from experiments.cli import build_parser
from experiments.paths import CONFIG_ROOT, REPO_ROOT, SCRIPTS_ROOT

SCRIPT = SCRIPTS_ROOT / "run_experiment.sh"
EXPERIMENT = CONFIG_ROOT / "experiments" / "smoke-3n.yaml"

#: Options of the CLI itself, not of a subcommand, that answer a question the
#: harness would otherwise refuse to answer for you. The wrapper must accept
#: each one and put it *before* the subcommand, where argparse expects it.
CONSENT_FLAGS = {"--allow-fallback-without-core", "--yes"}

STUB = """#!/usr/bin/env bash
# Stands in for `python3 -m experiments.cli`: records the invocation, and
# behaves like a run that produced a run id.
printf '%s\\n' "$*" >> "$ARGV_LOG"
case "$*" in
    *"experiment run"*) echo "run id: run-stub-0001"; exit ${STUB_RUN_RC:-0} ;;
esac
exit 0
"""


def _run(tmp_path, *args, rc_of_run: int = 0):
    """Drive the wrapper with the stub; return (exit code, [invocations])."""
    stub = tmp_path / "pystub"
    stub.write_text(STUB, encoding="utf-8")
    stub.chmod(0o755)
    log = tmp_path / "argv.log"
    env = dict(os.environ, PYTHON=str(stub), ARGV_LOG=str(log),
               STUB_RUN_RC=str(rc_of_run))
    completed = subprocess.run(
        [str(SCRIPT), "--experiment", str(EXPERIMENT), *args],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120)
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return completed, calls


def _the_run_call(calls: list[str]) -> str:
    matching = [c for c in calls if "experiment run" in c]
    assert len(matching) == 1, "expected exactly one `experiment run`: %s" % calls
    return matching[0]


def test_the_consent_flags_are_the_ones_the_wrapper_knows():
    """Gain a consent flag and this fails until the wrapper learns it too."""
    parser = build_parser()
    globals_ = {option
                for action in parser._actions
                for option in action.option_strings
                if action.dest in {"allow_fallback", "assume_yes"}}
    assert globals_ == CONSENT_FLAGS


@pytest.mark.parametrize("flag", sorted(CONSENT_FLAGS))
def test_a_consent_flag_reaches_the_cli_ahead_of_the_subcommand(tmp_path, flag):
    completed, calls = _run(tmp_path, flag)
    assert completed.returncode == 0, completed.stderr
    call = _the_run_call(calls)
    assert flag in call, "the wrapper swallowed %s" % flag
    assert call.index(flag) < call.index("experiment run"), \
        "%s is an option of the CLI, not of the subcommand: %s" % (flag, call)


def test_nothing_is_added_when_nothing_is_asked_for(tmp_path):
    """The gate must stay armed by default; silence is the whole point."""
    _, calls = _run(tmp_path)
    call = _the_run_call(calls)
    for flag in CONSENT_FLAGS:
        assert flag not in call


def test_a_failed_run_still_reaches_the_cleanup(tmp_path):
    """`set +e` does not disarm an ERR trap, and this trap exits.

    When it fired, the script left the run's leftover qdiscs in place - the
    thing the cleanup exists to prevent - and reported an internal line
    number instead of the failure.
    """
    completed, calls = _run(tmp_path, rc_of_run=3)
    assert completed.returncode == 3
    assert "failed at line" not in completed.stderr, completed.stderr
    assert "its logs and partial results are kept" in completed.stderr
    assert sum("results clean" in c for c in calls) == 2, \
        "the post-run fabric cleanup did not run: %s" % calls


def test_a_run_that_never_started_is_not_analysed(tmp_path):
    """Exit 2 leaves a manifest and no data; analysing it invents failures."""
    completed, calls = _run(tmp_path, rc_of_run=2)
    assert completed.returncode == 2
    assert "the run did not start" in completed.stderr
    assert not [c for c in calls if "analysis run" in c or "report generate" in c]
