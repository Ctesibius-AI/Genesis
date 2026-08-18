# tests/test_recall_scorer.py
"""DR-33 three-channel honest-empty scorer (spec §4.7a: 3->100, 2->70, 1->30, 0->none)."""
from __future__ import annotations

import pytest

from genesys.recall.scorer import (
    Channel,
    ChannelResult,
    EmptyCause,
    RecallVerdict,
    score_channels,
)


def _r(sem, kw, gr):
    return [ChannelResult(Channel.SEMANTIC, sem), ChannelResult(Channel.KEYWORD, kw),
            ChannelResult(Channel.GRAPH, gr)]


def test_three_channels_score_100_answer():
    v = score_channels(_r(True, True, True))
    assert v.score == 100 and v.label == "answer" and v.served() is True


def test_two_channels_score_70_corroborated_partial():
    v = score_channels(_r(True, False, True))
    assert v.score == 70 and v.label == "corroborated-partial"


def test_one_channel_scores_30_weak_single_source():
    v = score_channels(_r(False, False, True))
    assert v.score == 30 and v.label == "weak/single-source"


def test_zero_channels_is_earned_honest_empty():
    v = score_channels(_r(False, False, False))
    assert v.score == 0 and v.label == "honest-empty" and v.served() is False
    assert v.cause is EmptyCause.ABSENT  # default: genuinely absent


def test_empty_weighted_by_cause_pending_not_absent():
    # just-saved-not-yet-extracted: a queue lag, not an earned absence (do not confabulate).
    v = score_channels(_r(False, False, False), cause=EmptyCause.PENDING)
    assert v.score == 0 and v.cause is EmptyCause.PENDING


def test_per_channel_visibility_is_preserved():
    v = score_channels(_r(True, False, True))
    fired = {c.channel for c in v.channels if c.hit}
    assert fired == {Channel.SEMANTIC, Channel.GRAPH}


def test_scorer_forces_all_three_channels():
    with pytest.raises(ValueError):
        score_channels([ChannelResult(Channel.SEMANTIC, True)])  # missing keyword+graph
