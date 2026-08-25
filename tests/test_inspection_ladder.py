"""The ladder composer (spec §3): Tier 0 -> size guard -> Tier 1 raw Screen -> Tier 2 + audit.

Fake backend only. Shadow vs live, size-route, and the audit sampler are all asserted with an
injected seeded RNG so the decisions are deterministic.
"""
from __future__ import annotations

import random
from pathlib import Path

from genesis.graph.engine import FakeGraph, GraphEdge
from genesis.inspection.audit import FalsePassChart
from genesis.inspection.ladder import LadderConfig, run_ladder
from genesis.journal.journal import read_journal
from genesis.workers.backend import FakeLLMBackend


def _edge(eid, fact):
    return GraphEdge(edge_id=eid, fact=fact, episodes=["EP-1"])


def _run(tmp_path, backend, *, created, window, cfg, rng=None, chart=None, ride_along=""):
    return run_ladder(FakeGraph(), tmp_path, "EP-1", window=window,
                      manifest="e1: a fact", created=created, backend=backend,
                      ts="2026-08-18T10:00:00+00:00", ride_along=ride_along,
                      cfg=cfg, rng=rng or random.Random(0), chart=chart or FalsePassChart())


def test_screen_pass_no_audit_does_not_reach_the_verifier(tmp_path: Path):
    # rate 0 => never audited; a clean PASS resolves at Tier 1.
    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    cfg = LadderConfig(shadow=True, audit_rate=0.0)
    r = _run(tmp_path, b, created=[_edge("e1", "a fact")], window="a fact", cfg=cfg)
    assert r.verdict == "PASS"
    assert "gate-resolve" in [j.action for j in read_journal(tmp_path)]


def test_screen_flag_routes_to_the_verifier(tmp_path: Path):
    b = FakeLLMBackend('{"verdict": "FLAG", "flags": [{"code": "S1", "artifact": "e1"}], '
                       '"ruling": "OVERRULE", "reasoning": "x"}')
    cfg = LadderConfig(shadow=True, audit_rate=0.0)
    r = _run(tmp_path, b, created=[_edge("e1", "a fact")], window="a fact", cfg=cfg)
    assert r.verdict == "FLAG"
    actions = [j.action for j in read_journal(tmp_path)]
    assert "gate-flag" in actions and "gate-resolve" in actions


def test_shadow_mode_logs_tier0_but_routes_nothing(tmp_path: Path):
    # A hard Tier 0 flag (number absent) in SHADOW mode: logged, but the Screen's PASS stands.
    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    cfg = LadderConfig(shadow=True, audit_rate=0.0)
    r = _run(tmp_path, b, created=[_edge("e1", "it was 999 euros")], window="no number here",
             cfg=cfg)
    assert r.verdict == "PASS"                        # nothing routed
    reasons = [j.reason for j in read_journal(tmp_path)]
    assert "tier0-shadow" in reasons                  # would-be route was logged


def test_live_mode_hard_flag_routes_to_the_verifier(tmp_path: Path):
    b = FakeLLMBackend('{"verdict": "PASS", "flags": [], "ruling": "OVERRULE", "reasoning": "x"}')
    cfg = LadderConfig(shadow=False, audit_rate=0.0)  # LIVE
    r = _run(tmp_path, b, created=[_edge("e1", "it was 999 euros")], window="no number here",
             cfg=cfg)
    actions = [j.action for j in read_journal(tmp_path)]
    assert "gate-flag" in actions                     # hard flag routed despite Screen PASS
    assert "gate-resolve" in actions                  # Verifier actually ran


def test_oversized_window_skips_the_screen_and_verifies(tmp_path: Path):
    b = FakeLLMBackend('{"ruling": "OVERRULE", "reasoning": "x"}')  # only the Verifier is called
    cfg = LadderConfig(shadow=True, audit_rate=0.0, max_window_chars=10)
    r = _run(tmp_path, b, created=[_edge("e1", "f")], window="x" * 50, cfg=cfg)
    actions = [j.action for j in read_journal(tmp_path)]
    assert "gate-flag" in actions                     # size-routed straight to Tier 2


def test_audit_samples_a_pass_into_the_verifier_and_records_false_pass(tmp_path: Path):
    # rate 1.0 => this PASS is always audited; the Verifier UPHOLDS => a Screen false pass.
    b = FakeLLMBackend('{"verdict": "PASS", "flags": [], "ruling": "UPHOLD", '
                       '"remedy": {"action": "none"}, "reasoning": "x"}')
    cfg = LadderConfig(shadow=True, audit_rate=1.0)
    chart = FalsePassChart()
    r = _run(tmp_path, b, created=[_edge("e1", "a fact")], window="a fact", cfg=cfg,
             rng=random.Random(0), chart=chart)
    assert r.verdict == "PASS"
    assert chart.passes == 1 and chart.false_passes == 1
    assert chart.breached(cfg.false_pass_threshold) is True
