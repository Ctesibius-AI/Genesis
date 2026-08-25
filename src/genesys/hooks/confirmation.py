"""Session-start memory-load confirmation line (D-GCW-15 / AC-CONF1).

One USER-VISIBLE line at SessionStart stating the memory state — the diary *content* stays LLM-only
(`additionalContext`). Three states: loaded (+count) / empty / unavailable. Literalism (AC-CONF1):
"unavailable" is reachable ONLY from the real down-path (a failed memory read), never hardcoded.
"""

from __future__ import annotations

from pathlib import Path

from genesys.config import RECENT_SESSIONS_DEPTH
from genesys.ledger.store import read_all

LOADED = "Genesys: memory loaded — {n} recent sessions"
EMPTY = "Genesys: no memories yet"
UNAVAILABLE = "Genesys: memory unavailable"


def confirmation_line(*, available: bool, count: int) -> str:
    if not available:
        return UNAVAILABLE          # DEGRADED — only from a real failed read (AC-CONF1)
    if count <= 0:
        return EMPTY
    return LOADED.format(n=count)


def memory_state(data_root: Path, *, depth: int = RECENT_SESSIONS_DEPTH) -> tuple[bool, int]:
    """Return (available, recent_session_count). available=False ONLY when the ledger read fails."""
    try:
        entries = read_all(data_root)
    except Exception:  # noqa: BLE001 — a failed read is the DEGRADED signal, never a crash
        return (False, 0)
    # distinct sessions, most-recent first, capped at `depth` (matches the diary's recent window)
    sessions = list(dict.fromkeys(
        e.links.session_id for e in reversed(entries) if e.links.session_id))
    return (True, min(len(sessions), depth))
