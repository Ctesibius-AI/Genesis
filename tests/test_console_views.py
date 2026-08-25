from __future__ import annotations

from pathlib import Path

from genesis.console.views import Health, health_strip, infra_view, security_view
from genesis.journal.journal import JournalEntry, append_journal


def _j(tmp_path, action, scope="EP-1", ts="2026-08-17T10:00:00+00:00"):
    append_journal(tmp_path, JournalEntry(ts=ts, action=action, scope=scope, author="supervisor"))


def test_health_flag_rate(tmp_path: Path):
    _j(tmp_path, "gate-resolve"); _j(tmp_path, "gate-resolve"); _j(tmp_path, "gate-flag")
    _j(tmp_path, "verdict"); _j(tmp_path, "revert")
    h = health_strip(tmp_path)
    assert isinstance(h, Health)
    assert h.flag_rate == 1 / 3  # one flag of three gate events
    assert h.verdicts == 1 and h.reverts == 1


def test_security_and_infra_views(tmp_path: Path):
    _j(tmp_path, "scrub"); _j(tmp_path, "redact"); _j(tmp_path, "worker-error"); _j(tmp_path, "lock-violation")
    assert {j.action for j in security_view(tmp_path)} == {"scrub", "redact"}
    assert {j.action for j in infra_view(tmp_path)} == {"worker-error", "lock-violation"}
