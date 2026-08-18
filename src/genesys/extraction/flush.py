"""Flush-trigger policy (spec §4.5, DR-06).

Decides WHEN to drain. window>=5 is the primary hard trigger; idle / session-close / PreCompact /
`/night` are hard backstops that guarantee a drain on a slow day; inferred `departure` is a SOFT
trigger — it flushes sooner but is never the guarantee (NL departure inference misfires, DR-06).
"""

from __future__ import annotations

HARD_TRIGGERS: frozenset[str] = frozenset({"idle", "session-close", "precompact", "night"})


def should_flush(queue_len: int, trigger: str, *, window: int = 5) -> bool:
    if queue_len >= window:
        return True
    if trigger in HARD_TRIGGERS and queue_len > 0:
        return True
    if trigger == "departure" and queue_len > 0:
        return True
    return False
