from __future__ import annotations

from pathlib import Path

from genesis.diary.backend import FakeBackend
from genesis.diary.compiler import DIARY_PROMPT, compile_diary
from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.ledger.store import append


def _seed(tmp_path: Path):
    e = LedgerEntry(
        entry_id="EP-2026-08-16.0001", ts="2026-08-16T10:00:00+00:00",
        summary="decided on FalkorDB Lite", provenance=Provenance(
            "EP-2026-08-16.0001", "2026-08-16T10:00:00+00:00", "2026-08-16T10:00:00+00:00", ["the principal"]),
        links=Links(session_id="sess-1"), extracted=Extracted.NO,
    )
    append(tmp_path, e)


def test_prompt_is_the_ratified_e5_text():
    assert "You are the Diary Compiler" in DIARY_PROMPT
    assert "An empty input is an empty section" in DIARY_PROMPT
    assert "<inputs>" in DIARY_PROMPT
    assert "keep the [unverified] marker on that item verbatim" in DIARY_PROMPT
    assert "OPEN_QUESTIONS: queued C1/C2 clarifications" in DIARY_PROMPT


def test_compile_returns_briefing_from_the_ledger(tmp_path: Path):
    _seed(tmp_path)
    b = compile_diary(tmp_path, now_iso="2026-08-17T10:00:00+00:00", backend=FakeBackend())
    assert "TOP OF MIND" in b.sections
    assert "FalkorDB Lite" in b.render()
    assert "[unverified]" in b.render()  # entry not extracted


def test_empty_ledger_yields_empty_briefing(tmp_path: Path):
    b = compile_diary(tmp_path, now_iso="2026-08-17T10:00:00+00:00", backend=FakeBackend())
    assert b.sections == {}


def test_budget_is_enforced(tmp_path: Path):
    _seed(tmp_path)
    b = compile_diary(tmp_path, now_iso="2026-08-17T10:00:00+00:00", backend=FakeBackend(), cap_tokens=0)
    # cap 0 drops every droppable section; the seeded data has no commitments/questions
    assert b.sections == {}
