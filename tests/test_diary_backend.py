from __future__ import annotations

from genesys.diary.backend import SECTION_HEADERS, FakeBackend
from genesys.diary.inputs import DiaryInputs, LedgerItem


def test_headers_are_the_five_fixed_sections_in_order():
    assert SECTION_HEADERS == (
        "TOP OF MIND", "OPEN THREADS", "COMMITMENTS", "RECENT SESSIONS", "OPEN QUESTIONS",
    )


def test_fake_backend_emits_only_nonempty_sections():
    di = DiaryInputs(
        ledger=[LedgerItem("2026-08-16T10:00:00+00:00", "did a thing", False, "sess-1")],
        tasks=[], open_questions=[],
    )
    out = FakeBackend().synthesize("PROMPT", di)
    assert "## TOP OF MIND" in out
    assert "did a thing" in out
    assert "## COMMITMENTS" not in out      # empty tasks -> omitted
    assert "## OPEN QUESTIONS" not in out    # empty questions -> omitted


def test_fake_backend_preserves_unverified_marker():
    di = DiaryInputs(
        ledger=[LedgerItem("2026-08-16T10:00:00+00:00", "queued note", True, "sess-1")],
        tasks=[], open_questions=[],
    )
    out = FakeBackend().synthesize("PROMPT", di)
    assert "[unverified]" in out


def test_open_threads_emitted_when_ledger_nonempty():
    di = DiaryInputs(
        ledger=[LedgerItem("2026-08-16T10:00:00+00:00", "thread topic", False, "sess-1")],
        tasks=[], open_questions=[],
    )
    out = FakeBackend().synthesize("PROMPT", di)
    assert "## OPEN THREADS" in out


def test_recent_sessions_newest_first():
    di = DiaryInputs(
        ledger=[
            LedgerItem("2026-08-16T10:00:00+00:00", "older entry", False, "sess-1"),
            LedgerItem("2026-08-16T11:00:00+00:00", "newer entry", False, "sess-2"),
        ],
        tasks=[], open_questions=[],
    )
    out = FakeBackend().synthesize("PROMPT", di)
    assert "## RECENT SESSIONS" in out
    # sess-2 (newer) should appear before sess-1 (older)
    pos_sess2 = out.find("sess-2")
    pos_sess1 = out.find("sess-1")
    assert pos_sess2 < pos_sess1 and pos_sess2 > 0
