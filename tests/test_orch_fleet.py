from __future__ import annotations

import dataclasses

import pytest

from genesis.orchestration.fleet import (
    DAIMON,
    SubagentSummary,
    SubagentTask,
    is_write_bearing,
)


def test_task_rejects_daimon_and_unknown_role():
    with pytest.raises(ValueError):
        SubagentTask(task_id="T1", role="Daimon", instruction="do")   # Daimon is not a subagent
    with pytest.raises(ValueError):
        SubagentTask(task_id="T1", role="Wizard", instruction="do")   # unknown role
    SubagentTask(task_id="T1", role="Subagent", instruction="do")     # ok


def test_summary_is_frozen_and_not_write_bearing():
    s = SubagentSummary(task_id="T1", summary="did the thing", findings=("f1",))
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.summary = "tampered"  # immutable upward product
    assert is_write_bearing(s) is False  # a summary cannot write (DR-13)


def test_is_write_bearing_detects_stores():
    class FakeStore:
        def add(self, x): ...
    assert is_write_bearing(FakeStore()) is True
    assert is_write_bearing("just text") is False
