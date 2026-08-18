"""Startup self-check (spec §4.14, F-GENESYS-06).

Single-writer + no locks means a drain that wedges mid-flight leaves entries stuck at
``in-progress`` with nothing to finish them. On startup, re-queue those (``in-progress
→ no``) so the next drain picks them up. Idempotent (DR-05a re-scan pattern).
"""

from __future__ import annotations

from pathlib import Path

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
