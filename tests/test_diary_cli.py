from __future__ import annotations

from pathlib import Path

from genesis.config import DIARY_TOKEN_BUDGET, DIARY_WINDOW_DAYS, RECENT_SESSIONS_DEPTH
from genesis.diary.cli import main
from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.ledger.store import append


def _seed(data: Path):
    append(data, LedgerEntry(
        entry_id="EP-2026-08-16.0001", ts="2026-08-16T10:00:00+00:00", summary="a thing",
        provenance=Provenance("EP-2026-08-16.0001", "2026-08-16T10:00:00+00:00",
                              "2026-08-16T10:00:00+00:00", ["the principal"]),
        links=Links(session_id="sess-1"), extracted=Extracted.NO))


def test_defaults_match_the_ratified_values():
    assert DIARY_WINDOW_DAYS == 6
    assert DIARY_TOKEN_BUDGET == 4000
    assert RECENT_SESSIONS_DEPTH == 3


def test_cli_compile_prints_briefing(tmp_path: Path, capsys):
    data = tmp_path / "data"; data.mkdir()
    _seed(data)
    rc = main(["compile", "--data", str(data), "--now", "2026-08-17T10:00:00+00:00"])
    assert rc == 0
    assert "a thing" in capsys.readouterr().out


def test_cli_inject_prints_context(tmp_path: Path, capsys):
    data = tmp_path / "data"; data.mkdir()
    _seed(data)
    rc = main(["inject", "--data", str(data), "--now", "2026-08-17T10:00:00+00:00"])
    assert rc == 0
    assert "a thing" in capsys.readouterr().out
