from __future__ import annotations

import pytest

from genesys.persona.anchors import Sample, TraitAnchor, has_stated_sample
from genesys.persona.department import PerceptionDepartment
from genesys.persona.routing import (
    compile_visible_anchors,
    record_perceived,
    record_self_view,
    route,
    visible_perceived_default_locked,
)


def test_route_statements_to_self_view():
    assert route("articulation", "stated") == "self-view"
    assert route("statement", "stated") == "self-view"


def test_route_behaviour_to_perceived_view():
    assert route("A1", "inferred") == "perceived-view"
    assert route("behaviour", "inferred") == "perceived-view"


def test_route_rejects_inconsistent_pair():
    with pytest.raises(ValueError):
        route("behaviour", "stated")  # one-way street: a behaviour is never a stated sample


def test_record_self_view_refuses_inferred_sample():
    t = TraitAnchor(name="rigor")
    with pytest.raises(ValueError):
        record_self_view(t, Sample(provenance="EP-1", valid_at="t", author="inferred"))
    record_self_view(t, Sample(provenance="EP-2", valid_at="t", author="stated"))
    assert has_stated_sample(t) is True


def test_record_perceived_goes_to_department():
    d = PerceptionDepartment()
    e = record_perceived(d, anchor="Trait:rigor", episode="EP-1", valid_at="t")
    assert e.verdict == "provisional" and d.get("Trait:rigor") is e


def test_compile_visible_anchors_self_view_only():
    stated = TraitAnchor(name="a", samples=[Sample(provenance="EP-1", valid_at="t")])
    bare = TraitAnchor(name="b")
    assert [a.name for a in compile_visible_anchors([stated, bare])] == ["a"]


def test_default_read_is_fail_closed():
    d = PerceptionDepartment()
    record_perceived(d, anchor="Trait:rigor", episode="EP-1", valid_at="t")
    assert visible_perceived_default_locked(d) == []  # locked by default (Fence 1)


def test_route_normalizes_author_case():
    assert route("statement", "Stated") == "self-view"
    assert route("behaviour", "Inferred") == "perceived-view"
