"""BT-6b / Graphiti fix #3 — invalidation-subtraction, closed (design §7 #3, v1).

Two halves: (1) at the commit path, add_episode returns CREATED edges only and the invalidated
edge is subtracted and readable post-commit via invalidated_in_window (F-11 — already satisfied by
the engine); (2) recall never serves an invalidated (superseded) edge as current.
"""
from __future__ import annotations

from genesys.graph.engine import FakeGraph, GraphEdge, Verdict
from genesys.linking.relatedness import FakeRelatednessScorer
from genesys.persona.department import PerceptionDepartment
from genesys.recall.service import RecallService
from genesys.recall.tier import Tier


def test_invalidation_subtracted_post_commit():
    g = FakeGraph()
    g.seed(GraphEdge("e1", "old fact", ["EP-1"], verdict=Verdict.CONFIRMED, type="ABOUT",
                     valid_at="t0"))
    g.script_episode("EP-2", creates=[GraphEdge("e2", "new fact", ["EP-2"],
                     verdict=Verdict.CONFIRMED, type="ABOUT")], expires=["e1"], at="t1")
    res = g.add_episode("EP-2", "body")
    assert [e.edge_id for e in res.created] == ["e2"]          # created-only (F-11 #3)
    inval = g.invalidated_in_window("t1", "t1")
    assert [e.edge_id for e in inval] == ["e1"]                # e1 subtracted post-commit
    assert g.get("e1").invalid_at == "t1"


def test_recall_does_not_serve_invalidated_edge():
    g = FakeGraph()
    g.seed(GraphEdge("live", "current fact", ["EP-1"], verdict=Verdict.CONFIRMED, type="ABOUT"))
    g.seed(GraphEdge("dead", "superseded fact", ["EP-1"], verdict=Verdict.CONFIRMED, type="ABOUT",
                     invalid_at="t1", expired_at="t1"))
    svc = RecallService(g, PerceptionDepartment(), FakeRelatednessScorer(default=0.5))
    r = svc.expand("EP-1", Tier.EPISODIC)
    assert [re.edge.edge_id for re in r.edges] == ["live"]     # invalidated edge not resurrected
