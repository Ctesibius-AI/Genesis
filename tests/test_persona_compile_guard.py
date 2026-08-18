from __future__ import annotations

import pytest

from genesys.persona.compile_guard import assert_no_perceives, is_perceives
from genesys.persona.department import PerceptionDepartment
from genesys.persona.perceives import PerceivesEdge


def test_is_perceives():
    assert is_perceives(PerceivesEdge(to="Trait:rigor")) is True
    assert is_perceives("Values") is False


def test_assert_rejects_a_perceives_edge():
    with pytest.raises(TypeError):
        assert_no_perceives(PerceivesEdge(to="Trait:rigor"))


def test_assert_rejects_a_list_containing_perceives():
    with pytest.raises(TypeError):
        assert_no_perceives(["ok", PerceivesEdge(to="Trait:rigor")])


def test_assert_rejects_a_department():
    with pytest.raises(TypeError):
        assert_no_perceives(PerceptionDepartment())


def test_assert_allows_ordinary_anchors():
    assert_no_perceives(["Values", 1, {"anchor": "x"}])  # no raise
