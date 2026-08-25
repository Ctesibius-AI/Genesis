"""Graph engine abstraction (spec §4.9, §8; Graphiti-faithful, F-GENESIS-11).

`GraphEngine` mirrors the real contract: `add_episode` returns only CREATED edges; because
`AddEpisodeResults` has no invalidated set, invalidations are read POST-COMMIT via
`invalidated_in_window` (expired_at within the commit window — attribution-by-exclusivity on
the serial lane). FakeGraph is the in-memory implementation for tests; the real Graphiti/
FalkorDB adapter (a later sub-phase) implements the same Protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class Verdict(str, Enum):
    PROVISIONAL = "provisional"
    CONFIRMED = "confirmed"
    QUARANTINED = "quarantined"


@dataclass
class GraphEdge:
    edge_id: str
    fact: str
    episodes: list[str]
    author: str = "inferred"
    valid_at: str | None = None
    invalid_at: str | None = None
    expired_at: str | None = None
    verdict: Verdict = Verdict.PROVISIONAL
    contested: bool = False
    evidence_against: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    class_: str | None = None
    # BT-6 / D-GCW-14: the graphiti relation type (edge name, e.g. "WORKS_ON"). None = untyped /
    # unclassifiable — excluded by the fail-closed recall allow-list (D-GCW-7). Filled from
    # graphiti's EntityEdge.name via the typed add_episode feed on the live path.
    type: str | None = None


@dataclass
class AddResult:
    created: list[GraphEdge] = field(default_factory=list)


class GraphEngine(Protocol):
    def add_episode(self, episode_id: str, content: str) -> AddResult: ...
    def window_for(self, episode_id: str) -> tuple[str, str]: ...
    def created_in_episode(self, episode_id: str) -> list[GraphEdge]: ...
    def invalidated_in_window(self, start_ts: str, end_ts: str) -> list[GraphEdge]: ...
    def reopen(self, edge_id: str, evidence_episode: str) -> None: ...
    def set_verdict(self, edge_id: str, verdict: Verdict) -> None: ...
    def write_superseded_by(self, edge_id: str, successor_id: str) -> None: ...
    def get(self, edge_id: str) -> GraphEdge: ...
    def write_fact(self, edge_id: str, content: str) -> None: ...
    def link_episode(self, src_episode: str, dst_episode: str, label: str) -> None: ...


class FakeGraph:
    """In-memory GraphEngine for tests. `script_episode` scripts what an add_episode does."""

    def __init__(self) -> None:
        self._edges: dict[str, GraphEdge] = {}
        self._script: dict[str, tuple[list[GraphEdge], list[str], str]] = {}
        self._windows: dict[str, tuple[str, str]] = {}
        self._links: list[tuple[str, str, str]] = []

    # --- test helpers ---
    def seed(self, edge: GraphEdge) -> None:
        self._edges[edge.edge_id] = edge

    def script_episode(self, episode_id: str, *, creates: list[GraphEdge] | None = None,
                       expires: list[str] | None = None, at: str = "") -> None:
        self._script[episode_id] = (list(creates or []), list(expires or []), at)

    # --- GraphEngine ---
    def add_episode(self, episode_id: str, content: str) -> AddResult:
        creates, expires, at = self._script.get(episode_id, ([], [], ""))
        for edge in creates:
            self._edges[edge.edge_id] = edge
        for eid in expires:  # invalidation applied internally (not on the result, F-11)
            self._edges[eid].invalid_at = at
            self._edges[eid].expired_at = at
        self._windows[episode_id] = (at, at)
        return AddResult(created=list(creates))

    def window_for(self, episode_id: str) -> tuple[str, str]:
        return self._windows[episode_id]

    def created_in_episode(self, episode_id: str) -> list[GraphEdge]:
        return [e for e in self._edges.values() if episode_id in e.episodes]

    def invalidated_in_window(self, start_ts: str, end_ts: str) -> list[GraphEdge]:
        return [e for e in self._edges.values()
                if e.expired_at is not None and start_ts <= e.expired_at <= end_ts]

    def reopen(self, edge_id: str, evidence_episode: str) -> None:
        e = self._edges[edge_id]
        e.invalid_at = None
        e.expired_at = None
        e.contested = True
        if evidence_episode not in e.evidence_against:
            e.evidence_against.append(evidence_episode)

    def set_verdict(self, edge_id: str, verdict: Verdict) -> None:
        self._edges[edge_id].verdict = verdict

    def write_superseded_by(self, edge_id: str, successor_id: str) -> None:
        self._edges[edge_id].superseded_by = successor_id

    def get(self, edge_id: str) -> GraphEdge:
        return self._edges[edge_id]

    def write_fact(self, edge_id: str, content: str) -> None:
        self._edges[edge_id].fact = content

    def link_episode(self, src_episode: str, dst_episode: str, label: str) -> None:
        """Record a typed directed edge between two episodes (spec §4.6, D-SPINE-4)."""
        self._links.append((src_episode, dst_episode, label))

    def links_for(self, src_episode: str) -> list[tuple[str, str, str]]:
        """Test helper: return all typed edges originating from src_episode."""
        return [t for t in self._links if t[0] == src_episode]
