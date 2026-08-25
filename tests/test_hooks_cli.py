"""Tests for genesys.hooks.cli — stdin hook JSON → stdout JSON result.

All tests are offline. Uses monkeypatch to simulate stdin + env vars.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

from genesys.hooks.cli import main


# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #

NOW = "2026-08-17T13:00:00+00:00"

TOOL_USE_ID = "toolu_cli_test_01"


def _make_transcript(tmp_path: Path) -> Path:
    records = [
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": "CLI integration test input.",
            },
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "CLI integration test output reply.",
                    }
                ],
            },
        },
    ]
    path = tmp_path / "cli_transcript.jsonl"
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )
    return path


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    hook: dict,
    tmp_path: Path,
    *,
    now: str = NOW,
    capsys: pytest.CaptureFixture | None = None,
) -> tuple[int, dict]:
    """Run main() with monkeypatched stdin + env, capture stdout."""
    hook_json = json.dumps(hook)
    monkeypatch.setattr("sys.stdin", io.StringIO(hook_json))
    monkeypatch.setenv("GENESYS_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("GENESYS_NOW", now)

    exit_code = main()

    # Read stdout via capsys if provided, otherwise just return exit code
    if capsys is not None:
        captured = capsys.readouterr()
        result = json.loads(captured.out.strip().splitlines()[-1])  # SessionStart prepends a plain confirmation line (AC-CONF1); JSON is the last line
        return exit_code, result
    return exit_code, {}


# --------------------------------------------------------------------------- #
# Tests                                                                         #
# --------------------------------------------------------------------------- #

def test_cli_stop_hook_exits_zero_and_returns_append_only_sentinel(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    """cli.py passes annotate=False (Option B) so Stop returns the append-only sentinel."""
    transcript = _make_transcript(tmp_path)
    hook = {
        "hook_event_name": "Stop",
        "transcript_path": str(transcript),
        "session_id": "sess-cli-001",
    }
    exit_code, result = _run_main(monkeypatch, hook, tmp_path, capsys=capsys)
    assert exit_code == 0
    # append-only: WAL grows, no annotation queued
    assert result == {"appended": True, "annotated": False}


def test_cli_session_start_exits_zero_and_returns_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    hook = {"hook_event_name": "SessionStart"}
    exit_code, result = _run_main(monkeypatch, hook, tmp_path, capsys=capsys)
    assert exit_code == 0
    assert "hookSpecificOutput" in result


def test_cli_precompact_exits_zero_and_returns_append_only_sentinel(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    """cli.py passes annotate=False (Option B) so PreCompact returns the append-only sentinel."""
    transcript = _make_transcript(tmp_path)
    hook = {
        "hook_event_name": "PreCompact",
        "transcript_path": str(transcript),
        "session_id": "sess-cli-compact",
    }
    exit_code, result = _run_main(monkeypatch, hook, tmp_path, capsys=capsys)
    assert exit_code == 0
    # append-only: WAL grows, no annotation queued
    assert result.get("appended") is True
    assert result.get("annotated") is False


def test_cli_unknown_event_exits_zero_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    hook = {"hook_event_name": "UnknownEvent"}
    exit_code, result = _run_main(monkeypatch, hook, tmp_path, capsys=capsys)
    assert exit_code == 0
    assert result == {}


def test_cli_invalid_json_on_stdin_exits_one(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    monkeypatch.setattr("sys.stdin", io.StringIO("not { valid json"))
    monkeypatch.setenv("GENESYS_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("GENESYS_NOW", NOW)

    exit_code = main()
    assert exit_code == 1


def test_cli_now_from_env_is_used(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    """GENESYS_NOW env var is used as the clock.

    With Option B (annotate=False), cli.py produces the append-only sentinel; the WAL
    line's ts embeds the date from GENESYS_NOW — verifiable via the WAL segment, not
    entry_id (no annotation is created on the auto-hook path).
    """
    transcript = _make_transcript(tmp_path)
    custom_now = "2026-07-04T00:00:00+00:00"
    hook = {
        "hook_event_name": "Stop",
        "transcript_path": str(transcript),
        "session_id": "sess-clock-env",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook)))
    monkeypatch.setenv("GENESYS_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("GENESYS_NOW", custom_now)

    exit_code = main()
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    # append-only sentinel (Option B)
    assert result == {"appended": True, "annotated": False}
    # WAL segment for the injected date was written
    from genesys.wal.record import WalRecord
    from genesys.wal.store import read_segment
    lines = read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-07-04")
    assert lines, "WAL MEMORY_GRADE must have a line dated from GENESYS_NOW"


def test_cli_now_from_hook_json_is_used_when_env_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    """Hook JSON 'now' field is used when GENESYS_NOW is not set.

    With Option B (annotate=False) the auto-hook path produces no annotation, so we verify
    the WAL segment for the hook's date instead of checking entry_id.
    """
    transcript = _make_transcript(tmp_path)
    hook = {
        "hook_event_name": "Stop",
        "transcript_path": str(transcript),
        "session_id": "sess-clock-hook",
        "now": "2026-06-15T08:00:00+00:00",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook)))
    monkeypatch.setenv("GENESYS_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("GENESYS_NOW", raising=False)

    exit_code = main()
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    assert result == {"appended": True, "annotated": False}
    # WAL segment for the hook-injected date was written
    from genesys.wal.record import WalRecord
    from genesys.wal.store import read_segment
    lines = read_segment(tmp_path, WalRecord.MEMORY_GRADE, "2026-06-15")
    assert lines, "WAL MEMORY_GRADE must have a line dated from hook JSON 'now'"


def test_cli_output_is_valid_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    """Output must always be parseable JSON."""
    hook = {"hook_event_name": "SessionStart"}
    exit_code, result = _run_main(monkeypatch, hook, tmp_path, capsys=capsys)
    assert exit_code == 0
    assert isinstance(result, dict)


def test_cli_default_data_root_is_dot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
    tmp_path_factory: pytest.TempPathFactory,
):
    """When GENESYS_DATA_ROOT is not set, defaults to '.' (cwd)."""
    hook = {"hook_event_name": "SessionStart"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook)))
    monkeypatch.delenv("GENESYS_DATA_ROOT", raising=False)
    monkeypatch.setenv("GENESYS_NOW", NOW)
    # chdir to a tmp dir so "." resolves safely
    import os
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        exit_code = main()
        captured = capsys.readouterr()
        result = json.loads(captured.out.strip().splitlines()[-1])  # SessionStart prepends a plain confirmation line (AC-CONF1); JSON is the last line
        assert exit_code == 0
    finally:
        os.chdir(old_cwd)
