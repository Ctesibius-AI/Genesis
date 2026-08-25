from __future__ import annotations

from genesis.graph.engine import FakeGraph, GraphEdge
from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.linking.supersession import apply_supersession


def _entry(eid, ts):
    return LedgerEntry(entry_id=eid, ts=ts, summary=f"s {eid}",
                       provenance=Provenance(eid, "a", "b", ["the principal"]),
                       links=Links(session_id="s1"), extracted=Extracted.NO)


def test_records_supersedes_and_writes_graph(tmp_path):
    eng = FakeGraph()
    eng.seed(GraphEdge(edge_id="edge-old", fact="uses X", episodes=["EP-1"]))
    cur = _entry("EP-2", "2026-08-17T10:05:00Z")

    apply_supersession(tmp_path, cur, eng,
                       superseded_entry_ids=["EP-1"], superseded_edge_ids=["edge-old"])

    assert cur.links.supersedes == ["EP-1"]
    assert eng.get("edge-old").superseded_by == "EP-2"  # graph projection


def test_caused_by_and_idempotent(tmp_path):
    eng = FakeGraph()
    cur = _entry("EP-3", "2026-08-17T11:00:00Z")
    apply_supersession(tmp_path, cur, eng, superseded_entry_ids=["EP-1"], caused_by=["EP-0"])
    apply_supersession(tmp_path, cur, eng, superseded_entry_ids=["EP-1"], caused_by=["EP-0"])
    assert cur.links.supersedes == ["EP-1"]  # no dupes
    assert cur.links.caused_by == ["EP-0"]
