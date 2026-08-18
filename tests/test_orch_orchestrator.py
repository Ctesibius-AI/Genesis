from __future__ import annotations

from genesys.orchestration.fleet import SubagentSummary, SubagentTask
from genesys.orchestration.orchestrator import FakeOrchestrator, fan_out


def _task(i):
    return SubagentTask(task_id=f"T{i}", role="Subagent", instruction=f"do {i}")


def test_fan_out_returns_summaries_in_order():
    orch = FakeOrchestrator()
    orch.set("T1", SubagentSummary(task_id="T1", summary="alpha", findings=("a",)))
    summaries = fan_out(orch, [_task(1), _task(2)])
    assert [s.task_id for s in summaries] == ["T1", "T2"]
    assert summaries[0].summary == "alpha" and summaries[1].summary == "done"  # default


def test_fan_out_is_summaries_only_no_scratch():
    orch = FakeOrchestrator()
    out = fan_out(orch, [_task(1)])
    assert all(isinstance(s, SubagentSummary) for s in out)  # only summaries surface (DR-12)


def test_unlimited_fan_out_one_session():
    orch = FakeOrchestrator()
    out = fan_out(orch, [_task(i) for i in range(50)])
    assert len(out) == 50 and len(orch.dispatched) == 50  # one session, many subagents (DR-13)
