"""Backfill --wal: append+annotate unifies with the live path; idempotency preserved (§5)."""
from __future__ import annotations

import json
from pathlib import Path

from genesys.backfill.cli import main
from genesys.ids import episodes_dir
from genesys.ledger.store import read_all
from genesys.wal.annotate import is_annotation
from genesys.wal.record import WalRecord
from genesys.wal.store import read_segment


def _session(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n",
                 encoding="utf-8")
    return p


def test_backfill_wal_appends_and_annotates_no_copy(tmp_path: Path):
    data = tmp_path / "data"
    s = _session(tmp_path, "sess-a.jsonl", "historical content")
    rc = main([str(s), "--data", str(data), "--wal"])
    assert rc == 0
    entries = read_all(data)
    assert len(entries) == 1 and is_annotation(entries[0])
    assert not episodes_dir(data).exists() or list(episodes_dir(data).glob("*.md")) == []
    assert read_segment(data, WalRecord.MEMORY_GRADE, entries[0].ts[:10])


def test_backfill_wal_is_idempotent(tmp_path: Path):
    data = tmp_path / "data"
    s = _session(tmp_path, "sess-a.jsonl", "historical content")
    main([str(s), "--data", str(data), "--wal"])
    main([str(s), "--data", str(data), "--wal"])   # re-run same batch
    assert len(read_all(data)) == 1                # enqueued 0 the second time
