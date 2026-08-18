"""Orchestrator contract + fan-out (spec §4.13, DR-12/DR-13).

`dispatch` runs one subagent and returns its final summary; the ephemeral scratch is discarded.
`fan_out` runs a batch in one session and returns ONLY the summaries — the lead never sees
scratch (DR-12), and fan-out is unlimited within the session (DR-13).
"""

from __future__ import annotations

from typing import Protocol

from genesys.orchestration.fleet import SubagentSummary, SubagentTask


class Orchestrator(Protocol):
    def dispatch(self, task: SubagentTask) -> SubagentSummary: ...


class FakeOrchestrator:
    def __init__(self, *, summaries: dict[str, SubagentSummary] | None = None,
                 default_summary: str = "done") -> None:
        self._summaries = dict(summaries or {})
        self._default = default_summary
        self.dispatched: list[str] = []

    def set(self, task_id: str, summary: SubagentSummary) -> None:
        self._summaries[task_id] = summary

    def dispatch(self, task: SubagentTask) -> SubagentSummary:
        self.dispatched.append(task.task_id)
        return self._summaries.get(task.task_id,
                                   SubagentSummary(task_id=task.task_id, summary=self._default))


def fan_out(orchestrator: Orchestrator, tasks: list[SubagentTask]) -> list[SubagentSummary]:
    return [orchestrator.dispatch(t) for t in tasks]
