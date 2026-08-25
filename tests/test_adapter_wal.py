"""dispatch WAL path (opt-in): append+annotate, no episode copies, F4 dissolved (§2.1/§2.2, §5)."""
from __future__ import annotations

import json
from pathlib import Path

from genesis.hooks.adapter import dispatch
from genesis.ids import episodes_dir
from genesis.ledger.store import read_all
from genesis.wal.annotate import is_annotation
from genesis.wal.record import WalRecord
from genesis.wal.store import read_segment
from genesis.wal.window import read_window

NOW1 = "2026-08-18T11:00:00+00:00"
NOW2 = "2026-08-18T12:00:00+00:00"


def _transcript(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n",
                 encoding="utf-8")
    return p


def _hook(event, transcript, session_id="s1"):
    return {"hook_event_name": event, "transcript_path": str(transcript), "session_id": session_id}


def test_wal_path_annotates_and_writes_no_episode_copy(tmp_path: Path):
    t = _transcript(tmp_path, "t1.jsonl", "hello genesis")
    r = dispatch(_hook("Stop", t), tmp_path, now=NOW1, wal=True)
    assert "entry_id" in r
    e = read_all(tmp_path)[0]
    assert is_annotation(e)                                  # a window, not a copy
    assert not episodes_dir(tmp_path).exists() or list(episodes_dir(tmp_path).glob("*.md")) == []
    assert read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-18")  # ring appended


def test_n_rings_give_n_nonoverlapping_annotations_not_n2(tmp_path: Path):
    # F4 DISSOLUTION: two rings of NEW material -> two annotations tiling [cursor->now], no overlap.
    t1 = _transcript(tmp_path, "t1.jsonl", "first ring content")
    t2 = _transcript(tmp_path, "t2.jsonl", "second ring content")
    dispatch(_hook("Stop", t1), tmp_path, now=NOW1, wal=True)
    dispatch(_hook("Stop", t2), tmp_path, now=NOW2, wal=True)
    entries = read_all(tmp_path)
    assert len(entries) == 2                                 # n rings -> n annotations
    a, b = entries
    # non-overlapping: annotation 2 opens exactly where annotation 1 closed
    assert b.provenance.span_start == a.provenance.span_end == NOW1
    assert b.provenance.span_end == NOW2

    # F4 dissolution proof 1: ZERO episode .md files (no per-save copies).
    assert not episodes_dir(tmp_path).exists() or list(episodes_dir(tmp_path).glob("*.md")) == []

    # F4 dissolution proof 2: LINEAR (not n²) content—ring 2's appended content contains only
    # "second ring content", NOT "first ring content" (delta, not re-copy).
    # Read the segment directly and check the appended line for ring 2.
    lines = read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-18")
    assert len(lines) == 2  # two rings, two lines appended
    ring2_line = lines[1]  # the second appended line
    assert ring2_line.text and "second ring content" in ring2_line.text
    assert "first ring content" not in ring2_line.text


def test_wal_default_off_keeps_legacy_copy_path(tmp_path: Path):
    t = _transcript(tmp_path, "t1.jsonl", "hello")
    r = dispatch(_hook("Stop", t), tmp_path, now=NOW1)      # wal defaults OFF
    e = read_all(tmp_path)[0]
    assert not is_annotation(e)                              # legacy: real episode copy
    assert e.provenance.episode_id != ""


def test_precompact_wal_is_a_forced_final_append(tmp_path: Path):
    t = _transcript(tmp_path, "t1.jsonl", "precompact content")
    r = dispatch(_hook("PreCompact", t), tmp_path, now=NOW1, wal=True)
    assert r.get("entry_id")
    assert is_annotation(read_all(tmp_path)[0])
    assert read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-18")
    # PreCompact WAL return shape: diary NOT regenerated on WAL path (forced final append only).
    assert r.get("diary_regenerated") is False
