"""Tests for QA console server (spec §14 D-QA-7).

- `model_to_dict` is pure stdlib; serializable without FastAPI.
- `create_app` lazy-imports FastAPI (not at module load).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from genesys.console.server import model_to_dict
from genesys.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesys.ledger.store import append

NOW = "2026-08-18T12:00:00+00:00"


def _entry(eid, ts) -> LedgerEntry:
    return LedgerEntry(
        entry_id=eid, ts=ts, summary="s",
        provenance=Provenance(eid, "", "", ["the principal"]),
        links=Links(session_id="s1"), extracted=Extracted.NO,
    )


def test_model_to_dict_is_json_serializable(tmp_path: Path):
    d = model_to_dict(tmp_path)
    json.dumps(d)  # must not raise
    assert set(d) >= {"cards", "health", "security", "infra", "deadman"}


def test_model_to_dict_has_no_persona_surface(tmp_path: Path):
    # BT-4b / D-GCW-6: the persona surface (view 5) was removed from the OSS build.
    assert "persona" not in model_to_dict(tmp_path)


def test_model_to_dict_includes_deadman_when_now_given(tmp_path: Path):
    """dict layer must render deadman — the review finding that exposed the bug (spec §7)."""
    d = model_to_dict(tmp_path, now=NOW)
    assert "deadman" in d, "deadman key must be present when now= is supplied"
    assert d["deadman"] is not None, "deadman must not be None when now= is supplied"
    json.dumps(d["deadman"])  # must be JSON-serializable
    alerts = d["deadman"]["alerts"]
    assert any("STALE" in a for a in alerts), f"expected CAPTURE STALE alert; got: {alerts}"


def test_model_to_dict_includes_deadman_stale_and_unwired(tmp_path: Path):
    """Stale ledger + empty hooks config → both STALE and UNWIRED alerts in dict surface."""
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
    d = model_to_dict(tmp_path, now=NOW, settings_path=settings)
    alerts = d["deadman"]["alerts"]
    assert any("STALE" in a for a in alerts), f"expected STALE alert; got: {alerts}"
    assert any("UNWIRED" in a for a in alerts), f"expected UNWIRED alert; got: {alerts}"


def test_model_to_dict_deadman_present_even_without_explicit_now(tmp_path: Path):
    """Existing callers (no now=) still get deadman — wall-clock is read at the surface boundary."""
    d = model_to_dict(tmp_path)
    # deadman is always populated: wall-clock is read here when now= is not supplied
    assert "deadman" in d
    assert d["deadman"] is not None
    json.dumps(d["deadman"])  # must be JSON-serializable


def test_model_to_dict_queue_counts(tmp_path: Path):
    """model_to_dict must return a 'queue' key with pending/in_progress/done counts."""
    append(tmp_path, _entry("EP-2026-08-18.0001", "2026-08-18T10:00:00+00:00"))
    append(tmp_path, LedgerEntry(
        entry_id="EP-2026-08-18.0002", ts="2026-08-18T10:01:00+00:00", summary="s",
        provenance=Provenance("EP-2026-08-18.0002", "", "", ["the principal"]),
        links=Links(session_id="s1"), extracted=Extracted.IN_PROGRESS,
    ))
    append(tmp_path, LedgerEntry(
        entry_id="EP-2026-08-18.0003", ts="2026-08-18T10:02:00+00:00", summary="s",
        provenance=Provenance("EP-2026-08-18.0003", "", "", ["the principal"]),
        links=Links(session_id="s1"), extracted=Extracted.DONE,
    ))
    d = model_to_dict(tmp_path, now=NOW)
    assert "queue" in d, "model_to_dict must include a 'queue' key"
    q = d["queue"]
    assert q["pending"] == 1
    assert q["in_progress"] == 1
    assert q["done"] == 1


def test_server_module_does_not_import_fastapi_at_top_level():
    import genesys.console.server  # noqa: F401
    assert "fastapi" not in sys.modules
