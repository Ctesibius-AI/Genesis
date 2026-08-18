from __future__ import annotations

import pytest

from genesys.persona.anchors import Sample, TraitAnchor, ValueAnchor
from genesys.persona.constitution import (
    CategorizedAnchor,
    ConstitutionLine,
    compile_constitution,
    format_line,
)


def _valued(name, quote):
    return ValueAnchor(name=name, articulations=[Sample(provenance="EP-1", valid_at="t",
                                                        quote=quote, author="stated")])


def test_format_line_is_aaak():
    line = ConstitutionLine(category="Values", directive="prize honest evaluation",
                            quote="tell me what's actually true", gr_ref="Value:honesty")
    assert format_line(line) == 'Values|prize honest evaluation|"tell me what\'s actually true"|gr:Value:honesty|★★★'


def test_compiles_only_anchors_with_stated_sample():
    stated = CategorizedAnchor(_valued("Value:honesty", "tell me what's true"), "Values",
                               "prize honest evaluation")
    bare = CategorizedAnchor(TraitAnchor(name="Trait:rigor"), "Reasoning", "be rigorous")
    lines = compile_constitution([stated, bare])
    assert [l.gr_ref for l in lines] == ["Value:honesty"]  # bare (no stated sample) excluded
    assert lines[0].quote == "tell me what's true"


def test_caps_three_per_category():
    items = [CategorizedAnchor(_valued(f"Value:v{i}", f"q{i}"), "Values", f"d{i}") for i in range(5)]
    lines = compile_constitution(items)
    assert len([l for l in lines if l.category == "Values"]) == 3  # 5 → capped at 3


def test_unknown_category_raises():
    with pytest.raises(ValueError):
        compile_constitution([CategorizedAnchor(_valued("Value:x", "q"), "Nonsense", "d")])


def test_perceives_wrapped_as_anchor_is_rejected():
    from genesys.persona.perceives import PerceivesEdge
    with pytest.raises(TypeError):
        compile_constitution([CategorizedAnchor(PerceivesEdge(to="Trait:rigor"), "Values", "d")])
