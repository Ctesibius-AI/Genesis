"""Invalidation judgment wiring (spec §8.2/§8.4, DR-27 v3).

For each detected invalidation, the Invalidation Judge (LLM) decides EARNED vs REVERT
(sub-threshold); on REVERT the deterministic revert (P3.1) reopens the edge. The Judge
recommends; the Supervisor writes.
"""

from __future__ import annotations

from pathlib import Path

from genesis.graph.engine import GraphEdge, GraphEngine
from genesis.supervisor.reverts import revert_invalidation
from genesis.workers.backend import LLMBackend
from genesis.workers.judge import invalidation_judge


def judge_invalidations(engine: GraphEngine, data_root: Path, invalidated: list[GraphEdge],
                        evidence_episode: str, backend: LLMBackend, *, ts: str) -> list[str]:
    reverted: list[str] = []
    for edge in invalidated:
        verdict = invalidation_judge(
            backend, closed_fact=edge.fact, new_evidence=evidence_episode,
            fact_class=edge.class_ or "C1",
            prior_contest=", ".join(edge.evidence_against),
        )
        if verdict.recommendation == "REVERT":
            revert_invalidation(engine, data_root, edge, evidence_episode, ts=ts, reason="sub-threshold")
            reverted.append(edge.edge_id)
    return reverted
