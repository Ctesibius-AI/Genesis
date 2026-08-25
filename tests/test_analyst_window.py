"""Analyst cuts its window via read_window for annotations; legacy episodes still open (§2.3, §5)."""
from __future__ import annotations

from pathlib import Path

from genesis.extraction.analyst import prepare_episode
from genesis.save import fast_path_save
from genesis.wal.annotate import save_annotation
from genesis.wal.record import WalRecord
from genesis.wal.store import append_delta


def test_annotation_entry_is_cut_from_the_record(tmp_path: Path):
    append_delta(tmp_path, WalRecord.MEMORY_GRADE, ts="2026-08-18T10:30:00+00:00",
                 span_start="", span_end="", session_id="s1", text="the windowed material")
    e = save_annotation(tmp_path, start_ts="2026-08-18T10:00:00+00:00",
                        end_ts="2026-08-18T11:00:00+00:00", jot="j", session_id="s1",
                        speakers=["the principal"])
    ep = prepare_episode(tmp_path, e)
    assert ep.episode_id == e.entry_id
    assert ep.jot == "j"
    assert ep.content == "the windowed material"     # cut from the memory-grade record


def test_legacy_copied_episode_still_reads_the_owned_file(tmp_path: Path):
    e = fast_path_save(tmp_path, raw_span="legacy body", summary="s", session_id="s1",
                       speakers=["the principal"], span_start="", span_end="",
                       ts="2026-08-18T10:00:00+00:00")
    ep = prepare_episode(tmp_path, e)
    assert "legacy body" in ep.content               # unchanged legacy path
