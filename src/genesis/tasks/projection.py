"""Fold task events into current TaskState (spec §4.10, DR-17).

Pure, rebuildable projection over the append-only event log. Terminal statuses
(fulfilled/cancelled) are sticky; a later due_moved still tracks `due` but never reopens.
"""

from __future__ import annotations

from dataclasses import dataclass

from genesis.tasks.events import TaskEvent


@dataclass
class TaskState:
    task_id: str
    title: str
    kind: str
    status: str
    project_ref: str | None
    due: str | None
    recipient: str | None
    source_episode: str
    created_ts: str
    last_ts: str


def fold_tasks(events: list[TaskEvent]) -> dict[str, TaskState]:
    states: dict[str, TaskState] = {}
    for e in events:
        st = states.get(e.task_id)
        if e.event == "task.created":
            if st is None:
                states[e.task_id] = TaskState(
                    task_id=e.task_id, title=e.title, kind=e.kind, status="open",
                    project_ref=e.project_ref, due=e.due, recipient=e.recipient,
                    source_episode=e.source_episode, created_ts=e.ts, last_ts=e.ts,
                )
            else:  # re-created id: refresh mutable fields, keep status
                st.title = e.title or st.title
                st.due = e.due if e.due is not None else st.due
                st.last_ts = e.ts
            continue
        if st is None:
            continue  # orphan event on an unknown task — ignore defensively
        if e.event == "task.due_moved":
            st.due = e.due
        elif e.event == "task.done":
            st.status = "fulfilled"
        elif e.event == "task.cancelled":
            st.status = "cancelled"
        st.last_ts = e.ts
    return states
