"""Task-event emitters (spec §4.10). Write-through helpers over the event store; the
department is derived. Time is injected via `ts` — no wall-clock here.
"""

from __future__ import annotations

from pathlib import Path

from genesys.tasks.events import TaskEvent, append_event, new_task_id


def record_created(data_root: Path, *, ts: str, source_episode: str, title: str,
                   kind: str = "task", due: str | None = None, recipient: str | None = None,
                   project_ref: str | None = None, task_id: str | None = None) -> str:
    tid = task_id or new_task_id(data_root, ts[:10])
    append_event(data_root, TaskEvent(ts=ts, event="task.created", task_id=tid,
                                      source_episode=source_episode, title=title, kind=kind,
                                      due=due, recipient=recipient, project_ref=project_ref))
    return tid


def record_due_moved(data_root: Path, *, ts: str, task_id: str, due: str,
                     source_episode: str) -> None:
    append_event(data_root, TaskEvent(ts=ts, event="task.due_moved", task_id=task_id,
                                      source_episode=source_episode, due=due))


def record_done(data_root: Path, *, ts: str, task_id: str, source_episode: str) -> None:
    append_event(data_root, TaskEvent(ts=ts, event="task.done", task_id=task_id,
                                      source_episode=source_episode))


def record_cancelled(data_root: Path, *, ts: str, task_id: str, source_episode: str) -> None:
    append_event(data_root, TaskEvent(ts=ts, event="task.cancelled", task_id=task_id,
                                      source_episode=source_episode))
