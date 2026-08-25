"""BT-8 / AC-CONF1: the session-start memory-load confirmation line (D-GCW-15).

Three states — loaded (+count) / empty / unavailable — and the literalism guard: "unavailable" is
reachable ONLY from a real failed memory read, never hardcoded on the happy path.
"""
from __future__ import annotations

from pathlib import Path

from genesys.diary.backend import FakeBackend
from genesys.hooks import adapter as adapter_mod
from genesys.hooks.adapter import dispatch
from genesys.hooks.confirmation import EMPTY, UNAVAILABLE, confirmation_line, memory_state
from genesys.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesys.ledger.store import append

NOW = "2026-08-26T10:00:00+00:00"
START = {"hook_event_name": "SessionStart"}


def _seed(root: Path, eid, sid):
    append(root, LedgerEntry(entry_id=eid, ts=NOW, summary="s",
           provenance=Provenance(eid, "", "", ["the principal"]),
           links=Links(session_id=sid), extracted=Extracted.DONE))


# --- the pure line ---

def test_line_three_states():
    assert confirmation_line(available=False, count=9) == UNAVAILABLE  # down beats any count
    assert confirmation_line(available=True, count=0) == EMPTY
    assert "3 recent sessions" in confirmation_line(available=True, count=3)


def test_memory_state_counts_distinct_sessions(tmp_path):
    assert memory_state(tmp_path) == (True, 0)          # empty graph, but READABLE (not down)
    _seed(tmp_path, "EP-1", "sess-a")
    _seed(tmp_path, "EP-2", "sess-a")
    _seed(tmp_path, "EP-3", "sess-b")
    available, count = memory_state(tmp_path)
    assert available is True and count == 2               # two distinct sessions


# --- wired into SessionStart (user-visible via plain stdout; diary model-only) ---

def test_sessionstart_emits_empty_when_no_memories(tmp_path):
    out = dispatch(START, tmp_path, now=NOW, backend=FakeBackend())
    # AC-CONF1: the user-visible line rides _confirmation_stdout (cli.py prints it to plain stdout);
    # the diary stays model-only in additionalContext; never the model-only systemMessage.
    assert out["_confirmation_stdout"] == EMPTY
    assert "additionalContext" in out["hookSpecificOutput"]
    assert "systemMessage" not in out


def test_sessionstart_emits_loaded_with_count(tmp_path):
    _seed(tmp_path, "EP-1", "sess-a")
    _seed(tmp_path, "EP-2", "sess-b")
    out = dispatch(START, tmp_path, now=NOW, backend=FakeBackend())
    assert "2 recent sessions" in out["_confirmation_stdout"]


def test_unavailable_only_from_real_down_path(tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("diary/recall down")
    monkeypatch.setattr(adapter_mod, "session_start_context", _boom)
    out = dispatch(START, tmp_path, now=NOW, backend=FakeBackend())
    assert out["_confirmation_stdout"] == UNAVAILABLE     # reached ONLY via the failed read
    assert out["hookSpecificOutput"]["additionalContext"] == ""  # never breaks start


def test_cli_prints_confirmation_to_plain_stdout(tmp_path, monkeypatch, capsys):
    import io
    import json as _json

    from genesys.hooks import cli
    monkeypatch.setenv("GENESYS_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("GENESYS_NOW", NOW)
    monkeypatch.setattr("sys.stdin", io.StringIO(_json.dumps({"hook_event_name": "SessionStart"})))
    assert cli.main([]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("Genesys:")              # plain user-visible line FIRST
    payload = _json.loads(lines[-1])                     # structured JSON is still parseable
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "_confirmation_stdout" not in payload         # popped from the JSON, not double-emitted
