from __future__ import annotations

from pathlib import Path

from genesis.episode.ownedfile import EpisodeHeader, write_episode_file
from genesis.extraction.analyst import Episode, prepare_episode
from genesis.ledger.entry import LedgerEntry, Links, Provenance


def _seed(tmp_path: Path):
    eid = "EP-2026-08-17.0001"
    write_episode_file(tmp_path, EpisodeHeader(
        episode_id=eid, session_id="s", projection="memory-grade",
        captured_at="2026-08-17T10:00:00+00:00", span_start="a", span_end="b",
        speakers=["the principal"], source_transcript_ref="ref"), "raw span body")
    return LedgerEntry(entry_id=eid, ts="2026-08-17T10:00:00+00:00", summary="a quick jot",
                       provenance=Provenance(eid, "a", "b", ["the principal"]), links=Links(session_id="s"))


def test_prepare_reads_owned_body_and_uses_summary_as_jot(tmp_path: Path):
    ep = prepare_episode(tmp_path, _seed(tmp_path))
    assert isinstance(ep, Episode)
    assert ep.episode_id == "EP-2026-08-17.0001"
    assert ep.content.strip() == "raw span body"   # the owned raw, not the summary
    assert ep.jot == "a quick jot"
