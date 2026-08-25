"""drain_once opt-in ladder: default OFF unchanged; ladder=cfg screens on the raw window (§3)."""
from __future__ import annotations

import random
from pathlib import Path

from genesis.episode.ownedfile import EpisodeHeader, write_episode_file
from genesis.extraction.drain import drain_once
from genesis.graph.engine import FakeGraph, GraphEdge
from genesis.inspection.audit import FalsePassChart
from genesis.inspection.ladder import LadderConfig
from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.ledger.store import append, read_all
from genesis.workers.backend import FakeLLMBackend


def _seed_entry(data_root: Path, eid: str = "EP-2026-08-18.0001",
                ts: str = "2026-08-18T10:00:00+00:00") -> LedgerEntry:
    """Seed a legacy copied-episode entry (mirrors test_extraction_drain.py fixture)."""
    write_episode_file(data_root, EpisodeHeader(
        episode_id=eid, session_id="s1", projection="memory-grade",
        captured_at=ts, span_start="2026-08-18T09:00:00+00:00",
        span_end=ts, speakers=["the principal"], source_transcript_ref="r"),
        "the raw window text for the ladder")
    entry = LedgerEntry(
        entry_id=eid, ts=ts, summary="the demoted jot",
        provenance=Provenance(episode_id=eid,
                              span_start="2026-08-18T09:00:00+00:00",
                              span_end=ts, speakers=["the principal"]),
        links=Links(session_id="s1"),
    )
    append(data_root, entry)
    return entry


def test_drain_default_is_unchanged(tmp_path: Path):
    # No ladder param => the built path. Signature smoke: ladder kwarg exists with default None.
    import inspect
    sig = inspect.signature(drain_once)
    assert "ladder" in sig.parameters
    assert sig.parameters["ladder"].default is None
    assert "ride_along_for" in sig.parameters
    assert sig.parameters["ride_along_for"].default is None


def test_drain_with_ladder_screens_on_the_window(tmp_path: Path):
    """The ladder path threads cleanly through drain_once and marks the entry DONE."""
    eid = "EP-2026-08-18.0001"
    ts = "2026-08-18T10:00:00+00:00"
    _seed_entry(tmp_path, eid, ts)

    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    g = FakeGraph()
    g.script_episode(eid, creates=[GraphEdge("e1", "a fact", [eid])], at=ts)

    cfg = LadderConfig(shadow=True, audit_rate=0.0)
    processed = drain_once(tmp_path, g, b, ts=ts,
                           ladder=cfg, rng=random.Random(0), chart=FalsePassChart())
    assert eid in processed
    assert read_all(tmp_path)[0].extracted is Extracted.DONE


def test_drain_window_param_not_clobbered(tmp_path: Path):
    """The detection window=2 param is NOT clobbered by the ladder param."""
    for i in range(1, 4):
        eid = f"EP-2026-08-18.000{i}"
        ts = f"2026-08-18T10:0{i}:00+00:00"
        _seed_entry(tmp_path, eid, ts)

    g = FakeGraph()
    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    cfg = LadderConfig(shadow=True, audit_rate=0.0)
    # window=2 (detection window) limits drain to 2 entries — must NOT be clobbered by ladder
    processed = drain_once(tmp_path, g, b, ts="2026-08-18T10:10:00+00:00",
                           window=2, ladder=cfg, rng=random.Random(0), chart=FalsePassChart())
    assert len(processed) == 2
    still_queued = [e.entry_id for e in read_all(tmp_path) if e.extracted is Extracted.NO]
    assert still_queued == ["EP-2026-08-18.0003"]


def test_drain_ladder_screens_on_episode_content(tmp_path: Path, monkeypatch):
    """The ladder receives episode.content (the raw window) as its window, not the jot."""
    eid = "EP-2026-08-18.0001"
    ts = "2026-08-18T10:00:00+00:00"
    _seed_entry(tmp_path, eid, ts)

    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    g = FakeGraph()
    g.script_episode(eid, creates=[GraphEdge("e1", "a fact", [eid])], at=ts)

    cfg = LadderConfig(shadow=True, audit_rate=0.0)
    drain_once(tmp_path, g, b, ts=ts,
               ladder=cfg, rng=random.Random(0), chart=FalsePassChart())
    # The Screen backend received the raw window text (episode.content), not the jot.
    assert "the raw window text for the ladder" in b.last["user"]
    assert "the demoted jot" not in b.last["user"]


def test_drain_ride_along_for_is_optional(tmp_path: Path):
    """ride_along_for=None (default) => empty ride-along, no error."""
    eid = "EP-2026-08-18.0001"
    ts = "2026-08-18T10:00:00+00:00"
    _seed_entry(tmp_path, eid, ts)

    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    g = FakeGraph()
    g.script_episode(eid, creates=[GraphEdge("e1", "a fact", [eid])], at=ts)

    cfg = LadderConfig(shadow=True, audit_rate=0.0)
    # ride_along_for defaults to None => empty string passed to supervise_commit
    processed = drain_once(tmp_path, g, b, ts=ts,
                           ladder=cfg, rng=random.Random(0), chart=FalsePassChart(),
                           ride_along_for=None)
    assert eid in processed


def test_drain_ride_along_for_callable(tmp_path: Path):
    """ride_along_for(entry) -> str is called per-entry and threaded as ride_along."""
    eid = "EP-2026-08-18.0001"
    ts = "2026-08-18T10:00:00+00:00"
    _seed_entry(tmp_path, eid, ts)

    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    g = FakeGraph()
    g.script_episode(eid, creates=[GraphEdge("e1", "a fact", [eid])], at=ts)

    cfg = LadderConfig(shadow=True, audit_rate=0.0)
    called_with: list[str] = []

    def ride_along_for(entry):
        called_with.append(entry.entry_id)
        return "3-episode ride-along corpus"

    processed = drain_once(tmp_path, g, b, ts=ts,
                           ladder=cfg, rng=random.Random(0), chart=FalsePassChart(),
                           ride_along_for=ride_along_for)
    assert eid in processed
    assert called_with == [eid]  # called once per entry


def test_supervise_commit_ladder_none_unchanged(tmp_path: Path):
    """supervise_commit(ladder=None) => identical to today's built path."""
    from genesis.supervisor.supervise import supervise_commit
    g = FakeGraph()
    g.script_episode("EP-1", creates=[GraphEdge("e1", "a fact", ["EP-1"])],
                     at="2026-08-18T10:00:00+00:00")
    g.add_episode("EP-1", "c")
    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    out = supervise_commit(g, tmp_path, "EP-1", jot="j", manifest="m", backend=b,
                           commit_start="2026-08-18T10:00:00+00:00",
                           commit_end="2026-08-18T10:00:10+00:00",
                           ts="2026-08-18T10:00:11+00:00",
                           ladder=None)
    assert out["screen"] == "PASS"
    assert out["created"] == ["e1"]


def test_supervise_commit_ladder_routes_to_run_gate(tmp_path: Path):
    """supervise_commit(ladder=LadderConfig(...)) => run_gate takes the ladder path."""
    from genesis.supervisor.supervise import supervise_commit
    g = FakeGraph()
    g.script_episode("EP-1", creates=[GraphEdge("e1", "a fact", ["EP-1"])],
                     at="2026-08-18T10:00:00+00:00")
    g.add_episode("EP-1", "c")
    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    cfg = LadderConfig(shadow=True, audit_rate=0.0)
    out = supervise_commit(g, tmp_path, "EP-1", jot="the demoted jot", manifest="e1: a fact",
                           backend=b,
                           commit_start="2026-08-18T10:00:00+00:00",
                           commit_end="2026-08-18T10:00:10+00:00",
                           ts="2026-08-18T10:00:11+00:00",
                           raw_span="the raw window for ladder",
                           ladder=cfg, rng=random.Random(0), chart=FalsePassChart())
    assert out["screen"] == "PASS"
    # The raw window reached the Screen, not the jot
    assert "the raw window for ladder" in b.last["user"]
    assert "the demoted jot" not in b.last["user"]
