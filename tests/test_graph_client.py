from __future__ import annotations

from genesys.graph.client import (
    AddEpisodeResults,
    ClientEdge,
    CommitMarker,
    FakeGraphitiClient,
)


def test_commit_marker_issues_monotonic_tokens():
    cm = CommitMarker()
    a = cm.issue("2026-08-17T10:00:00Z")
    b = cm.issue("2026-08-17T10:00:01Z")
    assert a == ("cm-0", "2026-08-17T10:00:00Z")
    assert b == ("cm-1", "2026-08-17T10:00:01Z")


def test_add_episode_returns_created_only_expired_applied_internally():
    c = FakeGraphitiClient()
    old = ClientEdge(uuid="e-old", fact="uses X", episodes=["ep-0"])
    c.seed(old)
    new = ClientEdge(uuid="e-new", fact="uses Y", episodes=["ep-1"])
    c.script_episode("ep-1", creates=[new], expires=["e-old"], at="2026-08-17T10:00:00Z")

    res = c.add_episode("ep-1", "he now uses Y", "2026-08-17T10:00:00Z")

    assert isinstance(res, AddEpisodeResults)
    # F-11: only the created edge is returned; the expired one is applied internally
    assert [e.uuid for e in res.edges] == ["e-new"]
    assert c.get_edge("e-old").expired_at == "2026-08-17T10:00:00Z"
    assert c.get_edge("e-old").invalid_at == "2026-08-17T10:00:00Z"


def test_edges_expired_in_window_and_for_episode():
    c = FakeGraphitiClient()
    c.seed(ClientEdge(uuid="e-old", fact="uses X", episodes=["ep-0"]))
    new = ClientEdge(uuid="e-new", fact="uses Y", episodes=["ep-1"])
    c.script_episode("ep-1", creates=[new], expires=["e-old"], at="2026-08-17T10:00:00Z")
    c.add_episode("ep-1", "body", "2026-08-17T10:00:00Z")

    assert [e.uuid for e in c.edges_for_episode("ep-1")] == ["e-new"]
    win = c.edges_expired_in("2026-08-17T09:59:00Z", "2026-08-17T10:01:00Z")
    assert [e.uuid for e in win] == ["e-old"]
    assert c.edges_expired_in("2026-08-17T11:00:00Z", "2026-08-17T12:00:00Z") == []


def test_set_edge_fields_and_attributes():
    c = FakeGraphitiClient()
    c.seed(ClientEdge(uuid="e1", fact="f", episodes=["ep-0"]))
    c.set_edge_fields("e1", expired_at=None, invalid_at=None)
    c.set_edge_attributes("e1", verdict="confirmed", contested=True)
    e = c.get_edge("e1")
    assert e.expired_at is None and e.invalid_at is None
    assert e.attributes["verdict"] == "confirmed"
    assert e.attributes["contested"] is True
