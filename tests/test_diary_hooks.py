from __future__ import annotations

from pathlib import Path

from genesis.diary.backend import DiaryBackend, FakeBackend
from genesis.diary.hooks import precompact_flush, session_start_context
from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.ledger.store import append, read_all


def _seed(tmp_path: Path):
    append(tmp_path, LedgerEntry(
        entry_id="EP-2026-08-16.0001", ts="2026-08-16T10:00:00+00:00", summary="a thing",
        provenance=Provenance("EP-2026-08-16.0001", "2026-08-16T10:00:00+00:00",
                              "2026-08-16T10:00:00+00:00", ["the principal"]),
        links=Links(session_id="sess-1"), extracted=Extracted.NO))


def _save_kw():
    return dict(
        raw_span="the principal: unsaved discussion before compaction.",
        summary="pre-compaction flush", session_id="sess-1", speakers=["the principal"],
        span_start="2026-08-17T09:59:00+00:00", span_end="2026-08-17T10:00:00+00:00",
        ts="2026-08-17T10:00:00+00:00",
    )


def test_session_start_context_returns_briefing_text(tmp_path: Path):
    _seed(tmp_path)
    ctx = session_start_context(tmp_path, now_iso="2026-08-17T10:00:00+00:00", backend=FakeBackend())
    assert "a thing" in ctx


def test_session_start_context_empty_when_no_ledger(tmp_path: Path):
    assert session_start_context(tmp_path, now_iso="2026-08-17T10:00:00+00:00", backend=FakeBackend()) == ""


def test_precompact_flush_persists_durably_even_without_backend(tmp_path: Path):
    res = precompact_flush(tmp_path, backend=None, **_save_kw())
    assert res["entry_id"].startswith("EP-2026-08-17.")
    assert res["diary_regenerated"] is False
    assert any(e.entry_id == res["entry_id"] for e in read_all(tmp_path))  # durable part happened


def test_precompact_flush_durability_survives_a_failing_diary_backend(tmp_path: Path):
    class Boom:  # a backend whose synth explodes — must NOT break the durable flush
        def synthesize(self, prompt: str, inputs) -> str:
            raise RuntimeError("diary backend down")
    res = precompact_flush(tmp_path, backend=Boom(), **_save_kw())
    assert any(e.entry_id == res["entry_id"] for e in read_all(tmp_path))  # save still committed
    assert res["diary_regenerated"] is False  # best-effort diary failed, silently
