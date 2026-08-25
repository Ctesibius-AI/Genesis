"""P5 seam wired through the live hook dispatch (spec §4.10, §4.2a, DR-37).

When a capture carries first-class task-lifecycle records, the Stop / SessionEnd /
PreCompact hook path emits the corresponding ``task.*`` events into the event-sourced
Tasks store — attributed to the ledger entry the same save produced.

Opt-in and backward-compatible (like the P4 drain wiring): emission is OFF by default, so
every existing hook test is unaffected. All offline (fixtures only).
"""

from __future__ import annotations

import json
from pathlib import Path

from genesis.hooks.adapter import dispatch
from genesis.hooks.translate import cc_transcript_to_events
from genesis.tasks.events import read_events

NOW = "2026-08-17T12:00:00+00:00"


def _transcript_with_tasks(tmp_path: Path) -> Path:
    """A transcript that also carries the documented Genesis task-record intake shape
    (same shape as tests/fixtures/sample_transcript.json)."""
    records = [
        {"type": "user", "message": {"role": "user", "content": "let's ship PHR008"}},
        {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "text", "text": "On it."}]}},
        {"type": "task_created", "task_id": "t-1", "text": "send PHR008"},
        {"type": "task_completed", "task_id": "t-1", "text": "PHR008 sent"},
    ]
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


# --- translator forwards the documented task-record intake shape --------------------- #

def test_translator_forwards_task_records():
    records = [
        {"type": "task_created", "task_id": "t-1", "text": "do X"},
        {"type": "task_completed", "task_id": "t-1", "text": "did X"},
    ]
    events = cc_transcript_to_events(records)
    types = [e["type"] for e in events]
    assert types == ["task_created", "task_completed"]
    assert events[0]["task_id"] == "t-1" and events[0]["text"] == "do X"


# --- backward-compat: emission is OFF by default ------------------------------------- #

def test_stop_hook_does_not_emit_task_events_by_default(tmp_path: Path):
    transcript = _transcript_with_tasks(tmp_path)
    hook = {"hook_event_name": "Stop", "transcript_path": str(transcript),
            "session_id": "s"}
    result = dispatch(hook, tmp_path, now=NOW)  # no emit_task_events kwarg
    assert "entry_id" in result
    assert read_events(tmp_path) == []  # opt-in: nothing emitted


# --- opt-in: Stop / SessionEnd / PreCompact emit task.* events ----------------------- #

def test_stop_hook_emits_task_events_when_enabled(tmp_path: Path):
    transcript = _transcript_with_tasks(tmp_path)
    hook = {"hook_event_name": "Stop", "transcript_path": str(transcript),
            "session_id": "s"}
    result = dispatch(hook, tmp_path, now=NOW, emit_task_events=True)
    events = read_events(tmp_path)
    kinds = [e.event for e in events]
    assert kinds == ["task.created", "task.done"]
    # attributed to the ledger entry the same save produced
    assert all(e.source_episode == result["entry_id"] for e in events)
    assert events[0].title == "send PHR008"


def test_precompact_emits_task_events_when_enabled(tmp_path: Path):
    transcript = _transcript_with_tasks(tmp_path)
    hook = {"hook_event_name": "PreCompact", "transcript_path": str(transcript),
            "session_id": "s"}
    result = dispatch(hook, tmp_path, now=NOW, backend=None, emit_task_events=True)
    events = read_events(tmp_path)
    assert [e.event for e in events] == ["task.created", "task.done"]
    assert all(e.source_episode == result["entry_id"] for e in events)


def test_stop_then_session_end_is_idempotent(tmp_path: Path):
    transcript = _transcript_with_tasks(tmp_path)
    stop = {"hook_event_name": "Stop", "transcript_path": str(transcript),
            "session_id": "s"}
    end = {"hook_event_name": "SessionEnd", "transcript_path": str(transcript),
           "session_id": "s"}
    dispatch(stop, tmp_path, now=NOW, emit_task_events=True)
    dispatch(end, tmp_path, now="2026-08-17T12:05:00+00:00", emit_task_events=True)
    # same capture correlation id -> no duplicate task events
    assert [e.event for e in read_events(tmp_path)] == ["task.created", "task.done"]
