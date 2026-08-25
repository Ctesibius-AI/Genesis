# tests/test_recall_anchors.py
"""Code-inserted diary anchors from ledger links (spec §4.7b; App E delta)."""
from __future__ import annotations

from genesis.diary.briefing import Briefing
from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.ledger.store import append
from genesis.recall.anchors import DiaryAnchor, attach_anchors, resolve_anchors


def _entry(eid, ts, summary, **links):
    return LedgerEntry(entry_id=eid, ts=ts, summary=summary,
                       provenance=Provenance(eid, "0", "1", ["the principal"]),
                       links=Links(session_id="s1", **links), extracted=Extracted.DONE)


def test_resolve_anchors_from_reference_and_same_topic_links(tmp_path):
    append(tmp_path, _entry("EP-1", "2026-08-17T10:00:00Z", "old plan"))
    append(tmp_path, _entry("EP-2", "2026-08-17T10:05:00Z", "Phrase invoicing",
                            references=["EP-1"], same_topic=["EP-1"]))
    anchors = resolve_anchors(tmp_path)
    by_name = {a.anchor: a for a in anchors}
    assert "Phrase invoicing" in by_name
    assert set(by_name["Phrase invoicing"].episode_ids) == {"EP-1", "EP-2"}


def test_entries_without_link_sources_yield_no_anchor(tmp_path):
    # caused_by / prev / next are NOT anchor sources (§4.7b names references/same_topic/supersedes)
    append(tmp_path, _entry("EP-1", "2026-08-17T10:00:00Z", "solo", caused_by=["EP-0"], prev="EP-0"))
    assert resolve_anchors(tmp_path) == []


def test_attach_anchors_marks_only_content_already_in_the_briefing():
    b = Briefing(sections={"TOP OF MIND": "Resumed Phrase invoicing for PHR008."})
    anchors = [DiaryAnchor("Phrase invoicing", ["EP-2"]),
               DiaryAnchor("Something Not In Diary", ["EP-9"])]
    out = attach_anchors(b, anchors)
    assert "ANCHORS" in out.sections
    assert "Phrase invoicing" in out.sections["ANCHORS"]
    assert "Something Not In Diary" not in out.sections["ANCHORS"]  # not already in the diary
    assert b.sections.get("ANCHORS") is None  # original not mutated


def test_attach_anchors_never_adds_perceives_or_soul_content():
    b = Briefing(sections={"TOP OF MIND": "worked on the recall fence"})
    out = attach_anchors(b, [DiaryAnchor("recall fence", ["EP-7"])])
    text = out.render().lower()
    assert "perceives" not in text and "soul" not in text
