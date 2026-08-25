# tests/test_recall_daemon.py
"""The warm read-only recall daemon — degrades to honest-empty, never breaks (design §7)."""
from __future__ import annotations

import pytest

from genesis.graph.engine import FakeGraph, GraphEdge, Verdict
from genesis.linking.relatedness import FakeRelatednessScorer
from genesis.recall.daemon import RecallDaemon, build_recall_daemon
from genesis.recall.search_backend import FakeRecallSearch
from genesis.recall.service import RecallService
from genesis.recall.tier import Tier


def _daemon(*, search=None, engine=None):
    engine = engine or FakeGraph()
    svc = RecallService(engine, FakeRelatednessScorer(default=0.5), search=search)
    return RecallDaemon(svc)


def test_serve_search_returns_results_when_backend_healthy():
    hit = GraphEdge(edge_id="a", fact="fact a", episodes=["EP-1"], verdict=Verdict.CONFIRMED, type="ABOUT")
    g = FakeGraph(); g.seed(hit)
    search = FakeRecallSearch(); search.set_semantic("q", [hit]); search.set_keyword("q", [hit])
    d = RecallDaemon(RecallService(g, FakeRelatednessScorer(default=0.5), search=search))
    assert d.serve_search("q", Tier.FULL).verdict.score == 100


def test_serve_search_degrades_to_honest_empty_on_backend_failure():
    class _Boom(FakeRecallSearch):
        def semantic(self, query, top_n):
            raise RuntimeError("graph backend down")
    d = _daemon(search=_Boom())
    r = d.serve_search("q", Tier.FULL)
    assert r.is_empty() and r.verdict is not None and r.verdict.score == 0  # honest-empty, no raise


def test_serve_expand_degrades_on_failure():
    class _BoomEngine(FakeGraph):
        def created_in_episode(self, episode_id):
            raise RuntimeError("graph read failed")
    d = _daemon(engine=_BoomEngine())
    r = d.serve_expand("EP-1", Tier.EPISODIC)
    assert r.is_empty()  # degraded, not raised


def test_build_recall_daemon_is_a_documented_stub():
    with pytest.raises((RuntimeError, NotImplementedError)):
        build_recall_daemon("/tmp/nope")
