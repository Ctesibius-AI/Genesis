"""The release machine (spec §8.6 items 1-4).

Opens/closes the session-scoped ReleaseContext and journals every transition
(opinion-ask/confirm/release/close). Never writes a perceives edge or any graph state — the
context lives in the session; the audit trail lives in the grade-1 journal.
"""

from __future__ import annotations

from pathlib import Path

from genesys.journal.journal import JournalEntry, append_journal
from genesys.persona.department import PerceptionDepartment
from genesys.persona.perceives import PRINCIPAL
from genesys.persona.release import ReleaseContext, closed, is_open


def topic_anchors(asked_anchor: str, neighbours: list[str] | None = None) -> list[str]:
    out: list[str] = []
    for a in [asked_anchor, *(neighbours or [])]:
        if a not in out:
            out.append(a)
    return out


def general_anchors(dept: PerceptionDepartment, *, top_n: int, subject: str = PRINCIPAL) -> list[str]:
    edges = dept.edges_for_subject(subject)
    ranked = sorted(edges, key=lambda e: (-e.strength(), e.to))
    return [e.to for e in ranked[:top_n]]


def open_release(data_root: Path, dept: PerceptionDepartment, *, asked_anchor: str, scope: str,
                 ts: str, opened_by: str, neighbours: list[str] | None = None, top_n: int = 3,
                 subject: str = PRINCIPAL) -> ReleaseContext:
    append_journal(data_root, JournalEntry(ts=ts, action="opinion-ask", scope="session",
                                           target=asked_anchor, author="principal"))
    append_journal(data_root, JournalEntry(ts=ts, action="opinion-confirm", scope="session",
                                           target=asked_anchor, author="principal"))
    if scope == "general":
        anchors = general_anchors(dept, top_n=top_n, subject=subject)
    else:
        anchors = topic_anchors(asked_anchor, neighbours)
    append_journal(data_root, JournalEntry(ts=ts, action="opinion-release", scope="session",
                                           target=asked_anchor, author="supervisor",
                                           after={"scope": scope, "anchors": anchors}))
    return ReleaseContext(open=True, open_anchors=anchors, scope=scope,
                          opened_by=opened_by, confirmed_at=ts)


def close_release(data_root: Path, ctx: ReleaseContext | None, *, reason: str,
                  ts: str) -> ReleaseContext:
    if is_open(ctx):
        append_journal(data_root, JournalEntry(ts=ts, action="opinion-close", scope="session",
                                               author="supervisor", reason=reason,
                                               after={"closed_by": reason}))
    return closed()
