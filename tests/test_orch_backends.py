from __future__ import annotations

import pytest

from genesis.orchestration.backends import (
    agent_sdk_orchestrator,
    langgraph_orchestrator,
    select_orchestrator,
)


def test_agent_sdk_is_lazy_stub():
    with pytest.raises((RuntimeError, NotImplementedError)):
        agent_sdk_orchestrator()


def test_langgraph_is_lazy_stub():
    with pytest.raises((RuntimeError, NotImplementedError)):
        langgraph_orchestrator()


def test_select_falls_back_then_raises_offline():
    # offline: both deps absent → RuntimeError naming both (caller uses FakeOrchestrator)
    with pytest.raises(RuntimeError):
        select_orchestrator()


def test_backends_module_imports_without_deps():
    import genesis.orchestration.backends as b  # must import stdlib-only
    assert hasattr(b, "select_orchestrator")


def test_select_propagates_not_implemented(monkeypatch):
    """When a factory raises NotImplementedError (deps present, wiring stubbed),
    select_orchestrator must propagate it, not fall back (F-1 regression)."""
    import genesis.orchestration.backends as b

    def stubbed(*, model=None):
        raise NotImplementedError("wiring stubbed")

    monkeypatch.setattr(b, "agent_sdk_orchestrator", stubbed)
    with pytest.raises(NotImplementedError):
        b.select_orchestrator(prefer="agent-sdk")
