"""P5 integration seam: extraction/capture task-lifecycle signal -> task.* events.

The DR-37 capture-mirror (genesys.capture.mirror) already surfaces first-class
``task.created`` / ``task.completed`` projection entries (spec §4.2a). This wires that
clean signal into the event-sourced Tasks store (spec §4.10, DR-17): each captured
task-lifecycle entry becomes a ``TaskEvent`` via the existing emit/events API.

Contract under test:
  - task.created projection entry  -> task.created event (record_created)
  - task.completed projection entry -> task.done event   (record_done)
  - deterministic task_id derived from the capture correlation id (create/complete pair)
  - idempotent: re-running the same capture never double-emits (Stop AND SessionEnd
    both mirror the same transcript).
"""

from __future__ import annotations

from pathlib import Path

from genesys.capture.mirror import mirror_events
from genesys.tasks.capture_emit import emit_task_events_from_capture
from genesys.tasks.department import tasks_department
from genesys.tasks.events import read_events


def _capture_with_task(created_label: str, completed: bool, task_id: str = "t-1"):
    events = [
        {"type": "user", "author": "principal", "text": "let's do the thing"},
        {"type": "task_created", "task_id": task_id, "text": created_label},
    ]
    if completed:
        events.append(
            {"type": "task_completed", "task_id": task_id, "text": "done: " + created_label}
        )
    return mirror_events(events)


def test_task_created_signal_emits_task_created_event(tmp_path: Path):
    cap = _capture_with_task("send PHR008", completed=False)
    emitted = emit_task_events_from_capture(
        tmp_path, cap, ts="2026-08-17T10:00:00+00:00", source_episode="EP-1"
    )
    events = read_events(tmp_path)
    assert len(events) == 1
    assert events[0].event == "task.created"
    assert events[0].title == "send PHR008"
    assert events[0].source_episode == "EP-1"
    # the emitter returns the store task_id it minted, keyed by capture id
    assert emitted == {"t-1": events[0].task_id}


def test_task_completed_signal_emits_done_referencing_created(tmp_path: Path):
    cap = _capture_with_task("send PHR008", completed=True)
    emit_task_events_from_capture(
        tmp_path, cap, ts="2026-08-17T10:00:00+00:00", source_episode="EP-1"
    )
    events = read_events(tmp_path)
    kinds = [e.event for e in events]
    assert kinds == ["task.created", "task.done"]
    # done must reference the SAME store task_id created for capture id t-1
    assert events[1].task_id == events[0].task_id
    # and the task is terminal -> dropped from the active department view
    assert tasks_department(tmp_path, now="2026-08-17T12:00:00+00:00") == []


def test_created_only_is_open_in_department(tmp_path: Path):
    cap = _capture_with_task("review the spec", completed=False)
    emit_task_events_from_capture(
        tmp_path, cap, ts="2026-08-17T10:00:00+00:00", source_episode="EP-1"
    )
    views = tasks_department(tmp_path, now="2026-08-17T12:00:00+00:00")
    assert len(views) == 1
    assert views[0].state.title == "review the spec"
    assert views[0].effective_status == "open"


def test_idempotent_rerun_does_not_double_emit(tmp_path: Path):
    cap = _capture_with_task("ship it", completed=True)
    # Stop fires...
    emit_task_events_from_capture(
        tmp_path, cap, ts="2026-08-17T10:00:00+00:00", source_episode="EP-1"
    )
    # ...then SessionEnd mirrors the SAME transcript again.
    emit_task_events_from_capture(
        tmp_path, cap, ts="2026-08-17T10:05:00+00:00", source_episode="EP-1"
    )
    events = read_events(tmp_path)
    kinds = [e.event for e in events]
    assert kinds == ["task.created", "task.done"]  # exactly one of each, no duplicates


def test_deterministic_ids_across_fresh_stores(tmp_path: Path):
    cap = _capture_with_task("stable id", completed=False, task_id="t-42")
    a = tmp_path / "a"
    b = tmp_path / "b"
    id_a = emit_task_events_from_capture(a, cap, ts="2026-08-17T10:00:00+00:00",
                                         source_episode="EP-1")["t-42"]
    id_b = emit_task_events_from_capture(b, cap, ts="2026-08-17T10:00:00+00:00",
                                         source_episode="EP-1")["t-42"]
    assert id_a == id_b  # same capture id -> same store id, no wall-clock counter


def test_no_task_signal_emits_nothing(tmp_path: Path):
    cap = mirror_events([
        {"type": "user", "author": "principal", "text": "just chatting"},
        {"type": "assistant_text", "author": "daimon", "text": "sure"},
    ])
    emitted = emit_task_events_from_capture(
        tmp_path, cap, ts="2026-08-17T10:00:00+00:00", source_episode="EP-1"
    )
    assert emitted == {}
    assert read_events(tmp_path) == []


def test_completed_without_created_is_ignored_defensively(tmp_path: Path):
    # a task.completed whose task_id was never created in THIS capture: nothing to close.
    cap = mirror_events([
        {"type": "task_completed", "task_id": "t-orphan", "text": "closed something"},
    ])
    emitted = emit_task_events_from_capture(
        tmp_path, cap, ts="2026-08-17T10:00:00+00:00", source_episode="EP-1"
    )
    assert emitted == {}
    assert read_events(tmp_path) == []
