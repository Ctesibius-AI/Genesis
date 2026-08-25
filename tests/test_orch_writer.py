from __future__ import annotations

import pytest

from genesis.orchestration.fleet import SubagentSummary
from genesis.orchestration.writer import (
    assert_daimon,
    commit_findings,
    reject_subagent_write,
)


def test_only_daimon_commits():
    with pytest.raises(PermissionError):
        assert_daimon("Subagent")
    assert_daimon("Daimon")  # ok


def test_commit_findings_applies_only_for_daimon():
    store = []
    summaries = [SubagentSummary(task_id="T1", summary="s", findings=("f1", "f2"))]

    def apply(st, task_id, finding):
        st.append((task_id, finding))

    n = commit_findings(store, summaries, writer="Daimon", apply=apply)
    assert n == 2 and store == [("T1", "f1"), ("T1", "f2")]

    with pytest.raises(PermissionError):
        commit_findings(store, summaries, writer="Subagent", apply=apply)


def test_reject_subagent_write():
    with pytest.raises(PermissionError):
        reject_subagent_write("TeamManager")
    reject_subagent_write("Daimon")  # ok
