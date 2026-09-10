"""Process exit codes shared by the CLI and the shell scripts.

The same table is duplicated in ``scripts/_common.sh``; the two are kept in
sync by ``tests/unit/test_exit_codes.py``, which parses the shell file.
"""

from __future__ import annotations

SUCCESS = 0
CONFIG_ERROR = 1
ENVIRONMENT_UNAVAILABLE = 2
RUNTIME_ERROR = 3
INCOMPLETE_DATA = 4
ANALYSIS_FAILED = 5

NAMES = {
    SUCCESS: "success",
    CONFIG_ERROR: "configuration error",
    ENVIRONMENT_UNAVAILABLE: "environment unavailable",
    RUNTIME_ERROR: "runtime error",
    INCOMPLETE_DATA: "incomplete data",
    ANALYSIS_FAILED: "analysis failed",
}


class ExperimentError(Exception):
    """Base error carrying the exit code the CLI must return."""

    exit_code = RUNTIME_ERROR

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.hint = hint


class ConfigError(ExperimentError):
    """Malformed or inconsistent configuration."""

    exit_code = CONFIG_ERROR


class EnvironmentError_(ExperimentError):
    """A mandatory external component (CORE, MultiChain, tc, root) is missing."""

    exit_code = ENVIRONMENT_UNAVAILABLE


class RuntimeFailure(ExperimentError):
    """The emulated network or a MultiChain process failed at run time."""

    exit_code = RUNTIME_ERROR


class IncompleteData(ExperimentError):
    """A run produced fewer artefacts than the metric extractors require."""

    exit_code = INCOMPLETE_DATA


class AnalysisFailed(ExperimentError):
    """The statistical pipeline could not complete."""

    exit_code = ANALYSIS_FAILED
