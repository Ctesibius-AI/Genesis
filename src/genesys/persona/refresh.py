"""Refresh-as-ratification (spec §11 D-CON-7/7a, §8.7).

The LLM proposes a draft; the principal edits/ranks/ratifies; the ratified selection is compiled
and written back with a journaled `constitution-refresh`. The draft is the ONLY candidate in the
system, and it is principal-authored — nothing seats without his ratification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from genesys.journal.journal import JournalEntry, append_journal
from genesys.persona.compile_guard import assert_no_perceives
from genesys.persona.constitution import ConstitutionLine, compile_constitution, format_line


class Drafter(Protocol):
    def draft(self, items: list) -> list: ...


class FakeDrafter:
    def __init__(self, order: list | None = None) -> None:
        self._order = order

    def draft(self, items: list) -> list:
        return list(self._order) if self._order is not None else list(items)


def draft_constitution(drafter: Drafter, items: list) -> list:
    assert_no_perceives(items)
    return drafter.draft(items)


def ratify(data_root: Path, *, ts: str, ratified_items: list, editor: str = "principal") -> list[ConstitutionLine]:
    assert_no_perceives(ratified_items)
    lines = compile_constitution(ratified_items)
    append_journal(data_root, JournalEntry(
        ts=ts, action="constitution-refresh", scope="constitution", author=editor,
        after={"lines": [format_line(l) for l in lines]}))
    return lines
