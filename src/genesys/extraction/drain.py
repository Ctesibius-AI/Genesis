"""Windowed single-instance drain (spec §4.4/§4.5/§4.14, DR-05a/b/c).

Under the single-instance lock, take up to `window` queued (extracted==no) ledger entries
oldest-first, and for each: Analyst prepares the owned raw → Grapher feeds add_episode →
supervise_commit inspects/gates/judges → mark the entry done. Serial FIFO; the queue IS the
ledger; a wedged in-progress is P1 doctor's job.
"""

from __future__ import annotations

from pathlib import Path

from genesys.extraction.analyst import prepare_episode
from genesys.extraction.grapher import render_manifest, run_grapher
from genesys.extraction.lock import single_instance
from genesys.graph.engine import GraphEngine
from genesys.ledger.entry import Extracted
from genesys.ledger.store import read_all, update
from genesys.linking.decision import SupersessionDecision
from genesys.linking.projection import project_entry_links
from genesys.linking.relatedness import RelatednessScorer
from genesys.linking.semantic import apply_semantic_links
from genesys.linking.supersession import apply_supersession
from genesys.supervisor.supervise import supervise_commit
from genesys.workers.backend import LLMBackend


def drain_once(data_root: Path, engine: GraphEngine, backend: LLMBackend, *,
               ts: str, window: int = 5,
               scorer: RelatednessScorer | None = None,
               supersessions: dict[str, SupersessionDecision] | None = None,
               project: bool = False) -> list[str]:
    """Drain up to `window` queued entries, optionally applying semantic links, recording
    Supervisor-decided supersession, and projecting the final link state to typed edges.

    - `scorer`: populate same_topic/references/continues after supervise_commit (DR-20).
    - `supersessions`: entry_id -> SupersessionDecision from the Supervisor judgment path;
      records supersedes/caused_by on the ledger and writes graph superseded_by (§8.2, §4.9).
    - `project`: project each drained entry's complete links into typed episode edges last
      (D-SPINE-4). All three are opt-in; existing callers omitting them work unchanged.
    Structural links (prev/next) are set at save time; DR-09 lookback+backfill holds throughout.
    """
    processed: list[str] = []
    with single_instance(data_root, ts=ts):
        queued = [e for e in read_all(data_root) if e.extracted is Extracted.NO][:window]
        for entry in queued:
            entry.extracted = Extracted.IN_PROGRESS
            update(data_root, entry)
            episode = prepare_episode(data_root, entry)
            result = run_grapher(engine, episode)
            commit_start, commit_end = engine.window_for(episode.episode_id)
            supervise_commit(engine, data_root, episode.episode_id, jot=episode.jot,
                             manifest=render_manifest(result), backend=backend,
                             commit_start=commit_start, commit_end=commit_end, ts=ts,
                             raw_span=episode.content)
            # Semantic enrichment (DR-20): apply after graph commit, before marking DONE.
            # Structural links (prev/next) were already set at save time.
            if scorer is not None:
                apply_semantic_links(data_root, entry, scorer)
                update(data_root, entry)
            # Supersession (§8.2 rightful closure, §4.9 "change = supersession"): the
            # Supervisor decides; this records the ledger lists + graph superseded_by.
            decision = (supersessions or {}).get(entry.entry_id)
            if decision is not None and not decision.is_empty():
                apply_supersession(data_root, entry, engine,
                                   superseded_entry_ids=decision.superseded_entry_ids,
                                   superseded_edge_ids=decision.superseded_edge_ids,
                                   caused_by=decision.caused_by)
                update(data_root, entry)
            # Project the final link state into typed episode edges (D-SPINE-4). Last, so
            # structural + semantic + supersession links are all reflected.
            if project:
                project_entry_links(entry, engine)
            entry.extracted = Extracted.DONE
            update(data_root, entry)
            processed.append(entry.entry_id)
    return processed
