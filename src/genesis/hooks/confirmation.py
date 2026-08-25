"""Session-start memory-load confirmation line (D-GCW-15 / AC-CONF1 / D-GCW-18).

One USER-VISIBLE line at SessionStart stating the memory state — the diary *content* stays LLM-only
(`additionalContext`). Four states:
- **loaded** (+count) — the ledger has extracted/saved sessions.
- **unsaved** — nothing materialized yet, but the WAL holds captured-but-unsaved content. D-GCW-18:
  `/save` is the sole materialization path, so the line must NOT say "no memories" here — it tells the
  user their session is captured and offers `/save`.
- **empty** — truly nothing captured.
- **unavailable** — the memory read failed (DEGRADED). Literalism (AC-CONF1): reachable ONLY from the
  real down-path, never hardcoded.
"""

from __future__ import annotations

from typing import NamedTuple
from pathlib import Path

from genesis.config import RECENT_SESSIONS_DEPTH
from genesis.ledger.store import read_all
from genesis.wal.record import WalRecord
from genesis.wal.store import list_segment_dates, read_segment

LOADED = "Genesis: memory loaded — {n} recent sessions"
UNSAVED = "Genesis: this session's capture is unsaved — run /save to remember it"
EMPTY = "Genesis: no memories yet"
UNAVAILABLE = "Genesis: memory unavailable"


class MemoryState(NamedTuple):
    available: bool   # False ONLY when the ledger read failed (DEGRADED)
    sessions: int     # distinct recent sessions materialized into the ledger
    unsaved: bool     # ledger empty but the WAL holds captured-but-unsaved content


def _has_unsaved_wal(data_root: Path) -> bool:
    """True iff the memory-grade WAL has any captured content (D-GCW-18 unsaved detection)."""
    try:
        for date in list_segment_dates(data_root, WalRecord.MEMORY_GRADE):
            if read_segment(data_root, WalRecord.MEMORY_GRADE, date):
                return True
    except Exception:  # noqa: BLE001 — best-effort; absence of WAL is simply "not unsaved"
        return False
    return False


def confirmation_line(state: MemoryState) -> str:
    if not state.available:
        return UNAVAILABLE           # DEGRADED — only from a real failed read (AC-CONF1)
    if state.sessions > 0:
        return LOADED.format(n=state.sessions)
    if state.unsaved:
        return UNSAVED               # D-GCW-18: captured but unsaved — never "no memories"
    return EMPTY


def memory_state(data_root: Path, *, depth: int = RECENT_SESSIONS_DEPTH) -> MemoryState:
    """Compute the SessionStart memory state. available=False ONLY when the ledger read fails."""
    try:
        entries = read_all(data_root)
    except Exception:  # noqa: BLE001 — a failed read is the DEGRADED signal, never a crash
        return MemoryState(available=False, sessions=0, unsaved=False)
    # distinct sessions, most-recent first, capped at `depth` (matches the diary's recent window)
    sessions = list(dict.fromkeys(
        e.links.session_id for e in reversed(entries) if e.links.session_id))
    count = min(len(sessions), depth)
    unsaved = count == 0 and _has_unsaved_wal(data_root)
    return MemoryState(available=True, sessions=count, unsaved=unsaved)
