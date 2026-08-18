"""Fleet model (spec §4.13, DR-12/DR-13).

Daimon → Team Manager → subagents → ephemeral scratch. A subagent's only upward product is an
immutable `SubagentSummary` (the lead sees only this, DR-12); it carries no write handle, so a
subagent cannot write to the durable spine (DR-13 — Daimon is the sole durable writer).
"""

from __future__ import annotations

from dataclasses import dataclass, field

DAIMON = "Daimon"
ROLES = ("Daimon", "TeamManager", "Subagent")

_WRITE_HANDLES = ("add", "append", "write_superseded_by", "add_observation")


@dataclass
class SubagentTask:
    task_id: str
    role: str
    instruction: str
    context: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError(f"unknown fleet role: {self.role!r}")
        if self.role == DAIMON:
            raise ValueError("Daimon is the orchestrator, not a subagent target")


@dataclass(frozen=True)
class SubagentSummary:
    task_id: str
    summary: str
    findings: tuple[str, ...] = ()


def is_write_bearing(obj: object) -> bool:
    return any(callable(getattr(obj, h, None)) for h in _WRITE_HANDLES)
