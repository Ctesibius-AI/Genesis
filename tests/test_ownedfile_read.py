from __future__ import annotations

from pathlib import Path

from genesys.episode.ownedfile import EpisodeHeader, read_episode_file, write_episode_file


def _h(eid="EP-2026-08-17.0001") -> EpisodeHeader:
    return EpisodeHeader(episode_id=eid, session_id="s", projection="memory-grade",
                         captured_at="2026-08-17T10:00:00+00:00",
                         span_start="2026-08-17T09:58:00+00:00", span_end="2026-08-17T10:00:00+00:00",
                         speakers=["the principal"], source_transcript_ref="ref")


def test_read_round_trips_header_and_body(tmp_path: Path):
    write_episode_file(tmp_path, _h(), "the raw discussion body")
    header, body = read_episode_file(tmp_path, "EP-2026-08-17.0001")
    assert header.episode_id == "EP-2026-08-17.0001"
    assert body.strip() == "the raw discussion body"
