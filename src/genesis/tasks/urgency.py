"""Lazy urgency + effective status (spec §4.10, DR-18; A.1 status enum).

Urgency is computed at read time from (due, now) and rises as the due date nears; overdue
outranks all pending; no-due sits at baseline. `broken` is the lazily-computed status of an
overdue, still-open commitment — never an event, never stored. Clock is injected (`now`).
"""

from __future__ import annotations

from datetime import datetime

from genesis.tasks.projection import TaskState

HORIZON_DAYS = 14


def parse_iso(ts: str) -> datetime:
    s = ts.replace("Z", "+00:00")
    if "T" not in s:
        s = s + "T00:00:00+00:00"
    return datetime.fromisoformat(s)


def days_between(a_iso: str, b_iso: str) -> float:
    return (parse_iso(b_iso) - parse_iso(a_iso)).total_seconds() / 86400.0


def is_overdue(state: TaskState, now: str) -> bool:
    return state.due is not None and parse_iso(now) > parse_iso(state.due)


def urgency(state: TaskState, now: str) -> float:
    if state.status in ("fulfilled", "cancelled"):
        return 0.0
    if state.due is None:
        return 0.0
    if is_overdue(state, now):
        return 2.0
    days = days_between(now, state.due)
    if days >= HORIZON_DAYS:
        return 0.0
    return 1.0 - days / HORIZON_DAYS


def effective_status(state: TaskState, now: str) -> str:
    if state.status == "open" and state.kind == "commitment" and is_overdue(state, now):
        return "broken"
    return state.status
