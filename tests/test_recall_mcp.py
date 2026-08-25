"""BT-8: the recall MCP response shaping (design §4.2) — allow-list-scoped + honest-empty.

The response always carries the verdict cause so the caller distinguishes empty (ABSENT) from
down (DEGRADED) from queue-lag (PENDING) — never a bare [].
"""
from __future__ import annotations

from genesys.graph.engine import FakeGraph, GraphEdge, Verdict
from genesys.linking.relatedness import FakeRelatednessScorer
from genesys.recall.daemon import RecallDaemon
from genesys.recall.mcp_server import recall_response
from genesys.recall.scorer import EmptyCause
from genesys.recall.search_backend import FakeRecallSearch
from genesys.recall.service import RecallService
from genesys.recall.tier import Tier


def _daemon(search):
    return RecallDaemon(RecallService(FakeGraph(), FakeRelatednessScorer(default=0.5), search=search))


def test_response_shapes_served_edges():
    g = FakeGraph()
    hit = GraphEdge("a", "alpha works on beta", ["EP-1"], verdict=Verdict.CONFIRMED, type="WORKS_ON")
    g.seed(hit)
    search = FakeRecallSearch(); search.set_semantic("q", [hit]); search.set_keyword("q", [hit])
    d = RecallDaemon(RecallService(g, FakeRelatednessScorer(default=0.5), search=search))
    resp = recall_response(d.serve_search("q", Tier.FULL))
    assert resp["served"] is True
    assert resp["edges"] and resp["edges"][0]["fact"] == "alpha works on beta"
    assert resp["verdict"]["cause"] == "absent"  # served -> cause normalized to absent


def test_response_is_honest_empty_absent():
    resp = recall_response(_daemon(FakeRecallSearch()).serve_search("nothing", Tier.FULL))
    assert resp["served"] is False
    assert resp["edges"] == []
    assert resp["verdict"]["cause"] == "absent"


def test_response_surfaces_degraded_when_down():
    class _Boom(FakeRecallSearch):
        def semantic(self, query, top_n):
            raise RuntimeError("down")
    resp = recall_response(_daemon(_Boom()).serve_search("q", Tier.FULL))
    assert resp["served"] is False
    assert resp["verdict"]["cause"] == EmptyCause.DEGRADED.value
    assert "unavailable" in resp["message"].lower()  # never a bare []
