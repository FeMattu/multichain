"""Bridges between the new run layout and the migrated analysis pipeline."""

from .run_adapter import (  # noqa: F401
    discover_native_runs,
    is_native_run,
    write_compat_inputs,
)
