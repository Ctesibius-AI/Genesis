from __future__ import annotations

from pathlib import Path

from genesis.doctor import doctor_requeue
from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.ledger.store import append, read_all


def _entry(eid, ts, state=Extracted.NO) -> LedgerEntry:
    return LedgerEntry(
        entry_id=eid,
        ts=ts,
        summary="s",
        provenance=Provenance(eid, ts, ts, ["the principal"]),
        links=Links(session_id="sess-1"),
        extracted=state,
    )


def test_requeues_stuck_in_progress_entries(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-17.0001", "2026-08-17T10:00:00+00:00", Extracted.IN_PROGRESS))
    append(tmp_path, _entry("EP-2026-08-17.0002", "2026-08-17T11:00:00+00:00", Extracted.NO))
    requeued = doctor_requeue(tmp_path)
    assert requeued == ["EP-2026-08-17.0001"]
    by_id = {e.entry_id: e.extracted for e in read_all(tmp_path)}
    assert by_id["EP-2026-08-17.0001"] is Extracted.NO


def test_is_idempotent(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-17.0001", "2026-08-17T10:00:00+00:00", Extracted.IN_PROGRESS))
    doctor_requeue(tmp_path)
    assert doctor_requeue(tmp_path) == []


def test_leaves_done_and_queued_untouched(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-17.0001", "2026-08-17T10:00:00+00:00", Extracted.DONE))
    assert doctor_requeue(tmp_path) == []
