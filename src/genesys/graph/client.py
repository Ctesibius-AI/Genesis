"""Graphiti client surface Genesys uses (spec §4.9a, F-GENESYS-11, DR-35).

`GraphitiClient` is the narrow Protocol the adapter needs from graphiti-core: create edges
from an episode (created-only results, F-11), query edges by episode and by `expired_at`
window, and mutate native temporal fields + custom Genesys attributes. `FakeGraphitiClient`
is the in-memory stand-in that lets the whole adapter be tested offline. `CommitMarker` issues
the Genesys-controlled window boundary (§8.1 QA #6) that binds attribution to this writer's
commit rather than wall-clock alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ClientEdge:
    uuid: str
    fact: str
    episodes: list[str]
    valid_at: str | None = None
    invalid_at: str | None = None
    expired_at: str | None = None
    attributes: dict[str, object] = field(default_factory=dict)


@dataclass
class AddEpisodeResults:
    """Created edges only — mirrors graphiti's AddEpisodeResults (no invalidated set, F-11)."""

    edges: list[ClientEdge] = field(default_factory=list)


class CommitMarker:
    """Genesys-issued monotonic commit boundary (§8.1 QA #6 hardening)."""

    def __init__(self, seq: int = 0) -> None:
        self.seq = seq

    def issue(self, ts: str) -> tuple[str, str]:
        token = f"cm-{self.seq}"
        self.seq += 1
        return token, ts


class GraphitiClient(Protocol):
    def add_episode(self, name: str, body: str, ref_ts: str) -> AddEpisodeResults: ...
    def edges_for_episode(self, episode_id: str) -> list[ClientEdge]: ...
    def edges_expired_in(self, start_ts: str, end_ts: str) -> list[ClientEdge]: ...
    def get_edge(self, uuid: str) -> ClientEdge: ...
    def set_edge_fields(self, uuid: str, **fields: object) -> None: ...
    def set_edge_attributes(self, uuid: str, **attrs: object) -> None: ...
    def add_typed_edge(self, src: str, dst: str, label: str) -> None: ...


class FakeGraphitiClient:
    """In-memory GraphitiClient. `script_episode` scripts what an add_episode does."""

    def __init__(self) -> None:
        self._edges: dict[str, ClientEdge] = {}
        self._script: dict[str, tuple[list[ClientEdge], list[str], str]] = {}
        self._typed: list[tuple[str, str, str]] = []

    # --- test helpers ---
    def seed(self, edge: ClientEdge) -> None:
        self._edges[edge.uuid] = edge

    def script_episode(self, episode_id: str, *, creates: list[ClientEdge] | None = None,
                       expires: list[str] | None = None, at: str = "") -> None:
        self._script[episode_id] = (list(creates or []), list(expires or []), at)

    # --- GraphitiClient ---
    def add_episode(self, name: str, body: str, ref_ts: str) -> AddEpisodeResults:
        creates, expires, at = self._script.get(name, ([], [], ""))
        for edge in creates:
            if name not in edge.episodes:
                edge.episodes.append(name)
            self._edges[edge.uuid] = edge
        for uuid in expires:  # invalidation applied internally, never on the result (F-11)
            self._edges[uuid].invalid_at = at
            self._edges[uuid].expired_at = at
        return AddEpisodeResults(edges=list(creates))

    def edges_for_episode(self, episode_id: str) -> list[ClientEdge]:
        return [e for e in self._edges.values() if episode_id in e.episodes]

    def edges_expired_in(self, start_ts: str, end_ts: str) -> list[ClientEdge]:
        return [e for e in self._edges.values()
                if e.expired_at is not None and start_ts <= e.expired_at <= end_ts]

    def get_edge(self, uuid: str) -> ClientEdge:
        return self._edges[uuid]

    def set_edge_fields(self, uuid: str, **fields: object) -> None:
        e = self._edges[uuid]
        for k, v in fields.items():
            setattr(e, k, v)

    def set_edge_attributes(self, uuid: str, **attrs: object) -> None:
        self._edges[uuid].attributes.update(attrs)

    def add_typed_edge(self, src: str, dst: str, label: str) -> None:
        """Record a typed directed edge between two episode IDs (spec §4.6, D-SPINE-4)."""
        self._typed.append((src, dst, label))
