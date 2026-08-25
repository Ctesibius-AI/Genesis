"""Discovery + planning helpers for the backfill CLI.

Pure, offline helpers: expand input paths into session .jsonl files, and derive
each session's chronological anchor (content start time), end time, event count,
and session_id. Timestamp extraction reuses the tolerant reader from the hook
adapter (genesis.hooks.adapter._read_jsonl) so we never reimplement jsonl parsing.

Chronological ordering (spec / bi-temporal baseline) is load-bearing: sessions are
ordered by their content START time = the minimum top-level record ``timestamp``
across the session's records, falling back to file mtime when no record carries a
timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from genesis.hooks.adapter import _read_jsonl


@dataclass
class SessionPlan:
    """A single session's backfill plan (one .jsonl file)."""

    path: Path
    session_id: str
    start_ts: str           # content start = min record timestamp (ISO-8601) or "" if none
    end_ts: str             # content end   = max record timestamp (ISO-8601) or "" if none
    event_count: int        # number of records read (tolerant)
    sort_key: datetime      # normalized ordering key (content start, else file mtime)


def discover_jsonl(paths: list[str]) -> list[Path]:
    """Expand input paths into a de-duplicated list of .jsonl files.

    - A file path ending in .jsonl is taken as-is.
    - A directory is recursed for ``*.jsonl`` (rglob).
    - Anything else is ignored.
    Order is not guaranteed here; the caller sorts chronologically.
    """
    found: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        p = Path(raw)
        candidates: list[Path] = []
        if p.is_dir():
            candidates = sorted(p.rglob("*.jsonl"))
        elif p.is_file() and p.suffix == ".jsonl":
            candidates = [p]
        # else: non-existent or non-jsonl → skip silently
        for c in candidates:
            rp = c.resolve()
            if rp not in seen:
                seen.add(rp)
                found.append(c)
    return found


def _parse_iso(value: object) -> datetime | None:
    """Parse an ISO-8601 timestamp (tolerating a trailing 'Z'). Return None on failure."""
    if not isinstance(value, str) or not value.strip():
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _timestamps(records: list[dict]) -> tuple[str, str]:
    """Return (min_ts, max_ts) as the original ISO strings across records.

    Scans each record's top-level ``timestamp`` field only. Records without a
    parseable timestamp are ignored. Returns ("", "") when none is found.
    """
    dated: list[tuple[datetime, str]] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        raw = rec.get("timestamp")
        dt = _parse_iso(raw)
        if dt is not None:
            dated.append((dt, str(raw)))
    if not dated:
        return "", ""
    lo = min(dated, key=lambda x: x[0])
    hi = max(dated, key=lambda x: x[0])
    return lo[1], hi[1]


def plan_session(path: Path) -> SessionPlan:
    """Build a SessionPlan for one .jsonl file (tolerant read; never crashes on one bad line)."""
    records = _read_jsonl(path)
    start_ts, end_ts = _timestamps(records)

    if start_ts:
        sort_dt = _parse_iso(start_ts) or _mtime_dt(path)
    else:
        sort_dt = _mtime_dt(path)

    return SessionPlan(
        path=path,
        session_id=path.stem,
        start_ts=start_ts,
        end_ts=end_ts,
        event_count=len(records),
        sort_key=sort_dt,
    )


def _mtime_dt(path: Path) -> datetime:
    """File mtime as an aware UTC datetime (fallback ordering key)."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    return datetime.fromtimestamp(mtime, tz=timezone.utc)


def build_plan(paths: list[str]) -> list[SessionPlan]:
    """Discover sessions and return them sorted by content start time (else mtime)."""
    files = discover_jsonl(paths)
    plans = [plan_session(f) for f in files]
    plans.sort(key=lambda p: p.sort_key)
    return plans
