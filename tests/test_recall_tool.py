# tests/test_recall_tool.py
"""The Daimon-driven recall tool over the service (spec §4.7b; design §8; DR-08 — no hook)."""
from __future__ import annotations

from genesis.graph.engine import FakeGraph, GraphEdge, Verdict
from genesis.linking.relatedness import FakeRelatednessScorer
from genesis.recall.scorer import EmptyCause
from genesis.recall.search_backend import FakeRecallSearch
from genesis.recall.service import RecallService
from genesis.recall.tier import Tier
from genesis.recall.tool import format_for_injection, recall_tool


def _service(edges_by_query):
    g = FakeGraph()
    search = FakeRecallSearch()
    for q, edges in edges_by_query.items():
        for e in edges:
            g.seed(e)
        search.set_semantic(q, edges)
        search.set_keyword(q, edges)
    return RecallService(g, FakeRelatednessScorer(default=0.5), search=search)


def test_recall_tool_drives_full_search():
    hit = GraphEdge(edge_id="a", fact="PHR008 issued", episodes=["EP-9"], verdict=Verdict.CONFIRMED, type="ABOUT")
    r = recall_tool(_service({"invoicing": [hit]}), "invoicing")
    assert r.verdict.score == 100
    assert [re.edge.edge_id for re in r.edges] == ["a"]


def test_recall_tool_honest_empty_formats_dr33_line():
    r = recall_tool(_service({}), "nothing known")
    assert r.verdict.score == 0
    out = format_for_injection(r)
    assert "don't have anything related" in out.lower()


def test_recall_tool_pending_formats_queue_lag_not_absence():
    svc = _service({})
    r = recall_tool(svc, "just saved", cause=EmptyCause.PENDING)
    out = format_for_injection(r)
    assert "not yet extracted" in out.lower() or "queue" in out.lower()


def test_format_labels_unverified_edges():
    e = GraphEdge(edge_id="a", fact="draft fact", episodes=["EP-1"], verdict=Verdict.PROVISIONAL, type="ABOUT")
    r = recall_tool(_service({"q": [e]}), "q")
    assert "[unverified]" in format_for_injection(r)
