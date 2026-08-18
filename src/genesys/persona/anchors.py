"""Persona anchor nodes — the self-view (spec §9.1, §9.2, App A.2).

A `Trait`/`Value` anchor is a shared concept node (label, no authority). The self-view is the
set of STATED samples on the node; compile/speak reads require >=1 stated sample and read
stated samples only. Strength = independent-occurrence count (retellings collapse; §8.3),
never a High/Med/Low grade.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Sample:
    provenance: str
    valid_at: str
    quote: str = ""
    author: str = "stated"


@dataclass
class TraitAnchor:
    name: str
    disposition: str = ""
    samples: list[Sample] = field(default_factory=list)
    self_described: bool = False
    class_: str = "C3"
    framing: str = ""


@dataclass
class ValueAnchor:
    name: str
    commitment: str = ""
    articulations: list[Sample] = field(default_factory=list)
    framing: str = ""
    articulation_quote: str = ""
    class_: str = "C4"


def _self_view_samples(anchor: object) -> list[Sample]:
    if isinstance(anchor, ValueAnchor):
        return anchor.articulations
    return anchor.samples  # TraitAnchor


def stated_samples(anchor: object) -> list[Sample]:
    return [s for s in _self_view_samples(anchor) if s.author == "stated"]


def has_stated_sample(anchor: object) -> bool:
    return len(stated_samples(anchor)) >= 1


def independent_occurrence_count(samples: list[Sample]) -> int:
    return len({s.provenance for s in samples})
