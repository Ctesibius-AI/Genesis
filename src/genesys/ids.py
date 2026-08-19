"""Deterministic episode / ledger-entry IDs (spec App A.4.1).

ID = ``EP-YYYY-MM-DD.NNNN`` — date of the save + a zero-padded, per-day sequence.
No randomness: the sequence is derived by scanning existing episodes, so a rebuild
from the same owned files produces the same IDs (idempotent, DR-25/DR-26).
"""

from __future__ import annotations

import re
from pathlib import Path

EPISODE_ID_RE = re.compile(r"^EP-(\d{4}-\d{2}-\d{2})\.(\d{4})$")


def format_episode_id(date: str, seq: int) -> str:
    return f"EP-{date}.{seq:04d}"


def parse_episode_id(eid: str) -> tuple[str, int]:
    m = EPISODE_ID_RE.match(eid)
    if not m:
        raise ValueError(f"not a valid episode id: {eid!r}")
    return m.group(1), int(m.group(2))


def next_sequence(existing_ids: list[str], date: str) -> int:
    seqs = []
    for eid in existing_ids:
        m = EPISODE_ID_RE.match(eid)
        if m and m.group(1) == date:
            seqs.append(int(m.group(2)))
    return (max(seqs) + 1) if seqs else 1


def episodes_dir(data_root: Path) -> Path:
    return Path(data_root) / "episodes"


def existing_episode_ids(data_root: Path) -> list[str]:
    d = episodes_dir(data_root)
    if not d.is_dir():
        return []
    return [p.stem for p in d.glob("EP-*.md")]


def existing_ledger_entry_ids(data_root: Path) -> list[str]:
    """Return all entry_ids recorded in the ledger (complements existing_episode_ids).

    Annotations write no episode file, so their IDs are invisible to
    existing_episode_ids. Scanning the ledger ensures the per-day sequence counter
    never repeats, even across a mix of copy-path episodes and WAL annotations.
    """
    from genesys.ledger.store import read_all  # noqa: PLC0415 — local to avoid circular

    return [e.entry_id for e in read_all(data_root)]


def next_episode_id(data_root: Path, date: str) -> str:
    """Return the next unique episode/annotation ID for *date*.

    Scans both episode files (copy path) and ledger entries (annotation path) so
    the per-day sequence is strictly monotone regardless of which path wrote last.
    """
    all_ids = existing_episode_ids(data_root) + existing_ledger_entry_ids(data_root)
    return format_episode_id(date, next_sequence(all_ids, date))
