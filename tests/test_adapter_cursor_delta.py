"""dispatch cursor-delta: Stop-then-SessionEnd over the same transcript is idempotent (§2.2/§7)."""
from __future__ import annotations

import json
from pathlib import Path

from genesys.hooks.adapter import dispatch
from genesys.ledger.store import read_all

NOW = "2026-08-18T12:00:00+00:00"


def _transcript(tmp_path: Path) -> Path:
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps({
        "type": "user",
        "message": {"role": "user", "content": "hello genesys"},
    }) + "\n", encoding="utf-8")
    return p


def _hook(event, transcript, session_id="s1"):
    return {"hook_event_name": event, "transcript_path": str(transcript),
            "session_id": session_id}


def test_stop_then_sessionend_same_transcript_saves_once(tmp_path: Path):
    t = _transcript(tmp_path)
    r1 = dispatch(_hook("Stop", t), tmp_path, now=NOW, cursor_delta=True)
    r2 = dispatch(_hook("SessionEnd", t), tmp_path, now=NOW, cursor_delta=True)
    assert "entry_id" in r1
    assert r2 == {"skipped": True, "reason": "no-new-material"}
    assert len(read_all(tmp_path)) == 1  # F4 dissolved: no overlapping re-save


def test_without_flag_the_old_double_save_behaviour_is_preserved(tmp_path: Path):
    t = _transcript(tmp_path)
    dispatch(_hook("Stop", t), tmp_path, now=NOW)          # flag OFF (default)
    dispatch(_hook("SessionEnd", t), tmp_path, now=NOW)    # flag OFF (default)
    assert len(read_all(tmp_path)) == 2  # unchanged legacy behaviour


def test_later_ring_with_newer_now_saves_again(tmp_path: Path):
    t = _transcript(tmp_path)
    dispatch(_hook("Stop", t), tmp_path, now="2026-08-18T12:00:00+00:00", cursor_delta=True)
    r = dispatch(_hook("Stop", t), tmp_path, now="2026-08-18T12:30:00+00:00", cursor_delta=True)
    assert "entry_id" in r  # a genuinely later ring banks new material
    assert len(read_all(tmp_path)) == 2


def test_different_session_not_skipped(tmp_path: Path):
    """Per-session isolation: a different session is never skipped (§2.2/§7 load-bearing clause)."""
    t = _transcript(tmp_path)
    # Dispatch Stop over same transcript with session_id="s1"
    r1 = dispatch(_hook("Stop", t, session_id="s1"), tmp_path, now=NOW, cursor_delta=True)
    assert "entry_id" in r1
    # Then dispatch the SAME transcript with session_id="s2"
    r2 = dispatch(_hook("Stop", t, session_id="s2"), tmp_path, now=NOW, cursor_delta=True)
    # Must NOT be skipped — different session means new material
    assert "entry_id" in r2
    # Both entries should exist in ledger
    assert len(read_all(tmp_path)) == 2
