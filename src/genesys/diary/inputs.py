"""Diary input gathering (spec §4.7, App E.1, DR-10).

Deterministically collects the ~6-day ledger window into diary input lines:
prefers the enriched summary; marks not-yet-extracted entries [unverified]. Tasks and
open-questions arrive from the caller (their sources — Tasks dept P5, Supervisor
ask-queue P3 — are not built yet, so at P2 they are empty and their sections are omitted).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from genesys.ledger.entry import Extracted
from genesys.ledger.store import read_since


@dataclass
class LedgerItem:
    ts: str
    summary: str
    unverified: bool
    session_id: str | None


@dataclass
class DiaryInputs:
    ledger: list[LedgerItem] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)
    open_questions: list[dict] = field(default_factory=list)


def gather_ledger_items(data_root: Path, now_iso: str, window_days: int = 6) -> list[LedgerItem]:
    since = (datetime.fromisoformat(now_iso) - timedelta(days=window_days)).isoformat()
    items: list[LedgerItem] = []
    for e in read_since(data_root, since):
        enriched = (e.enrichment or {}).get("enriched_summary")
        if enriched:
            items.append(LedgerItem(e.ts, enriched, False, e.links.session_id))
        else:
            items.append(LedgerItem(e.ts, e.summary, e.extracted is not Extracted.DONE, e.links.session_id))
    return items
