"""Acceptance test: capture-once invariant (build/capture-once).

Simulates the owner's exact flow:
  1. Hook fires for reply-1 (append-only, wal=True, annotate=False).
  2. Hook fires again for reply-1 + reply-2 (growing transcript, same session).
  3. save_moment is called (manual save → SALIENT annotation).

Asserts:
  A. After the 2 hook rings: MEMORY_GRADE WAL contains "ANSWER-ONE" exactly 1x and
     "ANSWER-TWO" exactly 1x (capture-once). Ledger has 0 annotations (append-only).
  B. After the save: exactly 1 annotation (salient), whose read_window returns
     "ANSWER-ONE" exactly 1x and "ANSWER-TWO" exactly 1x (NO duplication).
  C. The save did not itself add duplicate WAL content (WAL line count unchanged after
     annotate-only step).

No mocks — real WAL/ledger under tmp_path (offline).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from genesys.hooks.adapter import dispatch
from genesys.ledger.store import read_all
from genesys.save_moment import save_moment
from genesys.wal.annotate import is_annotation
from genesys.wal.record import WalRecord
from genesys.wal.store import read_segment
from genesys.wal.window import read_window

SESSION_ID = "session-capture-once"
NOW1 = "2026-08-19T10:00:00+00:00"
NOW2 = "2026-08-19T11:00:00+00:00"
NOW_SAVE = "2026-08-19T12:00:00+00:00"
DATE = "2026-08-19"


def _write_transcript(path: Path, assistant_texts: list[str]) -> None:
    """Write a CC-style transcript .jsonl with one user msg and N assistant replies."""
    records = [
        {"type": "user", "message": {"role": "user", "content": "tell me something"}},
    ]
    for text in assistant_texts:
        records.append({
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
        })
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")


def _hook(event: str, transcript: Path, session_id: str = SESSION_ID) -> dict:
    return {
        "hook_event_name": event,
        "transcript_path": str(transcript),
        "session_id": session_id,
    }


def test_capture_once_full_flow(tmp_path: Path) -> None:
    """THE crux acceptance test: two hook rings + save → each reply captured exactly once."""
    data_root = tmp_path / "data"
    data_root.mkdir()

    transcript = tmp_path / f"{SESSION_ID}.jsonl"

    # ------------------------------------------------------------------ #
    # Ring 1: transcript has only reply-1                                  #
    # ------------------------------------------------------------------ #
    _write_transcript(transcript, ["ANSWER-ONE"])
    r1 = dispatch(
        _hook("Stop", transcript),
        data_root,
        now=NOW1,
        wal=True,
        annotate=False,
    )
    assert r1 == {"appended": True, "annotated": False}, f"ring-1 result: {r1}"

    # ------------------------------------------------------------------ #
    # Ring 2: transcript has reply-1 + reply-2                            #
    # ------------------------------------------------------------------ #
    _write_transcript(transcript, ["ANSWER-ONE", "ANSWER-TWO"])
    r2 = dispatch(
        _hook("Stop", transcript),
        data_root,
        now=NOW2,
        wal=True,
        annotate=False,
    )
    assert r2 == {"appended": True, "annotated": False}, f"ring-2 result: {r2}"

    # ------------------------------------------------------------------ #
    # Assertion A: WAL content — each reply exactly once                  #
    # ------------------------------------------------------------------ #
    mem_lines = read_segment(data_root, WalRecord.MEMORY_GRADE, DATE)
    all_wal_text = "\n".join(line.text for line in mem_lines)

    assert all_wal_text.count("ANSWER-ONE") == 1, (
        f"Expected ANSWER-ONE exactly 1x in WAL, got {all_wal_text.count('ANSWER-ONE')}x.\n"
        f"WAL text: {all_wal_text!r}"
    )
    assert all_wal_text.count("ANSWER-TWO") == 1, (
        f"Expected ANSWER-TWO exactly 1x in WAL, got {all_wal_text.count('ANSWER-TWO')}x.\n"
        f"WAL text: {all_wal_text!r}"
    )

    # Ledger has 0 annotations — append-only mode
    assert read_all(data_root) == [], "Ledger must be empty after append-only hook rings"

    # ------------------------------------------------------------------ #
    # save_moment                                                          #
    # ------------------------------------------------------------------ #
    entry = save_moment(
        data_root,
        transcript_path=transcript,
        session_id=SESSION_ID,
        now=NOW_SAVE,
        note="capture-once acceptance test",
    )
    assert entry is not None, "save_moment must return a LedgerEntry"
    assert is_annotation(entry), "save_moment must create an annotation entry"
    assert "salience" not in (entry.enrichment or {})  # BT-7: salience flag removed

    # ------------------------------------------------------------------ #
    # Assertion B: exactly 1 annotation; window has each reply 1x         #
    # ------------------------------------------------------------------ #
    entries = read_all(data_root)
    assert len(entries) == 1, f"Expected exactly 1 annotation after save, got {len(entries)}"

    ann = entries[0]
    span_start = ann.provenance.span_start
    span_end = ann.provenance.span_end
    window_text = read_window(WalRecord.MEMORY_GRADE, data_root, span_start, span_end)

    assert window_text.count("ANSWER-ONE") == 1, (
        f"Expected ANSWER-ONE exactly 1x in save window, got {window_text.count('ANSWER-ONE')}x.\n"
        f"Window text: {window_text!r}"
    )
    assert window_text.count("ANSWER-TWO") == 1, (
        f"Expected ANSWER-TWO exactly 1x in save window, got {window_text.count('ANSWER-TWO')}x.\n"
        f"Window text: {window_text!r}"
    )

    # ------------------------------------------------------------------ #
    # Assertion C: save did not add duplicate WAL content                  #
    # ------------------------------------------------------------------ #
    mem_lines_after_save = read_segment(data_root, WalRecord.MEMORY_GRADE, DATE)
    all_wal_text_after = "\n".join(line.text for line in mem_lines_after_save)

    assert all_wal_text_after.count("ANSWER-ONE") == 1, (
        f"Save must not add duplicate WAL content; ANSWER-ONE count after save: "
        f"{all_wal_text_after.count('ANSWER-ONE')}x"
    )
    assert all_wal_text_after.count("ANSWER-TWO") == 1, (
        f"Save must not add duplicate WAL content; ANSWER-TWO count after save: "
        f"{all_wal_text_after.count('ANSWER-TWO')}x"
    )


def test_second_ring_with_no_new_content_is_skipped(tmp_path: Path) -> None:
    """If the transcript doesn't grow between rings, the second ring appends nothing."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    transcript = tmp_path / "same.jsonl"
    _write_transcript(transcript, ["ONLY-ANSWER"])

    dispatch(_hook("Stop", transcript), data_root, now=NOW1, wal=True, annotate=False)
    dispatch(_hook("Stop", transcript), data_root, now=NOW2, wal=True, annotate=False)

    mem_lines = read_segment(data_root, WalRecord.MEMORY_GRADE, DATE)
    all_text = "\n".join(line.text for line in mem_lines)
    assert all_text.count("ONLY-ANSWER") == 1, (
        f"Duplicate WAL append: ONLY-ANSWER appears {all_text.count('ONLY-ANSWER')}x"
    )


def test_session_end_after_stop_appends_once(tmp_path: Path) -> None:
    """Stop then SessionEnd over the same growing transcript still captures each reply once."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    transcript = tmp_path / "growing.jsonl"

    _write_transcript(transcript, ["REPLY-ONE"])
    dispatch(_hook("Stop", transcript), data_root, now=NOW1, wal=True, annotate=False)

    _write_transcript(transcript, ["REPLY-ONE", "REPLY-TWO"])
    dispatch(_hook("SessionEnd", transcript), data_root, now=NOW2, wal=True, annotate=False)

    mem_lines = read_segment(data_root, WalRecord.MEMORY_GRADE, DATE)
    all_text = "\n".join(line.text for line in mem_lines)
    assert all_text.count("REPLY-ONE") == 1
    assert all_text.count("REPLY-TWO") == 1


def test_save_moment_without_prior_hooks(tmp_path: Path) -> None:
    """save_moment works even when no prior hook rings have run (first save of session)."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    transcript = tmp_path / "fresh.jsonl"
    _write_transcript(transcript, ["FRESH-ANSWER"])

    entry = save_moment(
        data_root,
        transcript_path=transcript,
        session_id="fresh-session",
        now=NOW_SAVE,
        note="first ever save",
    )
    assert entry is not None
    assert is_annotation(entry)
    assert "salience" not in (entry.enrichment or {})

    entries = read_all(data_root)
    assert len(entries) == 1

    window_text = read_window(
        WalRecord.MEMORY_GRADE, data_root,
        entries[0].provenance.span_start,
        entries[0].provenance.span_end,
    )
    assert "FRESH-ANSWER" in window_text


# --------------------------------------------------------------------------- #
# Compaction / shrink tests (QA-confirmed defect — write-cursor data loss)    #
# --------------------------------------------------------------------------- #

def test_compaction_shrink_new_content_not_lost(tmp_path: Path) -> None:
    """THE QA scenario: compaction shrinks the transcript → new post-compaction content MUST
    be captured (not silently dropped).

    Flow:
      1. Capture 6 records (cursor=6).
      2. Compaction rewrites the transcript to 3 NEW records (shorter).
      3. Fire the capture ring → the new post-compaction records MUST appear in the WAL.

    This test FAILS against the pre-fix slice-blindly code (``all_records[6:]`` == [])
    and PASSES after the fix detects the shrink and re-derives from record 0.
    """
    data_root = tmp_path / "data"
    data_root.mkdir()
    transcript = tmp_path / "compacted.jsonl"

    # Step 1: capture 6 records (1 user + 5 assistant replies)
    records_before = [
        {"type": "user", "message": {"role": "user", "content": "question"}},
    ]
    for i in range(1, 6):
        records_before.append({
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": f"BEFORE-{i}"}]},
        })
    transcript.write_text("\n".join(json.dumps(r) for r in records_before), encoding="utf-8")

    dispatch(
        {"hook_event_name": "Stop", "transcript_path": str(transcript), "session_id": "compact-session"},
        data_root,
        now=NOW1,
        wal=True,
        annotate=False,
    )

    # Confirm cursor is 6
    from genesys.wal.write_cursor import read_captured_count
    assert read_captured_count(data_root, "compact-session") == len(records_before)

    # Step 2: compaction rewrites the transcript to 3 NEW records (smaller, different content)
    records_after = [
        {"type": "user", "message": {"role": "user", "content": "summary question"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "COMPACTED-SUMMARY"}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "POST-COMPACTION-NEW"}]}},
    ]
    transcript.write_text("\n".join(json.dumps(r) for r in records_after), encoding="utf-8")

    # Step 3: fire the capture ring — cursor=6, transcript has only 3 records
    dispatch(
        {"hook_event_name": "Stop", "transcript_path": str(transcript), "session_id": "compact-session"},
        data_root,
        now=NOW2,
        wal=True,
        annotate=False,
    )

    # Assert: the NEW post-compaction content is captured (not silently lost)
    mem_lines = read_segment(data_root, WalRecord.MEMORY_GRADE, DATE)
    all_wal_text = "\n".join(line.text for line in mem_lines)

    assert "POST-COMPACTION-NEW" in all_wal_text, (
        f"POST-COMPACTION-NEW was silently lost after compaction shrink.\n"
        f"WAL text: {all_wal_text!r}"
    )

    # Cursor must be self-corrected to the new length (3), not stuck at 6
    assert read_captured_count(data_root, "compact-session") == len(records_after), (
        f"Cursor must self-correct to {len(records_after)} after compaction, "
        f"got {read_captured_count(data_root, 'compact-session')}"
    )


def test_stale_cursor_self_heals(tmp_path: Path) -> None:
    """Cursor > current record length → next ring captures content and resets cursor.

    Simulates a cursor that somehow got stuck above the actual transcript length
    (e.g. from a crash or partial write). The ring must not permanently skip.
    """
    data_root = tmp_path / "data"
    data_root.mkdir()
    transcript = tmp_path / "stale.jsonl"

    # Manually write a stale cursor that exceeds the actual transcript
    from genesys.wal.write_cursor import write_captured_count
    write_captured_count(data_root, "stale-session", 999)

    # Write a transcript with actual content
    records = [
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "STALE-HEAL-CONTENT"}]}},
    ]
    transcript.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    dispatch(
        {"hook_event_name": "Stop", "transcript_path": str(transcript), "session_id": "stale-session"},
        data_root,
        now=NOW1,
        wal=True,
        annotate=False,
    )

    mem_lines = read_segment(data_root, WalRecord.MEMORY_GRADE, DATE)
    all_wal_text = "\n".join(line.text for line in mem_lines)

    assert "STALE-HEAL-CONTENT" in all_wal_text, (
        f"Stale cursor (999) should not permanently block capture.\nWAL: {all_wal_text!r}"
    )

    from genesys.wal.write_cursor import read_captured_count
    assert read_captured_count(data_root, "stale-session") == len(records), (
        f"Cursor must self-correct to {len(records)}, "
        f"got {read_captured_count(data_root, 'stale-session')}"
    )


def test_save_moment_twice_creates_two_annotations_no_extra_wal(tmp_path: Path) -> None:
    """Two save_moment calls: 2 annotations, WAL content for each reply still only 1x."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    transcript = tmp_path / "two_saves.jsonl"

    # First save: reply-1 only
    _write_transcript(transcript, ["SAVE-ONE"])
    e1 = save_moment(
        data_root,
        transcript_path=transcript,
        session_id="two-saves",
        now=NOW1,
        note="first save",
    )
    assert e1 is not None

    # Second save: reply-1 + reply-2
    _write_transcript(transcript, ["SAVE-ONE", "SAVE-TWO"])
    e2 = save_moment(
        data_root,
        transcript_path=transcript,
        session_id="two-saves",
        now=NOW2,
        note="second save",
    )
    assert e2 is not None

    entries = read_all(data_root)
    assert len(entries) == 2

    mem_lines = read_segment(data_root, WalRecord.MEMORY_GRADE, DATE)
    all_text = "\n".join(line.text for line in mem_lines)
    assert all_text.count("SAVE-ONE") == 1, f"SAVE-ONE should appear 1x, got: {all_text!r}"
    assert all_text.count("SAVE-TWO") == 1, f"SAVE-TWO should appear 1x, got: {all_text!r}"
