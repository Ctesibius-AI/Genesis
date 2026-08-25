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
from genesys.extraction.lock import clear_if_dead, single_instance
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
               project: bool = False,
               time_budget_s: float | None = None, clock=None,
               ladder=None, rng=None, chart=None, ride_along_for=None) -> list[str]:
    """Drain up to `window` queued entries, optionally applying semantic links, recording
    Supervisor-decided supersession, and projecting the final link state to typed edges.

    - `time_budget_s`: BT-2 / D-GCW-5 (AC-D1) bounded drain — stop taking NEW entries once
      `clock()` shows the elapsed budget is spent; the remainder stays `Extracted.NO` and is
      deferred to the next start. `None` = count-bound only (`window`). An in-flight entry is
      never cut mid-way; the bound gates the *start* of each entry (never a block-forever drain).
    - `clock`: injected monotonic clock (callable -> float seconds); default `time.monotonic`.
      A stale dead-owner `.drain.lock` is cleared before acquiring the lock (AC-X1).
    - `scorer`: populate same_topic/references/continues after supervise_commit (DR-20).
    - `supersessions`: entry_id -> SupersessionDecision from the Supervisor judgment path;
      records supersedes/caused_by on the ledger and writes graph superseded_by (§8.2, §4.9).
    - `project`: project each drained entry's complete links into typed episode edges last
      (D-SPINE-4). All three are opt-in; existing callers omitting them work unchanged.
    - `ladder`: LadderConfig | None — opt-in inspection ladder (spec §3, DR-44). Default None
      keeps the built jot-Screen path for every entry. When supplied, the ladder window is
      `episode.content` (already the read_window-sourced raw span, Plan 2). NOTE: the
      `window` parameter above (int, default 5) is the DETECTION window (number of entries
      to drain) — it is DISTINCT from and never clobbered by the ladder params below.
    - `rng`: injected random.Random for deterministic sampling audit. Default None.
    - `chart`: FalsePassChart for Screen false-pass rate control chart. Default None.
    - `ride_along_for`: optional callable (entry -> str) supplying the 3-episode ride-along
      context (Tier 0 opaque extra corpus). Default None => empty ride-along.
    Structural links (prev/next) are set at save time; DR-09 lookback+backfill holds throughout.
    """
    processed: list[str] = []
    if clock is None:
        import time
        clock = time.monotonic
    clear_if_dead(data_root, ts=ts)  # AC-X1: a crashed drain never permanently wedges ingestion
    start = clock()
    with single_instance(data_root, ts=ts):
        queued = [e for e in read_all(data_root) if e.extracted is Extracted.NO][:window]
        for entry in queued:
            # AC-D1 bounded drain: stop STARTING new entries past the time budget; defer the rest.
            if time_budget_s is not None and (clock() - start) >= time_budget_s:
                break
            entry.extracted = Extracted.IN_PROGRESS
            update(data_root, entry)
            episode = prepare_episode(data_root, entry)
            result = run_grapher(engine, episode)
            commit_start, commit_end = engine.window_for(episode.episode_id)
            supervise_commit(engine, data_root, episode.episode_id, jot=episode.jot,
                             manifest=render_manifest(result), backend=backend,
                             commit_start=commit_start, commit_end=commit_end, ts=ts,
                             raw_span=episode.content,
                             ladder=ladder,
                             window=(episode.content if ladder is not None else None),
                             ride_along=(ride_along_for(entry) if ride_along_for is not None else ""),
                             rng=rng, chart=chart)
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
