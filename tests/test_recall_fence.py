# tests/test_recall_fence.py
"""Recall persona-fence composition — a CALL into P6 lock/leakcheck (spec §8.6 S2, V-1a)."""
from __future__ import annotations

import pytest

from genesys.graph.engine import GraphEdge
from genesys.persona.department import PerceptionDepartment
from genesys.persona.perceives import PRINCIPAL
from genesys.persona.release import ReleaseContext, closed
from genesys.recall.fence import fence_edges, opinion_edges_for_recall, perceives_anchor


def _fact(eid):
    return GraphEdge(edge_id=eid, fact=f"fact {eid}", episodes=["EP-1"])


def _perceived(eid, anchor):
    # the graph tags a perceived-of-principal edge C3/C4 with class_="perceives" (§9.4/R-N);
    # its anchor rides on the fact for this offline model.
    return GraphEdge(edge_id=eid, fact=anchor, episodes=["EP-1"], class_="perceives")


def test_non_perceived_edges_always_kept():
    kept, served = fence_edges([_fact("a"), _fact("b")], closed())
    assert {e.edge_id for e in kept} == {"a", "b"}
    assert served == []


def test_perceived_dropped_fail_closed_when_context_closed():
    kept, served = fence_edges([_fact("a"), _perceived("p", "diligence")], None)
    assert {e.edge_id for e in kept} == {"a"}  # perceived dropped: no open key
    assert served == []


def test_perceived_kept_only_when_context_covers_its_anchor():
    ctx = ReleaseContext(open=True, open_anchors=["diligence"])
    kept, served = fence_edges([_perceived("p", "diligence")], ctx)
    assert {e.edge_id for e in kept} == {"p"}
    assert served == ["diligence"]


def test_perceived_dropped_when_context_open_but_anchor_not_covered():
    ctx = ReleaseContext(open=True, open_anchors=["something-else"])
    kept, served = fence_edges([_perceived("p", "diligence")], ctx)
    assert kept == [] and served == []  # fail-closed on the specific anchor


def test_opinion_edges_for_recall_is_always_empty_R_M():
    dept = PerceptionDepartment()
    assert opinion_edges_for_recall(dept, ReleaseContext(open=True, open_anchors=["x"])) == []


def test_perceives_anchor_none_for_a_plain_fact():
    assert perceives_anchor(_fact("a")) is None
