"""Evidence routing (D-SUP-12′) + the one-way street + non-lock fences (spec §9.3).

Statements/articulations route to the self-view; behavioural observations route to the
perceived-view. The write API enforces the one-way street structurally: a stated sample can
only reach his record; a behavioural observation can only reach hers. Fence 2 (never compiled)
is the self-view-only compile read; Fence 1's default read is fail-closed (P6.2 adds the
ReleaseContext-aware variant).
"""

from __future__ import annotations

from genesys.persona.anchors import Sample, ValueAnchor, has_stated_sample
from genesys.persona.department import PerceptionDepartment
from genesys.persona.perceives import PRINCIPAL, PerceivesEdge

_SELF_KINDS = {"statement", "articulation", "a4", "a4'"}
_PERCEIVED_KINDS = {"a1", "a2", "a1'", "a2'", "behaviour", "behavior"}


def route(kind: str, author: str) -> str:
    k = kind.lower()
    a = author.lower()
    if a == "stated" and k in _SELF_KINDS:
        return "self-view"
    if a == "inferred" and k in _PERCEIVED_KINDS:
        return "perceived-view"
    raise ValueError(f"one-way street: inconsistent evidence (kind={kind!r}, author={author!r})")


def record_self_view(anchor: object, sample: Sample) -> None:
    if sample.author != "stated":
        raise ValueError("his record moves only by his words: sample.author must be 'stated'")
    if isinstance(anchor, ValueAnchor):
        anchor.articulations.append(sample)
    else:
        anchor.samples.append(sample)


def record_perceived(dept: PerceptionDepartment, *, anchor: str, episode: str, valid_at: str,
                     observation: str = "") -> PerceivesEdge:
    return dept.add_observation(anchor=anchor, episode=episode, valid_at=valid_at,
                                observation=observation)


def compile_visible_anchors(anchors: list[object]) -> list[object]:
    return [a for a in anchors if has_stated_sample(a)]


def visible_perceived_default_locked(dept: PerceptionDepartment, *,
                                     subject: str = PRINCIPAL) -> list[PerceivesEdge]:
    from genesys.persona.lock import visible_perceived
    return visible_perceived(dept, None, subject=subject)  # canonical fail-closed filter
