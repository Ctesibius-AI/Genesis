"""Console views — health strip + security/infra (spec §14 D-QA-3, §10 metrics).

Read-only folds of the grade-1 journal. The Security view shows scrub/redact events (metadata
only — the journal carries no secret). Infra shows worker/lock/backlog events.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from genesys.journal.journal import JournalEntry, read_journal

_SECURITY = {"scrub", "redact", "redact-cascade"}
_INFRA = {"worker-error", "lock-violation", "backlog-breach"}


@dataclass
class Health:
    commits: int
    flag_rate: float
    verdicts: int
    reverts: int
    worker_errors: int


def _counts(journal: list[JournalEntry]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for j in journal:
        counts[j.action] = counts.get(j.action, 0) + 1
    return counts


def health_strip(data_root: Path) -> Health:
    c = _counts(read_journal(data_root))
    flags = c.get("gate-flag", 0)
    gate_events = flags + c.get("gate-resolve", 0)
    return Health(
        commits=gate_events,
        flag_rate=(flags / gate_events) if gate_events else 0.0,
        verdicts=c.get("verdict", 0),
        reverts=c.get("revert", 0),
        worker_errors=c.get("worker-error", 0),
    )


def security_view(data_root: Path) -> list[JournalEntry]:
    return [j for j in read_journal(data_root) if j.action in _SECURITY]


def infra_view(data_root: Path) -> list[JournalEntry]:
    return [j for j in read_journal(data_root) if j.action in _INFRA]
