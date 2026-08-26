"""The permanent activity-log ledger (spec §4.2, DR-29).

Month-indexed JSONL under ``<data_root>/ledger/YYYY-MM.jsonl``. Entries are never
deleted; ``update`` rewrites a month file with one entry's line replaced (in-place
mutable fields only, DR-20). ``read_all`` returns current state in ``ts`` order.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from genesis.ledger.entry import LedgerEntry, from_jsonl, to_jsonl


def _atomic_write(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically (F-05.3): a same-dir tmp + ``os.replace``.

    A plain full-file rewrite that is interrupted mid-write (crash/kill/power loss) can leave a
    truncated month file — destroying an entire month of ledger history. os.replace is atomic on
    POSIX: readers see either the old file or the fully-written new one, never a partial. fsync the
    tmp before the swap so the bytes are durable, not just visible.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def ledger_dir(data_root: Path) -> Path:
    return Path(data_root) / "ledger"


def month_path(data_root: Path, ts: str) -> Path:
    # ts is ISO-8601; the month key is its first 7 chars, "YYYY-MM".
    return ledger_dir(data_root) / f"{ts[:7]}.jsonl"


def append(data_root: Path, entry: LedgerEntry) -> Path:
    path = month_path(data_root, entry.ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(to_jsonl(entry) + "\n")
    return path


def read_all(data_root: Path) -> list[LedgerEntry]:
    d = ledger_dir(data_root)
    if not d.is_dir():
        return []
    entries: list[LedgerEntry] = []
    for path in sorted(d.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(from_jsonl(line))
    entries.sort(key=lambda e: e.ts)
    return entries


def read_since(data_root: Path, since_iso: str) -> list[LedgerEntry]:
    since = datetime.fromisoformat(since_iso)
    return [e for e in read_all(data_root) if datetime.fromisoformat(e.ts) >= since]


def update(data_root: Path, entry: LedgerEntry) -> None:
    path = month_path(data_root, entry.ts)
    if not path.exists():
        raise FileNotFoundError(f"no ledger month file for {entry.entry_id}")
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    replaced = False
    for line in lines:
        if line.strip() and from_jsonl(line).entry_id == entry.entry_id:
            out.append(to_jsonl(entry))
            replaced = True
        elif line.strip():
            out.append(line)
    if not replaced:
        raise KeyError(f"entry not found for update: {entry.entry_id}")
    _atomic_write(path, "\n".join(out) + "\n")  # F-05.3: crash-safe, never a truncated month
