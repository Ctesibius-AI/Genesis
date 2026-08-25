"""BT-1 (D-GCW-2): per-workspace store env-pinning is fail-loud, never /tmp.

AC-I1/AC-ISO1: GENESYS_DB_PATH / GENESYS_GROUP_ID must be explicit; an unset value is a loud
ConfigError, not a silent ephemeral graph.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from genesys.config import ConfigError, get_db_path, get_group_id


def test_db_path_unset_fails_loud(monkeypatch):
    monkeypatch.delenv("GENESYS_DB_PATH", raising=False)
    with pytest.raises(ConfigError):
        get_db_path()


def test_db_path_set_returns_path(monkeypatch):
    monkeypatch.setenv("GENESYS_DB_PATH", "/ws/genesys.db")
    assert get_db_path() == Path("/ws/genesys.db")


def test_group_id_unset_fails_loud(monkeypatch):
    monkeypatch.delenv("GENESYS_GROUP_ID", raising=False)
    with pytest.raises(ConfigError):
        get_group_id()


def test_group_id_blank_fails_loud(monkeypatch):
    monkeypatch.setenv("GENESYS_GROUP_ID", "   ")
    with pytest.raises(ConfigError):
        get_group_id()


def test_group_id_set_is_stripped(monkeypatch):
    monkeypatch.setenv("GENESYS_GROUP_ID", "  ws-alpha  ")
    assert get_group_id() == "ws-alpha"
