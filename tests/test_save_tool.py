"""Manual save tool (CS4): assistant-invocable, annotates the current window, same door (§2.2, DR-43)."""
from __future__ import annotations

from pathlib import Path

from genesis.ids import episodes_dir
from genesis.save_tool import save_tool
from genesis.wal.annotate import is_annotation, save_annotation
from genesis.wal.record import WalRecord


def test_manual_save_annotates_current_window_with_owner_jot(tmp_path: Path):
    # prior auto annotation banks a cursor at 10:00
    save_annotation(tmp_path, start_ts="", end_ts="2026-08-18T10:00:00+00:00",
                    jot="auto", session_id="s1", speakers=["the principal"])
    e = save_tool(tmp_path, jot="save this, because it's the decision",
                  session_id="s1", now="2026-08-18T11:00:00+00:00")
    assert is_annotation(e)
    assert e.provenance.span_start == "2026-08-18T10:00:00+00:00"  # current window start = last cursor
    assert e.provenance.span_end == "2026-08-18T11:00:00+00:00"
    assert e.summary == "save this, because it's the decision"     # owner-authored jot
    assert "salience" not in (e.enrichment or {})                  # BT-7 / D-GCW-11: flag removed
    # same door => no owned copy
    assert not episodes_dir(tmp_path).exists() or list(episodes_dir(tmp_path).glob("*.md")) == []


def test_manual_save_first_ring_opens_at_empty_cursor(tmp_path: Path):
    e = save_tool(tmp_path, jot="first", session_id="s-new", now="2026-08-18T09:00:00+00:00")
    assert e.provenance.span_start == ""  # no prior cursor for this session
    assert e.provenance.span_end == "2026-08-18T09:00:00+00:00"
