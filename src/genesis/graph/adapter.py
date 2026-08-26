"""Real GraphEngine over a GraphitiClient (spec §4.9a, §8.1, F-GENESIS-11, DR-35/36).

`GraphitiEngine` satisfies the same `GraphEngine` Protocol as `FakeGraph`, translating between
graphiti's native edge shape (+ Genesis custom attributes) and `GraphEdge`. It stamps a
Genesis-controlled commit window (§8.1 QA #6) per episode so the Supervisor's `expired_at`
window binds to this writer's commit, not wall-clock alone. `add_episode` returns created edges
only (F-11); invalidations are read post-commit via `invalidated_in_window`.
"""

from __future__ import annotations

import logging
from typing import Callable

from genesis.graph.client import ClientEdge, CommitMarker, GraphitiClient
from genesis.graph.engine import AddResult, GraphEdge, Verdict

_log = logging.getLogger("genesis.graph")


def to_graph_edge(ce: ClientEdge) -> GraphEdge:
    a = ce.attributes
    verdict = a.get("verdict", Verdict.PROVISIONAL)
    return GraphEdge(
        edge_id=ce.uuid,
        fact=ce.fact,
        episodes=list(ce.episodes),
        author=str(a.get("author", "inferred")),
        valid_at=ce.valid_at,
        invalid_at=ce.invalid_at,
        expired_at=ce.expired_at,
        verdict=verdict if isinstance(verdict, Verdict) else Verdict(verdict),
        contested=bool(a.get("contested", False)),
        evidence_against=list(a.get("evidence_against", [])),
        superseded_by=a.get("superseded_by"),
        class_=a.get("class"),
        type=ce.type,  # BT-6: carry the graphiti relation type through for the allow-list
    )


def _no_clock() -> str:
    raise RuntimeError("GraphitiEngine needs an injected clock to stamp the commit window")


class GraphitiEngine:
    def __init__(self, client: GraphitiClient, *, marker: CommitMarker | None = None,
                 clock: Callable[[], str] | None = None) -> None:
        self._client = client
        self._marker = marker if marker is not None else CommitMarker()
        self._clock = clock if clock is not None else _no_clock
        self._windows: dict[str, tuple[str, str]] = {}

    def close(self) -> None:
        """Flush + shut the underlying store down cleanly (graph-harness T2).

        Delegates to the client's ``close()`` when it has one (the real GraphitiCoreClient SAVEs the
        embedded redislite RDB and stops its driver/loop). Best-effort and idempotent-safe: a client
        without ``close`` (e.g. a test fake) or a shutdown hiccup is logged, never raised — closing
        must not mask the caller's result. The WRITER must call this so a pass's writes reach disk.
        """
        closer = getattr(self._client, "close", None)
        if closer is None:
            return
        try:
            closer()
        except Exception:  # noqa: BLE001 — shutdown is best-effort; surface it in logs, never crash
            _log.warning("GraphitiEngine.close: client shutdown failed", exc_info=True)

    def add_episode(self, episode_id: str, content: str) -> AddResult:
        start_token, start_ts = self._marker.issue(self._clock())
        results = self._client.add_episode(episode_id, content, ref_ts=start_ts)
        _end_token, end_ts = self._marker.issue(self._clock())
        self._windows[episode_id] = (start_ts, end_ts)
        return AddResult(created=[to_graph_edge(e) for e in results.edges])

    def created_in_episode(self, episode_id: str) -> list[GraphEdge]:
        return [to_graph_edge(e) for e in self._client.edges_for_episode(episode_id)]

    def window_for(self, episode_id: str) -> tuple[str, str]:
        return self._windows[episode_id]

    def invalidated_in_window(self, start_ts: str, end_ts: str) -> list[GraphEdge]:
        return [to_graph_edge(e) for e in self._client.edges_expired_in(start_ts, end_ts)]

    def get(self, edge_id: str) -> GraphEdge:
        return to_graph_edge(self._client.get_edge(edge_id))

    def reopen(self, edge_id: str, evidence_episode: str) -> None:
        self._client.set_edge_fields(edge_id, invalid_at=None, expired_at=None)
        current = self._client.get_edge(edge_id)
        against = list(current.attributes.get("evidence_against", []))
        if evidence_episode not in against:
            against.append(evidence_episode)
        self._client.set_edge_attributes(edge_id, contested=True, evidence_against=against)

    def set_verdict(self, edge_id: str, verdict: Verdict) -> None:
        self._client.set_edge_attributes(edge_id, verdict=verdict.value)

    def write_superseded_by(self, edge_id: str, successor_id: str) -> None:
        self._client.set_edge_attributes(edge_id, superseded_by=successor_id)

    def write_fact(self, edge_id: str, content: str) -> None:
        self._client.set_edge_fields(edge_id, fact=content)

    def link_episode(self, src_episode: str, dst_episode: str, label: str) -> None:
        """Project a Genesis-side typed edge onto the graph client (spec §4.6, D-SPINE-4)."""
        self._client.add_typed_edge(src_episode, dst_episode, label)
