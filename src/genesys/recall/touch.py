"""Rules-first touch detector (spec §4.7b cascade; design §5c, OQ-1).

The cheapest step of the cascade: does the turn TOUCH a diary anchor? Rules-first (OQ-1 bias):
case-insensitive whole-word match of each anchor's name against the turn text — zero latency, no
model. A match routes to EPISODIC (cheap 1-hop expand of the anchor's episodes). No match +
substantive routes to FULL (gated three-channel search). A trivial turn (greeting / ≤ a few
tokens) routes to NONE (no read). A cheap-classifier fallback for paraphrase is DEFERRED (OQ-1) —
add only on evidence rules-first misses recallable touches; not built here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from genesys.recall.tier import Tier

_GREETINGS = {"hi", "hey", "hello", "ok", "okay", "thanks", "thx", "yes", "no", "yep", "nope"}


@dataclass
class Touch:
    touched: bool
    anchor: str | None
    tier: Tier
    episode_ids: list[str] = field(default_factory=list)


def is_trivial(text: str) -> bool:
    tokens = text.strip().lower().split()
    if not tokens:
        return True
    if len(tokens) <= 2 and all(t.strip(".,!?") in _GREETINGS or len(t) <= 3 for t in tokens):
        return True
    return False


def _matches(name: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(name)}\b", text, flags=re.IGNORECASE) is not None


def detect_touch(text: str, anchors, *, substantive: bool | None = None) -> Touch:
    for a in anchors:
        if _matches(a.anchor, text):
            return Touch(True, a.anchor, Tier.EPISODIC, list(a.episode_ids))
    is_sub = substantive if substantive is not None else not is_trivial(text)
    if is_sub:
        return Touch(False, None, Tier.FULL, [])
    return Touch(False, None, Tier.NONE, [])
