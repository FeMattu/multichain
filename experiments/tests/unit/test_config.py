"""Configuration loading and schema validation."""

from __future__ import annotations

import json

import pytest

from experiments import config
from experiments.exit_codes import ConfigError
from experiments.paths import CONFIG_ROOT


def test_every_schema_is_valid_json():
    for path in sorted((CONFIG_ROOT / "schema").glob("*.json")):
        assert json.loads(path.read_text(encoding="utf-8"))


def test_validation_is_offline(monkeypatch):
    """A schema $ref must never reach for the network.

    The schemas carry an $id, which makes jsonschema treat their own internal
    #/definitions references as remote. If the resolver store regresses, this
    test fails instead of the harness quietly depending on DNS.
    """
    import urllib.request

    def forbidden(*args, **kwargs):
        raise AssertionError("schema validation tried to open a URL")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    document = config.load_document(CONFIG_ROOT / "network-profiles" / "degraded.yaml")
    config.validate(document, "network_profile.schema.json")


def test_yaml_and_json_are_interchangeable(tmp_path):
    payload = {"name": "x", "direction": "bidirectional", "delay": {"mean_ms": 1}}
    as_json = tmp_path / "x.json"
    as_json.write_text(json.dumps(payload), encoding="utf-8")
    as_yaml = tmp_path / "x.yaml"
    as_yaml.write_text("name: x\ndirection: bidirectional\ndelay:\n  mean_ms: 1\n",
                       encoding="utf-8")
    assert config.load_document(as_json) == config.load_document(as_yaml)


def test_missing_file_is_a_config_error(tmp_path):
    with pytest.raises(ConfigError) as caught:
        config.load_document(tmp_path / "absent.yaml")
    assert "not found" in str(caught.value)


def test_invalid_document_names_the_offending_pointer(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: Not-A-Slug\ndirection: sideways\n", encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        config.load_validated(bad, "network_profile.schema.json")
    message = str(caught.value)
    assert "failed validation" in message
    assert "direction" in message or "name" in message


def test_exit_code_of_a_config_error():
    assert ConfigError("x").exit_code == 1
