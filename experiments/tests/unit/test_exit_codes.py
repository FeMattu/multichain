"""The exit-code table is duplicated in shell; prove the two agree."""

from __future__ import annotations

import re

from experiments import exit_codes
from experiments.paths import SCRIPTS_ROOT

SHELL_NAMES = {
    "EXIT_SUCCESS": "SUCCESS",
    "EXIT_CONFIG_ERROR": "CONFIG_ERROR",
    "EXIT_ENVIRONMENT_UNAVAILABLE": "ENVIRONMENT_UNAVAILABLE",
    "EXIT_RUNTIME_ERROR": "RUNTIME_ERROR",
    "EXIT_INCOMPLETE_DATA": "INCOMPLETE_DATA",
    "EXIT_ANALYSIS_FAILED": "ANALYSIS_FAILED",
}


def _shell_table() -> dict:
    text = (SCRIPTS_ROOT / "_common.sh").read_text(encoding="utf-8")
    return {name: int(value)
            for name, value in re.findall(r"^(EXIT_[A-Z_]+)=(\d+)$", text, re.M)}


def test_shell_and_python_agree():
    shell = _shell_table()
    assert set(shell) == set(SHELL_NAMES), "the shell table gained or lost an entry"
    for shell_name, python_name in SHELL_NAMES.items():
        assert shell[shell_name] == getattr(exit_codes, python_name), shell_name


def test_codes_are_the_documented_ones():
    assert (exit_codes.SUCCESS, exit_codes.CONFIG_ERROR,
            exit_codes.ENVIRONMENT_UNAVAILABLE, exit_codes.RUNTIME_ERROR,
            exit_codes.INCOMPLETE_DATA, exit_codes.ANALYSIS_FAILED) == (0, 1, 2, 3, 4, 5)


def test_every_error_class_carries_its_code():
    assert exit_codes.ConfigError("x").exit_code == 1
    assert exit_codes.EnvironmentError_("x").exit_code == 2
    assert exit_codes.RuntimeFailure("x").exit_code == 3
    assert exit_codes.IncompleteData("x").exit_code == 4
    assert exit_codes.AnalysisFailed("x").exit_code == 5
