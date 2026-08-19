"""read_window — per-day segment resolution + ts-range scan, cross-day in order (§2.3, CS5)."""
from __future__ import annotations

from pathlib import Path

from genesys.wal.record import WalRecord
from genesys.wal.store import append_delta
from genesys.wal.window import _dates_in_range, read_window


def _add(tmp_path, ts, text):
    append_delta(tmp_path, WalRecord.MEMORY_GRADE, ts=ts, span_start="", span_end="",
                 session_id="s1", text=text)


def test_window_scans_the_ts_range_within_a_day(tmp_path: Path):
    _add(tmp_path, "2026-08-18T10:00:00+00:00", "a")
    _add(tmp_path, "2026-08-18T11:00:00+00:00", "b")
    _add(tmp_path, "2026-08-18T12:00:00+00:00", "c")
    out = read_window(WalRecord.MEMORY_GRADE, tmp_path,
                      "2026-08-18T10:30:00+00:00", "2026-08-18T11:30:00+00:00")
    assert out == "b"  # only the 11:00 line falls in [10:30, 11:30]


def test_window_is_inclusive_of_both_ends(tmp_path: Path):
    _add(tmp_path, "2026-08-18T10:00:00+00:00", "a")
    _add(tmp_path, "2026-08-18T11:00:00+00:00", "b")
    out = read_window(WalRecord.MEMORY_GRADE, tmp_path,
                      "2026-08-18T10:00:00+00:00", "2026-08-18T11:00:00+00:00")
    assert out == "a\nb"


def test_window_excludes_lines_outside_range(tmp_path: Path):
    _add(tmp_path, "2026-08-18T09:59:59+00:00", "before")
    _add(tmp_path, "2026-08-18T10:00:00+00:00", "at-start")
    _add(tmp_path, "2026-08-18T11:00:00+00:00", "at-end")
    _add(tmp_path, "2026-08-18T11:00:01+00:00", "after")
    out = read_window(WalRecord.MEMORY_GRADE, tmp_path,
                      "2026-08-18T10:00:00+00:00", "2026-08-18T11:00:00+00:00")
    assert out == "at-start\nat-end"


def test_cross_day_window_reads_multiple_segments_in_order(tmp_path: Path):
    _add(tmp_path, "2026-08-17T23:00:00+00:00", "night")
    _add(tmp_path, "2026-08-18T01:00:00+00:00", "morning")
    out = read_window(WalRecord.MEMORY_GRADE, tmp_path,
                      "2026-08-17T22:00:00+00:00", "2026-08-18T02:00:00+00:00")
    assert out == "night\nmorning"
    assert _dates_in_range("2026-08-17T22:00:00+00:00", "2026-08-18T02:00:00+00:00") == \
        ["2026-08-17", "2026-08-18"]


def test_empty_start_reads_from_the_start_of_the_end_day(tmp_path: Path):
    _add(tmp_path, "2026-08-18T09:00:00+00:00", "first-ring-of-day")
    out = read_window(WalRecord.MEMORY_GRADE, tmp_path, "", "2026-08-18T10:00:00+00:00")
    assert out == "first-ring-of-day"


def test_empty_window_returns_empty_string(tmp_path: Path):
    _add(tmp_path, "2026-08-18T10:00:00+00:00", "a")
    assert read_window(WalRecord.MEMORY_GRADE, tmp_path,
                       "2026-08-18T20:00:00+00:00", "2026-08-18T21:00:00+00:00") == ""


# ── Fix verification: Z-suffix vs +00:00 mixed-format robustness ──────────────

def test_z_suffix_line_included_when_bounds_use_plus_offset(tmp_path: Path):
    """A line stored with Z-suffix must be included when the window bounds use +00:00.

    The old string comparison silently excluded it because 'Z' (0x5A) > '+' (0x2B),
    making 2026-08-18T10:00:00Z appear to sort GREATER than a +00:00-bounded end_ts
    at the same instant, wrongly failing the <= end_ts check.

    This test would FAIL against the old string-compare (RED); it passes after _parse fix (GREEN).
    """
    # Line stored with Z suffix (same instant as 10:00:00+00:00)
    _add(tmp_path, "2026-08-18T10:00:00Z", "z-line")
    # Query with +00:00 bounds that SHOULD include the Z line
    out = read_window(WalRecord.MEMORY_GRADE, tmp_path,
                      "2026-08-18T09:00:00+00:00", "2026-08-18T11:00:00+00:00")
    assert out == "z-line", (
        "Z-suffix line at 10:00:00Z must be included in [09:00:00+00:00, 11:00:00+00:00]"
    )

    # Also verify: Z line AT the exact +00:00 end bound is included (inclusive)
    _add(tmp_path, "2026-08-18T12:00:00Z", "z-at-end")
    out2 = read_window(WalRecord.MEMORY_GRADE, tmp_path,
                       "2026-08-18T09:00:00+00:00", "2026-08-18T12:00:00+00:00")
    assert "z-at-end" in out2, (
        "Z-suffix line at exact +00:00 end bound must be included (inclusive)"
    )

    # And: Z line AFTER the end bound must be EXCLUDED
    out3 = read_window(WalRecord.MEMORY_GRADE, tmp_path,
                       "2026-08-18T09:00:00+00:00", "2026-08-18T11:30:00+00:00")
    assert "z-at-end" not in out3, (
        "Z-suffix line at 12:00:00Z must be excluded when end_ts is 11:30:00+00:00"
    )


# ── Month-boundary _dates_in_range ────────────────────────────────────────────

def test_dates_in_range_crosses_month_boundary(tmp_path: Path):
    """_dates_in_range must enumerate both dates across a month boundary."""
    dates = _dates_in_range("2026-08-31T23:00:00+00:00", "2026-09-01T01:00:00+00:00")
    assert dates == ["2026-08-31", "2026-09-01"], (
        "_dates_in_range must enumerate both sides of a month boundary"
    )

    # Cross-month window concatenates in order
    _add(tmp_path, "2026-08-31T23:00:00+00:00", "aug-line")
    _add(tmp_path, "2026-09-01T01:00:00+00:00", "sep-line")
    out = read_window(WalRecord.MEMORY_GRADE, tmp_path,
                      "2026-08-31T23:00:00+00:00", "2026-09-01T01:00:00+00:00")
    assert out == "aug-line\nsep-line", (
        "Cross-month window must concatenate August line then September line in order"
    )
