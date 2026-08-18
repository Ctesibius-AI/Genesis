from __future__ import annotations

import pytest

from genesys.graph.engine import FakeGraph, GraphEdge, Verdict


def _build_fake():
    eng = FakeGraph()

    def seed_old():
        eng.seed(GraphEdge(edge_id="e-old", fact="uses X", episodes=["ep-0"]))

    def script_replace():
        eng.script_episode("ep-1",
                            creates=[GraphEdge(edge_id="e-new", fact="uses Y", episodes=["ep-1"])],
                            expires=["e-old"], at="2026-08-17T10:00:00Z")

    def window():
        return ("2026-08-17T09:59:00Z", "2026-08-17T10:01:00Z")

    return eng, seed_old, script_replace, window


def _build_adapter():
    from genesys.graph.adapter import GraphitiEngine
    from genesys.graph.client import ClientEdge, CommitMarker, FakeGraphitiClient

    c = FakeGraphitiClient()
    clock = iter(["2026-08-17T09:59:00Z", "2026-08-17T10:01:00Z"])
    eng = GraphitiEngine(c, marker=CommitMarker(), clock=lambda: next(clock))

    def seed_old():
        c.seed(ClientEdge(uuid="e-old", fact="uses X", episodes=["ep-0"]))

    def script_replace():
        c.script_episode("ep-1", creates=[ClientEdge(uuid="e-new", fact="uses Y", episodes=[])],
                         expires=["e-old"], at="2026-08-17T10:00:00Z")

    def window():
        return eng.window_for("ep-1")

    return eng, seed_old, script_replace, window


@pytest.mark.parametrize("build", [_build_fake, _build_adapter], ids=["fake", "adapter"])
def test_engine_contract_created_only_and_postcommit_invalidation(build):
    eng, seed_old, script_replace, window = build()
    seed_old()
    script_replace()

    result = eng.add_episode("ep-1", "he now uses Y")
    # F-11: add_episode returns created edges only
    assert [e.edge_id for e in result.created] == ["e-new"]

    # invalidation is visible only post-commit, via the window
    start, end = window()
    inv = eng.invalidated_in_window(start, end)
    assert [e.edge_id for e in inv] == ["e-old"]

    # writes flip attributes and round-trip through get()
    eng.set_verdict("e-new", Verdict.CONFIRMED)
    assert eng.get("e-new").verdict == Verdict.CONFIRMED
    eng.reopen("e-old", "ep-1")
    reopened = eng.get("e-old")
    assert reopened.expired_at is None and reopened.contested is True
    assert "ep-1" in reopened.evidence_against
