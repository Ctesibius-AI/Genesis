from __future__ import annotations

from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.ledger.store import append, read_all
from genesis.linking.relatedness import FakeRelatednessScorer
from genesis.linking.semantic import apply_semantic_links


def _entry(eid, ts, summary, session="s1", **links):
    return LedgerEntry(entry_id=eid, ts=ts, summary=summary,
                       provenance=Provenance(eid, "a", "b", ["the principal"]),
                       links=Links(session_id=session, **links), extracted=Extracted.NO)


def test_same_topic_is_symmetric_backfilled(tmp_path):
    p = _entry("EP-1", "2026-08-17T10:00:00Z", "GRAFIX invoicing")
    append(tmp_path, p)
    cur = _entry("EP-2", "2026-08-17T10:05:00Z", "GRAFIX invoice PHR008")
    scorer = FakeRelatednessScorer()
    scorer.set("GRAFIX invoicing", "GRAFIX invoice PHR008", 0.9)

    apply_semantic_links(tmp_path, cur, scorer)

    assert cur.links.same_topic == ["EP-1"]
    assert cur.links.continues == "EP-1"  # same session + above SAME_TOPIC_MIN
    reloaded = {e.entry_id: e for e in read_all(tmp_path)}
    assert reloaded["EP-1"].links.same_topic == ["EP-2"]  # backfilled


def test_references_is_directional_no_backfill(tmp_path):
    p = _entry("EP-1", "2026-08-17T10:00:00Z", "the Mnemon repo")
    append(tmp_path, p)
    cur = _entry("EP-2", "2026-08-17T10:05:00Z", "a tangent about Mnemon")
    scorer = FakeRelatednessScorer()
    scorer.set("the Mnemon repo", "a tangent about Mnemon", 0.5)  # between REFERENCES and SAME_TOPIC

    apply_semantic_links(tmp_path, cur, scorer)

    assert cur.links.references == ["EP-1"]
    assert cur.links.same_topic == []
    assert read_all(tmp_path)[0].links.references == []  # no backfill for references


def test_never_links_a_future_entry(tmp_path):
    # a future entry EP-9 exists in the ledger with a LATER ts; it must be ignored (DR-09)
    append(tmp_path, _entry("EP-9", "2026-08-17T12:00:00Z", "future work"))
    cur = _entry("EP-2", "2026-08-17T10:05:00Z", "current work")
    scorer = FakeRelatednessScorer(default=1.0)  # everything scores max
    apply_semantic_links(tmp_path, cur, scorer)
    assert "EP-9" not in cur.links.same_topic
    assert "EP-9" not in cur.links.references


def test_explicit_continues_is_not_overwritten(tmp_path):
    append(tmp_path, _entry("EP-1", "2026-08-17T10:00:00Z", "topic"))
    cur = _entry("EP-2", "2026-08-17T10:05:00Z", "topic again", continues="EP-0")
    scorer = FakeRelatednessScorer(default=1.0)
    apply_semantic_links(tmp_path, cur, scorer)
    assert cur.links.continues == "EP-0"  # explicit save-time continues wins


def test_idempotent(tmp_path):
    append(tmp_path, _entry("EP-1", "2026-08-17T10:00:00Z", "x"))
    cur = _entry("EP-2", "2026-08-17T10:05:00Z", "y")
    scorer = FakeRelatednessScorer()
    scorer.set("x", "y", 0.9)
    apply_semantic_links(tmp_path, cur, scorer)
    apply_semantic_links(tmp_path, cur, scorer)
    assert cur.links.same_topic == ["EP-1"]  # no dupes
