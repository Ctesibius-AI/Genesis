"""run_gate opt-in ladder path: default OFF keeps the jot gate; ladder=cfg takes the raw path."""
from __future__ import annotations

import random
from pathlib import Path

from genesis.graph.engine import FakeGraph, GraphEdge
from genesis.inspection.audit import FalsePassChart
from genesis.inspection.ladder import LadderConfig
from genesis.journal.journal import read_journal
from genesis.supervisor.gate import run_gate
from genesis.workers.backend import FakeLLMBackend


def test_ladder_none_keeps_the_built_jot_gate(tmp_path: Path):
    # No ladder => the built jot-Screen path (backward-compatible).
    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    r = run_gate(FakeGraph(), tmp_path, "EP-1", jot="j", manifest="m", created=[], backend=b,
                 ts="2026-08-18T10:00:00+00:00")
    assert r.verdict == "PASS"
    assert [j.action for j in read_journal(tmp_path)] == ["gate-resolve"]


def test_ladder_cfg_takes_the_raw_window_path(tmp_path: Path):
    # A ladder cfg + raw_span (the window) => the Screen grounds on the raw window, not the jot.
    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    cfg = LadderConfig(shadow=True, audit_rate=0.0)
    g = FakeGraph()
    e1 = GraphEdge("e1", "a fact", ["EP-1"])
    g.seed(e1)  # created edges live in the engine (spine births them) — gate promotion reads/writes them
    r = run_gate(g, tmp_path, "EP-1", jot="the demoted jot", manifest="e1: a fact",
                 created=[e1], backend=b,
                 ts="2026-08-18T10:00:00+00:00", raw_span="the raw window text",
                 ladder=cfg, rng=random.Random(0), chart=FalsePassChart())
    assert r.verdict == "PASS"
    # the raw window (not the jot) reached the Screen backend
    assert "the raw window text" in b.last["user"]
    assert "the demoted jot" not in b.last["user"]
