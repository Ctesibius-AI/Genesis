"""The warm read-only recall daemon (spec §4.7b; design §7; D-SUP-7).

A SEPARATE read-only process holding the graph client + bge-small embedder WARM (never cold-load
per query — the MemBus-on-a-port lesson). It must NOT share the sole-writer lockfile's fate
(D-SUP-7): recall down ⇒ degrade to diary + honest-empty, capture untouched. So serve_* CATCH any
backend failure and return an honest-empty RecallResult instead of raising — nothing breaks.
Read-only: it never writes, never touches the serial commit lane.
"""

from __future__ import annotations

from genesys.persona.release import ReleaseContext
from genesys.recall.scorer import Channel, ChannelResult, EmptyCause, score_channels
from genesys.recall.service import RecallResult, RecallService
from genesys.recall.tier import Tier


def _honest_empty(cause: EmptyCause = EmptyCause.ABSENT) -> RecallResult:
    verdict = score_channels(
        [ChannelResult(Channel.SEMANTIC, False), ChannelResult(Channel.KEYWORD, False),
         ChannelResult(Channel.GRAPH, False)], cause=cause)
    return RecallResult(edges=[], verdict=verdict, served_anchors=[])


class RecallDaemon:
    def __init__(self, service: RecallService) -> None:
        self._service = service

    def serve_expand(self, anchor_episode: str, tier: Tier, *,
                     ctx: ReleaseContext | None = None) -> RecallResult:
        try:
            return self._service.expand(anchor_episode, tier, ctx=ctx)
        except Exception:  # noqa: BLE001 — degrade to honest-empty, never break the caller
            return _honest_empty()

    def serve_search(self, query: str, tier: Tier, *, ctx: ReleaseContext | None = None,
                     top_n: int = 5) -> RecallResult:
        try:
            return self._service.search(query, tier, ctx=ctx, top_n=top_n)
        except Exception:  # noqa: BLE001 — recall down ⇒ diary + honest-empty (D-SUP-7)
            return _honest_empty()


def build_recall_daemon(data_root, *, db_path: str | None = None, env=None) -> RecallDaemon:
    """Build a warm RecallDaemon over the live graph client + embedder (design §7, D-SUP-7).

    Documented stub (same posture as graph.factory.real_client / relatedness.real_scorer). Lazy-
    imports the graph extra INSIDE this function; the offline suite never reaches it. The live
    daemon MUST run as a SEPARATE process from the sole writer (D-SUP-7) and hold the client +
    bge-small embedder WARM (never cold-load per query).

    Raises RuntimeError when the extra is absent (offline: construct RecallDaemon(RecallService(...))
    directly); NotImplementedError when present but the harness binding is not yet wired.
    """
    try:
        import graphiti_core  # noqa: F401, PLC0415 — lazy: absent offline
    except ImportError as exc:  # pragma: no cover - exercised only where the extra is absent
        raise RuntimeError(
            "the 'graph' extra is required for a warm recall daemon; offline construct "
            "RecallDaemon(RecallService(...)) directly") from exc
    raise NotImplementedError(  # pragma: no cover - reached only with the extra installed
        "warm recall daemon wiring lands with the graph harness; offline uses RecallDaemon(...)")
