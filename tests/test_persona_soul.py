from __future__ import annotations

import pytest

from genesys.persona.perceives import PerceivesEdge
from genesys.persona.soul import SoulSection, compile_soul


def test_compiles_about_her_sections_in_order():
    sections = [SoulSection("Success Metric", "did it help him"),
                SoulSection("Who I Am", "Daimon, his partner")]
    out = compile_soul(sections)
    assert [s.title for s in out] == ["Who I Am", "Success Metric"]  # canonical order


def test_unknown_section_raises():
    with pytest.raises(ValueError):
        compile_soul([SoulSection("His Values", "...")])  # about-him is not soul


def test_soul_is_blind_to_perceives():
    with pytest.raises(TypeError):
        compile_soul([PerceivesEdge(to="Trait:rigor")])  # perceives can never enter the soul
