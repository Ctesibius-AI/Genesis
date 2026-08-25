"""Tasks department — urgency-ranked CQRS read-model (spec §4.10, DR-17/DR-18).

A pure, rebuildable projection: fold the event log, compute lazy urgency + effective status,
rank. Never a work queue (PM boundary) and never a source of truth — the event log is.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from genesis.tasks.events import read_events
from genesis.tasks.projection import TaskState, fold_tasks
from genesis.tasks.urgency import effective_status, urgency


@dataclass
class TaskView:
    state: TaskState
    urgency: float
    effective_status: str


def tasks_department(data_root: Path, *, now: str, include_terminal: bool = False) -> list[TaskView]:
    states = fold_tasks(read_events(data_root))
    views = [
        TaskView(state=s, urgency=urgency(s, now), effective_status=effective_status(s, now))
        for s in states.values()
    ]
    if not include_terminal:
        views = [v for v in views if v.effective_status in ("open", "broken")]
    views.sort(key=lambda v: (
        -v.urgency,
        v.state.due is None,
        v.state.due or "",
        v.state.task_id,
    ))
    return views


def by_project(views: list[TaskView]) -> dict[str, list[TaskView]]:
    groups: dict[str, list[TaskView]] = {}
    for v in views:
        key = v.state.project_ref or "(none)"
        groups.setdefault(key, []).append(v)
    return groups
