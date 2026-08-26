"""D-FB-3 gate integrity — Round A acceptance.

Part A: unparseable/garbage Screen output → FLAG (never PASS); Verifier unavailable on a suspicion
path → QUARANTINE (never PASS). Part B: a genuine Screen PASS → CONFIRMED; a non-quarantine Verifier
resolution (incl. post-amend) → CONFIRMED. After a normal extraction, served facts carry NO
[unverified]; "[unverified]" thereafter means exactly "not yet gated".
"""
from __future__ import annotations

import random
from pathlib import Path

from genesis.graph.engine import FakeGraph, GraphEdge, Verdict
from genesis.inspection.audit import FalsePassChart
from genesis.inspection.ladder import LadderConfig, run_ladder
from genesis.recall.verdict import serving_label
from genesis.supervisor.gate import run_gate
from genesis.workers.backend import TIER_OPUS

TS = "2026-08-18T10:00:00+00:00"


class _Tiered:
    """A backend that answers the Screen (Sonnet) and the Verifier (Opus) differently; set
    verify_raises to simulate an unavailable Verifier."""
    def __init__(self, screen_reply: str, verify_reply: str = "", *, verify_raises: bool = False):
        self._screen, self._verify, self._raises = screen_reply, verify_reply, verify_raises
        self.last: dict | None = None

    def complete(self, system: str, user: str, *, model: str) -> str:
        self.last = {"system": system, "user": user, "model": model}
        if model == TIER_OPUS:                      # the Verifier
            if self._raises:
                raise RuntimeError("verifier backend unavailable")
            return self._verify
        return self._screen                         # the Screen


def _ladder(tmp_path, backend, created, *, window="a fact", cfg=None):
    g = FakeGraph()
    for e in created:
        g.seed(e)
    cfg = cfg or LadderConfig(shadow=True, audit_rate=0.0)
    r = run_ladder(g, tmp_path, "EP-1", window=window, manifest="e1: a fact", created=created,
                   backend=backend, ts=TS, cfg=cfg, rng=random.Random(0), chart=FalsePassChart())
    return g, r


# ── Part B: genuine PASS → CONFIRMED, served without [unverified] ─────────────────────────────

def test_genuine_pass_promotes_to_confirmed_and_serves_clean(tmp_path: Path):
    g, r = _ladder(tmp_path, _Tiered('{"verdict": "PASS", "flags": []}'),
                   [GraphEdge("e1", "a fact", ["EP-1"])])
    assert r.verdict == "PASS"
    assert g.get("e1").verdict is Verdict.CONFIRMED
    assert serving_label(g.get("e1")) == ""        # AC: served fact carries NO [unverified]


def test_flag_then_verifier_overrule_promotes_to_confirmed(tmp_path: Path):
    backend = _Tiered('{"verdict": "FLAG", "flags": [{"code": "S1", "artifact": "e1"}]}',
                      '{"ruling": "OVERRULE", "remedy": {"action": "none"}}')
    g, r = _ladder(tmp_path, backend, [GraphEdge("e1", "a fact", ["EP-1"])])
    # A non-quarantine Verifier resolution → CONFIRMED (incl. the OVERRULE-no-remedy case).
    assert g.get("e1").verdict is Verdict.CONFIRMED


# ── Part A: Verifier unavailable on a suspicion path → QUARANTINE, never PASS/CONFIRMED ────────

def test_verifier_unavailable_on_flag_quarantines_ladder(tmp_path: Path):
    backend = _Tiered('{"verdict": "FLAG", "flags": [{"code": "S1", "artifact": "e1"}]}',
                      verify_raises=True)
    g, _ = _ladder(tmp_path, backend, [GraphEdge("e1", "a fact", ["EP-1"])])
    v = g.get("e1").verdict
    assert v is Verdict.QUARANTINED
    assert v is not Verdict.CONFIRMED and v is not Verdict.PROVISIONAL  # never a quiet pass


def test_verifier_unavailable_on_flag_quarantines_nonladder(tmp_path: Path):
    backend = _Tiered('{"verdict": "FLAG", "flags": [{"code": "S1", "artifact": "e1"}]}',
                      verify_raises=True)
    g = FakeGraph()
    e1 = GraphEdge("e1", "a fact", ["EP-1"])
    g.seed(e1)
    run_gate(g, tmp_path, "EP-1", jot="j", manifest="m", created=[e1], backend=backend,
             ts=TS, raw_span="a fact")   # ladder=None → the non-ladder gate path
    assert g.get("e1").verdict is Verdict.QUARANTINED


# ── Part B fence: a persona-anchor amend stays QUARANTINED, never promoted ─────────────────────

def test_persona_anchor_amend_stays_quarantined_not_confirmed(tmp_path: Path):
    backend = _Tiered('{"verdict": "FLAG", "flags": [{"code": "S3", "artifact": "e1"}]}',
                      '{"ruling": "UPHOLD", "remedy": {"action": "amend", "target": "e1", '
                      '"content": "rewritten"}}')
    # C3 = persona anchor: the amend is fenced to quarantine (never rewrites the anchor).
    g, _ = _ladder(tmp_path, backend, [GraphEdge("e1", "Trait: stubborn", ["EP-1"], class_="C3")])
    assert g.get("e1").verdict is Verdict.QUARANTINED   # fenced, NOT confirmed


# ── Part A integration: garbage Screen lands FLAG/QUARANTINE, never PASS ───────────────────────

def test_garbage_screen_never_passes(tmp_path: Path):
    # Screen returns unparseable garbage → screen_raw defaults to FLAG → routes to the Verifier,
    # which here is unavailable → QUARANTINE. Never a silent PASS/CONFIRMED.
    backend = _Tiered("not json at all", verify_raises=True)
    g, _ = _ladder(tmp_path, backend, [GraphEdge("e1", "a fact", ["EP-1"])])
    assert g.get("e1").verdict is Verdict.QUARANTINED
