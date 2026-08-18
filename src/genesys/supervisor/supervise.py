"""supervise_commit — the post-commit Supervisor sequence (spec §8, §4.4).

Composes the P3.1 deterministic spine (detect + born-provisional) with the P3.2 judgment layer
(two-stage gate + invalidation judgment). Serial, one atomic unit per episode (DR-05c). Returns
a summary; all writes go through the deterministic ops + journal.
"""

from __future__ import annotations

from pathlib import Path

from genesys.graph.engine import GraphEngine
from genesys.supervisor.gate import run_gate
from genesys.supervisor.judgment import judge_invalidations
from genesys.supervisor.spine import inspect_commit
from genesys.workers.backend import LLMBackend


def supervise_commit(engine: GraphEngine, data_root: Path, episode_id: str, jot: str, manifest: str,
                     backend: LLMBackend, *, commit_start: str, commit_end: str, ts: str,
                     raw_span: str = "", contract: str = "") -> dict:
    d = inspect_commit(engine, data_root, episode_id,
                       commit_start=commit_start, commit_end=commit_end, ts=ts)
    result = run_gate(engine, data_root, episode_id, jot, manifest, d.created, backend,
                      ts=ts, raw_span=raw_span, contract=contract)
    reverted = judge_invalidations(engine, data_root, d.invalidated, episode_id, backend, ts=ts)
    return {
        "created": [e.edge_id for e in d.created],
        "invalidated": [e.edge_id for e in d.invalidated],
        "reverted": reverted,
        "screen": result.verdict,
    }
