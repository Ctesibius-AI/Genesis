"""Reconciliation & discussion surface facade (spec §10).

Ties alignment → PT-7 notice, "Discuss" → enqueue (no graph authority), and the in-window /
summons raise → PT-8 opener (topics only). Content is never served here — only anchors, notices,
and lifecycle. The backlog-breach check journals when the queue is over budget.
"""

from __future__ import annotations

from pathlib import Path

from genesys.journal.journal import JournalEntry, append_journal
from genesys.persona.alignment import Alignment
from genesys.persona.discussion import backlog_breach, enqueue, fold_requests, serve
from genesys.persona.templates import pt7_reconciliation_notice, pt8_opener
from genesys.persona.window import DiscussionWindow, may_raise


def notice_if_divergent(alignment: Alignment) -> str | None:
    if alignment.status == "divergent":
        return pt7_reconciliation_notice(alignment.anchor)
    return None


def request_discussion(data_root: Path, *, ts: str, anchor: str, seed_reason: str | None = None,
                       origin: str = "dashboard") -> str:
    return enqueue(data_root, ts=ts, anchor=anchor, origin=origin, seed_reason=seed_reason)


def raise_pending(data_root: Path, window: DiscussionWindow, *, now: str, text: str = ""):
    if not may_raise(window, now=now, text=text):
        return None, []
    open_reqs = [r for r in fold_requests(data_root).values() if r.state in ("queued", "served")]
    if not open_reqs:
        return None, []
    open_reqs.sort(key=lambda r: r.request_id)
    opener = pt8_opener([r.anchor for r in open_reqs])
    for r in open_reqs:
        if r.state == "queued":
            serve(data_root, ts=now, request_id=r.request_id, anchor=r.anchor)
    return opener, open_reqs


def check_backlog(data_root: Path, requests, *, now: str, max_open: int,
                  max_age_days: float) -> bool:
    if backlog_breach(requests, now=now, max_open=max_open, max_age_days=max_age_days):
        append_journal(data_root, JournalEntry(
            ts=now, action="backlog-breach", scope="session", author="supervisor"))
        return True
    return False
