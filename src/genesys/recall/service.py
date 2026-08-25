"""The recall service — allow-list-scoped, verdict-gated, ranked expand + three-channel search.

READ-ONLY (design §6/§7): expand/search only READ the engine (created_in_episode, get); no
mutator is ever called. Every read is scoped by the CLOSED allow-list (BT-3/D-GCW-7, the sole
leak-guard after the persona fence is removed — BT-4/CRIT-1 decouple), quarantine- and
invalidation-dropped (DR-33 / #3), and ranked by the injected RelatednessScorer. `search` is the
DR-33 three-channel honest-empty terminal; `expand` is the cheap 1-hop path (no honest-empty verdict).

BT-4 (AC-P2, red-line): this module carries NO `persona` import and NO `ReleaseContext` — recall is
decoupled from the persona layer; the allow-list, not the fence, is the guard.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from genesys.graph.engine import GraphEdge, GraphEngine
from genesys.linking.relatedness import RelatednessScorer
from genesys.recall.allowlist import filter_allowed
from genesys.recall.scorer import (
    Channel,
    ChannelResult,
    EmptyCause,
    RecallVerdict,
    score_channels,
)
from genesys.recall.search_backend import RecallSearch
from genesys.recall.tier import Tier, reads_graph
from genesys.recall.verdict import serving_label, servable_edges

_log = logging.getLogger("genesys.recall")


@dataclass
class RankedEdge:
    edge: GraphEdge
    score: float
    label: str


@dataclass
class RecallResult:
    edges: list[RankedEdge] = field(default_factory=list)
    verdict: RecallVerdict | None = None
    served_anchors: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.edges


class RecallService:
    def __init__(self, engine: GraphEngine, scorer: RelatednessScorer, *,
                 search: RecallSearch | None = None) -> None:
        self._engine = engine
        self._scorer = scorer
        self._search = search
        self._drop_count = 0  # AC-DROP1: cumulative non-allow-listed exclusions (observable)

    @property
    def drop_count(self) -> int:
        """AC-DROP1: how many edges recall has excluded as non-allow-listed (drop-visibility)."""
        return self._drop_count

    def _rank(self, anchor: str, edges: list[GraphEdge]) -> list[RankedEdge]:
        ranked = [RankedEdge(e, self._scorer.related(anchor, e.fact), serving_label(e))
                  for e in edges]
        ranked.sort(key=lambda re: re.score, reverse=True)
        return ranked

    def _gate(self, edges: list[GraphEdge]) -> list[GraphEdge]:
        """The recall read-guard (BT-4): quarantine-drop → invalidation-drop → CLOSED allow-list.

        No persona fence, no ReleaseContext (AC-P2). Quarantined (DR-33) and invalidated/expired
        (#3, not current) edges are dropped, then the fail-closed allow-list excludes any edge whose
        type is not one of the 8 named memory relations — counting the exclusions (AC-DROP1).
        """
        current = [e for e in servable_edges(edges)
                   if e.invalid_at is None and e.expired_at is None]
        allowed, dropped = filter_allowed(current)
        if dropped:
            self._drop_count += dropped
            _log.info("recall excluded %d non-allow-listed edge(s) (drop-visibility, AC-DROP1)", dropped)
        return allowed

    def expand(self, anchor_episode: str, tier: Tier) -> RecallResult:
        if not reads_graph(tier):
            return RecallResult()
        one_hop = self._engine.created_in_episode(anchor_episode)
        kept = self._gate(one_hop)
        return RecallResult(edges=self._rank(anchor_episode, kept), verdict=None)

    def _graph_channel_confirms(self, edge: GraphEdge) -> bool:
        try:
            g = self._engine.get(edge.edge_id)
        except KeyError:
            return False
        return g.invalid_at is None  # a real, current graph edge

    def search(self, query: str, tier: Tier, *,
               top_n: int = 5, cause: EmptyCause = EmptyCause.ABSENT) -> RecallResult:
        if self._search is None:
            raise RuntimeError("recall search needs a RecallSearch backend (offline: FakeRecallSearch)")
        sem = self._gate(self._search.semantic(query, top_n))
        kw = self._gate(self._search.keyword(query, top_n))
        union: dict[str, GraphEdge] = {e.edge_id: e for e in [*sem, *kw]}
        graph_hits = [e for e in union.values() if self._graph_channel_confirms(e)]
        results = [
            ChannelResult(Channel.SEMANTIC, hit=bool(sem), count=len(sem)),
            ChannelResult(Channel.KEYWORD, hit=bool(kw), count=len(kw)),
            ChannelResult(Channel.GRAPH, hit=bool(graph_hits), count=len(graph_hits)),
        ]
        verdict = score_channels(results, cause=cause)
        ranked = self._rank(query, list(union.values()))[:top_n]
        return RecallResult(edges=ranked, verdict=verdict)
