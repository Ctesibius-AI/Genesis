"""The courier's WAL append+annotate step (spec §2.1/§2.2).

On each ring the courier appends the delta to BOTH rolling records (memory-grade + flight
recorder, DR-37) then annotates the (cursor, now) window over the memory-grade record (DR-43).
This is the shared move behind the automatic hook trigger, backfill, and the precompact final
append. Skip-when-nothing-new (no new memory-grade material ⇒ append nothing, return None)
mirrors Plan 1's cursor-delta guard, so N rings produce N non-overlapping annotations (no F4
n² re-copy).
"""

from __future__ import annotations

from pathlib import Path

from genesys.capture.mirror import CaptureResult, flight_span_from_result, raw_span_from_result
from genesys.ledger.entry import LedgerEntry
from genesys.wal.annotate import save_annotation
from genesys.wal.record import WalRecord
from genesys.wal.store import append_delta


def append_and_annotate(data_root: Path, *, capture_result: CaptureResult, cursor: str,
                        now: str, session_id: str, speakers: list[str], jot: str,
                        salience: bool = False,
                        annotate: bool = True) -> LedgerEntry | None:
    """Append both rings then (optionally) annotate the (cursor, now) memory-grade window.

    When ``annotate=True`` (default): append both WAL rings + create the salient/normal
    ``save_annotation`` and return the ``LedgerEntry``.

    When ``annotate=False``: append both WAL rings as a cheap safety net (raw WAL only)
    but skip ``save_annotation`` entirely — no queue item is created. Returns ``None``.

    In both cases the skip-when-nothing-new guard is applied first: if the memory-grade
    delta is empty, return ``None`` immediately and append nothing.
    """
    mem_delta = raw_span_from_result(capture_result)
    if not mem_delta.strip():
        return None  # nothing new for this session — skip (Plan 1 parity)
    fly_delta = flight_span_from_result(capture_result)
    append_delta(data_root, WalRecord.MEMORY_GRADE, ts=now, span_start=cursor,
                 span_end=now, session_id=session_id, text=mem_delta)
    append_delta(data_root, WalRecord.FLIGHT_RECORDER, ts=now, span_start=cursor,
                 span_end=now, session_id=session_id, text=fly_delta)
    if not annotate:
        return None  # WAL rings grown; no ledger queue item
    return save_annotation(data_root, start_ts=cursor, end_ts=now, jot=jot,
                           session_id=session_id, speakers=speakers,
                           record=WalRecord.MEMORY_GRADE, salience=salience)
