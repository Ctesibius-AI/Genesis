from __future__ import annotations

from pathlib import Path

from genesis.episode.ownedfile import EpisodeHeader, write_episode_file
from genesis.extraction.drain import drain_once
from genesis.graph.engine import FakeGraph, GraphEdge
from genesis.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesis.ledger.store import append, read_all
from genesis.workers.backend import FakeLLMBackend


def _seed(tmp_path: Path, eid: str, ts: str):
    write_episode_file(tmp_path, EpisodeHeader(
        episode_id=eid, session_id="s", projection="memory-grade", captured_at=ts,
        span_start="a", span_end="b", speakers=["the principal"], source_transcript_ref="r"),
        f"raw for {eid}")
    append(tmp_path, LedgerEntry(entry_id=eid, ts=ts, summary=f"jot {eid}",
           provenance=Provenance(eid, "a", "b", ["the principal"]), links=Links(session_id="s")))


def test_drain_processes_queue_and_marks_done(tmp_path: Path):
    _seed(tmp_path, "EP-2026-08-17.0001", "2026-08-17T10:00:00+00:00")
    g = FakeGraph()
    g.script_episode("EP-2026-08-17.0001",
                     creates=[GraphEdge("e1", "decided X", ["EP-2026-08-17.0001"])],
                     at="2026-08-17T10:05:00+00:00")
    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    processed = drain_once(tmp_path, g, b, ts="2026-08-17T10:05:00+00:00")
    assert processed == ["EP-2026-08-17.0001"]
    by_id = {e.entry_id: e for e in read_all(tmp_path)}
    assert by_id["EP-2026-08-17.0001"].extracted is Extracted.DONE  # flipped no->done


def test_drain_respects_window(tmp_path: Path):
    for i in range(1, 4):
        _seed(tmp_path, f"EP-2026-08-17.000{i}", f"2026-08-17T10:0{i}:00+00:00")
    g = FakeGraph()
    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    processed = drain_once(tmp_path, g, b, ts="2026-08-17T10:10:00+00:00", window=2)
    assert len(processed) == 2  # only the window
    still_queued = [e.entry_id for e in read_all(tmp_path) if e.extracted.value == "no"]
    assert still_queued == ["EP-2026-08-17.0003"]  # third left queued
