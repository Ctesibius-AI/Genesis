from __future__ import annotations

import pytest

from genesys.persona.department import PerceptionDepartment
from genesys.persona.perceives import PerceivesEdge


def test_add_and_get():
    d = PerceptionDepartment()
    d.add(PerceivesEdge(to="Trait:rigor"))
    assert d.get("Trait:rigor").to == "Trait:rigor"
    assert d.get("Trait:absent") is None


def test_add_rejects_non_provisional():
    d = PerceptionDepartment()
    with pytest.raises(ValueError):
        d.add(PerceivesEdge(to="Trait:x", verdict="confirmed"))


def test_add_observation_accumulates_on_one_edge():
    d = PerceptionDepartment()
    d.add_observation(anchor="Trait:rigor", episode="EP-1", valid_at="t")
    e = d.add_observation(anchor="Trait:rigor", episode="EP-2", valid_at="t2")
    assert e.strength() == 2  # two distinct episodes on one anchor edge
    assert len(d.edges_for_subject()) == 1  # still one edge for the anchor


def test_edges_for_subject_is_scoped_and_ordered():
    d = PerceptionDepartment()
    d.add_observation(anchor="Trait:b", episode="EP-1", valid_at="t")
    d.add_observation(anchor="Trait:a", episode="EP-1", valid_at="t")
    d.add_observation(anchor="Trait:x", episode="EP-1", valid_at="t", subject="SomeoneElse")
    got = d.edges_for_subject()  # default PRINCIPAL only
    assert [e.to for e in got] == ["Trait:a", "Trait:b"]  # ordered, principal-scoped
