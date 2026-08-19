"""WAL append-only segment store: scrub-at-append (FROZEN), permanent per-day (§2.1, DR-38)."""
from __future__ import annotations

from pathlib import Path

from genesys.wal.record import WalRecord, segment_path
from genesys.wal.store import append_delta, list_segment_dates, read_segment


def test_append_writes_a_line_to_the_days_segment(tmp_path: Path):
    append_delta(tmp_path, WalRecord.MEMORY_GRADE, ts="2026-08-18T10:00:00+00:00",
                 span_start="", span_end="", session_id="s1", text="alpha")
    lines = read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-18")
    assert [l.text for l in lines] == ["alpha"]
    assert segment_path(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-18").exists()


def test_append_is_permanent_and_ordered(tmp_path: Path):
    for t, txt in [("2026-08-18T10:00:00+00:00", "a"), ("2026-08-18T11:00:00+00:00", "b")]:
        append_delta(tmp_path, WalRecord.MEMORY_GRADE, ts=t, span_start="", span_end="",
                     session_id="s1", text=txt)
    assert [l.text for l in read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-18")] == ["a", "b"]


def test_scrub_runs_at_append_before_first_byte(tmp_path: Path):
    # DR-38 FROZEN position: a secret in the delta never reaches disk unredacted.
    secret = "sk-ant-ABCDEFGHIJKLMNOPQRSTUVWX"
    append_delta(tmp_path, WalRecord.MEMORY_GRADE, ts="2026-08-18T10:00:00+00:00",
                 span_start="", span_end="", session_id="s1", text=f"key is {secret}")
    raw = segment_path(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-18").read_text(encoding="utf-8")
    assert secret not in raw
    assert "<redacted:secret" in raw


def test_two_records_are_parallel_and_independent(tmp_path: Path):
    append_delta(tmp_path, WalRecord.MEMORY_GRADE, ts="2026-08-18T10:00:00+00:00",
                 span_start="", span_end="", session_id="s1", text="clean")
    append_delta(tmp_path, WalRecord.FLIGHT_RECORDER, ts="2026-08-18T10:00:00+00:00",
                 span_start="", span_end="", session_id="s1", text="full incl thinking")
    assert list_segment_dates(tmp_path, WalRecord.MEMORY_GRADE) == ["2026-08-18"]
    mem = read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-08-18")
    fly = read_segment(tmp_path, WalRecord.FLIGHT_RECORDER, "2026-08-18")
    assert mem[0].text == "clean" and fly[0].text == "full incl thinking"


def test_read_absent_segment_is_empty(tmp_path: Path):
    assert read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-01-01") == []
    assert list_segment_dates(tmp_path, WalRecord.MEMORY_GRADE) == []
