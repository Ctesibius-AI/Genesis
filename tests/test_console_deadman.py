"""F3 console deadman surface — stale/unwired surfaced loudly as alerts (spec §7 item 1)."""
from __future__ import annotations

import json
from pathlib import Path

from genesis.console.model import console_model
from genesis.console.views import DeadmanStrip, deadman_strip
from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.ledger.store import append

NOW = "2026-08-18T12:00:00+00:00"


def _entry(eid, ts) -> LedgerEntry:
    return LedgerEntry(entry_id=eid, ts=ts, summary="s",
                       provenance=Provenance(eid, "", "", ["the principal"]),
                       links=Links(session_id="s1"), extracted=Extracted.NO)


def test_no_ring_surfaces_a_loud_stale_alert(tmp_path: Path):
    strip = deadman_strip(tmp_path, now=NOW)
    assert isinstance(strip, DeadmanStrip) and strip.stale is True
    assert any("STALE" in a for a in strip.alerts)


def test_healthy_recent_ring_has_no_alerts(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-18.0001", "2026-08-18T11:30:00+00:00"))
    strip = deadman_strip(tmp_path, now=NOW)
    assert strip.stale is False and strip.alerts == []


def test_unwired_events_surface_as_alerts(tmp_path: Path):
    append(tmp_path, _entry("EP-2026-08-18.0001", "2026-08-18T11:30:00+00:00"))
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
    strip = deadman_strip(tmp_path, now=NOW, settings_path=settings)
    assert strip.alerts, f"expected alerts for unwired hooks; got empty list"
    assert any("UNWIRED" in a and "SessionEnd" in a for a in strip.alerts)


def test_console_model_includes_deadman_only_when_now_given(tmp_path: Path):
    assert console_model(tmp_path).deadman is None  # existing callers unaffected
    m = console_model(tmp_path, now=NOW)
    assert isinstance(m.deadman, DeadmanStrip) and m.deadman.stale is True
