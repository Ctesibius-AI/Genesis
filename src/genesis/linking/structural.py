"""Structural entry linking at save (spec §4.6, DR-09).

Deterministic, ledger-authoritative: derive `prev` from the immediately-prior committed
entry (same session preferred) and backfill that entry's `next` in place. Never waits for a
future entry (DR-09) — it only looks back over what is already committed.
"""

from __future__ import annotations

from pathlib import Path

from genesis.ledger.entry import LedgerEntry
from genesis.ledger.store import read_all, update


def _prior(entries: list[LedgerEntry], entry: LedgerEntry) -> LedgerEntry | None:
    earlier = [e for e in entries
               if e.entry_id != entry.entry_id and (e.ts, e.entry_id) < (entry.ts, entry.entry_id)]
    if not earlier:
        return None
    same_session = [e for e in earlier if e.links.session_id == entry.links.session_id]
    pool = same_session if same_session else earlier
    return max(pool, key=lambda e: (e.ts, e.entry_id))


def apply_structural_links(data_root: Path, entry: LedgerEntry) -> None:
    prior = _prior(read_all(data_root), entry)
    if prior is None:
        return
    entry.links.prev = prior.entry_id
    if prior.links.next != entry.entry_id:
        prior.links.next = entry.entry_id
        update(data_root, prior)
