"""Console views — health strip + security/infra (spec §14 D-QA-3, §10 metrics).

Read-only folds of the grade-1 journal. The Security view shows scrub/redact events (metadata
only — the journal carries no secret). Infra shows worker/lock/backlog events.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from genesis.doctor import doctor_deadman
from genesis.journal.journal import JournalEntry, read_journal

_SECURITY = {"scrub", "redact", "redact-cascade"}
_INFRA = {"worker-error", "lock-violation", "stale-lock-cleared", "backlog-breach"}


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


@dataclass
class DeadmanStrip:
    last_ring_ts: str
    age_hours: float | None
    stale: bool
    wired: dict[str, bool] | None
    alerts: list[str]


def deadman_strip(data_root: Path, *, now: str, threshold_hours: float = 24.0,
                  settings_path: Path | None = None) -> DeadmanStrip:
    """F3 loud surface: fold the deadman report into console alerts (spec §7 item 1)."""
    r = doctor_deadman(data_root, now=now, threshold_hours=threshold_hours,
                       settings_path=settings_path)
    alerts: list[str] = []
    if r.stale:
        if r.age_hours is None:
            alerts.append("CAPTURE STALE: no capture ring on record")
        else:
            alerts.append(f"CAPTURE STALE: no ring in {r.age_hours:.1f}h")
    if r.wired is not None:
        alerts.extend(f"HOOK UNWIRED: {e}" for e, ok in r.wired.items() if not ok)
    return DeadmanStrip(last_ring_ts=r.last_ring_ts, age_hours=r.age_hours,
                        stale=r.stale, wired=r.wired, alerts=alerts)
