"""D-GCW-18 fix 1+2: the SessionStart drain is guarded/bounded/exception-safe; Stop is wired.

/save is the sole materialization path, so automatic capture leaves the ledger empty — the drain
must NOT pay the live-engine cold-load on an idle start, must never break start, and Stop must be a
wired capture event for crash durability.
"""
from __future__ import annotations

from pathlib import Path

import genesis.extraction.live as live
from genesis.hooks import cli
from genesis.hooks.wiring import GENESIS_EVENTS
from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.ledger.store import append

NOW = "2026-08-26T10:00:00+00:00"


def _queue(root: Path):
    append(root, LedgerEntry(entry_id="EP-1", ts=NOW, summary="s",
           provenance=Provenance("EP-1", "", "", ["the principal"]),
           links=Links(session_id="s1"), extracted=Extracted.NO))  # queued (not yet extracted)


def test_drain_skips_when_nothing_queued(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(live, "run_once", lambda *a, **k: calls.append(1))
    cli._session_start_drain(tmp_path, NOW)()   # empty ledger → guard skips the live build
    assert calls == []


def test_drain_runs_when_queued(tmp_path, monkeypatch):
    _queue(tmp_path)
    calls = []
    monkeypatch.setattr(live, "run_once", lambda *a, **k: (calls.append(k), [])[1])
    cli._session_start_drain(tmp_path, NOW)()
    assert calls and calls[0].get("window") == cli.SESSION_START_DRAIN_WINDOW
    assert calls[0].get("time_budget_s") == cli.SESSION_START_DRAIN_TIME_BUDGET_S


def test_drain_never_raises(tmp_path, monkeypatch):
    _queue(tmp_path)
    def _boom(*a, **k):
        raise RuntimeError("graph extra absent / API down")
    monkeypatch.setattr(live, "run_once", _boom)
    cli._session_start_drain(tmp_path, NOW)()   # must NOT raise — start is never broken


def test_stop_is_a_wired_capture_event():
    assert "Stop" in GENESIS_EVENTS  # crash durability (D-GCW-18)
