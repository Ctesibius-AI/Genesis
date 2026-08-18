from __future__ import annotations

import json
from pathlib import Path

from genesys.episode.ownedfile import EpisodeHeader, write_episode_file


def _header(eid="EP-2026-08-17.0001") -> EpisodeHeader:
    return EpisodeHeader(
        episode_id=eid,
        session_id="sess-1",
        projection="memory-grade",
        captured_at="2026-08-17T10:00:00+00:00",
        span_start="2026-08-17T09:58:00+00:00",
        span_end="2026-08-17T10:00:00+00:00",
        speakers=["the principal", "Daimon"],
        source_transcript_ref="~/.claude/projects/x/sess-1.jsonl#0-100",
    )


def test_writes_file_named_by_episode_id(tmp_path: Path):
    path = write_episode_file(tmp_path, _header(), "we chose FalkorDB Lite")
    assert path == tmp_path / "episodes" / "EP-2026-08-17.0001.md"
    assert path.exists()


def test_header_is_first_json_line_then_body(tmp_path: Path):
    path = write_episode_file(tmp_path, _header(), "hello world")
    header_line, _blank, body = path.read_text(encoding="utf-8").split("\n", 2)
    assert json.loads(header_line)["episode_id"] == "EP-2026-08-17.0001"
    assert body.strip() == "hello world"


def test_raw_span_is_scrubbed_and_redactions_recorded(tmp_path: Path):
    header = _header()
    secret = "export API_KEY=sk-abcdef0123456789abcdef0123"
    path = write_episode_file(tmp_path, header, secret)
    text = path.read_text(encoding="utf-8")
    assert "sk-abcdef0123456789abcdef0123" not in text  # scrubbed before first write
    assert "<redacted:secret" in text
    assert len(header.redactions) >= 1  # recorded in the header
