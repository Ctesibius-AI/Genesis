# tests/test_recall_tier.py
"""Tier -> retrieval-depth mapping (spec §4.7b cascade; design §5 — retrieval half only)."""
from __future__ import annotations

import pytest

from genesys.recall.tier import Retrieval, Tier, depth_for, reads_graph


def test_four_tiers_map_to_their_retrieval_depth():
    assert depth_for(Tier.NONE) is Retrieval.NOTHING
    assert depth_for(Tier.EPISODIC) is Retrieval.EPISODE_FACTS
    assert depth_for(Tier.DEEP) is Retrieval.IDENTITY_EPISODIC_ERRORS
    assert depth_for(Tier.FULL) is Retrieval.THREE_CHANNEL_SEARCH


def test_none_tier_does_not_read_the_graph():
    assert reads_graph(Tier.NONE) is False
    for t in (Tier.EPISODIC, Tier.DEEP, Tier.FULL):
        assert reads_graph(t) is True


def test_unknown_tier_raises():
    with pytest.raises(ValueError):
        depth_for("wharrgarbl")  # type: ignore[arg-type]
