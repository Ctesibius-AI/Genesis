from __future__ import annotations

from genesys.extraction.analyst import Episode
from genesys.extraction.grapher import render_manifest, run_grapher
from genesys.graph.engine import FakeGraph, GraphEdge


def test_grapher_calls_add_episode_and_returns_created():
    g = FakeGraph()
    g.script_episode("EP-1", creates=[GraphEdge("e1", "decided X", ["EP-1"])], at="2026-08-17T10:00:00+00:00")
    res = run_grapher(g, Episode("EP-1", "content", "jot"))
    assert [e.edge_id for e in res.created] == ["e1"]


def test_render_manifest_one_line_per_fact():
    from genesys.graph.engine import AddResult
    m = render_manifest(AddResult(created=[GraphEdge("e1", "fact one", ["EP-1"]),
                                           GraphEdge("e2", "fact two", ["EP-1"])]))
    assert m == "e1: fact one\ne2: fact two"
