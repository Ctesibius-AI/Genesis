"""Tier -> retrieval-depth mapping (spec §4.7b; design §5 — the retrieval half only).

ConBus's tiers carry two halves (model-routing + retrieval); recall uses ONLY the retrieval
half (design §5). NONE = trivial turn, no read; EPISODIC = the touched episode's facts; DEEP =
self-view identity + episodic + errors (persona-fenced, self-view only §9.1); FULL = the DR-33
three-channel search, top-N.
"""

from __future__ import annotations

from enum import Enum


class Tier(str, Enum):
    NONE = "none"
    EPISODIC = "episodic"
    DEEP = "deep"
    FULL = "full"


class Retrieval(str, Enum):
    NOTHING = "nothing"
    EPISODE_FACTS = "episode_facts"
    IDENTITY_EPISODIC_ERRORS = "identity_episodic_errors"
    THREE_CHANNEL_SEARCH = "three_channel_search"


_DEPTH = {
    Tier.NONE: Retrieval.NOTHING,
    Tier.EPISODIC: Retrieval.EPISODE_FACTS,
    Tier.DEEP: Retrieval.IDENTITY_EPISODIC_ERRORS,
    Tier.FULL: Retrieval.THREE_CHANNEL_SEARCH,
}


def depth_for(tier: Tier) -> Retrieval:
    try:
        return _DEPTH[tier]
    except (KeyError, TypeError):
        raise ValueError(f"unknown recall tier: {tier!r}")


def reads_graph(tier: Tier) -> bool:
    return depth_for(tier) is not Retrieval.NOTHING
