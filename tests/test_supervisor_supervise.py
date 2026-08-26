from __future__ import annotations

from pathlib import Path

from genesis.graph.engine import FakeGraph, GraphEdge, Verdict
from genesis.supervisor.supervise import supervise_commit
from genesis.workers.backend import FakeLLMBackend


def test_supervise_commit_full_sequence(tmp_path: Path):
    g = FakeGraph()
    g.seed(GraphEdge("old", "old", ["EP-0"], class_="C3"))
    g.script_episode("EP-1", creates=[GraphEdge("new", "new", ["EP-1"])],
                     expires=["old"], at="2026-08-17T10:00:03+00:00")
    g.add_episode("EP-1", "c")
    # Screen PASS + Judge REVERT: one canned reply valid for both parsers.
    b = FakeLLMBackend('{"verdict": "PASS", "flags": [], "recommendation": "REVERT", '
                       '"independent_occurrences": 1, "stated_update": false, "ask_window": false, '
                       '"reasoning": "one"}')
    out = supervise_commit(g, tmp_path, "EP-1", jot="j", manifest="m", backend=b,
                           commit_start="2026-08-17T10:00:00+00:00",
                           commit_end="2026-08-17T10:00:10+00:00", ts="2026-08-17T10:00:11+00:00")
    assert out["created"] == ["new"]
    assert out["invalidated"] == ["old"]
    assert out["reverted"] == ["old"]                 # Judge said REVERT → reopened
    # D-FB-3(b): a genuine Screen PASS promotes the created edge PROVISIONAL → CONFIRMED (the gate's
    # judgment now means something downstream; recall stops labelling it "[unverified]").
    assert g.get("new").verdict is Verdict.CONFIRMED
    assert g.get("old").contested is True             # reverted
