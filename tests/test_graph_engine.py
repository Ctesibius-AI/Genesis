from __future__ import annotations

from genesis.graph.engine import AddResult, FakeGraph, GraphEdge, Verdict


def _edge(eid, fact="f", episodes=("EP-1",)) -> GraphEdge:
    return GraphEdge(edge_id=eid, fact=fact, episodes=list(episodes))


def test_new_edge_is_provisional_and_uncontested():
    e = _edge("e1")
    assert e.verdict is Verdict.PROVISIONAL
    assert e.contested is False and e.evidence_against == []


def test_created_in_episode_matches_by_membership():
    g = FakeGraph()
    g.seed(_edge("e1", episodes=("EP-A",)))
    g.seed(_edge("e2", episodes=("EP-B",)))
    assert [e.edge_id for e in g.created_in_episode("EP-A")] == ["e1"]


def test_invalidated_in_window_selects_by_expired_at():
    g = FakeGraph()
    old = _edge("e1")
    old.expired_at = "2026-08-17T10:00:05+00:00"
    g.seed(old)
    g.seed(_edge("e2"))  # not expired
    got = [e.edge_id for e in g.invalidated_in_window("2026-08-17T10:00:00+00:00", "2026-08-17T10:00:10+00:00")]
    assert got == ["e1"]


def test_reopen_clears_temporal_and_marks_contested():
    g = FakeGraph()
    old = _edge("e1")
    old.invalid_at = "2026-08-17T10:00:05+00:00"
    old.expired_at = "2026-08-17T10:00:05+00:00"
    g.seed(old)
    g.reopen("e1", "EP-NEW")
    e = g.get("e1")
    assert e.invalid_at is None and e.expired_at is None
    assert e.contested is True and e.evidence_against == ["EP-NEW"]


def test_reopen_evidence_is_set_add():
    g = FakeGraph()
    g.seed(_edge("e1"))
    g.reopen("e1", "EP-X")
    g.reopen("e1", "EP-X")  # same episode again
    assert g.get("e1").evidence_against == ["EP-X"]


def test_set_verdict_and_superseded_by():
    g = FakeGraph()
    g.seed(_edge("e1"))
    g.set_verdict("e1", Verdict.CONFIRMED)
    g.write_superseded_by("e1", "e2")
    assert g.get("e1").verdict is Verdict.CONFIRMED
    assert g.get("e1").superseded_by == "e2"


def test_scripted_add_episode_creates_and_expires():
    g = FakeGraph()
    g.seed(GraphEdge("old", "old fact", ["EP-0"]))
    g.script_episode("EP-1", creates=[GraphEdge("new", "new fact", ["EP-1"])],
                     expires=["old"], at="2026-08-17T10:00:03+00:00")
    res = g.add_episode("EP-1", "content")
    assert isinstance(res, AddResult)
    assert [e.edge_id for e in res.created] == ["new"]      # created returned
    assert g.get("old").expired_at == "2026-08-17T10:00:03+00:00"  # invalidation applied internally


def test_window_for_returns_scripted_at_as_both_bounds():
    g = FakeGraph()
    g.script_episode("EP-1", creates=[GraphEdge("e1", "f", ["EP-1"])],
                     at="2026-08-17T10:00:03+00:00")
    g.add_episode("EP-1", "content")
    assert g.window_for("EP-1") == ("2026-08-17T10:00:03+00:00", "2026-08-17T10:00:03+00:00")


def test_window_for_unscripted_episode_returns_empty_string_bounds():
    g = FakeGraph()
    g.add_episode("EP-BLANK", "content")
    assert g.window_for("EP-BLANK") == ("", "")


def test_window_for_unknown_episode_raises_key_error():
    g = FakeGraph()
    import pytest
    with pytest.raises(KeyError):
        g.window_for("EP-NEVER-ADDED")
