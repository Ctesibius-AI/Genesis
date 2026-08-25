"""The activity-log ledger entry (spec App A.4.3, §4.2).

Permanent, date-indexed, append-only at the ledger level (DR-29). An entry's mutable
fields (``extracted``, ``enrichment``) update in place (DR-20); the entry is never deleted.
Serialized one-per-line as JSONL.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum


class Extracted(str, Enum):
    NO = "no"  # queued: not yet extracted
    IN_PROGRESS = "in-progress"
    DONE = "done"


@dataclass
class Provenance:
    episode_id: str
    span_start: str
    span_end: str
    speakers: list[str] = field(default_factory=list)


@dataclass
class Links:
    prev: str | None = None
    next: str | None = None
    session_id: str | None = None
    continues: str | None = None
    references: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    same_topic: list[str] = field(default_factory=list)
    caused_by: list[str] = field(default_factory=list)


@dataclass
class LedgerEntry:
    entry_id: str
    ts: str
    summary: str
    provenance: Provenance
    links: Links
    extracted: Extracted = Extracted.NO
    enrichment: dict | None = None


def to_jsonl(entry: LedgerEntry) -> str:
    d = asdict(entry)
    d["extracted"] = entry.extracted.value
    return json.dumps(d, ensure_ascii=False, separators=(",", ":"))


def from_jsonl(line: str) -> LedgerEntry:
    d = json.loads(line)
    return LedgerEntry(
        entry_id=d["entry_id"],
        ts=d["ts"],
        summary=d["summary"],
        provenance=Provenance(**d["provenance"]),
        links=Links(**d["links"]),
        extracted=Extracted(d["extracted"]),
        enrichment=d.get("enrichment"),
    )
