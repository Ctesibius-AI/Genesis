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
