"""Filesystem anchors.

Every path in the harness is derived from one of these functions, so that a
checkout can be moved and no personal absolute path is ever baked into a
versioned file. ``EXPERIMENT_ROOT`` overrides the location of the writable
results tree, which is the only directory the harness creates outside the
repository when the user asks for it.
"""

from __future__ import annotations

import os
from pathlib import Path

#: ``experiments/`` — the package directory itself.
PACKAGE_ROOT = Path(__file__).resolve().parent

#: The repository checkout that contains ``experiments/`` and ``src/``.
REPO_ROOT = PACKAGE_ROOT.parent

CONFIG_ROOT = PACKAGE_ROOT / "configs"
SCHEMA_ROOT = CONFIG_ROOT / "schema"
SCRIPTS_ROOT = PACKAGE_ROOT / "scripts"
ROLES_ROOT = PACKAGE_ROOT / "runtime" / "roles"
GENERATED_ROOT = PACKAGE_ROOT / "topology" / "generated"


def results_root() -> Path:
    """Where run directories are written.

    Defaults to ``experiments/results``; ``EXPERIMENT_ROOT`` moves it, which is
    how a large campaign is kept off the repository volume.
    """
    override = os.environ.get("EXPERIMENT_ROOT")
    return Path(override).expanduser().resolve() if override else PACKAGE_ROOT / "results"


def run_dir(run_id: str) -> Path:
    """Directory of a single run: ``<results root>/<run-id>``."""
    return results_root() / run_id
