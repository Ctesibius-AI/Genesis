from __future__ import annotations

from pathlib import Path

from genesys.console.cards import Card, build_cards
from genesys.journal.journal import JournalEntry, append_journal
from genesys.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesys.ledger.store import append


def _seed(tmp_path: Path):
    eid = "EP-2026-08-17.0001"
    append(tmp_path, LedgerEntry(entry_id=eid, ts="2026-08-17T10:00:00+00:00", summary="did a thing",
           provenance=Provenance(eid, "a", "b", ["the principal"]), links=Links(session_id="s"),
           extracted=Extracted.DONE))
    append_journal(tmp_path, JournalEntry(ts="2026-08-17T10:00:01+00:00", action="verdict",
                   scope=eid, target="e1", after="provisional", author="supervisor"))
    append_journal(tmp_path, JournalEntry(ts="2026-08-17T10:00:02+00:00", action="gate-resolve",
                   scope=eid, after="pass", author="supervisor"))
    return eid


def test_card_per_episode_with_summary_and_actions(tmp_path: Path):
    eid = _seed(tmp_path)
    cards = build_cards(tmp_path)
    assert len(cards) == 1
    c = cards[0]
    assert isinstance(c, Card)
    assert c.episode_id == eid and c.summary == "did a thing" and c.extracted == "done"
    assert [a.action for a in c.actions] == ["verdict", "gate-resolve"]


def test_journal_without_ledger_entry_is_skipped(tmp_path: Path):
    append_journal(tmp_path, JournalEntry(ts="2026-08-17T10:00:00+00:00", action="scrub",
                   scope="EP-orphan", author="supervisor"))
    assert build_cards(tmp_path) == []  # no ledger entry → no card
