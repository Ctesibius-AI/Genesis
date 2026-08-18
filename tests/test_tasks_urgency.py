"""Test task urgency and effective status (tests/test_tasks_urgency.py)."""
from __future__ import annotations

from genesys.tasks.projection import TaskState
from genesys.tasks.urgency import (
    HORIZON_DAYS,
    effective_status,
    is_overdue,
    urgency,
)


def _t(**kw):
    base = dict(task_id="TS-1", title="x", kind="task", status="open", project_ref=None,
                due=None, recipient=None, source_episode="EP-1", created_ts="t", last_ts="t")
    base.update(kw)
    return TaskState(**base)


NOW = "2026-08-17T00:00:00Z"


def test_no_due_is_baseline():
    assert urgency(_t(due=None), NOW) == 0.0


def test_terminal_is_zero():
    assert urgency(_t(due="2026-08-10", status="fulfilled"), NOW) == 0.0


def test_overdue_ranks_above_pending():
    over = urgency(_t(due="2026-08-10"), NOW)          # 7 days ago
    near = urgency(_t(due="2026-08-18"), NOW)          # 1 day out
    assert over == 2.0 and 0.0 < near < 2.0 and over > near


def test_nearer_due_is_more_urgent():
    near = urgency(_t(due="2026-08-18"), NOW)          # 1 day
    far = urgency(_t(due="2026-08-27"), NOW)           # 10 days
    assert near > far


def test_beyond_horizon_is_zero():
    assert urgency(_t(due="2026-09-30"), NOW) == 0.0   # > 14 days
    assert HORIZON_DAYS == 14


def test_effective_status_broken_only_for_overdue_open_commitment():
    assert effective_status(_t(kind="commitment", due="2026-08-10"), NOW) == "broken"
    assert effective_status(_t(kind="task", due="2026-08-10"), NOW) == "open"   # task, not commitment
    assert effective_status(_t(kind="commitment", due="2026-08-31"), NOW) == "open"  # not overdue
    assert effective_status(_t(kind="commitment", due="2026-08-10", status="fulfilled"), NOW) == "fulfilled"
    assert is_overdue(_t(due="2026-08-10"), NOW) is True
