"""The recall service — fenced, verdict-gated, ranked expand + three-channel search (§4.7b).

READ-ONLY (design §6/§7): expand/search only READ the engine (created_in_episode, get); no
mutator is ever called. Every read is persona-fenced (Task 4, a CALL into P6), quarantine-
dropped (Task 2, DR-33), and ranked by the injected RelatednessScorer (Fake offline, real_scorer
live). `search` is the DR-33 three-channel honest-empty terminal (Task 3); `expand` is the cheap
1-hop middle path and carries no honest-empty verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from genesys.graph.engine import GraphEdge, GraphEngine
from genesys.linking.relatedness import RelatednessScorer
from genesys.persona.department import PerceptionDepartment
from genesys.persona.release import ReleaseContext
from genesys.recall.fence import fence_edges
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
    def __init__(self, engine: GraphEngine, dept: PerceptionDepartment,
                 scorer: RelatednessScorer, *, search: RecallSearch | None = None) -> None:
        self._engine = engine
        self._dept = dept
        self._scorer = scorer
        self._search = search

    def _rank(self, anchor: str, edges: list[GraphEdge]) -> list[RankedEdge]:
        ranked = [RankedEdge(e, self._scorer.related(anchor, e.fact), serving_label(e))
                  for e in edges]
        ranked.sort(key=lambda re: re.score, reverse=True)
        return ranked

    def _fence_and_gate(self, edges: list[GraphEdge], ctx: ReleaseContext | None
                        ) -> tuple[list[GraphEdge], list[str]]:
        kept, served = fence_edges(servable_edges(edges), ctx)  # drop quarantined, then fence
        return kept, served

    def expand(self, anchor_episode: str, tier: Tier, *,
               ctx: ReleaseContext | None = None) -> RecallResult:
        if not reads_graph(tier):
            return RecallResult()
        one_hop = self._engine.created_in_episode(anchor_episode)
        kept, served = self._fence_and_gate(one_hop, ctx)
        return RecallResult(edges=self._rank(anchor_episode, kept), verdict=None,
                            served_anchors=served)

    def _graph_channel_confirms(self, edge: GraphEdge) -> bool:
        try:
            g = self._engine.get(edge.edge_id)
        except KeyError:
            return False
        return g.invalid_at is None  # a real, current graph edge

    def search(self, query: str, tier: Tier, *, ctx: ReleaseContext | None = None,
               top_n: int = 5, cause: EmptyCause = EmptyCause.ABSENT) -> RecallResult:
        if self._search is None:
            raise RuntimeError("recall search needs a RecallSearch backend (offline: FakeRecallSearch)")
        sem_raw = self._search.semantic(query, top_n)
        kw_raw = self._search.keyword(query, top_n)
        sem, sem_anchors = self._fence_and_gate(sem_raw, ctx)
        kw, kw_anchors = self._fence_and_gate(kw_raw, ctx)
        union: dict[str, GraphEdge] = {e.edge_id: e for e in [*sem, *kw]}
        graph_hits = [e for e in union.values() if self._graph_channel_confirms(e)]
        results = [
            ChannelResult(Channel.SEMANTIC, hit=bool(sem), count=len(sem)),
            ChannelResult(Channel.KEYWORD, hit=bool(kw), count=len(kw)),
            ChannelResult(Channel.GRAPH, hit=bool(graph_hits), count=len(graph_hits)),
        ]
        verdict = score_channels(results, cause=cause)
        ranked = self._rank(query, list(union.values()))[:top_n]
        return RecallResult(edges=ranked, verdict=verdict,
                            served_anchors=[*sem_anchors, *kw_anchors])
