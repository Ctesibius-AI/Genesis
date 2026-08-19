# tests/test_recall_touch.py
"""Rules-first touch detector vs diary anchors (spec §4.7b cascade; design §5c, OQ-1)."""
from __future__ import annotations

from dataclasses import dataclass

from genesys.recall.tier import Tier
from genesys.recall.touch import Touch, detect_touch, is_trivial


@dataclass
class _Anchor:
    anchor: str
    episode_ids: list[str]


ANCHORS = [_Anchor("Phrase invoicing", ["EP-9"]), _Anchor("Mnemon", ["EP-3", "EP-4"])]


def test_anchor_match_yields_episodic_touch():
    t = detect_touch("where did we land on Phrase invoicing?", ANCHORS)
    assert t.touched is True and t.anchor == "Phrase invoicing"
    assert t.tier is Tier.EPISODIC and t.episode_ids == ["EP-9"]


def test_no_anchor_but_substantive_yields_full_search():
    t = detect_touch("what was the FalkorDB pin decision", ANCHORS, substantive=True)
    assert t.touched is False and t.anchor is None and t.tier is Tier.FULL


def test_trivial_turn_yields_none_tier_no_read():
    t = detect_touch("ok", ANCHORS)
    assert t.touched is False and t.tier is Tier.NONE


def test_match_is_whole_word_case_insensitive():
    assert detect_touch("MNEMON is the store", ANCHORS).anchor == "Mnemon"
    # substring inside another word must not match
    assert detect_touch("premnemonic", ANCHORS, substantive=True).tier is Tier.FULL


def test_is_trivial_rules():
    assert is_trivial("ok") is True
    assert is_trivial("") is True
    assert is_trivial("what did we decide about the recall fence last week") is False
