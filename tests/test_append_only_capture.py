"""Append-only capture (Option B): auto hooks are WAL-only (no queue item); manual save annotates.

Tests cover:
  - courier append_and_annotate(annotate=False) → both WAL rings grow, ledger empty, returns None
  - courier append_and_annotate(annotate=True) → unchanged (rings + annotation, returns entry)
  - dispatch(wal=True, annotate=False) → WAL grows, ledger empty, returns append-only sentinel
  - dispatch(wal=True, annotate=True) → WAL grows + annotation created
  - dispatch(wal=True) default (no annotate arg) → still annotates (backward-compat)
  - save_moment (manual save path) → still creates a salient annotation (annotate=True)
"""
from __future__ import annotations

import json
from pathlib import Path

from genesys.capture.mirror import mirror_events
from genesys.hooks.adapter import dispatch
from genesys.ledger.store import read_all
from genesys.save_moment import save_moment
from genesys.wal.annotate import is_annotation
from genesys.wal.courier import append_and_annotate
from genesys.wal.record import WalRecord
from genesys.wal.store import read_segment


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

NOW = "2026-08-19T10:00:00+00:00"
NOW2 = "2026-08-19T11:00:00+00:00"


def _capture(user_text: str = "hello", thinking_text: str = "thought"):
    return mirror_events([
        {"type": "user", "text": user_text, "author": "principal"},
        {"type": "assistant_thinking", "text": thinking_text, "author": "daimon"},
        {"type": "assistant_text", "text": "reply", "author": "daimon"},
    ])


def _transcript(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n",
        encoding="utf-8",
    )
    return p


def _hook(event: str, transcript: Path, session_id: str = "s1") -> dict:
    return {
        "hook_event_name": event,
        "transcript_path": str(transcript),
        "session_id": session_id,
    }


# ------------------------------------------------------------------ #
# courier: annotate=False                                              #
# ------------------------------------------------------------------ #

def test_courier_annotate_false_appends_both_rings(tmp_path: Path):
    """annotate=False: BOTH WAL rings receive a line."""
    cap = _capture("append-only content", "secret")
    result = append_and_annotate(
        tmp_path, capture_result=cap, cursor="", now=NOW,
        session_id="s1", speakers=["the principal", "Daimon"], jot="auto hook",
        annotate=False,
    )
    # Returns None — no annotation created
    assert result is None
    # MEMORY_GRADE ring has content
    mem_lines = read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-19")
    assert len(mem_lines) >= 1
    assert any("append-only content" in l.text for l in mem_lines)
    # FLIGHT_RECORDER ring has content
    fly_lines = read_segment(tmp_path, WalRecord.FLIGHT_RECORDER, "2026-08-19")
    assert len(fly_lines) >= 1
    assert any("secret" in l.text for l in fly_lines)


def test_courier_annotate_false_ledger_is_empty(tmp_path: Path):
    """annotate=False: no ledger queue item is created."""
    cap = _capture("some text")
    append_and_annotate(
        tmp_path, capture_result=cap, cursor="", now=NOW,
        session_id="s1", speakers=["the principal", "Daimon"], jot="auto hook",
        annotate=False,
    )
    assert read_all(tmp_path) == []


def test_courier_annotate_false_returns_none(tmp_path: Path):
    """annotate=False returns None even when content is present."""
    cap = _capture("real content")
    result = append_and_annotate(
        tmp_path, capture_result=cap, cursor="", now=NOW,
        session_id="s1", speakers=["the principal", "Daimon"], jot="x",
        annotate=False,
    )
    assert result is None


# ------------------------------------------------------------------ #
# courier: annotate=True (unchanged behavior)                          #
# ------------------------------------------------------------------ #

def test_courier_annotate_true_appends_and_annotates(tmp_path: Path):
    """annotate=True (default): both rings appended + annotation created + entry returned."""
    cap = _capture("annotated content", "private thinking")
    entry = append_and_annotate(
        tmp_path, capture_result=cap, cursor="", now=NOW,
        session_id="s1", speakers=["the principal", "Daimon"], jot="manual save",
        annotate=True,
    )
    assert entry is not None
    assert is_annotation(entry)
    entries = read_all(tmp_path)
    assert len(entries) == 1
    mem_lines = read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-19")
    assert len(mem_lines) >= 1


# ------------------------------------------------------------------ #
# dispatch: annotate=False (append-only)                               #
# ------------------------------------------------------------------ #

def test_dispatch_stop_annotate_false_wal_grows_no_ledger_entry(tmp_path: Path):
    """dispatch Stop + wal=True + annotate=False: WAL ring grows, ledger stays empty."""
    t = _transcript(tmp_path, "t1.jsonl", "auto hook content")
    result = dispatch(_hook("Stop", t), tmp_path, now=NOW, wal=True, annotate=False)
    # WAL ring grew
    mem_lines = read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-19")
    assert len(mem_lines) >= 1
    # Ledger is empty — no queue item
    assert read_all(tmp_path) == []
    # Return shape: append-only sentinel
    assert result == {"appended": True, "annotated": False}


def test_dispatch_session_end_annotate_false_append_only(tmp_path: Path):
    """dispatch SessionEnd + wal=True + annotate=False behaves identically to Stop."""
    t = _transcript(tmp_path, "t1.jsonl", "session end content")
    result = dispatch(_hook("SessionEnd", t), tmp_path, now=NOW, wal=True, annotate=False)
    assert result == {"appended": True, "annotated": False}
    assert read_all(tmp_path) == []
    assert read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-19")


def test_dispatch_precompact_annotate_false_append_only(tmp_path: Path):
    """dispatch PreCompact + wal=True + annotate=False: raw WAL only."""
    t = _transcript(tmp_path, "t1.jsonl", "precompact content")
    result = dispatch(_hook("PreCompact", t), tmp_path, now=NOW, wal=True, annotate=False)
    assert result.get("appended") is True
    assert result.get("annotated") is False
    assert read_all(tmp_path) == []
    assert read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-19")


# ------------------------------------------------------------------ #
# dispatch: annotate=True (explicit — creates annotation)              #
# ------------------------------------------------------------------ #

def test_dispatch_annotate_true_creates_annotation(tmp_path: Path):
    """dispatch Stop + wal=True + annotate=True (explicit) creates the ledger entry."""
    t = _transcript(tmp_path, "t1.jsonl", "explicitly annotated")
    result = dispatch(_hook("Stop", t), tmp_path, now=NOW, wal=True, annotate=True)
    assert "entry_id" in result
    entries = read_all(tmp_path)
    assert len(entries) == 1
    assert is_annotation(entries[0])


# ------------------------------------------------------------------ #
# dispatch: backward-compat (no annotate arg → defaults True)          #
# ------------------------------------------------------------------ #

def test_dispatch_default_annotate_still_annotates(tmp_path: Path):
    """Calling dispatch without annotate= still produces a ledger annotation (backward-compat)."""
    t = _transcript(tmp_path, "t1.jsonl", "default annotate check")
    result = dispatch(_hook("Stop", t), tmp_path, now=NOW, wal=True)
    # annotate defaults to True → annotation created
    assert "entry_id" in result
    entries = read_all(tmp_path)
    assert len(entries) == 1
    assert is_annotation(entries[0])


# ------------------------------------------------------------------ #
# Manual save path (save_moment) still annotates + marks salient       #
# ------------------------------------------------------------------ #

def _fixture_transcript(tmp_path: Path, name: str = "t.jsonl") -> Path:
    p = tmp_path / name
    records = [
        {"type": "user", "message": {"role": "user", "content": "save this important thing"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "Sure, noted."}
        ]}},
    ]
    p.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return p


def test_save_moment_still_creates_salient_annotation(tmp_path: Path):
    """The manual save path (save_moment) always creates a SALIENT annotation.

    It calls append_and_annotate with annotate=True (the default), so it is
    unaffected by the append-only change and still queues an extraction item.
    """
    data_root = tmp_path / "data"
    data_root.mkdir()
    t = _fixture_transcript(tmp_path)
    entry = save_moment(
        data_root,
        transcript_path=t,
        session_id="sess-manual",
        now=NOW,
        note="important decision captured",
    )
    assert entry is not None
    assert is_annotation(entry)
    assert entry.enrichment.get("salience") is True
    assert entry.summary == "important decision captured"
    entries = read_all(data_root)
    assert len(entries) == 1
    # WAL ring also grew
    assert read_segment(data_root, WalRecord.MEMORY_GRADE, "2026-08-19")
