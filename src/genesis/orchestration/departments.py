"""Department-store abstraction + run_fleet facade (spec §4.13, DR-12/13).

Persistent department stores are Daimon's durable substrate; ephemeral subagents have none.
`run_fleet` fans out (subagents → summaries, DR-12), then Daimon — and only Daimon — commits the
findings to the durable store (DR-13).
"""

from __future__ import annotations

from typing import Protocol

from genesis.orchestration.fleet import DAIMON, SubagentTask
from genesis.orchestration.orchestrator import Orchestrator, fan_out
from genesis.orchestration.writer import commit_findings


class DepartmentStore(Protocol):
    def apply_finding(self, task_id: str, finding: str) -> None: ...


class ListDepartmentStore:
    def __init__(self) -> None:
        self.records: list[tuple[str, str]] = []

    def apply_finding(self, task_id: str, finding: str) -> None:
        self.records.append((task_id, finding))


def run_fleet(orchestrator: Orchestrator, tasks: list[SubagentTask], store: DepartmentStore, *,
              writer: str = DAIMON):
    summaries = fan_out(orchestrator, tasks)
    applied = commit_findings(store, summaries, writer=writer,
                              apply=lambda st, tid, f: st.apply_finding(tid, f))
    return summaries, applied
