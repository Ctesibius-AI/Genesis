"""fast_path_save cursor-delta skip (opt-in, backward-compatible) — spec §2.2/§7 item 2."""
from __future__ import annotations

from pathlib import Path

from genesis.ledger.store import read_all
from genesis.save import fast_path_save


def _save(data_root: Path, *, ts, session_id="s1", cursor_delta=False):
    return fast_path_save(
        data_root, raw_span="raw", summary="sum", session_id=session_id,
        speakers=["the principal"], span_start="", span_end="", ts=ts,
        cursor_delta=cursor_delta,
    )


def test_default_behaviour_unchanged_always_saves(tmp_path: Path):
    e1 = _save(tmp_path, ts="2026-08-18T10:00:00+00:00")
    e2 = _save(tmp_path, ts="2026-08-18T10:00:00+00:00")  # same cursor, flag OFF
    assert e1 is not None and e2 is not None
    assert len(read_all(tmp_path)) == 2  # backward-compatible: both saved


def test_cursor_delta_skips_when_nothing_new(tmp_path: Path):
    e1 = _save(tmp_path, ts="2026-08-18T10:00:00+00:00", cursor_delta=True)
    e2 = _save(tmp_path, ts="2026-08-18T10:00:00+00:00", cursor_delta=True)  # not newer
    assert e1 is not None and e2 is None
    assert len(read_all(tmp_path)) == 1  # only the first banked


def test_cursor_delta_saves_when_material_is_newer(tmp_path: Path):
    _save(tmp_path, ts="2026-08-18T10:00:00+00:00", cursor_delta=True)
    e2 = _save(tmp_path, ts="2026-08-18T10:30:00+00:00", cursor_delta=True)  # newer
    assert e2 is not None
    assert len(read_all(tmp_path)) == 2


def test_cursor_delta_is_per_session(tmp_path: Path):
    _save(tmp_path, ts="2026-08-18T10:00:00+00:00", session_id="s1", cursor_delta=True)
    e = _save(tmp_path, ts="2026-08-18T09:00:00+00:00", session_id="s2", cursor_delta=True)
    assert e is not None  # different session -> never skipped by s1's cursor
    assert len(read_all(tmp_path)) == 2
