from __future__ import annotations

from pathlib import Path

from genesis.graph.engine import FakeGraph, GraphEdge, Verdict
from genesis.journal.journal import read_journal
from genesis.supervisor.verdicts import set_verdict


def test_set_verdict_writes_graph_and_journals(tmp_path: Path):
    g = FakeGraph()
    e = GraphEdge("e1", "f", ["EP-1"], class_="C3")
    g.seed(e)
    set_verdict(g, tmp_path, e, Verdict.QUARANTINED, ts="2026-08-17T10:00:00+00:00", reason="unfaithful")
    assert g.get("e1").verdict is Verdict.QUARANTINED
    j = read_journal(tmp_path)
    assert len(j) == 1
    assert j[0].action == "verdict"
    assert j[0].target == "e1"
    assert j[0].before == "provisional" and j[0].after == "quarantined"
    assert j[0].class_ == "C3" and j[0].author == "supervisor"
    assert j[0].reason == "unfaithful"
