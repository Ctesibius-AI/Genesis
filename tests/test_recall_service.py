# tests/test_recall_service.py
"""The recall service: fenced, verdict-gated, ranked expand + three-channel search (§4.7b)."""
from __future__ import annotations

import pytest

from genesys.graph.engine import FakeGraph, GraphEdge, Verdict
from genesys.linking.relatedness import FakeRelatednessScorer
from genesys.persona.department import PerceptionDepartment
from genesys.persona.release import ReleaseContext, closed
from genesys.recall.scorer import EmptyCause
from genesys.recall.search_backend import FakeRecallSearch
from genesys.recall.service import RecallResult, RecallService
from genesys.recall.tier import Tier


def _edge(eid, fact, ep="EP-1", verdict=Verdict.CONFIRMED, class_=None):
    return GraphEdge(edge_id=eid, fact=fact, episodes=[ep], verdict=verdict, class_=class_)


def _svc(engine, *, search=None, scorer=None):
    return RecallService(engine, PerceptionDepartment(),
                         scorer or FakeRelatednessScorer(default=0.5), search=search)


def test_expand_none_tier_returns_empty_no_read():
    g = FakeGraph()
    r = _svc(g).expand("EP-1", Tier.NONE)
    assert r.is_empty() and r.verdict is None


def test_expand_returns_ranked_servable_fenced_edges():
    g = FakeGraph()
    g.seed(_edge("a", "alpha", "EP-1"))
    g.seed(_edge("b", "beta", "EP-1"))
    g.seed(_edge("q", "quarantined fact", "EP-1", verdict=Verdict.QUARANTINED))
    scorer = FakeRelatednessScorer(default=0.0)
    scorer.set("EP-1", "alpha", 0.9)
    scorer.set("EP-1", "beta", 0.3)
    r = _svc(g, scorer=scorer).expand("EP-1", Tier.EPISODIC)
    ids = [re.edge.edge_id for re in r.edges]
    assert ids == ["a", "b"]           # quarantined 'q' dropped; ranked alpha>beta
    assert r.verdict is None            # expand is not the honest-empty terminal


def test_expand_drops_perceived_of_principal_fail_closed():
    g = FakeGraph()
    g.seed(_edge("a", "alpha", "EP-1"))
    g.seed(_edge("p", "diligence", "EP-1", class_="perceives"))
    r = _svc(g).expand("EP-1", Tier.DEEP, ctx=closed())  # closed context, fail-closed
    assert [re.edge.edge_id for re in r.edges] == ["a"]  # perceived dropped
    assert r.served_anchors == []


def test_search_three_channel_score_and_honest_empty():
    g = FakeGraph()
    hit = _edge("a", "Acme invoicing INV-042", "EP-9")
    g.seed(hit)
    search = FakeRecallSearch()
    search.set_semantic("invoicing", [hit])
    search.set_keyword("invoicing", [hit])
    svc = _svc(g, search=search)
    r = svc.search("invoicing", Tier.FULL, top_n=5)
    # semantic + keyword + graph(engine.get confirms) = 3 -> 100
    assert r.verdict is not None and r.verdict.score == 100
    assert [re.edge.edge_id for re in r.edges] == ["a"]

    empty = svc.search("nothing here", Tier.FULL)
    assert empty.verdict.score == 0 and empty.is_empty()


def test_search_pending_cause_is_carried_into_empty_verdict():
    svc = _svc(FakeGraph(), search=FakeRecallSearch())
    r = svc.search("just saved", Tier.FULL, cause=EmptyCause.PENDING)
    assert r.verdict.score == 0 and r.verdict.cause is EmptyCause.PENDING


def test_search_without_backend_raises():
    with pytest.raises(RuntimeError):
        _svc(FakeGraph()).search("x", Tier.FULL)
