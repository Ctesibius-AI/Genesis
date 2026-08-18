"""Test task event store (tests/test_tasks_events.py)."""
from __future__ import annotations

import pytest

from genesys.tasks.events import (
    TaskEvent,
    append_event,
    from_jsonl,
    new_task_id,
    read_events,
    to_jsonl,
)


def test_task_event_rejects_unknown_event():
    with pytest.raises(ValueError):
        TaskEvent(ts="t", event="task.exploded", task_id="TS-1", source_episode="EP-1")


def test_roundtrip_jsonl():
    e = TaskEvent(ts="2026-08-17T10:00:00Z", event="task.created", task_id="TS-1",
                  source_episode="EP-1", project_ref="PR-9", kind="commitment",
                  title="send INV-042", due="2026-08-31", recipient="Acme")
    assert from_jsonl(to_jsonl(e)) == e


def test_append_and_read(tmp_path):
    a = TaskEvent(ts="2026-08-17T10:00:00Z", event="task.created", task_id="TS-1",
                  source_episode="EP-1", title="a")
    b = TaskEvent(ts="2026-08-17T10:05:00Z", event="task.done", task_id="TS-1",
                  source_episode="EP-2")
    append_event(tmp_path, a)
    append_event(tmp_path, b)
    got = read_events(tmp_path)
    assert [e.event for e in got] == ["task.created", "task.done"]


def test_read_missing_is_empty(tmp_path):
    assert read_events(tmp_path) == []


def test_new_task_id_counts_created_per_day(tmp_path):
    assert new_task_id(tmp_path, "2026-08-17") == "TS-2026-08-17.0000"
    append_event(tmp_path, TaskEvent(ts="2026-08-17T10:00:00Z", event="task.created",
                                     task_id="TS-2026-08-17.0000", source_episode="EP-1"))
    assert new_task_id(tmp_path, "2026-08-17") == "TS-2026-08-17.0001"
    # a different day restarts the sequence
    assert new_task_id(tmp_path, "2026-08-18") == "TS-2026-08-18.0000"
