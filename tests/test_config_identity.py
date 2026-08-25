from __future__ import annotations

import json

import pytest

from genesis import config


@pytest.fixture(autouse=True)
def _isolate_identity(tmp_path, monkeypatch):
    """Point the config file at a temp dir and clear identity env vars.

    Keeps every test independent of the developer's real ~/.genesis/config.json
    and of any exported GENESIS_PRINCIPAL / GENESIS_ASSISTANT.
    """
    monkeypatch.setenv(config.CONFIG_FILE_ENV, str(tmp_path / "config.json"))
    monkeypatch.delenv(config.PRINCIPAL_ENV, raising=False)
    monkeypatch.delenv(config.ASSISTANT_ENV, raising=False)


def test_defaults_when_nothing_configured():
    assert config.get_principal() == config.DEFAULT_PRINCIPAL
    assert config.get_assistant_name() == "Daimon"


def test_env_var_wins_over_file(tmp_path, monkeypatch):
    config.write_identity_config("Fromfile", "Filebot")
    monkeypatch.setenv(config.PRINCIPAL_ENV, "Fromenv")
    monkeypatch.setenv(config.ASSISTANT_ENV, "Envbot")
    assert config.get_principal() == "Fromenv"
    assert config.get_assistant_name() == "Envbot"


def test_config_file_is_read_when_env_unset():
    path = config.write_identity_config("Ada", "Athena")
    assert config.get_principal() == "Ada"
    assert config.get_assistant_name() == "Athena"
    # File is valid JSON with the expected keys.
    data = json.loads(path.read_text())
    assert data["principal"] == "Ada" and data["assistant"] == "Athena"


def test_malformed_config_file_degrades_to_defaults(tmp_path, monkeypatch):
    p = tmp_path / "bad.json"
    p.write_text("{not json")
    monkeypatch.setenv(config.CONFIG_FILE_ENV, str(p))
    assert config.get_principal() == config.DEFAULT_PRINCIPAL
    assert config.get_assistant_name() == "Daimon"


def test_write_merges_unrelated_keys(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"other": "keep-me"}))
    monkeypatch.setenv(config.CONFIG_FILE_ENV, str(p))
    config.write_identity_config("Ada", "Athena")
    data = json.loads(p.read_text())
    assert data["other"] == "keep-me"
    assert data["principal"] == "Ada"


def test_blank_env_var_falls_through_to_default(monkeypatch):
    monkeypatch.setenv(config.PRINCIPAL_ENV, "   ")
    assert config.get_principal() == config.DEFAULT_PRINCIPAL
