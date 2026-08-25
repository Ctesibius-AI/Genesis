"""The grade-1 Supervisor journal (spec §8.7, DR-26).

Append-only, per-day JSONL under <data_root>/journal/YYYY-MM-DD.jsonl. Every Supervisor
action emits a typed entry whose `action` is in the §8.7 union. Replayable; never deleted.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

JOURNAL_ACTIONS: frozenset[str] = frozenset({
    # supervision (hot lane)
    "verdict", "revert", "supersede", "contest", "ask-queued", "ask-resolved",
    "class-migrate", "merge", "gate-flag", "gate-resolve", "day-processed",
    # class auditor
    "class-audit", "drift-report", "fragment-merge", "example-conflict",
    # persona layer + calibration/constitution — REMOVED with the persona profiler (D-GCW-6 / BT-4b)
    # security
    "scrub", "redact", "redact-cascade",
    # recovery
    "snapshot", "snapshot-verify", "restore", "rebuild",
    # infra
    "worker-error", "lock-violation", "stale-lock-cleared",
})


@dataclass
class JournalEntry:
    ts: str
    action: str
    scope: str                       # episode|day id
    target: str | None = None        # edge|node id
    class_: str | None = None        # serialized as "class"
    before: object = None
    after: object = None
    reason: str | None = None
    evidence: list[str] = field(default_factory=list)
    author: str | None = None
    worker_findings_ref: str | None = None


def journal_dir(data_root: Path) -> Path:
    return Path(data_root) / "journal"


def journal_path(data_root: Path, ts: str) -> Path:
    return journal_dir(data_root) / f"{ts[:10]}.jsonl"


def to_jsonl(entry: JournalEntry) -> str:
    d = asdict(entry)
    d["class"] = d.pop("class_")
    return json.dumps(d, ensure_ascii=False, separators=(",", ":"))


def from_jsonl(line: str) -> JournalEntry:
    d = json.loads(line)
    d["class_"] = d.pop("class", None)
    return JournalEntry(**d)


def append_journal(data_root: Path, entry: JournalEntry) -> Path:
    if entry.action not in JOURNAL_ACTIONS:
        raise ValueError(f"unknown journal action: {entry.action!r}")
    path = journal_path(data_root, entry.ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(to_jsonl(entry) + "\n")
    return path


def read_journal(data_root: Path) -> list[JournalEntry]:
    d = journal_dir(data_root)
    if not d.is_dir():
        return []
    entries: list[JournalEntry] = []
    for path in sorted(d.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(from_jsonl(line))
    entries.sort(key=lambda e: e.ts)
    return entries
