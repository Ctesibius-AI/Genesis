"""BT-2 / AC-D1: the SessionStart drain is bounded (count OR time), then defers the remainder.

Literalism guard: the time bound forbids the block-forever drain — a backlog past the budget
drains only a prefix and leaves the rest queued (Extracted.NO) for the next start.
"""
from __future__ import annotations

from pathlib import Path

from genesys.episode.ownedfile import EpisodeHeader, write_episode_file
from genesys.extraction.drain import drain_once
from genesys.graph.engine import FakeGraph
from genesys.ledger.entry import Extracted, LedgerEntry, Links, Provenance
from genesys.ledger.store import append, read_all
from genesys.workers.backend import FakeLLMBackend


def _seed(root: Path, eid: str, ts: str):
    write_episode_file(root, EpisodeHeader(
        episode_id=eid, session_id="s", projection="memory-grade", captured_at=ts,
        span_start="a", span_end="b", speakers=["the principal"], source_transcript_ref="r"),
        f"raw for {eid}")
    append(root, LedgerEntry(entry_id=eid, ts=ts, summary=f"jot {eid}",
           provenance=Provenance(eid, "a", "b", ["the principal"]), links=Links(session_id="s")))


def _clock(seq):
    it = iter(seq)
    last = [0.0]
    def clock():
        try:
            last[0] = float(next(it))
        except StopIteration:
            pass
        return last[0]
    return clock


def test_time_budget_drains_prefix_and_defers_rest(tmp_path: Path):
    for i in range(1, 4):
        _seed(tmp_path, f"EP-2026-08-26.000{i}", f"2026-08-26T10:0{i}:00+00:00")
    g = FakeGraph()
    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    # clock(): start=0 ; iter1 check=0 (proceed) ; iter2 check=100 (>=budget 10 -> break)
    processed = drain_once(tmp_path, g, b, ts="2026-08-26T10:10:00+00:00",
                           time_budget_s=10, clock=_clock([0, 0, 100]))
    assert processed == ["EP-2026-08-26.0001"]  # only the prefix drained
    still_queued = sorted(e.entry_id for e in read_all(tmp_path)
                          if e.extracted is Extracted.NO)
    assert still_queued == ["EP-2026-08-26.0002", "EP-2026-08-26.0003"]  # deferred


def test_no_budget_drains_all_within_window(tmp_path: Path):
    for i in range(1, 3):
        _seed(tmp_path, f"EP-2026-08-26.010{i}", f"2026-08-26T11:0{i}:00+00:00")
    g = FakeGraph()
    b = FakeLLMBackend('{"verdict": "PASS", "flags": []}')
    processed = drain_once(tmp_path, g, b, ts="2026-08-26T11:10:00+00:00")  # no time_budget_s
    assert len(processed) == 2
