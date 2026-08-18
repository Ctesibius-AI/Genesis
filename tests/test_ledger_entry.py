from __future__ import annotations

from genesys.ledger.entry import (
    Extracted,
    LedgerEntry,
    Links,
    Provenance,
    from_jsonl,
    to_jsonl,
)


def _entry() -> LedgerEntry:
    return LedgerEntry(
        entry_id="EP-2026-08-17.0001",
        ts="2026-08-17T10:00:00+00:00",
        summary="Decided to use FalkorDB Lite for dev.",
        provenance=Provenance(
            episode_id="EP-2026-08-17.0001",
            span_start="2026-08-17T09:58:00+00:00",
            span_end="2026-08-17T10:00:00+00:00",
            speakers=["the principal", "Daimon"],
        ),
        links=Links(session_id="sess-1", prev=None),
    )


def test_new_entry_defaults_to_queued_and_unenriched():
    e = _entry()
    assert e.extracted is Extracted.NO
    assert e.enrichment is None


def test_to_jsonl_is_single_line():
    line = to_jsonl(_entry())
    assert "\n" not in line
    assert line.startswith("{") and line.endswith("}")


def test_jsonl_round_trip_preserves_everything():
    e = _entry()
    back = from_jsonl(to_jsonl(e))
    assert back == e
    assert back.extracted is Extracted.NO
    assert back.provenance.speakers == ["the principal", "Daimon"]
