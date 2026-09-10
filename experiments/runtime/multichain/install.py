"""Finding the MultiChain binaries and recording exactly which ones ran.

A run that cannot say which binary produced it is not reproducible, so the
manifest carries the resolved path, the SHA-256 and the reported version of
each of the three executables. Resolution order is the one documented in
``configs/multichain.yaml`` and each binary reports which rule matched, so
``env check`` can explain a surprising choice instead of just failing later.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ...exit_codes import EnvironmentError_
from ...plan import MultiChainSettings

LOG = logging.getLogger("experiments.runtime.multichain.install")

ENV_VARS = {
    "multichaind": "MULTICHAIN_BIN",
    "multichain-cli": "MULTICHAIN_CLI",
    "multichain-util": "MULTICHAIN_UTIL",
}


@dataclass
class BinaryInfo:
    name: str
    path: str
    found: bool
    origin: str
    sha256: str = ""
    version: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name, "path": self.path, "found": self.found,
            "origin": self.origin, "sha256": self.sha256, "version": self.version,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _version(path: Path, name: str) -> str:
    """Best-effort version string.

    ``multichaind --version`` prints and exits; ``multichain-util`` prints its
    banner on a bare invocation. Neither is guaranteed, so a failure here is
    recorded as an empty string rather than treated as a missing binary.
    """
    for argv in ([str(path), "--version"], [str(path)]):
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            continue
        text = (proc.stdout or proc.stderr or "").strip()
        for line in text.splitlines():
            if "version" in line.lower() or name in line:
                return line.strip()[:200]
        if text:
            return text.splitlines()[0][:200]
    return ""


def resolve_binary(name: str, settings: MultiChainSettings, explicit: str | None) -> BinaryInfo:
    """Resolve one binary, reporting which rule matched."""
    candidates: list[tuple[str, Path]] = []
    if explicit:
        candidates.append(("descriptor", Path(explicit).expanduser()))
    env_var = ENV_VARS[name]
    if os.environ.get(env_var):
        candidates.append((env_var, Path(os.environ[env_var]).expanduser()))
    base = os.environ.get("MULTICHAIN_BASE_DIR")
    if base:
        candidates.append(("MULTICHAIN_BASE_DIR", Path(base).expanduser() / name))
    if settings.bindir:
        candidates.append(("configured bindir", Path(settings.bindir) / name))
    on_path = shutil.which(name)
    if on_path:
        candidates.append(("PATH", Path(on_path)))

    for origin, path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return BinaryInfo(name=name, path=str(path), found=True, origin=origin,
                              sha256=_sha256(path), version=_version(path, name))
    tried = ", ".join("%s=%s" % (o, p) for o, p in candidates) or "nothing to try"
    return BinaryInfo(name=name, path="", found=False, origin="not found (%s)" % tried)


def resolve_all(settings: MultiChainSettings) -> dict[str, BinaryInfo]:
    """Resolve the three binaries the harness needs."""
    return {
        "multichaind": resolve_binary("multichaind", settings, settings.daemon),
        "multichain-cli": resolve_binary("multichain-cli", settings, settings.cli),
        "multichain-util": resolve_binary("multichain-util", settings, settings.util),
    }


def require_all(settings: MultiChainSettings) -> dict[str, BinaryInfo]:
    """Resolve, or fail with exit code 2 and the list of places searched."""
    resolved = resolve_all(settings)
    missing = [info for info in resolved.values() if not info.found]
    if missing:
        lines = ["the MultiChain binaries are required and were not found:"]
        for info in missing:
            lines.append("  - %s: %s" % (info.name, info.origin))
        lines.append("")
        lines.append("Build them with ./autogen.sh && ./configure && make, or point")
        lines.append("MULTICHAIN_BIN / MULTICHAIN_CLI / MULTICHAIN_UTIL at an existing build.")
        raise EnvironmentError_("\n".join(lines))
    for info in resolved.values():
        LOG.debug("%s -> %s (%s)", info.name, info.path, info.origin)
    return resolved
