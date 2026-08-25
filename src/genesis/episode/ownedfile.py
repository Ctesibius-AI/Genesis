"""Owned verbatim episode file (spec §4.9, App A.4.2, DR-24).

Written AT SAVE, before the ledger entry. One JSON header line, a blank line, then the
DR-38-scrubbed raw span as the body — human-readable and diffable (DR-15). Redactions
are recorded in the header so the file is honest about what was removed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from genesis.ids import episodes_dir
from genesis.scrub.scrubber import scrub_text


@dataclass
class EpisodeHeader:
    episode_id: str
    session_id: str
    projection: str  # "memory-grade" | "flight-recorder"
    captured_at: str
    span_start: str
    span_end: str
    speakers: list[str] = field(default_factory=list)
    source_transcript_ref: str = ""
    redactions: list[dict] = field(default_factory=list)


def write_episode_file(data_root: Path, header: EpisodeHeader, raw_span: str) -> Path:
    scrubbed = scrub_text(raw_span)
    header.redactions = [asdict(m) for m in scrubbed.matches]
    eps = episodes_dir(data_root)
    eps.mkdir(parents=True, exist_ok=True)
    path = eps / f"{header.episode_id}.md"
    header_line = json.dumps(asdict(header), ensure_ascii=False, separators=(",", ":"))
    path.write_text(f"{header_line}\n\n{scrubbed.text}", encoding="utf-8")
    return path


def read_episode_file(data_root: Path, episode_id: str) -> tuple["EpisodeHeader", str]:
    """Read an owned episode file back into (header, raw body). Inverse of write_episode_file."""
    path = episodes_dir(data_root) / f"{episode_id}.md"
    header_line, _blank, body = path.read_text(encoding="utf-8").split("\n", 2)
    return EpisodeHeader(**json.loads(header_line)), body
