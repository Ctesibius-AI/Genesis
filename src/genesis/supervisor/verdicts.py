"""Verdict state + journaling (spec §8, App A.3). Every fact is born `provisional`; the
Supervisor promotes to `confirmed` or demotes to `quarantined`, journaled grade-1. WHICH
transition to make is the judgment layer's call (P3.2); this is the mechanism + the ledger.
"""

from __future__ import annotations

from pathlib import Path

from genesis.graph.engine import GraphEdge, GraphEngine, Verdict
from genesis.journal.journal import JournalEntry, append_journal


def set_verdict(engine: GraphEngine, data_root: Path, edge: GraphEdge, verdict: Verdict,
                *, ts: str, reason: str | None = None) -> None:
    before = engine.get(edge.edge_id).verdict.value
    engine.set_verdict(edge.edge_id, verdict)
    append_journal(data_root, JournalEntry(
        ts=ts, action="verdict", scope=edge.episodes[-1] if edge.episodes else "",
        target=edge.edge_id, class_=edge.class_, before=before, after=verdict.value,
        reason=reason, author="supervisor",
    ))
