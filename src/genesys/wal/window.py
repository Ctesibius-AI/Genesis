"""read_window — the shared window-cut helper (spec §2.3; CS5).

The Analyst (and Plan 3's Verifier) cut their raw window from the memory-grade record via this
helper instead of opening an episode file. Resolution is a PURE ts-range scan: resolve the
per-day segment(s) for the dates spanned by [start_ts, end_ts], keep every line whose ts is in
the window, concat cross-day in date order. NO byte-offset index (DEFERRED per CS5) — that is a
later optimization; do not build it here.

This is the interface Plan 3 (Screen-on-raw + Verifier) consumes:
    read_window(record, data_root, start_ts, end_ts) -> str
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from genesys.wal.record import WalRecord, segment_date
from genesys.wal.store import read_segment


def _parse(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp, normalizing a trailing Z → +00:00.

    Mirrors the exact normalization used in genesys.doctor.doctor_deadman so that Z-suffix
    and +00:00-suffix timestamps for the same instant compare equal as datetimes.
    """
    normalized = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
    return datetime.fromisoformat(normalized)


def _dates_in_range(start_ts: str, end_ts: str) -> list[str]:
    """Inclusive YYYY-MM-DD dates from start (or end, if start empty) to end, day-stepped."""
    start_date = segment_date(start_ts) if start_ts else segment_date(end_ts)
    end_date = segment_date(end_ts)
    d0 = datetime.fromisoformat(start_date).date()
    d1 = datetime.fromisoformat(end_date).date()
    if d1 < d0:  # defensive: never step backwards
        d0, d1 = d1, d0
    out: list[str] = []
    cur = d0
    while cur <= d1:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def read_window(record: WalRecord, data_root: Path, start_ts: str, end_ts: str) -> str:
    """Cut the raw text for [start_ts, end_ts] from `record`, scanning per-day segment(s).

    Inclusive on both ends: a line whose ts == start_ts or ts == end_ts is included.
    Cross-day: segments are read in date order and concatenated.
    Empty start_ts: treated as "from the beginning of the end_ts day" (first-ring case).
    Empty result: returns "" (empty string, not None).
    Separator: kept text values are joined with "\n".
    """
    kept: list[str] = []
    end_dt = _parse(end_ts)
    for date in _dates_in_range(start_ts, end_ts):
        for line in read_segment(data_root, record, date):
            line_dt = _parse(line.ts)
            if start_ts:
                if _parse(start_ts) <= line_dt <= end_dt:
                    kept.append(line.text)
            else:
                # Empty start_ts: no lower bound — include everything up through end_ts
                if line_dt <= end_dt:
                    kept.append(line.text)
    return "\n".join(kept)
