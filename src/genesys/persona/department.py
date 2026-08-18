"""Perception department — the perceived-view store (spec §9.4, R-N).

Holds ONLY perceives edges, tagged by (edge-type, subject, anchor); disjoint from the
calibration bank and ethos layer (no cross-reads — Fence 3 boundary). The Supervisor is the
sole writer; `add`/`add_observation` are the only write paths and enforce Fence 4.
"""

from __future__ import annotations

from genesys.persona.perceives import (
    PRINCIPAL,
    PerceivesEdge,
    PerceivesSample,
    assert_provisional,
)


class PerceptionDepartment:
    def __init__(self) -> None:
        self._edges: dict[tuple[str, str], PerceivesEdge] = {}  # (subject, anchor) -> edge

    def add(self, edge: PerceivesEdge) -> None:
        assert_provisional(edge)
        self._edges[(edge.subject, edge.to)] = edge

    def add_observation(self, *, anchor: str, episode: str, valid_at: str,
                        observation: str = "", subject: str = PRINCIPAL) -> PerceivesEdge:
        edge = self._edges.get((subject, anchor))
        if edge is None:
            edge = PerceivesEdge(to=anchor, subject=subject)
            self._edges[(subject, anchor)] = edge
        edge.samples.append(PerceivesSample(anchor=anchor, episode=episode,
                                            valid_at=valid_at, observation=observation))
        return edge

    def get(self, anchor: str, *, subject: str = PRINCIPAL) -> PerceivesEdge | None:
        return self._edges.get((subject, anchor))

    def edges_for_subject(self, subject: str = PRINCIPAL) -> list[PerceivesEdge]:
        return [e for (subj, _), e in sorted(self._edges.items()) if subj == subject]
