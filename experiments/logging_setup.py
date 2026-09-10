"""Structured logging shared by the CLI, the runtime and the analysis.

One line per event, ``key=value`` pairs after the message, so that a run log
can be grepped and parsed without a JSON reader. A file handler is added
whenever a run directory is known, so every run keeps its own log next to its
artefacts.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)-22s %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def setup(verbose: bool = False, logfile: Path | None = None) -> None:
    """Configure the root logger once; repeated calls only add the file sink."""
    root = logging.getLogger()
    if not root.handlers:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        root.addHandler(stream)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    if logfile is not None:
        logfile.parent.mkdir(parents=True, exist_ok=True)
        already = any(
            isinstance(h, logging.FileHandler)
            and Path(getattr(h, "baseFilename", "")) == logfile.resolve()
            for h in root.handlers
        )
        if not already:
            handler = logging.FileHandler(logfile, encoding="utf-8")
            handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
            root.addHandler(handler)


def kv(**fields: Any) -> str:
    """Render structured fields for a log message: ``kv(host="m1", rc=0)``."""
    parts = []
    for key, value in fields.items():
        text = "" if value is None else str(value)
        if any(ch.isspace() for ch in text):
            text = '"%s"' % text.replace('"', "'")
        parts.append("%s=%s" % (key, text))
    return " ".join(parts)
