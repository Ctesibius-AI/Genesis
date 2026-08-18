from __future__ import annotations

from pathlib import Path

import pytest

from genesys.ids import (
    existing_episode_ids,
    format_episode_id,
    next_episode_id,
    next_sequence,
    parse_episode_id,
)


def test_format_is_zero_padded_and_dated():
    assert format_episode_id("2026-08-17", 3) == "EP-2026-08-17.0003"


def test_parse_round_trips():
    assert parse_episode_id("EP-2026-08-17.0003") == ("2026-08-17", 3)


def test_parse_rejects_malformed():
    with pytest.raises(ValueError):
        parse_episode_id("2026-08-17.3")


def test_next_sequence_starts_at_one_when_empty():
    assert next_sequence([], "2026-08-17") == 1


def test_next_sequence_is_max_plus_one_for_that_date_only():
    ids = ["EP-2026-08-17.0001", "EP-2026-08-17.0002", "EP-2026-08-16.0009"]
    assert next_sequence(ids, "2026-08-17") == 3


def test_next_episode_id_scans_the_episodes_dir(tmp_path: Path):
    eps = tmp_path / "episodes"
    eps.mkdir()
    (eps / "EP-2026-08-17.0001.md").write_text("x", encoding="utf-8")
    assert next_episode_id(tmp_path, "2026-08-17") == "EP-2026-08-17.0002"


def test_existing_episode_ids_empty_when_no_dir(tmp_path: Path):
    assert existing_episode_ids(tmp_path) == []
