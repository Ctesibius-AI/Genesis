"""Courier append+annotate: both rings appended, memory-grade annotated, skip-when-empty (§2.1/§2.2)."""
from __future__ import annotations

from pathlib import Path

from genesis.capture.mirror import mirror_events
from genesis.ledger.store import read_all
from genesis.wal.annotate import is_annotation
from genesis.wal.courier import append_and_annotate
from genesis.wal.record import WalRecord
from genesis.wal.store import read_segment


def _capture(user_text, thinking_text):
    return mirror_events([
        {"type": "user", "text": user_text, "author": "principal"},
        {"type": "assistant_thinking", "text": thinking_text, "author": "daimon"},
        {"type": "assistant_text", "text": "reply", "author": "daimon"},
    ])


def test_appends_both_rings_and_annotates_memory_grade(tmp_path: Path):
    cap = _capture("hello", "secret thinking")
    e = append_and_annotate(tmp_path, capture_result=cap, cursor="",
                            now="2026-08-18T11:00:00+00:00", session_id="s1",
                            speakers=["the principal", "Daimon"], jot="ring-1")
    assert e is not None and is_annotation(e)
    mem = read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-18")
    fly = read_segment(tmp_path, WalRecord.FLIGHT_RECORDER, "2026-08-18")
    joined_mem = "\n".join(l.text for l in mem)
    joined_fly = "\n".join(l.text for l in fly)
    assert "hello" in joined_mem and "reply" in joined_mem
    assert "secret thinking" not in joined_mem       # thinking is flight-only
    assert "secret thinking" in joined_fly            # flight recorder keeps it
    assert e.provenance.span_end == "2026-08-18T11:00:00+00:00"
    assert e.provenance.span_start == ""             # empty cursor passed through as window start


def test_skip_when_nothing_new(tmp_path: Path):
    empty = mirror_events([])  # no memory-grade material
    r = append_and_annotate(tmp_path, capture_result=empty, cursor="2026-08-18T10:00:00+00:00",
                            now="2026-08-18T10:00:00+00:00", session_id="s1",
                            speakers=["the principal"], jot="nothing")
    assert r is None
    assert read_all(tmp_path) == []
    assert read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-18") == []
    assert read_segment(tmp_path, WalRecord.FLIGHT_RECORDER, "2026-08-18") == []  # skip appends nothing to EITHER ring
