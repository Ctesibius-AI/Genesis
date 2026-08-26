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


def promote_created(engine: GraphEngine, data_root: Path, created: list[GraphEdge], *,
                    ts: str, reason: str) -> list[str]:
    """Promote to CONFIRMED every created edge the gate did NOT quarantine (D-FB-3 part B).

    The gate's judgment finally means something downstream: a genuine Screen PASS, or any
    non-quarantine Verifier resolution (incl. post-amend), promotes PROVISIONAL → CONFIRMED so recall
    stops labelling it "[unverified]". QUARANTINED edges are left held; already-CONFIRMED are skipped.
    Reads live verdict per edge (apply_remedy may have quarantined one already). Journaled per edge.
    """
    promoted: list[str] = []
    for edge in created:
        current = engine.get(edge.edge_id).verdict
        if current in (Verdict.QUARANTINED, Verdict.CONFIRMED):
            continue
        set_verdict(engine, data_root, edge, Verdict.CONFIRMED, ts=ts, reason=reason)
        promoted.append(edge.edge_id)
    return promoted


def quarantine_created(engine: GraphEngine, data_root: Path, created: list[GraphEdge], *,
                       ts: str, reason: str) -> list[str]:
    """QUARANTINE every not-yet-quarantined created edge (D-FB-3 part A: verifier-unavailable).

    Nothing enters memory on a shrug: when a SUSPICION path can't be adjudicated (the Verifier is
    unavailable/errors), the created edges are held (reviewable), never PASSed/CONFIRMED. Journaled.
    """
    held: list[str] = []
    for edge in created:
        if engine.get(edge.edge_id).verdict is Verdict.QUARANTINED:
            continue
        set_verdict(engine, data_root, edge, Verdict.QUARANTINED, ts=ts, reason=reason)
        held.append(edge.edge_id)
    return held
