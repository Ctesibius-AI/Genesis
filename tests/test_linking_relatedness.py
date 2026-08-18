from __future__ import annotations

import pytest

from genesys.linking.relatedness import (
    REFERENCES_MIN,
    SAME_TOPIC_MIN,
    FakeRelatednessScorer,
    real_scorer,
)


def test_thresholds_ordered():
    assert 0.0 < REFERENCES_MIN < SAME_TOPIC_MIN <= 1.0


def test_fake_is_symmetric_and_defaults():
    s = FakeRelatednessScorer(default=0.1)
    s.set("alpha", "beta", 0.8)
    assert s.related("alpha", "beta") == 0.8
    assert s.related("beta", "alpha") == 0.8  # symmetric
    assert s.related("alpha", "gamma") == 0.1  # default


def test_real_scorer_is_a_documented_stub():
    with pytest.raises((RuntimeError, NotImplementedError)):
        real_scorer()
