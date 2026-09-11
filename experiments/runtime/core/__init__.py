"""CORE availability, and the consent gate in front of any fallback."""

from .environment_check import (  # noqa: F401
    CoreStatus,
    FallbackRefused,
    check_core,
    require_core_or_consent,
)
