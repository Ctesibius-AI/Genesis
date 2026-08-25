"""The SupersessionDecision carrier from the Supervisor path to apply_supersession (§8.2)."""
from __future__ import annotations

from genesis.linking.decision import SupersessionDecision


def test_defaults_are_empty_and_is_empty_true():
    d = SupersessionDecision()
    assert d.superseded_entry_ids == []
    assert d.superseded_edge_ids == []
    assert d.caused_by == []
    assert d.is_empty() is True


def test_any_populated_list_makes_it_non_empty():
    assert SupersessionDecision(superseded_entry_ids=["EP-1"]).is_empty() is False
    assert SupersessionDecision(superseded_edge_ids=["edge-1"]).is_empty() is False
    assert SupersessionDecision(caused_by=["EP-0"]).is_empty() is False


def test_lists_are_independent_per_instance():
    a = SupersessionDecision()
    a.superseded_entry_ids.append("EP-1")
    b = SupersessionDecision()
    assert b.superseded_entry_ids == []  # no shared mutable default
