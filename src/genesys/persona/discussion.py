"""Discussion-request queue — journal-projected (spec §10.2, App A.4.7, DR-17).

"Discuss" enqueues a journal-projected request; it carries NO graph authority. Current state is
a fold over the `discussion-request` journal entries. The seed_reason is scrubbed at capture.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from genesys.journal.journal import JournalEntry, append_journal, read_journal
from genesys.scrub.scrubber import scrub_text


@dataclass
class DiscussionRequest:
    request_id: str
    anchor: str
    origin: str
    state: str
    queued_at: str
    served_at: str | None = None
    closed_at: str | None = None
    closed_reason: str | None = None
    seed_reason: str | None = None


def _dr_entries(data_root: Path) -> list[JournalEntry]:
    return [e for e in read_journal(data_root) if e.action == "discussion-request"]


def new_request_id(data_root: Path, ts: str) -> str:
    date = ts[:10]
    n = sum(1 for e in _dr_entries(data_root)
            if isinstance(e.after, dict) and e.after.get("state") == "queued"
            and str(e.after.get("request_id", "")).startswith(f"DR-{date}."))
    return f"DR-{date}.{n:04d}"


def enqueue(data_root: Path, *, ts: str, anchor: str, origin: str = "dashboard",
            seed_reason: str | None = None) -> str:
    rid = new_request_id(data_root, ts)
    scrubbed = scrub_text(seed_reason).text if seed_reason else None
    append_journal(data_root, JournalEntry(
        ts=ts, action="discussion-request", scope="session", target=anchor, author="supervisor",
        after={"state": "queued", "request_id": rid, "origin": origin, "seed_reason": scrubbed}))
    return rid


def serve(data_root: Path, *, ts: str, request_id: str, anchor: str) -> None:
    append_journal(data_root, JournalEntry(
        ts=ts, action="discussion-request", scope="session", target=anchor, author="supervisor",
        after={"state": "served", "request_id": request_id}))


def close(data_root: Path, *, ts: str, request_id: str, anchor: str, reason: str) -> None:
    append_journal(data_root, JournalEntry(
        ts=ts, action="discussion-request", scope="session", target=anchor, author="supervisor",
        after={"state": "closed", "request_id": request_id, "closed_reason": reason}))


def fold_requests(data_root: Path) -> dict[str, DiscussionRequest]:
    reqs: dict[str, DiscussionRequest] = {}
    for e in _dr_entries(data_root):
        a = e.after if isinstance(e.after, dict) else {}
        rid = a.get("request_id")
        if not rid:
            continue
        state = a.get("state")
        if state == "queued":
            reqs[rid] = DiscussionRequest(
                request_id=rid, anchor=e.target or "", origin=a.get("origin", "dashboard"),
                state="queued", queued_at=e.ts, seed_reason=a.get("seed_reason"))
        elif rid in reqs and state == "served":
            reqs[rid].state = "served"
            reqs[rid].served_at = e.ts
        elif rid in reqs and state == "closed":
            reqs[rid].state = "closed"
            reqs[rid].closed_at = e.ts
            reqs[rid].closed_reason = a.get("closed_reason")
    return reqs


def backlog_breach(requests: dict[str, DiscussionRequest], *, now: str, max_open: int,
                   max_age_days: float) -> bool:
    from genesys.tasks.urgency import days_between
    open_reqs = [r for r in requests.values() if r.state in ("queued", "served")]
    if len(open_reqs) > max_open:
        return True
    return any(days_between(r.queued_at, now) > max_age_days for r in open_reqs)
