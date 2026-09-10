"""Finding the MultiChain binaries, and refusing to substitute one silently."""

from __future__ import annotations


import stat

import pytest

from experiments.paths import CONFIG_ROOT
from experiments.plan import build_plan
from experiments.runtime.multichain.install import require_all, resolve_all, resolve_binary


@pytest.fixture
def settings():
    return build_plan(CONFIG_ROOT / "experiments" / "smoke-3n.yaml").multichain


def _fake_binary(directory, name):
    path = directory / name
    path.write_text("#!/bin/sh\necho fake\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def test_the_descriptor_declares_but_does_not_resolve():
    """Resolution belongs to install; the plan only carries what was declared.

    Chaining two resolvers is what made a wrong MULTICHAIN_BASE_DIR a hard
    failure instead of a fall-through.
    """
    plan = build_plan(CONFIG_ROOT / "experiments" / "smoke-3n.yaml")
    assert plan.multichain.daemon == ""


def test_default_resolution_finds_the_repository_build(settings):
    resolved = resolve_all(settings)
    for name, info in resolved.items():
        if info.found:
            assert info.origin in ("configured bindir", "PATH", "MULTICHAIN_BASE_DIR"), name


def test_an_explicit_env_var_is_honoured(monkeypatch, tmp_path, settings):
    fake = _fake_binary(tmp_path, "multichaind")
    monkeypatch.setenv("MULTICHAIN_BIN", str(fake))
    info = resolve_binary("multichaind", settings, None)
    assert info.found
    assert info.path == str(fake)
    assert info.origin == "MULTICHAIN_BIN"


def test_an_explicit_env_var_that_is_wrong_is_refused(monkeypatch, tmp_path, settings):
    """Never substitute. Falling back would run a different binary than asked."""
    monkeypatch.setenv("MULTICHAIN_BIN", str(tmp_path / "absent"))
    info = resolve_binary("multichaind", settings, None)
    assert not info.found
    assert "explicitly requested" in info.origin
    assert "is not a file" in info.origin


def test_a_non_executable_explicit_path_is_refused(monkeypatch, tmp_path, settings):
    path = tmp_path / "multichaind"
    path.write_text("not executable", encoding="utf-8")
    path.chmod(0o644)
    monkeypatch.setenv("MULTICHAIN_BIN", str(path))
    info = resolve_binary("multichaind", settings, None)
    assert not info.found
    assert "is not executable" in info.origin


def test_a_descriptor_path_that_is_wrong_is_refused(tmp_path, settings):
    info = resolve_binary("multichaind", settings, str(tmp_path / "absent"))
    assert not info.found
    assert info.origin.startswith("descriptor explicitly requested")


def test_base_dir_is_a_default_and_falls_through(monkeypatch, settings):
    """MULTICHAIN_BASE_DIR is a search location, not a request for one file."""
    monkeypatch.setenv("MULTICHAIN_BASE_DIR", "/nonexistent-base-dir")
    info = resolve_binary("multichaind", settings, None)
    if info.found:
        assert info.origin != "MULTICHAIN_BASE_DIR"
    else:
        assert "not found" in info.origin


def test_base_dir_is_used_when_it_is_right(monkeypatch, tmp_path, settings):
    _fake_binary(tmp_path, "multichaind")
    monkeypatch.setenv("MULTICHAIN_BASE_DIR", str(tmp_path))
    info = resolve_binary("multichaind", settings, None)
    assert info.found
    assert info.origin == "MULTICHAIN_BASE_DIR"


def test_a_found_binary_is_fingerprinted(monkeypatch, tmp_path, settings):
    """The manifest must be able to say exactly which binary ran."""
    fake = _fake_binary(tmp_path, "multichaind")
    monkeypatch.setenv("MULTICHAIN_BIN", str(fake))
    info = resolve_binary("multichaind", settings, None)
    assert len(info.sha256) == 64


def test_require_all_lists_every_place_it_looked(monkeypatch, tmp_path, settings):
    from experiments.exit_codes import EnvironmentError_

    monkeypatch.setenv("MULTICHAIN_BIN", str(tmp_path / "absent"))
    with pytest.raises(EnvironmentError_) as caught:
        require_all(settings)
    message = str(caught.value)
    assert "multichaind" in message
    assert "MULTICHAIN_BIN" in message
    assert caught.value.exit_code == 2


def test_env_vars_are_the_documented_ones():
    from experiments.runtime.multichain.install import ENV_VARS

    assert ENV_VARS == {
        "multichaind": "MULTICHAIN_BIN",
        "multichain-cli": "MULTICHAIN_CLI",
        "multichain-util": "MULTICHAIN_UTIL",
    }
