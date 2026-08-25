from __future__ import annotations

from pathlib import Path

import pytest

from genesis.journal.journal import (
    JOURNAL_ACTIONS,
    JournalEntry,
    append_journal,
    from_jsonl,
    read_journal,
    to_jsonl,
)


def _e(action="verdict", ts="2026-08-17T10:00:00+00:00", **kw) -> JournalEntry:
    return JournalEntry(ts=ts, action=action, scope="EP-2026-08-17.0001", **kw)


def test_union_has_the_core_action_types():
    for a in ("verdict", "revert", "supersede", "contest",
              "scrub", "redact", "day-processed", "stale-lock-cleared"):
        assert a in JOURNAL_ACTIONS


def test_persona_actions_removed_from_union():
    # BT-4b / D-GCW-6: persona-layer + calibration/constitution actions removed with the profiler.
    for a in ("perceive", "alignment", "opinion-release", "backlog-breach",
              "discussion-request", "rotation", "constitution-refresh"):
        assert a not in JOURNAL_ACTIONS


def test_class_key_serializes_as_class_not_class_():
    line = to_jsonl(_e(class_="C3"))
    assert '"class":"C3"' in line
    assert "class_" not in line


def test_jsonl_round_trip():
    e = _e(action="revert", target="edge-1", evidence=["EP-2026-08-16.0002"], author="supervisor")
    back = from_jsonl(to_jsonl(e))
    assert back == e


def test_append_rejects_unknown_action(tmp_path: Path):
    with pytest.raises(ValueError):
        append_journal(tmp_path, _e(action="not-a-real-action"))


def test_append_is_day_indexed_and_readable(tmp_path: Path):
    append_journal(tmp_path, _e(ts="2026-08-17T11:00:00+00:00", action="supersede"))
    append_journal(tmp_path, _e(ts="2026-08-17T10:00:00+00:00", action="verdict"))
    assert (tmp_path / "journal" / "2026-08-17.jsonl").exists()
    assert [e.action for e in read_journal(tmp_path)] == ["verdict", "supersede"]  # ts order
