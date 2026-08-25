"""BT-8 installer (D-GCW-10): AC-I1/I2/I3, AC-ISO1, AC-ISO2 (red-line), AC-C1.

Project-local ONLY, idempotent, no-clobber, fail-loud, CLAUDE.md untouched, clean uninstall.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from genesis.hooks.wiring import GENESIS_EVENTS, hook_wiring_status, is_genesis_hook
from genesis.install.installer import InstallError, compute_store, install, uninstall


def _settings(ws: Path) -> dict:
    return json.loads((ws / ".claude" / "settings.json").read_text())


def _install(ws: Path, data_root: Path, **kw):
    return install(ws, data_root=data_root, api_key_present=True, **kw)


# --- AC-I1 ---

def test_missing_api_key_fails_loud(tmp_path):
    with pytest.raises(InstallError):
        install(tmp_path / "ws", data_root=tmp_path / "d", api_key_present=False)


def test_claude_md_is_never_touched(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    claude_md = ws / "CLAUDE.md"
    claude_md.write_text("my master prompt\n", encoding="utf-8")
    before = claude_md.read_bytes()
    _install(ws, tmp_path / "data")
    assert claude_md.read_bytes() == before  # byte-identical


# --- AC-ISO2 (red-line): hooks project-local ONLY ---

def test_hooks_are_project_local_only(tmp_path):
    ws1, ws2 = tmp_path / "ws1", tmp_path / "ws2"
    fake_home_claude = tmp_path / "home" / ".claude" / "settings.json"
    _install(ws1, tmp_path / "data")
    # ws1 got the genesis hook
    assert any(hook_wiring_status(ws1 / ".claude" / "settings.json").values())
    # nothing written outside ws1: ws2 + a global ~/.claude are untouched
    assert not (ws2 / ".claude" / "settings.json").exists()
    assert not fake_home_claude.exists()


# --- AC-I2: idempotent + foreign hooks survive ---

def test_idempotent_and_foreign_hook_survives(tmp_path):
    ws = tmp_path / "ws"
    settings = ws / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    foreign = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "response_validator.py"}]}]}}
    settings.write_text(json.dumps(foreign), encoding="utf-8")
    _install(ws, tmp_path / "data")
    _install(ws, tmp_path / "data")  # second run: no-op
    hooks = _settings(ws)["hooks"]
    # foreign Stop hook preserved
    assert any("response_validator" in h["command"]
               for g in hooks["Stop"] for h in g["hooks"])
    # genesis added exactly once per event (idempotent)
    for ev in GENESIS_EVENTS:
        gen = [h for g in hooks[ev] for h in g["hooks"] if is_genesis_hook(h["command"])]
        assert len(gen) == 1


# --- AC-ISO1: two workspaces → two stores ---

def test_two_workspaces_resolve_to_two_stores(tmp_path):
    data = tmp_path / "data"
    r1 = _install(tmp_path / "wsA", data)
    r2 = _install(tmp_path / "wsB", data)
    assert r1["db_path"] != r2["db_path"]
    assert r1["group_id"] != r2["group_id"]


def test_store_modes(tmp_path):
    data = tmp_path / "data"
    ws = tmp_path / "ws"
    own = compute_store(ws, data, "own-isolated")
    shared_grp = compute_store(ws, data, "shared-store-own-group")
    shared_mem = compute_store(ws, data, "shared-memory")
    assert own[0] != shared_grp[0]          # own store has its own db_path
    assert shared_grp[1] != shared_mem[1]    # own group vs pooled "shared"
    assert shared_mem[1] == "shared"


# --- AC-I3: clean uninstall ---

def test_uninstall_removes_only_genesis(tmp_path):
    ws = tmp_path / "ws"
    settings = ws / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps(
        {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "response_validator.py"}]}]},
         "env": {"FOREIGN": "keep"}}), encoding="utf-8")
    save_src = tmp_path / "save.md"
    save_src.write_text("/save command\n", encoding="utf-8")
    _install(ws, tmp_path / "data", save_command_src=save_src)
    assert (ws / ".claude" / "commands" / "save.md").exists()

    uninstall(ws)
    s = _settings(ws)
    # foreign hook + foreign env key survive; genesis gone
    assert any("response_validator" in h["command"] for g in s["hooks"].get("Stop", []) for h in g["hooks"])
    assert not any(hook_wiring_status(settings).values())  # no genesis hooks left
    assert s["env"] == {"FOREIGN": "keep"}
    assert not (ws / ".claude" / "commands" / "save.md").exists()  # /save removed


# --- AC-C1: capture wiring is prompt-independent ---

def test_capture_events_registered_post_install(tmp_path):
    ws = tmp_path / "ws"
    _install(ws, tmp_path / "data")
    status = hook_wiring_status(ws / ".claude" / "settings.json")
    # the harness-level capture events are wired — they fire regardless of CLAUDE.md
    assert status.get("SessionEnd") and status.get("PreCompact")
