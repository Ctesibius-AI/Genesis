from __future__ import annotations

from pathlib import Path

from genesys.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesys.ledger.store import (
    append,
    month_path,
    read_all,
    read_since,
    update,
)


def _entry(eid: str, ts: str, summary: str = "s") -> LedgerEntry:
    return LedgerEntry(
        entry_id=eid,
        ts=ts,
        summary=summary,
        provenance=Provenance(eid, ts, ts, ["the principal"]),
        links=Links(session_id="sess-1"),
    )


def test_append_writes_month_indexed_file(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-17.0001", "2026-08-17T10:00:00+00:00"))
    assert month_path(tmp_path, "2026-08-17T10:00:00+00:00").name == "2026-08.jsonl"
    assert month_path(tmp_path, "2026-08-17T10:00:00+00:00").exists()


def test_read_all_returns_entries_in_ts_order(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-17.0002", "2026-08-17T11:00:00+00:00"))
    append(tmp_path, _entry("EP-2026-08-17.0001", "2026-08-17T10:00:00+00:00"))
    got = [e.entry_id for e in read_all(tmp_path)]
    assert got == ["EP-2026-08-17.0001", "EP-2026-08-17.0002"]


def test_read_since_filters(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-10.0001", "2026-08-10T10:00:00+00:00"))
    append(tmp_path, _entry("EP-2026-08-17.0001", "2026-08-17T10:00:00+00:00"))
    got = [e.entry_id for e in read_since(tmp_path, "2026-08-15T00:00:00+00:00")]
    assert got == ["EP-2026-08-17.0001"]


def test_update_replaces_only_the_matching_entry(tmp_path: Path):
    a = _entry("EP-2026-08-17.0001", "2026-08-17T10:00:00+00:00")
    b = _entry("EP-2026-08-17.0002", "2026-08-17T11:00:00+00:00")
    append(tmp_path, a)
    append(tmp_path, b)
    a.extracted = Extracted.DONE
    update(tmp_path, a)
    by_id = {e.entry_id: e for e in read_all(tmp_path)}
    assert by_id["EP-2026-08-17.0001"].extracted is Extracted.DONE
    assert by_id["EP-2026-08-17.0002"].extracted is Extracted.NO  # untouched
    assert len(by_id) == 2  # nothing deleted
