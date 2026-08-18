from __future__ import annotations

import io
import json

import pytest

from genesys import config
from genesys.setup import cli


@pytest.fixture(autouse=True)
def _isolate_identity(tmp_path, monkeypatch):
    monkeypatch.setenv(config.CONFIG_FILE_ENV, str(tmp_path / "config.json"))
    monkeypatch.delenv(config.PRINCIPAL_ENV, raising=False)
    monkeypatch.delenv(config.ASSISTANT_ENV, raising=False)


def _scripted_reader(answers):
    """Return a reader() that yields the given answers in order."""
    it = iter(answers)

    def reader(_prompt: str) -> str:
        return next(it)

    return reader


def test_run_setup_persists_entered_values():
    out = io.StringIO()
    result = cli.run_setup(reader=_scripted_reader(["Ada", "Athena"]), out=out)
    assert result["principal"] == "Ada"
    assert result["assistant"] == "Athena"
    assert config.get_principal() == "Ada"
    assert config.get_assistant_name() == "Athena"


def test_blank_answers_accept_defaults():
    out = io.StringIO()
    result = cli.run_setup(reader=_scripted_reader(["", ""]), out=out)
    assert result["principal"] == config.DEFAULT_PRINCIPAL
    assert result["assistant"] == "Daimon"


def test_eof_uses_default():
    def reader(_prompt: str) -> str:
        raise EOFError

    out = io.StringIO()
    result = cli.run_setup(reader=reader, out=out)
    assert result["principal"] == config.DEFAULT_PRINCIPAL
    assert result["assistant"] == "Daimon"


def test_main_non_interactive_flags_write_config(tmp_path, monkeypatch, capsys):
    rc = cli.main(["--principal", "Grace", "--assistant", "Oracle"])
    assert rc == 0
    assert config.get_principal() == "Grace"
    assert config.get_assistant_name() == "Oracle"
    data = json.loads((tmp_path / "config.json").read_text())
    assert data["principal"] == "Grace" and data["assistant"] == "Oracle"


def test_setup_reoffers_existing_values_as_defaults():
    config.write_identity_config("Ada", "Athena")
    out = io.StringIO()
    # Blank both answers -> should keep the previously-saved values.
    result = cli.run_setup(reader=_scripted_reader(["", ""]), out=out)
    assert result["principal"] == "Ada"
    assert result["assistant"] == "Athena"
