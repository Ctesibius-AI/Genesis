"""Report cards — one per save/episode (spec §14 D-QA-2).

A read-only fold of the ledger (summary/extracted) + the grade-1 journal (the supervision
events scoped to that episode). Cards regenerate from files; the console holds no truth (D-QA-1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from genesis.journal.journal import JournalEntry, read_journal
from genesis.ledger.store import read_all


@dataclass
class Card:
    episode_id: str
    ts: str
    summary: str
    extracted: str
    actions: list[JournalEntry] = field(default_factory=list)


def build_cards(data_root: Path) -> list[Card]:
    journal = read_journal(data_root)
    by_scope: dict[str, list[JournalEntry]] = {}
    for j in journal:
        by_scope.setdefault(j.scope, []).append(j)
    cards: list[Card] = []
    for e in read_all(data_root):
        cards.append(Card(
            episode_id=e.entry_id, ts=e.ts, summary=e.summary,
            extracted=e.extracted.value, actions=by_scope.get(e.entry_id, []),
        ))
    return cards
