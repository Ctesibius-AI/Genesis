# tests/test_recall_search_backend.py
"""The semantic+keyword search-channel seam (Fake offline; real is a documented stub)."""
from __future__ import annotations

import pytest

from genesys.graph.client import ClientEdge
from genesys.graph.engine import FakeGraph, GraphEdge, Verdict
from genesys.recall.search_backend import (
    FakeRecallSearch,
    GraphSearchChannel,
    GraphSearchRecallSearch,
    real_recall_search,
)


def _e(eid):
    return GraphEdge(edge_id=eid, fact=f"f {eid}", episodes=["EP-1"])


def test_fake_scripts_both_channels_and_truncates_to_top_n():
    s = FakeRecallSearch()
    s.set_semantic("Acme invoicing", [_e("a"), _e("b"), _e("c")])
    s.set_keyword("Acme invoicing", [_e("a")])
    assert [e.edge_id for e in s.semantic("Acme invoicing", 2)] == ["a", "b"]
    assert [e.edge_id for e in s.keyword("Acme invoicing", 5)] == ["a"]


def test_fake_unscripted_query_is_empty_both_channels():
    s = FakeRecallSearch()
    assert s.semantic("nothing", 5) == []
    assert s.keyword("nothing", 5) == []


def test_real_recall_search_needs_the_graph_extra_offline():
    # Same posture as real_scorer / agent_sdk_orchestrator: absent extra -> RuntimeError.
    # The real graphiti binding is lazy and offline-unreachable; offline uses the Fake.
    with pytest.raises(RuntimeError):
        real_recall_search(FakeGraph())


# --------------------------------------------------------------------------------------
# GraphSearchRecallSearch — the real adapter's OFFLINE-TESTABLE shaping/merge/routing.
# We inject a fake per-channel graph-search callable returning canned ClientEdge hits;
# no graphiti, no embedder, no network. This proves the ClientEdge->GraphEdge shaping,
# the semantic/keyword channel routing, verdict preservation (so the service's quarantine
# filter can fire downstream), and top_n truncation.
# --------------------------------------------------------------------------------------


class _FakeGraphSearch:
    """Records (query, top_n, channel) calls; returns scripted ClientEdge hits per channel."""

    def __init__(self):
        self.calls: list[tuple[str, int, GraphSearchChannel]] = []
        self._hits: dict[GraphSearchChannel, list[ClientEdge]] = {}

    def set(self, channel: GraphSearchChannel, edges: list[ClientEdge]) -> None:
        self._hits[channel] = list(edges)

    def __call__(self, query: str, top_n: int, channel: GraphSearchChannel) -> list[ClientEdge]:
        self.calls.append((query, top_n, channel))
        return self._hits.get(channel, [])[:top_n]


def _ce(uuid, fact, *, verdict=None):
    attrs = {"verdict": verdict.value} if verdict is not None else {}
    return ClientEdge(uuid=uuid, fact=fact, episodes=["EP-1"], attributes=attrs)


def test_graph_search_routes_semantic_and_keyword_to_distinct_channels():
    gs = _FakeGraphSearch()
    gs.set(GraphSearchChannel.SEMANTIC, [_ce("s1", "semantic hit")])
    gs.set(GraphSearchChannel.KEYWORD, [_ce("k1", "keyword hit")])
    backend = GraphSearchRecallSearch(gs)

    sem = backend.semantic("q", 5)
    kw = backend.keyword("q", 5)

    assert [e.edge_id for e in sem] == ["s1"]
    assert [e.edge_id for e in kw] == ["k1"]
    # each channel hit its own graphiti search method
    assert (("q", 5, GraphSearchChannel.SEMANTIC) in gs.calls)
    assert (("q", 5, GraphSearchChannel.KEYWORD) in gs.calls)


def test_graph_search_shapes_client_edges_into_graph_edges_preserving_verdict():
    gs = _FakeGraphSearch()
    gs.set(GraphSearchChannel.SEMANTIC,
           [_ce("q1", "quarantined", verdict=Verdict.QUARANTINED),
            _ce("c1", "confirmed", verdict=Verdict.CONFIRMED)])
    backend = GraphSearchRecallSearch(gs)

    out = backend.semantic("q", 5)
    assert all(isinstance(e, GraphEdge) for e in out)
    by_id = {e.edge_id: e for e in out}
    # verdict must survive the shaping so the SERVICE quarantine filter can drop q1
    assert by_id["q1"].verdict is Verdict.QUARANTINED
    assert by_id["c1"].verdict is Verdict.CONFIRMED


def test_graph_search_truncates_to_top_n_and_passes_it_through():
    gs = _FakeGraphSearch()
    gs.set(GraphSearchChannel.KEYWORD, [_ce(f"e{i}", f"f{i}") for i in range(5)])
    backend = GraphSearchRecallSearch(gs)

    out = backend.keyword("q", 2)
    assert [e.edge_id for e in out] == ["e0", "e1"]
    assert gs.calls[-1] == ("q", 2, GraphSearchChannel.KEYWORD)


def test_graph_search_empty_channel_returns_empty_list():
    backend = GraphSearchRecallSearch(_FakeGraphSearch())
    assert backend.semantic("nothing", 5) == []
    assert backend.keyword("nothing", 5) == []
