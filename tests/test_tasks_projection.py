"""Test task projection (tests/test_tasks_projection.py)."""
from __future__ import annotations

from genesis.tasks.events import TaskEvent
from genesis.tasks.projection import fold_tasks


def _ev(event, tid, ts, **kw):
    return TaskEvent(ts=ts, event=event, task_id=tid, source_episode=kw.pop("ep", "EP-1"), **kw)


def test_created_is_open():
    st = fold_tasks([_ev("task.created", "TS-1", "t0", title="a", kind="commitment")])
    assert st["TS-1"].status == "open" and st["TS-1"].title == "a"
    assert st["TS-1"].kind == "commitment" and st["TS-1"].created_ts == "t0"


def test_due_moved_updates_due_and_last_ts():
    st = fold_tasks([
        _ev("task.created", "TS-1", "t0", due="2026-08-20"),
        _ev("task.due_moved", "TS-1", "t1", due="2026-08-31"),
    ])
    assert st["TS-1"].due == "2026-08-31" and st["TS-1"].last_ts == "t1"


def test_done_and_cancelled_are_terminal():
    done = fold_tasks([_ev("task.created", "TS-1", "t0"), _ev("task.done", "TS-1", "t1")])
    assert done["TS-1"].status == "fulfilled"
    cancelled = fold_tasks([_ev("task.created", "TS-2", "t0"), _ev("task.cancelled", "TS-2", "t1")])
    assert cancelled["TS-2"].status == "cancelled"


def test_due_moved_after_done_does_not_reopen():
    st = fold_tasks([
        _ev("task.created", "TS-1", "t0", due="2026-08-20"),
        _ev("task.done", "TS-1", "t1"),
        _ev("task.due_moved", "TS-1", "t2", due="2026-09-01"),
    ])
    assert st["TS-1"].status == "fulfilled"  # not reopened
    assert st["TS-1"].due == "2026-09-01"  # but due still tracked


def test_orphan_non_created_event_ignored():
    st = fold_tasks([_ev("task.done", "TS-9", "t0")])  # no prior created
    assert "TS-9" not in st
