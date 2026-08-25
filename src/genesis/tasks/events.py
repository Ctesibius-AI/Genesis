"""Append-only task-event store (spec §4.10, App A.4.4, DR-17).

Truth for tasks is this event log; the Tasks department is a fold over it. Events are
append-only and never mutated (DR-17). The record shape is LOCKED (A.4.4).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

TASK_EVENTS = frozenset({"task.created", "task.due_moved", "task.done", "task.cancelled"})


@dataclass
class TaskEvent:
    ts: str
    event: str
    task_id: str
    source_episode: str
    project_ref: str | None = None
    kind: str = "task"
    title: str = ""
    due: str | None = None
    recipient: str | None = None

    def __post_init__(self) -> None:
        if self.event not in TASK_EVENTS:
            raise ValueError(f"unknown task event: {self.event!r}")


def to_jsonl(e: TaskEvent) -> str:
    return json.dumps(asdict(e), ensure_ascii=False, separators=(",", ":"))


def from_jsonl(line: str) -> TaskEvent:
    d = json.loads(line)
    return TaskEvent(**d)


def events_path(data_root: Path) -> Path:
    return data_root / "tasks" / "events.jsonl"


def append_event(data_root: Path, e: TaskEvent) -> Path:
    path = events_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(to_jsonl(e) + "\n")
    return path


def read_events(data_root: Path) -> list[TaskEvent]:
    path = events_path(data_root)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [from_jsonl(line) for line in f if line.strip()]


def new_task_id(data_root: Path, date: str) -> str:
    n = sum(1 for e in read_events(data_root)
            if e.event == "task.created" and e.task_id.startswith(f"TS-{date}."))
    return f"TS-{date}.{n:04d}"
