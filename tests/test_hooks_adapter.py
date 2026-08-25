"""Tests for genesis.hooks.adapter — hook dispatch to the capture pipeline.

All tests are offline (fixtures only, no real Claude Code, no API key).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from genesis.diary.backend import FakeBackend
from genesis.hooks.adapter import dispatch
from genesis.ledger.store import read_all


# --------------------------------------------------------------------------- #
# Shared fixture helpers                                                        #
# --------------------------------------------------------------------------- #

NOW = "2026-08-17T12:00:00+00:00"
TOOL_USE_ID = "toolu_testAbCd"


def _make_transcript(tmp_path: Path, *, name: str = "transcript.jsonl") -> Path:
    """Write a small but realistic CC transcript .jsonl to tmp_path."""
    records = [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": "Please list the genesis modules.",
            },
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "thinking",
                        "thinking": "I should run a find command.",
                    },
                    {
                        "type": "text",
                        "text": "Let me find the modules for you.",
                    },
                    {
                        "type": "tool_use",
                        "id": TOOL_USE_ID,
                        "name": "Bash",
                        "input": {"command": "ls src/genesis/"},
                    },
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": TOOL_USE_ID,
                        "content": "capture/\ndiary/\nhooks/\nledger/\n",
                    }
                ],
            },
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "The genesis package has capture, diary, hooks, and ledger modules.",
                    }
                ],
            },
        },
    ]
    path = tmp_path / name
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------- #
# Stop hook — creates a ledger entry                                            #
# --------------------------------------------------------------------------- #

def test_stop_hook_creates_ledger_entry(tmp_path: Path):
    transcript = _make_transcript(tmp_path)
    hook = {
        "hook_event_name": "Stop",
        "transcript_path": str(transcript),
        "session_id": "sess-test-001",
    }
    result = dispatch(hook, tmp_path, now=NOW)

    assert "entry_id" in result
    entries = read_all(tmp_path)
    assert len(entries) == 1
    assert entries[0].entry_id == result["entry_id"]


def test_stop_hook_summary_equals_last_assistant_text(tmp_path: Path):
    transcript = _make_transcript(tmp_path)
    hook = {
        "hook_event_name": "Stop",
        "transcript_path": str(transcript),
        "session_id": "sess-test-002",
    }
    dispatch(hook, tmp_path, now=NOW)

    entries = read_all(tmp_path)
    assert len(entries) == 1
    # Summary is the last assistant_text (provisional F-GENESIS-03 ruling)
    assert "genesis package has capture" in entries[0].summary


def test_session_end_hook_also_creates_ledger_entry(tmp_path: Path):
    """SessionEnd is equivalent to Stop."""
    transcript = _make_transcript(tmp_path)
    hook = {
        "hook_event_name": "SessionEnd",
        "transcript_path": str(transcript),
        "session_id": "sess-test-003",
    }
    result = dispatch(hook, tmp_path, now=NOW)
    assert "entry_id" in result
    assert read_all(tmp_path)


def test_stop_hook_with_empty_transcript_still_creates_entry(tmp_path: Path):
    """An empty transcript (no events) should still commit an entry (empty raw_span)."""
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    hook = {
        "hook_event_name": "Stop",
        "transcript_path": str(empty),
        "session_id": "sess-empty",
    }
    result = dispatch(hook, tmp_path, now=NOW)
    assert "entry_id" in result


def test_stop_hook_with_blank_and_malformed_lines(tmp_path: Path):
    """Blank and malformed lines in the .jsonl are skipped gracefully."""
    path = tmp_path / "messy.jsonl"
    records = [
        "",
        "   ",
        "not json at all {{{",
        json.dumps({"type": "user", "message": {"role": "user", "content": "Hello"}}),
        "",
    ]
    path.write_text("\n".join(records) + "\n", encoding="utf-8")
    hook = {
        "hook_event_name": "Stop",
        "transcript_path": str(path),
        "session_id": "sess-messy",
    }
    result = dispatch(hook, tmp_path, now=NOW)
    assert "entry_id" in result


def test_stop_hook_missing_transcript_path_still_creates_entry(tmp_path: Path):
    """Missing transcript_path is handled defensively."""
    hook = {
        "hook_event_name": "Stop",
        "session_id": "sess-no-path",
    }
    result = dispatch(hook, tmp_path, now=NOW)
    assert "entry_id" in result


# --------------------------------------------------------------------------- #
# SessionStart hook — returns additionalContext                                 #
# --------------------------------------------------------------------------- #

def test_session_start_returns_hook_specific_output(tmp_path: Path):
    hook = {"hook_event_name": "SessionStart"}
    result = dispatch(hook, tmp_path, backend=FakeBackend(), now=NOW)

    assert "hookSpecificOutput" in result
    hso = result["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart"
    assert "additionalContext" in hso
    # additionalContext is a string (the diary text)
    assert isinstance(hso["additionalContext"], str)


def test_session_start_with_empty_ledger_returns_empty_context(tmp_path: Path):
    hook = {"hook_event_name": "SessionStart"}
    result = dispatch(hook, tmp_path, backend=FakeBackend(), now=NOW)
    # Empty ledger → FakeBackend returns "" (no diary sections)
    assert result["hookSpecificOutput"]["additionalContext"] == ""


def test_session_start_with_existing_ledger_returns_diary_text(tmp_path: Path):
    """Seed a ledger entry, then confirm SessionStart includes it in context."""
    from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
    from genesis.ledger.store import append

    append(tmp_path, LedgerEntry(
        entry_id="EP-2026-08-17.0001",
        ts="2026-08-17T10:00:00+00:00",
        summary="Decided to use FakeBackend for tests.",
        provenance=Provenance(
            "EP-2026-08-17.0001",
            "2026-08-17T09:00:00+00:00",
            "2026-08-17T10:00:00+00:00",
            ["the principal", "Daimon"],
        ),
        links=Links(session_id="sess-prior"),
        extracted=Extracted.NO,
    ))

    hook = {"hook_event_name": "SessionStart"}
    result = dispatch(hook, tmp_path, backend=FakeBackend(), now=NOW)
    ctx = result["hookSpecificOutput"]["additionalContext"]
    assert "FakeBackend for tests" in ctx


# --------------------------------------------------------------------------- #
# PreCompact hook — returns dict with entry_id                                  #
# --------------------------------------------------------------------------- #

def test_precompact_returns_entry_id(tmp_path: Path):
    transcript = _make_transcript(tmp_path)
    hook = {
        "hook_event_name": "PreCompact",
        "transcript_path": str(transcript),
        "session_id": "sess-compact-001",
    }
    result = dispatch(hook, tmp_path, backend=FakeBackend(), now=NOW)
    assert "entry_id" in result


def test_precompact_is_durable_without_backend(tmp_path: Path):
    """precompact_flush must persist even when backend is None."""
    transcript = _make_transcript(tmp_path)
    hook = {
        "hook_event_name": "PreCompact",
        "transcript_path": str(transcript),
        "session_id": "sess-compact-002",
    }
    result = dispatch(hook, tmp_path, backend=None, now=NOW)
    assert "entry_id" in result
    entries = read_all(tmp_path)
    assert any(e.entry_id == result["entry_id"] for e in entries)


# --------------------------------------------------------------------------- #
# Unknown event — returns {}                                                    #
# --------------------------------------------------------------------------- #

def test_unknown_event_returns_empty_dict(tmp_path: Path):
    hook = {"hook_event_name": "SomethingWeirdAndUnknown"}
    result = dispatch(hook, tmp_path, now=NOW)
    assert result == {}


def test_missing_event_returns_empty_dict(tmp_path: Path):
    hook = {}  # no hook_event_name key
    result = dispatch(hook, tmp_path, now=NOW)
    assert result == {}


# --------------------------------------------------------------------------- #
# FakeBackend default                                                            #
# --------------------------------------------------------------------------- #

def test_dispatch_uses_fake_backend_by_default(tmp_path: Path):
    """Passing backend=None should not crash — FakeBackend is the default."""
    hook = {"hook_event_name": "SessionStart"}
    result = dispatch(hook, tmp_path, backend=None, now=NOW)
    assert "hookSpecificOutput" in result
