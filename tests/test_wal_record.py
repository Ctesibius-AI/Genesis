"""WAL record + per-day segment layout (spec §2.1; CS1 two permanent segmented records)."""
from __future__ import annotations

from pathlib import Path

from genesis.wal.record import (
    WalRecord,
    WalSegmentLine,
    from_jsonl,
    record_dir,
    segment_date,
    segment_path,
    to_jsonl,
    wal_dir,
)


def test_record_values_are_the_ondisk_directory_names():
    assert WalRecord.MEMORY_GRADE.value == "memory-grade"
    assert WalRecord.FLIGHT_RECORDER.value == "flight-recorder"


def test_layout_is_per_day_segment_under_wal_record_dir(tmp_path: Path):
    assert wal_dir(tmp_path) == tmp_path / "wal"
    assert record_dir(tmp_path, WalRecord.MEMORY_GRADE) == tmp_path / "wal" / "memory-grade"
    assert segment_date("2026-08-18T10:00:00+00:00") == "2026-08-18"
    assert segment_path(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-18") == (
        tmp_path / "wal" / "memory-grade" / "2026-08-18.jsonl"
    )


def test_segment_line_round_trips():
    line = WalSegmentLine(ts="2026-08-18T10:00:00+00:00", span_start="",
                          span_end="2026-08-18T10:05:00+00:00", session_id="s1",
                          text="hello genesis")
    assert from_jsonl(to_jsonl(line)) == line


def test_segment_line_round_trips_with_special_chars():
    """Verify JSONL serialization preserves commas, quotes, unicode, and newlines."""
    line = WalSegmentLine(
        ts="2026-08-18T10:00:00+00:00",
        span_start="2026-08-18T09:55:00+00:00",
        span_end="2026-08-18T10:05:00+00:00",
        session_id="s42",
        text='text with "quotes", commas, unicode: 🎯 μ, and\nnewline'
    )
    jsonl_str = to_jsonl(line)
    recovered = from_jsonl(jsonl_str)
    assert recovered == line
    assert recovered.text == line.text
