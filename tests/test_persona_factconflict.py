from __future__ import annotations

import pytest

from genesys.graph.engine import FakeGraph, GraphEdge
from genesys.journal.journal import read_journal
from genesys.persona.factconflict import resolve_fact_conflict


def _eng():
    g = FakeGraph()
    g.seed(GraphEdge(edge_id="E-old", fact="uses X", episodes=["EP-1"]))
    g.seed(GraphEdge(edge_id="E-new", fact="uses Y", episodes=["EP-2"]))
    return g


def test_new_holds_supersedes_earlier(tmp_path):
    g = _eng()
    resolve_fact_conflict(tmp_path, g, ts="t", earlier_edge="E-old", new_edge="E-new",
                          selection="new")
    assert g.get("E-old").superseded_by == "E-new"
    assert [e.action for e in read_journal(tmp_path)] == ["supersede"]


def test_earlier_holds_supersedes_new(tmp_path):
    g = _eng()
    resolve_fact_conflict(tmp_path, g, ts="t", earlier_edge="E-old", new_edge="E-new",
                          selection="earlier")
    assert g.get("E-new").superseded_by == "E-old"


def test_neither_or_both_is_contested(tmp_path):
    g = _eng()
    resolve_fact_conflict(tmp_path, g, ts="t", earlier_edge="E-old", new_edge="E-new",
                          selection="neither-or-both", reason="both true in context")
    assert g.get("E-old").contested is True
    assert [e.action for e in read_journal(tmp_path)] == ["contest"]


def test_reason_is_scrubbed(tmp_path):
    g = _eng()
    resolve_fact_conflict(tmp_path, g, ts="t", earlier_edge="E-old", new_edge="E-new",
                          selection="new", reason="because token sk-ABC123DEF456GHI789JKL0 says")
    entry = read_journal(tmp_path)[0]
    assert "sk-ABC123DEF456GHI789JKL0" not in (entry.reason or "")


def test_unknown_selection_raises(tmp_path):
    with pytest.raises(ValueError):
        resolve_fact_conflict(tmp_path, _eng(), ts="t", earlier_edge="E-old", new_edge="E-new",
                              selection="whatever")
