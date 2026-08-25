from __future__ import annotations

from pathlib import Path

import pytest

from genesis.extraction.lock import LockHeld, single_instance
from genesis.journal.journal import read_journal


def test_lock_acquires_and_releases(tmp_path: Path):
    with single_instance(tmp_path, ts="2026-08-17T10:00:00+00:00"):
        assert (tmp_path / ".drain.lock").exists()
    assert not (tmp_path / ".drain.lock").exists()  # released on exit


def test_second_instance_raises_and_journals(tmp_path: Path):
    with single_instance(tmp_path, ts="2026-08-17T10:00:00+00:00"):
        with pytest.raises(LockHeld):
            with single_instance(tmp_path, ts="2026-08-17T10:00:01+00:00"):
                pass
    assert any(j.action == "lock-violation" for j in read_journal(tmp_path))


def test_lock_released_even_on_exception(tmp_path: Path):
    with pytest.raises(ValueError):
        with single_instance(tmp_path, ts="2026-08-17T10:00:00+00:00"):
            raise ValueError("boom")
    assert not (tmp_path / ".drain.lock").exists()
