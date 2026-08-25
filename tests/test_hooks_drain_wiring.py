"""BT-2 / AC-D2: SessionStart runs the bounded drain, and a LockHeld is a no-op (never blocks).

The injected `drain` callable models the bounded SessionStart drain (cli.py binds the real one).
A drain already in progress raises LockHeld — start must still return the diary context.
"""
from __future__ import annotations

from pathlib import Path

from genesis.extraction.lock import LockHeld
from genesis.hooks.adapter import dispatch

NOW = "2026-08-26T10:00:00+00:00"
HOOK = {"hook_event_name": "SessionStart"}


def _has_context(out: dict) -> bool:
    return "additionalContext" in out.get("hookSpecificOutput", {})


def test_sessionstart_runs_drain(tmp_path: Path):
    calls = []
    out = dispatch(HOOK, tmp_path, now=NOW, drain=lambda: calls.append(1))
    assert calls == [1]
    assert _has_context(out)


def test_sessionstart_lockheld_is_noop(tmp_path: Path):
    def drain():
        raise LockHeld("a drain is already running")
    out = dispatch(HOOK, tmp_path, now=NOW, drain=drain)  # must NOT raise
    assert _has_context(out)  # start still compiles the diary


def test_sessionstart_without_drain_unchanged(tmp_path: Path):
    out = dispatch(HOOK, tmp_path, now=NOW)  # drain=None (backward compatible)
    assert _has_context(out)
