# tests/test_recall_verdict.py
"""DR-33 verdict-aware serving over a GraphEdge (spec §4.7a, §4.7b)."""
from __future__ import annotations

from genesis.graph.engine import GraphEdge, Verdict
from genesis.recall.verdict import is_servable, servable_edges, serving_label


def _edge(eid, verdict=Verdict.PROVISIONAL, contested=False):
    return GraphEdge(edge_id=eid, fact=f"f {eid}", episodes=["EP-1"],
                     verdict=verdict, contested=contested)


def test_quarantined_is_never_servable():
    assert is_servable(_edge("q", Verdict.QUARANTINED)) is False


def test_provisional_and_confirmed_are_servable():
    assert is_servable(_edge("p", Verdict.PROVISIONAL)) is True
    assert is_servable(_edge("c", Verdict.CONFIRMED)) is True


def test_serving_label_reflects_verdict_and_contest():
    assert serving_label(_edge("c", Verdict.CONFIRMED)) == ""
    assert serving_label(_edge("p", Verdict.PROVISIONAL)) == "[unverified]"
    assert serving_label(_edge("x", Verdict.CONFIRMED, contested=True)) == "[contested]"


def test_servable_edges_drops_only_quarantined():
    edges = [_edge("p", Verdict.PROVISIONAL), _edge("q", Verdict.QUARANTINED),
             _edge("c", Verdict.CONFIRMED)]
    kept = {e.edge_id for e in servable_edges(edges)}
    assert kept == {"p", "c"}
