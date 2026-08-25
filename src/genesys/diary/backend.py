"""Diary synthesis backend (spec App E.2/E.5).

The DiaryBackend turns diary inputs + the ratified E.5 prompt into a sectioned briefing.
FakeBackend is a deterministic, offline stand-in used by every test; the live
Anthropic adapter lives in genesys.diary.anthropic_backend. Sections are delimited by
fixed `## HEADER` lines so downstream budget enforcement can parse them.
"""

from __future__ import annotations

from typing import Protocol

from genesys.diary.inputs import DiaryInputs

SECTION_HEADERS: tuple[str, ...] = (
    "TOP OF MIND", "OPEN THREADS", "COMMITMENTS", "RECENT SESSIONS", "OPEN QUESTIONS",
    "ANCHORS",  # BT-10: code-inserted diary anchors (attached post-synthesis; never LLM-emitted)
)


class DiaryBackend(Protocol):
    def synthesize(self, prompt: str, inputs: DiaryInputs) -> str: ...


class FakeBackend:
    """Deterministic offline backend: echoes each non-empty input group into its section."""

    def synthesize(self, prompt: str, inputs: DiaryInputs) -> str:
        blocks: list[str] = []
        top = [f"- {i.summary}" + (" [unverified]" if i.unverified else "") for i in inputs.ledger]
        if top:
            blocks.append("## TOP OF MIND\n" + "\n".join(top))
        # Open Threads: reuse the ledger lines (a real backend would distil; the fake mirrors).
        if inputs.ledger:
            blocks.append("## OPEN THREADS\n" + "\n".join(f"- {i.summary}" for i in inputs.ledger))
        if inputs.tasks:
            blocks.append("## COMMITMENTS\n" + "\n".join(f"- {t}" for t in inputs.tasks))
        if inputs.ledger:
            sessions = list(reversed(list(dict.fromkeys(i.session_id for i in inputs.ledger if i.session_id))))
            if sessions:
                blocks.append("## RECENT SESSIONS\n" + "\n".join(f"- {s}" for s in sessions))
        if inputs.open_questions:
            blocks.append("## OPEN QUESTIONS\n" + "\n".join(f"- {q}" for q in inputs.open_questions))
        return "\n\n".join(blocks)
