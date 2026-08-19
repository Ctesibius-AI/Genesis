"""Switch-on wiring (owner go-ahead 2026-08-19): the LIVE entry points must pass the
new-flow flags. Offline — the real dispatch / drain / live-components are monkeypatched;
no network, no graph, no API. These lock the activation so a future edit can't silently
revert the live path to the legacy copy/jot gate.
"""

from __future__ import annotations

import io
import json

import genesys.extraction.live as live
import genesys.hooks.cli as hooks_cli
from genesys.inspection.ladder import LadderConfig


def test_live_hook_passes_wal_and_cursor_delta(monkeypatch, tmp_path):
    """genesys-hook (the wired SessionEnd/PreCompact/SessionStart entry) must dispatch
    with wal=True + cursor_delta=True so live capture takes the WAL annotation path."""
    captured: dict = {}

    def fake_dispatch(hook, data_root, *, now, **kw):
        captured.update(kw)
        captured["now"] = now
        return {"ok": True}

    monkeypatch.setattr(hooks_cli, "dispatch", fake_dispatch)
    monkeypatch.setenv("GENESYS_DATA_ROOT", str(tmp_path))
    payload = {"hook_event_name": "SessionEnd", "now": "2026-08-19T10:00:00+00:00"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

    rc = hooks_cli.main([])

    assert rc == 0
    assert captured.get("wal") is True, "live capture must use the WAL path"
    assert captured.get("cursor_delta") is True, "live capture must bank only the delta"


def test_live_drain_runs_the_ladder_shadow_off(monkeypatch, tmp_path):
    """genesys-worker's run_once must drain through the inspection ladder with shadow=False
    (Tier 0 routing live, per owner ruling)."""
    captured: dict = {}

    monkeypatch.setattr("genesys.doctor.doctor_requeue", lambda data_root: [])
    monkeypatch.setattr(live, "build_live", lambda data_root: ("ENG", "BK", "SC"))

    def fake_drain(data_root, engine, backend, *, ts, **kw):
        captured.update(kw)
        captured["ts"] = ts
        return ["EP-1"]

    monkeypatch.setattr("genesys.extraction.drain.drain_once", fake_drain)

    out = live.run_once(tmp_path, now="2026-08-19T10:00:00+00:00")

    assert out == ["EP-1"]
    ladder = captured.get("ladder")
    assert isinstance(ladder, LadderConfig), "live drain must supply a LadderConfig"
    assert ladder.shadow is False, "owner ruling: Tier 0 routes live (shadow off)"
    assert captured.get("scorer") == "SC", "the real relatedness scorer stays wired"
    assert captured.get("chart") is not None, "the audit control chart must be supplied"
    assert captured.get("rng") is not None, "the audit RNG must be supplied"
