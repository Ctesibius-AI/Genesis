"""Test tasks department (tests/test_tasks_department.py)."""
from __future__ import annotations

from genesis.tasks.events import TaskEvent, append_event
from genesis.tasks.department import by_project, tasks_department


def _seed(tmp_path, tid, *, due=None, kind="task", project=None, done=False, created_ts="2026-08-01T00:00:00Z"):
    append_event(tmp_path, TaskEvent(ts=created_ts, event="task.created", task_id=tid,
                                     source_episode="EP-1", due=due, kind=kind,
                                     title=tid, project_ref=project))
    if done:
        append_event(tmp_path, TaskEvent(ts="2026-08-05T00:00:00Z", event="task.done",
                                         task_id=tid, source_episode="EP-2"))


NOW = "2026-08-17T00:00:00Z"


def test_ranked_by_urgency_desc(tmp_path):
    _seed(tmp_path, "TS-far", due="2026-08-27")       # 10 days → low
    _seed(tmp_path, "TS-over", due="2026-08-10", kind="commitment")  # overdue → top
    _seed(tmp_path, "TS-near", due="2026-08-18")      # 1 day → mid
    views = tasks_department(tmp_path, now=NOW)
    assert [v.state.task_id for v in views] == ["TS-over", "TS-near", "TS-far"]
    assert views[0].effective_status == "broken"


def test_terminal_excluded_by_default(tmp_path):
    _seed(tmp_path, "TS-1", due="2026-08-18")
    _seed(tmp_path, "TS-2", due="2026-08-18", done=True)
    ids = [v.state.task_id for v in tasks_department(tmp_path, now=NOW)]
    assert ids == ["TS-1"]
    all_ids = {v.state.task_id for v in tasks_department(tmp_path, now=NOW, include_terminal=True)}
    assert all_ids == {"TS-1", "TS-2"}


def test_by_project_groups_belongs_to(tmp_path):
    _seed(tmp_path, "TS-1", due="2026-08-18", project="PR-A")
    _seed(tmp_path, "TS-2", due="2026-08-19", project=None)
    groups = by_project(tasks_department(tmp_path, now=NOW))
    assert set(groups) == {"PR-A", "(none)"}
    assert [v.state.task_id for v in groups["PR-A"]] == ["TS-1"]


def test_rebuildable_is_pure(tmp_path):
    _seed(tmp_path, "TS-1", due="2026-08-18")
    a = tasks_department(tmp_path, now=NOW)
    b = tasks_department(tmp_path, now=NOW)
    assert [v.state.task_id for v in a] == [v.state.task_id for v in b]
