from __future__ import annotations

from genesis.graph.engine import FakeGraph, GraphEdge
from genesis.supervisor.detection import detect


def test_detect_finds_created_and_invalidated():
    g = FakeGraph()
    g.seed(GraphEdge("old", "old", ["EP-0"]))
    g.script_episode("EP-1", creates=[GraphEdge("new", "new", ["EP-1"])],
                     expires=["old"], at="2026-08-17T10:00:03+00:00")
    g.add_episode("EP-1", "c")
    d = detect(g, "EP-1", "2026-08-17T10:00:00+00:00", "2026-08-17T10:00:10+00:00")
    assert [e.edge_id for e in d.created] == ["new"]
    assert [e.edge_id for e in d.invalidated] == ["old"]


def test_detect_empty_when_nothing_in_window():
    g = FakeGraph()
    g.seed(GraphEdge("e1", "f", ["EP-1"]))
    d = detect(g, "EP-1", "2026-08-17T10:00:00+00:00", "2026-08-17T10:00:10+00:00")
    assert [e.edge_id for e in d.created] == ["e1"]
    assert d.invalidated == []
