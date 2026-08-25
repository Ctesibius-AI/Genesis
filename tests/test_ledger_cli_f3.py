"""F3 CLI: doctor --deadman + consent-gated wire (spec §7 item 1; deploy-gate posture)."""
from __future__ import annotations

import json
from pathlib import Path

from genesis.ledger.cli import main
from genesis.hooks.wiring import hook_wiring_status


def test_doctor_deadman_reports_no_ring(tmp_path: Path, capsys):
    rc = main(["doctor", "--data", str(tmp_path), "--deadman", "--now",
               "2026-08-18T12:00:00+00:00"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "STALE" in out or "no capture ring" in out.lower()


def test_wire_without_yes_does_not_write(tmp_path: Path, capsys):
    settings = tmp_path / "settings.json"
    rc = main(["wire", "--settings", str(settings), "--command", "x -m genesis.hooks.cli"])
    assert rc == 0
    assert not settings.exists()  # deploy gate: nothing written without --yes
    assert "will not write" in capsys.readouterr().out.lower()


def test_wire_with_yes_writes_merge(tmp_path: Path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": ".../response_validator.py"}]}]}}), encoding="utf-8")
    rc = main(["wire", "--settings", str(settings), "--command",
               "x -m genesis.hooks.cli", "--yes"])
    assert rc == 0
    out = json.loads(settings.read_text(encoding="utf-8"))
    assert out["hooks"]["Stop"]  # foreign hook survives
    assert all(hook_wiring_status(settings).values())  # all Genesis events wired
