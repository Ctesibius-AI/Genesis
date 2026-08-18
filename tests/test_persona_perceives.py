from __future__ import annotations

import pytest

from genesys.persona.perceives import (
    PRINCIPAL,
    DAIMON,
    PerceivesEdge,
    PerceivesSample,
    annotate_dispute,
    assert_provisional,
)


def test_edge_fixed_fields():
    e = PerceivesEdge(to="Trait:rigor")
    assert e.type == "perceives" and e.from_ == DAIMON and e.author == "inferred"
    assert e.perceiver == "Daimon" and e.verdict == "provisional" and e.lock == "default-locked"
    assert e.subject == PRINCIPAL
    assert e.dispute == {"status": "none", "reason_ref": None}


def test_verdict_is_permanently_provisional():
    # Fence 4: a non-provisional perceived verdict must be unrepresentable
    with pytest.raises(ValueError):
        assert_provisional(PerceivesEdge(to="Trait:x", verdict="confirmed"))  # type: ignore[call-arg]


def test_strength_counts_distinct_episodes():
    e = PerceivesEdge(to="Trait:rigor", samples=[
        PerceivesSample(anchor="Trait:rigor", episode="EP-1", valid_at="t"),
        PerceivesSample(anchor="Trait:rigor", episode="EP-1", valid_at="t2"),  # same occurrence
        PerceivesSample(anchor="Trait:rigor", episode="EP-5", valid_at="t3"),
    ])
    assert e.strength() == 2


def test_dispute_is_annotation_only_and_scrubbed():
    e = PerceivesEdge(to="Trait:rigor")
    annotate_dispute(e, reason="he pushed back, token sk-ABC123DEF456GHI789JKL0", reason_ref="DR-1")
    assert e.dispute["status"] == "disputed" and e.dispute["reason_ref"] == "DR-1"
    assert "sk-ABC123DEF456GHI789JKL0" not in e.dispute["reason"]  # scrubbed
    assert e.verdict == "provisional"  # unchanged


def test_construction_rejects_non_provisional():
    # Fence 4: construction enforces provisional verdict (via __post_init__)
    with pytest.raises(ValueError):
        PerceivesEdge(to="Trait:x", verdict="confirmed")  # type: ignore[call-arg]


def test_verdict_cannot_be_mutated_after_construction():
    # Fence 4: in-place mutation of verdict to non-provisional is blocked at runtime
    e = PerceivesEdge(to="Trait:rigor")
    with pytest.raises(ValueError):
        e.verdict = "confirmed"
    assert e.verdict == "provisional"
    # samples remain mutable for the sole writer
    e.band = "high"
    assert e.band == "high"
