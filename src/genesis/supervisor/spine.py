"""Deterministic post-commit spine (spec §8, D-SUP-4 "the spine is deterministic").

Runs detection, guarantees each created edge carries a verdict (born `provisional`, journaled
once), and returns the Detection for the judgment layer (P3.2 — Screen/Judge/Verifier) to act
on the invalidations. Contains no LLM call. Idempotent: a created edge already at `provisional`
is not re-journaled.
"""

from __future__ import annotations

from pathlib import Path

from genesis.graph.engine import GraphEngine, Verdict
from genesis.journal.journal import read_journal
from genesis.supervisor.detection import Detection, detect
from genesis.supervisor.verdicts import set_verdict


def inspect_commit(engine: GraphEngine, data_root: Path, episode_id: str, *,
                   commit_start: str, commit_end: str, ts: str) -> Detection:
    d = detect(engine, episode_id, commit_start, commit_end)
    journaled = {j.target for j in read_journal(data_root) if j.action == "verdict"}
    for edge in d.created:
        # Idempotency gate: the birth verdict is journaled at most once per edge.
        if edge.edge_id in journaled:
            continue
        # Shortcut: if it was already promoted/demoted out of provisional, don't re-birth it.
        if engine.get(edge.edge_id).verdict is not Verdict.PROVISIONAL:
            continue
        set_verdict(engine, data_root, edge, Verdict.PROVISIONAL, ts=ts)
    return d
