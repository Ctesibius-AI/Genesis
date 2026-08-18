"""Discussion window (spec §10.2, App A.4.8).

The only two occasions a discussion request may be raised: inside the principal's configured
window, or on his summons phrase. Inject-the-clock (`now` is passed).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from genesys.tasks.urgency import parse_iso

_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class WindowRule:
    days: list[str]
    from_: str
    to: str


@dataclass
class DiscussionWindow:
    rules: list[WindowRule] = field(default_factory=list)
    summons_phrases: list[str] = field(default_factory=list)
    idle_timeout_min: int = 15


def in_window(window: DiscussionWindow, now: str) -> bool:
    dt = parse_iso(now)
    day = _WEEKDAYS[dt.weekday()]
    hhmm = f"{dt.hour:02d}:{dt.minute:02d}"
    return any(day in r.days and r.from_ <= hhmm <= r.to for r in window.rules)


def matches_summons(window: DiscussionWindow, text: str) -> bool:
    low = text.lower()
    return any(p.lower() in low for p in window.summons_phrases)


def may_raise(window: DiscussionWindow, *, now: str, text: str = "") -> bool:
    return in_window(window, now) or matches_summons(window, text)
