"""graph-harness T3 — the cross-process persistence AC that would have caught the memory loss.

The bug (owner live run, 2026-08-26): the worker reported "processed N" but the embedded FalkorDB
store never reached disk — in-process readback could not see the gap. This AC retires in-process
readback for any store-touching claim: process A writes through the real store and EXITS; a FRESH
process B opens the same config and MUST read it back. If the T2 close()/SAVE lifecycle regresses,
process B reads nothing and this fails.

LIVE-ONLY: needs the 'graph' extra (graphiti-core + redislite). Skipped in the offline suite; run in
the graph venv. Uses a direct driver write (no LLM, no API cost) — this exercises the redislite RDB
persistence lifecycle, which is exactly what evaporated. (Populated recall THROUGH the daemon with
real extraction is Athena's Condition-1 smoke.)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("graphiti_core", reason="graph extra absent (offline suite)")
pytest.importorskip("redislite", reason="graph extra absent (offline suite)")


_WRITER = """
import os
from genesis.graph.graphiti_backend import build_graphiti_client
c = build_graphiti_client()  # db_path/group_id resolve from GENESIS_DB_PATH/GENESIS_GROUP_ID (D-GCW-2)
try:
    c._run(c._driver.execute_query("CREATE (:XProcProbe {id: 'probe-1'})"))
finally:
    c.close()  # T2: SAVE the RDB + shut the embedded server down cleanly, THEN this process exits
print("WROTE")
"""

_READER = """
from genesis.graph.graphiti_backend import build_graphiti_client
c = build_graphiti_client()
try:
    records, _, _ = c._run(c._driver.execute_query("MATCH (n:XProcProbe) RETURN n.id AS id"))
    ids = [r["id"] for r in records]
    print("READ", ids)
finally:
    c.close()
"""


def _run(script: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", script], env=env,
                          capture_output=True, text=True, timeout=180)


def test_close_raises_persistence_error_when_save_fails(tmp_path: Path, monkeypatch):
    """harness-savefail: if the redislite SAVE fails, close() must raise PersistenceError (fail loud)
    rather than log-and-return — so the worker never reports success over a non-durable store."""
    from genesis.graph.client import PersistenceError
    from genesis.graph.graphiti_backend import build_graphiti_client

    monkeypatch.setenv("GENESIS_DB_PATH", str(tmp_path / "graph.db"))
    monkeypatch.setenv("GENESIS_GROUP_ID", "savefail")
    monkeypatch.setenv("GENESIS_DATA", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-not-called")
    monkeypatch.setenv("GRAPHITI_TELEMETRY_ENABLED", "false")

    c = build_graphiti_client()
    def _boom_save():
        raise OSError("simulated: disk full")
    c._redis_inst.save = _boom_save  # type: ignore[attr-defined]
    with pytest.raises(PersistenceError):
        c.close()


def test_write_in_process_a_is_readable_in_fresh_process_b(tmp_path: Path):
    db_path = tmp_path / "graph.db"
    env = {
        **os.environ,
        "GENESIS_DB_PATH": str(db_path),
        "GENESIS_GROUP_ID": "xproc-persist",
        "GENESIS_DATA": str(tmp_path),
        "ANTHROPIC_API_KEY": "dummy-not-called-for-a-direct-driver-write",
        "GRAPHITI_TELEMETRY_ENABLED": "false",
    }

    a = _run(_WRITER, env)
    assert a.returncode == 0 and "WROTE" in a.stdout, f"writer failed:\nSTDOUT{a.stdout}\nSTDERR{a.stderr}"
    # The RDB must exist on disk AFTER process A has fully exited (the persistence guarantee).
    assert db_path.exists(), "T2 regressed: no RDB written at GENESIS_DB_PATH after the writer exited"

    b = _run(_READER, env)
    assert b.returncode == 0, f"reader failed:\nSTDOUT{b.stdout}\nSTDERR{b.stderr}"
    assert "READ ['probe-1']" in b.stdout, (
        f"cross-process persistence broken: fresh process read {b.stdout!r} (expected probe-1)")
