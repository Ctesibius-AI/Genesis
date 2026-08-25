from __future__ import annotations

from pathlib import Path

from genesis.ledger.entry import LedgerEntry, Links, Provenance
from genesis.ledger.store import append, read_since


def _entry(eid: str, ts: str) -> LedgerEntry:
    return LedgerEntry(
        entry_id=eid, ts=ts, summary="s",
        provenance=Provenance(eid, ts, ts, ["the principal"]),
        links=Links(session_id="sess-1"),
    )


def test_read_since_compares_by_instant_not_string(tmp_path: Path):
    # 09:00-05:00 == 14:00Z, which is AFTER the 12:00Z cutoff — must be included,
    # even though the string "…T09:…" sorts BEFORE "…T12:…".
    append(tmp_path, _entry("EP-2026-08-17.0001", "2026-08-17T09:00:00-05:00"))
    append(tmp_path, _entry("EP-2026-08-17.0002", "2026-08-17T08:00:00+00:00"))  # before cutoff
    got = [e.entry_id for e in read_since(tmp_path, "2026-08-17T12:00:00+00:00")]
    assert got == ["EP-2026-08-17.0001"]


def test_read_since_utc_only_still_works(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-10.0001", "2026-08-10T10:00:00+00:00"))
    append(tmp_path, _entry("EP-2026-08-17.0001", "2026-08-17T10:00:00+00:00"))
    got = [e.entry_id for e in read_since(tmp_path, "2026-08-15T00:00:00+00:00")]
    assert got == ["EP-2026-08-17.0001"]
