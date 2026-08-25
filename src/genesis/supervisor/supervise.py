"""supervise_commit — the post-commit Supervisor sequence (spec §8, §4.4).

Composes the P3.1 deterministic spine (detect + born-provisional) with the P3.2 judgment layer
(two-stage gate + invalidation judgment). Serial, one atomic unit per episode (DR-05c). Returns
a summary; all writes go through the deterministic ops + journal.
"""

from __future__ import annotations

import random
from pathlib import Path

from genesis.graph.engine import GraphEngine
from genesis.supervisor.gate import run_gate
from genesis.supervisor.judgment import judge_invalidations
from genesis.supervisor.spine import inspect_commit
from genesis.workers.backend import LLMBackend


def supervise_commit(engine: GraphEngine, data_root: Path, episode_id: str, jot: str, manifest: str,
                     backend: LLMBackend, *, commit_start: str, commit_end: str, ts: str,
                     raw_span: str = "", contract: str = "",
                     ladder=None, window: str | None = None,
                     ride_along: str = "", rng: random.Random | None = None,
                     chart=None) -> dict:
    """Post-commit Supervisor sequence. The FROZEN spine (inspect_commit) and
    judge_invalidations are UNCHANGED. The opt-in ladder params (all default OFF/None)
    are threaded through to run_gate — `ladder=None` keeps the built jot-Screen path verbatim.

    Args:
        ladder: LadderConfig | None — opt-in inspection ladder (spec §3, DR-44). Default None.
        window: str | None — the raw window text for the ladder (episode.content). Default None.
        ride_along: str — opaque 3-episode context string for Tier 0 (default empty).
        rng: random.Random | None — injected RNG for deterministic sampling audit (default None).
        chart: FalsePassChart | None — control chart for Screen false-pass rate (default None).
    """
    # FROZEN spine — do NOT modify this call.
    d = inspect_commit(engine, data_root, episode_id,
                       commit_start=commit_start, commit_end=commit_end, ts=ts)
    result = run_gate(engine, data_root, episode_id, jot, manifest, d.created, backend,
                      ts=ts, raw_span=raw_span, contract=contract,
                      ladder=ladder, window=window, ride_along=ride_along, rng=rng, chart=chart)
    # FROZEN judgment — do NOT modify this call.
    reverted = judge_invalidations(engine, data_root, d.invalidated, episode_id, backend, ts=ts)
    return {
        "created": [e.edge_id for e in d.created],
        "invalidated": [e.edge_id for e in d.invalidated],
        "reverted": reverted,
        "screen": result.verdict,
    }
