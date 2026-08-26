"""BT-1 (D-GCW-2): per-workspace store env-pinning is fail-loud, never /tmp.

AC-I1/AC-ISO1: GENESIS_DB_PATH / GENESIS_GROUP_ID must be explicit; an unset value is a loud
ConfigError, not a silent ephemeral graph.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from genesis.config import ConfigError, get_data_root, get_db_path, get_group_id


# --- D-GCW-20 rename migration: old GENESYS_* names accepted for one release, with a warning ---

def test_legacy_genesys_env_name_is_accepted_with_deprecation(monkeypatch):
    monkeypatch.delenv("GENESIS_DATA", raising=False)
    monkeypatch.setenv("GENESYS_DATA", "/legacy/root")
    with pytest.warns(DeprecationWarning):
        assert get_data_root() == Path("/legacy/root")


def test_new_genesis_env_name_wins_without_warning(monkeypatch, recwarn):
    monkeypatch.setenv("GENESIS_DATA", "/new/root")
    monkeypatch.setenv("GENESYS_DATA", "/legacy/root")
    assert get_data_root() == Path("/new/root")
    assert not any(isinstance(w.message, DeprecationWarning) for w in recwarn.list)


def test_both_names_unset_still_fails_loud(monkeypatch):
    monkeypatch.delenv("GENESIS_DB_PATH", raising=False)
    monkeypatch.delenv("GENESYS_DB_PATH", raising=False)
    with pytest.raises(ConfigError):  # no silent /tmp graph even under the fallback path
        get_db_path()


# --- D-FB-2: GENESIS_DATA is the sole canonical data-root var; GENESIS_DATA_ROOT retired (1 release) ---

def test_legacy_data_root_name_accepted_with_deprecation(monkeypatch):
    """The retired GENESIS_DATA_ROOT is accepted for one release, with a DeprecationWarning."""
    monkeypatch.delenv("GENESIS_DATA", raising=False)
    monkeypatch.delenv("GENESYS_DATA", raising=False)
    monkeypatch.setenv("GENESIS_DATA_ROOT", "/old/root")
    with pytest.warns(DeprecationWarning):
        assert get_data_root() == Path("/old/root")


def test_canonical_data_root_wins_over_legacy_without_warning(monkeypatch, recwarn):
    """GENESIS_DATA (canonical) always wins over the deprecated GENESIS_DATA_ROOT — no warning."""
    monkeypatch.setenv("GENESIS_DATA", "/canonical/root")
    monkeypatch.setenv("GENESIS_DATA_ROOT", "/old/root")
    assert get_data_root() == Path("/canonical/root")
    assert not any(isinstance(w.message, DeprecationWarning) for w in recwarn.list)


def test_data_root_all_names_unset_fails_loud(monkeypatch):
    monkeypatch.delenv("GENESIS_DATA", raising=False)
    monkeypatch.delenv("GENESYS_DATA", raising=False)
    monkeypatch.delenv("GENESIS_DATA_ROOT", raising=False)
    with pytest.raises(ConfigError):  # neither canonical nor deprecated set → loud, never a guess
        get_data_root()


def test_db_path_unset_fails_loud(monkeypatch):
    monkeypatch.delenv("GENESIS_DB_PATH", raising=False)
    with pytest.raises(ConfigError):
        get_db_path()


def test_db_path_set_returns_path(monkeypatch):
    monkeypatch.setenv("GENESIS_DB_PATH", "/ws/genesis.db")
    assert get_db_path() == Path("/ws/genesis.db")


def test_group_id_unset_fails_loud(monkeypatch):
    monkeypatch.delenv("GENESIS_GROUP_ID", raising=False)
    with pytest.raises(ConfigError):
        get_group_id()


def test_group_id_blank_fails_loud(monkeypatch):
    monkeypatch.setenv("GENESIS_GROUP_ID", "   ")
    with pytest.raises(ConfigError):
        get_group_id()


def test_group_id_set_is_stripped(monkeypatch):
    monkeypatch.setenv("GENESIS_GROUP_ID", "  ws-alpha  ")
    assert get_group_id() == "ws-alpha"
