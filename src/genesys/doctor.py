"""Startup self-check (spec §4.14, F-GENESYS-06).

Single-writer + no locks means a drain that wedges mid-flight leaves entries stuck at
``in-progress`` with nothing to finish them. On startup, re-queue those (``in-progress
→ no``) so the next drain picks them up. Idempotent (DR-05a re-scan pattern).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from genesys.hooks.wiring import hook_wiring_status
from genesys.ledger.entry import Extracted
from genesys.ledger.store import read_all, update


def doctor_requeue(data_root: Path) -> list[str]:
    requeued: list[str] = []
    for entry in read_all(data_root):
        if entry.extracted is Extracted.IN_PROGRESS:
            entry.extracted = Extracted.NO
            update(data_root, entry)
            requeued.append(entry.entry_id)
    return requeued


@dataclass
class DeadmanReport:
    """F3 deadman (spec §5 "Doctor — … F3 deadman (last-ring timestamp)", §7 item 1)."""

    last_ring_ts: str
    age_hours: float | None
    stale: bool
    wired: dict[str, bool] | None


def doctor_deadman(data_root: Path, *, now: str, threshold_hours: float = 24.0,
                   settings_path: Path | None = None) -> DeadmanReport:
    """Report last-ring age + hook-wiring status; loud (stale=True) when capture is silent.

    Pure read; `now` is clock-injected (no wall-clock here). A no-ring ledger is the
    loudest signal (capture never ran) -> stale=True. Beyond threshold_hours -> stale.
    """
    entries = read_all(data_root)  # ts-sorted
    wired = hook_wiring_status(settings_path) if settings_path is not None else None
    if not entries:
        return DeadmanReport(last_ring_ts="", age_hours=None, stale=True, wired=wired)
    last_ts = entries[-1].ts
    # Normalize Z suffix to +00:00 for fromisoformat compatibility
    now_normalized = now.replace('Z', '+00:00') if now.endswith('Z') else now
    last_ts_normalized = last_ts.replace('Z', '+00:00') if last_ts.endswith('Z') else last_ts
    age_hours = (datetime.fromisoformat(now_normalized)
                 - datetime.fromisoformat(last_ts_normalized)).total_seconds() / 3600.0
    return DeadmanReport(last_ring_ts=last_ts, age_hours=age_hours,
                         stale=age_hours >= threshold_hours, wired=wired)
