"""The CORE check, and the consent gate in front of the fallback.

The property under test is negative and easy to regress: there must be **no**
path from "CORE is missing" to "a run started on netns" that does not pass
through an explicit human or an explicit flag.
"""

from __future__ import annotations

import io

import pytest

from experiments.runtime.core.environment_check import (
    CoreStatus,
    FallbackRefused,
    check_core,
    render_prompt,
    require_core_or_consent,
)


def _unusable() -> CoreStatus:
    return CoreStatus(python_api=False, python_api_detail="no module named core",
                      problems=["CORE's Python API is not installed"])


def test_check_core_reports_facts_and_decides_nothing():
    status = check_core()
    assert isinstance(status.usable, bool)
    assert isinstance(status.problems, list)
    if not status.usable:
        assert status.problems, "unusable without a stated reason is not a report"


def test_an_explicit_netns_choice_never_consults_core(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("CORE was probed for an explicit netns request")

    monkeypatch.setattr(
        "experiments.runtime.core.environment_check.check_core",
        lambda *a, **k: _unusable())
    backend, _ = require_core_or_consent(requested_backend="netns")
    assert backend == "netns"


def test_a_non_interactive_session_refuses_without_the_flag(monkeypatch):
    monkeypatch.setattr(
        "experiments.runtime.core.environment_check.check_core",
        lambda *a, **k: _unusable())
    stream = io.StringIO()          # not a tty
    with pytest.raises(FallbackRefused) as caught:
        require_core_or_consent(requested_backend="auto", stream=stream)
    assert caught.value.exit_code == 2
    assert "not interactive" in str(caught.value)
    assert "--allow-fallback-without-core" in caught.value.hint
    assert stream.getvalue() == "", "it must not prompt where nobody can answer"


def test_the_flag_authorises_the_fallback(monkeypatch):
    monkeypatch.setattr(
        "experiments.runtime.core.environment_check.check_core",
        lambda *a, **k: _unusable())
    backend, status = require_core_or_consent(
        requested_backend="auto", allow_fallback=True, stream=io.StringIO())
    assert backend == "netns"
    assert not status.usable


def test_an_explicit_core_backend_fails_rather_than_degrading(monkeypatch):
    from experiments.exit_codes import EnvironmentError_

    monkeypatch.setattr(
        "experiments.runtime.core.environment_check.check_core",
        lambda *a, **k: _unusable())
    with pytest.raises(EnvironmentError_) as caught:
        require_core_or_consent(requested_backend="core", stream=io.StringIO())
    assert caught.value.exit_code == 2
    assert "core" in str(caught.value)


def test_core_is_used_when_it_is_usable(monkeypatch):
    usable = CoreStatus(python_api=True, daemon_reachable=True, netns_usable=True,
                        daemon_detail="answered")
    monkeypatch.setattr(
        "experiments.runtime.core.environment_check.check_core",
        lambda *a, **k: usable)
    backend, _ = require_core_or_consent(requested_backend="auto")
    assert backend == "core"


def test_the_prompt_states_what_is_given_up():
    """'Lower fidelity' on its own is not informed consent."""
    text = render_prompt(_unusable(), "netns")
    assert "[y/N]" in text
    assert "What you give up" in text
    assert "What does NOT change" in text
    for kept in ("netem", "multichaind"):
        assert kept in text


def test_no_module_offers_a_silent_fallback():
    """A grep-level guard: the old code path must not come back."""


    from experiments.paths import PACKAGE_ROOT

    factory = (PACKAGE_ROOT / "runtime" / "fabric" / "factory.py").read_text()
    assert "require_core_or_consent" in factory
    # The previous implementation logged and continued; make sure nothing does.
    assert "auto; CORE unavailable" not in factory
