"""Fact-conflict resolution — panel (a) (spec §10.1a, §8.2, DR-27).

The principal selects which of two conflicting stated facts holds (earlier/new/neither-or-both);
the Supervisor writes a `stated` closure (superseded_by) or records contested-in-context. The
reason is scrubbed. No perceived-view content is involved.
"""

from __future__ import annotations

from pathlib import Path

from genesys.graph.engine import GraphEngine
from genesys.journal.journal import JournalEntry, append_journal
from genesys.scrub.scrubber import scrub_text

SELECTIONS = frozenset({"earlier", "new", "neither-or-both"})


def resolve_fact_conflict(data_root: Path, engine: GraphEngine, *, ts: str, earlier_edge: str,
                          new_edge: str, selection: str, reason: str | None = None) -> None:
    if selection not in SELECTIONS:
        raise ValueError(f"unknown fact-conflict selection: {selection!r}")
    scrubbed = scrub_text(reason).text if reason else None
    if selection == "new":
        engine.write_superseded_by(earlier_edge, new_edge)
        action, target = "supersede", earlier_edge
    elif selection == "earlier":
        engine.write_superseded_by(new_edge, earlier_edge)
        action, target = "supersede", new_edge
    else:  # neither-or-both → contested-in-context
        engine.reopen(earlier_edge, new_edge)
        action, target = "contest", earlier_edge
    append_journal(data_root, JournalEntry(
        ts=ts, action=action, scope="session", target=target, author="stated", reason=scrubbed))
