"""F4-interim cursor helper: newest banked cursor per session (spec §2.2/§7 item 2)."""
from __future__ import annotations

from pathlib import Path

from genesys.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesys.ledger.store import append
from genesys.save_cursor import entry_cursor, latest_span_end_for_session


def _entry(eid, ts, session_id, *, span_end="") -> LedgerEntry:
    return LedgerEntry(
        entry_id=eid, ts=ts, summary="s",
        provenance=Provenance(eid, "", span_end, ["the principal"]),
        links=Links(session_id=session_id), extracted=Extracted.NO,
    )


def test_entry_cursor_prefers_span_end_when_present():
    e = _entry("EP-1", "2026-08-18T10:00:00+00:00", "s1", span_end="2026-08-18T10:05:00+00:00")
    assert entry_cursor(e) == "2026-08-18T10:05:00+00:00"


def test_entry_cursor_falls_back_to_ts_when_span_end_empty():
    # The live reality today: _timestamps_from_events -> ("",""), so span_end == "".
    e = _entry("EP-1", "2026-08-18T10:00:00+00:00", "s1", span_end="")
    assert entry_cursor(e) == "2026-08-18T10:00:00+00:00"


def test_latest_cursor_is_the_max_over_the_session(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-18.0001", "2026-08-18T10:00:00+00:00", "s1"))
    append(tmp_path, _entry("EP-2026-08-18.0002", "2026-08-18T11:30:00+00:00", "s1"))
    append(tmp_path, _entry("EP-2026-08-18.0003", "2026-08-18T09:00:00+00:00", "s2"))
    assert latest_span_end_for_session(tmp_path, "s1") == "2026-08-18T11:30:00+00:00"
    assert latest_span_end_for_session(tmp_path, "s2") == "2026-08-18T09:00:00+00:00"


def test_unknown_or_empty_session_returns_empty(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-18.0001", "2026-08-18T10:00:00+00:00", "s1"))
    assert latest_span_end_for_session(tmp_path, "nope") == ""
    assert latest_span_end_for_session(tmp_path, "") == ""
    assert latest_span_end_for_session(tmp_path, None) == ""  # type: ignore[arg-type]
