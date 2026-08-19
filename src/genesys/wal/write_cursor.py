"""Per-session WAL write-cursor — tracks how many transcript records have been captured.

When the automatic hook fires in append-only mode (``annotate=False``), no ledger annotation
is created, so ``save_cursor.latest_span_end_for_session`` always returns ``""`` and the
next ring re-appends the whole transcript.  This module provides a lightweight alternative:
store the number of transcript records already appended per session, and on each ring slice
to only the NEW records.

On-disk layout: ``<data_root>/wal/write-cursor/<session_id>.json``
  ``{"session_id": "<id>", "records_captured": <int>}``

This file is created and updated ONLY by the append-only hook path (``annotate=False``).
The annotating paths (``annotate=True``) do NOT use it — they use the ledger-cursor
(``latest_span_end_for_session``) as before.

Invariant after N rings over a growing transcript:
  The MEMORY_GRADE WAL segment for this session contains each reply's content EXACTLY ONCE
  (no cumulative copies). Scrub-at-append (DR-38) is unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path


def _cursor_path(data_root: Path, session_id: str) -> Path:
    return data_root / "wal" / "write-cursor" / f"{session_id}.json"


def read_captured_count(data_root: Path, session_id: str) -> int:
    """Return the number of transcript records already captured for ``session_id``, or 0."""
    if not session_id:
        return 0
    p = _cursor_path(data_root, session_id)
    if not p.exists():
        return 0
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return int(d.get("records_captured", 0))
    except (OSError, ValueError, TypeError):
        return 0


def write_captured_count(data_root: Path, session_id: str, count: int) -> None:
    """Persist ``count`` as the captured record count for ``session_id``."""
    if not session_id:
        return
    p = _cursor_path(data_root, session_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"session_id": session_id, "records_captured": count},
                   ensure_ascii=False),
        encoding="utf-8",
    )
