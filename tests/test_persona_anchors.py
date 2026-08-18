from __future__ import annotations

from genesys.persona.anchors import (
    Sample,
    TraitAnchor,
    ValueAnchor,
    has_stated_sample,
    independent_occurrence_count,
    stated_samples,
)


def test_trait_defaults_c3():
    t = TraitAnchor(name="rigor")
    assert t.class_ == "C3" and t.samples == [] and t.self_described is False


def test_value_defaults_c4_articulation_only():
    v = ValueAnchor(name="honesty")
    assert v.class_ == "C4" and v.articulations == []


def test_has_stated_sample_and_stated_only():
    t = TraitAnchor(name="rigor", samples=[
        Sample(provenance="EP-1", valid_at="t", author="stated"),
        Sample(provenance="EP-2", valid_at="t", author="inferred"),  # not a self-view sample
    ])
    assert has_stated_sample(t) is True
    assert [s.provenance for s in stated_samples(t)] == ["EP-1"]


def test_no_stated_sample_is_not_compile_eligible():
    t = TraitAnchor(name="rigor", samples=[Sample(provenance="EP-2", valid_at="t", author="inferred")])
    assert has_stated_sample(t) is False


def test_independent_occurrence_collapses_retellings():
    samples = [
        Sample(provenance="EP-1", valid_at="t1"),
        Sample(provenance="EP-1", valid_at="t2"),  # retelling of the same episode
        Sample(provenance="EP-3", valid_at="t3"),
    ]
    assert independent_occurrence_count(samples) == 2
