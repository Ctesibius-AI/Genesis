"""The manual save tool — CS4 (spec §2.2 manual ritual; DR-43 one door, two triggers).

Assistant-invocable: the Daimon calls save_tool when the owner says "save this, because X."
It annotates the CURRENT window (from the session's last saved cursor to now) with the
owner-authored jot, through the SAME annotation door (save_annotation) as the automatic hook
trigger. The window start reuses Plan 1's latest_span_end_for_session (NOT forked). The manual
save's value is the owner-authored jot/label on a deliberate flush — `/save` = archival, not
curation (D-GCW-11): the dead significance flag was removed.
"""

from __future__ import annotations

from pathlib import Path

from genesis.config import get_assistant_name, get_principal
from genesis.ledger.entry import LedgerEntry
from genesis.save_cursor import latest_span_end_for_session
from genesis.wal.annotate import save_annotation
from genesis.wal.record import WalRecord


def save_tool(data_root: Path, *, jot: str, session_id: str, now: str,
              speakers: list[str] | None = None,
              record: WalRecord = WalRecord.MEMORY_GRADE) -> LedgerEntry:
    """Annotate the current (last-cursor, now) window with the owner-authored jot (CS4)."""
    if speakers is None:
        speakers = [get_principal(), get_assistant_name()]
    cursor = latest_span_end_for_session(data_root, session_id)
    return save_annotation(data_root, start_ts=cursor, end_ts=now, jot=jot,
                           session_id=session_id, speakers=speakers,
                           record=record)
