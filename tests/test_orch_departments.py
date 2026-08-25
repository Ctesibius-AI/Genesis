"""Tests for the department-store abstraction + run_fleet facade."""

from __future__ import annotations

import pytest

from genesis.orchestration.departments import ListDepartmentStore, run_fleet
from genesis.orchestration.fleet import SubagentSummary, SubagentTask
from genesis.orchestration.orchestrator import FakeOrchestrator


def _tasks(n):
    return [SubagentTask(task_id=f"T{i}", role="Subagent", instruction=f"do {i}") for i in range(n)]


def test_run_fleet_commits_findings_as_daimon():
    orch = FakeOrchestrator()
    orch.set("T0", SubagentSummary(task_id="T0", summary="s", findings=("f-a", "f-b")))
    store = ListDepartmentStore()
    summaries, applied = run_fleet(orch, _tasks(1), store)
    assert applied == 2
    assert store.records == [("T0", "f-a"), ("T0", "f-b")]
    assert [s.task_id for s in summaries] == ["T0"]


def test_run_fleet_subagent_writer_is_rejected():
    orch = FakeOrchestrator()
    store = ListDepartmentStore()
    with pytest.raises(PermissionError):
        run_fleet(orch, _tasks(1), store, writer="Subagent")  # DR-13: only Daimon writes


def test_ephemeral_fan_out_then_single_durable_write():
    orch = FakeOrchestrator()
    for i in range(3):
        orch.set(f"T{i}", SubagentSummary(task_id=f"T{i}", summary="s", findings=(f"f{i}",)))
    store = ListDepartmentStore()
    summaries, applied = run_fleet(orch, _tasks(3), store)
    assert applied == 3 and len(summaries) == 3
    assert store.records == [("T0", "f0"), ("T1", "f1"), ("T2", "f2")]
