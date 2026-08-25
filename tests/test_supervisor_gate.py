from __future__ import annotations

from pathlib import Path

from genesis.graph.engine import FakeGraph, GraphEdge, Verdict
from genesis.journal.journal import read_journal
from genesis.supervisor.gate import apply_remedy, is_persona_anchor, run_gate
from genesis.workers.backend import FakeLLMBackend
from genesis.workers.verifier import VerifierRemedy


def test_persona_anchor_detection():
    assert is_persona_anchor(GraphEdge("e", "f", ["EP-1"], class_="C4")) is True
    assert is_persona_anchor(GraphEdge("e", "f", ["EP-1"], class_="C1")) is False


def test_remedy_fence_quarantines_persona_instead_of_amending(tmp_path: Path):
    g = FakeGraph()
    e = GraphEdge("e1", "he is thorough", ["EP-1"], class_="C3")
    g.seed(e)
    out = apply_remedy(g, tmp_path, e, VerifierRemedy("amend", "e1", "rewritten persona"),
                       ts="2026-08-17T10:00:00+00:00")
    assert out == "quarantined"
    assert g.get("e1").verdict is Verdict.QUARANTINED
    assert g.get("e1").fact == "he is thorough"  # NEVER rewritten


def test_screen_pass_journals_gate_resolve_no_verifier(tmp_path: Path):
    g = FakeGraph()
    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    r = run_gate(g, tmp_path, "EP-1", jot="j", manifest="m", created=[], backend=b,
                 ts="2026-08-17T10:00:00+00:00")
    assert r.verdict == "PASS"
    assert [j.action for j in read_journal(tmp_path)] == ["gate-resolve"]


def test_screen_major_journals_gate_flag(tmp_path: Path):
    g = FakeGraph()
    # A backend that returns FLAG for the screen; the Verifier reply is also this fake — so
    # supply a reply the code will parse for BOTH calls: use two backends via a small shim.
    screen_b = FakeLLMBackend('{"verdict": "FLAG", "flags": [{"code": "S1", "artifact": "e1", "jot_evidence": "x"}]}')
    # run_gate uses one backend for both screen and verify; give a reply valid for verify too is
    # impossible with a single canned string — so this test only asserts the gate-flag journal on
    # the FLAG path by using a backend whose reply is valid JSON for the screen and yields an
    # OVERRULE verify (no remedy). Use a reply that both parsers accept:
    b = FakeLLMBackend('{"verdict": "FLAG", "flags": [], "ruling": "OVERRULE", "reasoning": "x"}')
    run_gate(g, tmp_path, "EP-1", jot="j", manifest="m", created=[], backend=b,
             ts="2026-08-17T10:00:00+00:00", raw_span="raw", contract="rules")
    actions = [j.action for j in read_journal(tmp_path)]
    assert "gate-flag" in actions
    assert "gate-resolve" in actions


def test_persona_anchor_by_fact_substring(tmp_path: Path):
    # Trait:/Value: substring fallback fences even without C3/C4 class.
    assert is_persona_anchor(GraphEdge("e", "Trait: diligent", ["EP-1"], class_="C1")) is True
