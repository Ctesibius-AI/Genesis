from __future__ import annotations

from pathlib import Path

from genesys.diary.inputs import DiaryInputs, LedgerItem, gather_ledger_items
from genesys.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesys.ledger.store import append


def _entry(eid, ts, summary="s", extracted=Extracted.NO, enrichment=None) -> LedgerEntry:
    return LedgerEntry(
        entry_id=eid, ts=ts, summary=summary,
        provenance=Provenance(eid, ts, ts, ["the principal"]),
        links=Links(session_id="sess-1"),
        extracted=extracted, enrichment=enrichment,
    )


def test_only_entries_within_the_window(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-01.0001", "2026-08-01T10:00:00+00:00"))  # >6d old
    append(tmp_path, _entry("EP-2026-08-16.0001", "2026-08-16T10:00:00+00:00"))  # in window
    items = gather_ledger_items(tmp_path, "2026-08-17T10:00:00+00:00", window_days=6)
    assert [i.ts for i in items] == ["2026-08-16T10:00:00+00:00"]


def test_unextracted_entry_is_marked_unverified(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-16.0001", "2026-08-16T10:00:00+00:00",
                            summary="fast note", extracted=Extracted.NO))
    item = gather_ledger_items(tmp_path, "2026-08-17T10:00:00+00:00")[0]
    assert item.unverified is True
    assert item.summary == "fast note"


def test_enriched_summary_preferred_and_not_unverified(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-16.0001", "2026-08-16T10:00:00+00:00",
                            summary="raw", extracted=Extracted.DONE,
                            enrichment={"enriched_summary": "polished"}))
    item = gather_ledger_items(tmp_path, "2026-08-17T10:00:00+00:00")[0]
    assert item.summary == "polished"
    assert item.unverified is False


def test_diary_inputs_defaults_empty_task_and_question_lists():
    di = DiaryInputs(ledger=[])
    assert di.tasks == []
    assert di.open_questions == []


def test_in_progress_entry_is_marked_unverified(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-16.0001", "2026-08-16T10:00:00+00:00",
                            summary="work in progress", extracted=Extracted.IN_PROGRESS))
    item = gather_ledger_items(tmp_path, "2026-08-17T10:00:00+00:00")[0]
    assert item.unverified is True
    assert item.summary == "work in progress"
