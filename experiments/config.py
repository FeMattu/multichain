"""Loading and schema validation of every configuration file.

YAML and JSON are both accepted everywhere: the schemas describe the data, not
the serialisation. Validation happens once, at load time, and an invalid file
raises :class:`ConfigError` with the JSON-pointer path of the offending value —
never a stack trace from deep inside the runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .exit_codes import ConfigError
from .paths import REPO_ROOT, SCHEMA_ROOT

try:
    import yaml
except ImportError:  # pragma: no cover - declared in requirements.txt
    yaml = None

try:
    import jsonschema
except ImportError:  # pragma: no cover - declared in requirements.txt
    jsonschema = None

_SCHEMA_STORE: dict | None = None


def load_document(path: Path | str) -> Any:
    """Read a YAML or JSON document, chosen by suffix."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(
            "configuration file not found: %s" % path,
            hint="paths in an experiment descriptor are resolved against the "
                 "repository root unless absolute",
        )
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        if yaml is None:
            raise ConfigError("PyYAML is required to read %s (pip install -r experiments/requirements.txt)" % path)
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:  # pragma: no cover - message passthrough
            raise ConfigError("%s is not valid YAML: %s" % (path, exc)) from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError("%s is not valid JSON: %s" % (path, exc)) from exc


def load_schema(name: str) -> dict:
    """Read one schema from ``configs/schema/``."""
    return json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))



def _schema_store() -> dict:
    """Every local schema, keyed by both its ``$id`` and its file URI.

    Without this the ``$id`` of a schema makes ``jsonschema`` treat internal
    ``#/definitions`` references as remote and try to fetch them over HTTP.
    Validation must never depend on the network.
    """
    global _SCHEMA_STORE
    if _SCHEMA_STORE is None:
        store = {}
        for path in sorted(SCHEMA_ROOT.glob("*.schema.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            store[path.as_uri()] = document
            store[path.name] = document
            if "$id" in document:
                store[document["$id"]] = document
        _SCHEMA_STORE = store
    return _SCHEMA_STORE


def _resolver(schema: dict):
    """Offline ``$ref`` resolver rooted at ``configs/schema/``."""
    return jsonschema.RefResolver(
        base_uri=SCHEMA_ROOT.as_uri() + "/",
        referrer=schema,
        store=_schema_store(),
    )


def validate(document: Any, schema_name: str, *, origin: str = "<document>") -> None:
    """Validate against a schema, raising :class:`ConfigError` on the first failure.

    Cross-file ``$ref`` (experiment -> node) is resolved from ``SCHEMA_ROOT``.
    A missing ``jsonschema`` is reported once and treated as a hard error: a
    silently unvalidated configuration is exactly what this harness must not do.
    """
    if jsonschema is None:
        raise ConfigError(
            "jsonschema is required to validate %s" % origin,
            hint="pip install -r experiments/requirements.txt",
        )
    schema = load_schema(schema_name)
    validator = jsonschema.Draft7Validator(schema, resolver=_resolver(schema))
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        pointer = "/".join(str(p) for p in first.absolute_path) or "(root)"
        extra = "" if len(errors) == 1 else " (+%d more)" % (len(errors) - 1)
        raise ConfigError(
            "%s failed validation against %s at %s: %s%s"
            % (origin, schema_name, pointer, first.message, extra)
        )


def resolve_path(value: str | Path, *, base: Path | None = None) -> Path:
    """Resolve a configured path.

    Absolute paths are taken as they are; relative ones are resolved against
    ``base`` (usually the descriptor's own directory) and then, as a fallback,
    against the repository root. That second attempt is what lets a descriptor
    say ``experiments/configs/topologies/regional.yaml`` and still be loadable
    from any working directory.
    """
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate
    if base is not None:
        local = (base / candidate).resolve()
        if local.exists():
            return local
    return (REPO_ROOT / candidate).resolve()


def load_validated(path: Path | str, schema_name: str) -> Any:
    """Load a document and validate it in one step."""
    path = Path(path)
    document = load_document(path)
    validate(document, schema_name, origin=str(path))
    return document
