"""Shared fixtures and capability markers.

Three capabilities decide what can run here, and each is detected rather than
assumed: root (or passwordless sudo) for the fabric, the MultiChain binaries
for a real run, and a reachable CORE daemon for that backend. A test that
needs one it does not have **skips with the reason**, so an incomplete
environment produces a short honest report rather than a wall of red.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from experiments.paths import REPO_ROOT  # noqa: E402
from experiments.plan import build_plan  # noqa: E402


def _has_privileges() -> bool:
    if os.geteuid() == 0:
        return True
    sudo = shutil.which("sudo")
    if not sudo:
        return False
    return subprocess.run([sudo, "-n", "true"], capture_output=True).returncode == 0


def _has_multichain() -> bool:
    from experiments.runtime.multichain.install import resolve_all

    try:
        plan = build_plan(REPO_ROOT / "experiments/configs/experiments/smoke-3n.yaml")
    except Exception:  # noqa: BLE001
        return False
    return all(info.found for info in resolve_all(plan.multichain).values())


def _has_core() -> bool:
    from experiments.runtime.fabric.core_emulator import import_core

    modules, _ = import_core()
    return modules is not None


HAS_PRIVILEGES = _has_privileges()
HAS_MULTICHAIN = _has_multichain()
HAS_CORE = _has_core()


def pytest_configure(config):
    for marker, description in (
        ("requires_root", "needs CAP_NET_ADMIN to create namespaces and apply tc"),
        ("requires_multichain", "needs the MultiChain binaries"),
        ("requires_core", "needs a reachable CORE Network Emulator daemon"),
        ("slow", "takes more than a few seconds"),
    ):
        config.addinivalue_line("markers", "%s: %s" % (marker, description))


def pytest_collection_modifyitems(config, items):
    del config
    skip_root = pytest.mark.skip(
        reason="needs root or passwordless sudo to create network namespaces")
    skip_mc = pytest.mark.skip(
        reason="the MultiChain binaries were not found; build them or set MULTICHAIN_BIN")
    skip_core = pytest.mark.skip(
        reason="CORE's Python API is not importable; install CORE")
    for item in items:
        if "requires_root" in item.keywords and not HAS_PRIVILEGES:
            item.add_marker(skip_root)
        if "requires_multichain" in item.keywords and not HAS_MULTICHAIN:
            item.add_marker(skip_mc)
        if "requires_core" in item.keywords and not HAS_CORE:
            item.add_marker(skip_core)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def smoke_descriptor(repo_root) -> Path:
    return repo_root / "experiments/configs/experiments/smoke-3n.yaml"


@pytest.fixture(scope="session")
def regional_descriptor(repo_root) -> Path:
    return repo_root / "experiments/configs/experiments/regional.yaml"


@pytest.fixture
def smoke_plan(smoke_descriptor):
    return build_plan(smoke_descriptor)


@pytest.fixture
def synthetic_run(tmp_path, smoke_descriptor):
    """A complete synthetic run directory, built fresh for each test."""
    from experiments.tests.fixtures.make_run import build_synthetic_run

    return build_synthetic_run(tmp_path / "run-fixture", descriptor=smoke_descriptor)
