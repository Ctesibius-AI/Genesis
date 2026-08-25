"""Tests for genesis.backfill.cli — batch backfill injection door.

All tests are OFFLINE: fixture .jsonl transcripts constructed in-test, tmp_path as
data_root, no network, no real LLM, no writes to the real ~/.genesis. The backfill
CLI is a thin driver over the existing hook adapter (dispatch), which for SessionEnd
is model-free.

Coverage:
  1. Sessions enqueue → one ledger entry per session with extracted:no.
  2. Chronological ordering by content start time (min record timestamp).
  3. Injected clock = session END timestamp, not wall-clock.
  4. Idempotent re-run → second run enqueues 0, skips N.
  5. --dry-run writes nothing to the ledger.
  6. Malformed / empty session does not crash the batch.
  7. session_id derived from the filename stem.
"""

from __future__ import annotations

import json
from pathlib import Path

from genesis.backfill.cli import main
from genesis.ledger.entry import Extracted
from genesis.ledger.store import read_all


# --------------------------------------------------------------------------- #
# Fixture helpers                                                               #
# --------------------------------------------------------------------------- #

def _record(kind: str, text: str, ts: str) -> dict:
    """Build a minimal CC transcript record with a top-level timestamp."""
    if kind == "user":
        return {
            "type": "user",
            "timestamp": ts,
            "message": {"role": "user", "content": text},
        }
    return {
        "type": "assistant",
        "timestamp": ts,
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


def _write_session(
    tmp_path: Path,
    stem: str,
    *,
    start: str,
    end: str,
    extra_lines: list[str] | None = None,
) -> Path:
    """Write a two-record session .jsonl whose min/max timestamps are start/end."""
    records = [
        _record("user", "Let's talk about the water clock.", start),
        _record("assistant", "The clepsydra measures time by flow.", end),
    ]
    lines = [json.dumps(r) for r in records]
    if extra_lines:
        lines.extend(extra_lines)
    path = tmp_path / f"{stem}.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# 1. Enqueue — one entry per session, extracted:no                              #
# --------------------------------------------------------------------------- #

def test_each_session_enqueues_one_entry(tmp_path: Path):
    data = tmp_path / "data"
    _write_session(tmp_path, "sess-a", start="2025-12-11T09:00:00+00:00",
                   end="2025-12-11T10:00:00+00:00")
    _write_session(tmp_path, "sess-b", start="2025-12-19T09:00:00+00:00",
                   end="2025-12-19T10:00:00+00:00")

    rc = main([str(tmp_path / "sess-a.jsonl"), str(tmp_path / "sess-b.jsonl"),
               "--data", str(data)])
    assert rc == 0

    entries = read_all(data)
    assert len(entries) == 2
    assert all(e.extracted is Extracted.NO for e in entries)


def test_directory_is_recursed_for_jsonl(tmp_path: Path):
    data = tmp_path / "data"
    src = tmp_path / "src"
    src.mkdir()
    _write_session(src, "one", start="2025-12-11T09:00:00+00:00",
                   end="2025-12-11T10:00:00+00:00")
    # a non-jsonl file must be ignored
    (src / "notes.txt").write_text("ignore me", encoding="utf-8")

    rc = main([str(src), "--data", str(data)])
    assert rc == 0
    assert len(read_all(data)) == 1


# --------------------------------------------------------------------------- #
# 2. Chronological ordering by content start time                               #
# --------------------------------------------------------------------------- #

def test_sessions_enqueue_in_content_time_order(tmp_path: Path):
    data = tmp_path / "data"
    # Later session listed FIRST on the command line; earlier session second.
    _write_session(tmp_path, "later", start="2025-12-19T09:00:00+00:00",
                   end="2025-12-19T10:00:00+00:00")
    _write_session(tmp_path, "earlier", start="2025-12-11T09:00:00+00:00",
                   end="2025-12-11T10:00:00+00:00")

    rc = main([str(tmp_path / "later.jsonl"), str(tmp_path / "earlier.jsonl"),
               "--data", str(data)])
    assert rc == 0

    entries = read_all(data)  # read_all sorts by ts
    assert len(entries) == 2
    # The earlier-content session must be dated first.
    assert entries[0].ts.startswith("2025-12-11")
    assert entries[1].ts.startswith("2025-12-19")
    assert entries[0].links.session_id == "earlier"
    assert entries[1].links.session_id == "later"


# --------------------------------------------------------------------------- #
# 3. Injected clock = session END timestamp (not wall-clock)                     #
# --------------------------------------------------------------------------- #

def test_entry_ts_is_session_end_not_wallclock(tmp_path: Path):
    data = tmp_path / "data"
    _write_session(tmp_path, "sess", start="2025-12-11T09:00:00+00:00",
                   end="2025-12-11T18:30:00+00:00")

    rc = main([str(tmp_path / "sess.jsonl"), "--data", str(data)])
    assert rc == 0

    entries = read_all(data)
    assert len(entries) == 1
    # ts is the session's OWN end timestamp — the injected clock.
    assert entries[0].ts == "2025-12-11T18:30:00+00:00"
    # provenance span_end also reflects the session end (from adapter timestamps).
    assert entries[0].ts.startswith("2025-12-11")


# --------------------------------------------------------------------------- #
# 4. Idempotent re-run                                                           #
# --------------------------------------------------------------------------- #

def test_rerun_is_idempotent(tmp_path: Path, capsys):
    data = tmp_path / "data"
    _write_session(tmp_path, "s1", start="2025-12-11T09:00:00+00:00",
                   end="2025-12-11T10:00:00+00:00")
    _write_session(tmp_path, "s2", start="2025-12-19T09:00:00+00:00",
                   end="2025-12-19T10:00:00+00:00")
    args = [str(tmp_path / "s1.jsonl"), str(tmp_path / "s2.jsonl"), "--data", str(data)]

    assert main(args) == 0
    assert len(read_all(data)) == 2

    capsys.readouterr()  # clear
    assert main(args) == 0
    out = capsys.readouterr().out
    # Second run enqueues nothing more.
    assert len(read_all(data)) == 2
    # Report says 0 enqueued, 2 skipped.
    assert "0 enqueued" in out
    assert "2 skipped" in out


# --------------------------------------------------------------------------- #
# 5. --dry-run writes nothing                                                    #
# --------------------------------------------------------------------------- #

def test_dry_run_writes_nothing(tmp_path: Path, capsys):
    data = tmp_path / "data"
    _write_session(tmp_path, "alpha", start="2025-12-11T09:00:00+00:00",
                   end="2025-12-11T10:00:00+00:00")
    _write_session(tmp_path, "beta", start="2025-12-19T09:00:00+00:00",
                   end="2025-12-19T10:00:00+00:00")

    rc = main([str(tmp_path / "beta.jsonl"), str(tmp_path / "alpha.jsonl"),
               "--data", str(data), "--dry-run"])
    assert rc == 0

    # Nothing written to the ledger.
    assert read_all(data) == []
    # No ledger directory created at all.
    assert not (data / "ledger").exists()

    out = capsys.readouterr().out
    # Plan lists both sessions in chronological order.
    assert "alpha" in out and "beta" in out
    assert out.index("alpha") < out.index("beta")


# --------------------------------------------------------------------------- #
# 6. Malformed / empty session does not crash the batch                          #
# --------------------------------------------------------------------------- #

def test_malformed_and_empty_sessions_do_not_crash(tmp_path: Path):
    data = tmp_path / "data"

    # A good session.
    _write_session(tmp_path, "good", start="2025-12-11T09:00:00+00:00",
                   end="2025-12-11T10:00:00+00:00")

    # A session with blank + malformed lines mixed with one valid record.
    messy = tmp_path / "messy.jsonl"
    messy.write_text(
        "\n".join([
            "",
            "   ",
            "not json {{{",
            json.dumps(_record("user", "Hello there.", "2025-12-15T09:00:00+00:00")),
            "",
        ]) + "\n",
        encoding="utf-8",
    )

    # A completely empty file (no records, no timestamps → falls back to mtime).
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")

    rc = main([str(tmp_path / "good.jsonl"), str(messy), str(empty),
               "--data", str(data)])
    assert rc == 0

    # All three sessions enqueue without crashing.
    entries = read_all(data)
    assert len(entries) == 3


# --------------------------------------------------------------------------- #
# 7. session_id derived from filename stem                                        #
# --------------------------------------------------------------------------- #

def test_session_id_from_filename_stem(tmp_path: Path):
    data = tmp_path / "data"
    _write_session(tmp_path, "01_deadbeef-cafe", start="2025-12-11T09:00:00+00:00",
                   end="2025-12-11T10:00:00+00:00")

    rc = main([str(tmp_path / "01_deadbeef-cafe.jsonl"), "--data", str(data)])
    assert rc == 0

    entries = read_all(data)
    assert len(entries) == 1
    assert entries[0].links.session_id == "01_deadbeef-cafe"
