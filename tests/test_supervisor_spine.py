from __future__ import annotations

from pathlib import Path

from genesys.graph.engine import FakeGraph, GraphEdge, Verdict
from genesys.journal.journal import read_journal
from genesys.supervisor.spine import inspect_commit


def test_inspect_sets_provisional_on_created_and_returns_detection(tmp_path: Path):
    g = FakeGraph()
    g.seed(GraphEdge("old", "old", ["EP-0"]))
    g.script_episode("EP-1", creates=[GraphEdge("new", "new", ["EP-1"])],
                     expires=["old"], at="2026-08-17T10:00:03+00:00")
    g.add_episode("EP-1", "c")
    d = inspect_commit(g, tmp_path, "EP-1",
                       commit_start="2026-08-17T10:00:00+00:00",
                       commit_end="2026-08-17T10:00:10+00:00",
                       ts="2026-08-17T10:00:11+00:00")
    assert [e.edge_id for e in d.created] == ["new"]
    assert [e.edge_id for e in d.invalidated] == ["old"]
    assert g.get("new").verdict is Verdict.PROVISIONAL
    # exactly one verdict journal line for the created edge
    assert [j.action for j in read_journal(tmp_path)] == ["verdict"]


def test_inspect_is_idempotent_on_verdict(tmp_path: Path):
    g = FakeGraph()
    g.script_episode("EP-1", creates=[GraphEdge("new", "new", ["EP-1"])], at="")
    g.add_episode("EP-1", "c")
    kw = dict(commit_start="2026-08-17T10:00:00+00:00", commit_end="2026-08-17T10:00:10+00:00",
              ts="2026-08-17T10:00:11+00:00")
    inspect_commit(g, tmp_path, "EP-1", **kw)
    inspect_commit(g, tmp_path, "EP-1", **kw)  # again
    assert len([j for j in read_journal(tmp_path) if j.action == "verdict"]) == 1  # not doubled
