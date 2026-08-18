"""Revert mechanics + rightful closure — D-SUP-3 (spec §8.2, DR-27 v3).

Sub-threshold invalidation → reopen the SAME edge (clear temporal), mark contested, add the
episode to evidence_against, and journal `revert` + `contest`. The new event edge stands.
Rightful closure (stated update) writes `superseded_by` and journals `supersede`. WHICH
invalidations are sub-threshold is the Invalidation Judge's call (LLM, P3.2) — not here.
"""

from __future__ import annotations

from pathlib import Path

from genesys.graph.engine import GraphEdge, GraphEngine
from genesys.journal.journal import JournalEntry, append_journal


def revert_invalidation(engine: GraphEngine, data_root: Path, edge: GraphEdge,
                        evidence_episode: str, *, ts: str, reason: str) -> None:
    engine.reopen(edge.edge_id, evidence_episode)
    append_journal(data_root, JournalEntry(
        ts=ts, action="revert", scope=evidence_episode, target=edge.edge_id,
        class_=edge.class_, reason=reason, author="supervisor",
    ))
    append_journal(data_root, JournalEntry(
        ts=ts, action="contest", scope=evidence_episode, target=edge.edge_id,
        class_=edge.class_, evidence=[evidence_episode], author="supervisor",
    ))


def rightful_closure(engine: GraphEngine, data_root: Path, edge_id: str, successor_id: str,
                     *, ts: str, reason: str | None = None, class_: str | None = None,
                     author: str = "stated") -> None:
    engine.write_superseded_by(edge_id, successor_id)
    append_journal(data_root, JournalEntry(
        ts=ts, action="supersede", scope=successor_id, target=edge_id,
        class_=class_, before=None, after=successor_id, reason=reason, author=author,
    ))
