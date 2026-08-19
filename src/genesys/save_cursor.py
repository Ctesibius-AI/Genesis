"""F4-interim cursor helper (spec §2.2 "ledger-cursor delta", §7 item 2).

The cost bug F4: each Stop re-saves the whole session-so-far as a fresh episode
(n turns -> ~n²/2 re-extract cost). The interim guard, before F5's rolling record
lands: bank only material AFTER this session's last saved cursor, and skip when
nothing is new -- the same shape as the backfill idempotency guard
(backfill.cli._existing_session_ids: "Re-running the same batch enqueues 0").

CODE-REALITY (honored, not assumed): hooks.adapter._timestamps_from_events returns
("","") today (CC transcripts carry no per-event timestamp in the observed format),
so every live-saved entry has provenance.span_end == "". A literal span_end cursor
is therefore a constant empty string and cannot order saves. This helper uses
provenance.span_end WHEN NON-EMPTY, else the entry `ts` (the injected save clock --
populated and monotonic per session). Correct today AND once F5 lands real spans.
"""

from __future__ import annotations

from pathlib import Path

from genesys.ledger.entry import LedgerEntry
from genesys.ledger.store import read_all


def entry_cursor(entry: LedgerEntry) -> str:
    """The ordering cursor for one entry: span_end if present, else ts."""
    span_end = entry.provenance.span_end
    return span_end if span_end else entry.ts


def latest_span_end_for_session(data_root: Path, session_id: str) -> str:
    """Newest banked cursor for `session_id`, or "" if the session has none.

    Empty/None session_id returns "" (a session-less save is never skipped).
    ISO-8601 UTC strings from the one injected clock compare correctly lexically.
    """
    if not session_id:
        return ""
    cursors = [
        entry_cursor(e)
        for e in read_all(data_root)
        if e.links.session_id == session_id
    ]
    return max(cursors) if cursors else ""
