"""The manual save tool — CS4 (spec §2.2 manual ritual; DR-43 one door, two triggers).

Assistant-invocable: the Daimon calls save_tool when the owner says "save this, because X."
It annotates the CURRENT window (from the session's last saved cursor to now) with the
owner-authored jot, through the SAME annotation door (save_annotation) as the automatic hook
trigger. The window start reuses Plan 1's latest_span_end_for_session (NOT forked). Salience is
set — the manual save's remaining merit is deliberate significance-marking (§2.2, F1).
"""

from __future__ import annotations

from pathlib import Path

from genesys.config import get_assistant_name, get_principal
from genesys.ledger.entry import LedgerEntry
from genesys.save_cursor import latest_span_end_for_session
from genesys.wal.annotate import save_annotation
from genesys.wal.record import WalRecord


def save_tool(data_root: Path, *, jot: str, session_id: str, now: str,
              speakers: list[str] | None = None,
              record: WalRecord = WalRecord.MEMORY_GRADE) -> LedgerEntry:
    """Annotate the current (last-cursor, now) window with the owner-authored jot (CS4)."""
    if speakers is None:
        speakers = [get_principal(), get_assistant_name()]
    cursor = latest_span_end_for_session(data_root, session_id)
    return save_annotation(data_root, start_ts=cursor, end_ts=now, jot=jot,
                           session_id=session_id, speakers=speakers,
                           record=record, salience=True)
