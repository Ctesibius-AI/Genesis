from __future__ import annotations

from pathlib import Path

from genesis.graph.engine import FakeGraph, GraphEdge
from genesis.supervisor.judgment import judge_invalidations
from genesis.workers.backend import FakeLLMBackend


def test_revert_recommendation_reopens_and_returns_id(tmp_path: Path):
    g = FakeGraph()
    e = GraphEdge("e1", "old", ["EP-0"], class_="C3")
    e.invalid_at = e.expired_at = "2026-08-17T10:00:05+00:00"
    g.seed(e)
    b = FakeLLMBackend('{"recommendation": "REVERT", "independent_occurrences": 1, '
                       '"stated_update": false, "ask_window": false, "reasoning": "one"}')
    reverted = judge_invalidations(g, tmp_path, [e], "EP-NEW", b, ts="2026-08-17T10:00:06+00:00")
    assert reverted == ["e1"]
    assert g.get("e1").contested is True and g.get("e1").invalid_at is None


def test_earned_recommendation_leaves_closure(tmp_path: Path):
    g = FakeGraph()
    e = GraphEdge("e1", "old", ["EP-0"])
    e.expired_at = "2026-08-17T10:00:05+00:00"
    g.seed(e)
    b = FakeLLMBackend('{"recommendation": "EARNED", "independent_occurrences": 3, '
                       '"stated_update": true, "ask_window": false, "reasoning": "stated"}')
    reverted = judge_invalidations(g, tmp_path, [e], "EP-NEW", b, ts="2026-08-17T10:00:06+00:00")
    assert reverted == []
    assert g.get("e1").expired_at == "2026-08-17T10:00:05+00:00"  # closure stands
