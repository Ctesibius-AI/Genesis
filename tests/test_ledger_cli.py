"""Fixtures-only CLI tests for P1 save + doctor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from genesys.config import ConfigError, get_data_root
from genesys.ledger.cli import main
from genesys.ledger.store import read_all


def _fixture(tmp_path: Path) -> Path:
    payload = {
        "raw_span": "the principal: use FalkorDB Lite. Daimon: agreed.",
        "summary": "Decided on FalkorDB Lite.",
        "session_id": "sess-1",
        "speakers": ["the principal", "Daimon"],
        "span_start": "2026-08-17T09:58:00+00:00",
        "span_end": "2026-08-17T10:00:00+00:00",
        "ts": "2026-08-17T10:00:00+00:00",
    }
    p = tmp_path / "save.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_get_data_root_requires_env(monkeypatch):
    monkeypatch.delenv("GENESYS_DATA", raising=False)
    with pytest.raises(ConfigError):
        get_data_root()


def test_get_data_root_reads_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GENESYS_DATA", str(tmp_path))
    assert get_data_root() == tmp_path


def test_cli_save_persists_entry(tmp_path: Path):
    data = tmp_path / "data"
    rc = main(["save", str(_fixture(tmp_path)), "--data", str(data)])
    assert rc == 0
    assert [e.entry_id for e in read_all(data)] == ["EP-2026-08-17.0001"]


def test_cli_doctor_runs_clean(tmp_path: Path):
    data = tmp_path / "data"
    main(["save", str(_fixture(tmp_path)), "--data", str(data)])
    rc = main(["doctor", "--data", str(data)])
    assert rc == 0
