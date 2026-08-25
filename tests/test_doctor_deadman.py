"""F3 doctor deadman: last-ring age + wiring status, loud when stale (spec §5/§7)."""
from __future__ import annotations

import json
from pathlib import Path

from genesis.doctor import DeadmanReport, doctor_deadman
from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.ledger.store import append

NOW = "2026-08-18T12:00:00+00:00"


def _entry(eid, ts) -> LedgerEntry:
    return LedgerEntry(entry_id=eid, ts=ts, summary="s",
                       provenance=Provenance(eid, "", "", ["the principal"]),
                       links=Links(session_id="s1"), extracted=Extracted.NO)


def test_no_ring_is_stale_and_loud(tmp_path: Path):
    r = doctor_deadman(tmp_path, now=NOW)
    assert isinstance(r, DeadmanReport)
    assert r.last_ring_ts == "" and r.age_hours is None and r.stale is True


def test_recent_ring_is_not_stale(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-18.0001", "2026-08-18T11:00:00+00:00"))
    r = doctor_deadman(tmp_path, now=NOW, threshold_hours=24.0)
    assert r.last_ring_ts == "2026-08-18T11:00:00+00:00"
    assert r.age_hours == 1.0 and r.stale is False


def test_old_ring_beyond_threshold_is_stale(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-16.0001", "2026-08-16T11:00:00+00:00"))
    r = doctor_deadman(tmp_path, now=NOW, threshold_hours=24.0)
    assert r.age_hours == 49.0 and r.stale is True


def test_wiring_status_is_included_when_settings_path_given(tmp_path: Path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
    r = doctor_deadman(tmp_path, now=NOW, settings_path=settings)
    assert r.wired == {"SessionStart": False, "Stop": False, "SessionEnd": False, "PreCompact": False}


def test_no_settings_path_leaves_wired_none(tmp_path: Path):
    assert doctor_deadman(tmp_path, now=NOW).wired is None


def test_z_suffix_timestamps_do_not_crash(tmp_path: Path):
    """Regression test: Z suffix (RFC 3339) should not crash fromisoformat."""
    append(tmp_path, _entry("EP-2026-08-18.0001", "2026-08-18T11:00:00Z"))
    r = doctor_deadman(tmp_path, now="2026-08-18T12:00:00Z", threshold_hours=24.0)
    assert r.last_ring_ts == "2026-08-18T11:00:00Z"
    assert r.age_hours == 1.0 and r.stale is False


def test_ring_exactly_at_threshold_is_stale(tmp_path: Path):
    """Boundary: age == threshold_hours => stale=True (>= not >)."""
    append(tmp_path, _entry("EP-2026-08-17.0001", "2026-08-17T12:00:00+00:00"))
    r = doctor_deadman(tmp_path, now=NOW, threshold_hours=24.0)
    # now=2026-08-18T12:00:00+00:00, last_ts=2026-08-17T12:00:00+00:00 => exactly 24 hours
    assert r.age_hours == 24.0 and r.stale is True
