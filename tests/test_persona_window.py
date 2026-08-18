from __future__ import annotations

from genesys.persona.window import (
    DiscussionWindow,
    WindowRule,
    in_window,
    matches_summons,
    may_raise,
)

# 2026-08-17 is a Monday.
_WIN = DiscussionWindow(
    rules=[WindowRule(days=["Mon", "Tue", "Wed", "Thu", "Fri"], from_="21:00", to="23:00")],
    summons_phrases=["let's check our discussion requests"],
    idle_timeout_min=15,
)


def test_in_window_true_inside_slot():
    assert in_window(_WIN, "2026-08-17T21:30:00Z") is True


def test_in_window_false_outside_hours_and_days():
    assert in_window(_WIN, "2026-08-17T10:00:00Z") is False   # Monday but morning
    assert in_window(_WIN, "2026-08-16T21:30:00Z") is False   # Sunday (no rule)


def test_matches_summons_case_insensitive():
    assert matches_summons(_WIN, "hey, LET'S CHECK OUR DISCUSSION REQUESTS now") is True
    assert matches_summons(_WIN, "what's on my plate?") is False


def test_may_raise_either_window_or_summons():
    assert may_raise(_WIN, now="2026-08-17T10:00:00Z", text="let's check our discussion requests") is True
    assert may_raise(_WIN, now="2026-08-17T21:30:00Z") is True
    assert may_raise(_WIN, now="2026-08-17T10:00:00Z") is False
