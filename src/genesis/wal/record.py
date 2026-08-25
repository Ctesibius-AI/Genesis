"""WAL record names + per-day segment layout (spec §2.1; CS1).

Two records (memory-grade + flight-recorder), each a directory of per-day JSONL segments.
The enum value IS the on-disk directory name so the layout is derivable from the record with
no extra mapping. Segment key = ts[:10] (calendar date), the same determinism as
ids.next_episode_id's date key and ledger.store.month_path's month key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class WalRecord(str, Enum):
    MEMORY_GRADE = "memory-grade"      # clean; the pipeline reads this (§2.1)
    FLIGHT_RECORDER = "flight-recorder"  # full incl. thinking; QA-only (§2.1)


@dataclass
class WalSegmentLine:
    ts: str
    span_start: str
    span_end: str
    session_id: str
    text: str


def to_jsonl(line: WalSegmentLine) -> str:
    return json.dumps(
        {"ts": line.ts, "span_start": line.span_start, "span_end": line.span_end,
         "session_id": line.session_id, "text": line.text},
        ensure_ascii=False, separators=(",", ":"),
    )


def from_jsonl(line: str) -> WalSegmentLine:
    d = json.loads(line)
    return WalSegmentLine(ts=d["ts"], span_start=d["span_start"], span_end=d["span_end"],
                          session_id=d["session_id"], text=d["text"])


def wal_dir(data_root: Path) -> Path:
    return Path(data_root) / "wal"


def record_dir(data_root: Path, record: WalRecord) -> Path:
    return wal_dir(data_root) / record.value


def segment_date(ts: str) -> str:
    return ts[:10]


def segment_path(data_root: Path, record: WalRecord, date: str) -> Path:
    return record_dir(data_root, record) / f"{date}.jsonl"
