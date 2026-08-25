"""BT-2 / AC-X1: the `.drain.lock` records PID+start-time and a dead-owner lock is cleared.

A SIGKILL/crash must never permanently wedge ingestion. `single_instance` self-heals a
dead-owner lock and retries; a live owner's lock still raises `LockHeld`.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from genesys.extraction.lock import LockHeld, clear_if_dead, single_instance
from genesys.journal.journal import read_journal

TS = "2026-08-26T10:00:00+00:00"


def _dead_pid() -> int:
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid  # reaped — now dead


def _write_lock(root: Path, payload: dict) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".drain.lock"
    lock.write_text(json.dumps(payload), encoding="utf-8")
    return lock


def test_lock_records_pid_and_start(tmp_path: Path):
    with single_instance(tmp_path, ts=TS):
        info = json.loads((tmp_path / ".drain.lock").read_text())
        assert info["pid"] == os.getpid()
        assert "start" in info


def test_clear_if_dead_removes_dead_owner_lock(tmp_path: Path):
    lock = _write_lock(tmp_path, {"pid": _dead_pid(), "start": None, "ts": TS})
    assert clear_if_dead(tmp_path, ts=TS) is True
    assert not lock.exists()
    assert any(j.action == "stale-lock-cleared" for j in read_journal(tmp_path))


def test_clear_if_dead_keeps_live_owner_lock(tmp_path: Path):
    with single_instance(tmp_path, ts=TS):  # held by this live process
        assert clear_if_dead(tmp_path, ts=TS) is False
        assert (tmp_path / ".drain.lock").exists()


def test_clear_if_dead_treats_empty_legacy_lock_as_stale(tmp_path: Path):
    _write_lock(tmp_path, {})  # legacy empty lock, no PID
    assert clear_if_dead(tmp_path, ts=TS) is True
    assert not (tmp_path / ".drain.lock").exists()


def test_single_instance_self_heals_dead_owner_lock(tmp_path: Path):
    _write_lock(tmp_path, {"pid": _dead_pid(), "start": None, "ts": TS})
    with single_instance(tmp_path, ts=TS):  # would raise if not self-healed
        assert (tmp_path / ".drain.lock").exists()
    assert not (tmp_path / ".drain.lock").exists()


def test_live_second_instance_still_raises(tmp_path: Path):
    with single_instance(tmp_path, ts=TS):
        with pytest.raises(LockHeld):
            with single_instance(tmp_path, ts=TS):
                pass
