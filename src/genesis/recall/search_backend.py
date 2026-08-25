"""The semantic + keyword graph-search channels (spec §4.7a DR-33; design §3, §7).

DR-33 forces three channels — semantic + keyword + graph. Two of them (semantic vector,
keyword BM25) are a HYBRID SEARCH over the graph's entity edges; the third (GRAPH) is
structural and is computed by the RecallService itself (`_graph_channel_confirms` via the
engine's `created_in_episode`/`get`), so it works offline today and is NOT in this seam.

This module holds the semantic+keyword seam:
- `RecallSearch` — the Protocol the service consumes (`semantic`/`keyword` → list[GraphEdge]).
- `FakeRecallSearch` — offline in-memory backend; script each channel per query string.
- `GraphSearchRecallSearch` — the REAL adapter's shaping/routing/merge logic, offline-testable
  by injecting a per-channel graph-search callable that returns canned `ClientEdge` hits. It
  maps graphiti's two edge-search methods onto DR-33's two retrieval channels and shapes the
  `ClientEdge`s into `GraphEdge`s (verdict preserved, so the service's quarantine filter fires
  downstream — verdict-aware serving, DR-33).
- `real_recall_search` — the LIVE binding. Lazy-imports graphiti/embedder INSIDE the function
  (same posture as linking.relatedness.real_scorer / graph.factory.real_client); the offline
  sandbox never reaches it and uses `FakeRecallSearch` instead. It reaches the live
  `GraphitiCoreClient.search_edges` (added lazily on the client) and wraps it in a
  `GraphSearchRecallSearch`.

Channel → graphiti-core API mapping (design §7; graphiti hybrid search over EntityEdges):
    semantic → EdgeSearchMethod.cosine_similarity  (bge-small vector search)
    keyword  → EdgeSearchMethod.bm25               (FalkorDB full-text BM25 over edge facts)
    graph    → NOT here (structural; RecallService computes it from created_in_episode/get)
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol

from genesis.graph.adapter import to_graph_edge
from genesis.graph.client import ClientEdge
from genesis.graph.engine import GraphEdge, GraphEngine


class RecallSearch(Protocol):
    def semantic(self, query: str, top_n: int) -> list[GraphEdge]: ...
    def keyword(self, query: str, top_n: int) -> list[GraphEdge]: ...


class GraphSearchChannel(str, Enum):
    """The two graph-search channels this seam serves (the third, GRAPH, is structural).

    Values are the graphiti-core EdgeSearchMethod names the live binding selects:
    `cosine_similarity` (semantic vector) and `bm25` (keyword full-text).
    """

    SEMANTIC = "cosine_similarity"
    KEYWORD = "bm25"


class FakeRecallSearch:
    """In-memory search backend for offline tests. Script each channel per query string."""

    def __init__(self) -> None:
        self._semantic: dict[str, list[GraphEdge]] = {}
        self._keyword: dict[str, list[GraphEdge]] = {}

    def set_semantic(self, query: str, edges: list[GraphEdge]) -> None:
        self._semantic[query] = list(edges)

    def set_keyword(self, query: str, edges: list[GraphEdge]) -> None:
        self._keyword[query] = list(edges)

    def semantic(self, query: str, top_n: int) -> list[GraphEdge]:
        return self._semantic.get(query, [])[:top_n]

    def keyword(self, query: str, top_n: int) -> list[GraphEdge]:
        return self._keyword.get(query, [])[:top_n]


class GraphSearchRecallSearch:
    """RecallSearch over a per-channel graph-search callable (spec §4.7a, DR-33; design §7).

    Decoupled from graphiti so it is offline-testable: inject any callable of the shape
    `(query: str, top_n: int, channel: GraphSearchChannel) -> list[ClientEdge]`. It routes the
    semantic and keyword channels to that callable, then shapes the returned `ClientEdge`s into
    `GraphEdge`s via `to_graph_edge` — carrying the verdict through so the RecallService's
    verdict-aware gate (quarantined never served, DR-33) fires on the results downstream.

    The live binding (`real_recall_search`) injects `GraphitiCoreClient.search_edges`, which runs
    graphiti hybrid search with a single EdgeSearchMethod per channel. Truncation to `top_n` is
    the callable's job (it passes num_results through); we defensively re-slice too.
    """

    def __init__(self, graph_search) -> None:  # noqa: ANN001 — a (query, top_n, channel) callable
        self._graph_search = graph_search

    def _run(self, query: str, top_n: int, channel: GraphSearchChannel) -> list[GraphEdge]:
        hits: list[ClientEdge] = self._graph_search(query, top_n, channel)
        return [to_graph_edge(ce) for ce in hits[:top_n]]

    def semantic(self, query: str, top_n: int) -> list[GraphEdge]:
        return self._run(query, top_n, GraphSearchChannel.SEMANTIC)

    def keyword(self, query: str, top_n: int) -> list[GraphEdge]:
        return self._run(query, top_n, GraphSearchChannel.KEYWORD)


def real_recall_search(engine: GraphEngine, *, model: str | None = None) -> RecallSearch:
    """Return a live Graphiti-hybrid-search RecallSearch (spec §4.7a, DR-33/34/35; design §7).

    Lazy binding, same posture as linking.relatedness.real_scorer / graph.factory.real_client:
    the graphiti/embedder imports live INSIDE this function so the offline suite (no graphiti-core)
    never reaches them and uses `FakeRecallSearch` instead. Raises RuntimeError when the extra is
    absent (offline).

    Wiring: reaches the live `GraphitiCoreClient` behind the `GraphitiEngine` (`engine._client`),
    binds its `search_edges(query, top_n, channel)` method (added lazily on the client — a single
    graphiti EdgeSearchMethod per DR-33 channel: SEMANTIC→cosine_similarity, KEYWORD→bm25), and
    wraps it in a `GraphSearchRecallSearch`. The GRAPH channel is not built here — the
    RecallService computes it structurally from the engine.
    """
    try:
        import graphiti_core  # noqa: F401, PLC0415 — lazy: absent offline
    except ImportError as exc:  # pragma: no cover - exercised only where the extra is absent
        raise RuntimeError(
            "the 'graph' extra is required for real recall search; offline uses "
            "FakeRecallSearch") from exc

    # pragma: no cover below — reached only with graphiti-core installed (live venv, not offline).
    client = getattr(engine, "_client", None)  # pragma: no cover
    if client is None or not hasattr(client, "search_edges"):  # pragma: no cover
        raise RuntimeError(
            "real recall search needs a GraphitiEngine over a GraphitiCoreClient "
            "(with search_edges); got an engine without a live graph client")

    def _graph_search(query: str, top_n: int,
                      channel: GraphSearchChannel) -> list[ClientEdge]:  # pragma: no cover
        return client.search_edges(query, top_n, channel.value)

    return GraphSearchRecallSearch(_graph_search)  # pragma: no cover
