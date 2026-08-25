"""BT-8 / AC-CONF1 / D-GCW-18: the session-start memory-load confirmation line (D-GCW-15).

Four states — loaded (+count) / unsaved / empty / unavailable. Literalism: "unavailable" is reachable
ONLY from a real failed memory read; and (D-GCW-18) it must NOT say "no memories" when the WAL holds
captured-but-unsaved content.
"""
from __future__ import annotations

from pathlib import Path

from genesys.diary.backend import FakeBackend
from genesys.hooks import adapter as adapter_mod
from genesys.hooks.adapter import dispatch
from genesys.hooks.confirmation import (
    EMPTY, UNAVAILABLE, UNSAVED, MemoryState, confirmation_line, memory_state)
from genesys.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesys.ledger.store import append
from genesys.wal.record import WalRecord
from genesys.wal.store import append_delta

NOW = "2026-08-26T10:00:00+00:00"
START = {"hook_event_name": "SessionStart"}


def _seed(root: Path, eid, sid):
    append(root, LedgerEntry(entry_id=eid, ts=NOW, summary="s",
           provenance=Provenance(eid, "", "", ["the principal"]),
           links=Links(session_id=sid), extracted=Extracted.DONE))


def _seed_wal(root: Path):
    append_delta(root, WalRecord.MEMORY_GRADE, ts=NOW, span_start="", span_end=NOW,
                 session_id="sess-x", text="captured but unsaved content")


# --- the pure line ---

def test_line_four_states():
    assert confirmation_line(MemoryState(False, 9, False)) == UNAVAILABLE  # down beats any count
    assert confirmation_line(MemoryState(True, 0, True)) == UNSAVED        # D-GCW-18
    assert confirmation_line(MemoryState(True, 0, False)) == EMPTY
    assert "3 recent sessions" in confirmation_line(MemoryState(True, 3, False))


def test_memory_state_counts_distinct_sessions(tmp_path):
    assert memory_state(tmp_path) == MemoryState(True, 0, False)  # empty + readable
    _seed(tmp_path, "EP-1", "sess-a")
    _seed(tmp_path, "EP-2", "sess-a")
    _seed(tmp_path, "EP-3", "sess-b")
    st = memory_state(tmp_path)
    assert st.available and st.sessions == 2 and not st.unsaved   # two distinct sessions


def test_unsaved_wal_is_not_no_memories(tmp_path):
    # D-GCW-18: WAL captured but nothing in the ledger → "unsaved", never EMPTY.
    _seed_wal(tmp_path)
    st = memory_state(tmp_path)
    assert st.sessions == 0 and st.unsaved is True
    assert confirmation_line(st) == UNSAVED


# --- wired into SessionStart: user-visible via `systemMessage`; diary model-only ---
# systemMessage is the field CC shows the user at SessionStart (v2.1.158, CLI). additionalContext
# stays model-only. (⚠ CC bug #15344: the VS Code extension ignores SessionStart systemMessage.)

def test_sessionstart_emits_empty_when_no_memories(tmp_path):
    out = dispatch(START, tmp_path, now=NOW, backend=FakeBackend())
    assert out["systemMessage"] == EMPTY
    assert "additionalContext" in out["hookSpecificOutput"]  # diary stays model-only


def test_sessionstart_emits_loaded_with_count(tmp_path):
    _seed(tmp_path, "EP-1", "sess-a")
    _seed(tmp_path, "EP-2", "sess-b")
    out = dispatch(START, tmp_path, now=NOW, backend=FakeBackend())
    assert "2 recent sessions" in out["systemMessage"]


def test_unavailable_only_from_real_down_path(tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("diary/recall down")
    monkeypatch.setattr(adapter_mod, "session_start_context", _boom)
    out = dispatch(START, tmp_path, now=NOW, backend=FakeBackend())
    assert out["systemMessage"] == UNAVAILABLE               # reached ONLY via the failed read
    assert out["hookSpecificOutput"]["additionalContext"] == ""  # never breaks start


def test_cli_output_is_pure_json_carrying_systemMessage(tmp_path, monkeypatch, capsys):
    import io
    import json as _json

    from genesys.hooks import cli
    monkeypatch.setenv("GENESYS_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("GENESYS_NOW", NOW)
    monkeypatch.setattr("sys.stdin", io.StringIO(_json.dumps({"hook_event_name": "SessionStart"})))
    assert cli.main([]) == 0
    payload = _json.loads(capsys.readouterr().out)           # whole stdout is valid JSON (no leading line)
    assert payload["systemMessage"].startswith("Genesys:")   # user-visible line rides systemMessage
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
