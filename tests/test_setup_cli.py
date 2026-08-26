from __future__ import annotations

import io
import json

import pytest

from genesis import config
from genesis.setup import cli


@pytest.fixture(autouse=True)
def _isolate_identity(tmp_path, monkeypatch):
    monkeypatch.setenv(config.CONFIG_FILE_ENV, str(tmp_path / "config.json"))
    monkeypatch.delenv(config.PRINCIPAL_ENV, raising=False)
    monkeypatch.delenv(config.ASSISTANT_ENV, raising=False)


def _scripted_reader(answers):
    """Return a reader() that yields the given answers in order, then "" (accept default / decline).

    Degrading to "" past the scripted answers means these identity-focused tests don't have to
    thread an answer for the D-FB-4 redaction-key offer that run_setup now makes last — "" declines it.
    """
    it = iter(answers)

    def reader(_prompt: str) -> str:
        return next(it, "")

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


# --- D-FB-4: the redaction-key offer (consent-gated, printed once, never persisted) ---

import re  # noqa: E402


def test_setup_generates_key_on_consent_and_never_persists_it(tmp_path, monkeypatch):
    monkeypatch.delenv(config.HMAC_KEY_ENV, raising=False)
    monkeypatch.delenv("GENESYS_LOCAL_HMAC_KEY", raising=False)
    out = io.StringIO()
    cli.run_setup(reader=_scripted_reader(["Ada", "Athena", "y"]), out=out)
    text = out.getvalue()
    m = re.search(rf"export {config.HMAC_KEY_ENV}=([0-9a-f]{{64}})", text)
    assert m, "consent must print a fresh 64-hex key with an export line"
    key = m.group(1)
    assert "does NOT store it" in text
    # The key is NEVER written to disk by Genesis (config file holds identity only).
    assert key not in (tmp_path / "config.json").read_text()


def test_setup_declines_key_prints_manual_instructions(monkeypatch):
    monkeypatch.delenv(config.HMAC_KEY_ENV, raising=False)
    monkeypatch.delenv("GENESYS_LOCAL_HMAC_KEY", raising=False)
    out = io.StringIO()
    cli.run_setup(reader=_scripted_reader(["Ada", "Athena", "n"]), out=out)
    text = out.getvalue()
    assert "openssl rand -hex 32" in text          # manual path offered
    assert "export " + config.HMAC_KEY_ENV + "=" in text
    assert not re.search(rf"{config.HMAC_KEY_ENV}=[0-9a-f]{{64}}", text)  # no key generated


def test_setup_key_already_configured_is_a_noop(monkeypatch):
    monkeypatch.setenv(config.HMAC_KEY_ENV, "already-set")
    out = io.StringIO()
    cli.run_setup(reader=_scripted_reader(["Ada", "Athena"]), out=out)
    assert "already configured" in out.getvalue()
