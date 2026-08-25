"""The warm read-only recall daemon (spec §4.7b; design §7; D-SUP-7).

A SEPARATE read-only process holding the graph client + bge-small embedder WARM (never cold-load
per query — the MemBus-on-a-port lesson). It must NOT share the sole-writer lockfile's fate
(D-SUP-7): recall down ⇒ degrade to diary + honest-empty, capture untouched. So serve_* CATCH any
backend failure and return an honest-empty RecallResult instead of raising — nothing breaks.
Read-only: it never writes, never touches the serial commit lane.
"""

from __future__ import annotations

import logging
from pathlib import Path

from genesis.recall.scorer import Channel, ChannelResult, EmptyCause, score_channels
from genesis.recall.service import RecallResult, RecallService
from genesis.recall.tier import Tier

_log = logging.getLogger("genesis.recall")


def _honest_empty(cause: EmptyCause = EmptyCause.ABSENT) -> RecallResult:
    verdict = score_channels(
        [ChannelResult(Channel.SEMANTIC, False), ChannelResult(Channel.KEYWORD, False),
         ChannelResult(Channel.GRAPH, False)], cause=cause)
    return RecallResult(edges=[], verdict=verdict, served_anchors=[])


class RecallDaemon:
    def __init__(self, service: RecallService) -> None:
        self._service = service

    def serve_expand(self, anchor_episode: str, tier: Tier) -> RecallResult:
        try:
            return self._service.expand(anchor_episode, tier)
        except Exception:  # noqa: BLE001 — recall DOWN ⇒ honest-empty DEGRADED (AC-R2), never break the caller
            _log.warning("recall serve_expand degraded", exc_info=True)  # F-17.2: log before the polite banner
            return _honest_empty(EmptyCause.DEGRADED)

    def serve_search(self, query: str, tier: Tier, *, top_n: int = 5) -> RecallResult:
        try:
            return self._service.search(query, tier, top_n=top_n)
        except Exception:  # noqa: BLE001 — recall DOWN ⇒ diary + honest-empty DEGRADED (D-SUP-7, AC-R2)
            _log.warning("recall serve_search degraded", exc_info=True)  # F-17.2: a real bug isn't hidden
            return _honest_empty(EmptyCause.DEGRADED)


def build_recall_daemon(data_root, *, db_path: str | None = None, env=None) -> RecallDaemon:  # pragma: no cover - live only
    """Build a warm, read-only RecallDaemon over the live graph client + embedder (F-17.1; D-SUP-7).

    Composes the components that already exist and are offline-tested — the BINDING was the gap:
      real_client → GraphitiEngine → real_recall_search (hybrid search) + real_scorer (bge-small)
      → RecallService → RecallDaemon.
    Read-only: no LLM backend, no writes, no commit lane. MUST run in a SEPARATE process from the
    sole writer (D-SUP-7); it holds the graph client + embedder WARM. Lazy-imports the graph extra
    so the offline suite never reaches this (construct `RecallDaemon(RecallService(...))` there).

    Raises RuntimeError when the 'graph' extra is absent.
    """
    from datetime import datetime, timezone

    try:
        import graphiti_core  # noqa: F401, PLC0415 — lazy: absent offline
    except ImportError as exc:
        raise RuntimeError(
            "the 'graph' extra is required for a warm recall daemon; offline construct "
            "RecallDaemon(RecallService(...)) directly") from exc

    from genesis.graph.adapter import GraphitiEngine
    from genesis.graph.factory import real_client
    from genesis.linking.relatedness import real_scorer
    from genesis.recall.search_backend import real_recall_search

    resolved_db = db_path or str(Path(data_root) / "graph.db")
    client = real_client(db_path=resolved_db, env=env)
    # Recall never adds episodes; the clock is only used on the write path — a real one is harmless.
    engine = GraphitiEngine(client, clock=lambda: datetime.now(tz=timezone.utc).isoformat())
    search = real_recall_search(engine)   # semantic (bge-small) + keyword (bm25); allow-list-scoped
    scorer = real_scorer()                # bge-small relatedness for ranking
    return RecallDaemon(RecallService(engine, scorer, search=search))
