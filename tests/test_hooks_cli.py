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
        result = json.loads(captured.out)
        return exit_code, result
    return exit_code, {}


# --------------------------------------------------------------------------- #
# Tests                                                                         #
# --------------------------------------------------------------------------- #

def test_cli_stop_hook_exits_zero_and_returns_entry_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    transcript = _make_transcript(tmp_path)
    hook = {
        "hook_event_name": "Stop",
        "transcript_path": str(transcript),
        "session_id": "sess-cli-001",
    }
    exit_code, result = _run_main(monkeypatch, hook, tmp_path, capsys=capsys)
    assert exit_code == 0
    assert "entry_id" in result


def test_cli_session_start_exits_zero_and_returns_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    hook = {"hook_event_name": "SessionStart"}
    exit_code, result = _run_main(monkeypatch, hook, tmp_path, capsys=capsys)
    assert exit_code == 0
    assert "hookSpecificOutput" in result


def test_cli_precompact_exits_zero_and_returns_entry_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    transcript = _make_transcript(tmp_path)
    hook = {
        "hook_event_name": "PreCompact",
        "transcript_path": str(transcript),
        "session_id": "sess-cli-compact",
    }
    exit_code, result = _run_main(monkeypatch, hook, tmp_path, capsys=capsys)
    assert exit_code == 0
    assert "entry_id" in result


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
    """GENESYS_NOW env var is used as the clock."""
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
    # Entry ID embeds the date from GENESYS_NOW
    assert "EP-2026-07-04" in result["entry_id"]


def test_cli_now_from_hook_json_is_used_when_env_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    """Hook JSON 'now' field is used when GENESYS_NOW is not set."""
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
    assert "EP-2026-06-15" in result["entry_id"]


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
        result = json.loads(captured.out)
        assert exit_code == 0
    finally:
        os.chdir(old_cwd)
