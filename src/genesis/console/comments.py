"""Comment channel — the one bounded capture surface (spec §14 D-QA-4).

A comment is feedback ABOUT the machinery; it NEVER becomes a memory fact (D-QA-1/D-QA-6). It is
a capture surface, so scrub-at-capture (DR-38 / D-QA-4a) runs before the append. Comments are read
ON REQUEST only (D-QA-5) — an explicit call, never automatic.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from genesis.scrub.scrubber import scrub_text


@dataclass
class Comment:
    ts: str
    episode_id: str
    card_section: str
    comment: str
    verdict_hint: str | None = None


def _path(data_root: Path) -> Path:
    return Path(data_root) / "qa_comments.jsonl"


def add_comment(data_root: Path, *, ts: str, episode_id: str, card_section: str,
                comment: str, verdict_hint: str | None = None) -> Comment:
    c = Comment(ts=ts, episode_id=episode_id, card_section=card_section,
                comment=scrub_text(comment).text, verdict_hint=verdict_hint)  # DR-38 scrub
    path = _path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(c), ensure_ascii=False, separators=(",", ":")) + "\n")
    return c


def read_comments(data_root: Path) -> list[Comment]:
    path = _path(data_root)
    if not path.exists():
        return []
    return [Comment(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
