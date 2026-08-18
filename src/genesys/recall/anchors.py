"""Code-inserted diary anchors (spec §4.7b; App E delta — ratify with App E, not separately).

The diary is App-E LLM-synthesised — a summariser, not a knower — and hard-excludes perceives /
soul / raw. So anchor references are CODE-INSERTED post-synthesis, NEVER LLM-emitted (the
summariser would hallucinate ids). After compile_diary returns a Briefing, resolve_anchors reads
the ledger links (references / same_topic / supersedes -> episodes) and attach_anchors marks ONLY
anchors whose name already appears in the briefing — content the diary is already allowed to
contain. The Briefing is regenerated, never truth (DR-10): attach_anchors returns a new object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from genesys.diary.briefing import Briefing
from genesys.ledger.store import read_all

ANCHORS_SECTION = "ANCHORS"


@dataclass
class DiaryAnchor:
    anchor: str
    episode_ids: list[str] = field(default_factory=list)


def resolve_anchors(data_root: Path, *, session_id: str | None = None) -> list[DiaryAnchor]:
    anchors: list[DiaryAnchor] = []
    for e in read_all(data_root):
        if session_id is not None and e.links.session_id != session_id:
            continue
        linked = [*e.links.references, *e.links.same_topic, *e.links.supersedes]
        if not linked:
            continue
        eids = list(dict.fromkeys([e.entry_id, *linked]))  # dedupe, preserve order
        anchors.append(DiaryAnchor(e.summary, eids))
    return anchors


def attach_anchors(briefing: Briefing, anchors: list[DiaryAnchor]) -> Briefing:
    body = briefing.render()
    lines = [f"- {a.anchor} -> {', '.join(a.episode_ids)}"
             for a in anchors if a.anchor and a.anchor in body]
    sections = dict(briefing.sections)  # copy — never mutate the original (DR-10)
    if lines:
        sections[ANCHORS_SECTION] = "\n".join(lines)
    return Briefing(sections=sections)
