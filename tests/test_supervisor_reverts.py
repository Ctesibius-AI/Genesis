from __future__ import annotations

from pathlib import Path

from genesys.graph.engine import FakeGraph, GraphEdge
from genesys.journal.journal import read_journal
from genesys.supervisor.reverts import revert_invalidation, rightful_closure


def test_revert_reopens_marks_contested_and_journals_revert_plus_contest(tmp_path: Path):
    g = FakeGraph()
    e = GraphEdge("e1", "f", ["EP-0"])
    e.invalid_at = e.expired_at = "2026-08-17T10:00:05+00:00"
    g.seed(e)
    revert_invalidation(g, tmp_path, e, "EP-NEW", ts="2026-08-17T10:00:06+00:00", reason="sub-threshold")
    got = g.get("e1")
    assert got.invalid_at is None and got.contested is True
    assert got.expired_at is None
    assert got.evidence_against == ["EP-NEW"]
    journal = read_journal(tmp_path)
    actions = [j.action for j in journal]
    assert "revert" in actions and "contest" in actions
    revert_entry = next(j for j in journal if j.action == "revert")
    assert revert_entry.reason == "sub-threshold"


def test_rightful_closure_writes_superseded_by_and_journals(tmp_path: Path):
    g = FakeGraph()
    g.seed(GraphEdge("e1", "old", ["EP-0"]))
    rightful_closure(g, tmp_path, "e1", "e2", ts="2026-08-17T10:00:00+00:00", class_="C3", author="stated")
    assert g.get("e1").superseded_by == "e2"
    j = read_journal(tmp_path)
    assert j[0].action == "supersede" and j[0].after == "e2" and j[0].author == "stated"
    assert j[0].class_ == "C3"
