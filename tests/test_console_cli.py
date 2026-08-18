"""Tests for QA console CLI (spec §14).

`dump` uses stdlib only (fixtures/offline). `serve` lazy-imports FastAPI.
"""

from __future__ import annotations

from pathlib import Path

from genesys.console.cli import main


def test_cli_dump_prints_json(tmp_path: Path, capsys):
    data = tmp_path / "d"
    data.mkdir()
    assert main(["dump", "--data", str(data)]) == 0
    out = capsys.readouterr().out
    assert '"cards"' in out and '"health"' in out
