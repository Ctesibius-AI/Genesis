"""F3 hook wiring: status + consent-gated merge-never-clobber writer (spec §7 item 1)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from genesys.hooks.wiring import (
    GENESYS_EVENTS,
    hook_wiring_status,
    is_genesys_hook,
    write_hook_wiring,
)

CMD = ("GENESYS_DATA_ROOT=/x PYTHONPATH=/y /z/python -m genesys.hooks.cli")
FOREIGN_STOP = {
    "hooks": [{"type": "command", "command": "/usr/bin/python3 .../response_validator.py",
               "timeout": 10}]
}


def _write(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_is_genesys_hook_distinguishes_the_foreign_stop_hook():
    assert is_genesys_hook(CMD) is True
    assert is_genesys_hook("/usr/bin/python3 .../response_validator.py") is False


def test_status_reports_missing_file_as_all_unwired(tmp_path: Path):
    status = hook_wiring_status(tmp_path / "nope.json")
    assert status == {e: False for e in GENESYS_EVENTS}


def test_write_refuses_without_consent(tmp_path: Path):
    p = tmp_path / "settings.json"
    with pytest.raises(PermissionError):
        write_hook_wiring(p, command=CMD, consent=False)
    assert not p.exists()  # nothing written


@pytest.mark.parametrize("bad_consent", [1, "yes", None])
def test_write_refuses_truthy_but_not_True_consent(tmp_path: Path, bad_consent):
    """write_hook_wiring uses ``consent is not True`` (identity), not ``not consent``.

    Truthy-but-not-True values (int 1, non-empty string, None) must raise PermissionError
    and leave the settings file unchanged/uncreated. Locks the gate against a future
    weakening to ``if not consent``.
    """
    p = tmp_path / "settings.json"
    with pytest.raises(PermissionError):
        write_hook_wiring(p, command=CMD, consent=bad_consent)
    assert not p.exists()  # file must not be created


def test_write_merges_without_clobbering_the_foreign_stop_hook(tmp_path: Path):
    p = tmp_path / "settings.json"
    _write(p, {"hooks": {"Stop": [FOREIGN_STOP]}, "permissions": {"allow": ["x"]}})
    actions = write_hook_wiring(p, command=CMD, consent=True)
    out = json.loads(p.read_text(encoding="utf-8"))
    # foreign Stop hook survives (Genesys wires Stop now — D-GCW-18 — but never clobbers it)
    assert FOREIGN_STOP in out["hooks"]["Stop"]
    assert out["permissions"] == {"allow": ["x"]}
    # every Genesys event now wired
    assert all(actions[e] == "added" for e in GENESYS_EVENTS)
    assert hook_wiring_status(p) == {e: True for e in GENESYS_EVENTS}


def test_write_is_idempotent(tmp_path: Path):
    p = tmp_path / "settings.json"
    write_hook_wiring(p, command=CMD, consent=True)
    actions = write_hook_wiring(p, command=CMD, consent=True)  # second run
    assert all(actions[e] == "already-wired" for e in GENESYS_EVENTS)
    out = json.loads(p.read_text(encoding="utf-8"))
    for e in GENESYS_EVENTS:
        gen = [h for grp in out["hooks"][e] for h in grp["hooks"] if is_genesys_hook(h["command"])]
        assert len(gen) == 1  # no duplicate
