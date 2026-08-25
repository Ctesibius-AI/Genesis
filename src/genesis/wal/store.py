"""WAL append-only segment store (spec §2.1; DR-24 revised; DR-38 scrub-at-append FROZEN).

Append a scrubbed delta to a record's per-day segment; read a segment back. The records are
PERMANENT (CS1) — this module never rotates, truncates, or deletes; owner pruning is explicit
and out of scope here. The scrubber runs INSIDE append_delta, before the first byte hits disk
— the same frozen position as episode.ownedfile.write_episode_file and capture.mirror._scrub.
"""

from __future__ import annotations

from pathlib import Path

from genesis.scrub.scrubber import scrub_text
from genesis.wal.record import (
    WalRecord,
    WalSegmentLine,
    from_jsonl,
    record_dir,
    segment_date,
    segment_path,
    to_jsonl,
)


def append_delta(data_root: Path, record: WalRecord, *, ts: str, span_start: str,
                 span_end: str, session_id: str, text: str) -> Path:
    """Scrub `text` (DR-38, before first byte) then append one line to the day segment."""
    scrubbed = scrub_text(text).text  # FROZEN position — at append, before disk
    line = WalSegmentLine(ts=ts, span_start=span_start, span_end=span_end,
                          session_id=session_id, text=scrubbed)
    path = segment_path(data_root, record, segment_date(ts))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(to_jsonl(line) + "\n")
    return path


def read_segment(data_root: Path, record: WalRecord, date: str) -> list[WalSegmentLine]:
    path = segment_path(data_root, record, date)
    if not path.exists():
        return []
    return [from_jsonl(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def list_segment_dates(data_root: Path, record: WalRecord) -> list[str]:
    d = record_dir(data_root, record)
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.jsonl"))
