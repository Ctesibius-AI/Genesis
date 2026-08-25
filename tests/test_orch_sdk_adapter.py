# tests/test_orch_sdk_adapter.py
"""The real orchestration-backend seam (spec §4.13, DR-12/DR-13).

Two live SDKs sit behind lazy factories (`agent_sdk_orchestrator` primary, `langgraph_orchestrator`
fallback) that the offline sandbox never reaches — offline drives `FakeOrchestrator`. The
SDK-decoupled adapter (`SdkOrchestrator`) is offline-testable: inject a fake per-task run callable
returning canned subagent results (no network). These tests prove:
  - protocol conformance (`dispatch(task) -> SubagentSummary`, so `fan_out`/`run_fleet` accept it),
  - the summary-only / no-write invariant (a returned summary never carries a write handle, DR-12/13),
  - the raw-result -> immutable SubagentSummary shaping (summary + findings), and
  - the lazy real bindings raise RuntimeError when their SDK is absent (offline-unreachable).
"""
from __future__ import annotations

import sys

import pytest

from genesis.orchestration.backends import (
    SdkOrchestrator,
    agent_sdk_orchestrator,
    langgraph_orchestrator,
    select_orchestrator,
)
from genesis.orchestration.fleet import SubagentSummary, SubagentTask, is_write_bearing
from genesis.orchestration.orchestrator import Orchestrator, fan_out
from genesis.orchestration.writer import commit_findings


def _task(i, role="Subagent"):
    return SubagentTask(task_id=f"T{i}", role=role, instruction=f"do {i}", context={"n": i})


class _FakeSubagentRun:
    """Records the tasks it ran; returns scripted raw subagent results per task_id.

    A raw result is whatever the live SDK hands back for one ephemeral subagent — here a dict
    with a final `summary` string and optional `findings`. No network, no SDK import.
    """

    def __init__(self):
        self.ran: list[SubagentTask] = []
        self._results: dict[str, object] = {}

    def set(self, task_id: str, result: object) -> None:
        self._results[task_id] = result

    def __call__(self, task: SubagentTask) -> object:
        self.ran.append(task)
        return self._results.get(task.task_id, {"summary": "done"})


# --------------------------------------------------------------------------------------
# SdkOrchestrator — the SDK-decoupled adapter, offline-testable via an injected run callable.
# --------------------------------------------------------------------------------------


def test_adapter_satisfies_orchestrator_protocol():
    orch: Orchestrator = SdkOrchestrator(_FakeSubagentRun())
    assert hasattr(orch, "dispatch")
    summary = orch.dispatch(_task(1))
    assert isinstance(summary, SubagentSummary)


def test_dispatch_runs_the_subagent_and_shapes_the_summary():
    run = _FakeSubagentRun()
    run.set("T1", {"summary": "analysed the invoice", "findings": ["PHR008 is next", "May was PHR007"]})
    out = SdkOrchestrator(run).dispatch(_task(1))
    assert out.task_id == "T1"
    assert out.summary == "analysed the invoice"
    assert out.findings == ("PHR008 is next", "May was PHR007")
    # the adapter actually ran the task through the SDK run callable
    assert [t.task_id for t in run.ran] == ["T1"]


def test_dispatch_defaults_findings_to_empty_when_absent():
    run = _FakeSubagentRun()
    run.set("T1", {"summary": "only a summary"})
    out = SdkOrchestrator(run).dispatch(_task(1))
    assert out.summary == "only a summary"
    assert out.findings == ()


def test_dispatch_accepts_a_subagentsummary_result_passthrough():
    """A run callable that already returns a SubagentSummary is normalised (task_id enforced)."""
    run = _FakeSubagentRun()
    run.set("T1", SubagentSummary(task_id="T1", summary="native", findings=("f",)))
    out = SdkOrchestrator(run).dispatch(_task(1))
    assert isinstance(out, SubagentSummary)
    assert out.summary == "native" and out.findings == ("f",)


def test_dispatch_accepts_a_plain_string_result():
    run = _FakeSubagentRun()
    run.set("T1", "just text")
    out = SdkOrchestrator(run).dispatch(_task(1))
    assert out.task_id == "T1" and out.summary == "just text" and out.findings == ()


def test_returned_summary_is_never_write_bearing():
    """DR-12/13: a subagent summary carries no durable-write handle back to the lead."""
    run = _FakeSubagentRun()
    run.set("T1", {"summary": "s", "findings": ["x"]})
    out = SdkOrchestrator(run).dispatch(_task(1))
    assert not is_write_bearing(out)


def test_adapter_composes_with_fan_out_summaries_only():
    run = _FakeSubagentRun()
    run.set("T1", {"summary": "a", "findings": ["fa"]})
    run.set("T2", {"summary": "b"})
    summaries = fan_out(SdkOrchestrator(run), [_task(1), _task(2)])
    assert [s.task_id for s in summaries] == ["T1", "T2"]
    assert all(isinstance(s, SubagentSummary) for s in summaries)  # only summaries surface (DR-12)


def test_adapter_findings_reach_the_store_only_through_daimon():
    """End-to-end DR-13: subagent findings become durable ONLY via Daimon's commit path."""
    run = _FakeSubagentRun()
    run.set("T1", {"summary": "s", "findings": ["one", "two"]})
    summaries = fan_out(SdkOrchestrator(run), [_task(1)])
    records: list[tuple[str, str]] = []
    applied = commit_findings(
        object(), summaries, writer="Daimon",
        apply=lambda st, tid, f: records.append((tid, f)),
    )
    assert applied == 2
    assert records == [("T1", "one"), ("T1", "two")]
    # a non-Daimon writer is refused
    with pytest.raises(PermissionError):
        commit_findings(object(), summaries, writer="Subagent", apply=lambda *a: None)


# --------------------------------------------------------------------------------------
# Lazy real bindings — offline-unreachable; absent SDK -> RuntimeError (like real_client).
# --------------------------------------------------------------------------------------


def test_agent_sdk_binding_needs_the_extra_offline():
    with pytest.raises(RuntimeError):
        agent_sdk_orchestrator()


def test_langgraph_binding_needs_the_extra_offline():
    with pytest.raises(RuntimeError):
        langgraph_orchestrator()


def test_backends_module_does_not_import_any_sdk_at_top_level():
    import genesis.orchestration.backends  # noqa: F401
    assert "claude_agent_sdk" not in sys.modules
    assert "langgraph" not in sys.modules


def test_select_falls_back_to_langgraph_then_raises_offline():
    # offline: both SDKs absent -> agent-sdk RuntimeError -> langgraph RuntimeError -> combined raise
    with pytest.raises(RuntimeError) as ei:
        select_orchestrator()
    assert "no orchestration backend" in str(ei.value)


def test_select_returns_a_conforming_orchestrator_when_a_backend_is_present(monkeypatch):
    """When agent-sdk resolves, select_orchestrator hands back an Orchestrator (not a raise)."""
    import genesis.orchestration.backends as b

    sentinel = SdkOrchestrator(_FakeSubagentRun())
    monkeypatch.setattr(b, "agent_sdk_orchestrator", lambda *, model=None: sentinel)
    got = b.select_orchestrator(prefer="agent-sdk")
    assert got is sentinel
    assert isinstance(got.dispatch(_task(1)), SubagentSummary)
