"""Save = ledger annotation — a window, not a copy (spec §2.2, DR-43, F-GENESIS-03 superseded)."""
from __future__ import annotations

from pathlib import Path

from genesis.ids import episodes_dir
from genesis.ledger.store import read_all
from genesis.wal.annotate import annotation_record, is_annotation, save_annotation
from genesis.wal.record import WalRecord


def test_annotation_is_a_window_not_a_copy(tmp_path: Path):
    e = save_annotation(tmp_path, start_ts="2026-08-18T10:00:00+00:00",
                        end_ts="2026-08-18T11:00:00+00:00", jot="save this, because X",
                        session_id="s1", speakers=["the principal", "Daimon"])
    assert e.provenance.episode_id == ""              # NO owned copy
    assert e.provenance.span_start == "2026-08-18T10:00:00+00:00"
    assert e.provenance.span_end == "2026-08-18T11:00:00+00:00"
    assert e.summary == "save this, because X"        # jot = display label
    assert is_annotation(e) is True
    assert annotation_record(e) is WalRecord.MEMORY_GRADE
    # persisted to the ledger; NO episode .md file was written
    assert read_all(tmp_path)[0].entry_id == e.entry_id
    assert not (episodes_dir(tmp_path)).exists() or list(episodes_dir(tmp_path).glob("*.md")) == []

    # Prove enrichment survives ledger round-trip on re-read entry (to_jsonl/from_jsonl)
    got = read_all(tmp_path)[0]
    assert is_annotation(got) is True
    assert annotation_record(got) is WalRecord.MEMORY_GRADE
    assert got.provenance.span_start == "2026-08-18T10:00:00+00:00"
    assert got.provenance.span_end == "2026-08-18T11:00:00+00:00"
    assert "salience" not in (got.enrichment or {})  # BT-7: salience flag removed


def test_jot_is_scrubbed_as_free_text(tmp_path: Path):
    e = save_annotation(tmp_path, start_ts="", end_ts="2026-08-18T11:00:00+00:00",
                        jot="token=sk-ant-ABCDEFGHIJKLMNOPQRSTUVWX", session_id="s1",
                        speakers=["the principal"])
    assert "sk-ant-ABCDEFGHIJKLMNOPQRSTUVWX" not in e.summary
    assert "<redacted:secret" in e.summary


def test_record_choice_is_recorded(tmp_path: Path):
    e = save_annotation(tmp_path, start_ts="", end_ts="2026-08-18T11:00:00+00:00",
                        jot="j", session_id="s1", speakers=["the principal"],
                        record=WalRecord.FLIGHT_RECORDER)
    assert annotation_record(e) is WalRecord.FLIGHT_RECORDER
    # Prove record survives ledger round-trip
    got = read_all(tmp_path)[0]
    assert annotation_record(got) is WalRecord.FLIGHT_RECORDER


def test_salience_flag_removed(tmp_path: Path):
    # D-GCW-11 / BT-7: the dead salience flag is gone — annotations carry no salience key.
    e = save_annotation(tmp_path, start_ts="", end_ts="2026-08-18T11:00:00+00:00",
                        jot="j", session_id="s1", speakers=["the principal"])
    assert "salience" not in (e.enrichment or {})
    got = read_all(tmp_path)[0]
    assert "salience" not in (got.enrichment or {})


def test_consecutive_annotations_are_structurally_chained(tmp_path: Path):
    """WAL-path annotations must have their prev/next chain set at save time (DR-09).

    Save two annotations in the same session; the second entry's prev must point to
    the first, and the first entry's next must point to the second — matching the
    structural-linking guarantee of the fast_path_save (copy) route.
    """
    first = save_annotation(tmp_path, start_ts="2026-08-18T09:00:00+00:00",
                            end_ts="2026-08-18T10:00:00+00:00", jot="first save",
                            session_id="s1", speakers=["the principal"])
    second = save_annotation(tmp_path, start_ts="2026-08-18T10:00:00+00:00",
                             end_ts="2026-08-18T11:00:00+00:00", jot="second save",
                             session_id="s1", speakers=["the principal"])

    # The second annotation's prev must point to the first.
    assert second.links.prev == first.entry_id

    # Re-read from ledger to confirm the backfill on the first entry's next.
    entries = {e.entry_id: e for e in read_all(tmp_path)}
    assert entries[first.entry_id].links.next == second.entry_id


def test_a_legacy_copied_episode_is_not_an_annotation(tmp_path: Path):
    from genesis.save import fast_path_save
    e = fast_path_save(tmp_path, raw_span="raw", summary="s", session_id="s1",
                       speakers=["the principal"], span_start="", span_end="",
                       ts="2026-08-18T10:00:00+00:00")
    assert is_annotation(e) is False  # has a real episode_id + no annotation marker
