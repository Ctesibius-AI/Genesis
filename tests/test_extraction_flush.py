from __future__ import annotations

from genesys.extraction.flush import should_flush


def test_window_reached_is_hard_flush():
    assert should_flush(5, "save", window=5) is True
    assert should_flush(3, "save", window=5) is False   # below window, plain save waits


def test_hard_backstops_flush_any_nonempty_queue():
    for t in ("idle", "session-close", "precompact", "night"):
        assert should_flush(1, t) is True
        assert should_flush(0, t) is False              # nothing to flush


def test_departure_is_soft_flush_when_nonempty():
    assert should_flush(1, "departure") is True
    assert should_flush(0, "departure") is False
