"""Sole-durable-writer enforcement (spec §4.13/§4.14, DR-13).

Daimon is the sole durable writer. Subagents return findings and never write; the only path
from a subagent summary to a durable store is `commit_findings`, gated on writer == Daimon.
"""

from __future__ import annotations

from genesys.orchestration.fleet import DAIMON, SubagentSummary, is_write_bearing


def assert_daimon(writer: str) -> None:
    if writer != DAIMON:
        raise PermissionError(f"only Daimon is the durable writer (DR-13); got {writer!r}")


def reject_subagent_write(actor: str) -> None:
    if actor != DAIMON:
        raise PermissionError(f"subagents never write the durable spine (DR-13); actor={actor!r}")


def commit_findings(store, summaries: list[SubagentSummary], *, writer: str, apply) -> int:
    assert_daimon(writer)
    applied = 0
    for summary in summaries:
        if is_write_bearing(summary):  # defensive: a summary must never carry a store handle
            raise TypeError("a SubagentSummary must not be write-bearing (DR-12/13)")
        for finding in summary.findings:
            apply(store, summary.task_id, finding)
            applied += 1
    return applied
